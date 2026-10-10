"""Authenticated application -> REAL existing development WireGuard interface.

No HTTP listener, new interface, new VM, transport retest or RouterOS operation.
Requires the approved existing VM and namespaces. Secrets never leave memory.
On failure leave all synthetic peer state/evidence intact and stop.
"""
import hashlib
import json
import logging
import os
from pathlib import Path
import platform
import secrets
import shutil
import subprocess
import sys
import tempfile
import time
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
from sqlalchemy import select
from backend.app import make_app,HASHER
from backend.models import Tenant,User,RouterPlan,MagicConnectAttempt,MagicConnectEnrollment,MagicConnectEvent,Audit,HubAssignment
from backend.hub_orchestrator import HubPeerOrchestrator,HostOperationPolicy
from backend.wireguard_hub import WireGuardHubAdapter

NS, INTERFACE, POOL = 'mm-wg-hub','mm-dev-hub','10.240.231.0/24'
results={}
mutations=0


def require(ok,label):
    if not ok:raise RuntimeError(label)
    results[label]='PASS'


def runner(args,**kwargs):
    global mutations
    if len(args)>1 and args[1]=='set':mutations+=1
    return subprocess.run(['ip','netns','exec',NS,*args],**kwargs)


def public_key():
    private=subprocess.run(['wg','genkey'],capture_output=True,text=True,timeout=5,check=True).stdout
    public=subprocess.run(['wg','pubkey'],input=private,capture_output=True,text=True,timeout=5,check=True).stdout.strip()
    private=None
    return public


def main():
    require(platform.system()=='Linux' and os.geteuid()==0,'linux_guest_root_required')
    marker=Path('/etc/mikromagic-wg-development')
    require(marker.is_file() and marker.read_text().strip()=='mikromagic-wg-dev','dedicated_vm_required')
    for logger in ('httpx','httpcore'):logging.getLogger(logger).setLevel(logging.CRITICAL)
    os.umask(0o077)
    directory=Path(tempfile.mkdtemp(prefix='mikromagic-pairing-evidence-',dir='/var/tmp'))
    results['evidence_directory']=str(directory)
    adapter=WireGuardHubAdapter(shutil.which('wg'),runner)
    hub_key=adapter._run(INTERFACE,'public-key').strip()
    require(not adapter._peers(INTERFACE)[0],'expected_previous_revoked_hub_state')
    guard_key=public_key()
    adapter.provision_peer(INTERFACE,guard_key,'10.240.231.250/32',POOL)
    guard_snapshot=adapter._peers(INTERFACE)
    app=make_app('sqlite:///'+str(directory/'synthetic-authentication.sqlite3'),initialize=True)
    app.state.magic_connect_pairing_enabled=True  # Approved isolated lab workflow only.
    # Resolve the injected clock dynamically so API and orchestrator use the
    # same controlled time in boundary tests (the production default is real).
    service=HubPeerOrchestrator(adapter,HostOperationPolicy('isolated-magic-connect-test',True,True,INTERFACE),clock=lambda:time.time())
    app.state.magic_hub_orchestrator=service
    users={};passwords={}
    with app.state.factory() as session:
        session.add_all([Tenant(id='tenant-a',name='Synthetic A'),Tenant(id='tenant-b',name='Synthetic B')]);session.flush()
        for name,role,tenant in [('owner','sme','tenant-a'),('sibling','sme','tenant-a'),('other','sme','tenant-b'),('guest','guest','tenant-a'),('platform','platform',None)]:
            passwords[name]=secrets.token_urlsafe(32)
            user=User(username='isolated-pairing-'+name,role=role,tenant_id=tenant,password_hash=HASHER.hash(passwords[name]),active=True)
            session.add(user);session.flush();users[name]=user.id
        session.commit()
    with TestClient(app) as client:
        def call(method,path,expected,label,headers=None,body=None):
            response=client.request(method,path,headers=headers,json=body)
            require(response.status_code==expected,label)
            return response.json()
        headers={}
        for name in users:
            response=call('POST','/v1/auth/login',200,'actual_password_login_'+name,body={'username':'isolated-pairing-'+name,'password':passwords[name]})
            headers[name]={'Authorization':'Bearer '+response['access_token']}
        passwords.clear()
        owner,platform_h=headers['owner'],headers['platform']
        site=call('POST','/v1/sites',201,'site_created',owner,{'name':'Synthetic pairing site'})['id']
        site2=call('POST','/v1/sites',201,'second_site_created',owner,{'name':'Synthetic other site'})['id']
        hub=call('POST','/v1/hubs',201,'development_hub_registered',platform_h,{'name':'Isolated existing Linux Hub','endpoint':'development.example.com','port':51820,'pool':POOL,'public_key':hub_key,'interface_name':INTERFACE})['id']
        call('POST',f'/v1/hubs/{hub}/assignments',200,'development_hub_assigned',platform_h,{'tenant_id':'tenant-a'})

        def plan(name,site_id=site,review=True):
            router=call('POST','/v1/routers',201,'synthetic_router_registered_'+name,owner,{'site_id':site_id,'name':name,'model':'synthetic-linux-only','reported_routeros':''})['id']
            public=public_key()
            p=call('POST',f'/v1/routers/{router}/plan',201,'plan_created_'+name,owner,{'hub_id':hub,'router_public_key':public})
            if review:call('POST',f"/v1/router-plans/{p['id']}/review",200,'plan_reviewed_'+name,owner,{'confirmed_review':True})
            return p,public
        def attempt(name,site_id=site,approve=True):
            a=call('POST',f'/v1/sites/{site_id}/magic-connect/attempts',201,'pairing_created_'+name,owner,{'router_name':name})
            require(a['expires']-a['created']==600,'exact_600_second_pairing_'+name)
            c=call('POST','/v1/magic-connect/claim',200,'technician_claim_'+name,body={'code':a['manual_code']})
            if approve:call('POST',f"/v1/magic-connect/attempts/{a['id']}/approve",200,'owner_approval_'+name,owner,{'comparison_confirmed':True})
            return a,{'Authorization':'Bearer '+c['technician_session']}
        def bind(a,p,expected=201,label='enrollment_bound'):
            return call('POST',f"/v1/magic-connect/attempts/{a['id']}/enrollment",expected,label,owner,{'plan_id':p['id']})
        def provision(p,expected=200,key='authenticated-enrollment-001',who=owner,label='peer_provisioned'):
            return call('POST',f"/v1/router-plans/{p['id']}/hub-peer/provision",expected,label,who,{'confirmed':True,'idempotency_key':key})
        def unchanged(label):require(adapter._peers(INTERFACE)==guard_snapshot,label)

        p,key=plan('primary',review=False)
        a,technician=attempt('primary',approve=False)
        call('POST','/v1/magic-connect/claim',409,'pairing_claim_replay_rejected',body={'code':a['manual_code']})
        for who,label,code in [(None,'anonymous',401),(headers['guest'],'guest',403),(platform_h,'platform',403),(headers['other'],'cross_tenant',404),(technician,'technician',401)]:
            provision(p,code,who=who,label=label+'_provision_rejected')
        call('POST',f"/v1/magic-connect/attempts/{a['id']}/approve",401,'technician_cannot_approve',technician,{'comparison_confirmed':True})
        call('POST',f"/v1/magic-connect/attempts/{a['id']}/approve",404,'different_owner_same_tenant_cannot_approve',headers['sibling'],{'comparison_confirmed':True})
        bind(a,p,409,'unapproved_pairing_rejected')
        call('POST',f"/v1/magic-connect/attempts/{a['id']}/approve",200,'primary_owner_approval',owner,{'comparison_confirmed':True})
        provision(p,403,label='unreviewed_plan_rejected')
        bind(a,p,409,'unreviewed_binding_rejected')
        call('POST',f"/v1/router-plans/{p['id']}/review",200,'primary_review',owner,{'confirmed_review':True})
        provision(p,403,label='approval_without_enrollment_binding_rejected')
        other_site_plan,_=plan('different-site',site2)
        bind(a,other_site_plan,409,'cross_site_binding_rejected')
        call('POST',f"/v1/magic-connect/attempts/{a['id']}/enrollment",404,'cross_tenant_binding_rejected',headers['other'],{'plan_id':p['id']})
        bind(a,p)
        require(bind(a,p)['replayed'],'same_binding_idempotent')
        duplicate_plan,_=plan('duplicate-target')
        bind(a,duplicate_plan,409,'same_authorization_other_plan_rejected')
        with app.state.factory() as session:
            assignment=session.get(HubAssignment,(hub,'tenant-a'));session.delete(assignment);session.commit()
        provision(p,404,label='unassigned_hub_rejected')
        call('POST',f'/v1/hubs/{hub}/assignments',200,'restore_synthetic_hub_assignment',platform_h,{'tenant_id':'tenant-a'})
        from backend.models import MagicHub
        with app.state.factory() as session:
            session.get(MagicHub,hub).public_key=public_key();session.commit()
        provision(p,503,label='actual_hub_identity_mismatch_rejected')
        with app.state.factory() as session:
            session.get(MagicHub,hub).public_key=hub_key;session.commit()
        unchanged('all_unauthorized_requests_leave_kernel_unchanged')

        denied_plan,_=plan('denied');denied,_=attempt('denied',approve=False)
        call('POST',f"/v1/magic-connect/attempts/{denied['id']}/deny",200,'owner_denial',owner)
        bind(denied,denied_plan,409,'denied_enrollment_rejected')
        cancelled_plan,_=plan('cancelled');cancelled,_=attempt('cancelled');bind(cancelled,cancelled_plan)
        call('POST',f"/v1/magic-connect/attempts/{cancelled['id']}/cancel",200,'owner_cancellation',owner)
        provision(cancelled_plan,403,key='cancelled-operation-001',label='cancelled_enrollment_rejected')
        expired_plan,_=plan('expired');expired,expired_technician=attempt('expired')
        # Controlled clock only: real authentication, database and wg remain in use.
        with patch('time.time',return_value=expired['created']+599):bind(expired,expired_plan)
        with patch('time.time',return_value=expired['created']+600):
            provision(expired_plan,403,key='expired-operation-001',label='expiry_exact_600_second_boundary_rejected')
            call('GET','/v1/magic-connect/technician/status',401,'expired_technician_session_rejected',expired_technician)
        unchanged('closed_authorizations_leave_kernel_unchanged')

        before=mutations
        created=provision(p)
        require(mutations==before+1,'authenticated_api_causes_exactly_one_real_peer_write')
        require(created['state']=='awaiting_handshake' and not created['connection_verified'],'peer_provisioned_not_router_connected')
        require(adapter.observe_peer(INTERFACE,key,p['address']+'/32',POOL)['peer_found'],'real_enrolled_peer_readback')
        repeated=provision(p)
        require(repeated['replayed'] and mutations==before+1,'same_operation_retry_has_no_kernel_write')
        provision(p,409,key='different-operation-001',label='different_operation_replay_rejected')
        observed=call('POST',f"/v1/router-plans/{p['id']}/hub-peer/observe",200,'real_handshake_observation',owner)
        require(not observed['connection_verified'],'no_router_connected_claim_from_enrollment')
        # Recovery of an intentionally staged interruption reads the REAL peer.
        with app.state.factory() as session:
            row=session.get(RouterPlan,p['id']);row.lifecycle_state='provisioning_peer';session.commit()
        recovered=call('POST',f"/v1/router-plans/{p['id']}/hub-peer/recovery-check",200,'authenticated_recovery_readback',owner,{'confirmed':True})
        require(recovered['recovery_readback']=='recorded_peer_present' and not recovered['retry_allowed'],'recovery_does_not_blindly_reapply')
        require(mutations==before+1,'recovery_is_read_only')
        call('POST',f"/v1/router-plans/{p['id']}/emergency-lock",404,'cross_tenant_revocation_rejected',headers['other'],{'confirmed':True,'reason':'Synthetic security test'})
        locked=call('POST',f"/v1/router-plans/{p['id']}/emergency-lock",200,'authenticated_emergency_revocation',owner,{'confirmed':True,'reason':'Synthetic isolated acceptance incident'})
        require(locked['state']=='management_locked' and not locked['on_router_cleanup_verified'],'revocation_reports_honest_scope')
        unchanged('unrelated_guard_peer_preserved_through_revocation')
        require(not adapter.observe_peer(INTERFACE,key,p['address']+'/32',POOL)['peer_found'],'target_peer_absent_after_revocation')
        provision(p,409,label='locked_peer_cannot_be_reprovisioned')
        with app.state.factory() as session:
            enrollment=session.get(MagicConnectEnrollment,p['id'])
            require(bool(enrollment.consumed_at and enrollment.peer_provisioned_at),'consumption_and_peer_milestones_persisted')
            require(session.get(MagicConnectAttempt,a['id']).enrollment_state=='management_locked','pairing_state_synchronized')
            require(bool(session.scalar(select(MagicConnectEvent).where(MagicConnectEvent.attempt_id==a['id'],MagicConnectEvent.event=='peer_operation_claimed'))),'durable_claim_audit_present')
            actions={row.action for row in session.scalars(select(Audit))}
            require({'magic_connect_technician_approved','magic_connect_enrollment_bound','hub_peer_provisioned','hub_peer_recovery_read','hub_management_emergency_lock'}<=actions,'application_audit_chain_present')
        results['peer_mutation_count_including_guard']=mutations
        results['remaining_peers']=len(adapter._peers(INTERFACE)[0])
        results['guard_peer_fingerprint']=hashlib.sha256(guard_key.encode()).hexdigest()
    app.state.engine.dispose()
    results['status']='PASS';results['routeros_management']='NOT_TESTED'
    results['handshake_traffic_retest']='NOT_REPEATED'
    results['recovery_interruption']='SIMULATED_STATE_REAL_KERNEL_READBACK'
    results['database']='NEW_GUEST_ONLY_SYNTHETIC_SQLITE'
    results['public_api_listener']='NONE_ASGI_IN_PROCESS'


if __name__=='__main__':
    try:main()
    except Exception as exc:
        results['status']='FAIL';results['failure']=str(exc) if type(exc) is RuntimeError else 'sanitized_'+type(exc).__name__
    if 'evidence_directory' in results:
        (Path(results['evidence_directory'])/'result.json').write_text(json.dumps(results,indent=2)+'\n')
    print(json.dumps(results,indent=2))
    sys.exit(0 if results.get('status')=='PASS' else 1)
