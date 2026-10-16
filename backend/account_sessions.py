"""Own-account session control. No device identity is inferred from tokens."""
import time
from fastapi import Depends,Request,HTTPException
from sqlalchemy import select,delete
from pydantic import Field
from .schemas import Strict
from .models import SessionToken,LoginHistory
class RevokeSession(Strict):
 session_ref:str=Field(pattern=r'^[a-f0-9]{64}$')
class RevokeOthers(Strict):
 confirmed:bool
def register_account_sessions(app,current,db,log,digest):
 def current_hash(request):return digest(request.headers.get('authorization','').split(' ',1)[-1])
 def ref(value):return digest('session-ref:'+value)
 @app.get('/v1/account/sessions')
 def sessions(request:Request,u=Depends(current),s=Depends(db)):
  own=current_hash(request)
  return [{'session_ref':ref(t.token_hash),'login_at':t.login_at,'last_active':t.last_active,'device':t.device or 'Unavailable (signed in before device history was enabled)','browser':t.browser or 'Unavailable (signed in before device history was enabled)','approximate_source':t.source or 'Unavailable','expires':t.expires,'current':t.token_hash==own} for t in s.scalars(select(SessionToken).where(SessionToken.user_id==u.id,SessionToken.expires>time.time()).order_by(SessionToken.login_at.desc().nullslast(),SessionToken.expires.desc()))]
 @app.get('/v1/account/login-history')
 def login_history(u=Depends(current),s=Depends(db)):
  # Frozen v1 exposes this history only to an SME Owner/Admin, never delegated staff.
  if u.role!='sme' or u.staff_profile is not None:raise HTTPException(403,'Owner/Admin access required')
  cutoff=int(time.time())-7*24*60*60
  s.execute(delete(LoginHistory).where(LoginHistory.user_id==u.id,LoginHistory.created<cutoff));s.commit()
  rows=s.scalars(select(LoginHistory).where(LoginHistory.user_id==u.id,LoginHistory.tenant_id==u.tenant_id,LoginHistory.created>=cutoff).order_by(LoginHistory.created.desc()).limit(500))
  return [{'id':row.id,'outcome':row.outcome,'time':row.created,'device':row.device,'browser':row.browser,'approximate_source':row.source,'retained_until':row.created+7*24*60*60} for row in rows]
 @app.post('/v1/account/sessions/revoke')
 def revoke(b:RevokeSession,request:Request,u=Depends(current),s=Depends(db)):
  # Public references are domain-separated digests, never bearer tokens or their stored hashes.
  target=next((t for t in s.scalars(select(SessionToken).where(SessionToken.user_id==u.id,SessionToken.expires>time.time())) if ref(t.token_hash)==b.session_ref),None)
  if not target:raise HTTPException(404,'Active session not found')
  if target.token_hash==current_hash(request):raise HTTPException(409,'Use Sign out to end the current session')
  s.execute(delete(SessionToken).where(SessionToken.token_hash==target.token_hash,SessionToken.user_id==u.id));log(s,u,'other_session_revoked',b.session_ref);s.commit();return {'revoked':True}
 @app.post('/v1/account/sessions/revoke-others')
 def others(b:RevokeOthers,request:Request,u=Depends(current),s=Depends(db)):
  if not b.confirmed:raise HTTPException(422,'Confirm that other sessions should end')
  removed=s.execute(delete(SessionToken).where(SessionToken.user_id==u.id,SessionToken.token_hash!=current_hash(request))).rowcount
  log(s,u,'other_sessions_revoked',str(removed));s.commit();return {'revoked_count':removed,'current_session_preserved':True,'service_credentials_changed':False}
