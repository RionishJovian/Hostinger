"""Tenant portal drafts and guest-facing publication; never applies router rules."""
import hashlib,time
from fastapi import Depends,HTTPException
from sqlalchemy import select,update
from sqlalchemy.exc import IntegrityError
from .models import PortalSettings,Tenant,LocalPortalPackage
from .schemas import PortalConfig,PortalDraftIn,PortalPublishIn
PUBLIC_FIELDS=('business_name','welcome','language','terms','contact','direct_purchase','voucher_login','payment_destination','payment_instructions','payment_methods')
def public_config(settings):return {k:settings[k] for k in PUBLIC_FIELDS}
def package_scope_key(tenant_id,site_id=None):return 'site:'+site_id if site_id else 'tenant:'+tenant_id
def prepared_package(s,tenant_id,site_id,published_revision):
 if not published_revision:return None
 return s.scalar(select(LocalPortalPackage).where(LocalPortalPackage.tenant_id==tenant_id,LocalPortalPackage.site_id==site_id,LocalPortalPackage.scope_key==package_scope_key(tenant_id,site_id),LocalPortalPackage.published_revision==published_revision))
def package_status(package,published_revision):
 if not published_revision:return {'status':'not_published','published_revision':None,'sha256':None}
 if not package:return {'status':'pending','published_revision':published_revision,'sha256':None}
 return {'status':'ready_for_router_deployment','published_revision':package.published_revision,'sha256':package.package_sha256}
def store_local_portal_package(s,tenant_id,site_id,revision,cfg):
 from .local_portal_package import build_local_hotspot_package
 from .models import LocalPortalPackage
 payload=build_local_hotspot_package(cfg,tenant_id=tenant_id,site_id=site_id,revision=revision)
 artifact=LocalPortalPackage(tenant_id=tenant_id,site_id=site_id,scope_key=package_scope_key(tenant_id,site_id),published_revision=revision,package_sha256=hashlib.sha256(payload).hexdigest(),package_bytes=payload,created=int(time.time()))
 s.add(artifact);s.flush();return artifact
def portal_state(row,name='My business',package=None):
 published_revision=row.published_revision if row else None
 return {'revision':row.revision if row else 0,'draft':row.draft if row else PortalConfig(business_name=name).model_dump(),'published':public_config(row.published) if row and row.published else None,'published_revision':published_revision,'local_portal_package':package_status(package,published_revision),'router_deployment_status':'pending','router_apply_state':'not_connected'}
def register_portal(app,current,db,owner,log):
 @app.get('/v1/portal')
 def get_portal(u=Depends(current),s=Depends(db)):
  owner(u);row=s.get(PortalSettings,u.tenant_id);return portal_state(row,s.get(Tenant,u.tenant_id).name,prepared_package(s,u.tenant_id,None,row.published_revision if row else None))
 @app.get('/v1/portal/public')
 def guest_portal(site_id:str|None=None,u=Depends(current),s=Depends(db)):
  if u.role not in ['guest','sme']:raise HTTPException(403,'Business context required')
  from .site_portal import selected_portal
  row=selected_portal(s,u,site_id)
  return {'site_id':site_id,'revision':row.published_revision if row else None,'settings':public_config(row.published) if row and row.published else None,'network_access':'not_connected','voucher_redemption':'stored_pass_only'}
 @app.post('/v1/portal/draft')
 def save_draft(b:PortalDraftIn,u=Depends(current),s=Depends(db)):
  owner(u);now=int(time.time());row=s.get(PortalSettings,u.tenant_id)
  if row:
   result=s.execute(update(PortalSettings).where(PortalSettings.tenant_id==u.tenant_id,PortalSettings.revision==b.expected_revision).values(draft=b.settings.model_dump(),revision=b.expected_revision+1,updated=now))
   if result.rowcount!=1:raise HTTPException(409,'Portal changed in another session. Refresh before editing again.')
  else:
   if b.expected_revision!=0:raise HTTPException(409,'Portal revision does not match. Refresh before editing again.')
   s.add(PortalSettings(tenant_id=u.tenant_id,revision=1,draft=b.settings.model_dump(),updated=now))
  try:
   s.flush();log(s,u,'portal_draft_saved',str(b.expected_revision+1));s.commit()
  except IntegrityError:
   s.rollback();raise HTTPException(409,'Portal changed in another session. Refresh before editing again.')
  s.expire_all();row=s.get(PortalSettings,u.tenant_id);return portal_state(row,package=prepared_package(s,u.tenant_id,None,row.published_revision if row else None))
 @app.post('/v1/portal/publish')
 def publish(b:PortalPublishIn,u=Depends(current),s=Depends(db)):
  owner(u);row=s.get(PortalSettings,u.tenant_id)
  if not row or row.revision!=b.expected_revision:raise HTTPException(409,'Portal changed. Refresh and review the latest draft.')
  cfg=PortalConfig.model_validate(row.draft)
  if cfg.direct_purchase and (not cfg.payment_destination or not cfg.payment_methods or not cfg.payment_instructions):raise HTTPException(422,'Direct purchases need a payment destination, instructions and at least one method.')
  new_revision=b.expected_revision+1
  result=s.execute(update(PortalSettings).where(PortalSettings.tenant_id==u.tenant_id,PortalSettings.revision==b.expected_revision).values(published=cfg.model_dump(),published_revision=new_revision,revision=new_revision,updated=int(time.time())))
  if result.rowcount!=1:raise HTTPException(409,'Portal changed. Refresh and review the latest draft.')
  store_local_portal_package(s,u.tenant_id,None,new_revision,cfg);log(s,u,'portal_published',str(new_revision));s.commit();s.expire_all();row=s.get(PortalSettings,u.tenant_id);return portal_state(row,package=prepared_package(s,u.tenant_id,None,new_revision))
