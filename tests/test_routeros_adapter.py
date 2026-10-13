import json,os,tempfile,unittest,time
from pathlib import Path
from unittest.mock import patch
import httpx
import test_backend as fixture
from backend.routeros_adapter import RouterOSClient,RouterOSError,discover_routeros,hotspot_portal_inventory,load_routeros_credential,load_routeros_monitoring_credential,load_routeros_safe_change_credential,observe_wireguard_peer,_duration_seconds,wireguard_peer_state,set_wireguard_keepalive
from backend.models import RouterPlan,RouterEvidence,User,MagicConnectAttempt,MagicConnectEnrollment
from backend.enrollment import router_identity_digest

class RouterOSAdapterTests(unittest.TestCase):
 def test_secret_loading_requires_https_and_rejects_extra_fields(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'router.json';p.write_text(json.dumps({'base_url':'https://router.example','username':'mm-monitor-router','password':'secret'}));p.chmod(0o640);c=load_routeros_credential('router',d);self.assertEqual(c.base_url,'https://router.example');self.assertTrue(c.verify)
   p.write_text(json.dumps({'base_url':'http://router.example','username':'mm-monitor-router','password':'secret'}));p.chmod(0o640)
   with self.assertRaisesRegex(RouterOSError,'requires HTTPS'):load_routeros_credential('router',d)
   p.write_text(json.dumps({'base_url':'https://router.example','username':'mm-monitor-router','password':'secret','private_key':'no'}));p.chmod(0o640)
   with self.assertRaisesRegex(RouterOSError,'unsupported fields'):load_routeros_credential('router',d)
 def test_monitoring_and_safe_change_secrets_are_separate_and_identity_bound(self):
  with tempfile.TemporaryDirectory() as d:
   ro=Path(d)/'monitor';rw=Path(d)/'safe';ro.mkdir(mode=0o700);rw.mkdir(mode=0o700)
   (ro/'router.json').write_text(json.dumps({'base_url':'https://router.example','username':'mm-monitor-router','password':'read-secret'}));(ro/'router.json').chmod(0o640)
   (rw/'router.json').write_text(json.dumps({'base_url':'https://router.example','username':'mm-safechange-router','password':'write-secret'}));(rw/'router.json').chmod(0o640)
   self.assertEqual(load_routeros_monitoring_credential('router',str(ro)).username,'mm-monitor-router')
   self.assertEqual(load_routeros_safe_change_credential('router',str(rw)).username,'mm-safechange-router')
   with self.assertRaisesRegex(RouterOSError,'dedicated monitoring'):
    load_routeros_monitoring_credential('router',str(rw))
   (ro/'router.json').chmod(0o604)
   with self.assertRaisesRegex(RouterOSError,'accessible to other users'):
    load_routeros_monitoring_credential('router',str(ro))
 def test_live_read_shape_never_claims_handshake_or_enforcement(self):
  methods=[]
  def handle(request):
   methods.append(request.method)
   data={
    '/rest/system/resource':{'platform':'MikroTik','version':'7.20','architecture-name':'arm64','board-name':'hAP ax3','cpu-count':'4'},
    '/rest/system/routerboard':{'routerboard':'true','model':'C53UiG+5HPaxD2HPaxD','serial-number':'SAFE-SERIAL','current-firmware':'7.20'},
    '/rest/interface/wireguard':[{'name':'mm-test'}],'/rest/ip/hotspot':[{'name':'hotspot1','profile':'default'}],'/rest/ip/hotspot/user':[],
    '/rest/ip/hotspot/profile':[{'name':'default','html-directory':'hotspot','login-by':'http-chap,cookie'}],'/rest/ip/hotspot/walled-garden':[],
    '/rest/file':[{'name':'flash','type':'disk'},{'name':'hotspot/login.html','type':'html','size':'512'}],
    '/rest/ip/dhcp-server':[{'name':'dhcp1'}],'/rest/system/ntp/client':{'enabled':'true'},
   }
   if request.url.path=='/rest/file' and request.url.params.get('.proplist')!='name,type,size,last-modified':
    return httpx.Response(200,content=b'[{"name":"hotspot/img/logo.png","contents":"\x89PNG"}]')
   return httpx.Response(200,json=data[request.url.path])
  credential=type('Credential',(),{'base_url':'https://router.example','username':'api','password':'secret','verify':True})()
  with RouterOSClient(credential,transport=httpx.MockTransport(handle)) as client:r=discover_routeros(client)
  self.assertEqual(r['evidence_source'],'routeros_rest_live_read');self.assertTrue(r['capabilities']['wireguard']);self.assertEqual(r['compatibility']['status'],'compatible_for_safe_change');self.assertEqual(r['compatibility']['architecture'],'arm64');self.assertEqual(r['compatibility']['management_permissions']['safe_change_write'],'not_tested');self.assertEqual(r['inventory_counts']['hotspot'],1);self.assertFalse(r['wireguard_handshake_verified']);self.assertFalse(r['hotspot_enforcement_verified']);self.assertFalse(r['configuration_modified']);self.assertNotIn('password',json.dumps(r));self.assertEqual(set(methods),{'GET'})
  self.assertFalse(r['hotspot_portal_inventory']['write_operations_enabled']);self.assertEqual(r['hotspot_portal_inventory']['profiles'][0]['server_count'],1)

 def test_hotspot_portal_inventory_is_allowlisted_and_never_exposes_file_contents(self):
  report=hotspot_portal_inventory(
   [{'name':'hs-main','interface':'bridge-guest','profile':'shared','disabled':'false','secret':'do-not-return'}],
   [{'name':'shared','html-directory':'flash/hotspot-mm','login-by':'http-chap','radius-secret':'do-not-return'}],
   [{'name':'*1','server':'hs-main','action':'allow','dst-host':'portal.example.test','path':'/assets/*','private-field':'do-not-return'}],
   [{'name':'flash','type':'disk'},{'name':'flash/hotspot-mm/login.html','type':'html','size':2048,'contents':'must-not-return'},
    {'name':'flash/private.key','type':'file','size':64,'contents':'must-not-return'}])
  encoded=json.dumps(report)
  self.assertEqual(report['servers'][0]['profile_server_count'],1);self.assertEqual(report['profiles'][0]['server_count'],1)
  self.assertTrue(report['storage']['flash_directory_present']);self.assertEqual([x['name'] for x in report['storage']['configured_portal_files']],['flash/hotspot-mm/login.html'])
  self.assertFalse(report['write_operations_enabled']);self.assertNotIn('do-not-return',encoded);self.assertNotIn('must-not-return',encoded)
 def test_auth_and_optional_capability_handling(self):
  def auth(request):return httpx.Response(401,json={'error':'bad'})
  credential=type('Credential',(),{'base_url':'https://router.example','username':'api','password':'secret','verify':True})()
  with RouterOSClient(credential,transport=httpx.MockTransport(auth)) as client:
   with self.assertRaisesRegex(RouterOSError,'rejected'):client.get('system/resource')
  def optional(request):return httpx.Response(404,json={'error':'missing'})
  with RouterOSClient(credential,transport=httpx.MockTransport(optional)) as client:self.assertIsNone(client.get('interface/wireguard',optional=True))
 def test_router_side_wireguard_observation_is_scoped_and_not_full_acceptance(self):
  self.assertEqual(_duration_seconds('1w2d03:04:05'),788645);self.assertEqual(_duration_seconds('1m2s'),62);self.assertIsNone(_duration_seconds('never'))
  def handle(request):return httpx.Response(200,json=[{'interface':'mm-router1','public-key':'hub-public-key','last-handshake':'42s','rx':'123','tx':'456'}])
  credential=type('Credential',(),{'base_url':'https://router.example','username':'api','password':'secret','verify':True})()
  plan={'hub':{'public_key':'hub-public-key'},'router':{'interface':'mm-router1'}}
  with RouterOSClient(credential,transport=httpx.MockTransport(handle)) as client:r=observe_wireguard_peer(client,plan,recent_seconds=180)
  self.assertTrue(r['router_side_handshake_observed']);self.assertEqual(r['handshake_age_seconds'],42);self.assertFalse(r['hub_side_handshake_verified']);self.assertFalse(r['management_reachability_verified']);self.assertFalse(r['acceptance_complete']);self.assertNotIn('hub-public-key',json.dumps(r))
  plan['router']['interface']='different'
  with RouterOSClient(credential,transport=httpx.MockTransport(handle)) as client:r=observe_wireguard_peer(client,plan,recent_seconds=180)
  self.assertFalse(r['router_side_handshake_observed']);self.assertFalse(r['interface_match'])
 def test_controlled_peer_write_and_sensitive_redacted_export_transport(self):
  seen=[]
  def handle(request):
   seen.append((request.method,request.url.path,request.read()))
   if request.url.path=='/rest/interface/wireguard/peers':return httpx.Response(200,json=[{'.id':'*A','interface':'mm-router','public-key':'hub-key','persistent-keepalive':'25','disabled':'false'}])
   if request.url.path=='/rest/export':return httpx.Response(200,json={'ret':'/interface wireguard peers export show-sensitive=no'})
   return httpx.Response(200,json={})
  credential=type('Credential',(),{'base_url':'https://router.example','username':'api','password':'secret','verify':True})()
  with RouterOSClient(credential,transport=httpx.MockTransport(handle)) as client:
   state=wireguard_peer_state(client,'hub-key');self.assertEqual(state['persistent_keepalive_seconds'],25);self.assertNotIn('hub-key',json.dumps(state));set_wireguard_keepalive(client,state['resource_id'],30);backup=client.export_configuration()
  self.assertEqual(seen[1][0:2],('PATCH','/rest/interface/wireguard/peers/*A'));self.assertIn(b'"persistent-keepalive":"30"',seen[1][2]);self.assertIn(b'show-sensitive=no',backup)

class RouterOSPreflightApiTests(unittest.TestCase):
 setUp=fixture.AccountPaymentTests.setUp
 tearDown=fixture.AccountPaymentTests.tearDown
 login=fixture.AccountPaymentTests.login
 def test_preflight_is_scoped_audited_and_does_not_claim_acceptance(self):
  owner=self.login('owner');site=self.client.post('/v1/sites',headers=owner,json={'name':'RouterOS Lab'}).json()['id'];router=self.client.post('/v1/routers',headers=owner,json={'site_id':site,'name':'Gateway','model':'unknown','reported_routeros':''}).json()['id']
  self.assertEqual(self.client.post('/v1/routers/'+router+'/preflight',headers=owner).status_code,409)
  with self.app.state.factory() as s:
   user=s.query(User).filter_by(username='owner').one();now=int(time.time());s.connection().exec_driver_sql('PRAGMA foreign_keys=OFF');plan=RouterPlan(tenant_id=user.tenant_id,router_id=router,hub_id='isolated-test-hub',router_public_key='router-public-key',address='10.0.0.2',snapshot={'hub':{'public_key':'hub-public-key'},'router':{'interface':'mm-test'}},created=now,reviewed_at=now,lifecycle_state='verifying_management',handshake_verified_at=now);s.add(plan);s.commit()
  evidence={'checked_at':int(time.time()),'evidence_source':'routeros_rest_live_read','transport':{'scheme':'https','tls_verified':True},'identity':{'version':'7.20.2','architecture-name':'arm64'},'capabilities':{'wireguard':True},'compatibility':{'status':'compatible_for_safe_change'},'wireguard_handshake_verified':False,'hotspot_enforcement_verified':False,'configuration_modified':False}
  class Context:
   def __init__(self,*a,**k):pass
   def __enter__(self):return self
   def __exit__(self,*a):pass
  credential=type('Credential',(),{'username':'mm-monitor-'+router[:8]})()
  with patch('backend.routeros_preflight.load_routeros_monitoring_credential',return_value=credential),patch('backend.routeros_preflight.RouterOSClient',Context),patch('backend.routeros_preflight.discover_routeros',return_value=evidence):
   result=self.client.post('/v1/routers/'+router+'/preflight',headers=owner)
  self.assertEqual(result.status_code,200,result.text);self.assertEqual(result.json()['evidence']['preflight_stage'],'post_connection');self.assertFalse(result.json()['connection']['connection_verified']);self.assertEqual(result.json()['next_gate'],'management_identity_verification_required_no_router_changes')
  with self.app.state.factory() as s:self.assertEqual(s.get(RouterPlan,plan.id).lifecycle_state,'verifying_management')
  with self.app.state.factory() as s:self.assertEqual(s.query(RouterEvidence).filter_by(router_id=router,kind='preflight').count(),1)
  identity={'serial_number':'SYNTHETIC-ONLY','model':'fixture-board','architecture-name':'arm64'}
  with self.app.state.factory() as s:
   s.connection().exec_driver_sql('PRAGMA foreign_keys=OFF')
   attempt=MagicConnectAttempt(id='bound-read',tenant_id=user.tenant_id,site_id=site,owner_id=user.id,router_name='Synthetic',code_hash='e'*64,comparison_code='000000',status='approved',created=1,expires=4102444800,approved_at=2)
   s.add_all([attempt,MagicConnectEnrollment(plan_id=plan.id,attempt_id=attempt.id,tenant_id=user.tenant_id,site_id=site,owner_id=user.id,expected_identity_digest=router_identity_digest(identity),created=2)]);s.commit()
  evidence['identity']=identity|{'serial_number':'DIFFERENT-SYNTHETIC'}
  with patch('backend.routeros_preflight.load_routeros_monitoring_credential',return_value=credential),patch('backend.routeros_preflight.RouterOSClient',Context),patch('backend.routeros_preflight.discover_routeros',return_value=evidence):
   self.assertFalse(self.client.post('/v1/routers/'+router+'/preflight',headers=owner).json()['connection']['connection_verified'])
   evidence['identity']=identity
   self.assertTrue(self.client.post('/v1/routers/'+router+'/preflight',headers=owner).json()['connection']['connection_verified'])
   evidence['transport']['tls_verified']=False
   self.assertFalse(self.client.post('/v1/routers/'+router+'/preflight',headers=owner).json()['connection']['connection_verified'])
  self.assertEqual(self.client.post('/v1/routers/'+router+'/preflight',headers=self.login('other')).status_code,404);self.assertEqual(self.client.post('/v1/routers/'+router+'/preflight',headers=self.login('guest')).status_code,403)
 def test_wireguard_evidence_requires_review_and_is_durable_without_false_acceptance(self):
  owner=self.login('owner');site=self.client.post('/v1/sites',headers=owner,json={'name':'WireGuard Lab'}).json()['id'];router=self.client.post('/v1/routers',headers=owner,json={'site_id':site,'name':'Gateway','model':'RB5009','reported_routeros':'7.20'}).json()['id']
  self.assertEqual(self.client.post('/v1/routers/'+router+'/wireguard-evidence',headers=owner).status_code,409)
  with self.app.state.factory() as s:
   user=s.query(User).filter_by(username='owner').one();plan=RouterPlan(tenant_id=user.tenant_id,router_id=router,hub_id='unused-test-hub',router_public_key='router-key',address='10.0.0.2',snapshot={'hub':{'public_key':'hub-key'},'router':{'interface':'mm-test'}},created=1,reviewed_at=2)
   # The endpoint only reads the plan; avoid a synthetic hub FK in SQLite by disabling checks for this focused API test.
   s.connection().exec_driver_sql('PRAGMA foreign_keys=OFF');s.add(plan);s.commit();plan_id=plan.id
  evidence={'observed_at':3,'evidence_source':'routeros_rest_live_read','router_side_handshake_observed':True,'hub_side_handshake_verified':False,'management_reachability_verified':False,'acceptance_complete':False}
  class Context:
   def __init__(self,*a,**k):pass
   def __enter__(self):return self
   def __exit__(self,*a):pass
  with patch('backend.routeros_preflight.load_routeros_monitoring_credential',return_value=object()),patch('backend.routeros_preflight.RouterOSClient',Context),patch('backend.routeros_preflight.observe_wireguard_peer',return_value=evidence):result=self.client.post('/v1/routers/'+router+'/wireguard-evidence',headers=owner)
  self.assertEqual(result.status_code,200,result.text);self.assertEqual(result.json()['plan_id'],plan_id);self.assertFalse(result.json()['evidence']['acceptance_complete'])
  history=self.client.get('/v1/routers/'+router+'/evidence',headers=owner);self.assertEqual(history.status_code,200);self.assertEqual(history.json()[0]['kind'],'wireguard_router_peer')
  self.assertEqual(self.client.get('/v1/routers/'+router+'/evidence',headers=self.login('other')).status_code,404)

if __name__=='__main__':unittest.main()
