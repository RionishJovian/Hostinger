"""Firmware rollout plans; execution remains capability- and adapter-gated."""
import time
from fastapi import Depends,HTTPException
from sqlalchemy import select
from .models import FirmwarePlan,Site
from .schemas import FirmwarePlanIn

def firmware_json(x):return {k:getattr(x,k) for k in ['id','site_id','device_id','current_version','target_version','minimum_safe_version','window_start','window_end','status','attempts','rollback_version','notes','created_by','created']}
def register_firmware(app,current,db,owner,log):
 @app.get('/v1/firmware-plans')
 def plans(u=Depends(current),s=Depends(db)):
  if u.role=='guest':raise HTTPException(403,'Firmware plans are not available to guests')
  q=select(FirmwarePlan)
  if u.role!='platform':q=q.where(FirmwarePlan.tenant_id==u.tenant_id)
  return [firmware_json(x) for x in s.scalars(q.order_by(FirmwarePlan.created.desc()))]
 @app.post('/v1/firmware-plans',status_code=201)
 def schedule(b:FirmwarePlanIn,u=Depends(current),s=Depends(db)):
  owner(u);site=s.get(Site,b.site_id)
  if not site or site.tenant_id!=u.tenant_id:raise HTTPException(404,'Site not found')
  if b.window_end<b.window_start:raise HTTPException(422,'Maintenance window is invalid')
  if b.target_version==b.current_version:raise HTTPException(422,'Target firmware must differ from the current version')
  x=FirmwarePlan(tenant_id=u.tenant_id,created_by=u.id,created=int(time.time()),window_start=b.window_start,window_end=b.window_end,**{k:getattr(b,k) for k in ['site_id','device_id','current_version','target_version','minimum_safe_version','notes']});s.add(x);s.flush();log(s,u,'firmware_plan_scheduled',x.id);s.commit();return firmware_json(x)|{'execution_state':'adapter_pending'}
