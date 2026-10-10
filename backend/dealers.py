"""Frozen-v1 owner-managed dealers and physical voucher stock.

Dealers have no login, app or portal in v1; the Owner/Admin records every handover, payment and count.
Generated ≠ Sold and Activated ≠ Sold: handing stock to a dealer charges the agreed dealer (wholesale)
price on a separate settlement ledger and never becomes counter-sale revenue. Ranking uses activated
vouchers and is never called sales. Movement and ledger rows are append-only; corrections and reversals
are new rows. Only unused vouchers move: activated, expired and revoked vouchers stay with the dealer.
"""
import time
from typing import Literal
from fastapi import Depends,HTTPException
from pydantic import Field,model_validator
from sqlalchemy import select,update,func
from sqlalchemy.exc import IntegrityError
from .models import Voucher,VoucherSale,VoucherProductionJob,Dealer,DealerMovement,DealerLedgerEntry
from .schemas import Strict
from .vouchers import voucher_json

MAX_DEALERS=200
MAX_BATCH=1000
MAX_MONEY=1_000_000_000
REASONS={'lost':'Lost','damaged':'Damaged','counting_difference':'Counting difference','other':'Other'}
METHODS=Literal['Cash','KBZPay','WavePay','Other']

def request_key():return Field(min_length=8,max_length=72)

class DealerIn(Strict):
 name:str=Field(min_length=1,max_length=120)
 location:str|None=Field(default=None,max_length=160)
 phone:str|None=Field(default=None,max_length=40)
 short_code:str|None=Field(default=None,max_length=6,pattern=r'^[A-Za-z0-9]*$')
 settlement:Literal['prepaid','credit']
 credit_limit:int|None=Field(default=None,ge=0,le=MAX_MONEY)
class Selection(Strict):
 voucher_ids:list[str]|None=Field(default=None,min_length=1,max_length=MAX_BATCH)
 serial_from:int|None=Field(default=None,ge=1)
 serial_to:int|None=Field(default=None,ge=1)
 production_job_id:str|None=Field(default=None,min_length=1,max_length=36)
 note:str|None=Field(default=None,max_length=500)
 request_key:str=request_key()
 @model_validator(mode='after')
 def one_way(self):
  ranged=self.serial_from is not None
  if ranged!=(self.serial_to is not None):raise ValueError('Give both the first and last serial number')
  if ranged and self.serial_to<self.serial_from:raise ValueError('The last serial number must not be lower than the first')
  if ranged and self.serial_to-self.serial_from>=MAX_BATCH:raise ValueError(f'Move up to {MAX_BATCH} vouchers at a time')
  if self.voucher_ids and (ranged or self.production_job_id):raise ValueError('Choose vouchers by ID or by serial range, not both')
  if not (self.voucher_ids or ranged or self.production_job_id):raise ValueError('Choose the vouchers to move')
  return self
class AssignIn(Selection):unit_price:int=Field(ge=0,le=MAX_MONEY)
class ReturnIn(Selection):
 to_dealer_id:str|None=Field(default=None,min_length=1,max_length=36)
 unit_price:int|None=Field(default=None,ge=0,le=MAX_MONEY)
 credit:bool=True
 @model_validator(mode='after')
 def reassign_price(self):
  if self.to_dealer_id and self.unit_price is None:raise ValueError('Enter the dealer price for the receiving dealer')
  return self
class StockCheckIn(Strict):
 counted:int=Field(ge=0,le=100_000)
 missing_serials:list[int]=Field(default_factory=list,max_length=MAX_BATCH)
 reason:Literal['lost','damaged','counting_difference','other']|None=None
 note:str|None=Field(default=None,max_length=500)
 disable_missing:bool=False
 request_key:str=request_key()
class PaymentIn(Strict):
 amount:int=Field(gt=0,le=MAX_MONEY)
 method:METHODS
 reference:str|None=Field(default=None,max_length=160)
 note:str|None=Field(default=None,max_length=500)
 request_key:str=request_key()
class AdjustmentIn(Strict):
 direction:Literal['credit','charge']
 amount:int=Field(gt=0,le=MAX_MONEY)
 reason:str=Field(min_length=1,max_length=500)
 request_key:str=request_key()
class ReverseIn(Strict):
 reason:str=Field(min_length=1,max_length=500)
 request_key:str=request_key()

def usable(now):return (Voucher.redeemed_by.is_(None),Voucher.revoked==False,Voucher.disabled_at.is_(None),Voucher.deleted_at.is_(None),Voucher.expires>now)
def serial(n):return f'{n:06d}' if n else '—'
def span(vouchers):
 numbers=sorted({v.serial_no for v in vouchers if v.serial_no});parts=[];i=0
 while i<len(numbers):
  j=i
  while j+1<len(numbers) and numbers[j+1]==numbers[j]+1:j+=1
  parts.append(serial(numbers[i]) if i==j else f'{serial(numbers[i])}–{serial(numbers[j])}');i=j+1
 return ', '.join(parts) or None
def record(s,model,**fields):
 """Append a movement or ledger row with the next per-dealer sequence number (the dealer row is locked)."""
 s.flush();row=model(seq=(s.scalar(select(func.max(model.seq)).where(model.dealer_id==fields['dealer_id'])) or 0)+1,**fields);s.add(row)
 try:s.flush()
 except IntegrityError:s.rollback();raise HTTPException(409,'This change was already recorded; refresh to see it')
 return row
def balance(s,dealer_id):return int(s.scalar(select(func.coalesce(func.sum(DealerLedgerEntry.delta),0)).where(DealerLedgerEntry.dealer_id==dealer_id)) or 0)
def refuse(bad,verb):
 parts=[f"{why}: {', '.join(serial(x) for x in xs[:10])}{' …' if len(xs)>10 else ''}" for why,xs in bad.items()]
 raise HTTPException(409,f'Cannot {verb} these vouchers — '+'; '.join(parts))
def problems(vouchers,check):
 bad={}
 for v in vouchers:
  why=check(v)
  if why:bad.setdefault(why,[]).append(v.serial_no)
 return bad
def money_check(dealer,current,charge):
 after=current+charge
 if charge<=0:return
 if dealer.settlement=='prepaid' and after>0:raise HTTPException(409,f'Prepaid dealer: record a payment of at least {after} MMK before handing over this stock')
 if dealer.settlement=='credit' and dealer.credit_limit is not None and after>dealer.credit_limit:raise HTTPException(409,f'This would bring the balance owed to {after} MMK, above the {dealer.credit_limit} MMK credit limit. Record a payment or raise the limit first')
def assign_problem(v,sold):
 status=voucher_json(v)['status']
 if status!='unused':return {'redeemed':'already activated'}.get(status,status)
 if v.dealer_id:return 'already with a dealer'
 if v.id in sold:return 'already sold at the counter'

def hand_over(s,u,log,dealer,vouchers,unit_price,key,kind='assign',note=None,job_id=None,counterpart=None):
 """Give unused, unsold, unassigned vouchers to a dealer and charge the dealer price."""
 now=int(time.time());ids=[v.id for v in vouchers]
 sold=set(s.scalars(select(VoucherSale.voucher_id).where(VoucherSale.voucher_id.in_(ids))))
 bad=problems(vouchers,lambda v:assign_problem(v,sold))
 if bad:refuse(bad,'hand over')
 charge=unit_price*len(ids);money_check(dealer,balance(s,dealer.id),charge)
 result=s.execute(update(Voucher).where(Voucher.id.in_(ids),Voucher.tenant_id==u.tenant_id,Voucher.dealer_id.is_(None),*usable(now)).values(dealer_id=dealer.id,dealer_price=unit_price).execution_options(synchronize_session=False))
 if result.rowcount!=len(ids):s.rollback();raise HTTPException(409,'Some vouchers changed at the same time; refresh and try again')
 # The update above takes the row lock that counter-sale recording also takes.
 if s.scalar(select(VoucherSale.id).where(VoucherSale.voucher_id.in_(ids))):s.rollback();raise HTTPException(409,'A counter sale was recorded at the same time; refresh and try again')
 movement=record(s,DealerMovement,tenant_id=u.tenant_id,dealer_id=dealer.id,kind=kind,voucher_ids=ids,count=len(ids),unit_price=unit_price,production_job_id=job_id,counterpart_dealer_id=counterpart,note=note,details={'serials':span(vouchers),'face_value':sum(int(v.policy.get('price') or 0) for v in vouchers)},request_key=key,actor_id=u.id,created=now)
 if charge:record(s,DealerLedgerEntry,tenant_id=u.tenant_id,dealer_id=dealer.id,kind='charge',delta=charge,movement_id=movement.id,note=f'{len(ids)} vouchers × {unit_price} MMK',request_key=key+':charge',actor_id=u.id,created=now)
 log(s,u,'dealer_stock_assigned',movement.id)
 for v in vouchers:s.expire(v)
 return movement

def take_back(s,u,log,dealer,vouchers,key,credit,kind='return',note=None,counterpart=None):
 """Return unused vouchers from a dealer to the owner's stock, crediting what was charged."""
 now=int(time.time())
 def problem(v):
  if v.dealer_id!=dealer.id:return 'not held by this dealer'
  if v.revoked:return 'revoked'
  if v.redeemed_by:return 'already activated'
  if v.expires<=now:return 'expired'
 bad=problems(vouchers,problem)
 if bad:refuse(bad,'return')
 ids=[v.id for v in vouchers];credited=sum(v.dealer_price or 0 for v in vouchers) if credit else 0
 result=s.execute(update(Voucher).where(Voucher.id.in_(ids),Voucher.dealer_id==dealer.id,Voucher.redeemed_by.is_(None),Voucher.revoked==False,Voucher.deleted_at.is_(None),Voucher.expires>now).values(dealer_id=None,dealer_price=None).execution_options(synchronize_session=False))
 if result.rowcount!=len(ids):s.rollback();raise HTTPException(409,'Some vouchers were activated or changed at the same time; refresh and try again')
 movement=record(s,DealerMovement,tenant_id=u.tenant_id,dealer_id=dealer.id,kind=kind,voucher_ids=ids,count=len(ids),counterpart_dealer_id=counterpart,note=note,details={'serials':span(vouchers),'credited':credited},request_key=key,actor_id=u.id,created=now)
 if credited:record(s,DealerLedgerEntry,tenant_id=u.tenant_id,dealer_id=dealer.id,kind='return_credit',delta=-credited,movement_id=movement.id,note=f'{len(ids)} unused vouchers returned',request_key=key+':credit',actor_id=u.id,created=now)
 log(s,u,'dealer_stock_returned',movement.id)
 for v in vouchers:s.refresh(v)
 return movement

def register_dealers(app,current,db,owner,log):
 def dealer_for(s,u,id,lock=False,active=True):
  d=s.get(Dealer,id,with_for_update=lock)
  if not d or d.tenant_id!=u.tenant_id:raise HTTPException(404,'Dealer not found')
  if active and d.archived_at:raise HTTPException(409,'This dealer is archived')
  return d
 def dealer_json(d):return {k:getattr(d,k) for k in ['id','name','location','phone','short_code','settlement','credit_limit','created','archived_at']}
 def stats(s,d):
  counts={}
  for v in s.scalars(select(Voucher).where(Voucher.dealer_id==d.id,Voucher.deleted_at.is_(None))):
   status=voucher_json(v)['status'];counts[status]=counts.get(status,0)+1
  moved=dict(s.execute(select(DealerMovement.kind,func.sum(DealerMovement.count)).where(DealerMovement.dealer_id==d.id).group_by(DealerMovement.kind)).all())
  last=s.scalar(select(DealerMovement.count).where(DealerMovement.dealer_id==d.id,DealerMovement.kind.in_(['assign','reassign_in'])).order_by(DealerMovement.seq.desc()).limit(1))
  unused=counts.get('unused',0)
  return {'holding':counts,'unused':unused,'activated':counts.get('redeemed',0),'received':int(moved.get('assign',0)+moved.get('reassign_in',0)),'returned':int(moved.get('return',0)+moved.get('reassign_out',0)),'balance':balance(s,d.id),'low_stock':bool(last) and unused<=last//5}
 def detail(s,d):
  held=list(s.scalars(select(Voucher).where(Voucher.dealer_id==d.id,Voucher.deleted_at.is_(None)).order_by(Voucher.serial_no)))
  moves=s.scalars(select(DealerMovement).where(DealerMovement.dealer_id==d.id).order_by(DealerMovement.seq.desc()))
  ledger=s.scalars(select(DealerLedgerEntry).where(DealerLedgerEntry.dealer_id==d.id).order_by(DealerLedgerEntry.seq.desc()))
  reversed_ids=set(s.scalars(select(DealerLedgerEntry.reverses_id).where(DealerLedgerEntry.dealer_id==d.id,DealerLedgerEntry.reverses_id.is_not(None))))
  return dealer_json(d)|stats(s,d)|{
   'vouchers':[{k:voucher_json(v)[k] for k in ['id','serial_no','package_id','status','production_job_id','expires']}|{'dealer_price':v.dealer_price,'face_price':v.policy.get('price')} for v in held],
   'movements':[{k:getattr(m,k) for k in ['id','seq','kind','count','unit_price','production_job_id','counterpart_dealer_id','reason','note','details','created']} for m in moves],
   'ledger':[{k:getattr(e,k) for k in ['id','seq','kind','delta','method','reference','note','movement_id','reverses_id','created']}|{'reversed':e.id in reversed_ids} for e in ledger]}
 def replayed(s,u,model,key,d):
  if s.scalar(select(model.id).where(model.tenant_id==u.tenant_id,model.request_key==key)):return detail(s,d)|{'replayed':True}
 def commit(s):
  try:s.commit()
  except IntegrityError:s.rollback();raise HTTPException(409,'This change was already recorded; refresh to see it')
 def choose(s,u,b):
  q=select(Voucher).where(Voucher.tenant_id==u.tenant_id,Voucher.deleted_at.is_(None));job=None
  if b.production_job_id:
   job=s.get(VoucherProductionJob,b.production_job_id)
   if not job or job.tenant_id!=u.tenant_id:raise HTTPException(404,'Production job not found')
   q=q.where(Voucher.production_job_id==job.id)
  if b.voucher_ids:q=q.where(Voucher.id.in_(set(b.voucher_ids)))
  if b.serial_from is not None:q=q.where(Voucher.serial_no.between(b.serial_from,b.serial_to))
  found=list(s.scalars(q.order_by(Voucher.serial_no,Voucher.created)))
  if b.voucher_ids and len(found)!=len(set(b.voucher_ids)):raise HTTPException(404,'Some vouchers were not found')
  if b.serial_from is not None and len(found)!=b.serial_to-b.serial_from+1:raise HTTPException(404,f"Not every serial from {serial(b.serial_from)} to {serial(b.serial_to)} exists{' in this job' if job else ''}")
  if not found:raise HTTPException(404,'No vouchers match this selection')
  if len(found)>MAX_BATCH:raise HTTPException(422,f'Move up to {MAX_BATCH} vouchers at a time')
  return found,job

 @app.get('/v1/dealers')
 def dealers(include_archived:bool=False,u=Depends(current),s=Depends(db)):
  owner(u);q=select(Dealer).where(Dealer.tenant_id==u.tenant_id)
  if not include_archived:q=q.where(Dealer.archived_at.is_(None))
  rows=[dealer_json(d)|stats(s,d) for d in s.scalars(q)]
  rows.sort(key=lambda r:(-r['activated'],r['name'].casefold()))
  return [r|{'rank':i+1} for i,r in enumerate(rows)]

 @app.post('/v1/dealers',status_code=201)
 def create(b:DealerIn,u=Depends(current),s=Depends(db)):
  owner(u);active=list(s.scalars(select(Dealer).where(Dealer.tenant_id==u.tenant_id,Dealer.archived_at.is_(None))))
  if any(d.name.casefold()==b.name.casefold() for d in active):raise HTTPException(409,'A dealer with this name already exists')
  if len(active)>=MAX_DEALERS:raise HTTPException(409,f'Archive a dealer first; up to {MAX_DEALERS} active dealers are kept')
  d=Dealer(tenant_id=u.tenant_id,**(b.model_dump()|{'short_code':(b.short_code or '').upper() or None,'location':b.location or None,'phone':b.phone or None}),created_by=u.id,created=int(time.time()))
  s.add(d);s.flush();log(s,u,'dealer_created',d.id);s.commit();return detail(s,d)

 @app.get('/v1/dealers/{id}')
 def show(id:str,u=Depends(current),s=Depends(db)):
  owner(u);return detail(s,dealer_for(s,u,id,active=False))

 @app.post('/v1/dealers/{id}/update')
 def edit(id:str,b:DealerIn,u=Depends(current),s=Depends(db)):
  owner(u);d=dealer_for(s,u,id,lock=True)
  if any(x.id!=d.id and x.name.casefold()==b.name.casefold() for x in s.scalars(select(Dealer).where(Dealer.tenant_id==u.tenant_id,Dealer.archived_at.is_(None)))):raise HTTPException(409,'A dealer with this name already exists')
  for k,v in (b.model_dump()|{'short_code':(b.short_code or '').upper() or None,'location':b.location or None,'phone':b.phone or None}).items():setattr(d,k,v)
  log(s,u,'dealer_updated',d.id);s.commit();return detail(s,d)

 @app.post('/v1/dealers/{id}/archive')
 def archive(id:str,u=Depends(current),s=Depends(db)):
  owner(u);d=dealer_for(s,u,id,lock=True);st=stats(s,d)
  if st['unused'] or st['holding'].get('disabled'):raise HTTPException(409,'Return or check this dealer\'s unused stock before archiving')
  if st['balance']:raise HTTPException(409,'Settle or correct the dealer balance to zero before archiving')
  d.archived_at=int(time.time());log(s,u,'dealer_archived',d.id);s.commit();return detail(s,d)

 @app.post('/v1/dealers/{id}/assign')
 def assign(id:str,b:AssignIn,u=Depends(current),s=Depends(db)):
  owner(u);d=dealer_for(s,u,id,lock=True)
  if (r:=replayed(s,u,DealerMovement,b.request_key,d)):return r
  vouchers,job=choose(s,u,b)
  if job and not b.voucher_ids and b.serial_from is None:
   # "Everything left in this job": skip cards already activated, sold, disabled or with a dealer.
   sold=set(s.scalars(select(VoucherSale.voucher_id).where(VoucherSale.voucher_id.in_([v.id for v in vouchers]))))
   vouchers=[v for v in vouchers if not assign_problem(v,sold)]
   if not vouchers:raise HTTPException(409,'No unused vouchers are left in this job to hand over')
  hand_over(s,u,log,d,vouchers,b.unit_price,b.request_key,note=b.note,job_id=job.id if job else None);commit(s);return detail(s,d)

 @app.post('/v1/dealers/{id}/return')
 def give_back(id:str,b:ReturnIn,u=Depends(current),s=Depends(db)):
  owner(u)
  if b.to_dealer_id==id:raise HTTPException(422,'Choose a different dealer to receive the stock')
  ids=sorted({id,b.to_dealer_id} if b.to_dealer_id else {id})
  locked={x:dealer_for(s,u,x,lock=True) for x in ids};d=locked[id]
  if (r:=replayed(s,u,DealerMovement,b.request_key,d)):return r
  vouchers,_=choose(s,u,b)
  if b.to_dealer_id:
   target=locked[b.to_dealer_id]
   take_back(s,u,log,d,vouchers,b.request_key,b.credit,kind='reassign_out',note=b.note,counterpart=target.id)
   hand_over(s,u,log,target,vouchers,b.unit_price,b.request_key+':in',kind='reassign_in',note=b.note,counterpart=d.id)
  else:take_back(s,u,log,d,vouchers,b.request_key,b.credit,note=b.note)
  commit(s);return detail(s,d)

 @app.post('/v1/dealers/{id}/stock-check')
 def stock_check(id:str,b:StockCheckIn,u=Depends(current),s=Depends(db)):
  owner(u);d=dealer_for(s,u,id,lock=True)
  if (r:=replayed(s,u,DealerMovement,b.request_key,d)):return r
  now=int(time.time());held=list(s.scalars(select(Voucher).where(Voucher.dealer_id==d.id,*usable(now)).order_by(Voucher.serial_no)))
  by_serial={v.serial_no:v for v in held};wanted=sorted(set(b.missing_serials))
  unknown=[x for x in wanted if x not in by_serial]
  if unknown:raise HTTPException(409,'Not in this dealer\'s unused stock: '+', '.join(serial(x) for x in unknown[:10]))
  difference=b.counted-len(held)
  if (difference or wanted) and not b.reason:raise HTTPException(422,'Choose a reason for the difference: Lost, Damaged, Counting difference or Other')
  if b.disable_missing and not wanted:raise HTTPException(422,'List the missing serial numbers to disable')
  missing=[by_serial[x] for x in wanted];disabled=0
  if b.disable_missing:
   ids=[v.id for v in missing]
   result=s.execute(update(Voucher).where(Voucher.id.in_(ids),Voucher.dealer_id==d.id,*usable(now)).values(disabled_at=now,disabled_reason=f'Dealer stock check · {REASONS[b.reason]} · {d.name}'+(f': {b.note}' if b.note else ''),router_sync='disable').execution_options(synchronize_session=False))
   if result.rowcount!=len(ids):s.rollback();raise HTTPException(409,'Some vouchers were activated or changed at the same time; refresh and check again')
   disabled=len(ids)
   for vid in ids:log(s,u,'voucher_disabled',vid)
  for v in missing:s.expire(v)
  m=record(s,DealerMovement,tenant_id=u.tenant_id,dealer_id=d.id,kind='stock_check',voucher_ids=[v.id for v in missing],count=len(missing),reason=b.reason,note=b.note,details={'expected':len(held),'counted':b.counted,'difference':difference,'missing_serials':wanted,'disabled':disabled},request_key=b.request_key,actor_id=u.id,created=now)
  log(s,u,'dealer_stock_checked',m.id);commit(s)
  return detail(s,d)|{'check':m.details,'message':'The dealer balance is unchanged. Record a correction if you agree to credit missing stock.'}

 @app.post('/v1/dealers/{id}/payments')
 def payment(id:str,b:PaymentIn,u=Depends(current),s=Depends(db)):
  owner(u);d=dealer_for(s,u,id,lock=True)
  if (r:=replayed(s,u,DealerLedgerEntry,b.request_key,d)):return r
  e=record(s,DealerLedgerEntry,tenant_id=u.tenant_id,dealer_id=d.id,kind='payment',delta=-b.amount,method=b.method,reference=b.reference or None,note=b.note or None,request_key=b.request_key,actor_id=u.id,created=int(time.time()))
  log(s,u,'dealer_payment_recorded',e.id);commit(s);return detail(s,d)

 @app.post('/v1/dealers/{id}/adjustments')
 def adjustment(id:str,b:AdjustmentIn,u=Depends(current),s=Depends(db)):
  owner(u);d=dealer_for(s,u,id,lock=True)
  if (r:=replayed(s,u,DealerLedgerEntry,b.request_key,d)):return r
  e=record(s,DealerLedgerEntry,tenant_id=u.tenant_id,dealer_id=d.id,kind='adjustment',delta=b.amount if b.direction=='charge' else -b.amount,note=b.reason,request_key=b.request_key,actor_id=u.id,created=int(time.time()))
  log(s,u,'dealer_adjustment_recorded',e.id);commit(s);return detail(s,d)

 @app.post('/v1/dealers/{id}/ledger/{entry}/reverse')
 def reverse(id:str,entry:str,b:ReverseIn,u=Depends(current),s=Depends(db)):
  owner(u);d=dealer_for(s,u,id,lock=True)
  if (r:=replayed(s,u,DealerLedgerEntry,b.request_key,d)):return r
  original=s.get(DealerLedgerEntry,entry)
  if not original or original.dealer_id!=d.id:raise HTTPException(404,'Ledger entry not found')
  if original.kind not in ('payment','adjustment'):raise HTTPException(409,'Only payments and corrections can be reversed; stock charges and credits follow stock returns')
  if s.scalar(select(DealerLedgerEntry.id).where(DealerLedgerEntry.reverses_id==original.id)):raise HTTPException(409,'This entry was already reversed')
  e=record(s,DealerLedgerEntry,tenant_id=u.tenant_id,dealer_id=d.id,kind='reversal',delta=-original.delta,note=b.reason,reverses_id=original.id,request_key=b.request_key,actor_id=u.id,created=int(time.time()))
  log(s,u,'dealer_ledger_reversed',e.id);commit(s);return detail(s,d)
