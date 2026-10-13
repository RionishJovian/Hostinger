"""Frozen-v1 voucher lifecycle: Delete (unused only), Disable, Re-enable. Revoke stays permanent.

There is no Reset action. Every change records the router follow-up it needs in `router_sync`;
no router is updated here. Disable and revoke are high priority when a router reconnects.
"""
import time
from fastapi import Depends,HTTPException
from pydantic import Field
from sqlalchemy import select,update
from .models import Voucher,VoucherSale
from .schemas import Strict
from .vouchers import voucher_json

HIGH_PRIORITY_SYNC=('disable','revoke')

class VoucherReason(Strict):reason:str=Field(min_length=1,max_length=1000)

def register_voucher_lifecycle(app,current,db,owner,log):
 def load(s,u,id):
  v=s.get(Voucher,id)
  if not v or v.tenant_id!=u.tenant_id or v.deleted_at:raise HTTPException(404,'Voucher not found')
  return v
 def changed(s,u,v,action,result,message):
  if result.rowcount!=1:
   s.rollback();raise HTTPException(409,message)
  log(s,u,'voucher_'+action,v.id);s.commit();s.refresh(v)
  if hasattr(app.state,'hotspot_sync_voucher'):app.state.hotspot_sync_voucher(s,v)
  return voucher_json(v)

 @app.post('/v1/vouchers/{id}/disable')
 def disable(id:str,b:VoucherReason,u=Depends(current),s=Depends(db)):
  owner(u);v=load(s,u,id);now=int(time.time())
  if v.revoked:raise HTTPException(409,'Revoked vouchers are permanent and cannot be disabled')
  if v.disabled_at:raise HTTPException(409,'Voucher is already disabled')
  if not v.redeemed_by and v.expires<=now:raise HTTPException(409,'Expired unused vouchers cannot be disabled; they are already unusable')
  result=s.execute(update(Voucher).where(Voucher.id==id,Voucher.revoked==False,Voucher.disabled_at.is_(None),Voucher.deleted_at.is_(None)).values(disabled_at=now,disabled_reason=b.reason,router_sync='disable'))
  return changed(s,u,v,'disabled',result,'Voucher changed at the same time; refresh and try again')

 @app.post('/v1/vouchers/{id}/enable')
 def enable(id:str,u=Depends(current),s=Depends(db)):
  owner(u);v=load(s,u,id)
  if v.revoked:raise HTTPException(409,'Revoked vouchers are permanent and cannot be re-enabled')
  if not v.disabled_at:raise HTTPException(409,'Voucher is not disabled')
  result=s.execute(update(Voucher).where(Voucher.id==id,Voucher.revoked==False,Voucher.disabled_at.is_not(None),Voucher.deleted_at.is_(None)).values(disabled_at=None,disabled_reason=None,router_sync='enable'))
  return changed(s,u,v,'reenabled',result,'Voucher changed at the same time; refresh and try again')

 @app.post('/v1/vouchers/{id}/delete')
 def delete(id:str,u=Depends(current),s=Depends(db)):
  owner(u);v=load(s,u,id)
  if v.redeemed_by or v.activated:raise HTTPException(409,'Activated vouchers cannot be deleted; disable it instead')
  if v.revoked:raise HTTPException(409,'Revoked vouchers stay in permanent voucher history')
  if v.dealer_id:raise HTTPException(409,'This voucher is with a dealer; return it to your stock or disable it instead')
  result=s.execute(update(Voucher).where(Voucher.id==id,Voucher.redeemed_by.is_(None),Voucher.activated.is_(None),Voucher.revoked==False,Voucher.deleted_at.is_(None),Voucher.dealer_id.is_(None)).values(deleted_at=int(time.time()),router_sync='delete'))
  # The row lock above is shared with sale recording, so a concurrent sale is visible here.
  if result.rowcount==1 and s.scalar(select(VoucherSale.id).where(VoucherSale.voucher_id==id,VoucherSale.cancelled_at.is_(None))):
   s.rollback();raise HTTPException(409,'A payment is recorded for this voucher; disable it or record a refund instead')
  return changed(s,u,v,'deleted',result,'Voucher was redeemed or changed at the same time; refresh and check it')
