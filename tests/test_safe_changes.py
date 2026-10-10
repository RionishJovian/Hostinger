import base64,os,tempfile,unittest,time
from pathlib import Path
from unittest.mock import patch
import test_backend as fixture
from backend.models import User,RouterPlan,RouterChange,BackupArtifact,RouterEvidence
from backend.routeros_adapter import RouterOSError
from backend.safe_changes import EncryptedBackupStore,process_due_changes
from cryptography.fernet import Fernet

def key(n):return base64.b64encode(bytes([n])*32).decode()
class Context:
 def __init__(self,*a,**k):pass
 def __enter__(self):return self
 def __exit__(self,*a):pass
 def export_configuration(self):return b'/interface wireguard peers export show-sensitive=no'
class Store:
 def __init__(self,*a,**k):pass
 def save_verified(self,data):return ('encrypted://test.bin','a'*64)
 def remove(self,ref):pass

class SafeChangeTests(unittest.TestCase):
 setUp=fixture.AccountPaymentTests.setUp
 tearDown=fixture.AccountPaymentTests.tearDown
 login=fixture.AccountPaymentTests.login
 def setup_router(self):
  platform=self.login('platform');owner=self.login('owner');hub=self.client.post('/v1/hubs',headers=platform,json={'name':'Safe Hub','endpoint':'hub.example.com','pool':'10.90.10.0/24','public_key':key(1)}).json()['id']
  with self.app.state.factory() as s:tenant=s.get(User,self.users['owner']).tenant_id
  self.client.post('/v1/hubs/'+hub+'/assignments',headers=platform,json={'tenant_id':tenant});site=self.client.post('/v1/sites',headers=owner,json={'name':'Safe Site'}).json()['id'];router=self.client.post('/v1/routers',headers=owner,json={'site_id':site,'name':'Gateway','model':'RB5009','reported_routeros':'7.20'}).json()['id']
  with self.app.state.factory() as s:
   user=s.query(User).filter_by(username='owner').one();now=int(time.time());s.add(RouterEvidence(tenant_id=tenant,router_id=router,kind='preflight',observed_at=now,source='routeros_rest_live_read',payload={'preflight_stage':'post_connection','compatibility':{'status':'compatible_for_safe_change'}},created_by=user.id,created=now));s.commit()
  plan=self.client.post('/v1/routers/'+router+'/plan',headers=owner,json={'hub_id':hub,'router_public_key':key(2)}).json();self.client.post('/v1/router-plans/'+plan['id']+'/review',headers=owner,json={'confirmed_review':True})
  with self.app.state.factory() as s:
   current=s.get(RouterPlan,plan['id']);now=int(time.time());current.lifecycle_state='connected';current.handshake_verified_at=now;current.management_read_verified_at=now;preflight=s.query(RouterEvidence).filter_by(router_id=router,kind='preflight').one();preflight.observed_at=now;s.commit()
  return owner,router
 def harness(self,state,setter=None,store=Store,reader=None):
  def read(client,hub_key):return reader(state) if reader else dict(state)
  def write(client,resource,seconds):
   if setter:return setter(state,seconds)
   state['persistent_keepalive_seconds']=seconds
  return patch.multiple('backend.safe_changes',load_routeros_safe_change_credential=lambda id:object(),RouterOSClient=Context,wireguard_peer_state=read,set_wireguard_keepalive=write,EncryptedBackupStore=store)
 def preview(self,owner,router,state):
  with self.harness(state):r=self.client.post('/v1/routers/'+router+'/changes/preview',headers=owner,json={'persistent_keepalive_seconds':25})
  self.assertEqual(r.status_code,201,r.text);self.assertEqual(r.json()['risk'],'high');self.assertEqual(r.json()['diff']['persistent_keepalive_seconds'],{'before':15,'after':25});return r.json()
 def base_state(self,router):return {'resource_id':'*A','interface':'mm-'+router[:8],'persistent_keepalive_seconds':15,'disabled':False,'public_key_fingerprint':'fingerprint'}
 def test_initial_bootstrap_or_stale_preflight_cannot_open_safe_change_gate(self):
  owner,router=self.setup_router()
  with self.app.state.factory() as s:
   evidence=s.query(RouterEvidence).filter_by(router_id=router,kind='preflight').one()
   evidence.payload={'preflight_stage':'initial_bootstrap','compatibility':{'status':'compatible_for_safe_change'}}
   s.commit()
  result=self.client.post('/v1/routers/'+router+'/changes/preview',headers=owner,json={'persistent_keepalive_seconds':25})
  self.assertEqual(result.status_code,409,result.text)
  self.assertIn('last 15 minutes',result.text)
  with self.app.state.factory() as s:self.assertEqual(s.query(RouterChange).filter_by(router_id=router).count(),0)

 def test_success_requires_confirmation_creates_verified_backup_and_preserves_expected_actual(self):
  owner,router=self.setup_router();state=self.base_state(router);change=self.preview(owner,router,state)
  with self.harness(state):self.assertEqual(self.client.post('/v1/router-changes/'+change['id']+'/apply',headers=owner,json={'expected_revision':1,'confirm_high_risk':False}).status_code,422)
  with self.harness(state):r=self.client.post('/v1/router-changes/'+change['id']+'/apply',headers=owner,json={'expected_revision':1,'confirm_high_risk':True})
  self.assertEqual(r.status_code,200,r.text);self.assertEqual(r.json()['status'],'applied');self.assertEqual(r.json()['before']['persistent_keepalive_seconds'],15);self.assertEqual(r.json()['desired']['persistent_keepalive_seconds'],25);self.assertEqual(r.json()['actual']['persistent_keepalive_seconds'],25);self.assertTrue(r.json()['safety_backup_verified'])
  with self.app.state.factory() as s:b=s.get(BackupArtifact,r.json()['backup_id']);self.assertTrue(b.encrypted and b.integrity_verified);self.assertFalse(b.restore_verified);self.assertEqual(b.router_id,router)
  self.assertNotIn('storage_ref',self.client.get('/v1/backups',headers=owner).text)
 def test_backup_failure_stops_before_apply(self):
  owner,router=self.setup_router();state=self.base_state(router);change=self.preview(owner,router,state);writes=[]
  class FailedStore:
   def __init__(self):pass
   def save_verified(self,data):raise RouterOSError('backup_verification_failed','bad')
  with self.harness(state,lambda state,seconds:writes.append(seconds),FailedStore):r=self.client.post('/v1/router-changes/'+change['id']+'/apply',headers=owner,json={'expected_revision':1,'confirm_high_risk':True})
  self.assertEqual(r.status_code,409);self.assertEqual(writes,[]);self.assertEqual(state['persistent_keepalive_seconds'],15)
  with self.app.state.factory() as s:self.assertEqual(s.get(RouterChange,change['id']).status,'failed')
 def test_apply_failure_unchanged_is_failed_without_false_rollback(self):
  owner,router=self.setup_router();state=self.base_state(router);change=self.preview(owner,router,state)
  def fail(state,seconds):raise RouterOSError('router_write_failed','no')
  with self.harness(state,fail):r=self.client.post('/v1/router-changes/'+change['id']+'/apply',headers=owner,json={'expected_revision':1,'confirm_high_risk':True})
  self.assertEqual(r.json()['status'],'failed');self.assertEqual(r.json()['error_code'],'apply_failed_unchanged');self.assertEqual(r.json()['actual'],r.json()['before'])
 def test_verification_mismatch_rolls_back_and_confirms_actual(self):
  owner,router=self.setup_router();state=self.base_state(router);change=self.preview(owner,router,state);calls=[]
  def mismatch_then_rollback(state,seconds):
   calls.append(seconds);state['persistent_keepalive_seconds']=99 if len(calls)==1 else seconds
  with self.harness(state,mismatch_then_rollback):r=self.client.post('/v1/router-changes/'+change['id']+'/apply',headers=owner,json={'expected_revision':1,'confirm_high_risk':True})
  self.assertEqual(r.json()['status'],'rolled_back');self.assertEqual(calls,[25,15]);self.assertEqual(r.json()['actual']['persistent_keepalive_seconds'],15)
 def test_rollback_failure_marks_recovery_required(self):
  owner,router=self.setup_router();state=self.base_state(router);change=self.preview(owner,router,state);calls=[]
  def broken(state,seconds):
   calls.append(seconds)
   if len(calls)==1:state['persistent_keepalive_seconds']=99
   else:raise RouterOSError('router_write_failed','rollback failed')
  with self.harness(state,broken):r=self.client.post('/v1/router-changes/'+change['id']+'/apply',headers=owner,json={'expected_revision':1,'confirm_high_risk':True})
  self.assertEqual(r.json()['status'],'recovery_required');self.assertEqual(r.json()['error_code'],'rollback_unconfirmed')
 def test_stale_router_state_and_request_revision_are_rejected(self):
  owner,router=self.setup_router();state=self.base_state(router);change=self.preview(owner,router,state);state['persistent_keepalive_seconds']=44
  with self.harness(state):r=self.client.post('/v1/router-changes/'+change['id']+'/apply',headers=owner,json={'expected_revision':1,'confirm_high_risk':True})
  self.assertEqual(r.status_code,409);self.assertEqual(self.client.get('/v1/router-changes',headers=owner).json()[0]['status'],'conflict')
  with self.harness(state):self.assertEqual(self.client.post('/v1/router-changes/'+change['id']+'/apply',headers=owner,json={'expected_revision':1,'confirm_high_risk':True}).status_code,409)
 def test_tenant_isolation(self):
  owner,router=self.setup_router();state=self.base_state(router);change=self.preview(owner,router,state);other=self.login('other')
  self.assertEqual(self.client.get('/v1/router-changes',headers=other).json(),[])
  with self.harness(state):self.assertEqual(self.client.post('/v1/router-changes/'+change['id']+'/apply',headers=other,json={'expected_revision':1,'confirm_high_risk':True}).status_code,404)
 def test_backup_retention_is_seven_days_and_maximum_three_fifo(self):
  owner,router=self.setup_router();state=self.base_state(router)
  for seconds in [20,30,40,50]:
   with self.harness(state):preview=self.client.post('/v1/routers/'+router+'/changes/preview',headers=owner,json={'persistent_keepalive_seconds':seconds}).json()
   with self.harness(state):result=self.client.post('/v1/router-changes/'+preview['id']+'/apply',headers=owner,json={'expected_revision':1,'confirm_high_risk':True})
   self.assertEqual(result.json()['status'],'applied')
  with self.app.state.factory() as s:
   rows=s.query(BackupArtifact).filter_by(router_id=router).order_by(BackupArtifact.created,BackupArtifact.id).all();self.assertEqual(len(rows),4);self.assertEqual(sum(x.status!='expired' for x in rows),3);self.assertEqual(sum(x.status=='expired' for x in rows),1)
   self.assertTrue(all(x.retention_until-x.created==7*24*60*60 for x in rows))
 def waiting_change(self):
  owner,router=self.setup_router();state=self.base_state(router);change=self.preview(owner,router,state);calls=[]
  def reader(state):
   calls.append(1)
   if len(calls)>1:raise RouterOSError('unreachable','offline')
   return dict(state)
  with self.harness(state,reader=reader):result=self.client.post('/v1/router-changes/'+change['id']+'/apply',headers=owner,json={'expected_revision':1,'confirm_high_risk':True})
  self.assertEqual(result.status_code,200,result.text);self.assertEqual(result.json()['phase'],'waiting_for_gateway');return owner,router,state,result.json()
 def scheduler(self,state,reader=None,setter=None,now=None):
  with self.harness(state,setter=setter,reader=reader):return process_due_changes(self.app.state.factory,now=now)
 def test_scheduler_reconnects_before_timeout_and_is_restart_idempotent(self):
  owner,router,state,change=self.waiting_change();state['persistent_keepalive_seconds']=25
  self.scheduler(state,now=change['gateway_deadline']-1)
  row=self.client.get('/v1/router-changes',headers=owner).json()[0];self.assertEqual(row['status'],'applied');self.assertEqual(row['phase'],'reconnected')
  revision=row['revision'];self.assertEqual(self.scheduler(state,now=change['gateway_deadline']+1),[]);self.assertEqual(self.client.get('/v1/router-changes',headers=owner).json()[0]['revision'],revision)
 def test_timeout_attempts_and_verifies_deterministic_rollback(self):
  owner,router,state,change=self.waiting_change();reads=[];writes=[]
  def reader(state):
   reads.append(1)
   if len(reads)==1:raise RouterOSError('unreachable','offline')
   return dict(state)
  def setter(state,seconds):writes.append(seconds);state['persistent_keepalive_seconds']=seconds
  self.scheduler(state,reader,setter,change['gateway_deadline'])
  row=self.client.get('/v1/router-changes',headers=owner).json()[0];self.assertEqual(row['status'],'rolled_back');self.assertEqual(writes,[15]);self.assertTrue(row['rollback_attempted'])
 def test_timeout_rollback_failure_then_delayed_recovery_requires_verified_state(self):
  owner,router,state,change=self.waiting_change()
  def offline(state):raise RouterOSError('unreachable','offline')
  def fail(state,seconds):raise RouterOSError('router_write_failed','failed')
  self.scheduler(state,offline,fail,change['gateway_deadline']);row=self.client.get('/v1/router-changes',headers=owner).json()[0];self.assertEqual(row['status'],'recovery_required')
  state['persistent_keepalive_seconds']=99;self.scheduler(state,now=change['gateway_deadline']+10);self.assertEqual(self.client.get('/v1/router-changes',headers=owner).json()[0]['status'],'recovery_required')
  state['persistent_keepalive_seconds']=15;self.scheduler(state,now=change['gateway_deadline']+20);row=self.client.get('/v1/router-changes',headers=owner).json()[0];self.assertEqual(row['status'],'rolled_back');self.assertIsNone(row['error_code']);self.assertIn('manual_or_delayed_recovery_verified',str(row['recovery_evidence']))
 def conflict(self):
  owner,router=self.setup_router();state=self.base_state(router);change=self.preview(owner,router,state);state['persistent_keepalive_seconds']=44
  with self.harness(state):result=self.client.post('/v1/router-changes/'+change['id']+'/apply',headers=owner,json={'expected_revision':1,'confirm_high_risk':True})
  self.assertEqual(result.status_code,409);return owner,router,state,self.client.get('/v1/router-changes',headers=owner).json()[0]
 def test_keep_router_accepts_verified_whole_state_without_backup(self):
  owner,router,state,change=self.conflict()
  with self.harness(state):result=self.client.post('/v1/router-changes/'+change['id']+'/resolve-conflict',headers=owner,json={'expected_revision':change['revision'],'choice':'keep_router','confirm_high_risk':False})
  self.assertEqual(result.status_code,200,result.text);self.assertEqual(result.json()['resolution_choice'],'keep_router');self.assertEqual(result.json()['expected']['persistent_keepalive_seconds'],44);self.assertFalse(result.json()['safety_backup_verified'])
  with self.app.state.factory() as s:self.assertEqual(s.query(BackupArtifact).filter_by(router_id=router).count(),0)
 def test_keep_mikromagic_requires_backup_and_verifies_whole_expected_state(self):
  owner,router,state,change=self.conflict();writes=[]
  with self.harness(state):self.assertEqual(self.client.post('/v1/router-changes/'+change['id']+'/resolve-conflict',headers=owner,json={'expected_revision':change['revision'],'choice':'keep_mikromagic','confirm_high_risk':False}).status_code,422)
  def setter(state,seconds):writes.append(seconds);state['persistent_keepalive_seconds']=seconds
  with self.harness(state,setter):result=self.client.post('/v1/router-changes/'+change['id']+'/resolve-conflict',headers=owner,json={'expected_revision':change['revision'],'choice':'keep_mikromagic','confirm_high_risk':True})
  self.assertEqual(result.status_code,200,result.text);self.assertEqual(result.json()['status'],'applied');self.assertEqual(result.json()['resolution_choice'],'keep_mikromagic');self.assertTrue(result.json()['safety_backup_verified']);self.assertEqual(writes,[25])
  self.assertEqual(self.client.post('/v1/router-changes/'+change['id']+'/resolve-conflict',headers=owner,json={'expected_revision':change['revision'],'choice':'keep_router','confirm_high_risk':False}).status_code,409)
 def test_keep_mikromagic_backup_failure_leaves_conflict_unresolved(self):
  owner,router,state,change=self.conflict();writes=[]
  class FailedStore:
   def __init__(self):pass
   def save_verified(self,data):raise RouterOSError('backup_verification_failed','bad')
  with self.harness(state,lambda state,seconds:writes.append(seconds),FailedStore):result=self.client.post('/v1/router-changes/'+change['id']+'/resolve-conflict',headers=owner,json={'expected_revision':change['revision'],'choice':'keep_mikromagic','confirm_high_risk':True})
  self.assertEqual(result.status_code,409);self.assertEqual(writes,[]);self.assertEqual(self.client.get('/v1/router-changes',headers=owner).json()[0]['status'],'conflict')
 def test_keep_mikromagic_verification_mismatch_rolls_back_to_conflict_state(self):
  owner,router,state,change=self.conflict();calls=[]
  def setter(state,seconds):calls.append(seconds);state['persistent_keepalive_seconds']=99 if len(calls)==1 else seconds
  with self.harness(state,setter):result=self.client.post('/v1/router-changes/'+change['id']+'/resolve-conflict',headers=owner,json={'expected_revision':change['revision'],'choice':'keep_mikromagic','confirm_high_risk':True})
  self.assertEqual(result.json()['status'],'rolled_back');self.assertEqual(calls,[25,44]);self.assertEqual(result.json()['actual']['persistent_keepalive_seconds'],44)
 def test_conflict_resolution_tenant_isolation(self):
  owner,router,state,change=self.conflict();other=self.login('other')
  with self.harness(state):self.assertEqual(self.client.post('/v1/router-changes/'+change['id']+'/resolve-conflict',headers=other,json={'expected_revision':change['revision'],'choice':'keep_router','confirm_high_risk':False}).status_code,404)

class EncryptedBackupStoreTests(unittest.TestCase):
 def test_artifact_is_ciphertext_mode_600_and_roundtrip_verified(self):
  with tempfile.TemporaryDirectory() as folder:
   key=Fernet.generate_key();store=EncryptedBackupStore(key,folder);ref,digest=store.save_verified(b'sensitive-redacted-export')
   path=Path(folder)/ref.removeprefix('encrypted://');self.assertNotIn(b'sensitive-redacted-export',path.read_bytes());self.assertEqual(oct(path.stat().st_mode&0o777),'0o600');self.assertEqual(len(digest),64)

if __name__=='__main__':unittest.main()
