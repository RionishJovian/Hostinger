"""Site-scoped switch/AP inventory. Live vendor control remains deferred."""
import os,time
from fastapi import Depends,HTTPException
from sqlalchemy import select,func
from sqlalchemy.exc import IntegrityError
from .models import ManagedDevice,Site
from .schemas import ManagedDeviceIn

def site_limit(kind):
 key='MIKROMAGIC_MAX_APS_PER_SITE' if kind=='access_point' else 'MIKROMAGIC_MAX_SWITCHES_PER_SITE'
 default='5' if kind=='access_point' else '1'
 try:return max(1,int(os.environ.get(key,default)))
 except ValueError:return int(default)

def register_managed_devices(app,current,db,owner,log):
 @app.get('/v1/site-devices')
 def devices(u=Depends(current),s=Depends(db)):
  if u.role=='guest':raise HTTPException(403,'Device inventory is not available to guests')
  q=select(ManagedDevice)
  if u.role!='platform':q=q.where(ManagedDevice.tenant_id==u.tenant_id)
  return [{k:getattr(x,k) for k in ['id','tenant_id','site_id','kind','name','vendor','model','serial_or_mac','location','firmware','created','last_seen']}|{'connection_state':'unverified','metadata_source':'owner_reported','capabilities':[],'site_limit':site_limit(x.kind)} for x in s.scalars(q.order_by(ManagedDevice.created.desc()))]

 @app.post('/v1/site-devices',status_code=201)
 def create_device(b:ManagedDeviceIn,u=Depends(current),s=Depends(db)):
  owner(u);site=s.get(Site,b.site_id)
  if not site or site.tenant_id!=u.tenant_id:raise HTTPException(404,'Site not found')
  limit=site_limit(b.kind);count=s.scalar(select(func.count()).select_from(ManagedDevice).where(ManagedDevice.site_id==b.site_id,ManagedDevice.kind==b.kind)) or 0
  if count>=limit:raise HTTPException(409,f'{b.kind} site limit reached ({limit}); update the commercial plan or site configuration')
  x=ManagedDevice(tenant_id=u.tenant_id,**b.model_dump(),created=int(time.time()));s.add(x)
  try:s.flush();log(s,u,'managed_device_registered',x.id);s.commit()
  except IntegrityError:s.rollback();raise HTTPException(409,'A device with this name already exists at this site')
  return {'id':x.id,'kind':x.kind,'site_id':x.site_id,'connection_state':'unverified','metadata_source':'owner_reported','capabilities':[],'site_limit':limit}
