"""Tenant-scoped, read-only RouterOS capability pre-flight."""
import time
from fastapi import Depends,HTTPException
from sqlalchemy import select
from .models import RouterDevice,RouterPlan,RouterEvidence,MagicConnectEnrollment,MagicConnectAttempt,MagicConnectEvent
from .enrollment import router_identity_digest,sync_enrollment_state
import hmac
from .routeros_adapter import RouterOSClient,RouterOSError,discover_routeros,load_routeros_monitoring_credential,observe_wireguard_peer
from .hub_orchestrator import confirm_management_read
from .management_enrollment import ManagementSetupError,provision_management_identities

def register_routeros_preflight(app,current,db,log):
 def visible_router(s,u,id):
  if u.role not in ('sme','platform') or getattr(u,'staff_profile',None):raise HTTPException(403,'Router evidence permission required')
  router=s.get(RouterDevice,id)
  if not router or (u.role=='sme' and router.tenant_id!=u.tenant_id):raise HTTPException(404,'Router not found')
  return router
 def save(s,u,router,kind,evidence):
  observed=evidence.get('checked_at') or evidence.get('observed_at') or int(time.time())
  record=RouterEvidence(tenant_id=router.tenant_id,router_id=router.id,kind=kind,observed_at=observed,source=evidence['evidence_source'],payload=evidence,created_by=u.id,created=int(time.time()));s.add(record);s.flush();return record
 @app.post('/v1/routers/{id}/management-setup')
 def management_setup(id:str,u=Depends(current),s=Depends(db)):
  if u.role!='sme' or getattr(u,'staff_profile',None):raise HTTPException(403,'SME Owner permission required')
  router=visible_router(s,u,id)
  if not (app.state.magic_connect_pairing_enabled and getattr(app.state,'magic_connect_router_setup_enabled',False)):raise HTTPException(503,'Technician-guided router setup is not enabled')
  plan=s.scalar(select(RouterPlan).where(RouterPlan.router_id==id,RouterPlan.tenant_id==router.tenant_id))
  enrollment=s.get(MagicConnectEnrollment,plan.id) if plan else None;attempt=s.get(MagicConnectAttempt,enrollment.attempt_id) if enrollment else None
  if not attempt or attempt.router_id!=id or enrollment.owner_id!=u.id:raise HTTPException(409,{'code':'pairing_setup_required','message':'Finish management setup from the pairing that linked this router'})
  if enrollment.management_identities_at:raise HTTPException(409,{'code':'management_already_set_up','message':'MikroMagic logins already exist for this router'})
  now=int(time.time())
  if plan.lifecycle_state!='verifying_management' or not plan.handshake_verified_at or not 0<=now-plan.handshake_verified_at<=180:
   raise HTTPException(409,{'code':'fresh_hub_handshake_required','message':'Check the handshake again, then finish management setup within three minutes'})
  provision=getattr(app.state,'management_provisioner',provision_management_identities)
  try:evidence=provision(id,plan.snapshot,enrollment.expected_serial_digest)
  except (ManagementSetupError,RouterOSError) as e:
   log(s,u,'router_management_setup_failed',id);s.commit()
   raise HTTPException(e.status,{'code':e.code,'message':str(e)})
  enrollment.expected_identity_digest=evidence['identity_digest'];enrollment.management_identities_at=now
  s.add(MagicConnectEvent(tenant_id=attempt.tenant_id,attempt_id=attempt.id,actor_kind='owner',actor_id=u.id,event='management_identities_created',created=now))
  log(s,u,'router_management_identities_created',id);s.commit()
  return {'router_id':id,'plan_id':plan.id,'evidence':evidence,'connection_verified':False,'next_gate':'run_authenticated_preflight'}
 @app.post('/v1/routers/{id}/preflight')
 def preflight(id:str,u=Depends(current),s=Depends(db)):
  router=visible_router(s,u,id)
  plan=s.scalar(select(RouterPlan).where(RouterPlan.router_id==id,RouterPlan.tenant_id==router.tenant_id))
  if not plan or plan.lifecycle_state not in ('verifying_management','connected') or not plan.handshake_verified_at:
   raise HTTPException(409,{'code':'post_connection_preflight_required','message':'Run this authenticated capability pre-flight only after the reviewed bootstrap and a fresh Hub handshake. Initial owner review does not require remote pre-flight.'})
  now=int(time.time())
  if now-plan.handshake_verified_at<0 or now-plan.handshake_verified_at>180:
   raise HTTPException(409,{'code':'fresh_hub_handshake_required','message':'Refresh the Hub handshake before verifying authenticated router management access.'})
  try:
   credential=load_routeros_monitoring_credential(id)
   with RouterOSClient(credential) as client:evidence=discover_routeros(client)
  except RouterOSError as e:raise HTTPException(e.status,{'code':e.code,'message':str(e)})
  observed=evidence.get('checked_at') or int(time.time())
  enrollment=s.get(MagicConnectEnrollment,plan.id);expected=enrollment.expected_identity_digest if enrollment else None;actual=router_identity_digest(evidence.get('identity') or {})
  transport=evidence.get('transport') or {}
  identity_verified=bool(expected and actual and hmac.compare_digest(expected,actual) and credential.username=='mm-monitor-'+id[:8] and transport.get('scheme')=='https' and transport.get('tls_verified') is True)
  management_read={'evidence_source':'authenticated_routeros_read','authenticated':True,'identity_verified':identity_verified,'tenant_id':router.tenant_id,'router_id':router.id,'observed_at':observed}
  evidence['preflight_stage']='post_connection';evidence['management_read']=management_read
  connection=confirm_management_read(plan,management_read,tenant_id=router.tenant_id,router_id=router.id,now=int(time.time()))
  sync_enrollment_state(s,plan)
  if connection.get('connection_verified'):
   log(s,u,'router_management_read_verified',id)
  record=save(s,u,router,'preflight',evidence);log(s,u,'router_preflight_read',id);s.commit()
  if connection.get('connection_verified'):
   from .hotspot_sync import background_sync
   getattr(app.state,'hotspot_background_sync',background_sync)(app.state.factory,[id])
  compatibility=(evidence.get('compatibility') or {}).get('status','needs_review')
  next_gate=('management_identity_verification_required_no_router_changes' if not connection.get('connection_verified') else 'continue_to_separately_gated_safe_change_or_higher_review' if compatibility=='compatible_for_safe_change' else 'show_compatibility_guidance_no_router_changes')
  return {'router_id':id,'plan_id':plan.id,'evidence_id':record.id,'site_id':router.site_id,'configured_name':router.name,'configured_model':router.model,'configured_routeros':router.reported_routeros,'evidence':evidence,'connection':connection,'next_gate':next_gate}
 @app.post('/v1/routers/{id}/wireguard-evidence')
 def wireguard_evidence(id:str,u=Depends(current),s=Depends(db)):
  router=visible_router(s,u,id);plan=s.scalar(select(RouterPlan).where(RouterPlan.router_id==id))
  if not plan or not plan.reviewed_at:raise HTTPException(409,'A reviewed immutable router plan is required before WireGuard evidence can be collected')
  try:
   credential=load_routeros_monitoring_credential(id)
   with RouterOSClient(credential) as client:evidence=observe_wireguard_peer(client,plan.snapshot)
  except RouterOSError as e:raise HTTPException(e.status,{'code':e.code,'message':str(e)})
  record=save(s,u,router,'wireguard_router_peer',evidence);log(s,u,'router_wireguard_evidence_read',id);s.commit()
  return {'router_id':id,'plan_id':plan.id,'evidence_id':record.id,'evidence':evidence,'next_gate':'verify_hub_side_peer_handshake_and_tunnel_management_reachability'}
 @app.get('/v1/routers/{id}/evidence')
 def evidence_history(id:str,u=Depends(current),s=Depends(db)):
  visible_router(s,u,id)
  rows=s.scalars(select(RouterEvidence).where(RouterEvidence.router_id==id).order_by(RouterEvidence.observed_at.desc(),RouterEvidence.created.desc()).limit(100))
  return [{'id':x.id,'kind':x.kind,'observed_at':x.observed_at,'source':x.source,'payload':x.payload,'created_by':x.created_by,'created':x.created} for x in rows]
