"""Platform console: platform-wide sign-in oversight for the platform owner account only."""
import time
from fastapi import Depends,Request,HTTPException
from sqlalchemy import select
from .models import SessionToken,LoginHistory,Audit,User,Tenant,StaffGrant
RETENTION=7*24*60*60
EVENTS={'sign_in':'Signed in','sign_out':'Signed out','other_session_revoked':'Ended another session','other_sessions_revoked':'Ended all other sessions'}
def register_platform_console(app,current,db,digest):
 def platform_owner(u):
  if u.role!='platform' or not u.platform_owner:raise HTTPException(403,'Platform console is limited to the platform owner')
 def accounts(s,ids):
  users={x.id:x for x in s.scalars(select(User).where(User.id.in_(ids)))} if ids else {}
  tenants={x.id:x.name for x in s.scalars(select(Tenant).where(Tenant.id.in_({x.tenant_id for x in users.values() if x.tenant_id})))} if users else {}
  staff={x.user_id for x in s.scalars(select(StaffGrant).where(StaffGrant.user_id.in_(ids)))} if ids else set()
  def describe(user_id):
   x=users.get(user_id)
   if not x:return {'account':'Unknown account','role':'unknown','business':None}
   role='staff' if x.id in staff else x.role
   return {'account':x.username,'role':role,'business':tenants.get(x.tenant_id)}
  return describe
 @app.get('/v1/platform/console/sessions')
 def sessions(request:Request,u=Depends(current),s=Depends(db)):
  platform_owner(u)
  own=digest(request.headers.get('authorization','').split(' ',1)[-1])
  rows=list(s.scalars(select(SessionToken).where(SessionToken.expires>time.time()).order_by(SessionToken.login_at.desc().nullslast(),SessionToken.expires.desc()).limit(500)))
  describe=accounts(s,{t.user_id for t in rows})
  return [{**describe(t.user_id),'login_at':t.login_at,'last_active':t.last_active,'device':t.device or 'Not recorded','browser':t.browser or 'Not recorded','approximate_source':t.source or 'Not recorded','expires':t.expires,'current':t.token_hash==own} for t in rows]
 @app.get('/v1/platform/console/sign-ins')
 def sign_ins(u=Depends(current),s=Depends(db)):
  platform_owner(u)
  cutoff=int(time.time())-RETENTION
  history=list(s.scalars(select(LoginHistory).where(LoginHistory.created>=cutoff)))
  audits=list(s.scalars(select(Audit).where(Audit.action.in_(list(EVENTS)),Audit.created>=cutoff)))
  successes={}
  for h in history:
   if h.outcome=='success':successes.setdefault(h.user_id,[]).append(h)
  def detail(a):
   # Sign-in audit events and login history rows are written in the same request.
   if a.action!='sign_in':return None
   return next((h for h in successes.get(a.actor_id,[]) if abs(h.created-a.created)<=5),None)
  describe=accounts(s,{h.user_id for h in history}|{a.actor_id for a in audits})
  events=[]
  for a in audits:
   h=detail(a)
   events.append({**describe(a.actor_id),'time':a.created,'event':EVENTS[a.action],'outcome':'success','device':h.device if h else None,'browser':h.browser if h else None,'approximate_source':h.source if h else None})
  for h in history:
   if h.outcome=='failure':
    events.append({**describe(h.user_id),'time':h.created,'event':'Failed sign-in','outcome':'failure','device':h.device,'browser':h.browser,'approximate_source':h.source})
  events.sort(key=lambda e:e['time'],reverse=True)
  return {'retention_days':7,'events':events[:500]}
