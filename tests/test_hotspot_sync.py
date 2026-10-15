import os,time,unittest
from unittest.mock import patch
from cryptography.fernet import Fernet
import test_hubs
from backend.hotspot_sync import EXPIRY_CHECK,SCHEDULER,USER_COMMENT,internet_limits,profile_for,reconcile,user_limits
from backend.models import HotspotVoucherSync,MagicConnectEnrollment,RouterPlan,Voucher
from backend.routeros_adapter import RouterOSCredential,RouterOSError
from backend.voucher_vault import unseal

class FakeHotspot:
 """RouterOS HotSpot REST stand-in: users, profiles, active sessions, cookies and the expiry scheduler."""
 def __init__(self):self.users={};self.profiles={};self.schedulers={};self.active=[];self.cookies=[];self.next=1;self.fail=None;self.writes=[]
 def client(self,credential,router_id=None,**kwargs):return FakeClient(self)
 def new_id(self):self.next+=1;return f'*{self.next:X}'
 def user(self,name):return next((u for u in self.users.values() if u['name']==name),None)

class FakeClient:
 def __init__(self,router):self.router=router
 def __enter__(self):return self
 def __exit__(self,*args):pass
 def get(self,path,optional=False):
  if self.router.fail:raise RouterOSError(self.router.fail,'simulated')
  menu,_,query=path.partition('?');key,_,value=query.partition('=')
  table={'ip/hotspot/user':self.router.users,'ip/hotspot/user/profile':self.router.profiles,'system/scheduler':self.router.schedulers}.get(menu)
  if table is not None:return [dict(x) for x in table.values() if x.get(key)==value]
  if menu=='ip/hotspot/active':return [dict(x) for x in self.router.active if x['user']==value]
  if menu=='ip/hotspot/cookie':return [dict(x) for x in self.router.cookies if x['user']==value]
  raise AssertionError(path)
 def write(self,method,path,payload):
  if self.router.fail:raise RouterOSError(self.router.fail,'simulated')
  self.router.writes.append((method,path,dict(payload or {})))
  tables={'ip/hotspot/user':self.router.users,'ip/hotspot/user/profile':self.router.profiles,'system/scheduler':self.router.schedulers}
  if method=='PUT':
   if path=='ip/hotspot/user/profile' and 'comment' in payload:raise RouterOSError('router_write_failed','unknown parameter comment')
   if any(x['name']==payload['name'] for x in tables[path].values()):raise RouterOSError('router_write_failed','already exists')
   new=self.router.new_id();tables[path][new]={'.id':new,'disabled':'false',**payload};return {}
  menu,_,item=path.rpartition('/')
  if menu=='ip/hotspot/active':self.router.active=[x for x in self.router.active if x['.id']!=item];return {}
  if menu=='ip/hotspot/cookie':self.router.cookies=[x for x in self.router.cookies if x['.id']!=item];return {}
  if method=='PATCH':tables[menu][item].update(payload);return {}
  if method=='DELETE':del tables[menu][item];return {}
  raise AssertionError((method,path))

class HotspotSyncTests(unittest.TestCase):
 H=test_hubs.HubTests
 setUp=H.setUp;tearDown=H.tearDown;login=H.login;setup_hub=H.setup_hub;router=H.router;plan=H.plan
 def managed(self,owner,hub,site,n=2,name='Gateway'):
  router=self.router(owner,site,name);plan=self.plan(owner,hub,router,n).json()['id']
  attempt=self.client.post(f'/v1/sites/{site}/magic-connect/attempts',headers=owner,json={'router_name':name}).json()['id']
  with self.app.state.factory() as s:
   p=s.get(RouterPlan,plan);now=int(time.time());p.lifecycle_state='connected';p.handshake_verified_at=now;p.management_read_verified_at=now
   s.add(MagicConnectEnrollment(plan_id=plan,attempt_id=attempt,tenant_id=p.tenant_id,site_id=site,owner_id=self.users['owner'],created=now,management_identities_at=now));s.commit()
  return router
 def package(self,owner,**policy):
  body={'name':'Day pass','service':'internet','mode':'both','price':1000,'gb':2,'hours':24,'devices':2,'speed':10}|policy
  r=self.client.post('/v1/packages',headers=owner,json=body);self.assertEqual(r.status_code,201,r.text);return r.json()['id']
 def issue(self,owner,package,site,key):
  r=self.client.post('/v1/vouchers',headers=owner,json={'site_id':site,'package_id':package,'request_key':key.ljust(16,'x')});self.assertEqual(r.status_code,201,r.text);return r.json()
 def sync(self,router,fake):
  with patch('backend.hotspot_sync.load_routeros_safe_change_credential',return_value=RouterOSCredential('https://10.90.1.2','mm-safechange-x','x')):
   with self.app.state.factory() as s:return reconcile(s,router,fake.client)
 def fixture(self):
  self.env=patch.dict(os.environ,{'MIKROMAGIC_BACKUP_KEY':Fernet.generate_key().decode()});self.env.start();self.addCleanup(self.env.stop)
  self.app.state.hotspot_background_sync=lambda factory,routers:self.triggered.extend(routers);self.triggered=[]
  _,owner,hub,site,_=self.setup_hub();return owner,hub,site

 def test_issue_batch_generate_and_lost_auto_trigger_connected_router(self):
  owner,hub,site=self.fixture();router=self.managed(owner,hub,site);package=self.package(owner)
  issued=self.issue(owner,package,site,'auto-single');self.assertEqual(self.triggered,[router])
  replay=self.issue(owner,package,site,'auto-single');self.assertTrue(replay['replayed']);self.assertEqual(self.triggered,[router])
  batch={'site_id':site,'package_id':package,'count':2,'expires_days':7,'request_key':'auto-batch-00001'}
  created=self.client.post('/v1/vouchers/batch',headers=owner,json=batch);self.assertEqual(created.status_code,201,created.text);self.assertEqual(self.triggered,[router]*3)
  self.assertTrue(self.client.post('/v1/vouchers/batch',headers=owner,json=batch).json()['replayed']);self.assertEqual(self.triggered,[router]*3)
  drafted=self.client.post('/v1/voucher-jobs',headers=owner,json={'site_id':site,'package_id':package,'quantity':2,'layout':'a4_premium'});self.assertEqual(drafted.status_code,201,drafted.text)
  generated=self.client.post(f"/v1/voucher-jobs/{drafted.json()['id']}/generate",headers=owner,json={'confirm':True});self.assertEqual(generated.status_code,200,generated.text);self.assertEqual(self.triggered,[router]*5)
  replayed=self.client.post(f"/v1/voucher-jobs/{drafted.json()['id']}/generate",headers=owner,json={'confirm':True});self.assertTrue(replayed.json()['replayed']);self.assertEqual(self.triggered,[router]*5)
  lost=self.client.post(f"/v1/voucher-jobs/{drafted.json()['id']}/sheets/1/lost",headers=owner,json={'reason':'Missing envelope'});self.assertEqual(lost.status_code,200,lost.text);self.assertEqual(lost.json()['disabled'],2);self.assertEqual(self.triggered,[router]*7)

 def test_codes_are_sealed_per_business_and_never_returned(self):
  owner,hub,site=self.fixture();package=self.package(owner);issued=self.issue(owner,package,site,'seal-one')
  self.assertNotIn('code_sealed',issued)
  with self.app.state.factory() as s:
   v=s.get(Voucher,issued['id']);self.assertNotIn(issued['code'],v.code_sealed)
   self.assertEqual(unseal(v.tenant_id,v.code_sealed),issued['code']);self.assertIsNone(unseal('other-tenant',v.code_sealed))
  listed=self.client.get('/v1/vouchers',headers=owner).text;self.assertNotIn('code_sealed',listed);self.assertNotIn(issued['code'],listed)
  with patch.dict(os.environ,{'MIKROMAGIC_BACKUP_KEY':''}):unsealed=self.issue(owner,package,site,'seal-two')
  with self.app.state.factory() as s:self.assertIsNone(s.get(Voucher,unsealed['id']).code_sealed)
  import base64
  with patch.dict(os.environ,{'MIKROMAGIC_BACKUP_KEY':base64.b64encode(bytes(range(200,248))).decode()}):
   longer=self.issue(owner,package,site,'seal-three')
   with self.app.state.factory() as s:v=s.get(Voucher,longer['id']);self.assertEqual(unseal(v.tenant_id,v.code_sealed),longer['code'])

 def test_limits_map_to_profiles_and_users(self):
  limits=internet_limits({'service':'internet','mode':'both','gb':2,'hours':24,'devices':2,'speed':10,'clock':'elapsed'})
  name,profile=profile_for(limits)
  self.assertEqual((profile['shared-users'],profile['rate-limit']),('2','5000k/5000k'));self.assertIn('1d00:00:00',profile['on-login']);self.assertIn('|exp=',profile['on-login'])
  self.assertEqual(user_limits(limits),{'limit-bytes-total':'2000000000'})
  connected=internet_limits({'service':'internet','mode':'time','hours':1.5,'devices':1,'speed':4,'clock':'connected'})
  self.assertEqual(profile_for(connected)[1]['on-login'],'');self.assertEqual(user_limits(connected),{'limit-uptime':'0d01:30:00'})
  self.assertNotEqual(profile_for(connected)[0],name);self.assertIsNone(internet_limits({'service':'media','mode':'library'}))

 def test_sync_creates_disables_and_removes_only_mikromagic_users(self):
  owner,hub,site=self.fixture();router=self.managed(owner,hub,site);package=self.package(owner);fake=FakeHotspot()
  first,second,third=(self.issue(owner,package,site,k) for k in ('sync-a','sync-b','sync-c'))
  result=self.sync(router,fake);self.assertEqual((result['applied'],result['pending'],result['aborted']),(3,0,None))
  user=fake.user(first['code']);self.assertEqual((user['password'],user['comment'],user['limit-bytes-total'],user['disabled']),(first['code'],USER_COMMENT,'2000000000','false'))
  self.assertEqual(len(fake.profiles),1);self.assertEqual(list(fake.profiles.values())[0]['name'],user['profile'])
  self.assertEqual(fake.schedulers[next(iter(fake.schedulers))]['on-event'],EXPIRY_CHECK);self.assertEqual(next(iter(fake.schedulers.values()))['name'],SCHEDULER)
  self.assertEqual(self.sync(router,fake)['applied'],0)
  fake.active.append({'.id':'*S1','user':first['code']})
  fake.cookies.append({'.id':'*C1','user':first['code'],'mac-address':'AA:BB:CC:DD:EE:FF'})
  fake.cookies.append({'.id':'*C2','user':second['code'],'mac-address':'11:22:33:44:55:66'})
  self.triggered.clear()
  self.assertEqual(self.client.post(f"/v1/vouchers/{first['id']}/disable",headers=owner,json={'reason':'Lost'}).status_code,200);self.assertEqual(self.triggered,[router])
  self.client.post(f"/v1/vouchers/{second['id']}/delete",headers=owner)
  self.client.post(f"/v1/vouchers/{third['id']}/revoke",headers=owner,json={'reason':'Fraud'})
  fourth=self.issue(owner,package,site,'sync-d');fake.writes.clear()
  result=self.sync(router,fake);self.assertEqual(result['applied'],4)
  self.assertEqual(fake.user(first['code'])['disabled'],'true');self.assertEqual(fake.active,[]);self.assertEqual(fake.cookies,[])
  self.assertIsNone(fake.user(second['code']))
  self.assertEqual(fake.user(third['code'])['disabled'],'true');self.assertEqual(fake.user(fourth['code'])['disabled'],'false')
  self.assertTrue(any(m=='DELETE' and p.startswith('ip/hotspot/cookie/') for m,p,_ in fake.writes))
  self.assertIn('/ip hotspot cookie remove [find where user=$u]',EXPIRY_CHECK)
  self.assertEqual(fake.writes[-1][0],'PUT')
  self.client.post(f"/v1/vouchers/{first['id']}/enable",headers=owner);self.sync(router,fake)
  self.assertEqual(fake.user(first['code'])['disabled'],'false')

 def test_conflicts_old_vouchers_media_and_outages_are_reported_not_forced(self):
  owner,hub,site=self.fixture();router=self.managed(owner,hub,site);package=self.package(owner);fake=FakeHotspot()
  mine=self.issue(owner,package,site,'conflict-a');fake.users['*99']={'.id':'*99','name':mine['code'],'comment':'Owner account','disabled':'false'}
  media=self.issue(owner,package,site,'media-a')
  with self.app.state.factory() as s:v=s.get(Voucher,media['id']);v.policy={'service':'media','mode':'library','hours':24};s.commit()
  with patch.dict(os.environ,{'MIKROMAGIC_BACKUP_KEY':''}):self.issue(owner,package,site,'old-a')
  result=self.sync(router,fake)
  self.assertEqual((result['applied'],result['failed']),(0,1));self.assertEqual(result['skipped'],{'media_pass':1,'issued_before_router_sync':1})
  self.assertEqual(fake.users['*99']['comment'],'Owner account')
  with self.app.state.factory() as s:self.assertEqual(s.get(HotspotVoucherSync,(mine['id'],router)).last_error,'hotspot_user_conflict')
  del fake.users['*99'];fake.fail='unreachable'
  result=self.sync(router,fake);self.assertEqual((result['applied'],result['aborted']),(0,'unreachable'))
  fake.fail=None;self.assertEqual(self.sync(router,fake)['applied'],1)

 def test_same_named_profile_with_other_limits_is_a_conflict(self):
  owner,hub,site=self.fixture();router=self.managed(owner,hub,site);package=self.package(owner);fake=FakeHotspot()
  issued=self.issue(owner,package,site,'profile-a')
  limits=internet_limits({'service':'internet','mode':'both','gb':2,'hours':24,'devices':2,'speed':10,'clock':'elapsed'});name,_=profile_for(limits)
  fake.profiles['*50']={'.id':'*50','name':name,'shared-users':'5','rate-limit':''}
  self.assertEqual((self.sync(router,fake)['failed'],fake.profiles['*50']['shared-users']),(1,'5'))
  with self.app.state.factory() as s:self.assertEqual(s.get(HotspotVoucherSync,(issued['id'],router)).last_error,'profile_conflict')
  fake.profiles['*50'].update({'shared-users':'2','rate-limit':'5000k/5000k'})
  self.assertEqual(self.sync(router,fake)['applied'],1);self.assertEqual(fake.user(issued['code'])['profile'],name)

 def test_endpoints_require_a_managed_router_and_one_router_per_shop(self):
  owner,hub,site=self.fixture();plain=self.router(owner,site,'Unmanaged')
  self.assertEqual(self.client.post(f'/v1/routers/{plain}/hotspot-sync',headers=owner).json()['detail']['code'],'router_not_managed')
  self.assertFalse(self.client.get(f'/v1/routers/{plain}/hotspot-sync',headers=owner).json()['managed'])
  router=self.managed(owner,hub,site,3,'Managed');package=self.package(owner);self.issue(owner,package,site,'endpoint-a');fake=FakeHotspot()
  self.assertEqual(self.client.get(f'/v1/routers/{router}/hotspot-sync',headers=owner).json()['pending'],1)
  self.assertEqual(self.client.post(f'/v1/routers/{router}/hotspot-sync',headers=self.login('other')).status_code,404)
  self.app.state.hotspot_client_factory=fake.client
  with patch('backend.hotspot_sync.load_routeros_safe_change_credential',return_value=RouterOSCredential('https://10.90.1.3','mm-safechange-x','x')):
   done=self.client.post(f'/v1/routers/{router}/hotspot-sync',headers=owner)
  self.assertEqual(done.status_code,200,done.text);self.assertEqual(done.json()['applied'],1);self.assertFalse(done.json()['enforcement_verified'])
  status=self.client.get(f'/v1/routers/{router}/hotspot-sync',headers=owner).json();self.assertEqual((status['in_sync'],status['pending']),(1,0))
  self.managed(owner,hub,site,4,'Second')
  self.assertEqual(self.client.post(f'/v1/routers/{router}/hotspot-sync',headers=owner).json()['detail']['code'],'router_choice_required')

if __name__=='__main__':unittest.main()
