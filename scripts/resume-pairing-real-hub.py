"""Finish only outstanding gates after the preserved test-clock fixture failure.

Existing synthetic DB/namespace only. No interface creation or transport retest.
New result directory; never overwrite the stopped run's evidence. Fixture-only
password rotation permits actual login without persisting plaintext credentials.
"""
import importlib.util
import json
import logging
import os
from pathlib import Path
import platform
import secrets
import shutil
import sys
import tempfile
import time
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
spec=importlib.util.spec_from_file_location('real_pairing',ROOT/'scripts/verify-pairing-real-hub.py')
t=importlib.util.module_from_spec(spec);spec.loader.exec_module(t)
from fastapi.testclient import TestClient
from sqlalchemy import select
from backend.app import make_app,HASHER
from backend.models import User,MagicHub,RouterPlan,MagicConnectAttempt,MagicConnectEnrollment,MagicConnectEvent,Audit
from backend.hub_orchestrator import HubPeerOrchestrator,HostOperationPolicy
from backend.wireguard_hub import WireGuardHubAdapter


def main():
    t.require(platform.system()=='Linux' and os.geteuid()==0,'linux_guest_root_required')
    t.require(Path('/etc/mikromagic-wg-development').read_text().strip()=='mikromagic-wg-dev','dedicated_vm_required')
    source=Path(sys.argv[1])
    t.require(source.parent==Path('/var/tmp') and source.name.startswith('mikromagic-pairing-evidence-') and not source.is_symlink(),'protected_previous_evidence_required')
    t.require(source.stat().st_uid==0 and source.stat().st_mode & 0o077==0,'previous_evidence_private')
    previous=json.loads((source/'result.json').read_text())
    t.require(previous.get('failure')=='expiry_exact_600_second_boundary_rejected','specific_clock_fixture_failure_required')
    db=source/'synthetic-authentication.sqlite3'
    t.require(db.is_file() and not db.is_symlink(),'existing_synthetic_database_required')
    os.umask(0o077)
    directory=Path(tempfile.mkdtemp(prefix='mikromagic-pairing-continuation-',dir='/var/tmp'))
    t.results.update(evidence_directory=str(directory),previous_evidence_directory=str(source))
    for logger in ('httpx','httpcore'):logging.getLogger(logger).setLevel(logging.CRITICAL)
    adapter=WireGuardHubAdapter(shutil.which('wg'),t.runner)
    baseline=adapter._peers(t.INTERFACE)
    t.require(len(baseline[0])==2,'preserved_guard_and_clock_fixture_peer')
    app=make_app('sqlite:///'+str(db),initialize=False)
    app.state.magic_connect_pairing_enabled=True  # Approved isolated lab workflow only.
    app.state.magic_hub_orchestrator=HubPeerOrchestrator(adapter,HostOperationPolicy('isolated-magic-connect-test',True,True,t.INTERFACE),clock=lambda:time.time())
    passwords={}
    with app.state.factory() as session:
        for name,tenant in [('owner','tenant-a'),('other','tenant-b')]:
            user=session.scalar(select(User).where(User.username=='isolated-pairing-'+name))
            t.require(user is not None and user.role=='sme' and user.tenant_id==tenant,'synthetic_fixture_identity_'+name)
            passwords[name]=secrets.token_urlsafe(32)
            user.password_hash=HASHER.hash(passwords[name])
        hub=session.scalar(select(MagicHub))
        hub_id=hub.id
        t.require(adapter.verify_hub_identity(t.INTERFACE,hub.public_key),'assigned_real_hub_identity_verified')
        # Exact prior DB is preserved; fixture passwords only, no session deletion.
        session.commit()
    with TestClient(app) as client:
        def call(method,path,expected,label,headers=None,body=None):
            response=client.request(method,path,headers=headers,json=body)
            if response.status_code!=expected:
                t.results['failed_http_status']=response.status_code
                t.results['expected_http_status']=expected
            t.require(response.status_code==expected,label)
            return response.json()
        headers={}
        for name in passwords:
            login=call('POST','/v1/auth/login',200,'actual_password_login_'+name,body={'username':'isolated-pairing-'+name,'password':passwords[name]})
            headers[name]={'Authorization':'Bearer '+login['access_token']}
        passwords.clear();owner=headers['owner']
        with app.state.factory() as session:
            original=session.scalar(select(MagicConnectAttempt).where(MagicConnectAttempt.router_name=='primary'))
            site=original.site_id
        def scenario(name):
            router=call('POST','/v1/routers',201,'router_'+name,owner,{'site_id':site,'name':name,'model':'synthetic-linux-only','reported_routeros':''})['id']
            key=t.public_key()
            p=call('POST',f'/v1/routers/{router}/plan',201,'plan_'+name,owner,{'hub_id':hub_id,'router_public_key':key})
            call('POST',f"/v1/router-plans/{p['id']}/review",200,'review_'+name,owner,{'confirmed_review':True})
            a=call('POST',f'/v1/sites/{site}/magic-connect/attempts',201,'pairing_'+name,owner,{'router_name':name})
            t.require(a['expires']-a['created']==600,'exact_ten_minutes_'+name)
            tech=call('POST','/v1/magic-connect/claim',200,'claim_'+name,body={'code':a['manual_code']})
            call('POST',f"/v1/magic-connect/attempts/{a['id']}/approve",200,'owner_approval_'+name,owner,{'comparison_confirmed':True})
            return p,a,key,{'Authorization':'Bearer '+tech['technician_session']}
        def provision(p,expected=200,key='continuation-enrollment-001',label='peer_provisioned'):
            return call('POST',f"/v1/router-plans/{p['id']}/hub-peer/provision",expected,label,owner,{'confirmed':True,'idempotency_key':key})
        ep,ea,_,tech=scenario('controlled-expiry-continuation')
        with patch('time.time',return_value=ea['created']+599):
            call('POST',f"/v1/magic-connect/attempts/{ea['id']}/enrollment",201,'binding_before_expiry',owner,{'plan_id':ep['id']})
        before=t.mutations
        with patch('time.time',return_value=ea['created']+600):
            provision(ep,403,key='expired-continuation-001',label='expiry_exact_600_second_boundary_rejected')
            call('GET','/v1/magic-connect/technician/status',401,'expired_technician_session_rejected',tech)
        t.require(t.mutations==before and adapter._peers(t.INTERFACE)==baseline,'expiry_rejection_no_kernel_changes')
        p,a,key,_=scenario('authorized-continuation')
        call('POST',f"/v1/magic-connect/attempts/{a['id']}/enrollment",201,'exact_enrollment_binding',owner,{'plan_id':p['id']})
        created=provision(p)
        t.require(t.mutations==before+1,'authenticated_api_causes_exactly_one_real_peer_write')
        t.require(created['state']=='awaiting_handshake' and not created['connection_verified'],'peer_provisioned_not_router_connected')
        t.require(adapter.observe_peer(t.INTERFACE,key,p['address']+'/32',t.POOL)['peer_found'],'real_enrolled_peer_readback')
        repeated=provision(p)
        t.require(repeated['replayed'] and t.mutations==before+1,'same_operation_retry_has_no_kernel_write')
        provision(p,409,key='different-operation-001',label='different_operation_replay_rejected')
        observed=call('POST',f"/v1/router-plans/{p['id']}/hub-peer/observe",200,'real_handshake_observation',owner)
        t.require(not observed['connection_verified'],'no_router_connected_claim_from_enrollment')
        with app.state.factory() as session:
            session.get(RouterPlan,p['id']).lifecycle_state='provisioning_peer';session.commit()
        recovered=call('POST',f"/v1/router-plans/{p['id']}/hub-peer/recovery-check",200,'authenticated_recovery_readback',owner,{'confirmed':True})
        t.require(recovered['recovery_readback']=='recorded_peer_present' and not recovered['retry_allowed'],'recovery_does_not_blindly_reapply')
        t.require(t.mutations==before+1,'recovery_is_read_only')
        call('POST',f"/v1/router-plans/{p['id']}/emergency-lock",404,'cross_tenant_revocation_rejected',headers['other'],{'confirmed':True,'reason':'Synthetic security test'})
        locked=call('POST',f"/v1/router-plans/{p['id']}/emergency-lock",200,'authenticated_emergency_revocation',owner,{'confirmed':True,'reason':'Synthetic isolated acceptance incident'})
        t.require(locked['state']=='management_locked' and not locked['on_router_cleanup_verified'],'revocation_reports_honest_scope')
        t.require(adapter._peers(t.INTERFACE)==baseline,'all_preexisting_synthetic_peers_preserved')
        t.require(not adapter.observe_peer(t.INTERFACE,key,p['address']+'/32',t.POOL)['peer_found'],'target_peer_absent_after_revocation')
        provision(p,409,label='locked_peer_cannot_be_reprovisioned')
        with app.state.factory() as session:
            enrollment=session.get(MagicConnectEnrollment,p['id'])
            t.require(bool(enrollment.consumed_at and enrollment.peer_provisioned_at),'consumption_and_peer_milestones_persisted')
            t.require(session.get(MagicConnectAttempt,a['id']).enrollment_state=='management_locked','pairing_state_synchronized')
            t.require(bool(session.scalar(select(MagicConnectEvent).where(MagicConnectEvent.attempt_id==a['id'],MagicConnectEvent.event=='peer_operation_claimed'))),'durable_claim_audit_present')
            actions={row.action for row in session.scalars(select(Audit))}
            t.require({'magic_connect_technician_approved','magic_connect_enrollment_bound','hub_peer_provisioned','hub_peer_recovery_read','hub_management_emergency_lock'}<=actions,'application_audit_chain_present')
    app.state.engine.dispose()
    t.results.update(status='PASS',routeros_management='NOT_TESTED',handshake_traffic_retest='NOT_REPEATED',recovery_interruption='SIMULATED_STATE_REAL_KERNEL_READBACK',database='EXISTING_GUEST_ONLY_SYNTHETIC_SQLITE',public_api_listener='NONE_ASGI_IN_PROCESS',real_peer_mutations=t.mutations)


if __name__=='__main__':
    try:main()
    except Exception as exc:
        t.results.update(status='FAIL',failure=str(exc) if type(exc) is RuntimeError else 'sanitized_'+type(exc).__name__)
    if 'evidence_directory' in t.results:
        (Path(t.results['evidence_directory'])/'result.json').write_text(json.dumps(t.results,indent=2)+'\n')
    print(json.dumps(t.results,indent=2))
    sys.exit(0 if t.results.get('status')=='PASS' else 1)
