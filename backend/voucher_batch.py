"""Atomic batch issuance; full codes are never stored and appear once."""
import time
from fastapi import Depends,HTTPException
from pydantic import Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from .schemas import VoucherIssue
from .models import Voucher,Package
from .vouchers import digest,voucher_json
from .voucher_codes import new_code,normalize_prefix,display
from .sites import allowed_site
from .media import ensure_media_offer,ensure_sold_separately
class BatchIn(VoucherIssue):
 count:int=Field(ge=1,le=100)
def register_voucher_batch(app,current,db,owner,log):
 @app.post('/v1/vouchers/batch',status_code=201)
 def issue(b:BatchIn,u=Depends(current),s=Depends(db)):
  owner(u);code_prefix=normalize_prefix(b.prefix)
  if b.custom_code:raise HTTPException(422,'Custom codes are issued one at a time')
  prefix='batch:'+digest(b.request_key)[:40]+':'
  previous=list(s.scalars(select(Voucher).where(Voucher.issued_by==u.id,Voucher.request_key.like(prefix+'%')).order_by(Voucher.request_key)))
  if previous:
   if len(previous)!=b.count or any(v.site_id!=b.site_id or v.package_id!=b.package_id or v.expires-v.created!=b.expires_days*86400 or v.code_prefix!=code_prefix for v in previous):raise HTTPException(409,'Batch request key reused with different settings')
   return {'replayed':True,'items':[voucher_json(v)|{'code':None} for v in previous],'message':'Already issued. Codes are shown only once; revoke lost codes before issuing replacements.'}
  if b.site_id:allowed_site(s,u,b.site_id)
  package=s.get(Package,b.package_id)
  if not package or package.tenant_id!=u.tenant_id or not package.active:raise HTTPException(404,'Package not available')
  ensure_sold_separately(package.policy);ensure_media_offer(s,u.tenant_id,package.policy);now=int(time.time());items=[];codes=set()
  for i in range(b.count):
   code,code_hash,hint=new_code(s,u.tenant_id,code_prefix,exclude=codes);codes.add(code)
   v=Voucher(site_id=b.site_id,tenant_id=u.tenant_id,package_id=package.id,policy=package.policy.copy(),code_hash=code_hash,code_hint=hint,code_format='prefixed' if code_prefix else 'standard',code_prefix=code_prefix,issued_by=u.id,request_key=prefix+str(i).zfill(3),created=now,expires=now+b.expires_days*86400);s.add(v);items.append((v,display(code,code_prefix)))
  try:
   s.flush()
   for v,_ in items:log(s,u,'voucher_batch_issued',v.id)
   s.commit()
  except IntegrityError:s.rollback();raise HTTPException(409,'Batch issuance raced; retry the same request key')
  return {'replayed':False,'items':[voucher_json(v)|{'code':code} for v,code in items]}
