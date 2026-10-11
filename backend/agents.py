"""Referral Agents (owner decisions Q20–Q30).

Anyone may apply; the platform owner approves before an Agent can register SME businesses. An
approved Agent creates a business and its Owner/Admin through the same one-time temporary-password
flow as the platform; the Agent never gains access to that business afterwards. Each approved
monthly or annual subscription payment of an attributed business earns the Agent 20% or 30% of
the list price, available at once. A refund reverses the commission; if it was already paid out
the negative balance offsets future earnings. Withdrawals go to the Agent's own KBZPay or WavePay
wallet, from 10,000 MMK, and are paid manually: requested, approved and paid are separate states.
"""
import time
from typing import Literal
from fastapi import Depends,HTTPException,Request
from pydantic import Field,field_validator,model_validator
from sqlalchemy import select,update,func
from sqlalchemy.exc import IntegrityError
from .schemas import Strict
from .models import User,Tenant,AgentProfile,AgentReferral,AgentCommission,AgentWallet,AgentWithdrawal,BusinessProvisioning,TenantSubscription,LoginAttempt
from .subscriptions import subscription_json
from .onboarding import BusinessIn,provision_business

RATES={1:20,12:30}
MIN_WITHDRAWAL=10_000
WITHDRAWAL_CURRENCY='MMK'
METHODS=('kbzpay','wavepay')
RESERVED=('requested','approved')
def agent_allowed(path):
 return path in ('/v1/me','/v1/auth/logout','/v1/auth/password') or path.startswith(('/v1/agent/','/v1/account/'))

def record_commission(s,v,now):
 """Earn the commission for an approved invoice of an attributed business, once per invoice."""
 ref=s.get(AgentReferral,v.tenant_id);months=int(v.snapshot.get('months',1));rate=RATES.get(months)
 if not ref or rate is None or s.scalar(select(AgentCommission.id).where(AgentCommission.invoice_id==v.id)):return None
 base=int(v.snapshot['monthly_price'])*months
 c=AgentCommission(agent_id=ref.agent_id,tenant_id=v.tenant_id,invoice_id=v.id,months=months,rate_percent=rate,base_amount=base,amount=base*rate//100,currency=v.currency,state='earned',created=now);s.add(c);return c
def reverse_commission(s,invoice_id,reason,now):
 return s.execute(update(AgentCommission).where(AgentCommission.invoice_id==invoice_id,AgentCommission.state=='earned').values(state='reversed',reversed_at=now,reversal_reason=reason)).rowcount
def balances(s,agent_id):
 out={}
 def row(c):return out.setdefault(c,{'currency':c,'earned':0,'reversed':0,'reserved':0,'paid':0})
 for c,state,total in s.execute(select(AgentCommission.currency,AgentCommission.state,func.sum(AgentCommission.amount)).where(AgentCommission.agent_id==agent_id).group_by(AgentCommission.currency,AgentCommission.state)):
  row(c)['earned' if state=='earned' else 'reversed']+=int(total or 0)
 for c,status,total in s.execute(select(AgentWithdrawal.currency,AgentWithdrawal.status,func.sum(AgentWithdrawal.amount)).where(AgentWithdrawal.agent_id==agent_id,AgentWithdrawal.status.in_(RESERVED+('paid',))).group_by(AgentWithdrawal.currency,AgentWithdrawal.status)):
  row(c)['paid' if status=='paid' else 'reserved']+=int(total or 0)
 for b in out.values():b['available']=b['earned']-b['reserved']-b['paid']
 return sorted(out.values(),key=lambda b:(b['currency']!=WITHDRAWAL_CURRENCY,b['currency']))
def available(s,agent_id,currency=WITHDRAWAL_CURRENCY):return next((b['available'] for b in balances(s,agent_id) if b['currency']==currency),0)

class ApplicationIn(Strict):
 username:str=Field(min_length=3,max_length=160,pattern=r'^[a-z0-9][a-z0-9_.@+-]{2,159}$')
 password:str=Field(min_length=6,max_length=256)
 full_name:str=Field(min_length=1,max_length=160)
 phone:str=Field(min_length=6,max_length=40,pattern=r'^[0-9+ ()-]+$')
 note:str|None=Field(default=None,max_length=1000)
 @field_validator('username',mode='before')
 @classmethod
 def lower(cls,v):return v.strip().lower() if isinstance(v,str) else v
class AgentDecisionIn(Strict):
 expected_revision:int=Field(ge=1)
 status:Literal['approved','rejected','suspended']
 reason:str=Field(default='',max_length=1000)
 @model_validator(mode='after')
 def explained(self):
  self.reason=self.reason.strip()
  if self.status!='approved' and not self.reason:raise ValueError('Give a reason for rejecting or suspending')
  return self
class WalletIn(Strict):
 method:Literal['kbzpay','wavepay']
 account_name:str=Field(min_length=1,max_length=160)
 account_number:str=Field(min_length=6,max_length=40,pattern=r'^[0-9+ -]+$')
class WithdrawalIn(Strict):
 amount:int=Field(ge=MIN_WITHDRAWAL,le=10**12)
 method:Literal['kbzpay','wavepay']
 request_key:str=Field(min_length=16,max_length=80,pattern=r'^[A-Za-z0-9-]+$')
class WithdrawalDecisionIn(Strict):
 expected_revision:int=Field(ge=1)
 decision:Literal['approved','rejected','paid']
 reason:str=Field(default='',max_length=1000)
 payout_reference:str=Field(default='',max_length=160)
 confirmed_paid:bool=False
 @model_validator(mode='after')
 def complete(self):
  self.reason=self.reason.strip();self.payout_reference=self.payout_reference.strip()
  if self.decision=='rejected' and not self.reason:raise ValueError('Give a reason for rejecting')
  if self.decision=='paid' and (not self.payout_reference or not self.confirmed_paid):raise ValueError('Record the payout reference and confirm the money was sent')
  return self

TRANSITIONS={'pending':('approved','rejected'),'approved':('suspended',),'suspended':('approved',),'rejected':('approved',)}
WITHDRAWAL_TRANSITIONS={'requested':('approved','rejected'),'approved':('paid','rejected')}
def profile_json(p,u=None):
 return {'id':p.user_id,'username':u.username if u else None,'full_name':p.full_name,'phone':p.phone,'note':p.note,'status':p.status,'reason':p.reason,'revision':p.revision,'applied':p.applied,'decided':p.decided}
def commission_json(c,name=None):
 return {'id':c.id,'business_id':c.tenant_id,'business':name,'invoice_id':c.invoice_id,'months':c.months,'rate_percent':c.rate_percent,'base_amount':c.base_amount,'amount':c.amount,'currency':c.currency,'state':c.state,'created':c.created,'reversed_at':c.reversed_at,'reversal_reason':c.reversal_reason}
def withdrawal_json(w,u=None,p=None):
 return {'id':w.id,'agent_id':w.agent_id,'agent':u.username if u else None,'agent_name':p.full_name if p else None,'amount':w.amount,'currency':w.currency,'method':w.method,'wallet':w.wallet,'status':w.status,'revision':w.revision,'reason':w.reason,'payout_reference':w.payout_reference,'requested':w.requested,'decided':w.decided,'paid_at':w.paid_at}

def register_agents(app,current,db,log,hasher,check,client_ip,digest):
 def agent(s,u):
  check(u.role=='agent','Agent account required');p=s.get(AgentProfile,u.id);check(p,'Agent profile missing',404);return p
 def approved(p):
  if p.status!='approved':raise HTTPException(403,{'pending':'Your Agent application is waiting for approval','rejected':'Your Agent application was not approved','suspended':'Your Agent account is suspended'}[p.status])
 def owner_only(u):
  if u.role!='platform' or not u.platform_owner:raise HTTPException(403,'Agent management is limited to the platform owner')
 def wallets(s,agent_id):return [{'method':w.method,'account_name':w.account_name,'account_number':w.account_number,'updated':w.updated} for w in s.scalars(select(AgentWallet).where(AgentWallet.agent_id==agent_id).order_by(AgentWallet.method))]

 @app.post('/v1/agent-applications',status_code=201)
 def apply(b:ApplicationIn,request:Request,s=Depends(db)):
  now=int(time.time());key=digest('agent-application-ip:'+client_ip(request));bucket=s.get(LoginAttempt,key)
  if not bucket:bucket=LoginAttempt(key=key,failures=0,window_start=now);s.add(bucket)
  if now-bucket.window_start>=3600:bucket.failures=0;bucket.window_start=now
  if bucket.failures>=5:raise HTTPException(429,'Too many applications from this network; try again later')
  bucket.failures+=1
  try:s.commit()
  except IntegrityError:s.rollback();raise HTTPException(429,'Applications are busy; try again shortly')
  if s.scalar(select(User.id).where(User.username==b.username)):raise HTTPException(409,'Username unavailable; choose another username')
  u=User(username=b.username,password_hash=hasher.hash(b.password),role='agent',tenant_id=None,active=True);s.add(u)
  try:
   s.flush();s.add(AgentProfile(user_id=u.id,full_name=b.full_name.strip(),phone=b.phone.strip(),note=(b.note or '').strip() or None,status='pending',revision=1,ledger_revision=0,applied=now));log(s,u,'agent_applied',u.id);s.commit()
  except IntegrityError:s.rollback();raise HTTPException(409,'Username unavailable; choose another username')
  return {'username':u.username,'status':'pending'}

 @app.get('/v1/agent/profile')
 def profile(u=Depends(current),s=Depends(db)):
  p=agent(s,u);return profile_json(p,u)|{'balances':balances(s,u.id),'wallets':wallets(s,u.id),'rates':{'monthly':RATES[1],'annual':RATES[12]},'minimum_withdrawal':MIN_WITHDRAWAL,'withdrawal_currency':WITHDRAWAL_CURRENCY,'businesses':s.scalar(select(func.count()).select_from(AgentReferral).where(AgentReferral.agent_id==u.id))}
 @app.get('/v1/agent/businesses')
 def businesses(u=Depends(current),s=Depends(db)):
  agent(s,u);rows=s.execute(select(AgentReferral,Tenant,BusinessProvisioning).join(Tenant,Tenant.id==AgentReferral.tenant_id).join(BusinessProvisioning,BusinessProvisioning.tenant_id==AgentReferral.tenant_id).where(AgentReferral.agent_id==u.id).order_by(AgentReferral.created.desc()))
  out=[]
  for r,t,prov in rows:
   o=s.get(User,prov.owner_id);sub=subscription_json(s.get(TenantSubscription,t.id))
   earned=s.scalar(select(func.coalesce(func.sum(AgentCommission.amount),0)).where(AgentCommission.agent_id==u.id,AgentCommission.tenant_id==t.id,AgentCommission.state=='earned'))
   out.append({'id':t.id,'name':t.name,'owner_username':o.username,'owner_signed_in':not o.must_change_password,'registered':r.created,'subscription':{k:sub.get(k) for k in ('state','expires_on','days_left','restricted')},'commission_earned':int(earned)})
  return out
 @app.post('/v1/agent/businesses',status_code=201)
 def register_business(b:BusinessIn,u=Depends(current),s=Depends(db)):
  p=agent(s,u);approved(p)
  def attribute(s,t,now):s.add(AgentReferral(tenant_id=t.id,agent_id=u.id,created=now));log(s,u,'agent_business_registered',t.id)
  return provision_business(s,u,b,hasher,log,check,attribute)
 @app.get('/v1/agent/commissions')
 def commissions(u=Depends(current),s=Depends(db)):
  agent(s,u);return [commission_json(c,n) for c,n in s.execute(select(AgentCommission,Tenant.name).join(Tenant,Tenant.id==AgentCommission.tenant_id).where(AgentCommission.agent_id==u.id).order_by(AgentCommission.created.desc()).limit(500))]
 @app.post('/v1/agent/wallets')
 def save_wallet(b:WalletIn,u=Depends(current),s=Depends(db)):
  agent(s,u);now=int(time.time());w=s.get(AgentWallet,(u.id,b.method))
  if w:w.account_name=b.account_name.strip();w.account_number=b.account_number.strip();w.updated=now
  else:s.add(AgentWallet(agent_id=u.id,method=b.method,account_name=b.account_name.strip(),account_number=b.account_number.strip(),updated=now))
  log(s,u,'agent_wallet_saved',b.method)
  try:s.commit()
  except IntegrityError:s.rollback();raise HTTPException(409,'Wallet changed at the same time; refresh')
  return wallets(s,u.id)
 @app.get('/v1/agent/withdrawals')
 def withdrawals(u=Depends(current),s=Depends(db)):
  agent(s,u);return [withdrawal_json(w) for w in s.scalars(select(AgentWithdrawal).where(AgentWithdrawal.agent_id==u.id).order_by(AgentWithdrawal.requested.desc()).limit(200))]
 @app.post('/v1/agent/withdrawals',status_code=201)
 def request_withdrawal(b:WithdrawalIn,u=Depends(current),s=Depends(db)):
  p=agent(s,u);approved(p)
  prior=s.scalar(select(AgentWithdrawal).where(AgentWithdrawal.agent_id==u.id,AgentWithdrawal.request_key==b.request_key))
  if prior:
   if (prior.amount,prior.method)!=(b.amount,b.method):raise HTTPException(409,'Request key reused for a different withdrawal')
   return withdrawal_json(prior)|{'replayed':True}
  w=s.get(AgentWallet,(u.id,b.method))
  if not w:raise HTTPException(422,'Save your '+('KBZPay' if b.method=='kbzpay' else 'WavePay')+' wallet before requesting a withdrawal')
  # The row update serializes concurrent requests so the same balance cannot be reserved twice.
  if not s.execute(update(AgentProfile).where(AgentProfile.user_id==u.id).values(ledger_revision=AgentProfile.ledger_revision+1)).rowcount:raise HTTPException(409,'Agent profile changed; refresh')
  balance=available(s,u.id)
  if b.amount>balance:s.rollback();raise HTTPException(422,f'Only {max(balance,0):,} {WITHDRAWAL_CURRENCY} is available to withdraw')
  now=int(time.time());x=AgentWithdrawal(agent_id=u.id,amount=b.amount,currency=WITHDRAWAL_CURRENCY,method=b.method,wallet={'account_name':w.account_name,'account_number':w.account_number},status='requested',revision=1,request_key=b.request_key,requested=now);s.add(x)
  try:s.flush();log(s,u,'agent_withdrawal_requested',x.id);s.commit()
  except IntegrityError:s.rollback();raise HTTPException(409,'Withdrawal request raced; retry with the same request key')
  return withdrawal_json(x)|{'replayed':False}
 @app.post('/v1/agent/withdrawals/{id}/cancel')
 def cancel_withdrawal(id:str,u=Depends(current),s=Depends(db)):
  agent(s,u);x=s.get(AgentWithdrawal,id)
  if not x or x.agent_id!=u.id:raise HTTPException(404,'Withdrawal not found')
  if not s.execute(update(AgentWithdrawal).where(AgentWithdrawal.id==id,AgentWithdrawal.status=='requested').values(status='cancelled',revision=AgentWithdrawal.revision+1,decided=int(time.time()))).rowcount:raise HTTPException(409,'Only a request that has not been reviewed can be cancelled')
  log(s,u,'agent_withdrawal_cancelled',id);s.commit();s.refresh(x);return withdrawal_json(x)

 @app.get('/v1/developer/agents')
 def agents(u=Depends(current),s=Depends(db)):
  owner_only(u);counts=dict(s.execute(select(AgentReferral.agent_id,func.count()).group_by(AgentReferral.agent_id)).all())
  return [profile_json(p,a)|{'businesses':counts.get(p.user_id,0),'balances':balances(s,p.user_id)} for p,a in s.execute(select(AgentProfile,User).join(User,User.id==AgentProfile.user_id).order_by(AgentProfile.applied.desc()))]
 @app.post('/v1/developer/agents/{id}/decision')
 def decide_agent(id:str,b:AgentDecisionIn,u=Depends(current),s=Depends(db)):
  owner_only(u);p=s.get(AgentProfile,id)
  if not p:raise HTTPException(404,'Agent not found')
  if p.revision!=b.expected_revision:raise HTTPException(409,'Agent changed; refresh')
  if b.status not in TRANSITIONS[p.status]:raise HTTPException(409,f'A {p.status} Agent cannot become {b.status}')
  now=int(time.time())
  if not s.execute(update(AgentProfile).where(AgentProfile.user_id==id,AgentProfile.revision==b.expected_revision).values(status=b.status,reason=b.reason or None,revision=b.expected_revision+1,decided=now,decided_by=u.id)).rowcount:raise HTTPException(409,'Agent changed; refresh')
  log(s,u,'agent_'+b.status,id);s.commit();s.refresh(p);return profile_json(p,s.get(User,id))
 @app.get('/v1/developer/agent-businesses')
 def agent_businesses(u=Depends(current),s=Depends(db)):
  owner_only(u);return [{'business_id':r.tenant_id,'business':t.name,'agent_id':r.agent_id,'agent':a.username,'registered':r.created} for r,t,a in s.execute(select(AgentReferral,Tenant,User).join(Tenant,Tenant.id==AgentReferral.tenant_id).join(User,User.id==AgentReferral.agent_id).order_by(AgentReferral.created.desc()))]
 @app.get('/v1/developer/agent-commissions')
 def all_commissions(u=Depends(current),s=Depends(db)):
  owner_only(u);return [commission_json(c,n)|{'agent':a} for c,n,a in s.execute(select(AgentCommission,Tenant.name,User.username).join(Tenant,Tenant.id==AgentCommission.tenant_id).join(User,User.id==AgentCommission.agent_id).order_by(AgentCommission.created.desc()).limit(500))]
 @app.get('/v1/developer/agent-withdrawals')
 def all_withdrawals(u=Depends(current),s=Depends(db)):
  owner_only(u);return [withdrawal_json(w,a,p)|{'available':available(s,w.agent_id)} for w,a,p in s.execute(select(AgentWithdrawal,User,AgentProfile).join(User,User.id==AgentWithdrawal.agent_id).join(AgentProfile,AgentProfile.user_id==AgentWithdrawal.agent_id).order_by(AgentWithdrawal.requested.desc()).limit(500))]
 @app.post('/v1/developer/agent-withdrawals/{id}/decision')
 def decide_withdrawal(id:str,b:WithdrawalDecisionIn,u=Depends(current),s=Depends(db)):
  owner_only(u);x=s.get(AgentWithdrawal,id)
  if not x:raise HTTPException(404,'Withdrawal not found')
  if x.revision!=b.expected_revision:raise HTTPException(409,'Withdrawal changed; refresh')
  if b.decision not in WITHDRAWAL_TRANSITIONS.get(x.status,()):raise HTTPException(409,f'A {x.status} withdrawal cannot become {b.decision}')
  now=int(time.time());values={'status':b.decision,'revision':b.expected_revision+1,'decided':now,'decided_by':u.id}
  if b.decision=='rejected':values['reason']=b.reason
  if b.decision=='paid':values|={'payout_reference':b.payout_reference,'paid_at':now}
  if not s.execute(update(AgentWithdrawal).where(AgentWithdrawal.id==id,AgentWithdrawal.revision==b.expected_revision).values(**values)).rowcount:raise HTTPException(409,'Withdrawal changed; refresh')
  log(s,u,'agent_withdrawal_'+b.decision,id);s.commit();s.refresh(x);return withdrawal_json(x,s.get(User,x.agent_id),s.get(AgentProfile,x.agent_id))
