"""SME self-service subscription requests, platform payment details and the renewal-only login.

An SME Owner picks a paid plan, a monthly or annual term, and submits payment evidence. Only the
platform owner can approve such a request; approval sets the term with `renewal_term` (early
renewal keeps the remaining days, renewal after expiry starts on the approval date) and restores
access at once. Evidence alone never activates anything, and a replayed approval cannot extend twice.
"""
import time
from pydantic import Field,field_validator
from fastapi import Depends,HTTPException
from sqlalchemy import select,update
from sqlalchemy.exc import IntegrityError
from .schemas import Strict
from .models import PlatformSetting,SubscriptionPlan,SubscriptionInvoice,TenantSubscription,Tenant,StaffGrant,BillingEvent
from .subscriptions import plan_json,renewal_term,subscription_json
from .subscription_billing import fingerprint,invoice_json

PAYMENT_KEY='subscription_payment'
MONTH_CHOICES=(1,12)
OPEN_STATUSES=('pending','needs_evidence')
RESTRICTED_MESSAGE='Your MikroMagic subscription has expired. Renew it on the Subscription page to restore your workspace.'
def renewal_allowed(path):
 return path in ('/v1/me','/v1/auth/logout','/v1/auth/password','/v1/subscription') or path.startswith(('/v1/subscription/','/v1/account/'))
def staff_restricted_allowed(path):
 return path in ('/v1/me','/v1/auth/logout','/v1/auth/password')

class PaymentSettingsIn(Strict):
 expected_revision:int=Field(ge=0)
 destination:str=Field(min_length=1,max_length=500)
 instructions:str=Field(min_length=1,max_length=2000)
 methods:list[str]=Field(min_length=1,max_length=10)
 @field_validator('methods')
 @classmethod
 def clean(cls,v):
  v=[x.strip() for x in v]
  if any(not x or len(x)>80 for x in v) or len(set(v))!=len(v):raise ValueError('Payment methods must be distinct and up to 80 characters')
  return v
class RequestIn(Strict):
 plan_id:str=Field(min_length=1,max_length=36)
 months:int
 method:str=Field(min_length=1,max_length=80)
 reference:str=Field(min_length=1,max_length=160)
 evidence:str=Field(min_length=1,max_length=4000)
 request_key:str=Field(min_length=16,max_length=80,pattern=r'^[A-Za-z0-9-]+$')
 @field_validator('months')
 @classmethod
 def choice(cls,v):
  if v not in MONTH_CHOICES:raise ValueError('Choose a monthly (1) or annual (12) term')
  return v

def payment_json(row):
 if not row:return {'revision':0,'destination':None,'instructions':None,'methods':[]}
 return {'revision':row.revision,**row.value,'updated':row.updated}

def register_subscription_renewal(app,current,db,log):
 def platform_owner(u):
  if u.role!='platform' or not u.platform_owner:raise HTTPException(403,'Only the platform owner manages subscription payments')
 def owner(s,u):
  if u.role!='sme' or s.get(StaffGrant,u.id):raise HTTPException(403,'Business owner required')
 @app.get('/v1/platform/subscription-payment')
 def payment(u=Depends(current),s=Depends(db)):
  platform_owner(u);return payment_json(s.get(PlatformSetting,PAYMENT_KEY))
 @app.post('/v1/platform/subscription-payment')
 def save_payment(b:PaymentSettingsIn,u=Depends(current),s=Depends(db)):
  platform_owner(u);row=s.get(PlatformSetting,PAYMENT_KEY);now=int(time.time());value=b.model_dump(exclude={'expected_revision'})
  if (row.revision if row else 0)!=b.expected_revision:raise HTTPException(409,'Payment details changed; refresh')
  if row:
   if not s.execute(update(PlatformSetting).where(PlatformSetting.key==PAYMENT_KEY,PlatformSetting.revision==b.expected_revision).values(value=value,revision=b.expected_revision+1,updated=now,updated_by=u.id)).rowcount:raise HTTPException(409,'Payment details changed; refresh')
  else:s.add(PlatformSetting(key=PAYMENT_KEY,value=value,revision=1,updated=now,updated_by=u.id))
  log(s,u,'subscription_payment_details_saved',PAYMENT_KEY)
  try:s.commit()
  except IntegrityError:s.rollback();raise HTTPException(409,'Payment details changed; refresh')
  s.expire_all();return payment_json(s.get(PlatformSetting,PAYMENT_KEY))
 @app.get('/v1/subscription/plans')
 def plans(u=Depends(current),s=Depends(db)):
  owner(s,u);settings=s.get(PlatformSetting,PAYMENT_KEY)
  paid=[plan_json(p) for p in s.scalars(select(SubscriptionPlan).order_by(SubscriptionPlan.created.desc(),SubscriptionPlan.id)) if p.settings['monthly_price']>0]
  return {'plans':paid,'months':list(MONTH_CHOICES),'payment':payment_json(settings) if settings else None,'subscription':subscription_json(s.get(TenantSubscription,u.tenant_id))}
 @app.post('/v1/subscription/requests',status_code=201)
 def request(b:RequestIn,u=Depends(current),s=Depends(db)):
  owner(s,u);key=fingerprint(b.model_dump(exclude={'request_key'}))
  previous=s.scalar(select(SubscriptionInvoice).where(SubscriptionInvoice.created_by==u.id,SubscriptionInvoice.request_key==b.request_key))
  if previous:
   if previous.request_hash!=key:raise HTTPException(409,'Request key reused for a different request')
   return invoice_json(previous)|{'replayed':True}
  settings=s.get(PlatformSetting,PAYMENT_KEY)
  if not settings:raise HTTPException(409,'MikroMagic has not published subscription payment details yet; contact MikroMagic')
  if b.method not in settings.value['methods']:raise HTTPException(422,'Choose one of the listed payment methods')
  p=s.get(SubscriptionPlan,b.plan_id)
  if not p or p.settings['monthly_price']<=0:raise HTTPException(404,'Plan not found')
  if s.scalar(select(SubscriptionInvoice.id).where(SubscriptionInvoice.tenant_id==u.tenant_id,SubscriptionInvoice.status.in_(OPEN_STATUSES)).limit(1)):raise HTTPException(409,'A subscription payment is already waiting for review')
  t=s.get(Tenant,u.tenant_id);sub=s.get(TenantSubscription,u.tenant_id);now=int(time.time());start,end,_=renewal_term(sub,b.months,now)
  v=SubscriptionInvoice(tenant_id=t.id,plan_id=p.id,snapshot=plan_json(p)|{'business_name':t.name,'months':b.months,'self_service':True},amount=p.settings['monthly_price']*b.months,currency=p.settings['currency'],period_start=start,period_end=end,subscription_revision=sub.revision if sub else 0,revision=1,status='pending',destination=settings.value['destination'],instructions=settings.value['instructions'],method=b.method,reference=b.reference,evidence=b.evidence,submission_key=b.request_key,submission_hash=key,created_by=u.id,request_key=b.request_key,request_hash=key,created=now,updated=now)
  s.add(v)
  try:
   s.flush();s.add(BillingEvent(invoice_id=v.id,actor_id=u.id,event='renewal_requested',payload=invoice_json(v),created=now));log(s,u,'subscription_renewal_requested',v.id);s.commit()
  except IntegrityError:s.rollback();raise HTTPException(409,'Request raced; retry the same request')
  return invoice_json(v)|{'replayed':False}
