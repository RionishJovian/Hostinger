"""D1/S1 software boundary: metadata inspection and data-only validation.

No RouterOS bootstrap rendering, command dispatch, account creation, credential
issuance or browser route. Device delivery remains hardware-gated. Never use a
successful TLS read as physical identity or least-privilege proof.
"""
from dataclasses import dataclass,field
import hashlib
import hmac
import json
import re
import time
import ipaddress
from urllib.parse import urlencode,urlparse
from .models import MagicConnectAttempt,MagicConnectEnrollment,RouterPlan,RouterDevice,MagicHub,HubAssignment,User,StaffGrant
from .routeros_adapter import RouterOSError
from .routeros_compatibility import classify_routeros_compatibility

POLICIES={'monitoring':('read','rest-api'),'safe_change':('read','write','rest-api')}


class BootstrapSecurityError(RuntimeError):pass


def provisioning_review(session,plan_id,owner_id,now=None):
    """Recheck stored authority; output a secret-free BLOCKED review, not a token."""
    now=int(time.time() if now is None else now)
    p=session.get(RouterPlan,plan_id);u=session.get(User,owner_id)
    e=session.get(MagicConnectEnrollment,plan_id)
    a=session.get(MagicConnectAttempt,e.attempt_id) if e else None
    r=session.get(RouterDevice,p.router_id) if p else None
    h=session.get(MagicHub,p.hub_id) if p else None
    if not all((p,u,e,a,r,h)) or not u.active or u.role!='sme' or getattr(u,'staff_profile',None) or session.get(StaffGrant,u.id):
        raise BootstrapSecurityError('authorized_original_owner_required')
    if not (u.id==e.owner_id==a.owner_id and u.tenant_id==p.tenant_id==e.tenant_id==a.tenant_id==r.tenant_id and e.site_id==a.site_id==r.site_id and session.get(HubAssignment,(h.id,u.tenant_id))):
        raise BootstrapSecurityError('enrollment_scope_mismatch')
    if not p.reviewed_at or a.status!='approved' or not a.approved_at or a.expires<=now or p.management_lock_reason or p.lifecycle_state in ('management_locked','management_lock_pending','revoked','failed_recovery_required'):
        raise BootstrapSecurityError('fresh_reviewed_authority_required')
    binding={'tenant_id':u.tenant_id,'site_id':r.site_id,'router_id':r.id,'attempt_id':a.id,'plan_id':p.id,'hub_id':h.id,'reviewed_at':p.reviewed_at,'router_public_key':p.router_public_key,'snapshot':p.snapshot,'expected_identity_digest':e.expected_identity_digest}
    digest=hashlib.sha256(json.dumps(binding,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    return {'status':'BLOCKED_HARDWARE_VERIFICATION_REQUIRED','binding_digest':digest,
        'identities':{role:{'username':('mm-monitor-' if role=='monitoring' else 'mm-safechange-')+r.id[:8],'candidate_policies':list(policies),'effective_permissions_verified':False} for role,policies in POLICIES.items()},
        'credential_delivery_enabled':False,'router_writes_enabled':False,'connection_verified':False,
        'remaining_gates':['separate_device_capability','router_tls_trust','confidential_bounded_delivery','S1_effective_permissions','partial_failure_recovery']}


def _rows(value):
    if isinstance(value,dict):return [value]
    if not isinstance(value,list) or any(not isinstance(x,dict) for x in value):
        raise BootstrapSecurityError('invalid_metadata_response')
    return value


def _restricted(address):
    if not address:return False
    try:
        networks=[ipaddress.ip_network(x.strip(),strict=False) for x in str(address).split(',')]
        return all(n.prefixlen>0 for n in networks)
    except ValueError:return None


def inspect_security_prerequisites(client,router_id):
    """Explicit later-session call, fixed GETs only, no new login/credentials.

Requires an already provisioned dedicated Monitoring credential. Initial local
bootstrap review must NOT depend on this post-provisioning remote inspection.
    """
    c=client.credential
    if urlparse(c.base_url).scheme!='https' or c.verify is False or c.verify is None or not c.verify:
        raise BootstrapSecurityError('certificate_verified_https_required')
    if c.username!='mm-monitor-'+router_id[:8]:raise BootstrapSecurityError('dedicated_monitoring_identity_required')
    def read(menu,fields,**query):
        try:return _rows(client.get(menu+'?'+urlencode({'.proplist':','.join(fields),**query})))
        except RouterOSError:return None
    resource=read('system/resource',('version','architecture-name'))
    wg=read('interface/wireguard',('name',))
    services=read('ip/service',('name','disabled','certificate','tls-version','address'),name='www-ssl')
    web=read('ip/service/webserver',('rest-secure','rest-plain'))
    certs=read('certificate',('name','trusted','invalid','expired','key-usage','invalid-before','invalid-after','trust-store'))
    group_rows=read('user/group',('name','policy'))
    identities={}
    for role,prefix in [('monitoring','mm-monitor-'),('safe_change','mm-safechange-')]:
        users=read('user',('group','disabled','address'),name=prefix+router_id[:8])
        user=users[0] if users and len(users)==1 else None
        group=next((x for x in (group_rows or []) if user and x.get('name')==user.get('group')),None)
        policy=set(str(group.get('policy','')).split(',')) if group else set()
        identities[role]={'present':True if user else (False if users==[] else None),
            'disabled':user.get('disabled') if user else None,'source_restricted':_restricted(user.get('address')) if user else None,
            'candidate_policy_match':policy==set(POLICIES[role]) if group else None,'effective_permissions':'INCONCLUSIVE'}
    service=services[0] if services and len(services)==1 else {}
    cert=next((x for x in (certs or []) if x.get('name')==service.get('certificate')),None)
    identity=resource[0] if resource and len(resource)==1 else {}
    compatibility=classify_routeros_compatibility(identity,{'wireguard':wg is not None},{'scheme':'https','tls_verified':resource is not None},read_access_verified=resource is not None)
    return {'stage':'post_provisioning_security_inspection','checked_at':int(time.time()),
        'authenticated_tls_read':'PASS' if resource is not None else 'INCONCLUSIVE',
        'compatibility':compatibility,'https_service_enabled':service.get('disabled')=='false' if service else None,
        'certificate_assigned':bool(service.get('certificate') not in (None,'','none')) if service else None,
        'certificate_metadata_available':cert is not None,'rest_secure':(web or [{}])[0].get('rest-secure'),
        'identities':identities,'D1':'BLOCKED_HARDWARE_VERIFICATION_REQUIRED','S1':'INCONCLUSIVE',
        'router_configuration_changed':False,'connection_verified':False}


@dataclass(frozen=True,repr=False)
class ValidatedIdentityDelivery:
    """Internal-only parsed data; safe repr never includes reusable secrets."""
    binding_digest:str
    monitoring_password:str=field(repr=False)
    safe_change_password:str=field(repr=False)
    def __repr__(self):return '<ValidatedIdentityDelivery REDACTED; dispatch disabled>'


def validate_identity_delivery(raw:bytes,review:dict):
    """Synthetic/offline validator only; does not issue or deliver credentials."""
    if not isinstance(raw,bytes) or not 0<len(raw)<=4096:raise BootstrapSecurityError('invalid_delivery_envelope')
    def unique(items):
        result={}
        for key,value in items:
            if key in result:raise BootstrapSecurityError('invalid_delivery_envelope')
            result[key]=value
        return result
    try:
        value=json.loads(raw,object_pairs_hook=unique)
        if not isinstance(value,dict) or set(value)!={'version','binding_digest','identities'} or type(value['version']) is not int or value['version']!=1:raise ValueError()
        if not isinstance(value['binding_digest'],str) or not hmac.compare_digest(value['binding_digest'],review['binding_digest']):raise ValueError()
        if not isinstance(value['identities'],dict) or set(value['identities'])!=set(POLICIES):raise ValueError()
        passwords=[]
        for role in POLICIES:
            identity=value['identities'][role];expected=review['identities'][role]
            if not isinstance(identity,dict) or set(identity)!={'username','policies','password'} or identity['username']!=expected['username'] or identity['policies']!=expected['candidate_policies']:raise ValueError()
            secret=identity['password']
            if not isinstance(secret,str) or not re.fullmatch(r'[A-Za-z0-9_-]{43,128}',secret):raise ValueError()
            passwords.append(secret)
        if hmac.compare_digest(*passwords):raise ValueError()
        return ValidatedIdentityDelivery(value['binding_digest'],*passwords)
    except (ValueError,KeyError,TypeError,UnicodeDecodeError):
        raise BootstrapSecurityError('invalid_delivery_envelope') from None


def dispatch_identity_provisioning(*args,**kwargs):
    # Deliberately not controlled by an environment flag or browser parameter.
    raise BootstrapSecurityError('D1_S1_hardware_acceptance_required_no_router_writes')
