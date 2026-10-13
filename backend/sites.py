"""Tenant-scoped registration; user-reported router metadata is not telemetry."""
import time
from fastapi import Depends,HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from .hub_orchestrator import connection_is_fresh
from .models import Site,SiteMaintenance,RouterDevice,RouterPlan
from .schemas import SiteIn,SiteSettingsIn,RouterIn

def allowed_site(s,u,id):
 site=s.get(Site,id)
 if not site or site.tenant_id!=u.tenant_id:raise HTTPException(404,'Site not found')
 return site

def router_display(device,plan=None,now=None):
 """Owner-facing connection_state from the plan: Connected only with fresh evidence."""
 fresh=bool(plan and connection_is_fresh(plan,now))
 return {k:getattr(device,k) for k in ['id','tenant_id','site_id','name','model','reported_routeros','created']}|{
  'connection_state':'connected' if fresh else 'unverified',
  'connection_verified':fresh,
  'hub_id':plan.hub_id if plan else None,
  'last_handshake':plan.handshake_verified_at if plan else None,
  'lifecycle_state':plan.lifecycle_state if plan else None,
  'management_read_verified_at':plan.management_read_verified_at if plan else None,
  'metadata_source':'owner_reported',
 }

def register_sites(app,current,db,owner,log):
 @app.get('/v1/sites')
 def sites(u=Depends(current),s=Depends(db)):
  if u.role=='guest':raise HTTPException(403,'Guest site discovery uses the published portal list')
  q=select(Site)
  if u.role!='platform':q=q.where(Site.tenant_id==u.tenant_id)
  now=int(time.time());active=select(SiteMaintenance).where(SiteMaintenance.ended.is_(None),SiteMaintenance.planned_end>now)
  if u.role!='platform':active=active.where(SiteMaintenance.tenant_id==u.tenant_id)
  until={m.site_id:m.planned_end for m in s.scalars(active)}
  return [{k:getattr(x,k) for k in ['id','tenant_id','name','timezone','created','printed_ssid','business_hours','network_hours_mode','network_hours']}|{'maintenance_until':until.get(x.id)} for x in s.scalars(q.order_by(Site.name))]
 @app.post('/v1/sites',status_code=201)
 def create_site(b:SiteIn,u=Depends(current),s=Depends(db)):
  owner(u);x=Site(tenant_id=u.tenant_id,**b.model_dump(),created=int(time.time()));s.add(x)
  try:s.flush();log(s,u,'site_registered',x.id);s.commit()
  except IntegrityError:s.rollback();raise HTTPException(409,'A shop with this name already exists')
  return {'id':x.id,'name':x.name,'timezone':x.timezone,'printed_ssid':x.printed_ssid}
 @app.post('/v1/sites/{id}/settings')
 def site_settings(id:str,b:SiteSettingsIn,u=Depends(current),s=Depends(db)):
  owner(u);x=allowed_site(s,u,id)
  if x.printed_ssid!=b.printed_ssid:
   x.printed_ssid=b.printed_ssid;log(s,u,'site_printed_ssid_updated',x.id);s.commit()
  return {'id':x.id,'name':x.name,'timezone':x.timezone,'printed_ssid':x.printed_ssid}
 @app.get('/v1/routers')
 def routers(u=Depends(current),s=Depends(db)):
  if u.role not in ['sme','platform']:raise HTTPException(403,'Router registry permission required')
  q=select(RouterDevice)
  if u.role=='sme':q=q.where(RouterDevice.tenant_id==u.tenant_id)
  plans={p.router_id:p for p in s.scalars(select(RouterPlan).where(RouterPlan.tenant_id==u.tenant_id) if u.role=='sme' else select(RouterPlan))}
  now=int(time.time())
  return [router_display(x,plans.get(x.id),now) for x in s.scalars(q.order_by(RouterDevice.created.desc()))]
 @app.post('/v1/routers',status_code=201)
 def register_router(b:RouterIn,u=Depends(current),s=Depends(db)):
  owner(u);allowed_site(s,u,b.site_id);x=RouterDevice(tenant_id=u.tenant_id,**b.model_dump(),registered_by=u.id,created=int(time.time()));s.add(x)
  try:s.flush();log(s,u,'router_registered',x.id);s.commit()
  except IntegrityError:s.rollback();raise HTTPException(409,'Router name already registered at this site')
  return {'id':x.id,'connection_state':'unverified','connection_verified':False,'hub_id':None,'lifecycle_state':None,'management_read_verified_at':None}
