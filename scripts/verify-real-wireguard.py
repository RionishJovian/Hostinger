"""REAL Linux kernel WireGuard acceptance; never run on Mac/VPS/router.

Requires a dedicated, approved Lima VM with /etc/mikromagic-wg-development
containing exactly mikromagic-wg-dev. No resources are deleted automatically.
Raw subprocess errors and keys are never emitted. On failure preserve evidence.
"""
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from backend.models import (Base, Tenant, User, Site, RouterDevice, MagicHub,
                            HubAssignment, RouterPlan, MagicConnectAttempt, MagicConnectEnrollment)
from backend.hub_orchestrator import HubPeerOrchestrator, HostOperationPolicy, HubOrchestrationError
from backend.wireguard_hub import WireGuardHubAdapter, HubWireGuardError

HUB, PEER = 'mm-wg-hub', 'mm-wg-peer'
WG_HUB, WG_PEER = 'mm-dev-hub', 'mm-dev-peer'


def run(args, **kwargs):
    kwargs.setdefault('capture_output', True)
    kwargs.setdefault('text', True)
    kwargs.setdefault('timeout', 10)
    kwargs.setdefault('check', False)
    return subprocess.run(args, **kwargs)


def require(ok, name):
    if not ok:
        raise RuntimeError(name)
    results[name] = 'PASS'


def checked(args, **kwargs):
    result = run(args, **kwargs)
    if result.returncode:
        raise RuntimeError('guest_command_failed_no_raw_output')
    return result.stdout.strip()


def ns(name, *args):
    return checked(['ip', 'netns', 'exec', name, *args])


def main():
    require(platform.system() == 'Linux' and os.geteuid() == 0, 'linux_guest_root_required')
    marker = Path('/etc/mikromagic-wg-development')
    require(marker.is_file() and marker.read_text().strip() == 'mikromagic-wg-dev', 'dedicated_vm_marker')
    require(all(shutil.which(x) for x in ('ip', 'wg', 'ping')), 'guest_dependencies')
    existing = checked(['ip', 'netns', 'list']).splitlines()
    require(not any(line.split()[0] in (HUB, PEER) for line in existing), 'no_existing_namespace_collision')
    os.umask(0o077)
    evidence_dir = Path(tempfile.mkdtemp(prefix='mikromagic-wg-evidence-', dir='/var/tmp'))
    secret_dir = Path(tempfile.mkdtemp(prefix='mikromagic-wg-keys-', dir='/run'))
    results['evidence_directory'] = str(evidence_dir)
    for name in (HUB, PEER):
        checked(['ip', 'netns', 'add', name])
        ns(name, 'ip', 'link', 'set', 'lo', 'up')
    # Both endpoints live entirely inside namespaces, never in the VM main netns.
    checked(['ip', '-n', HUB, 'link', 'add', 'mm-under-h', 'type', 'veth', 'peer', 'name', 'mm-under-p', 'netns', PEER])
    public = {}
    for name, under, address, interface, tunnel in (
        (HUB, 'mm-under-h', '192.0.2.1/30', WG_HUB, '10.240.231.1/32'),
        (PEER, 'mm-under-p', '192.0.2.2/30', WG_PEER, '10.240.231.2/32'),
    ):
        ns(name, 'ip', 'address', 'add', address, 'dev', under)
        ns(name, 'ip', 'link', 'set', under, 'up')
        ns(name, 'ip', 'link', 'add', interface, 'type', 'wireguard')
        # Synthetic private keys generated in their own peer namespace; not returned.
        private = ns(name, 'wg', 'genkey')
        path = secret_dir / name
        path.write_text(private + '\n'); path.chmod(0o600)
        public[name] = checked(['ip', 'netns', 'exec', name, 'wg', 'pubkey'], input=private+'\n')
        private = None
        ns(name, 'wg', 'set', interface, 'private-key', str(path), 'listen-port', '51820')
        ns(name, 'ip', 'address', 'add', tunnel, 'dev', interface)
        ns(name, 'ip', 'link', 'set', interface, 'up')
        other = '10.240.231.2/32' if name == HUB else '10.240.231.1/32'
        ns(name, 'ip', 'route', 'add', other, 'dev', interface)
        require(not ns(name, 'ip', 'route', 'show', 'default') and not ns(name, 'ip', '-6', 'route', 'show', 'default'), name+'_no_default_route')
    engine = create_engine('sqlite:///'+str(evidence_dir/'synthetic-lifecycle.sqlite3'))
    Base.metadata.create_all(engine)
    now = int(time.time())
    with Session(engine, expire_on_commit=False) as session:
        session.add_all([
            Tenant(id='t',name='Synthetic'), User(id='u',username='synthetic-no-login',password_hash='disabled',role='sme',tenant_id='t',active=True),
            Site(id='s',tenant_id='t',name='Synthetic',timezone='UTC',created=now),
            RouterDevice(id='r',tenant_id='t',site_id='s',name='Linux transport only',model='synthetic-linux',reported_routeros='none',registered_by='u',created=now),
            MagicHub(id='h',name='Isolated',endpoint='test.invalid',port=51820,pool='10.240.231.0/24',public_key=public[HUB],interface_name=WG_HUB,next_host=3,created=now),
            HubAssignment(hub_id='h',tenant_id='t',created=now),
            RouterPlan(id='p',tenant_id='t',router_id='r',hub_id='h',router_public_key=public[PEER],address='10.240.231.2',snapshot={},created=now,reviewed_at=now,lifecycle_state='awaiting_bootstrap'),
            MagicConnectAttempt(id='a',tenant_id='t',site_id='s',owner_id='u',router_name='Linux transport only',code_hash='f'*64,comparison_code='000000',status='approved',approved_at=now,created=now,expires=now+600),
            MagicConnectEnrollment(plan_id='p',attempt_id='a',tenant_id='t',site_id='s',owner_id='u',created=now),
        ]); session.commit()
        plan, hub = session.get(RouterPlan,'p'), session.get(MagicHub,'h')
        def runner(args, **kwargs): return run(['ip','netns','exec',HUB,*args], **kwargs)
        adapter = WireGuardHubAdapter(shutil.which('wg'), runner)
        service = HubPeerOrchestrator(adapter,HostOperationPolicy('isolated-magic-connect-test',True,True,WG_HUB))
        gated = HubPeerOrchestrator(adapter,HostOperationPolicy('isolated-magic-connect-test',True,True,'wrong-interface'))
        try: gated.provision(session,plan,hub,'t',confirmed=True,idempotency_key='synthetic-once')
        except HubOrchestrationError as exc: require(exc.code=='host_peer_interface_not_allowlisted','interface_allowlist')
        else: raise RuntimeError('interface_gate_failed')
        first = service.provision(session,plan,hub,'t',confirmed=True,idempotency_key='synthetic-once'); session.commit()
        require(first['state']=='awaiting_handshake','owner_bound_peer_creation')
        require(service.provision(session,plan,hub,'t',confirmed=True,idempotency_key='synthetic-once')['replayed'],'idempotent_retry')
        # Simulated process interruption, but recovery reads the REAL kernel peer.
        plan.lifecycle_state='provisioning_peer';session.commit()
        require(service.recover(session,plan,hub,'t',confirmed=True)['recovery_readback']=='recorded_peer_present','interrupted_claim_real_readback')
        try: adapter.observe_peer('mm-nonexistent',public[PEER],plan.address+'/32',hub.pool)
        except HubWireGuardError: results['missing_interface_fail_closed']='PASS'
        else: raise RuntimeError('missing_interface_unexpectedly_available')
        require(not service.observe(session,plan,hub,'t')['connection_verified'],'no_false_connection_before_handshake')
        ns(PEER,'wg','set',WG_PEER,'peer',public[HUB],'allowed-ips','10.240.231.1/32','endpoint','192.0.2.1:51820','persistent-keepalive','1')
        require(run(['ip','netns','exec',PEER,'ping','-c','3','-W','3','10.240.231.1'],timeout=15).returncode==0,'peer_to_hub_traffic')
        require(run(['ip','netns','exec',HUB,'ping','-c','3','-W','3','10.240.231.2'],timeout=15).returncode==0,'hub_to_peer_traffic')
        observation=service.observe(session,plan,hub,'t'); session.commit()
        require(observation['evidence']['fresh_handshake'],'real_fresh_handshake')
        require(observation['state']=='verifying_management' and not observation['connection_verified'],'linux_transport_not_routeros_verified')
        counters=ns(HUB,'wg','show',WG_HUB,'transfer').splitlines()
        require(any(len(x.split())==3 and int(x.split()[1])>0 and int(x.split()[2])>0 for x in counters),'bidirectional_encrypted_counters')
        # Real conflict readback: existing key may not be silently reassigned.
        try: adapter.provision_peer(WG_HUB,public[PEER],'10.240.231.3/32',hub.pool)
        except HubWireGuardError: results['conflict_rejected']='PASS'
        else: raise RuntimeError('conflicting_allocation_accepted')
        require(adapter.revoke_peer(WG_HUB,public[PEER],plan.address+'/32',hub.pool)['result']=='revoked','peer_remove_readback')
        require(not adapter.observe_peer(WG_HUB,public[PEER],plan.address+'/32',hub.pool)['peer_found'],'peer_absent_after_remove')
        adapter.provision_peer(WG_HUB,public[PEER],plan.address+'/32',hub.pool)
        require(service.emergency_lock(session,plan,hub,'t',actor_id='u',reason='Synthetic acceptance emergency revocation',confirmed=True)['state']=='management_locked','emergency_revocation')
        session.commit()
        require(not adapter.observe_peer(WG_HUB,public[PEER],plan.address+'/32',hub.pool)['peer_found'],'emergency_removal_readback')
        require(run(['ip','netns','exec',HUB,'ping','-c','1','-W','2','10.240.231.2']).returncode!=0,'traffic_denied_after_revocation')
    results['status']='PASS'
    results['routeros_management']='NOT_TESTED'
    results['resources_preserved']=True
    (evidence_dir/'result.json').write_text(json.dumps(results,indent=2)+'\n')


results = {}
if __name__ == '__main__':
    try: main()
    except Exception as exc:
        results['status']='BLOCKED_OR_FAILED'
        # Only our own constant RuntimeError labels are safe to print.
        results['failure']=str(exc) if type(exc) is RuntimeError else 'sanitized_'+type(exc).__name__
        if 'evidence_directory' in results:
            (Path(results['evidence_directory'])/'result.json').write_text(json.dumps(results,indent=2)+'\n')
    print(json.dumps(results,indent=2))
    sys.exit(0 if results.get('status')=='PASS' else 1)
