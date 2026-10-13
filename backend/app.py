import os,time,secrets,hashlib,re,ipaddress
from fastapi import FastAPI,Depends,HTTPException,Request,Response,Query
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer,HTTPAuthorizationCredentials
from sqlalchemy import create_engine,select,update,delete,event,or_
from sqlalchemy.orm import Session,sessionmaker
from sqlalchemy.exc import IntegrityError
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError,VerificationError
from .models import Base,Tenant,User,SessionToken,LoginAttempt,LoginHistory,Package,Order,Entitlement,Audit,Outbox,PortalSettings,VoucherSale
from .schemas import Login,PackageIn,OrderIn,Decision,EvidenceIn,Refund
from .media import package_snapshot,media_offer_available,ensure_media_offer,ensure_sold_separately,media_policy
from .revenue import record_event
from .deliveries import emit_payment_event
from .models import StaffGrant
from .staff import staff_allowed,LEGACY_STAFF_CLOSED
from .models import TenantSubscription
from .subscriptions import is_restricted
from .subscription_renewal import renewal_allowed,RESTRICTED_MESSAGE
from .agents import agent_allowed
from .auth_metadata import client_labels,approximate_source
HASHER=PasswordHasher();DUMMY=HASHER.hash(secrets.token_urlsafe(24));auth=HTTPBearer(auto_error=False)

def _validation_detail_without_input(errors):
 """Keep loc/msg/type; never echo submitted body fields (passwords, tokens, secrets)."""
 safe=[]
 for error in errors:
  item={key:error[key] for key in ('type','loc','msg') if key in error}
  if 'ctx' in error and isinstance(error['ctx'],dict):
   # Drop ctx values that might mirror user input; keep non-input hints when present.
   ctx={k:v for k,v in error['ctx'].items() if k not in ('error','input')}
   if ctx:item['ctx']=ctx
  safe.append(item)
 return safe

def digest(value):return hashlib.sha256(value.encode()).hexdigest()
def check(ok,msg,code=403):
 if not ok:raise HTTPException(code,msg)
LOGIN_WINDOW_SECONDS=900
ACCOUNT_FAILURE_LIMIT=5
ACCOUNT_LOCK_SECONDS=300
IP_FAILURE_LIMIT=60
IP_LOCK_SECONDS=60
MAX_FORWARDED_HOPS=10
def trusted_proxy_networks(value):
 networks=[]
 for raw in (value or '').split(','):
  raw=raw.strip()
  if not raw:continue
  try:network=ipaddress.ip_network(raw,strict=False)
  except ValueError as exc:raise RuntimeError('Invalid MIKROMAGIC_TRUSTED_PROXY_CIDRS configuration') from exc
  if network.prefixlen!=network.max_prefixlen or not (network.is_private or network.is_loopback or network.is_link_local):
   raise RuntimeError('Trusted proxies must be configured as exact private, loopback, or link-local IP addresses')
  networks.append(network)
 return tuple(networks)
def _normalized_ip(value):
 address=ipaddress.ip_address(value.split('%',1)[0])
 if isinstance(address,ipaddress.IPv6Address) and address.ipv4_mapped:return address.ipv4_mapped
 return address
def resolve_client_ip(request, trusted_proxies=()):
 peer_text=request.client.host if request.client else ''
 try:peer=_normalized_ip(peer_text)
 except ValueError:return 'unknown'
 if not any(peer in network for network in trusted_proxies):return str(peer)
 raw=request.headers.get('x-forwarded-for','')
 if not raw or len(raw)>2048:return str(peer)
 pieces=raw.split(',')
 if len(pieces)>MAX_FORWARDED_HOPS:return str(peer)
 try:forwarded=[_normalized_ip(piece.strip()) for piece in pieces]
 except ValueError:return str(peer)
 chain=[*forwarded,peer]
 for address in reversed(chain):
  if any(address in network for network in trusted_proxies):continue
  return str(address)
 return str(forwarded[0]) if forwarded else str(peer)
def login_bucket(s,key,scope,now):
 dialect=s.get_bind().dialect.name
 if dialect=='sqlite':
  from sqlalchemy.dialects.sqlite import insert
 elif dialect=='postgresql':
  from sqlalchemy.dialects.postgresql import insert
 else:
  raise RuntimeError('Login lockout requires SQLite or PostgreSQL upsert support')
 s.execute(insert(LoginAttempt).values(key=key,scope=scope,failures=0,window_start=now,locked_until=None).on_conflict_do_nothing(index_elements=[LoginAttempt.key]))
 bucket=s.scalar(select(LoginAttempt).where(LoginAttempt.key==key).with_for_update())
 check(bucket.scope==scope,'Login throttle scope is inconsistent',503)
 if now-bucket.window_start>=LOGIN_WINDOW_SECONDS:
  bucket.failures=0;bucket.window_start=now;bucket.locked_until=None
 elif bucket.locked_until is not None:
  if bucket.locked_until>now:raise HTTPException(429,'Too many attempts; try again later',headers={'Retry-After':str(bucket.locked_until-now)})
  bucket.failures=0;bucket.window_start=now;bucket.locked_until=None
 return bucket
def make_app(url=None,initialize=False):
 url=url or os.environ.get('DATABASE_URL')
 if not url:raise RuntimeError('DATABASE_URL is required; no production fallback to demo database')
 engine=create_engine(url,connect_args={'check_same_thread':False} if url.startswith('sqlite') else {},pool_pre_ping=True)
 if url.startswith('sqlite'):
  @event.listens_for(engine,'connect')
  def foreign_keys(dbapi,record):dbapi.execute('PRAGMA foreign_keys=ON')
 if initialize:Base.metadata.create_all(engine)
 factory=sessionmaker(engine,expire_on_commit=False);app=FastAPI(title='MikroMagic account & payment API',version='0.2.0');app.state.engine=engine;app.state.factory=factory
 from .routeros_lock import configure_routeros_lock
 configure_routeros_lock(engine)
 isolated_pairing=(os.environ.get('MIKROMAGIC_ENVIRONMENT')=='isolated-magic-connect-test' and os.environ.get('MIKROMAGIC_MAGIC_CONNECT_TEST_MODE','').lower()=='true')
 dedicated_pairing=(os.environ.get('MIKROMAGIC_ENVIRONMENT')=='hostinger-public-test' and os.environ.get('MIKROMAGIC_HUB_MODE')=='dedicated-agent' and os.environ.get('MIKROMAGIC_MAGIC_CONNECT_ENABLED','').lower()=='true')
 app.state.magic_connect_pairing_enabled=isolated_pairing or dedicated_pairing
 # Off until a hardware window; enabling it is a reviewed environment change.
 app.state.magic_connect_router_setup_enabled=app.state.magic_connect_pairing_enabled and os.environ.get('MIKROMAGIC_MAGIC_CONNECT_ROUTER_SETUP','').lower()=='true'
 # Off until a hardware window; enabling is a reviewed environment change (not in default compose).
 app.state.router_settings_changes_enabled=os.environ.get('MIKROMAGIC_ROUTER_SETTINGS_CHANGES','').lower()=='true'
 app.state.trusted_proxy_networks=trusted_proxy_networks(os.environ.get('MIKROMAGIC_TRUSTED_PROXY_CIDRS',''))
 @app.exception_handler(RequestValidationError)
 async def validation_errors_without_input(request:Request,exc:RequestValidationError):
  return JSONResponse(status_code=422,content={'detail':_validation_detail_without_input(exc.errors())})
 @app.middleware('http')
 async def safety(request,call_next):
  limit=5*1024*1024 if request.method=='POST' and re.fullmatch(r'/v1/orders/[^/]+/receipts',request.url.path) else 1024*1024+1024 if request.method=='POST' and request.url.path=='/v1/developer/application/logo' else 64_000
  chunks=[];size=0
  async for chunk in request.stream():
   size+=len(chunk)
   if size>limit:return Response('Request too large',status_code=413,headers={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'})
   chunks.append(chunk)
  request._body=b''.join(chunks)
  r=await call_next(request);r.headers['Cache-Control']='no-store';r.headers['X-Content-Type-Options']='nosniff';return r
 def db():
  with factory() as s:yield s
 def current(request:Request,credentials:HTTPAuthorizationCredentials|None=Depends(auth),s:Session=Depends(db)):
  check(credentials and credentials.scheme.lower()=='bearer','Authentication required',401);tok=s.get(SessionToken,digest(credentials.credentials));check(tok and tok.expires>time.time(),'Session expired or invalid',401);u=s.get(User,tok.user_id);check(u and u.active,'Account unavailable',401)
  now=int(time.time())
  if tok.last_active is None or now-tok.last_active>=60:
   s.execute(update(SessionToken).where(SessionToken.token_hash==tok.token_hash).values(last_active=now));s.commit();tok.last_active=now
  if tok.must_change_password:
   check(not u.temporary_password_expires or u.temporary_password_expires>time.time(),'Temporary password expired; ask the platform operator for a reset',401)
   check(request.url.path in ['/v1/me','/v1/auth/password','/v1/auth/logout'],'Change your temporary password before accessing this workspace',403)
  u.session_must_change_password=tok.must_change_password
  grant=s.get(StaffGrant,u.id);u.staff_profile=grant.profile if grant else None
  if grant:
   check(u.role=='sme' and grant.tenant_id==u.tenant_id,'Staff authority is invalid')
   check(staff_allowed(grant.profile,request.method,request.url.path),LEGACY_STAFF_CLOSED)
  u.subscription_restricted=u.role=='sme' and is_restricted(s.get(TenantSubscription,u.tenant_id),now)
  if u.subscription_restricted:check(renewal_allowed(request.url.path),RESTRICTED_MESSAGE)
  if u.role=='agent':check(agent_allowed(request.url.path),'Agent accounts can only use the Agent workspace')
  return u
 def log(s,u,action,target):s.add(Audit(actor_id=u.id,tenant_id=u.tenant_id,action=action,target=target,created=int(time.time())))
 def tenant(u,t):check(u.tenant_id==t,'Different business',404)
 def owner(u):check(u.role=='sme' and not getattr(u,'staff_profile',None),'SME Owner/Admin permission required')
 def order_for(s,u,id):
  o=s.get(Order,id);check(o,'Order not found',404);tenant(u,o.tenant_id);check(u.role=='sme' or (u.role=='guest' and o.guest_id==u.id),'Order not found',404);return o
 def order_json(o):return {k:getattr(o,k) for k in ['id','tenant_id','guest_id','site_id','snapshot','payment_context','amount','currency','method','reference','evidence','status','fulfillment','reviewer_id','reason','created','receipt_revision']}
 @app.get('/v1/health')
 def health():return {'service':'mikromagic','version':'0.2.0','network_adapter':'not_connected'}
 @app.get('/v1/ready')
 def ready():
  try:
   with engine.connect() as connection:connection.exec_driver_sql('SELECT 1')
  except Exception:raise HTTPException(503,'Service temporarily unavailable') from None
  return {'service':'mikromagic','ready':True}
 @app.post('/v1/auth/login')
 def login(body:Login,request:Request,s:Session=Depends(db)):
  # Account lockout is isolated per normalized username. The higher IP burst guard
  # mitigates username spraying without coupling five failures to every user on a NAT.
  now=int(time.time());name=body.username.strip().lower();ip=resolve_client_ip(request,app.state.trusted_proxy_networks)
  u=s.scalar(select(User).where(User.username==name))
  device,browser=client_labels(request.headers.get('user-agent'));source=approximate_source(ip)
  def record_history(outcome):
   # Login history covers Owner/Admin and platform accounts (Platform console only).
   # Delegated staff, guests, and unknown usernames do not gain a history row.
   if not u or u.role not in ('sme','platform') or s.get(StaffGrant,u.id):return
   s.add(LoginHistory(user_id=u.id,tenant_id=u.tenant_id,outcome=outcome,created=now,device=device,browser=browser,source=source))
   s.execute(delete(LoginHistory).where(LoginHistory.user_id==u.id,LoginHistory.created<now-7*24*60*60))
  try:
   account_bucket=login_bucket(s,digest('account:'+name),'account',now)
   ip_bucket=login_bucket(s,digest('ip:'+ip),'ip',now)
  except HTTPException as exc:
   if exc.status_code==429:record_history('failure');s.commit()
   raise
  try:ok=HASHER.verify(u.password_hash if u else DUMMY,body.password)
  except (VerifyMismatchError,VerificationError):ok=False
  if u and ok and u.role=='sme' and u.access_state=='suspended':
   record_history('failure');s.commit();raise HTTPException(403,'This MikroMagic account is suspended. Reason: '+(u.access_reason or 'not given')+'. Contact MikroMagic to restore access.')
  if not u or not u.active or not ok or (u.must_change_password and u.temporary_password_expires and u.temporary_password_expires<=now):
   account_bucket.failures+=1
   if account_bucket.failures>=ACCOUNT_FAILURE_LIMIT:account_bucket.locked_until=now+ACCOUNT_LOCK_SECONDS
   ip_bucket.failures+=1
   if ip_bucket.failures>=IP_FAILURE_LIMIT:ip_bucket.locked_until=now+IP_LOCK_SECONDS
   record_history('failure');s.commit();raise HTTPException(401,'Invalid username or password')
  if not s.execute(update(User).where(User.id==u.id,User.password_hash==u.password_hash,User.active==True).values(active=User.active)).rowcount:raise HTTPException(401,'Account changed; sign in again')
  account_bucket.failures=0;account_bucket.locked_until=None;account_bucket.window_start=now
  if HASHER.check_needs_rehash(u.password_hash):u.password_hash=HASHER.hash(body.password)
  raw=secrets.token_urlsafe(48);s.add(SessionToken(token_hash=digest(raw),user_id=u.id,expires=now+3600,must_change_password=u.must_change_password,login_at=now,last_active=now,device=device,browser=browser,source=source));record_history('success');log(s,u,'sign_in',u.id);s.commit();return {'access_token':raw,'token_type':'bearer','expires_in':3600,'user':{'id':u.id,'role':u.role,'tenant_id':u.tenant_id,'must_change_password':u.must_change_password}}
 @app.post('/v1/auth/logout')
 def logout(c:HTTPAuthorizationCredentials=Depends(auth),u:User=Depends(current),s:Session=Depends(db)):
  s.delete(s.get(SessionToken,digest(c.credentials)));log(s,u,'sign_out',u.id);s.commit();return {'signed_out':True}
 @app.get('/v1/me')
 def me(u:User=Depends(current)):return {'id':u.id,'username':u.username,'role':u.role,'tenant_id':u.tenant_id,'must_change_password':u.session_must_change_password,'temporary_password_expires':u.temporary_password_expires if u.session_must_change_password else None,'staff_profile':u.staff_profile,'platform_owner':bool(u.role=='platform' and u.platform_owner),'subscription_restricted':u.subscription_restricted}
 @app.get('/v1/tenants')
 def tenants(u:User=Depends(current),s:Session=Depends(db)):
  q=select(Tenant)
  if u.role!='platform':q=q.where(Tenant.id==u.tenant_id)
  return [{'id':t.id,'name':t.name} for t in s.scalars(q)]
 @app.post('/v1/packages',status_code=201)
 def new_package(b:PackageIn,u:User=Depends(current),s:Session=Depends(db)):
  owner(u);p=Package(tenant_id=u.tenant_id,policy=package_snapshot(s,u.tenant_id,b.model_dump()));s.add(p);s.flush();log(s,u,'package_created',p.id);s.commit();return {'id':p.id,**p.policy}
 @app.get('/v1/packages')
 def packages(u:User=Depends(current),s:Session=Depends(db)):
  return [{'id':p.id,**p.policy} for p in s.scalars(select(Package).where(Package.tenant_id==u.tenant_id,Package.active==True)) if u.role!='guest' or media_offer_available(s,u.tenant_id,p.policy)]
 @app.post('/v1/orders',status_code=201)
 def new_order(b:OrderIn,u:User=Depends(current),s:Session=Depends(db)):
  check(u.role=='guest','Guest account required');existing=s.scalar(select(Order).where(Order.guest_id==u.id,Order.request_key==b.request_key))
  if existing:
   check(existing.site_id==b.site_id and existing.package_id==b.package_id and existing.reference==b.reference and existing.evidence==b.evidence and existing.method==b.method and existing.payment_context and existing.payment_context['portal_revision']==b.portal_revision,'Request key reused with different order',409);return order_json(existing)
  p=s.get(Package,b.package_id);check(p and p.tenant_id==u.tenant_id and p.active,'Package not available',404)
  ensure_sold_separately(p.policy);ensure_media_offer(s,u.tenant_id,p.policy)
  from .site_portal import selected_portal
  portal=selected_portal(s,u,b.site_id)
  check(portal and portal.published and portal.published['direct_purchase'],'Purchases are not enabled for this business',409)
  check(portal.published_revision==b.portal_revision,'Payment instructions changed. Refresh and review before submitting.',409)
  check(b.method in portal.published['payment_methods'],'Payment method is not offered',422)
  context={'portal_revision':portal.published_revision,'destination':portal.published['payment_destination'],'instructions':portal.published['payment_instructions'],'business_name':portal.published['business_name']}
  o=Order(site_id=b.site_id,payment_context=context,tenant_id=u.tenant_id,guest_id=u.id,package_id=p.id,snapshot=p.policy.copy(),amount=p.policy['price'],method=b.method,reference=b.reference,evidence=b.evidence,request_key=b.request_key,created=int(time.time()));s.add(o)
  try:s.flush();emit_payment_event(s,o,'payment.submitted');log(s,u,'payment_submitted',o.id);s.commit()
  except IntegrityError:s.rollback();raise HTTPException(409,'Concurrent submission; retry with the same request key')
  return order_json(o)
 @app.get('/v1/orders')
 def orders(u:User=Depends(current),s:Session=Depends(db)):
  check(u.role in ['sme','guest'],'Select an explicitly authorized business context');q=select(Order).where(Order.tenant_id==u.tenant_id)
  if u.role=='guest':q=q.where(Order.guest_id==u.id)
  return [order_json(o) for o in s.scalars(q.order_by(Order.created.desc()))]
 def perform_review(s,u,id,b,allow_replay=True):
  owner(u);o=order_for(s,u,id)
  if allow_replay and o.status==b.decision:return {**order_json(o),'replayed':True}
  check(b.expected_receipt_revision==o.receipt_revision or (b.expected_receipt_revision is None and o.receipt_revision==0),'Receipt evidence changed or has not been reviewed. Refresh before deciding.',409)
  if b.decision=='approved':ensure_media_offer(s,u.tenant_id,o.snapshot)
  # Conditional UPDATE claims pending transition before any side effects.
  result=s.execute(update(Order).where(Order.id==id,Order.tenant_id==u.tenant_id,Order.status=='pending',Order.receipt_revision==o.receipt_revision).values(status=b.decision,reason=b.reason,reviewer_id=u.id))
  check(result.rowcount==1,'Order no longer pending',409)
  if b.decision=='approved':
   s.add(Entitlement(site_id=o.site_id,order_id=o.id,tenant_id=o.tenant_id,guest_id=o.guest_id,policy=o.snapshot.copy()));o.fulfillment='pending_adapter'
   record_event(s,u=u,source='guest_order',record=o,site_id=o.site_id)
  emit_payment_event(s,o,'payment.'+b.decision);log(s,u,'payment_'+b.decision,id)
  s.flush();return order_json(o)
 @app.post('/v1/orders/{id}/decision')
 def review(id:str,b:Decision,u:User=Depends(current),s:Session=Depends(db)):
  try:result=perform_review(s,u,id,b);s.commit();return result
  except IntegrityError:s.rollback();raise HTTPException(409,'Order already processed')
 @app.post('/v1/orders/{id}/evidence')
 def evidence(id:str,b:EvidenceIn,u:User=Depends(current),s:Session=Depends(db)):
  check(u.role=='guest','Guest account required');o=order_for(s,u,id);result=s.execute(update(Order).where(Order.id==id,Order.status=='needs_evidence').values(status='pending',evidence=b.evidence));check(result.rowcount==1,'Evidence not requested',409);emit_payment_event(s,o,'payment.evidence_resubmitted');log(s,u,'evidence_resubmitted',id);s.commit();s.refresh(o);return order_json(o)
 @app.post('/v1/orders/{id}/refund')
 def refund(id:str,b:Refund,u:User=Depends(current),s:Session=Depends(db)):
  owner(u);o=order_for(s,u,id);result=s.execute(update(Order).where(Order.id==id,Order.status=='approved').values(status='refunded',reason=b.reason));check(result.rowcount==1,'Order not approved',409);s.execute(update(Entitlement).where(Entitlement.order_id==id).values(revoked=True));emit_payment_event(s,o,'payment.refunded');log(s,u,'refund_recorded',id);record_event(s,u=u,source='guest_order',record=o,site_id=o.site_id,kind='refund');s.commit();s.refresh(o);return order_json(o)
 @app.get('/v1/entitlements')
 def entitlements(u:User=Depends(current),s:Session=Depends(db)):
  check(u.role in ['guest','sme'],'Business context required');q=select(Entitlement).where(Entitlement.tenant_id==u.tenant_id)
  if u.role=='guest':q=q.where(Entitlement.guest_id==u.id)
  return [{'id':e.id,'order_id':e.order_id,'site_id':e.site_id,'voucher_id':e.voucher_id,'source':'voucher' if e.voucher_id else 'order','policy':e.policy,'revoked':e.revoked,'activation':e.activated,'enforcement':'not_connected','media_policy':media_policy(e.policy,e.activated,e.revoked)} for e in s.scalars(q)]
 from .access_diagnostics import register_access_diagnostics
 register_access_diagnostics(app,current,db)
 @app.get('/v1/audit')
 def audit(search:str=Query(default='',max_length=160),action:str=Query(default='',max_length=100),actor_id:str=Query(default='',max_length=36),limit:int=Query(default=200,ge=1,le=200),offset:int=Query(default=0,ge=0),start:int|None=Query(default=None,ge=0),end:int|None=Query(default=None,ge=0),u:User=Depends(current),s:Session=Depends(db)):
  q=select(Audit)
  if u.role!='platform':q=q.where(Audit.tenant_id==u.tenant_id)
  if u.role=='guest' or getattr(u,'staff_profile',None)=='technician':q=q.where(Audit.actor_id==u.id)
  if start is not None and end is not None and end<start:raise HTTPException(422,'End must follow start')
  if search:q=q.where(or_(Audit.action.contains(search,autoescape=True),Audit.target.contains(search,autoescape=True),Audit.actor_id.contains(search,autoescape=True)))
  if action:q=q.where(Audit.action==action)
  if actor_id:q=q.where(Audit.actor_id==actor_id)
  if start is not None:q=q.where(Audit.created>=start)
  if end is not None:q=q.where(Audit.created<end)
  return [{k:getattr(a,k) for k in ['id','actor_id','action','target','created']} for a in s.scalars(q.order_by(Audit.created.desc(),Audit.id.desc()).offset(offset).limit(limit))]
 from .portal_export import register_portal_exports
 from .account_sessions import register_account_sessions
 from .site_planning import register_site_planning
 from .subscriptions import register_subscriptions
 from .subscription_billing import register_subscription_billing
 register_subscription_billing(app,current,db,log)
 from .subscription_renewal import register_subscription_renewal
 from .developer import register_developer
 register_developer(app,current,db,log)
 from .branding import register_branding
 register_branding(app,current,db,log)
 from .notifications import register_notifications
 register_notifications(app,current,db,owner,log)
 from .agents import register_agents
 register_agents(app,current,db,log,HASHER,check,lambda request:resolve_client_ip(request,app.state.trusted_proxy_networks),digest)
 register_subscription_renewal(app,current,db,log)
 from .staff import register_staff
 register_staff(app,current,db,owner,log,HASHER,digest)
 register_subscriptions(app,current,db,log)
 register_site_planning(app,current,db,owner,log)
 from .managed_devices import register_managed_devices
 register_managed_devices(app,current,db,owner,log)
 register_account_sessions(app,current,db,log,digest)
 from .platform_console import register_platform_console
 register_platform_console(app,current,db,digest)
 register_portal_exports(app,current,db,owner,log)
 from .guest_entry import register_guest_entry
 register_guest_entry(app,db,HASHER,digest,log)
 from .onboarding import register_onboarding
 register_onboarding(app,current,db,log,HASHER,digest,check)
 from .portal import register_portal
 register_portal(app,current,db,owner,log)
 from .vouchers import register_vouchers
 register_vouchers(app,current,db,owner,log)
 from .offline_vouchers import register_offline_vouchers
 register_offline_vouchers(app,current,db,owner,log)
 from .incidents import register_incidents
 register_incidents(app,current,db,owner,log)
 from .backups import register_backups
 register_backups(app,current,db,owner,log)
 from .firmware import register_firmware
 register_firmware(app,current,db,owner,log)
 from .hotspot_sync import register_hotspot_sync
 register_hotspot_sync(app,current,db,log)
 from .hotspot_accounting import register_hotspot_accounting
 register_hotspot_accounting(app,current,db,log)
 from .routeros_preflight import register_routeros_preflight
 register_routeros_preflight(app,current,db,log)
 from .safe_changes import register_safe_changes
 register_safe_changes(app,current,db,owner,log)
 from .hotspot_portal_plans import register_hotspot_portal_plans
 register_hotspot_portal_plans(app,current,db,log)
 from .voucher_batch import register_voucher_batch
 register_voucher_batch(app,current,db,owner,log)
 from .voucher_lifecycle import register_voucher_lifecycle
 register_voucher_lifecycle(app,current,db,owner,log)
 from .voucher_production import register_voucher_production
 register_voucher_production(app,current,db,owner,log)
 from .dealers import register_dealers
 register_dealers(app,current,db,owner,log)
 from .voucher_sales import register_voucher_sales
 register_voucher_sales(app,current,db,owner,log)
 from .sites import register_sites
 register_sites(app,current,db,owner,log)
 from .site_hours import register_site_hours
 register_site_hours(app,current,db,owner,log)
 from .support_report import register_support_reports
 register_support_reports(app,current,db,owner,log)
 from .first_site_acceptance import register_first_site_acceptance
 register_first_site_acceptance(app,current,db)
 from .site_portal import register_site_portals
 register_site_portals(app,current,db,owner,log)
 from .hubs import register_hubs
 register_hubs(app,current,db,owner,log)
 from .magic_connect import register_magic_connect
 register_magic_connect(app,current,db,owner,log,resolve_client_ip,digest)
 from .magic_hub_connect import register_magic_hub_connect
 register_magic_hub_connect(app,current,db,owner,log)
 from .revenue import register_revenue
 register_revenue(app,current,db,owner)
 from .appearance import register_appearance
 register_appearance(app,current,db,log)
 from .review_api import register_review_api
 register_review_api(app,current,db,owner,order_for,order_json,perform_review,log)
 from .receipts import register_receipts
 register_receipts(app,current,db,order_for,log)
 from .knowledge import register_knowledge
 register_knowledge(app,current,db,log)
 from .media import register_media
 register_media(app,current,db,owner,log)
 return app

def create_app():return make_app()
