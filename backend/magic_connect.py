"""Tenant-scoped, single-use Magic Connect technician handoff.

Pairing consent, plus an optional technician-guided transport setup (off by
default). The setup shows copy-and-paste RouterOS steps for the management
WireGuard tunnel only; the router generates its own private key and the
technician returns the public key through this pairing. After the handshake
the technician adds a temporary enrollment login (Hub address only); MikroMagic
then creates its own logins (management_enrollment) and deletes it. Connected
still requires a fresh authenticated read.
"""
from __future__ import annotations
import base64,hashlib,ipaddress,re,secrets,time
from fastapi import Depends,Header,HTTPException,Request
from pydantic import Field,field_validator
from sqlalchemy import case,select,update
from sqlalchemy.exc import IntegrityError
from .models import MagicConnectAttempt,MagicConnectClaimRate,MagicConnectEvent,MagicConnectEnrollment,MagicHub,RouterDevice,RouterPlan,Site
from .hubs import public_key,router_interface
from .hub_orchestrator import connection_is_fresh
from .management_enrollment import CERTIFICATE_PREFIX,ENROLL_PREFIX,GROUPS,USER_PREFIX,ManagementSetupError,enrollment_password
from .schemas import Strict

PAIRING_LIFETIME_SECONDS=600
CLAIM_RATE_WINDOW_SECONDS=900
CLAIM_RATE_LIMIT=30
CODE_SIZE=20
# RouterOS needs a listen port even though the router only dials out to the Hub.
ROUTER_LISTEN_PORT=13239
# Fits uplinks that are themselves tunnelled or PPPoE; WireGuard's default 1420 stalls TLS there.
TUNNEL_MTU=1280

class PairingCreate(Strict):
 router_name:str=Field(min_length=1,max_length=120)
class PairingClaim(Strict):
 code:str=Field(min_length=8,max_length=48)
class PairingDecision(Strict):
 comparison_confirmed:bool
 router_id:str|None=Field(default=None,min_length=1,max_length=36)
class RouterKeySubmit(Strict):
 router_public_key:str=Field(min_length=44,max_length=44)
 @field_validator('router_public_key')
 @classmethod
 def key(cls,v):return public_key(v)

def _digest(value:str)->str:return hashlib.sha256(value.encode('utf-8')).hexdigest()
def _manual_code()->str:
 raw=base64.b32encode(secrets.token_bytes(CODE_SIZE)).decode('ascii').rstrip('=')
 return '-'.join(raw[i:i+4] for i in range(0,len(raw),4))
def _normalize_code(value:str)->str:
 normalized=re.sub(r'[-\s]','',value.strip().upper())
 if len(normalized)!=32 or not re.fullmatch(r'[A-Z2-7]{32}',normalized):return ''
 return normalized
def _event(s,attempt,actor_kind,event,actor_id=None,now=None):
 s.add(MagicConnectEvent(tenant_id=attempt.tenant_id,attempt_id=attempt.id,actor_kind=actor_kind,actor_id=actor_id,event=event,created=int(now or time.time())))
def _owner(u):
 if u.role!='sme' or getattr(u,'staff_profile',None):raise HTTPException(403,'SME Owner/Admin permission required')
def _expire(attempt,s,now):
 if attempt.status in ('pending','claimed','approved') and now>=attempt.expires:
  if s.bind.dialect.name=='postgresql':s.refresh(attempt,with_for_update=True)
  consumed=select(MagicConnectEnrollment.plan_id).where(MagicConnectEnrollment.attempt_id==attempt.id,MagicConnectEnrollment.consumed_at.is_not(None)).exists()
  result=s.execute(update(MagicConnectAttempt).where(MagicConnectAttempt.id==attempt.id,MagicConnectAttempt.status.in_(['pending','claimed','approved']),MagicConnectAttempt.expires<=now,~consumed).values(status='expired',technician_session_hash=None,technician_session_expires=None).execution_options(synchronize_session=False))
  s.refresh(attempt)
  if result.rowcount!=1:return False
  _event(s,attempt,'system','pairing_expired',now=now)
  return True
 return False
def _owner_json(attempt):
 state=attempt.enrollment_state
 if state=='connected' and (attempt.state_changed_at is None or not 0<=int(time.time())-attempt.state_changed_at<=180):state='verifying_management'
 return {'id':attempt.id,'site_id':attempt.site_id,'router_name':attempt.router_name,'status':attempt.status,'enrollment_state':state,'failure_code':attempt.failure_code,'state_changed_at':attempt.state_changed_at,'comparison_code':attempt.comparison_code,'created':attempt.created,'expires':attempt.expires,'claimed_at':attempt.claimed_at,'approved_at':attempt.approved_at,'router_id':attempt.router_id,'router_public_key':attempt.router_public_key,'router_key_submitted_at':attempt.router_key_submitted_at}
def _rate_limit(s,source_digest,now):
 bucket=now-(now%CLAIM_RATE_WINDOW_SECONDS);table=MagicConnectClaimRate.__table__
 values={'source_digest':source_digest,'window_started':bucket,'attempts':1}
 dialect=s.bind.dialect.name
 if dialect=='sqlite':
  from sqlalchemy.dialects.sqlite import insert as dialect_insert
 elif dialect=='postgresql':
  from sqlalchemy.dialects.postgresql import insert as dialect_insert
 else:raise HTTPException(503,'Pairing rate-limit storage is unavailable')
 statement=dialect_insert(table).values(**values)
 statement=statement.on_conflict_do_update(index_elements=['source_digest'],set_={'window_started':bucket,'attempts':case((table.c.window_started==bucket,table.c.attempts+1),else_=1)})
 statement=statement.returning(table.c.attempts)
 count=s.execute(statement).scalar_one();s.flush()
 if count>CLAIM_RATE_LIMIT:
  s.commit();raise HTTPException(429,'Too many technician pairing attempts from this network; try again later')

def _router_setup(attempt,plan,enrollment):
 if attempt.status!='approved':return {'step':'closed','commands':{}}
 if not attempt.router_id:return {'step':'router_not_linked','commands':{}}
 iface=router_interface(attempt.router_id);port=ROUTER_LISTEN_PORT
 commands={'inspect':['/system resource print','/interface wireguard print detail','/interface wireguard peers print','/ip address print','/ip route print where dst-address in 10.0.0.0/8'],
  'create_interface':[f'/interface wireguard add name={iface} listen-port={port} mtu={TUNNEL_MTU} comment="MikroMagic management"',f':put [/interface wireguard get [find name="{iface}"] public-key]'],
  'rollback':[f'/ip route remove [find where gateway="{iface}" and comment="MikroMagic Hub"]',f'/ip address remove [find where interface="{iface}"]',f'/interface wireguard peers remove [find where interface="{iface}"]',f'/interface wireguard remove [find where name="{iface}"]']}
 stop_if=[f'An interface named {iface} already exists',f'Another WireGuard interface already uses listen port {port}','The router is not RouterOS 7 or has no WireGuard menu','Any address or route already uses the MikroMagic tunnel pool shown after owner review']
 result={'interface':iface,'listen_port':port,'router_public_key':attempt.router_public_key,'stop_if':stop_if,'commands':commands}
 if not attempt.router_public_key:return result|{'step':'generate_key'}
 if not plan or plan.router_public_key!=attempt.router_public_key or not plan.reviewed_at:return result|{'step':'owner_review'}
 if plan.lifecycle_state in ('management_lock_pending','management_locked','revoked'):return result|{'step':'closed','commands':{'rollback':commands['rollback']}}
 snap=plan.snapshot;hub=snap['hub'];router=snap['router']
 commands['connect_hub']=[f'/interface wireguard peers add interface={iface} public-key="{hub["public_key"]}" endpoint-address={hub["endpoint"]} endpoint-port={hub["port"]} allowed-address={hub["hub_address"]}/32 persistent-keepalive={router["persistent_keepalive_seconds"]}s comment="MikroMagic Hub"',
  f'/ip address add address={router["address"]} interface={iface} comment="MikroMagic management"',
  f'/ip route add dst-address={hub["hub_address"]}/32 gateway={iface} comment="MikroMagic Hub"',
  f'/ping {hub["hub_address"]} count=3']
 result|={'hub_address':hub['hub_address'],'router_address':router['address']}
 if not (enrollment and enrollment.peer_provisioned_at):return result|{'step':'connect_hub'}
 id8=attempt.router_id[:8];ip=str(ipaddress.ip_interface(router['address']).ip);hub_ip=hub['hub_address'];cert=CERTIFICATE_PREFIX+id8;enroll=ENROLL_PREFIX+id8
 commands['rollback']=[f'/user remove [find where name="{enroll}" or name="{USER_PREFIX["monitoring"]}{id8}" or name="{USER_PREFIX["safe_change"]}{id8}"]',
  f'/user group remove [find where name="{GROUPS["monitoring"]}" or name="{GROUPS["safe_change"]}"]',
  f'/ip firewall filter remove [find where chain=input and in-interface="{iface}" and comment="MikroMagic management"]',
  f'/ip service set www-ssl disabled=yes certificate=none address=""',f'/certificate remove [find where name="{cert}"]']+commands['rollback']
 if enrollment.management_identities_at:return result|{'step':'management_ready'}
 if not plan.handshake_verified_at:return result|{'step':'awaiting_handshake'}
 commands['inspect_management']=['/ip service print where name=www-ssl',f'/user print where name~"^mm-"','/ip firewall filter print where chain=input']
 commands['management_access']=[f'/certificate add name={cert} common-name={ip} subject-alt-name=IP:{ip} key-usage=key-cert-sign,digital-signature,key-encipherment,tls-server days-valid=3650',
  f'/certificate sign {cert}',
  f'/ip service set www-ssl certificate={cert} address={hub_ip}/32 disabled=no',
  f'/ip firewall filter add chain=input in-interface={iface} src-address={hub_ip} protocol=tcp dst-port=443 action=accept comment="MikroMagic management" place-before=0',
  None]
 result['stop_if']=stop_if+['www-ssl is already enabled (someone uses HTTPS WebFig); do not change it, ask MikroMagic support','A user or group starting with mm- already exists','The firewall input chain is empty: run the firewall command without place-before=0']
 return result|{'step':'management_access','enrollment_user':enroll}

def _fill_enrollment_login(setup,router_id,hub_ip):
 """Insert the temporary enrollment secret; only the technician view calls this."""
 if not setup or setup.get('step')!='management_access':return setup
 try:password=enrollment_password(router_id,create=True)
 except ManagementSetupError:return setup|{'step':'management_storage_unavailable','commands':{'rollback':setup['commands']['rollback']}}
 commands=dict(setup['commands']);commands['management_access']=commands['management_access'][:-1]+[f'/user add name={setup["enrollment_user"]} group=full address={hub_ip}/32 password="{password}" comment="MikroMagic temporary enrollment"']
 return setup|{'commands':commands}

def register_magic_connect(app,current,db,owner,log,resolve_ip,digest_ip):
 def router_setup_enabled():
  return bool(app.state.magic_connect_pairing_enabled and getattr(app.state,'magic_connect_router_setup_enabled',False))
 def require_pairing_available():
  if not app.state.magic_connect_pairing_enabled:
   raise HTTPException(503,'Magic Connect pairing is unavailable until router bootstrap is verified')
 def site_for_owner(s,u,site_id):
  _owner(u);site=s.get(Site,site_id)
  if not site or site.tenant_id!=u.tenant_id:raise HTTPException(404,'Site not found')
  return site
 def attempt_for_owner(s,u,attempt_id):
  _owner(u);attempt=s.get(MagicConnectAttempt,attempt_id)
  if not attempt or attempt.tenant_id!=u.tenant_id or attempt.owner_id!=u.id:raise HTTPException(404,'Pairing request not found')
  return attempt
 def technician_attempt(s,authorization):
  match=re.fullmatch(r'Bearer ([A-Za-z0-9_-]{40,100})',authorization or '')
  if not match:raise HTTPException(401,'Technician pairing session required')
  token_hash=_digest('magic-connect-technician:'+match.group(1))
  attempt=s.scalar(select(MagicConnectAttempt).where(MagicConnectAttempt.technician_session_hash==token_hash))
  if not attempt:raise HTTPException(401,'Technician pairing session is invalid')
  now=int(time.time());_expire(attempt,s,now)
  if not attempt.technician_session_expires or now>=attempt.technician_session_expires:
   attempt.technician_session_hash=None;attempt.technician_session_expires=None;s.commit()
   raise HTTPException(401,'Technician pairing session expired')
  return attempt

 @app.get('/v1/magic-connect/capability')
 def capability():
  return {'pairing_available':app.state.magic_connect_pairing_enabled,'router_setup_available':router_setup_enabled(),'router_bootstrap_available':False,'connection_verified':False}

 @app.post('/v1/sites/{site_id}/magic-connect/attempts',status_code=201)
 def create_attempt(site_id:str,b:PairingCreate,u=Depends(current),s=Depends(db)):
  site=site_for_owner(s,u,site_id);require_pairing_available();now=int(time.time())
  duplicate=s.scalar(select(MagicConnectAttempt).where(MagicConnectAttempt.tenant_id==u.tenant_id,MagicConnectAttempt.site_id==site.id,MagicConnectAttempt.router_name==b.router_name,MagicConnectAttempt.status.in_(['pending','claimed','approved']),MagicConnectAttempt.expires>now))
  if duplicate:raise HTTPException(409,'A pairing request for this router name is already active at this site')
  code=_manual_code();normalized=_normalize_code(code);comparison=f'{secrets.randbelow(1_000_000):06d}'
  attempt=MagicConnectAttempt(tenant_id=u.tenant_id,site_id=site.id,owner_id=u.id,router_name=b.router_name.strip(),code_hash=_digest('magic-connect-code:'+normalized),comparison_code=comparison,status='pending',enrollment_state='pairing_pending',state_changed_at=now,created=now,expires=now+PAIRING_LIFETIME_SECONDS)
  s.add(attempt)
  try:s.flush();log(s,u,'magic_connect_pairing_created',attempt.id);_event(s,attempt,'owner','pairing_created',u.id,now);s.commit()
  except IntegrityError:s.rollback();raise HTTPException(409,'Could not create a unique pairing request; try again')
  # The manual code is also the QR payload. It is returned once and is never put
  # in a URL; the technician page submits it in a POST body.
  return _owner_json(attempt)|{'manual_code':code,'qr_payload':code,'qr_encoding':'opaque_code_text','single_use':True}

 @app.get('/v1/sites/{site_id}/magic-connect/attempts')
 def list_attempts(site_id:str,u=Depends(current),s=Depends(db)):
  site=site_for_owner(s,u,site_id);now=int(time.time());items=list(s.scalars(select(MagicConnectAttempt).where(MagicConnectAttempt.tenant_id==u.tenant_id,MagicConnectAttempt.site_id==site.id).order_by(MagicConnectAttempt.created.desc()).limit(25)))
  changed=False
  for attempt in items:changed=_expire(attempt,s,now) or changed
  if changed:s.commit()
  return [_owner_json(item) for item in items]

 @app.post('/v1/magic-connect/claim')
 def claim(b:PairingClaim,request:Request,s=Depends(db)):
  require_pairing_available()
  peer=resolve_ip(request,app.state.trusted_proxy_networks)
  _rate_limit(s,digest_ip('magic-connect-source:'+peer),int(time.time()))
  normalized=_normalize_code(b.code)
  attempt=s.scalar(select(MagicConnectAttempt).where(MagicConnectAttempt.code_hash==_digest('magic-connect-code:'+normalized))) if normalized else None
  now=int(time.time())
  if not attempt: s.commit();raise HTTPException(404,'Pairing code is invalid or unavailable')
  if attempt.expires<=now:
   _expire(attempt,s,now);s.commit();raise HTTPException(410,'Pairing code expired')
  token=secrets.token_urlsafe(32);token_hash=_digest('magic-connect-technician:'+token)
  # A conditional database update makes the single-use claim atomic across
  # workers. A read-then-write check alone allows two concurrent claims.
  result=s.execute(update(MagicConnectAttempt).where(MagicConnectAttempt.id==attempt.id,MagicConnectAttempt.status=='pending',MagicConnectAttempt.expires>now).values(status='claimed',claimed_at=now,technician_session_hash=token_hash,technician_session_expires=attempt.expires).execution_options(synchronize_session=False))
  if result.rowcount!=1:
   s.rollback()
   raise HTTPException(409,'Pairing code was already claimed or is no longer available')
  s.expire_all();attempt=s.get(MagicConnectAttempt,attempt.id)
  _event(s,attempt,'technician','technician_claimed',now=now);s.commit()
  return {'status':'awaiting_owner_approval','technician_session':token,'comparison_code':attempt.comparison_code,'router_name':attempt.router_name,'expires':attempt.expires,'business_access':False,'router_commands_available':False}

 @app.get('/v1/magic-connect/technician/status')
 def technician_status(authorization:str|None=Header(default=None),s=Depends(db)):
  attempt=technician_attempt(s,authorization);now=int(time.time())
  enrollment=s.scalar(select(MagicConnectEnrollment).where(MagicConnectEnrollment.attempt_id==attempt.id));plan=s.get(RouterPlan,enrollment.plan_id) if enrollment else None
  if not plan and attempt.router_id:plan=s.scalar(select(RouterPlan).where(RouterPlan.router_id==attempt.router_id))
  verified=bool(enrollment and plan and connection_is_fresh(plan,now));setup=None
  if attempt.status=='approved' and router_setup_enabled():
   access='transport_setup';setup=_router_setup(attempt,plan,enrollment)
   if setup.get('step')=='management_access':setup=_fill_enrollment_login(setup,attempt.router_id,setup['hub_address'])
   instructions=bool(setup['commands'])
  elif attempt.status=='approved':
   access='blocked_pending_hardware_verification';instructions=False
  elif attempt.status=='pending' or attempt.status=='claimed':access='awaiting_owner_approval';instructions=False
  else:access='closed';instructions=False
  state='verifying_management' if attempt.enrollment_state=='connected' and not verified else attempt.enrollment_state
  return {'status':attempt.status,'enrollment_state':state,'failure_code':attempt.failure_code,'router_name':attempt.router_name,'comparison_code':attempt.comparison_code,'expires':attempt.technician_session_expires or attempt.expires,'setup_access':access,'setup_instructions_available':instructions,'router_setup':setup,'business_data_access':False,'router_write_access':False,'connection_verified':verified,'observed_at':now}

 @app.post('/v1/magic-connect/technician/router-key')
 def submit_router_key(b:RouterKeySubmit,authorization:str|None=Header(default=None),s=Depends(db)):
  attempt=technician_attempt(s,authorization);now=int(time.time())
  if not router_setup_enabled():raise HTTPException(503,'Technician-guided router setup is not enabled')
  if attempt.status!='approved' or attempt.expires<=now:raise HTTPException(409,'Owner approval is required before submitting a router key')
  if not attempt.router_id:raise HTTPException(409,'The owner has not linked this pairing to a registered router')
  if attempt.router_public_key:
   if attempt.router_public_key==b.router_public_key:return {'router_public_key':attempt.router_public_key,'replayed':True}
   raise HTTPException(409,'A different router key was already submitted; ask the owner to cancel and start a new pairing')
  if s.scalar(select(MagicHub.id).where(MagicHub.public_key==b.router_public_key)) or s.scalar(select(RouterPlan.id).where(RouterPlan.router_public_key==b.router_public_key)):
   raise HTTPException(409,'This public key is already in use; create a new WireGuard interface on the router')
  try:
   result=s.execute(update(MagicConnectAttempt).where(MagicConnectAttempt.id==attempt.id,MagicConnectAttempt.status=='approved',MagicConnectAttempt.expires>now,MagicConnectAttempt.router_public_key.is_(None)).values(router_public_key=b.router_public_key,router_key_submitted_at=now).execution_options(synchronize_session=False))
   if result.rowcount!=1:s.rollback();raise HTTPException(409,'Router key could not be recorded; refresh the setup status')
   s.expire_all();attempt=s.get(MagicConnectAttempt,attempt.id);_event(s,attempt,'technician','router_key_submitted',now=now);s.commit()
  except IntegrityError:s.rollback();raise HTTPException(409,'This public key is already in use; create a new WireGuard interface on the router')
  return {'router_public_key':attempt.router_public_key,'replayed':False}

 @app.post('/v1/magic-connect/attempts/{attempt_id}/approve')
 def approve(attempt_id:str,b:PairingDecision,u=Depends(current),s=Depends(db)):
  attempt=attempt_for_owner(s,u,attempt_id);require_pairing_available();now=int(time.time())
  if _expire(attempt,s,now):s.commit();raise HTTPException(410,'Pairing request expired')
  if not b.comparison_confirmed:raise HTTPException(422,'Confirm that the comparison code matches the technician screen')
  if b.router_id:
   if not router_setup_enabled():raise HTTPException(503,'Technician-guided router setup is not enabled')
   router=s.get(RouterDevice,b.router_id)
   if not router or router.tenant_id!=u.tenant_id or router.site_id!=attempt.site_id:raise HTTPException(404,'Registered router not found at this shop')
   if s.scalar(select(RouterPlan.id).where(RouterPlan.router_id==router.id)):raise HTTPException(409,'This router already has a connection plan')
   if s.scalar(select(MagicConnectAttempt.id).where(MagicConnectAttempt.router_id==router.id,MagicConnectAttempt.id!=attempt.id,MagicConnectAttempt.status.in_(['claimed','approved']),MagicConnectAttempt.expires>now)):raise HTTPException(409,'Another active pairing is already setting up this router')
  result=s.execute(update(MagicConnectAttempt).where(MagicConnectAttempt.id==attempt.id,MagicConnectAttempt.status=='claimed',MagicConnectAttempt.expires>now).values(status='approved',enrollment_state='pairing_approved',approved_at=now,state_changed_at=now,router_id=b.router_id).execution_options(synchronize_session=False))
  if result.rowcount!=1:raise HTTPException(409,'A claimed, unexpired technician request is required before approval')
  s.expire_all();attempt=s.get(MagicConnectAttempt,attempt.id)
  log(s,u,'magic_connect_technician_approved',attempt.id);_event(s,attempt,'owner','technician_approved',u.id,now);s.commit()
  setup=bool(attempt.router_id and router_setup_enabled())
  return _owner_json(attempt)|{'setup_access':'transport_setup' if setup else 'blocked_pending_hardware_verification','setup_instructions_available':setup}

 @app.post('/v1/magic-connect/attempts/{attempt_id}/deny')
 def deny(attempt_id:str,u=Depends(current),s=Depends(db)):
  attempt=attempt_for_owner(s,u,attempt_id);now=int(time.time())
  result=s.execute(update(MagicConnectAttempt).where(MagicConnectAttempt.id==attempt.id,MagicConnectAttempt.status.in_(['pending','claimed']),MagicConnectAttempt.expires>now).values(status='denied',enrollment_state='failed_recovery_required',failure_code='owner_denied_pairing',state_changed_at=now,denied_at=now,technician_session_hash=None,technician_session_expires=None).execution_options(synchronize_session=False))
  if result.rowcount!=1:raise HTTPException(409,'Pairing request can no longer be denied')
  s.expire_all();attempt=s.get(MagicConnectAttempt,attempt.id)
  log(s,u,'magic_connect_technician_denied',attempt.id);_event(s,attempt,'owner','technician_denied',u.id,now);s.commit();return _owner_json(attempt)

 @app.post('/v1/magic-connect/attempts/{attempt_id}/cancel')
 def cancel(attempt_id:str,u=Depends(current),s=Depends(db)):
  attempt=attempt_for_owner(s,u,attempt_id);now=int(time.time())
  # Wait for any consume transaction before checking its committed enrollment.
  # A NOT EXISTS subquery alone can retain a pre-wait PostgreSQL snapshot.
  if s.bind.dialect.name=='postgresql':s.refresh(attempt,with_for_update=True)
  if s.scalar(select(MagicConnectEnrollment).where(MagicConnectEnrollment.attempt_id==attempt.id,MagicConnectEnrollment.consumed_at.is_not(None))):raise HTTPException(409,'Enrollment authority was consumed; use the auditable emergency management lock, not pairing cancellation')
  consumed=select(MagicConnectEnrollment.plan_id).where(MagicConnectEnrollment.attempt_id==attempt.id,MagicConnectEnrollment.consumed_at.is_not(None)).exists()
  result=s.execute(update(MagicConnectAttempt).where(MagicConnectAttempt.id==attempt.id,MagicConnectAttempt.status.in_(['pending','claimed','approved']),~consumed).values(status='cancelled',enrollment_state='revoked',state_changed_at=now,cancelled_at=now,technician_session_hash=None,technician_session_expires=None).execution_options(synchronize_session=False))
  if result.rowcount!=1:raise HTTPException(409,'Pairing request is already closed')
  s.expire_all();attempt=s.get(MagicConnectAttempt,attempt.id)
  log(s,u,'magic_connect_pairing_cancelled',attempt.id);_event(s,attempt,'owner','pairing_cancelled',u.id,now);s.commit();return _owner_json(attempt)|{'router_changes_reverted':False,'note':'No RouterOS bootstrap is enabled in this build.'}
