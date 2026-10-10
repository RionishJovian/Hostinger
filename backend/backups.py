"""Backup metadata and restore verification records; storage execution is separate."""
import time
from fastapi import Depends,HTTPException
from sqlalchemy import select
from .models import BackupArtifact,Site
from .schemas import BackupIn

def backup_json(x):return {k:getattr(x,k) for k in ['id','site_id','router_id','kind','version','checksum','encrypted','status','restore_verified','integrity_verified','created','retention_until']}
def register_backups(app,current,db,owner,log):
 @app.get('/v1/backups')
 def backups(u=Depends(current),s=Depends(db)):
  if u.role=='guest':raise HTTPException(403,'Backup history is not available to guests')
  q=select(BackupArtifact)
  if u.role!='platform':q=q.where(BackupArtifact.tenant_id==u.tenant_id)
  return [backup_json(x) for x in s.scalars(q.order_by(BackupArtifact.created.desc()))]
 @app.post('/v1/backups',status_code=201)
 def create_backup(b:BackupIn,u=Depends(current),s=Depends(db)):
  owner(u)
  if b.site_id:
   site=s.get(Site,b.site_id)
   if not site or site.tenant_id!=u.tenant_id:raise HTTPException(404,'Site not found')
  if b.status=='healthy' and not b.restore_verified:raise HTTPException(422,'A healthy backup must have a verified restore')
  if not b.encrypted and b.kind!='control_plane':raise HTTPException(422,'Device backups must be encrypted')
  x=BackupArtifact(tenant_id=u.tenant_id,created=int(time.time()),**b.model_dump());s.add(x);s.flush();log(s,u,'backup_recorded',x.id);s.commit();return backup_json(x)
