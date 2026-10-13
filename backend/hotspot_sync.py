"""Reconcile MikroMagic vouchers into one router's HotSpot users and profiles.

Only objects carrying MikroMagic's comment marker are touched, disables and
removals go first, and every write is read back. A router qualifies only after
MikroMagic created its own logins and an authenticated management read
succeeded. Wall-clock validity from first login uses a router-side script that
is unverified until real hardware runs it. The redeem-before deadline is not
enforced on the router yet: activation is only known after session reads.
"""
import hashlib,json,threading,time
from fastapi import Depends,HTTPException
from sqlalchemy import or_,select
from .models import HotspotVoucherSync,MagicConnectEnrollment,RouterDevice,RouterPlan,Voucher
from .routeros_adapter import RouterOSClient,RouterOSError,load_routeros_safe_change_credential
from .voucher_vault import unseal

USER_COMMENT='MikroMagic voucher'
PROFILE_COMMENT='MikroMagic plan'
SCHEDULER='mm-voucher-expiry'
GB=1_000_000_000
BATCH=200
TRANSPORT_ERRORS={'unreachable','timeout','transport_error','tls_verification_failed','authentication_failed','relay_unavailable','relay_invalid','credential_missing','credential_invalid','credential_permissions','credential_identity','transport_policy'}
LOCKED_STATES=('management_lock_pending','management_locked','revoked')

class HotspotSyncError(RuntimeError):
 def __init__(self,code,message,status=409):super().__init__(message);self.code=code;self.status=status

def duration(seconds):
 days,rest=divmod(int(seconds),86400);hours,rest=divmod(rest,3600);minutes,secs=divmod(rest,60)
 return f'{days}d{hours:02}:{minutes:02}:{secs:02}'

def internet_limits(policy):
 """HotSpot limits for an Internet voucher snapshot, or None for Media passes."""
 if not isinstance(policy,dict) or policy.get('service') not in ('internet','combined'):return None
 mode=policy.get('mode');devices=max(1,int(policy.get('devices') or 1));speed=policy.get('speed')
 data=int(float(policy.get('gb') or 0)*GB) if mode in ('data','both') else 0
 seconds=int(float(policy.get('hours') or 0)*3600) if mode in ('time','both') else 0
 return {'devices':devices,'rate_kbps':max(1,int(float(speed)*1000/devices)) if speed else None,
  'data_bytes':data or None,'seconds':seconds or None,'clock':policy.get('clock') or 'elapsed'}

def expiry_on_login(seconds):
 """Stamp the absolute expiry into the user's comment on first login only."""
 return (':local i [/ip hotspot user find where name=$user];:if ([:len $i]=1) do={:local c [/ip hotspot user get $i comment];'
  ':if ([:typeof [:find $c "|exp="]]="nil") do={/ip hotspot user set $i comment=($c."|exp=".[:tostr ([:timestamp]+'+duration(seconds)+')])}}')

EXPIRY_CHECK=(':local now [:timestamp];:foreach i in=[/ip hotspot user find where comment~"^'+USER_COMMENT+'" and disabled=no] do={'
 ':local c [/ip hotspot user get $i comment];:local p [:find $c "|exp="];:if ([:typeof $p]!="nil") do={'
 ':if ($now>=[:totime [:pick $c ($p+5) [:len $c]]]) do={:local u [/ip hotspot user get $i name];/ip hotspot user disable $i;'
 '/ip hotspot active remove [find where user=$u];/ip hotspot cookie remove [find where user=$u]}}}')

def profile_for(limits):
 fields={'shared-users':str(limits['devices']),'rate-limit':f"{limits['rate_kbps']}k/{limits['rate_kbps']}k" if limits['rate_kbps'] else '',
  'on-login':expiry_on_login(limits['seconds']) if limits['seconds'] and limits['clock']=='elapsed' else ''}
 name='mm-'+hashlib.sha256(json.dumps(fields,sort_keys=True).encode()).hexdigest()[:10]
 # RouterOS HotSpot user profiles have no comment; the content-hash name marks ownership.
 return name,{'name':name,**fields}

def user_limits(limits):
 fields={}
 if limits['data_bytes']:fields['limit-bytes-total']=str(limits['data_bytes'])
 if limits['seconds'] and limits['clock']=='connected':fields['limit-uptime']=duration(limits['seconds'])
 return fields

def desired_state(voucher):
 if voucher.deleted_at:return 'absent'
 if voucher.revoked or voucher.disabled_at:return 'disabled'
 return 'present'

def fingerprint(desired,profile,fields):
 return hashlib.sha256(json.dumps([desired,profile,fields],sort_keys=True).encode()).hexdigest()

def _row(value):
 if isinstance(value,list):
  if len(value)>1:raise HotspotSyncError('router_response_invalid','Router returned more than one matching record')
  value=value[0] if value else None
 if value is not None and not isinstance(value,dict):raise HotspotSyncError('router_response_invalid','Router returned an invalid record')
 return value

class RouterHotspot:
 """Allowlisted HotSpot operations for MikroMagic-owned objects only."""
 def __init__(self,client):self.client=client;self.profiles=set();self.scheduler=False
 def ensure_scheduler(self):
  if self.scheduler:return
  existing=_row(self.client.get('system/scheduler?name='+SCHEDULER))
  if existing and existing.get('comment')!=PROFILE_COMMENT:raise HotspotSyncError('scheduler_conflict',f'A scheduler named {SCHEDULER} already exists and is not MikroMagic\'s')
  fields={'interval':'1m','on-event':EXPIRY_CHECK,'policy':'read,write','comment':PROFILE_COMMENT,'disabled':'false'}
  if existing:self.client.write('PATCH','system/scheduler/'+existing['.id'],fields)
  else:self.client.write('PUT','system/scheduler',{'name':SCHEDULER,**fields})
  self.scheduler=True
 def ensure_profile(self,name,fields):
  if name in self.profiles:return
  existing=_row(self.client.get('ip/hotspot/user/profile?name='+name))
  if existing and any(str(existing.get(k) or '')!=fields[k] for k in ('shared-users','rate-limit')):raise HotspotSyncError('profile_conflict',f'HotSpot profile {name} exists and is not MikroMagic\'s')
  if not existing:self.client.write('PUT','ip/hotspot/user/profile',fields)
  if fields.get('on-login'):self.ensure_scheduler()
  self.profiles.add(name)
 def _user(self,code):
  user=_row(self.client.get('ip/hotspot/user?name='+code))
  if user and not str(user.get('comment') or '').startswith(USER_COMMENT):raise HotspotSyncError('hotspot_user_conflict','A HotSpot user with this voucher code exists and was not created by MikroMagic')
  return user
 def disconnect(self,code):
  """Drop active sessions and HotSpot cookies so a disabled/removed voucher cannot stay logged in."""
  sessions=self.client.get('ip/hotspot/active?user='+code)
  for session in sessions if isinstance(sessions,list) else []:self.client.write('DELETE','ip/hotspot/active/'+session['.id'],None)
  cookies=self.client.get('ip/hotspot/cookie?user='+code)
  for cookie in cookies if isinstance(cookies,list) else []:self.client.write('DELETE','ip/hotspot/cookie/'+cookie['.id'],None)
 def apply(self,code,desired,profile,fields):
  user=self._user(code)
  if desired=='present':
   values={'password':code,'profile':profile,**fields,'disabled':'false'}
   if user:self.client.write('PATCH','ip/hotspot/user/'+user['.id'],values)
   else:self.client.write('PUT','ip/hotspot/user',{'name':code,'comment':USER_COMMENT,**values})
  elif desired=='disabled':
   if user:self.client.write('PATCH','ip/hotspot/user/'+user['.id'],{'disabled':'true'})
   self.disconnect(code)
  else:
   self.disconnect(code)
   if user:self.client.write('DELETE','ip/hotspot/user/'+user['.id'],None)
  after=self._user(code);state=str((after or {}).get('disabled')).lower()
  if desired=='absent':ok=after is None
  elif desired=='disabled':ok=state=='true' if after else user is None
  else:ok=bool(after) and state=='false' and after.get('profile')==profile
  if not ok:raise HotspotSyncError('readback_mismatch','Router did not show the expected HotSpot user state after the change')

def managed_router(s,router_id,tenant_id=None):
 router=s.get(RouterDevice,router_id)
 if not router or (tenant_id and router.tenant_id!=tenant_id):return None,None
 plan=s.scalar(select(RouterPlan).where(RouterPlan.router_id==router.id,RouterPlan.tenant_id==router.tenant_id))
 enrollment=s.get(MagicConnectEnrollment,plan.id) if plan else None
 if not (enrollment and enrollment.management_identities_at and plan.management_read_verified_at and plan.lifecycle_state not in LOCKED_STATES):return router,None
 return router,plan

def scope(s,router):
 others=[r for r in s.scalars(select(RouterDevice).where(RouterDevice.tenant_id==router.tenant_id,RouterDevice.site_id==router.site_id,RouterDevice.id!=router.id)) if managed_router(s,r.id)[1]]
 if others:raise HotspotSyncError('router_choice_required','This shop has more than one managed router; voucher pools per router are not supported yet')
 return list(s.scalars(select(Voucher).where(Voucher.tenant_id==router.tenant_id,or_(Voucher.site_id==router.site_id,Voucher.site_id.is_(None))).order_by(Voucher.created)))

def plan_work(s,router):
 rows={x.voucher_id:x for x in s.scalars(select(HotspotVoucherSync).where(HotspotVoucherSync.router_id==router.id))}
 work=[];summary={'in_sync':0,'pending':0,'skipped':{}}
 def skip(reason):summary['skipped'][reason]=summary['skipped'].get(reason,0)+1
 for voucher in scope(s,router):
  limits=internet_limits(voucher.policy)
  if not limits:skip('media_pass');continue
  desired=desired_state(voucher);row=rows.get(voucher.id)
  if desired=='absent' and not (row and row.applied in ('present','disabled')):continue
  if not voucher.code_sealed:skip('issued_before_router_sync');continue
  profile,profile_fields=profile_for(limits);fields=user_limits(limits);fp=fingerprint(desired,profile,fields)
  if row and row.applied==desired and row.applied_fingerprint==fp:summary['in_sync']+=1;continue
  summary['pending']+=1;work.append((0 if desired!='present' else 1,voucher.created,voucher,desired,profile,profile_fields,fields,fp,row))
 work.sort(key=lambda x:(x[0],x[1]))
 return work,summary

def reconcile(s,router_id,client_factory=RouterOSClient,now=None,limit=BATCH):
 router,plan=managed_router(s,router_id)
 if not router:raise HotspotSyncError('router_not_found','Router not found',404)
 if not plan:raise HotspotSyncError('router_not_managed','Voucher sync starts after MikroMagic logins exist and the router was verified Connected')
 work,summary=plan_work(s,router);result={'applied':0,'failed':0,'aborted':None,'remaining':max(0,len(work)-limit),**summary}
 if not work:return result
 now=int(time.time() if now is None else now)
 try:client=client_factory(load_routeros_safe_change_credential(router.id),router_id=router.id)
 except RouterOSError as error:result['aborted']=error.code;return result
 with client:
  hotspot=RouterHotspot(client)
  for _,_,voucher,desired,profile,profile_fields,fields,fp,row in work[:limit]:
   row=row or s.get(HotspotVoucherSync,(voucher.id,router.id))
   if not row:row=HotspotVoucherSync(voucher_id=voucher.id,router_id=router.id,tenant_id=router.tenant_id,attempts=0);s.add(row)
   row.attempts=(row.attempts or 0)+1;row.last_attempt_at=now
   code=unseal(voucher.tenant_id,voucher.code_sealed)
   try:
    if not code:raise HotspotSyncError('code_unreadable','The stored voucher code cannot be read with this server key')
    if desired=='present':hotspot.ensure_profile(profile,profile_fields)
    hotspot.apply(code,desired,profile,fields)
    row.applied=desired;row.applied_fingerprint=fp;row.applied_at=now;row.last_error=None;result['applied']+=1;result['pending']-=1
   except RouterOSError as error:
    row.last_error=error.code[:60];result['failed']+=1;s.commit()
    if error.code in TRANSPORT_ERRORS:result['aborted']=error.code;break
    continue
   except HotspotSyncError as error:row.last_error=error.code[:60];result['failed']+=1
   s.commit()
 return result

def sync_status(s,router_id):
 router,plan=managed_router(s,router_id)
 if not plan:return {'managed':False,'in_sync':0,'pending':0,'skipped':{},'failed':0}
 try:work,summary=plan_work(s,router)
 except HotspotSyncError as error:return {'managed':True,'blocked':error.code,'in_sync':0,'pending':0,'skipped':{},'failed':0}
 failed=sum(1 for item in work if item[8] and item[8].last_error)
 last=s.scalar(select(HotspotVoucherSync.applied_at).where(HotspotVoucherSync.router_id==router.id).order_by(HotspotVoucherSync.applied_at.desc()).limit(1))
 return {'managed':True,**summary,'failed':failed,'last_applied_at':last}

_running=set();_guard=threading.Lock()

def background_sync(factory,router_ids):
 """Best-effort sync after voucher changes or a fresh Connected; one run per router per process."""
 def run(router_id):
  try:
   with factory() as s:reconcile(s,router_id)
  except Exception:pass
  finally:
   with _guard:_running.discard(router_id)
 for router_id in router_ids:
  with _guard:
   if router_id in _running:continue
   _running.add(router_id)
  threading.Thread(target=run,args=(router_id,),daemon=True).start()

def routers_for_voucher(s,voucher):
 query=select(RouterDevice.id).where(RouterDevice.tenant_id==voucher.tenant_id)
 if voucher.site_id:query=query.where(RouterDevice.site_id==voucher.site_id)
 return [rid for rid in s.scalars(query) if managed_router(s,rid)[1]]

def register_hotspot_sync(app,current,db,log):
 def owner_router(s,u,id):
  if u.role!='sme' or getattr(u,'staff_profile',None):raise HTTPException(403,'SME Owner permission required')
  router=s.get(RouterDevice,id)
  if not router or router.tenant_id!=u.tenant_id:raise HTTPException(404,'Router not found')
  return router
 @app.get('/v1/routers/{id}/hotspot-sync')
 def status(id:str,u=Depends(current),s=Depends(db)):
  owner_router(s,u,id);return sync_status(s,id)|{'enforcement_verified':False}
 @app.post('/v1/routers/{id}/hotspot-sync')
 def sync_now(id:str,u=Depends(current),s=Depends(db)):
  owner_router(s,u,id)
  try:result=reconcile(s,id,getattr(app.state,'hotspot_client_factory',RouterOSClient))
  except HotspotSyncError as error:raise HTTPException(error.status,{'code':error.code,'message':str(error)})
  log(s,u,'router_hotspot_sync',id);s.commit()
  return result|{'enforcement_verified':False}
 def trigger(s,voucher):
  routers=routers_for_voucher(s,voucher)
  if routers:getattr(app.state,'hotspot_background_sync',background_sync)(app.state.factory,routers)
 app.state.hotspot_sync_voucher=trigger
