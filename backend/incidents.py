"""Tenant-scoped incident history; root cause remains evidence-labelled.

Incidents that start during planned maintenance or network-off hours are labelled expected when recorded."""
import time
from fastapi import Depends,HTTPException
from sqlalchemy import select,update
from .models import Site,SiteIncident
from .schemas import IncidentIn
from .site_hours import expected_reason

def incident_json(x):return {k:getattr(x,k) for k in ['id','site_id','scope','status','started','ended','detection_source','symptoms','suspected_root_cause','confirmed_root_cause','remediation','notes','created_by','created','expected_reason']}
def register_incidents(app,current,db,owner,log):
 @app.get('/v1/incidents')
 def incidents(u=Depends(current),s=Depends(db)):
  if u.role=='guest':raise HTTPException(403,'Incident history is not available to guests')
  q=select(SiteIncident)
  if u.role!='platform':q=q.where(SiteIncident.tenant_id==u.tenant_id)
  return [incident_json(x) for x in s.scalars(q.order_by(SiteIncident.started.desc()))]

 @app.post('/v1/incidents',status_code=201)
 def create_incident(b:IncidentIn,u=Depends(current),s=Depends(db)):
  owner(u);site=s.get(Site,b.site_id)
  if not site or site.tenant_id!=u.tenant_id:raise HTTPException(404,'Site not found')
  if b.status=='resolved' and b.ended is None:raise HTTPException(422,'Resolved incidents require an end time')
  if b.ended is not None and b.ended<b.started:raise HTTPException(422,'End time cannot precede start time')
  x=SiteIncident(tenant_id=u.tenant_id,created_by=u.id,created=int(time.time()),expected_reason=expected_reason(s,site,b.scope,b.started),**b.model_dump());s.add(x);s.flush();log(s,u,'incident_recorded',x.id);s.commit();return incident_json(x)

 @app.post('/v1/incidents/{id}/resolve')
 def resolve_incident(id:str,b:IncidentIn,u=Depends(current),s=Depends(db)):
  owner(u);x=s.get(SiteIncident,id)
  if not x or x.tenant_id!=u.tenant_id:raise HTTPException(404,'Incident not found')
  if b.site_id!=x.site_id or b.scope!=x.scope:raise HTTPException(409,'Incident identity does not match')
  if b.ended is None:raise HTTPException(422,'Resolution requires an end time')
  if b.ended<x.started:raise HTTPException(422,'End time cannot precede start time')
  s.execute(update(SiteIncident).where(SiteIncident.id==id,SiteIncident.status!='resolved').values(status='resolved',ended=b.ended,confirmed_root_cause=b.confirmed_root_cause,remediation=b.remediation,notes=b.notes));log(s,u,'incident_resolved',id);s.commit();s.refresh(x);return incident_json(x)
