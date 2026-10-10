"""Durable offline voucher reconciliation records; no silent access grants."""
import time
from fastapi import Depends,HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from .models import OfflineVoucherEvent,Voucher
from .schemas import OfflineVoucherEventIn
from .voucher_codes import candidate_hashes,find_voucher,scoped_hash

def event_json(x):return {k:getattr(x,k) for k in ['id','site_id','event_key','voucher_id','event_type','local_time','device_id','status','reason','created']}
def register_offline_vouchers(app,current,db,owner,log):
 @app.post('/v1/vouchers/offline-events',status_code=201)
 def ingest(b:OfflineVoucherEventIn,u=Depends(current),s=Depends(db)):
  owner(u);digest=scoped_hash(u.tenant_id,b.code)
  existing=s.scalar(select(OfflineVoucherEvent).where(OfflineVoucherEvent.tenant_id==u.tenant_id,OfflineVoucherEvent.event_key==b.event_key))
  if existing:
   if existing.code_hash not in candidate_hashes(u.tenant_id,b.code) or existing.site_id!=b.site_id or existing.event_type!=b.event_type:raise HTTPException(409,'Offline event key reused with different data')
   return JSONResponse(status_code=200,content=event_json(existing)|{'replayed':True})
  from .sites import allowed_site
  allowed_site(s,u,b.site_id)
  voucher=find_voucher(s,u.tenant_id,b.code)
  reason=None;status='pending_review';voucher_id=voucher.id if voucher else None
  if not voucher:status='conflict';reason='Voucher is not part of this business inventory'
  elif voucher.site_id and voucher.site_id!=b.site_id:status='conflict';reason='Voucher belongs to another site'
  elif voucher.revoked:status='conflict';reason='Voucher is revoked'
  elif voucher.deleted_at:status='conflict';reason='Voucher was deleted'
  elif voucher.disabled_at:status='conflict';reason='Voucher is disabled'
  elif voucher.expires<=b.local_time:status='conflict';reason='Voucher was expired at the local event time'
  x=OfflineVoucherEvent(tenant_id=u.tenant_id,site_id=b.site_id,event_key=b.event_key,voucher_id=voucher_id,code_hash=digest,event_type=b.event_type,local_time=b.local_time,device_id=b.device_id,status=status,reason=reason,created=int(time.time()));s.add(x)
  try:s.flush();log(s,u,'offline_voucher_event_ingested',x.id);s.commit()
  except IntegrityError:s.rollback();raise HTTPException(409,'Offline event raced with another request; retry with the same event key')
  return event_json(x)|{'replayed':False,'access_granted':False}

 @app.get('/v1/vouchers/offline-events')
 def events(u=Depends(current),s=Depends(db)):
  owner(u);return [event_json(x) for x in s.scalars(select(OfflineVoucherEvent).where(OfflineVoucherEvent.tenant_id==u.tenant_id).order_by(OfflineVoucherEvent.created.desc()))]
