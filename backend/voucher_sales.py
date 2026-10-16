"""Owner-confirmed receipt/refund records; no money is transferred."""
import time
from fastapi import Depends,HTTPException
from sqlalchemy import select,update
from sqlalchemy.exc import IntegrityError
from .models import Voucher,VoucherSale,Entitlement
from .revenue import record_event
from .schemas import VoucherSaleIn,VoucherSaleRefund,VoucherSaleCancel

ACTIVE=VoucherSale.cancelled_at.is_(None)
def sale_json(sale):
 return {k:getattr(sale,k) for k in ['id','voucher_id','snapshot','amount','currency','method','reference','evidence','recorded_by','created','refunded_at','refunded_by','refund_reason','refund_reference','cancelled_at','cancelled_by','cancel_reason']}
def active_sale(s,voucher_id):return s.scalar(select(VoucherSale).where(VoucherSale.voucher_id==voucher_id,ACTIVE))
def register_voucher_sales(app,current,db,owner,log):
 def voucher(s,u,id):
  v=s.get(Voucher,id)
  if not v or v.tenant_id!=u.tenant_id:raise HTTPException(404,'Voucher not found')
  return v
 @app.post('/v1/vouchers/{id}/sale')
 def record(id:str,b:VoucherSaleIn,u=Depends(current),s=Depends(db)):
  owner(u);v=voucher(s,u,id);old=active_sale(s,id)
  if old:
   if any(getattr(old,k)!=getattr(b,k) for k in ['amount','method','reference','evidence']):raise HTTPException(409,'A different payment is already recorded for this voucher')
   return sale_json(old)|{'replayed':True}
  if v.dealer_id:raise HTTPException(409,'This voucher is with a dealer. Dealer stock is settled on the dealer ledger, not as a counter sale; return it to your stock first')
  if b.amount!=v.policy['price']:raise HTTPException(422,'Received amount must match the voucher package price; discounts and partial payments are not supported yet')
  # Claim a row lock shared with redemption/revocation before recording a sale.
  claimed=s.execute(update(Voucher).where(Voucher.id==id,Voucher.revoked==False,Voucher.disabled_at.is_(None),Voucher.deleted_at.is_(None),Voucher.dealer_id.is_(None)).values(reason=Voucher.reason))
  if not claimed.rowcount:raise HTTPException(409,'Revoked, disabled, deleted or dealer-held vouchers cannot be sold at the counter')
  s.refresh(v)
  if v.expires<=time.time() and not v.redeemed_by:raise HTTPException(409,'Unused voucher has expired')
  sale=VoucherSale(voucher_id=id,tenant_id=u.tenant_id,snapshot=v.policy.copy(),amount=b.amount,method=b.method,reference=b.reference,evidence=b.evidence,recorded_by=u.id,created=int(time.time()));s.add(sale)
  try:s.flush();record_event(s,u=u,source='voucher_sale',record=sale,site_id=v.site_id,occurred_at=sale.created);log(s,u,'voucher_payment_recorded',id);s.commit()
  except IntegrityError:s.rollback();raise HTTPException(409,'Voucher already has a payment record; refresh and check it')
  return sale_json(sale)|{'replayed':False}
 @app.post('/v1/vouchers/{id}/sale/refund')
 def refund(id:str,b:VoucherSaleRefund,u=Depends(current),s=Depends(db)):
  owner(u);v=voucher(s,u,id);sale=active_sale(s,id)
  if not sale:raise HTTPException(404,'No confirmed voucher payment')
  if sale.refunded_at:
   if sale.refund_reason!=b.reason or sale.refund_reference!=b.reference:raise HTTPException(409,'A different refund is already recorded')
   return sale_json(sale)|{'replayed':True}
  # Lock voucher first, as redemption also locks it before creating a pass.
  s.execute(update(Voucher).where(Voucher.id==id).values(reason=Voucher.reason))
  changed=s.execute(update(VoucherSale).where(VoucherSale.id==sale.id,VoucherSale.refunded_at.is_(None),ACTIVE).values(refunded_at=int(time.time()),refunded_by=u.id,refund_reason=b.reason,refund_reference=b.reference))
  if not changed.rowcount:raise HTTPException(409,'Refund already processed; refresh and check it')
  s.execute(update(Voucher).where(Voucher.id==id).values(revoked=True,reason=b.reason));s.execute(update(Entitlement).where(Entitlement.voucher_id==id).values(revoked=True));log(s,u,'voucher_refund_recorded',id);record_event(s,u=u,source='voucher_sale',record=sale,site_id=v.site_id,kind='refund',reference=b.reference,occurred_at=sale.refunded_at);s.commit();s.refresh(sale)
  return sale_json(sale)|{'replayed':False}
 @app.post('/v1/vouchers/{id}/sale/cancel')
 def cancel(id:str,b:VoucherSaleCancel,u=Depends(current),s=Depends(db)):
  """Undo a counter sale of a voucher nobody has used: the sale stays as history and the voucher returns to unsold stock."""
  owner(u);v=voucher(s,u,id)
  # Same row lock as redemption, so a voucher cannot be used while its sale is being cancelled.
  s.execute(update(Voucher).where(Voucher.id==id).values(reason=Voucher.reason));s.refresh(v)
  sale=active_sale(s,id)
  if not sale:
   last=s.scalar(select(VoucherSale).where(VoucherSale.voucher_id==id,VoucherSale.cancelled_at.is_not(None)).order_by(VoucherSale.cancelled_at.desc()).limit(1))
   if last and last.cancel_reason==b.reason:return sale_json(last)|{'replayed':True}
   raise HTTPException(404,'No active sale to cancel for this voucher')
  if sale.refunded_at:raise HTTPException(409,'This sale was already refunded')
  if v.redeemed_by:raise HTTPException(409,'This voucher has been used, so the sale cannot be cancelled. Record a refund instead')
  now=int(time.time())
  changed=s.execute(update(VoucherSale).where(VoucherSale.id==sale.id,ACTIVE,VoucherSale.refunded_at.is_(None)).values(cancelled_at=now,cancelled_by=u.id,cancel_reason=b.reason))
  if not changed.rowcount:s.rollback();raise HTTPException(409,'This sale changed at the same time; refresh and check it')
  record_event(s,u=u,source='voucher_sale',record=sale,site_id=v.site_id,kind='refund',reference=('Sale cancelled: '+b.reason)[:160],occurred_at=now)
  log(s,u,'voucher_sale_cancelled',id);s.commit();s.refresh(sale)
  return sale_json(sale)|{'replayed':False}
