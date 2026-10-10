"""Legacy staff records. Frozen v1 has one SME Owner/Admin role: staff rows and history are
preserved, staff may only identify themselves and sign out, and no new staff can be created."""
import secrets,time
from typing import Literal
from pydantic import Field
from fastapi import Depends,HTTPException
from sqlalchemy import select,update,delete
from .schemas import Strict
from .models import StaffGrant,User,SessionToken,ReviewCredential,LoginAttempt
LEGACY_STAFF_PATHS=frozenset({'/v1/me','/v1/auth/logout'})
LEGACY_STAFF_CLOSED='Legacy staff access is closed in MikroMagic v1; ask the business Owner/Admin'
def staff_allowed(profile,method,path):return path in LEGACY_STAFF_PATHS
class StaffCreate(Strict):
 username:str=Field(min_length=3,max_length=160,pattern=r'^[a-z0-9][a-z0-9_.@+-]{2,159}$')
 profile:Literal['manager','cashier','technician']
 request_key:str=Field(min_length=16,max_length=80)
class StaffChange(Strict):
 expected_revision:int=Field(ge=1)
 profile:Literal['manager','cashier','technician']
 active:bool
 reason:str=Field(min_length=1,max_length=1000)
class StaffReset(StaffChange):
 confirmed_authority:Literal[True]
def staff_json(g,a):return {'id':a.id,'username':a.username,'profile':g.profile,'revision':g.revision,'active':a.active,'must_change_password':a.must_change_password,'temporary_password_expires':a.temporary_password_expires,'last_reason':g.last_reason}
def register_staff(app,current,db,owner,log,hasher,digest):
 def full_owner(s,u):
  owner(u)
  if s.get(StaffGrant,u.id):raise HTTPException(403,'Only the business owner manages staff')
 def target(s,u,id):
  g=s.get(StaffGrant,id);a=s.get(User,id)
  if not g or not a or a.tenant_id!=u.tenant_id or g.tenant_id!=u.tenant_id:raise HTTPException(404,'Staff account not found')
  return g,a
 @app.get('/v1/staff')
 def staff(u=Depends(current),s=Depends(db)):
  full_owner(s,u);return [staff_json(g,a) for g,a in s.execute(select(StaffGrant,User).join(User,User.id==StaffGrant.user_id).where(StaffGrant.tenant_id==u.tenant_id).order_by(User.username))]
 @app.post('/v1/staff',status_code=201)
 def create(b:StaffCreate,u=Depends(current),s=Depends(db)):
  full_owner(s,u);raise HTTPException(410,'New staff accounts are not part of MikroMagic v1. Existing legacy staff can be reviewed, disabled or reset.')
 @app.post('/v1/staff/{id}')
 def change(id:str,b:StaffChange,u=Depends(current),s=Depends(db)):
  full_owner(s,u);g,a=target(s,u,id)
  if not s.execute(update(StaffGrant).where(StaffGrant.user_id==id,StaffGrant.revision==b.expected_revision).values(profile=b.profile,revision=b.expected_revision+1,last_reason=b.reason,updated=int(time.time()))).rowcount:raise HTTPException(409,'Staff account changed; refresh')
  a.active=b.active;s.execute(delete(SessionToken).where(SessionToken.user_id==a.id));s.execute(update(ReviewCredential).where(ReviewCredential.user_id==a.id,ReviewCredential.revoked_at==None).values(revoked_at=int(time.time()),revoke_reason='Staff authority changed: '+b.reason[:970]));log(s,u,'staff_authority_changed',id+':'+b.profile+':'+str(b.active));s.commit();s.refresh(g)
  return staff_json(g,a)
 @app.post('/v1/staff/{id}/reset-password')
 def reset(id:str,b:StaffReset,u=Depends(current),s=Depends(db)):
  full_owner(s,u);g,a=target(s,u,id)
  if b.profile!=g.profile or b.active!=a.active:raise HTTPException(409,'Password reset cannot also change authority')
  if not s.execute(update(StaffGrant).where(StaffGrant.user_id==id,StaffGrant.revision==b.expected_revision).values(revision=b.expected_revision+1,last_reason=b.reason,updated=int(time.time()))).rowcount:raise HTTPException(409,'Staff account changed; refresh')
  raw=secrets.token_urlsafe(18);a.password_hash=hasher.hash(raw);a.must_change_password=True;a.temporary_password_expires=int(time.time())+86400
  s.execute(update(ReviewCredential).where(ReviewCredential.user_id==id,ReviewCredential.revoked_at==None).values(revoked_at=int(time.time()),revoke_reason='Staff password reset: '+b.reason[:970]));s.execute(delete(LoginAttempt).where(LoginAttempt.key.in_([digest('account:'+a.username),digest('password-change:'+a.id)])));log(s,u,'staff_password_reset',id);s.commit();s.refresh(g)
  return {'staff':staff_json(g,a),'temporary_password':raw,'shown_once':True}
