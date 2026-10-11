"""Platform subscription records; no payment gateway or router cutoff.

Terms run in whole calendar months in the subscription timezone and end at local midnight, so the
expiry date is the first day without paid access: the owner is warned for the seven days before it
and, from that date, can sign in only to renew.
"""
import time,calendar
from datetime import datetime,date,time as day_time
from zoneinfo import ZoneInfo
from typing import Literal
from fastapi import Depends,HTTPException
from pydantic import Field,model_validator
from sqlalchemy import select,update
from sqlalchemy.exc import IntegrityError
from .models import SubscriptionPlan,TenantSubscription,Tenant
from .schemas import Strict
class PlanIn(Strict):
 name:str=Field(min_length=1,max_length=120)
 monthly_price:int=Field(ge=0,le=1000000000)
 currency:str=Field(default='MMK',pattern=r'^[A-Z]{3}$')
 site_limit:int=Field(ge=1,le=10000)
 router_limit:int=Field(ge=1,le=10000)
 notes:str=Field(default='',max_length=2000)
class SubscriptionIn(Strict):
 expected_revision:int=Field(ge=0)
 plan_id:str
 state:Literal['trial','active','past_due','suspended','cancelled']
 period_start:int=Field(ge=0)
 period_end:int=Field(gt=0)
 reason:str=Field(min_length=1,max_length=1000)
 @model_validator(mode='after')
 def dates(self):
  if self.period_end<=self.period_start:raise ValueError('Period end must follow start')
  return self
SUBSCRIPTION_TZ='Asia/Yangon'
WARNING_DAYS=7
def local_date(ts):return datetime.fromtimestamp(ts,ZoneInfo(SUBSCRIPTION_TZ)).date()
def midnight(d):return int(datetime.combine(d,day_time.min,ZoneInfo(SUBSCRIPTION_TZ)).timestamp())
def add_months(d,months):
 y,m=divmod(d.month-1+months,12);y+=d.year;m+=1
 return date(y,m,min(d.day,calendar.monthrange(y,m)[1]))
def is_restricted(row,now):return bool(row) and local_date(now)>=local_date(row.period_end)
def renewal_term(row,months,now):
 """Early renewal extends the current expiry; renewal after expiry starts on the approval date."""
 if row and not is_restricted(row,now):start=local_date(row.period_end);period_start=row.period_start
 else:start=local_date(now);period_start=midnight(start)
 return midnight(start),midnight(add_months(start,months)),period_start
def term_status(row,now):
 if not row:return {'expires_on':None,'days_left':None,'warning':False,'restricted':False}
 expiry=local_date(row.period_end);days=(expiry-local_date(now)).days
 return {'expires_on':expiry.isoformat(),'days_left':max(days,0),'warning':0<days<=WARNING_DAYS,'restricted':days<=0}
def plan_json(p):return {'id':p.id,**p.settings,'created':p.created,'pricing_source':'platform_entered'}
def subscription_json(row):
 if not row:return {'revision':0,'state':'unassigned','enforcement':'not_connected'}|term_status(None,0)
 data={k:getattr(row,k) for k in ['tenant_id','revision','plan_id','plan_snapshot','state','period_start','period_end','updated','reason']}
 return data|term_status(row,int(time.time()))|{'period_elapsed':row.period_end<=time.time(),'enforcement':'not_connected','payment_verified':False,'payment_source_invoice_id':row.payment_source_invoice_id,'payment_confirmation':'operator_confirmed' if row.payment_source_invoice_id else 'not_recorded'}
def register_subscriptions(app,current,db,log):
 def platform(u):
  if u.role!='platform':raise HTTPException(403,'Platform operator required')
 @app.get('/v1/platform/subscription-plans')
 def plans(u=Depends(current),s=Depends(db)):
  platform(u);return [plan_json(p) for p in s.scalars(select(SubscriptionPlan).order_by(SubscriptionPlan.created.desc(),SubscriptionPlan.id))]
 @app.post('/v1/platform/subscription-plans',status_code=201)
 def create(b:PlanIn,u=Depends(current),s=Depends(db)):
  platform(u);p=SubscriptionPlan(settings=b.model_dump(),created=int(time.time()));s.add(p);s.flush();log(s,u,'subscription_plan_created',p.id);s.commit();return plan_json(p)
 @app.get('/v1/platform/subscriptions')
 def subscriptions(u=Depends(current),s=Depends(db)):
  platform(u);return [subscription_json(r) for r in s.scalars(select(TenantSubscription).order_by(TenantSubscription.updated.desc()))]
 @app.get('/v1/subscription')
 def mine(u=Depends(current),s=Depends(db)):
  if u.role!='sme':raise HTTPException(403,'Business account required')
  return subscription_json(s.get(TenantSubscription,u.tenant_id))
 @app.post('/v1/platform/businesses/{id}/subscription')
 def save(id:str,b:SubscriptionIn,u=Depends(current),s=Depends(db)):
  platform(u)
  if not s.get(Tenant,id):raise HTTPException(404,'Business not found')
  plan=s.get(SubscriptionPlan,b.plan_id)
  if not plan:raise HTTPException(404,'Plan not found')
  row=s.get(TenantSubscription,id);values={k:getattr(b,k) for k in ['plan_id','state','period_start','period_end','reason']};values.update(plan_snapshot=plan_json(plan),updated=int(time.time()),revision=b.expected_revision+1,payment_source_invoice_id=None)
  if row:
   if not s.execute(update(TenantSubscription).where(TenantSubscription.tenant_id==id,TenantSubscription.revision==b.expected_revision).values(**values)).rowcount:raise HTTPException(409,'Subscription changed; refresh')
  else:
   if b.expected_revision:raise HTTPException(409,'Subscription revision does not match')
   s.add(TenantSubscription(tenant_id=id,**values))
  try:s.flush();log(s,u,'subscription_state_saved',id+':'+b.state);s.commit()
  except IntegrityError:s.rollback();raise HTTPException(409,'Subscription changed; refresh')
  s.expire_all();return subscription_json(s.get(TenantSubscription,id))
