"""WireGuard plans and explicitly gated Hub peer lifecycle."""
import base64,ipaddress,re,time,os
from fastapi import Depends,HTTPException
from pydantic import Field,field_validator
from typing import Literal
from sqlalchemy import select,update
from sqlalchemy.exc import IntegrityError
from .schemas import Strict
from .models import MagicHub,HubAssignment,RouterPlan,RouterDevice,Tenant,SitePortal,PortalSettings,MagicConnectAttempt,MagicConnectEnrollment
from .enrollment import sync_enrollment_state,enrollment_milestones
from .wireguard_hub import hub_adapter_from_environment
from .bootstrap_security import provisioning_review
from .hub_orchestrator import HubPeerOrchestrator,HostOperationPolicy,HubOrchestrationError,connection_is_fresh

def router_interface(router_id):return 'mm-'+router_id[:8]
PRIVATE=[ipaddress.ip_network(x) for x in ['10.0.0.0/8','172.16.0.0/12','192.168.0.0/16']]
def public_key(value):
 try:
  raw=base64.b64decode(value,validate=True)
  if len(raw)!=32 or raw==bytes(32) or base64.b64encode(raw).decode()!=value:raise ValueError()
 except (ValueError,TypeError):raise ValueError('Use a canonical base64 WireGuard public key (32 bytes)')
 return value
class HubIn(Strict):
 name:str=Field(min_length=1,max_length=120)
 endpoint:str=Field(min_length=1,max_length=253)
 port:int=Field(ge=1,le=65535,default=51820)
 pool:str=Field(min_length=1,max_length=18)
 public_key:str=Field(min_length=44,max_length=44)
 interface_name:str|None=Field(default=None,min_length=1,max_length=15)
 @field_validator('public_key')
 @classmethod
 def key(cls,v):return public_key(v)
 @field_validator('interface_name')
 @classmethod
 def interface(cls,v):
  if v is not None and not re.fullmatch(r'[A-Za-z0-9_.-]{1,15}',v):raise ValueError('Use a preconfigured dedicated WireGuard interface name')
  return v
 @field_validator('pool')
 @classmethod
 def network(cls,v):
  try:n=ipaddress.IPv4Network(v,strict=True)
  except ValueError:raise ValueError('Use an aligned private IPv4 /24 network')
  if n.prefixlen!=24 or not any(n.subnet_of(p) for p in PRIVATE):raise ValueError('Use an RFC1918 private IPv4 /24 network')
  return str(n)
 @field_validator('endpoint')
 @classmethod
 def host(cls,v):
  v=v.lower()
  try:
   a=ipaddress.ip_address(v)
   if not isinstance(a,ipaddress.IPv4Address) or not a.is_global:raise ValueError('Use a public IPv4 address or DNS name')
  except ValueError:
   if not re.fullmatch(r'(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z](?:[a-z0-9-]{0,61}[a-z0-9])?',v) or v.endswith(('.local','.localhost','.internal','.invalid')):raise ValueError('Use a public IPv4 address or DNS name without URL, path or port')
  return v
class AssignmentIn(Strict):tenant_id:str=Field(min_length=1,max_length=36)
class PlanIn(Strict):
 hub_id:str=Field(min_length=1,max_length=36)
 router_public_key:str=Field(min_length=44,max_length=44)
 @field_validator('router_public_key')
 @classmethod
 def key(cls,v):return public_key(v)
class PairingPlanIn(Strict):hub_id:str=Field(min_length=1,max_length=36)
class PlanReview(Strict):confirmed_review:Literal[True]
class EnrollmentIn(Strict):
 plan_id:str=Field(min_length=1,max_length=36)
 expected_identity_digest:str|None=Field(default=None,pattern=r'^[a-f0-9]{64}$')

def hub_json(h):
 n=ipaddress.ip_network(h.pool)
 return {k:getattr(h,k) for k in ['id','name','endpoint','port','pool','public_key','interface_name','created']}|{'hub_address':str(n.network_address+1),'remaining_addresses':max(0,255-h.next_host),'operational_state':'unverified'}
def plan_json(p):
 verified=connection_is_fresh(p);state='verifying_management' if p.lifecycle_state=='connected' and not verified else p.lifecycle_state
 return {k:getattr(p,k) for k in ['id','tenant_id','router_id','hub_id','address','snapshot','created','reviewed_at','lifecycle_state','last_failure_code','handshake_verified_at','management_read_verified_at']}|{'state':state,'connection_state':'verified' if verified else 'unverified','connection_verified':verified,'last_handshake':p.handshake_verified_at}
def conflict_portals(s,router,pool):
 configs=[]
 for row in [s.get(SitePortal,router.site_id),s.get(PortalSettings,router.tenant_id)]:
  if row:configs.extend([row.draft,row.published])
 for cfg in configs:
  if cfg and cfg.get('guest_subnet') and ipaddress.ip_network(cfg['guest_subnet']).overlaps(pool):raise HTTPException(409,'Hub pool overlaps this business portal subnet; resolve addressing before planning')

def register_hubs(app,current,db,owner,log):
 def orchestrator():
  existing=getattr(app.state,'magic_hub_orchestrator',None)
  if existing:return existing
  policy=HostOperationPolicy(environment=os.environ.get('MIKROMAGIC_ENVIRONMENT',''),peer_writes_enabled=os.environ.get('MIKROMAGIC_HUB_PEER_WRITES_ENABLED','').lower()=='true',peer_reads_enabled=os.environ.get('MIKROMAGIC_HUB_PEER_READS_ENABLED','').lower()=='true',dedicated_interface=os.environ.get('MIKROMAGIC_HUB_DEDICATED_INTERFACE'),deployment_mode=os.environ.get('MIKROMAGIC_HUB_MODE',''))
  return HubPeerOrchestrator(hub_adapter_from_environment(),policy)
 def orchestration_error(s,u,plan,error):
  if plan.lifecycle_state=='failed_recovery_required':
   sync_enrollment_state(s,plan)
   log(s,u,'hub_peer_operation_failed',plan.id+':'+error.code);s.commit()
  raise HTTPException(error.status,{'code':error.code,'message':'Hub peer operation could not be completed safely'})
 def platform(u):
  if u.role!='platform':raise HTTPException(403,'Platform hub administration required')
 def visible_hub(s,u,id):
  h=s.get(MagicHub,id)
  if not h or (u.role!='platform' and not s.get(HubAssignment,(id,u.tenant_id))):raise HTTPException(404,'Assigned hub not found')
  return h
 @app.get('/v1/hubs')
 def hubs(u=Depends(current),s=Depends(db)):
  if u.role not in ['sme','platform']:raise HTTPException(403,'Hub permission required')
  q=select(MagicHub)
  if u.role=='sme':q=q.join(HubAssignment).where(HubAssignment.tenant_id==u.tenant_id)
  service=orchestrator()
  return [hub_json(h)|service.readiness(h) for h in s.scalars(q.order_by(MagicHub.created))]
 @app.post('/v1/hubs',status_code=201)
 def create(b:HubIn,u=Depends(current),s=Depends(db)):
  platform(u);h=MagicHub(**b.model_dump(),created=int(time.time()),next_host=2);s.add(h)
  try:s.flush();log(s,u,'hub_registered',h.id);s.commit()
  except IntegrityError:s.rollback();raise HTTPException(409,'Hub name, pool, endpoint/port or public key already registered')
  return hub_json(h)
 @app.get('/v1/hub-assignments')
 def assignments(u=Depends(current),s=Depends(db)):
  platform(u);return [{'hub_id':x.hub_id,'tenant_id':x.tenant_id,'created':x.created} for x in s.scalars(select(HubAssignment))]
 @app.post('/v1/hubs/{id}/assignments')
 def assign(id:str,b:AssignmentIn,u=Depends(current),s=Depends(db)):
  platform(u);visible_hub(s,u,id)
  if not s.get(Tenant,b.tenant_id):raise HTTPException(404,'Business not found')
  key=(id,b.tenant_id)
  if s.get(HubAssignment,key):return {'hub_id':id,'tenant_id':b.tenant_id,'replayed':True}
  s.add(HubAssignment(hub_id=id,tenant_id=b.tenant_id,created=int(time.time())))
  try:s.flush();log(s,u,'hub_assigned',id+':'+b.tenant_id);s.commit()
  except IntegrityError:s.rollback();return {'hub_id':id,'tenant_id':b.tenant_id,'replayed':True}
  return {'hub_id':id,'tenant_id':b.tenant_id,'replayed':False}
 @app.get('/v1/router-plans')
 def plans(u=Depends(current),s=Depends(db)):
  if u.role not in ['sme','platform']:raise HTTPException(403,'Router plan permission required')
  q=select(RouterPlan)
  if u.role=='sme':q=q.where(RouterPlan.tenant_id==u.tenant_id)
  return [plan_json(p) for p in s.scalars(q.order_by(RouterPlan.created))]
 def build_plan(s,u,r,h,router_public_key):
  old=s.scalar(select(RouterPlan).where(RouterPlan.router_id==r.id))
  if old:
   if old.hub_id!=h.id or old.router_public_key!=router_public_key:raise HTTPException(409,'Router already has an immutable plan; migration or key rotation needs an explicit workflow')
   return plan_json(old)|{'replayed':True}
  if router_public_key==h.public_key:raise HTTPException(422,'Router and hub public keys must differ')
  pool=ipaddress.ip_network(h.pool);conflict_portals(s,r,pool)
  # One atomic counter update serializes allocation across SQLite and PostgreSQL.
  index=s.execute(update(MagicHub).where(MagicHub.id==h.id,MagicHub.next_host<255).values(next_host=MagicHub.next_host+1).returning(MagicHub.next_host)).scalar_one_or_none()
  if index is None:raise HTTPException(409,'Hub address pool exhausted')
  address=str(pool.network_address+index-1);hub=hub_json(h);hub_address=hub['hub_address'];interface=router_interface(r.id)
  snapshot={'version':1,'purpose':'router_management','hub':{k:hub[k] for k in ['id','name','endpoint','port','public_key','hub_address']},'router':{'id':r.id,'site_id':r.site_id,'public_key':router_public_key,'interface':interface,'address':address+'/32','peer_allowed_addresses':[hub_address+'/32'],'routes':[{'destination':hub_address+'/32','interface':interface}],'persistent_keepalive_seconds':25},'hub_peer':{'public_key':router_public_key,'allowed_addresses':[address+'/32']},'private_key_location':'router_only','guest_traffic_via_hub':False,'bootstrap_scope':{'status':'proposal_only_not_executable','allowed_router_changes':['Create one new MikroMagic WireGuard interface using a private key generated locally by RouterOS','Add one peer for the assigned Magic Hub public key and endpoint, limited to the Hub /32','Assign the allocated nonconflicting router management /32','Add only the matching Hub /32 route','Set the planned persistent keepalive'], 'hub_change':'After separate owner confirmation, register only this router public key and allocated /32 on the assigned Hub through the narrow adapter','requires_before_any_execution':['Verify supported RouterOS version, architecture and WireGuard capability','Inspect existing interface names, keys, addresses, routes and WAN/LAN/VPN subnets for conflicts','Review management reachability and the exact before/after diff','Verify a recoverable router backup and recovery procedure','Resolve D1 secure Monitoring and Safe Change identity provisioning on a supported physical device'],'explicitly_excluded':['Existing WireGuard interfaces or peers','Default route, WAN, customer LAN, DHCP or DNS','Firewall changes except a separately reviewed minimum management rule','HotSpot, captive portal, vouchers or customer authentication','Unrelated VPNs, services, users or router configuration']},'checks_required':['Verify RouterOS WireGuard capabilities and existing interfaces/routes','Compare all live LAN/WAN/VPN subnets for address overlap','Take a recoverable router backup and review configuration diff','Register peer on hub through authenticated adapter','Review hub peer isolation and management-service firewall/TLS restrictions','Confirm recent handshake, tunnel reachability and management-service authorization'],'dispatch':'not_implemented'}
  p=RouterPlan(tenant_id=u.tenant_id,router_id=r.id,hub_id=h.id,router_public_key=router_public_key,address=address,snapshot=snapshot,created=int(time.time()),lifecycle_state='awaiting_review');s.add(p)
  try:s.flush();log(s,u,'router_plan_created',p.id);s.commit()
  except IntegrityError:
   s.rollback();old=s.scalar(select(RouterPlan).where(RouterPlan.router_id==r.id))
   if old and old.hub_id==h.id and old.router_public_key==router_public_key:return plan_json(old)|{'replayed':True}
   raise HTTPException(409,'Router public key or plan already allocated')
  return plan_json(p)
 @app.post('/v1/routers/{id}/plan',status_code=201)
 def plan(id:str,b:PlanIn,u=Depends(current),s=Depends(db)):
  owner(u);r=s.get(RouterDevice,id)
  if not r or r.tenant_id!=u.tenant_id:raise HTTPException(404,'Router not found')
  return build_plan(s,u,r,visible_hub(s,u,b.hub_id),b.router_public_key)
 @app.post('/v1/magic-connect/attempts/{id}/plan',status_code=201)
 def plan_from_pairing(id:str,b:PairingPlanIn,u=Depends(current),s=Depends(db)):
  owner(u);attempt=s.get(MagicConnectAttempt,id);now=int(time.time())
  if not attempt or attempt.tenant_id!=u.tenant_id or attempt.owner_id!=u.id:raise HTTPException(404,'Approved pairing not found')
  if not getattr(app.state,'magic_connect_router_setup_enabled',False):raise HTTPException(503,'Technician-guided router setup is not enabled')
  if attempt.status!='approved' or attempt.expires<=now:raise HTTPException(409,'An approved unexpired pairing is required')
  if not attempt.router_id or not attempt.router_public_key:raise HTTPException(409,'The technician has not submitted the router public key yet')
  r=s.get(RouterDevice,attempt.router_id)
  if not r or r.tenant_id!=u.tenant_id or r.site_id!=attempt.site_id:raise HTTPException(409,'Linked router no longer matches this pairing')
  return build_plan(s,u,r,visible_hub(s,u,b.hub_id),attempt.router_public_key)
 @app.post('/v1/router-plans/{id}/review')
 def review(id:str,b:PlanReview,u=Depends(current),s=Depends(db)):
  owner(u);p=s.get(RouterPlan,id)
  if not p or p.tenant_id!=u.tenant_id:raise HTTPException(404,'Router plan not found')
  now=int(time.time())
  changed=s.execute(update(RouterPlan).where(RouterPlan.id==id,RouterPlan.reviewed_at.is_(None)).values(reviewed_at=now,lifecycle_state='awaiting_bootstrap')).rowcount
  if changed:log(s,u,'router_plan_reviewed',id)
  s.commit();s.refresh(p);return plan_json(p)|{'replayed':not bool(changed),'review_stage':'initial_bootstrap_authorization','remote_device_verified':False,'post_connection_preflight_required':True}

 class PeerProvision(Strict):
  confirmed:bool
  idempotency_key:str=Field(min_length=12,max_length=80)
 class EmergencyLock(Strict):
  confirmed:bool
  reason:str=Field(min_length=8,max_length=500)
 class RecoveryCheck(Strict):
  confirmed:bool
 def owner_plan(s,u,id):
  if u.role!='sme' or getattr(u,'staff_profile',None):raise HTTPException(403,'SME Owner/Admin permission required')
  p=s.get(RouterPlan,id)
  if not p or p.tenant_id!=u.tenant_id:raise HTTPException(404,'Router plan not found')
  h=s.get(MagicHub,p.hub_id)
  if not h or not s.get(HubAssignment,(h.id,u.tenant_id)):raise HTTPException(404,'Assigned Hub not found')
  enrollment=s.get(MagicConnectEnrollment,p.id)
  if enrollment and enrollment.owner_id!=u.id:raise HTTPException(403,'Original approving owner required')
  return p,h
 @app.post('/v1/magic-connect/attempts/{id}/enrollment',status_code=201)
 def bind_enrollment(id:str,b:EnrollmentIn,u=Depends(current),s=Depends(db)):
  p,h=owner_plan(s,u,b.plan_id);attempt=s.get(MagicConnectAttempt,id);router=s.get(RouterDevice,p.router_id);now=int(time.time())
  if not app.state.magic_connect_pairing_enabled:raise HTTPException(503,'Magic Connect pairing is unavailable until router bootstrap is verified')
  if not attempt or attempt.tenant_id!=u.tenant_id or attempt.owner_id!=u.id:raise HTTPException(404,'Approved pairing not found')
  existing=s.get(MagicConnectEnrollment,p.id)
  if existing:
   if existing.attempt_id!=id or existing.expected_identity_digest!=b.expected_identity_digest:raise HTTPException(409,'Plan already bound to another enrollment authorization')
   return {'plan_id':p.id,'replayed':True,**enrollment_milestones(s,p),'connection_verified':False}
  if attempt.status!='approved' or attempt.expires<=now or not attempt.approved_at:raise HTTPException(409,'An approved unexpired pairing is required')
  if attempt.site_id!=router.site_id or not p.reviewed_at or p.lifecycle_state!='awaiting_bootstrap':raise HTTPException(409,'Reviewed plan and pairing site must match')
  if attempt.router_id and (attempt.router_id!=p.router_id or attempt.router_public_key!=p.router_public_key):raise HTTPException(409,'Plan does not match the router and key submitted through this pairing')
  s.add(MagicConnectEnrollment(plan_id=p.id,attempt_id=id,tenant_id=u.tenant_id,site_id=router.site_id,owner_id=u.id,expected_identity_digest=b.expected_identity_digest,created=now))
  try:
   s.flush();sync_enrollment_state(s,p);log(s,u,'magic_connect_enrollment_bound',p.id);s.commit()
  except IntegrityError:s.rollback();raise HTTPException(409,'Pairing authorization has already been bound')
  return {'plan_id':p.id,'replayed':False,**enrollment_milestones(s,p),'connection_verified':False,'bootstrap_enabled':False,'credential_provisioning':provisioning_review(s,p.id,u.id,now)}
 @app.post('/v1/router-plans/{id}/hub-peer/provision')
 def provision_peer(id:str,b:PeerProvision,u=Depends(current),s=Depends(db)):
  p,h=owner_plan(s,u,id)
  if not app.state.magic_connect_pairing_enabled:raise HTTPException(503,'Magic Connect pairing is unavailable until router bootstrap is verified')
  try:result=orchestrator().provision(s,p,h,u.tenant_id,confirmed=b.confirmed,idempotency_key=b.idempotency_key)
  except HubOrchestrationError as error:orchestration_error(s,u,p,error)
  log(s,u,'hub_peer_provisioned',p.id);s.commit();s.refresh(p)
  return result|{'plan':plan_json(p),**enrollment_milestones(s,p)}
 @app.post('/v1/router-plans/{id}/hub-peer/observe')
 def observe_peer(id:str,u=Depends(current),s=Depends(db)):
  p,h=owner_plan(s,u,id)
  try:result=orchestrator().observe(s,p,h,u.tenant_id)
  except HubOrchestrationError as error:orchestration_error(s,u,p,error)
  log(s,u,'hub_peer_observed',p.id);s.commit();s.refresh(p)
  return result|{'plan':plan_json(p)}
 @app.post('/v1/router-plans/{id}/hub-peer/recovery-check')
 def recovery_check(id:str,b:RecoveryCheck,u=Depends(current),s=Depends(db)):
  p,h=owner_plan(s,u,id)
  try:result=orchestrator().recover(s,p,h,u.tenant_id,confirmed=b.confirmed)
  except HubOrchestrationError as error:orchestration_error(s,u,p,error)
  log(s,u,'hub_peer_recovery_read',p.id);s.commit();s.refresh(p)
  return result|{'plan':plan_json(p)}
 @app.post('/v1/router-plans/{id}/emergency-lock')
 def emergency_lock(id:str,b:EmergencyLock,u=Depends(current),s=Depends(db)):
  p,h=owner_plan(s,u,id)
  try:result=orchestrator().emergency_lock(s,p,h,u.tenant_id,actor_id=u.id,reason=b.reason,confirmed=b.confirmed)
  except HubOrchestrationError as error:orchestration_error(s,u,p,error)
  log(s,u,'hub_management_emergency_lock',p.id);s.commit();s.refresh(p)
  return result|{'plan':plan_json(p)}
