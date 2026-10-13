"""Fail-closed RouterOS Safe Change, recovery scheduler and conflicts.

Writable v1 operations: reviewed Magic Hub WireGuard peer keepalive,
HotSpot local portal package publish, guest Wi-Fi SSID/security, guest
network addressing, and guest VLAN for an external AP. Real-device acceptance
remains external.
"""
from __future__ import annotations
import hashlib,json,os,time,uuid
from pathlib import Path
from cryptography.fernet import Fernet,InvalidToken
from fastapi import Depends,HTTPException
from sqlalchemy import select,update,or_
from .backup_key import derived_fernet
from .models import RouterDevice,RouterPlan,RouterEvidence,RouterChange,BackupArtifact,Audit,LocalPortalPackage
from .schemas import RouterChangePreviewIn,RouterChangeApplyIn,RouterConflictResolutionIn
from .routeros_adapter import RouterOSClient,RouterOSError,load_routeros_safe_change_credential,wireguard_peer_state,set_wireguard_keepalive
from . import hotspot_portal_publish as portal
from . import guest_wifi_settings as guest_wifi
from . import guest_network_addressing as guest_net
from . import guest_vlan_external_ap as guest_vlan
from .local_portal_package import package_install_files

ACTIVE=('applying','verifying','rolling_back');BLOCKING=ACTIVE+('conflict','recovery_required')
RETENTION_SECONDS=7*24*60*60;CONFLICT_HISTORY_SECONDS=7*24*60*60;GATEWAY_TIMEOUT_SECONDS=5*60
GUEST_SETTINGS_OPS=frozenset({'guest_wifi_settings','guest_network_addressing','guest_vlan_external_ap'})
IMMEDIATE_OPS=frozenset({'hotspot_portal_publish'})|GUEST_SETTINGS_OPS
def fingerprint(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def _phase(x):return {'applying':'applying','verifying':'waiting_for_gateway','applied':'reconnected','failed':'failed','rolled_back':'failed_restored','recovery_required':'recovery_required','conflict':'configuration_conflict','rolling_back':'rolling_back'}.get(x.status,x.status)
def _redact_change_fields(operation,data):
 if operation=='guest_wifi_settings':
  for key in ('before','desired','actual','expected'):
   if isinstance(data.get(key),dict):data[key]=guest_wifi.redact_state(data[key])
  if isinstance(data.get('diff'),dict):data['diff']=guest_wifi.redact_diff(data['diff'])
 elif operation=='guest_vlan_external_ap':
  for key in ('before','desired','actual','expected'):
   if isinstance(data.get(key),dict):
    data[key]={k:v for k,v in data[key].items() if k!='_created'}
 return data
def change_json(x):
 data={k:getattr(x,k) for k in ['id','router_id','operation','risk','status','revision','before','desired','actual','expected','diff','backup_id','safety_backup_verified','confirmed_at','gateway_deadline','last_probe_at','recovery_evidence','conflict_detected_at','conflict_history_until','resolution_choice','rollback_attempted','created','updated','error_code']}
 return _redact_change_fields(x.operation,data)|{'phase':_phase(x),'real_device_acceptance':'not_yet_performed'}
def _evidence(x,kind,now,actual=None,detail=None):
 events=list((x.recovery_evidence or {}).get('events',[]));item={'kind':kind,'at':now}
 if actual is not None:
  safe=guest_wifi.redact_state(actual) if x.operation=='guest_wifi_settings' else actual
  if isinstance(safe,dict):safe={k:v for k,v in safe.items() if k!='_created'}
  item['actual_fingerprint']=fingerprint(safe)
 if detail:item['detail']=detail
 events.append(item);x.recovery_evidence={'events':events[-30:]}
def _audit(s,x,action):s.add(Audit(actor_id=x.created_by,tenant_id=x.tenant_id,action=action,target=x.id,created=int(time.time())))
def _hub_key_needed(operation):return operation not in IMMEDIATE_OPS
def _wifi_verify(actual,expected):
 return fingerprint(guest_wifi.comparable(actual))==fingerprint(guest_wifi.comparable(expected))
def _net_verify(actual,expected):
 return fingerprint(guest_net.verify_shape(actual))==fingerprint(guest_net.verify_shape(expected))
def _vlan_verify(actual,expected):
 return fingerprint(guest_vlan.verify_shape(actual))==fingerprint(guest_vlan.verify_shape(expected))
def _guest_verify(operation,actual,expected):
 if operation=='guest_wifi_settings':return _wifi_verify(actual,expected)
 if operation=='guest_network_addressing':return _net_verify(actual,expected)
 if operation=='guest_vlan_external_ap':return _vlan_verify(actual,expected)
 return fingerprint(actual)==fingerprint(expected)

class EncryptedBackupStore:
 def __init__(self,key=None,directory=None):
  raw=key or os.environ.get('MIKROMAGIC_BACKUP_KEY')
  if not raw:raise RouterOSError('backup_key_missing','Encrypted backup key is not configured',500)
  try:self.cipher=Fernet(raw.encode() if isinstance(raw,str) else raw)
  except (ValueError,TypeError):
   self.cipher=derived_fernet(raw,b'mikromagic-router-backup-v1')
   if self.cipher is None:raise RouterOSError('backup_key_invalid','Encrypted backup key is invalid',500)
  self.root=Path(directory or os.environ.get('MIKROMAGIC_BACKUP_DIR','/var/lib/mikromagic/backups')).resolve();self.root.mkdir(parents=True,exist_ok=True,mode=0o700);os.chmod(self.root,0o700)
 def save_verified(self,plaintext:bytes):
  if not plaintext:raise RouterOSError('backup_invalid','Router configuration backup was empty')
  digest=hashlib.sha256(plaintext).hexdigest();name=str(uuid.uuid4())+'.bin';path=self.root/name;encrypted=self.cipher.encrypt(plaintext);fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
  try:
   with os.fdopen(fd,'wb') as output:output.write(encrypted);output.flush();os.fsync(output.fileno())
   try:restored=self.cipher.decrypt(path.read_bytes())
   except (InvalidToken,OSError):raise RouterOSError('backup_verification_failed','Encrypted backup could not be verified')
   if hashlib.sha256(restored).hexdigest()!=digest:raise RouterOSError('backup_verification_failed','Encrypted backup checksum verification failed')
  except Exception:path.unlink(missing_ok=True);raise
  return 'encrypted://'+name,digest
 def remove(self,storage_ref):
  if not isinstance(storage_ref,str) or not storage_ref.startswith('encrypted://'):return
  name=storage_ref.removeprefix('encrypted://')
  if not name or Path(name).name!=name:return
  path=(self.root/name).resolve()
  if path.parent==self.root:path.unlink(missing_ok=True)
def _prune(s,store,router_id,now):
 rows=list(s.scalars(select(BackupArtifact).where(BackupArtifact.router_id==router_id,BackupArtifact.status!='expired').order_by(BackupArtifact.created.desc(),BackupArtifact.id.desc())))
 for index,row in enumerate(rows):
  if (row.retention_until and row.retention_until<=now) or index>=3:store.remove(row.storage_ref);row.status='expired'
def _capture_backup(s,client,x,router,now):
 store=EncryptedBackupStore();storage_ref,checksum=store.save_verified(client.export_configuration());backup=BackupArtifact(tenant_id=x.tenant_id,site_id=router.site_id,router_id=router.id,kind='router_export',version='safe-change-'+x.id+'-'+str(x.revision),checksum=checksum,encrypted=True,status='created',restore_verified=False,integrity_verified=True,storage_ref=storage_ref,created=now,retention_until=now+RETENTION_SECONDS);s.add(backup);s.flush();_prune(s,store,router.id,now);x.backup_id=backup.id;x.safety_backup_verified=True;_evidence(x,'safety_backup_verified',now);return backup

def _read_live(client,x,hub_key=None):
 if x.operation=='hotspot_portal_publish':return portal.read_actual(client,x.desired if x.desired else x.before)
 if x.operation=='guest_wifi_settings':
  live=guest_wifi.read_actual(client,x.desired if x.desired else x.before);live.pop('_passphrase_secret',None);return live
 if x.operation=='guest_network_addressing':return guest_net.read_actual(client,x.desired if x.desired else x.before)
 if x.operation=='guest_vlan_external_ap':return guest_vlan.read_actual(client,x.desired if x.desired else x.before)
 return wireguard_peer_state(client,hub_key)

def _rollback(client,x,hub_key,now):
 x.status='rolling_back';x.rollback_attempted=True;x.expected=x.before;x.revision+=1;x.updated=now;_evidence(x,'rollback_attempted',now)
 try:
  if x.operation=='hotspot_portal_publish':actual=portal.rollback_portal(client,x.before,x.desired)
  elif x.operation=='guest_wifi_settings':
   actual=guest_wifi.rollback_change(client,x.before)
   if not _wifi_verify(actual,x.before):raise RouterOSError('rollback_mismatch','Router Wi-Fi state did not return to the rollback snapshot')
  elif x.operation=='guest_network_addressing':
   actual=guest_net.rollback_change(client,x.before)
   if not _net_verify(actual,x.before):raise RouterOSError('rollback_mismatch','Router guest addressing did not return to the rollback snapshot')
  elif x.operation=='guest_vlan_external_ap':
   actual=guest_vlan.rollback_change(client,x.before,x.actual if x.actual else x.desired)
   if not _vlan_verify(actual,x.before):raise RouterOSError('rollback_mismatch','Router guest VLAN state did not return to the rollback snapshot')
  else:
   set_wireguard_keepalive(client,x.resource_id,x.before['persistent_keepalive_seconds']);actual=wireguard_peer_state(client,hub_key)
   if fingerprint(actual)!=fingerprint(x.before):raise RouterOSError('rollback_mismatch','Router state did not return to the rollback snapshot')
  x.actual=actual
  x.status='rolled_back';x.error_code='change_failed_rollback_confirmed';x.revision+=1;x.updated=now;_evidence(x,'rollback_verified',now,actual);return True
 except RouterOSError as error:
  x.status='recovery_required';x.error_code='rollback_unconfirmed';x.revision+=1;x.updated=now;_evidence(x,'rollback_unconfirmed',now,detail=error.code);return False

def _plan(s,router_id):return s.scalar(select(RouterPlan).where(RouterPlan.router_id==router_id))
def _finish_probe(x,client,hub_key,now):
 x.last_probe_at=now
 try:actual=_read_live(client,x,hub_key)
 except RouterOSError as error:_evidence(x,'gateway_unreachable',now,detail=error.code);return False
 x.actual=actual
 if fingerprint(actual)==fingerprint(x.expected or x.desired):x.status='applied';x.error_code=None;x.revision+=1;x.updated=now;_evidence(x,'gateway_reconnected_verified',now,actual);return True
 _evidence(x,'verification_mismatch',now,actual);_rollback(client,x,hub_key,now);return True

def process_due_changes(factory,now=None):
 """Idempotent one-shot scheduler; safe to invoke repeatedly after restarts."""
 now=int(now or time.time());processed=[]
 with factory() as s:ids=list(s.scalars(select(RouterChange.id).where(RouterChange.status.in_(('verifying','recovery_required'))).order_by(RouterChange.updated,RouterChange.id)))
 for id in ids:
  with factory() as s:
   x=s.get(RouterChange,id)
   if not x or x.status not in ('verifying','recovery_required'):continue
   revision=x.revision;claimed=s.execute(update(RouterChange).where(RouterChange.id==id,RouterChange.revision==revision,RouterChange.status==x.status).values(last_probe_at=now,revision=RouterChange.revision+1)).rowcount
   if not claimed:s.rollback();continue
   s.commit();s.refresh(x);plan=_plan(s,x.router_id)
   if not plan or not plan.reviewed_at:x.status='recovery_required';x.error_code='reviewed_plan_missing';_evidence(x,'scheduler_blocked',now,detail='reviewed_plan_missing');x.updated=now;s.commit();processed.append((id,x.status));continue
   hub_key=plan.snapshot['hub']['public_key'] if _hub_key_needed(x.operation) else None
   try:
    credential=load_routeros_safe_change_credential(x.router_id)
    with RouterOSClient(credential) as client:
     if x.status=='recovery_required':
      try:actual=_read_live(client,x,hub_key)
      except RouterOSError as error:_evidence(x,'recovery_probe_unreachable',now,detail=error.code);x.updated=now;s.commit();processed.append((id,x.status));continue
      x.actual=actual
      expected_match=x.expected is not None and (
       _guest_verify(x.operation,actual,x.expected) if x.operation in GUEST_SETTINGS_OPS else fingerprint(actual)==fingerprint(x.expected)
      )
      desired_match=(
       _guest_verify(x.operation,x.expected,x.desired) if x.operation in GUEST_SETTINGS_OPS else fingerprint(x.expected)==fingerprint(x.desired)
      ) if x.expected is not None else False
      if expected_match:x.status='applied' if desired_match else 'rolled_back';x.error_code=None;x.revision+=1;x.updated=now;_evidence(x,'manual_or_delayed_recovery_verified',now,actual);_audit(s,x,'router_change_recovery_verified')
      else:_evidence(x,'recovery_state_mismatch',now,actual);x.updated=now
     else:
      try:actual=_read_live(client,x,hub_key)
      except RouterOSError as error:
       _evidence(x,'gateway_unreachable',now,detail=error.code);x.updated=now
       if x.gateway_deadline is not None and now>=x.gateway_deadline:_rollback(client,x,hub_key,now);_audit(s,x,'router_change_timeout_rollback')
      else:
       x.actual=actual
       ok=_guest_verify(x.operation,actual,x.expected or x.desired) if x.operation in GUEST_SETTINGS_OPS else fingerprint(actual)==fingerprint(x.expected or x.desired)
       if ok:x.status='applied';x.error_code=None;x.revision+=1;x.updated=now;_evidence(x,'gateway_reconnected_verified',now,actual);_audit(s,x,'router_change_reconnected')
       else:_evidence(x,'verification_mismatch',now,actual);_rollback(client,x,hub_key,now);_audit(s,x,'router_change_verification_failed')
   except RouterOSError as error:
    _evidence(x,'scheduler_transport_error',now,detail=error.code);x.updated=now
    if x.status=='verifying' and x.gateway_deadline is not None and now>=x.gateway_deadline:x.status='recovery_required';x.error_code='rollback_unconfirmed'
   s.commit();processed.append((id,x.status))
 return processed

def register_safe_changes(app,current,db,owner,log):
 def visible_router(s,u,id):
  owner(u);r=s.get(RouterDevice,id)
  if not r or r.tenant_id!=u.tenant_id:raise HTTPException(404,'Router not found')
  return r
 def plan_for(s,router):
  plan=_plan(s,router.id)
  if not plan or not plan.reviewed_at:raise HTTPException(409,'A reviewed immutable Magic Hub plan is required')
  if plan.lifecycle_state!='connected' or not plan.handshake_verified_at or not plan.management_read_verified_at:
   raise HTTPException(409,'A fresh Hub handshake and authenticated post-connection RouterOS read are required before Safe Change')
  evidence=s.scalar(select(RouterEvidence).where(RouterEvidence.router_id==router.id,RouterEvidence.tenant_id==router.tenant_id,RouterEvidence.kind=='preflight').order_by(RouterEvidence.observed_at.desc(),RouterEvidence.created.desc()).limit(1))
  payload=(evidence.payload or {}) if evidence else {};compatibility=payload.get('compatibility') or {}
  if (payload.get('preflight_stage')!='post_connection' or compatibility.get('status')!='compatible_for_safe_change' or
      evidence.observed_at<plan.management_read_verified_at or time.time()-evidence.observed_at>900):
   raise HTTPException(409,'A compatible post-connection RouterOS pre-flight from the last 15 minutes is required before Safe Change')
  return plan,evidence,payload
 def _apply_guest_immediate(client,x,hub_key,now,s,u,log):
  try:
   if x.operation=='guest_wifi_settings':actual=guest_wifi.apply_change(client,x.before,x.desired)
   elif x.operation=='guest_network_addressing':actual=guest_net.apply_change(client,x.before,x.desired)
   else:actual=guest_vlan.apply_change(client,x.before,x.desired)
  except RouterOSError as error:
   _evidence(x,'apply_response_failed',now,detail=error.code);s.commit()
   try:actual=_read_live(client,x,hub_key)
   except RouterOSError:x.status='recovery_required';x.error_code=error.code;x.revision+=1;x.updated=now;s.commit();return change_json(x)
   x.actual=actual
   unchanged=_guest_verify(x.operation,actual,x.before)
   if unchanged:x.status='failed';x.error_code='apply_failed_unchanged';x.revision+=1;x.updated=now;_evidence(x,'apply_failed_unchanged',now,actual)
   else:_rollback(client,x,hub_key,now)
   log(s,u,'router_change_apply_failed',x.id);s.commit();return change_json(x)
  x.actual=actual
  ok=_guest_verify(x.operation,actual,x.desired)
  if ok:
   x.status='applied';x.error_code=None;x.revision+=1;x.updated=now;_evidence(x,'guest_settings_verified',now,actual);log(s,u,'router_change_applied',x.id);s.commit();return change_json(x)
  _evidence(x,'verification_mismatch',now,actual);_rollback(client,x,hub_key,now);log(s,u,'router_change_verification_failed',x.id);s.commit();return change_json(x)
 @app.get('/v1/router-changes')
 def changes(u=Depends(current),s=Depends(db)):
  owner(u);now=int(time.time());q=select(RouterChange).where(RouterChange.tenant_id==u.tenant_id,or_(RouterChange.conflict_detected_at.is_(None),RouterChange.status=='conflict',RouterChange.conflict_history_until>now)).order_by(RouterChange.created.desc()).limit(100);return [change_json(x) for x in s.scalars(q)]
 @app.post('/v1/routers/{id}/changes/preview',status_code=201)
 def preview(id:str,b:RouterChangePreviewIn,u=Depends(current),s=Depends(db)):
  router=visible_router(s,u,id);plan,evidence,payload=plan_for(s,router)
  if b.operation in GUEST_SETTINGS_OPS:
   guest_wifi.require_flag(app)
  if s.scalar(select(RouterChange.id).where(RouterChange.router_id==id,RouterChange.status.in_(BLOCKING))):raise HTTPException(409,'Resolve the active protected operation or configuration conflict first')
  now=int(time.time())
  try:
   credential=load_routeros_safe_change_credential(id)
   with RouterOSClient(credential) as client:
    if b.operation=='hotspot_portal_publish':
     hotspot_plan,package,destination,profile_name=portal.load_reviewed_plan(s,u.tenant_id,id,b.hotspot_portal_plan_id)
     before,desired,diff,_files=portal.preview_state(client,hotspot_plan,package,destination,profile_name)
     x=RouterChange(tenant_id=u.tenant_id,router_id=id,operation='hotspot_portal_publish',resource_id=before['resource_id'],risk='high',status='previewed',revision=1,before=before,desired=desired,actual=before,expected=desired,diff=diff,before_fingerprint=fingerprint(before),safety_backup_verified=False,rollback_attempted=False,created_by=u.id,created=now,updated=now)
    elif b.operation=='guest_wifi_settings':
     before,desired,diff=guest_wifi.preview_state(client,payload,interface_name=b.wifi_interface,ssid=b.ssid,security_mode=b.security_mode,passphrase=b.passphrase)
     x=RouterChange(tenant_id=u.tenant_id,router_id=id,operation='guest_wifi_settings',resource_id=before['resource_id'],risk='high',status='previewed',revision=1,before=before,desired=desired,actual=guest_wifi.redact_state(before),expected=guest_wifi.redact_state(desired),diff=diff,before_fingerprint=fingerprint(guest_wifi.comparable(before)),safety_backup_verified=False,rollback_attempted=False,created_by=u.id,created=now,updated=now)
    elif b.operation=='guest_network_addressing':
     before,desired,diff=guest_net.preview_state(client,payload,interface_name=b.wifi_interface,network_cidr=b.network_cidr,gateway=b.gateway,pool_start=b.pool_start,pool_end=b.pool_end,dns=b.dns)
     x=RouterChange(tenant_id=u.tenant_id,router_id=id,operation='guest_network_addressing',resource_id=before['resource_id'],risk='high',status='previewed',revision=1,before=before,desired=desired,actual=before,expected=desired,diff=diff,before_fingerprint=fingerprint(guest_net.verify_shape(before)),safety_backup_verified=False,rollback_attempted=False,created_by=u.id,created=now,updated=now)
    elif b.operation=='guest_vlan_external_ap':
     before,desired,diff=guest_vlan.preview_state(client,payload,ethernet_port=b.ethernet_port,vlan_id=b.vlan_id,vlan_name=b.vlan_name,hotspot_interface=b.hotspot_interface or b.wifi_interface)
     x=RouterChange(tenant_id=u.tenant_id,router_id=id,operation='guest_vlan_external_ap',resource_id=before['resource_id'],risk='high',status='previewed',revision=1,before=before,desired=desired,actual=before,expected=desired,diff=diff,before_fingerprint=fingerprint(guest_vlan.verify_shape(before)),safety_backup_verified=False,rollback_attempted=False,created_by=u.id,created=now,updated=now)
    else:
     before=wireguard_peer_state(client,plan.snapshot['hub']['public_key'])
     if before['interface']!=plan.snapshot['router']['interface']:raise HTTPException(409,'Live peer interface conflicts with the reviewed MikroMagic plan')
     desired={**before,'persistent_keepalive_seconds':b.persistent_keepalive_seconds};diff={'persistent_keepalive_seconds':{'before':before['persistent_keepalive_seconds'],'after':b.persistent_keepalive_seconds},'impact':'Management tunnel keepalive changes may interrupt cloud management; guest internet routing is not intentionally changed.'}
     x=RouterChange(tenant_id=u.tenant_id,router_id=id,operation='wireguard_peer_keepalive',resource_id=before['resource_id'],risk='high',status='previewed',revision=1,before=before,desired=desired,actual=before,expected=desired,diff=diff,before_fingerprint=fingerprint(before),safety_backup_verified=False,rollback_attempted=False,created_by=u.id,created=now,updated=now)
  except HTTPException:raise
  except RouterOSError as e:raise HTTPException(e.status,{'code':e.code,'message':str(e)})
  s.add(x);s.flush();log(s,u,'router_change_previewed',x.id);s.commit();result=change_json(x);result['requires_owner_confirmation']=True;return result
 @app.post('/v1/router-changes/{id}/apply')
 def apply(id:str,b:RouterChangeApplyIn,u=Depends(current),s=Depends(db)):
  owner(u);x=s.get(RouterChange,id)
  if not x or x.tenant_id!=u.tenant_id:raise HTTPException(404,'Router change not found')
  if not b.confirm_high_risk:raise HTTPException(422,'Owner confirmation is required for this high-risk change')
  if x.operation in GUEST_SETTINGS_OPS:guest_wifi.require_flag(app)
  router=visible_router(s,u,x.router_id);plan,_evidence_row,_payload=plan_for(s,router)
  now=int(time.time());claimed=s.execute(update(RouterChange).where(RouterChange.id==id,RouterChange.revision==b.expected_revision,RouterChange.status=='previewed').values(status='applying',revision=RouterChange.revision+1,confirmed_at=now,updated=now)).rowcount
  if not claimed:s.rollback();raise HTTPException(409,'Change preview is stale or already processed; refresh before applying')
  s.commit();s.refresh(x);hub_key=plan.snapshot['hub']['public_key'] if _hub_key_needed(x.operation) else None
  try:
   credential=load_routeros_safe_change_credential(router.id)
   with RouterOSClient(credential) as client:
    if x.operation=='hotspot_portal_publish':
     live_before=portal.read_actual(client,{**x.before,'html_directory':x.before['html_directory'],'destination_present':False,'installed_file_names':[]})
     comparable={**x.before,'html_directory':live_before['html_directory'],'destination_present':live_before['destination_present'],'installed_file_names':live_before['installed_file_names'],'resource_id':live_before['resource_id']}
     if fingerprint(comparable)!=x.before_fingerprint:
      x.actual=comparable;x.status='conflict';x.error_code='stale_router_state';x.conflict_detected_at=now;x.conflict_history_until=now+CONFLICT_HISTORY_SECONDS;x.revision+=1;x.updated=now;_evidence(x,'configuration_conflict_detected',now,comparable);log(s,u,'router_change_conflict',x.id);s.commit();raise HTTPException(409,'Router configuration changed after preview; choose one whole version')
    elif x.operation=='guest_wifi_settings':
     actual=guest_wifi.read_actual(client,x.before);actual.pop('_passphrase_secret',None)
     if fingerprint(guest_wifi.comparable(actual))!=x.before_fingerprint:
      x.actual=guest_wifi.redact_state(actual);x.status='conflict';x.error_code='stale_router_state';x.conflict_detected_at=now;x.conflict_history_until=now+CONFLICT_HISTORY_SECONDS;x.revision+=1;x.updated=now;_evidence(x,'configuration_conflict_detected',now,actual);log(s,u,'router_change_conflict',x.id);s.commit();raise HTTPException(409,'Router configuration changed after preview; choose one whole version')
    elif x.operation=='guest_network_addressing':
     actual=guest_net.read_actual(client,x.before)
     if fingerprint(guest_net.verify_shape(actual))!=x.before_fingerprint:
      x.actual=actual;x.status='conflict';x.error_code='stale_router_state';x.conflict_detected_at=now;x.conflict_history_until=now+CONFLICT_HISTORY_SECONDS;x.revision+=1;x.updated=now;_evidence(x,'configuration_conflict_detected',now,actual);log(s,u,'router_change_conflict',x.id);s.commit();raise HTTPException(409,'Router configuration changed after preview; choose one whole version')
    elif x.operation=='guest_vlan_external_ap':
     actual=guest_vlan.read_actual(client,x.before)
     if fingerprint(guest_vlan.verify_shape(actual))!=x.before_fingerprint:
      x.actual=actual;x.status='conflict';x.error_code='stale_router_state';x.conflict_detected_at=now;x.conflict_history_until=now+CONFLICT_HISTORY_SECONDS;x.revision+=1;x.updated=now;_evidence(x,'configuration_conflict_detected',now,actual);log(s,u,'router_change_conflict',x.id);s.commit();raise HTTPException(409,'Router configuration changed after preview; choose one whole version')
    else:
     actual=wireguard_peer_state(client,hub_key)
     if fingerprint(actual)!=x.before_fingerprint:
      x.actual=actual;x.status='conflict';x.error_code='stale_router_state';x.conflict_detected_at=now;x.conflict_history_until=now+CONFLICT_HISTORY_SECONDS;x.revision+=1;x.updated=now;_evidence(x,'configuration_conflict_detected',now,actual);log(s,u,'router_change_conflict',x.id);s.commit();raise HTTPException(409,'Router configuration changed after preview; choose one whole version')
    try:_capture_backup(s,client,x,router,now)
    except RouterOSError as e:x.status='failed';x.error_code=e.code;x.revision+=1;x.updated=now;log(s,u,'router_change_backup_failed',x.id);s.commit();raise HTTPException(409,{'code':e.code,'message':'Required safety backup failed; no change was applied'})
    s.commit();x.expected=x.desired;x.updated=now
    if x.operation=='hotspot_portal_publish':
     package=s.get(LocalPortalPackage,x.desired['content_package_id'])
     if not package or package.package_sha256!=x.desired['content_sha256']:
      x.status='failed';x.error_code='package_missing';x.revision+=1;x.updated=now;log(s,u,'router_change_package_missing',x.id);s.commit();raise HTTPException(409,{'code':'package_missing','message':'The published portal package is no longer available'})
     files=package_install_files(package.package_bytes)
     try:actual=portal.apply_install(client,x.before,x.desired,files)
     except RouterOSError as error:
      _evidence(x,'apply_response_failed',now,detail=error.code);s.commit()
      try:actual=portal.read_actual(client,x.desired)
      except RouterOSError:x.status='recovery_required';x.error_code=error.code;x.revision+=1;x.updated=now;s.commit();return change_json(x)
      x.actual=actual
      if fingerprint({**actual,'html_directory':actual['html_directory'],'destination_present':actual['destination_present'],'installed_file_names':actual['installed_file_names']})==fingerprint(x.before) or (actual['html_directory']==x.before['html_directory'] and not actual['destination_present'] and not actual['installed_file_names']):
       if actual['html_directory']==x.before['html_directory'] and not actual['installed_file_names']:
        x.status='failed';x.error_code='apply_failed_unchanged';x.revision+=1;x.updated=now;_evidence(x,'apply_failed_unchanged',now,actual)
       else:_rollback(client,x,hub_key,now)
      elif fingerprint(actual)==fingerprint(x.desired):x.status='applied';x.error_code=None;x.revision+=1;x.updated=now;_evidence(x,'portal_publish_verified',now,actual)
      else:_rollback(client,x,hub_key,now)
      log(s,u,'router_change_apply_failed',x.id);s.commit();return change_json(x)
     x.actual=actual
     if fingerprint(actual)==fingerprint(x.desired):
      x.status='applied';x.error_code=None;x.revision+=1;x.updated=now;_evidence(x,'portal_publish_verified',now,actual);log(s,u,'router_change_applied',x.id);s.commit();return change_json(x)
     _evidence(x,'verification_mismatch',now,actual);_rollback(client,x,hub_key,now);log(s,u,'router_change_verification_failed',x.id);s.commit();return change_json(x)
    if x.operation in GUEST_SETTINGS_OPS:
     return _apply_guest_immediate(client,x,hub_key,now,s,u,log)
    x.gateway_deadline=now+GATEWAY_TIMEOUT_SECONDS;x.status='verifying';x.revision+=1;x.updated=now
    try:set_wireguard_keepalive(client,x.resource_id,x.desired['persistent_keepalive_seconds'])
    except RouterOSError as error:
     _evidence(x,'apply_response_failed',now,detail=error.code);s.commit()
     try:actual=wireguard_peer_state(client,hub_key)
     except RouterOSError:return change_json(x)
     x.actual=actual
     if fingerprint(actual)==fingerprint(x.before):x.status='failed';x.error_code='apply_failed_unchanged';x.revision+=1;x.updated=now;_evidence(x,'apply_failed_unchanged',now,actual)
     elif fingerprint(actual)==fingerprint(x.desired):x.status='applied';x.error_code=None;x.revision+=1;x.updated=now;_evidence(x,'gateway_reconnected_verified',now,actual)
     else:_rollback(client,x,hub_key,now)
     log(s,u,'router_change_apply_failed',x.id);s.commit();return change_json(x)
    s.commit();_finish_probe(x,client,hub_key,now);log(s,u,'router_change_waiting_or_verified',x.id);s.commit();return change_json(x)
  except HTTPException:raise
  except RouterOSError as e:x.status='recovery_required' if x.safety_backup_verified else 'failed';x.error_code=e.code;x.revision+=1;x.updated=now;_evidence(x,'transport_failed',now,detail=e.code);log(s,u,'router_change_transport_failed',x.id);s.commit();raise HTTPException(e.status,{'code':e.code,'message':str(e)})
 @app.post('/v1/router-changes/{id}/resolve-conflict')
 def resolve_conflict(id:str,b:RouterConflictResolutionIn,u=Depends(current),s=Depends(db)):
  owner(u);x=s.get(RouterChange,id)
  if not x or x.tenant_id!=u.tenant_id:raise HTTPException(404,'Router change not found')
  if b.choice=='keep_mikromagic' and not b.confirm_high_risk:raise HTTPException(422,'Owner confirmation is required to apply the MikroMagic version')
  if x.operation in GUEST_SETTINGS_OPS:guest_wifi.require_flag(app)
  now=int(time.time());claimed=s.execute(update(RouterChange).where(RouterChange.id==id,RouterChange.revision==b.expected_revision,RouterChange.status=='conflict').values(status='applying',revision=RouterChange.revision+1,updated=now)).rowcount
  if not claimed:s.rollback();raise HTTPException(409,'Conflict changed or was already resolved; refresh')
  s.commit();s.refresh(x);router=visible_router(s,u,x.router_id);plan,_ev,_pl=plan_for(s,router);hub_key=plan.snapshot['hub']['public_key'] if _hub_key_needed(x.operation) else None
  try:
   credential=load_routeros_safe_change_credential(router.id)
   with RouterOSClient(credential) as client:
    actual=_read_live(client,x,hub_key)
    if x.operation=='hotspot_portal_publish':
     actual=portal.read_actual(client,x.before)
    if x.actual is not None:
     same=_guest_verify(x.operation,actual,x.actual) if x.operation in GUEST_SETTINGS_OPS else fingerprint(actual)==fingerprint(x.actual)
     if not same:x.actual=actual;x.status='conflict';x.error_code='conflict_changed_again';x.revision+=1;x.updated=now;_evidence(x,'conflict_changed_again',now,actual);log(s,u,'router_conflict_changed',x.id);s.commit();raise HTTPException(409,'Router configuration changed again; review the whole version')
    if b.choice=='keep_router':x.actual=actual;x.expected=actual;x.status='applied';x.resolution_choice='keep_router';x.error_code=None;x.revision+=1;x.updated=now;_evidence(x,'keep_router_verified',now,actual);log(s,u,'router_conflict_keep_router',x.id);s.commit();return change_json(x)
    x.before=actual;x.before_fingerprint=(
     fingerprint(guest_wifi.comparable(actual)) if x.operation=='guest_wifi_settings' else
     fingerprint(guest_net.verify_shape(actual)) if x.operation=='guest_network_addressing' else
     fingerprint(guest_vlan.verify_shape(actual)) if x.operation=='guest_vlan_external_ap' else
     fingerprint(actual)
    );x.expected=x.desired;x.resolution_choice='keep_mikromagic';x.safety_backup_verified=False
    try:_capture_backup(s,client,x,router,now)
    except RouterOSError as error:x.status='conflict';x.error_code=error.code;x.revision+=1;x.updated=now;_evidence(x,'keep_mikromagic_backup_failed',now,detail=error.code);log(s,u,'router_conflict_backup_failed',x.id);s.commit();raise HTTPException(409,{'code':error.code,'message':'Safety backup failed; conflict remains unresolved and no change was applied'})
    if x.operation=='hotspot_portal_publish':
     package=s.get(LocalPortalPackage,x.desired['content_package_id'])
     if not package:x.status='conflict';x.error_code='package_missing';x.revision+=1;x.updated=now;s.commit();raise HTTPException(409,{'code':'package_missing','message':'The published portal package is no longer available'})
     files=package_install_files(package.package_bytes)
     try:actual=portal.apply_install(client,x.before,x.desired,files)
     except RouterOSError as error:_evidence(x,'keep_mikromagic_apply_response_failed',now,detail=error.code);x.status='conflict';x.revision+=1;x.updated=now;s.commit();return change_json(x)
     x.actual=actual
     if fingerprint(actual)==fingerprint(x.desired):x.status='applied';x.error_code=None;x.revision+=1;x.updated=now;_evidence(x,'portal_publish_verified',now,actual)
     else:_rollback(client,x,hub_key,now)
     log(s,u,'router_conflict_keep_mikromagic',x.id);s.commit();return change_json(x)
    if x.operation in GUEST_SETTINGS_OPS:
     return _apply_guest_immediate(client,x,hub_key,now,s,u,log)
    x.gateway_deadline=now+GATEWAY_TIMEOUT_SECONDS;x.status='verifying';x.revision+=1;x.updated=now;_evidence(x,'keep_mikromagic_applying',now)
    try:set_wireguard_keepalive(client,x.resource_id,x.desired['persistent_keepalive_seconds'])
    except RouterOSError as error:_evidence(x,'keep_mikromagic_apply_response_failed',now,detail=error.code);s.commit();return change_json(x)
    s.commit();_finish_probe(x,client,hub_key,now);log(s,u,'router_conflict_keep_mikromagic',x.id);s.commit();return change_json(x)
  except HTTPException:raise
  except RouterOSError as error:x.status='conflict';x.error_code=error.code;x.revision+=1;x.updated=now;_evidence(x,'conflict_resolution_transport_failed',now,detail=error.code);s.commit();raise HTTPException(error.status,{'code':error.code,'message':str(error)})
