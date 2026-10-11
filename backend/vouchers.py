"""Voucher issuance does not imply payment or revenue."""
import hashlib,time
from fastapi import Depends,HTTPException
from sqlalchemy import select,update
from sqlalchemy.exc import IntegrityError
from .models import Voucher,Package,Entitlement,PortalSettings,LoginAttempt,VoucherSale
from .media import ensure_media_offer,ensure_sold_separately
from .schemas import VoucherIssue,VoucherRedeem,VoucherRevoke
from .voucher_codes import new_code,find_voucher,normalize_prefix,normalize_custom,display

def digest(code):return hashlib.sha256(code.encode()).hexdigest()
def voucher_json(v):
 status='revoked' if v.revoked else 'deleted' if v.deleted_at else 'disabled' if v.disabled_at else 'redeemed' if v.redeemed_by else 'expired' if v.expires<=time.time() else 'unused'
 return {k:getattr(v,k) for k in ['id','site_id','package_id','policy','code_hint','code_prefix','code_format','created','expires','redeemed_at','redeemed_by','reason','disabled_at','disabled_reason','router_sync','serial_no','production_job_id','sheet_no','dealer_id']}|{'status':status,'enforcement':'not_connected'}
def register_vouchers(app,current,db,owner,log):
 @app.get('/v1/vouchers')
 def inventory(u=Depends(current),s=Depends(db)):
  from .voucher_sales import sale_json
  owner(u);sales={};cancelled={}
  for x in s.scalars(select(VoucherSale).where(VoucherSale.tenant_id==u.tenant_id).order_by(VoucherSale.created)):
   if x.cancelled_at:cancelled.setdefault(x.voucher_id,[]).append(sale_json(x))
   else:sales[x.voucher_id]=sale_json(x)
  return [voucher_json(v)|{'sale':sales.get(v.id),'cancelled_sales':cancelled.get(v.id,[])} for v in s.scalars(select(Voucher).where(Voucher.tenant_id==u.tenant_id,Voucher.deleted_at.is_(None)).order_by(Voucher.created.desc()))]
 @app.post('/v1/vouchers',status_code=201)
 def issue(b:VoucherIssue,u=Depends(current),s=Depends(db)):
  owner(u);prefix=normalize_prefix(b.prefix);custom=normalize_custom(b.custom_code) if b.custom_code else None
  if custom and prefix:raise HTTPException(422,'Use either a prefix or a custom code, not both')
  existing=s.scalar(select(Voucher).where(Voucher.issued_by==u.id,Voucher.request_key==b.request_key))
  if existing:
   if existing.site_id!=b.site_id or existing.package_id!=b.package_id or existing.expires-existing.created!=b.expires_days*86400 or existing.code_prefix!=prefix or (existing.code_format=='custom')!=bool(custom):raise HTTPException(409,'Request key reused with different voucher')
   return voucher_json(existing)|{'replayed':True,'code':None,'message':'Already issued. The full code is shown once; if it was lost, revoke this voucher and issue another.'}
  if b.site_id:
   from .sites import allowed_site
   allowed_site(s,u,b.site_id)
  p=s.get(Package,b.package_id)
  if not p or p.tenant_id!=u.tenant_id or not p.active:raise HTTPException(404,'Package not available')
  if custom and not p.policy.get('vip'):raise HTTPException(422,'Custom codes are available only for VIP packages')
  ensure_sold_separately(p.policy);ensure_media_offer(s,u.tenant_id,p.policy)
  code,code_hash,hint=new_code(s,u.tenant_id,prefix,custom);now=int(time.time())
  v=Voucher(site_id=b.site_id,tenant_id=u.tenant_id,package_id=p.id,policy=p.policy.copy(),code_hash=code_hash,code_hint=hint,code_format='custom' if custom else 'prefixed' if prefix else 'standard',code_prefix=prefix,issued_by=u.id,request_key=b.request_key,created=now,expires=now+b.expires_days*86400);s.add(v)
  try:s.flush();log(s,u,'voucher_issued',v.id);s.commit()
  except IntegrityError:s.rollback();raise HTTPException(409,'Issuance raced with another request; retry the same request key')
  return voucher_json(v)|{'code':display(code,prefix),'replayed':False}
 @app.post('/v1/vouchers/redeem')
 def redeem(b:VoucherRedeem,u=Depends(current),s=Depends(db)):
  if u.role!='guest':raise HTTPException(403,'Guest account required')
  now=int(time.time());key=digest('voucher-attempt:'+u.id);bucket=s.get(LoginAttempt,key)
  if not bucket:
   try:
    with s.begin_nested():s.add(LoginAttempt(key=key,failures=0,window_start=now));s.flush()
   except IntegrityError:pass
   bucket=s.get(LoginAttempt,key)
  if now-bucket.window_start>=900:bucket.failures=0;bucket.window_start=now
  if bucket.failures>=10:raise HTTPException(429,'Too many invalid voucher attempts; try again later')
  v=find_voucher(s,u.tenant_id,b.code)
  if v and v.site_id!=b.site_id:raise HTTPException(400,'Voucher belongs to a different site; choose the correct portal')
  if v and v.redeemed_by==u.id:
   e=s.scalar(select(Entitlement).where(Entitlement.voucher_id==v.id));return {'id':e.id,'voucher_id':v.id,'revoked':e.revoked,'fulfillment':'revoked' if e.revoked else 'pending_adapter','replayed':True}
  from .site_portal import selected_portal
  portal=selected_portal(s,u,b.site_id)
  if not portal or not portal.published or not portal.published['voucher_login']:raise HTTPException(409,'Voucher login is not enabled by this business')
  if not v or v.revoked or v.deleted_at or v.disabled_at or v.redeemed_by or v.expires<=now:
   s.execute(update(LoginAttempt).where(LoginAttempt.key==key).values(failures=LoginAttempt.failures+1));s.commit();raise HTTPException(400,'Voucher unavailable. Check the code or contact the owner.')
  result=s.execute(update(Voucher).where(Voucher.id==v.id,Voucher.redeemed_by.is_(None),Voucher.revoked==False,Voucher.disabled_at.is_(None),Voucher.deleted_at.is_(None),Voucher.expires>now).values(redeemed_by=u.id,redeemed_at=now))
  if result.rowcount!=1:raise HTTPException(409,'Voucher already processed. Check your passes before retrying.')
  e=Entitlement(site_id=v.site_id,voucher_id=v.id,tenant_id=u.tenant_id,guest_id=u.id,policy=v.policy.copy(),activated=now if v.policy.get('service')=='media' else None);s.add(e);bucket.failures=0
  try:s.flush();log(s,u,'voucher_redeemed',v.id);s.commit()
  except IntegrityError:s.rollback();raise HTTPException(409,'Voucher already processed. Check your passes before retrying.')
  return {'id':e.id,'voucher_id':v.id,'revoked':False,'fulfillment':'pending_adapter','replayed':False,'media_activated_at':e.activated}
 @app.post('/v1/vouchers/{id}/revoke')
 def revoke(id:str,b:VoucherRevoke,u=Depends(current),s=Depends(db)):
  owner(u);v=s.get(Voucher,id)
  if not v or v.tenant_id!=u.tenant_id or v.deleted_at:raise HTTPException(404,'Voucher not found')
  result=s.execute(update(Voucher).where(Voucher.id==id,Voucher.revoked==False).values(revoked=True,reason=b.reason,router_sync='revoke'))
  if result.rowcount:
   s.execute(update(Entitlement).where(Entitlement.voucher_id==id).values(revoked=True));log(s,u,'voucher_revoked',id);s.commit()
  s.refresh(v);return voucher_json(v)
