"""Developer Dashboard: SME owner account management and the role overview, for the platform owner only.

Suspending or disabling an owner ends their sessions and delegated review credentials at once.
A suspended owner who signs in with the right password is told the reason; a disabled owner
gets the ordinary sign-in failure. Passwords are never shown here; resets use the existing
temporary-password flow in `onboarding.py`.
"""
import time
from typing import Literal
from fastapi import Depends,HTTPException
from pydantic import Field
from sqlalchemy import select,update,delete,func,or_
from .schemas import Strict
from .models import User,Tenant,StaffGrant,SessionToken,LoginHistory,Audit,OwnerAccessEvent,ReviewCredential,PasswordResetRecord,TenantSubscription
from .subscriptions import subscription_json

class AccessIn(Strict):
 expected_revision:int=Field(ge=0)
 state:Literal['active','suspended','disabled']
 reason:str=Field(min_length=1,max_length=1000)
class RenameIn(Strict):
 expected_name:str=Field(min_length=1,max_length=160)
 name:str=Field(min_length=1,max_length=160)

def register_developer(app,current,db,log):
 def owner_only(u):
  if u.role!='platform' or not u.platform_owner:raise HTTPException(403,'The Developer Dashboard is limited to the platform owner')
 def sme_owner(s,id):
  a=s.get(User,id)
  if not a or a.role!='sme' or s.get(StaffGrant,a.id):raise HTTPException(404,'Business owner not found')
  return a
 def usernames(s,ids):
  ids={x for x in ids if x}
  return {x.id:x.username for x in s.scalars(select(User).where(User.id.in_(ids)))} if ids else {}
 @app.get('/v1/developer/owners')
 def owners(u=Depends(current),s=Depends(db)):
  owner_only(u);now=int(time.time())
  rows=list(s.execute(select(User,Tenant).join(Tenant,Tenant.id==User.tenant_id).where(User.role=='sme',~User.id.in_(select(StaffGrant.user_id))).order_by(Tenant.name,User.username)))
  ids=[a.id for a,_ in rows]
  sessions=dict(s.execute(select(SessionToken.user_id,func.count()).where(SessionToken.user_id.in_(ids),SessionToken.expires>now).group_by(SessionToken.user_id)).all()) if ids else {}
  last=dict(s.execute(select(LoginHistory.user_id,func.max(LoginHistory.created)).where(LoginHistory.user_id.in_(ids),LoginHistory.outcome=='success').group_by(LoginHistory.user_id)).all()) if ids else {}
  token_last=dict(s.execute(select(SessionToken.user_id,func.max(SessionToken.login_at)).where(SessionToken.user_id.in_(ids)).group_by(SessionToken.user_id)).all()) if ids else {}
  def subscription(t):
   x=subscription_json(s.get(TenantSubscription,t.id));return {k:x.get(k) for k in ['state','expires_on','days_left','warning','restricted']}|{'plan':(x.get('plan_snapshot') or {}).get('name')}
  return [{'id':a.id,'username':a.username,'business_id':t.id,'business':t.name,'access_state':a.access_state,'access_reason':a.access_reason,'access_revision':a.access_revision,'must_change_password':a.must_change_password,'temporary_password_expires':a.temporary_password_expires,'active_sessions':sessions.get(a.id,0),'last_sign_in':max([x for x in (last.get(a.id),token_last.get(a.id)) if x],default=None),'subscription':subscription(t)} for a,t in rows]
 @app.post('/v1/developer/owners/{id}/access')
 def access(id:str,b:AccessIn,u=Depends(current),s=Depends(db)):
  owner_only(u);a=sme_owner(s,id);now=int(time.time())
  if a.access_state==b.state:raise HTTPException(409,'The account is already '+b.state)
  previous=a.access_state
  if not s.execute(update(User).where(User.id==a.id,User.access_revision==b.expected_revision).values(access_state=b.state,access_reason=None if b.state=='active' else b.reason,access_revision=b.expected_revision+1,active=b.state=='active')).rowcount:raise HTTPException(409,'The account changed; refresh')
  ended=0
  if b.state!='active':
   ended=s.execute(delete(SessionToken).where(SessionToken.user_id==a.id)).rowcount
   s.execute(update(ReviewCredential).where(ReviewCredential.user_id==a.id,ReviewCredential.revoked_at==None).values(revoked_at=now,revoke_reason='Owner account '+b.state+': '+b.reason[:960]))
  s.add(OwnerAccessEvent(user_id=a.id,actor_id=u.id,revision=b.expected_revision+1,previous_state=previous,state=b.state,reason=b.reason,sessions_ended=ended,created=now));log(s,u,'owner_access_'+b.state,a.id);s.commit()
  return {'id':a.id,'access_state':b.state,'access_revision':b.expected_revision+1,'sessions_ended':ended}
 @app.post('/v1/developer/businesses/{id}/name')
 def rename(id:str,b:RenameIn,u=Depends(current),s=Depends(db)):
  owner_only(u)
  if not s.get(Tenant,id):raise HTTPException(404,'Business not found')
  if not s.execute(update(Tenant).where(Tenant.id==id,Tenant.name==b.expected_name).values(name=b.name)).rowcount:raise HTTPException(409,'The business name changed; refresh')
  log(s,u,'business_renamed',id);s.commit();return {'id':id,'name':b.name}
 @app.get('/v1/developer/owners/{id}/history')
 def history(id:str,u=Depends(current),s=Depends(db)):
  owner_only(u);a=sme_owner(s,id)
  access=list(s.scalars(select(OwnerAccessEvent).where(OwnerAccessEvent.user_id==a.id).order_by(OwnerAccessEvent.revision.desc())))
  audit=list(s.scalars(select(Audit).where(or_(Audit.actor_id==a.id,Audit.target.in_([a.id,a.tenant_id]))).order_by(Audit.created.desc(),Audit.id).limit(200)))
  sign_ins=list(s.scalars(select(LoginHistory).where(LoginHistory.user_id==a.id).order_by(LoginHistory.created.desc()).limit(100)))
  resets=list(s.scalars(select(PasswordResetRecord).where(PasswordResetRecord.user_id==a.id).order_by(PasswordResetRecord.created.desc())))
  names=usernames(s,{e.actor_id for e in access}|{e.actor_id for e in audit}|{r.actor_id for r in resets})
  return {'access':[{'time':e.created,'actor':names.get(e.actor_id),'from':e.previous_state,'to':e.state,'reason':e.reason,'sessions_ended':e.sessions_ended} for e in access],
   'resets':[{'time':r.created,'actor':names.get(r.actor_id),'reason':r.reason} for r in resets],
   'sign_ins':[{'time':h.created,'outcome':h.outcome,'device':h.device,'browser':h.browser,'approximate_source':h.source} for h in sign_ins],
   'activity':[{'time':e.created,'actor':names.get(e.actor_id),'action':e.action,'target':e.target} for e in audit],
   'sign_in_retention_days':7}
 @app.get('/v1/developer/roles')
 def roles(u=Depends(current),s=Depends(db)):
  owner_only(u);platform=list(s.scalars(select(User).where(User.role=='platform').order_by(User.username)))
  owners=s.scalar(select(func.count()).select_from(User).where(User.role=='sme',~User.id.in_(select(StaffGrant.user_id))))
  return {'roles':[
   {'key':'developer','accounts':[{'username':x.username,'active':x.active} for x in platform if x.platform_owner]},
   {'key':'platform','accounts':[{'username':x.username,'active':x.active} for x in platform if not x.platform_owner]},
   {'key':'user','count':owners},
   {'key':'agent','count':0,'built':False}],
   'custom_roles':{'available':False,'reason':'Waiting for the owner to confirm the permission catalogue'}}
