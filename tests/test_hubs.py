import base64,unittest
import os
from concurrent.futures import ThreadPoolExecutor
import test_backend as fixture
from sqlalchemy import select
from backend.models import MagicHub,HubAssignment,RouterPlan,User,Audit,MagicConnectAttempt,MagicConnectEvent,MagicConnectEnrollment
from unittest.mock import patch

def key(n):return base64.b64encode(bytes([n])*32).decode()
class HubTests(unittest.TestCase):
 def setUp(self):
  fixture.AccountPaymentTests.setUp(self)
  self.app.state.magic_connect_pairing_enabled=True  # Explicit synthetic internal test mode.
 tearDown=fixture.AccountPaymentTests.tearDown
 login=fixture.AccountPaymentTests.login
 def setup_hub(self):
  platform=self.login('platform');owner=self.login('owner')
  body={'name':'Magic Hub A','endpoint':'hub.example.com','pool':'10.90.1.0/24','public_key':key(1),'interface_name':'wg-mm'}
  r=self.client.post('/v1/hubs',headers=platform,json=body);self.assertEqual(r.status_code,201,r.text);hub=r.json()['id']
  with self.app.state.factory() as s:tenant=s.get(User,self.users['owner']).tenant_id
  r=self.client.post('/v1/hubs/'+hub+'/assignments',headers=platform,json={'tenant_id':tenant});self.assertEqual(r.status_code,200)
  site=self.client.post('/v1/sites',headers=owner,json={'name':'Cafe'}).json()['id']
  return platform,owner,hub,site,tenant
 def router(self,owner,site,name='Gateway'):
  r=self.client.post('/v1/routers',headers=owner,json={'site_id':site,'name':name,'model':'hAP ax3','reported_routeros':'7.x'});self.assertEqual(r.status_code,201);return r.json()['id']
 def plan(self,owner,hub,router,n=2):return self.client.post('/v1/routers/'+router+'/plan',headers=owner,json={'hub_id':hub,'router_public_key':key(n)})
 def test_approved_pairing_binds_reviewed_plan_and_cannot_be_replayed_elsewhere(self):
  _,owner,hub,site,_=self.setup_hub();router=self.router(owner,site);plan=self.plan(owner,hub,router).json()['id']
  attempt=self.client.post(f'/v1/sites/{site}/magic-connect/attempts',headers=owner,json={'router_name':'Synthetic gateway'}).json()
  route=f"/v1/magic-connect/attempts/{attempt['id']}/enrollment";body={'plan_id':plan,'expected_identity_digest':'a'*64}
  self.assertEqual(self.client.post(route,headers=owner,json=body).status_code,409)
  self.client.post('/v1/magic-connect/claim',json={'code':attempt['manual_code']})
  with self.app.state.factory() as s:
   primary=s.get(User,self.users['owner']);s.add(User(username='sibling-owner',role='sme',tenant_id=primary.tenant_id,password_hash=fixture.HASHER.hash('test-password-only')));s.commit()
  sibling=self.login('sibling-owner')
  self.assertEqual(self.client.post(f"/v1/magic-connect/attempts/{attempt['id']}/approve",headers=sibling,json={'comparison_confirmed':True}).status_code,404)
  self.client.post(f"/v1/magic-connect/attempts/{attempt['id']}/approve",headers=owner,json={'comparison_confirmed':True})
  self.assertEqual(self.client.post(route,headers=owner,json=body).status_code,409)
  self.client.post(f'/v1/router-plans/{plan}/review',headers=owner,json={'confirmed_review':True})
  self.assertEqual(self.client.post(route,headers=self.login('other'),json=body).status_code,404)
  bound=self.client.post(route,headers=owner,json=body)
  self.assertEqual(bound.status_code,201,bound.text);self.assertTrue(bound.json()['pairing_bound']);self.assertFalse(bound.json()['connection_verified']);self.assertFalse(bound.json()['bootstrap_enabled'])
  self.assertEqual(bound.json()['credential_provisioning']['status'],'BLOCKED_HARDWARE_VERIFICATION_REQUIRED');self.assertFalse(bound.json()['credential_provisioning']['credential_delivery_enabled'])
  self.assertTrue(self.client.post(route,headers=owner,json=body).json()['replayed'])
  self.assertEqual(self.client.post(route,headers=owner,json=body|{'expected_identity_digest':'b'*64}).status_code,409)
  other_router=self.router(owner,site,'Second');other_plan=self.plan(owner,hub,other_router,3).json()['id']
  self.client.post(f'/v1/router-plans/{other_plan}/review',headers=owner,json={'confirmed_review':True})
  self.assertEqual(self.client.post(route,headers=owner,json={'plan_id':other_plan}).status_code,409)
  with self.app.state.factory() as s:
   enrollment=s.get(MagicConnectEnrollment,plan);self.assertIsNone(enrollment.consumed_at)
   enrollment.consumed_at=1;s.commit()
  self.assertEqual(self.client.post(f"/v1/magic-connect/attempts/{attempt['id']}/cancel",headers=owner).status_code,409)
  with self.app.state.factory() as s:
   row=s.get(MagicConnectAttempt,attempt['id']);row.expires=row.created+1;s.commit()
  from backend.magic_connect import _expire
  with self.app.state.factory() as s:
   row=s.get(MagicConnectAttempt,attempt['id']);self.assertFalse(_expire(row,s,4102444800));self.assertEqual(row.status,'approved')
 def test_platform_admin_and_assigned_business_visibility(self):
  platform,owner,hub,site,tenant=self.setup_hub();other=self.login('other');guest=self.login('guest')
  for h in [owner,guest,other]:self.assertEqual(self.client.post('/v1/hubs',headers=h,json={'name':'Blocked','endpoint':'b.example.com','pool':'10.90.2.0/24','public_key':key(4)}).status_code,403)
  self.assertEqual(len(self.client.get('/v1/hubs',headers=owner).json()),1);self.assertEqual(self.client.get('/v1/hubs',headers=other).json(),[])
  self.assertEqual(self.client.get('/v1/hubs',headers=guest).status_code,403);self.assertEqual(self.client.get('/v1/hub-assignments',headers=owner).status_code,403)
  again=self.client.post('/v1/hubs/'+hub+'/assignments',headers=platform,json={'tenant_id':tenant});self.assertTrue(again.json()['replayed'])
  self.assertEqual(self.client.post('/v1/hubs/'+hub+'/assignments',headers=platform,json={'tenant_id':'missing'}).status_code,404)
  foreignsite=self.client.post('/v1/sites',headers=other,json={'name':'Other'}).json()['id'];foreignrouter=self.router(other,foreignsite)
  self.assertEqual(self.plan(other,hub,foreignrouter).status_code,404)
  self.assertEqual(self.plan(owner,hub,foreignrouter).status_code,404)
 def test_plan_retries_review_and_no_fabricated_connectivity(self):
  platform,owner,hub,site,tenant=self.setup_hub();router=self.router(owner,site);first=self.plan(owner,hub,router);self.assertEqual(first.status_code,201,first.text);p=first.json()
  self.assertEqual(p['address'],'10.90.1.2');self.assertEqual(p['state'],'awaiting_review');self.assertEqual(p['snapshot']['router']['peer_allowed_addresses'],['10.90.1.1/32']);self.assertFalse(p['snapshot']['guest_traffic_via_hub']);self.assertNotIn('private_key',p['snapshot']['router'])
  scope=p['snapshot']['bootstrap_scope'];self.assertEqual(scope['status'],'proposal_only_not_executable');self.assertIn('Create one new MikroMagic WireGuard interface using a private key generated locally by RouterOS',scope['allowed_router_changes']);self.assertIn('HotSpot, captive portal, vouchers or customer authentication',scope['explicitly_excluded']);self.assertIn('Resolve D1 secure Monitoring and Safe Change identity provisioning on a supported physical device',scope['requires_before_any_execution']);self.assertEqual(p['snapshot']['dispatch'],'not_implemented')
  self.assertEqual(self.plan(owner,hub,router).json()['id'],p['id']);self.assertEqual(self.plan(owner,hub,router,3).status_code,409)
  for role in ['guest','other','platform']:
   self.assertIn(self.client.post('/v1/router-plans/'+p['id']+'/review',headers=self.login(role),json={'confirmed_review':True}).status_code,[403,404])
  self.assertEqual(self.client.post('/v1/router-plans/'+p['id']+'/review',headers=owner,json={'confirmed_review':False}).status_code,422)
  reviewed_response=self.client.post('/v1/router-plans/'+p['id']+'/review',headers=owner,json={'confirmed_review':True})
  self.assertEqual(reviewed_response.status_code,200,reviewed_response.text);reviewed=reviewed_response.json();self.assertEqual(reviewed['state'],'awaiting_bootstrap');self.assertEqual(reviewed['connection_state'],'unverified');self.assertIsNone(reviewed['last_handshake']);self.assertEqual(reviewed['review_stage'],'initial_bootstrap_authorization');self.assertFalse(reviewed['remote_device_verified']);self.assertTrue(reviewed['post_connection_preflight_required'])
  self.assertTrue(self.client.post('/v1/router-plans/'+p['id']+'/review',headers=owner,json={'confirmed_review':True}).json()['replayed'])
  self.assertEqual(self.client.get('/v1/router-plans',headers=self.login('other')).json(),[]);self.assertEqual(self.client.get('/v1/router-plans',headers=self.login('guest')).status_code,403)
  self.assertEqual(len(self.client.get('/v1/router-plans',headers=platform).json()),1)
  fleet=self.client.get('/v1/routers',headers=owner).json()[0];self.assertEqual(fleet['hub_id'],hub);self.assertEqual(fleet['connection_state'],'unverified');self.assertIsNone(fleet['last_handshake'])
  with self.app.state.factory() as s:self.assertEqual(s.get(MagicHub,hub).next_host,3);self.assertEqual(len(list(s.scalars(select(Audit).where(Audit.action=='router_plan_reviewed')))),1)
 def test_validation_duplicates_and_secret_fields(self):
  platform=self.login('platform');body={'name':'Valid','endpoint':'hub.example.com','pool':'10.90.1.0/24','public_key':key(1),'interface_name':'wg-mm'}
  for changed in [{'endpoint':'https://hub.example.com/path'},{'endpoint':'127.0.0.1'},{'endpoint':'10.0.0.1'},{'endpoint':'hub.local'},{'pool':'10.90.1.0/25'},{'pool':'10.90.1.1/24'},{'pool':'8.8.8.0/24'},{'port':0},{'public_key':key(0)},{'public_key':'invalid'},{'private_key':key(5)},{'operational_state':'online'},{'interface_name':'wg; arbitrary'}]:
   r=self.client.post('/v1/hubs',headers=platform,json=body|changed);self.assertEqual(r.status_code,422,r.text)
  created=self.client.post('/v1/hubs',headers=platform,json=body);self.assertEqual(created.status_code,201);self.assertEqual(created.json()['interface_name'],'wg-mm')
  self.assertEqual(self.client.post('/v1/hubs',headers=platform,json=body|{'name':'Another','endpoint':'another.example.com','public_key':key(4)}).status_code,409)
 def test_atomic_allocation_and_public_key_uniqueness(self):
  platform,owner,hub,site,tenant=self.setup_hub();a=self.router(owner,site,'A');b=self.router(owner,site,'B')
  with ThreadPoolExecutor(2) as pool:results=list(pool.map(lambda args:self.plan(owner,hub,*args),[(a,2),(b,3)]))
  self.assertEqual([r.status_code for r in results],[201,201]);self.assertEqual({r.json()['address'] for r in results},{'10.90.1.2','10.90.1.3'})
  c=self.router(owner,site,'C');self.assertEqual(self.plan(owner,hub,c,2).status_code,409)
  with self.app.state.factory() as s:self.assertEqual(s.get(MagicHub,hub).next_host,4)
  self.assertEqual(self.plan(owner,hub,c,1).status_code,422)
 def test_exhaustion_and_portal_overlap(self):
  platform,owner,hub,site,tenant=self.setup_hub();a=self.router(owner,site)
  cfg=self.client.get('/v1/sites/'+site+'/portal',headers=owner).json()['draft'];cfg['guest_subnet']='10.90.1.0/24'
  self.assertEqual(self.client.post('/v1/sites/'+site+'/portal/draft',headers=owner,json={'expected_revision':0,'settings':cfg}).status_code,200)
  self.assertEqual(self.plan(owner,hub,a).status_code,409)
  cfg['guest_subnet']='192.168.50.0/24';self.client.post('/v1/sites/'+site+'/portal/draft',headers=owner,json={'expected_revision':1,'settings':cfg})
  with self.app.state.factory() as s:h=s.get(MagicHub,hub);h.next_host=254;s.commit()
  self.assertEqual(self.plan(owner,hub,a).json()['address'],'10.90.1.254')
  b=self.router(owner,site,'Second');self.assertEqual(self.plan(owner,hub,b,3).status_code,409)
  self.assertEqual(self.client.get('/v1/hubs',headers=owner).json()[0]['remaining_addresses'],0)
 def test_concurrent_same_plan_reuses_allocation(self):
  platform,owner,hub,site,tenant=self.setup_hub();router=self.router(owner,site)
  with ThreadPoolExecutor(2) as pool:results=list(pool.map(lambda _:self.plan(owner,hub,router),range(2)))
  self.assertEqual([r.status_code for r in results],[201,201]);self.assertEqual(len({r.json()['id'] for r in results}),1)
  with self.app.state.factory() as s:self.assertEqual(s.get(MagicHub,hub).next_host,3)

 def test_magic_connect_requires_owner_approval_and_is_single_use(self):
  _,owner,_,site,tenant=self.setup_hub();other=self.login('other')
  created=self.client.post(f'/v1/sites/{site}/magic-connect/attempts',headers=owner,json={'router_name':'Front desk'})
  self.assertEqual(created.status_code,201,created.text);item=created.json();self.assertEqual(item['status'],'pending');self.assertTrue(item['single_use']);self.assertEqual(item['qr_encoding'],'opaque_code_text')
  self.assertEqual(len(item['manual_code'].replace('-','')),32)
  with self.app.state.factory() as s:
   row=s.get(MagicConnectAttempt,item['id']);self.assertNotIn(item['manual_code'].replace('-',''),row.code_hash);self.assertEqual(row.tenant_id,tenant)
  self.assertEqual(self.client.get(f'/v1/sites/{site}/magic-connect/attempts',headers=other).status_code,404)
  self.assertEqual(self.client.post(f'/v1/sites/{site}/magic-connect/attempts',headers=other,json={'router_name':'Front desk'}).status_code,404)
  claimed=self.client.post('/v1/magic-connect/claim',json={'code':item['manual_code']},headers={'X-Forwarded-For':'203.0.113.99'})
  self.assertEqual(claimed.status_code,200,claimed.text);claim=claimed.json();self.assertFalse(claim['business_access']);self.assertFalse(claim['router_commands_available'])
  replay=self.client.post('/v1/magic-connect/claim',json={'code':item['manual_code']});self.assertEqual(replay.status_code,409)
  status=self.client.get('/v1/magic-connect/technician/status',headers={'Authorization':'Bearer '+claim['technician_session']})
  self.assertEqual(status.status_code,200);self.assertEqual(status.json()['setup_access'],'awaiting_owner_approval');self.assertFalse(status.json()['setup_instructions_available'])
  self.assertEqual(self.client.post(f"/v1/magic-connect/attempts/{item['id']}/approve",headers=owner,json={'comparison_confirmed':False}).status_code,422)
  approved=self.client.post(f"/v1/magic-connect/attempts/{item['id']}/approve",headers=owner,json={'comparison_confirmed':True})
  self.assertEqual(approved.status_code,200);self.assertEqual(approved.json()['setup_access'],'blocked_pending_hardware_verification');self.assertFalse(approved.json()['setup_instructions_available']);self.assertEqual(approved.json()['enrollment_state'],'pairing_approved')
  status=self.client.get('/v1/magic-connect/technician/status',headers={'Authorization':'Bearer '+claim['technician_session']})
  self.assertEqual(status.json()['setup_access'],'blocked_pending_hardware_verification');self.assertEqual(status.json()['enrollment_state'],'pairing_approved');self.assertFalse(status.json()['business_data_access']);self.assertFalse(status.json()['router_write_access'])
  with self.app.state.factory() as s:self.assertEqual(len(list(s.scalars(select(MagicConnectEvent).where(MagicConnectEvent.attempt_id==item['id'])))),3)

 def test_hub_host_operations_require_isolated_environment_gate(self):
  _,owner,hub,site,tenant=self.setup_hub();router=self.router(owner,site);plan=self.plan(owner,hub,router,2).json()
  self.client.post('/v1/router-plans/'+plan['id']+'/review',headers=owner,json={'confirmed_review':True})
  with patch.dict(os.environ,{'MIKROMAGIC_ENVIRONMENT':'local-development','MIKROMAGIC_HUB_PEER_WRITES_ENABLED':'true','MIKROMAGIC_HUB_PEER_READS_ENABLED':'true'}):
   result=self.client.post('/v1/router-plans/'+plan['id']+'/hub-peer/provision',headers=owner,json={'confirmed':True,'idempotency_key':'isolated-op-00001'})
   self.assertEqual(result.status_code,503,result.text)
   self.assertEqual(result.json()['detail']['code'],'host_peer_writes_disabled_pending_isolated_test_approval')
   lock=self.client.post('/v1/router-plans/'+plan['id']+'/emergency-lock',headers=owner,json={'confirmed':True,'reason':'Synthetic security test incident'})
   self.assertEqual(lock.status_code,503)
  with self.app.state.factory() as s:
   current=s.get(RouterPlan,plan['id']);self.assertEqual(current.lifecycle_state,'awaiting_bootstrap');self.assertIsNone(current.peer_operation_key)

 def test_public_pairing_gate_blocks_ui_capability_and_api_operations(self):
  _,owner,hub,site,_=self.setup_hub()
  self.assertTrue(self.client.get('/v1/magic-connect/capability').json()['pairing_available'])
  attempt=self.client.post(f'/v1/sites/{site}/magic-connect/attempts',headers=owner,json={'router_name':'Synthetic prior request'}).json()
  self.assertEqual(self.client.post('/v1/magic-connect/claim',json={'code':attempt['manual_code']}).status_code,200)
  self.assertEqual(self.client.post(f"/v1/magic-connect/attempts/{attempt['id']}/approve",headers=owner,json={'comparison_confirmed':True}).status_code,200)
  router=self.router(owner,site)
  plan=self.plan(owner,hub,router).json()['id']
  self.assertEqual(self.client.post(f'/v1/router-plans/{plan}/review',headers=owner,json={'confirmed_review':True}).status_code,200)
  self.app.state.magic_connect_pairing_enabled=False
  capability=self.client.get('/v1/magic-connect/capability').json()
  self.assertFalse(capability['pairing_available'])
  self.assertFalse(capability['router_bootstrap_available'])
  self.assertEqual(self.client.post(f'/v1/sites/{site}/magic-connect/attempts',headers=owner,json={'router_name':'Blocked'}).status_code,503)
  self.assertEqual(self.client.post('/v1/magic-connect/claim',json={'code':attempt['manual_code']}).status_code,503)
  self.assertEqual(self.client.post(f"/v1/magic-connect/attempts/{attempt['id']}/approve",headers=owner,json={'comparison_confirmed':True}).status_code,503)
  self.assertEqual(self.client.post(f"/v1/magic-connect/attempts/{attempt['id']}/enrollment",headers=owner,json={'plan_id':plan}).status_code,503)
  self.assertEqual(self.client.post(f'/v1/router-plans/{plan}/hub-peer/provision',headers=owner,json={'confirmed':True,'idempotency_key':'blocked-public-operation'}).status_code,503)
  self.assertEqual(self.client.post(f"/v1/magic-connect/attempts/{attempt['id']}/cancel",headers=owner).status_code,200)
  self.assertEqual(self.client.get(f'/v1/sites/{site}/magic-connect/attempts',headers=owner).json()[0]['status'],'cancelled')

 def test_pairing_requires_both_explicit_isolated_test_flags(self):
  from backend.app import make_app
  from fastapi.testclient import TestClient
  for environment,flag,available in [('production','true',False),('isolated-magic-connect-test','false',False),('isolated-magic-connect-test','true',True)]:
   with patch.dict(os.environ,{'MIKROMAGIC_ENVIRONMENT':environment,'MIKROMAGIC_MAGIC_CONNECT_TEST_MODE':flag}):
    app=make_app('sqlite:///:memory:',initialize=True)
    with TestClient(app) as client:
     response=client.get('/v1/magic-connect/capability')
     self.assertEqual(response.status_code,200)
     self.assertEqual(response.json()['pairing_available'],available)
     self.assertFalse(response.json()['router_bootstrap_available'])
    app.state.engine.dispose()

 def test_public_pairing_requires_every_dedicated_agent_gate(self):
  from backend.app import make_app
  from fastapi.testclient import TestClient
  cases=[
   ({'MIKROMAGIC_ENVIRONMENT':'hostinger-public-test','MIKROMAGIC_HUB_MODE':'dedicated-agent','MIKROMAGIC_MAGIC_CONNECT_ENABLED':'true'},True),
   ({'MIKROMAGIC_ENVIRONMENT':'hostinger-public-test','MIKROMAGIC_HUB_MODE':'dedicated-agent','MIKROMAGIC_MAGIC_CONNECT_ENABLED':'false'},False),
   ({'MIKROMAGIC_ENVIRONMENT':'hostinger-public-test','MIKROMAGIC_HUB_MODE':'local-host','MIKROMAGIC_MAGIC_CONNECT_ENABLED':'true'},False),
  ]
  for environment,available in cases:
   with patch.dict(os.environ,environment,clear=False):
    app=make_app('sqlite:///:memory:',initialize=True)
    with TestClient(app) as client:self.assertEqual(client.get('/v1/magic-connect/capability').json()['pairing_available'],available)
    app.state.engine.dispose()

 def test_authenticated_pairing_to_synthetic_peer_revocation_flow(self):
  from backend.hub_orchestrator import HubPeerOrchestrator,HostOperationPolicy
  from test_hub_orchestrator import FakeHubAdapter
  _,owner,hub,site,_=self.setup_hub();router=self.router(owner,site)
  plan=self.plan(owner,hub,router).json()['id']
  attempt=self.client.post(f'/v1/sites/{site}/magic-connect/attempts',headers=owner,json={'router_name':'Synthetic router'}).json()
  claimed=self.client.post('/v1/magic-connect/claim',json={'code':attempt['manual_code']})
  self.assertEqual(claimed.status_code,200,claimed.text)
  self.assertEqual(self.client.post(f"/v1/magic-connect/attempts/{attempt['id']}/approve",headers=owner,json={'comparison_confirmed':True}).status_code,200)
  self.assertEqual(self.client.post(f'/v1/router-plans/{plan}/review',headers=owner,json={'confirmed_review':True}).status_code,200)
  bound=self.client.post(f"/v1/magic-connect/attempts/{attempt['id']}/enrollment",headers=owner,json={'plan_id':plan})
  self.assertEqual(bound.status_code,201,bound.text)
  adapter=FakeHubAdapter()
  self.app.state.magic_hub_orchestrator=HubPeerOrchestrator(adapter,HostOperationPolicy('isolated-magic-connect-test',True,True,'wg-mm'))
  provision=self.client.post(f'/v1/router-plans/{plan}/hub-peer/provision',headers=owner,json={'confirmed':True,'idempotency_key':'synthetic-flow-001'})
  self.assertEqual(provision.status_code,200,provision.text)
  self.assertEqual(provision.json()['state'],'awaiting_handshake')
  self.assertTrue(adapter.peer_present)
  self.assertFalse(provision.json()['connection_verified'])
  observed=self.client.post(f'/v1/router-plans/{plan}/hub-peer/observe',headers=owner)
  self.assertEqual(observed.status_code,200,observed.text)
  self.assertEqual(observed.json()['state'],'awaiting_handshake')
  adapter.peer_present=False  # Synthetic VM restart loses the in-kernel peer.
  stale=self.client.post(f'/v1/router-plans/{plan}/hub-peer/provision',headers=owner,json={'confirmed':True,'idempotency_key':'synthetic-flow-001'})
  self.assertEqual(stale.status_code,503,stale.text)
  self.assertEqual(stale.json()['detail']['code'],'hub_peer_missing_or_conflicting_on_replay')
  recovery=self.client.post(f'/v1/router-plans/{plan}/hub-peer/recovery-check',headers=owner,json={'confirmed':True})
  self.assertEqual(recovery.status_code,200,recovery.text)
  self.assertEqual(recovery.json()['recovery_readback'],'peer_absent')
  self.assertTrue(recovery.json()['retry_allowed'])
  restored=self.client.post(f'/v1/router-plans/{plan}/hub-peer/provision',headers=owner,json={'confirmed':True,'idempotency_key':'synthetic-flow-001'})
  self.assertEqual(restored.status_code,200,restored.text)
  self.assertTrue(adapter.peer_present)
  locked=self.client.post(f'/v1/router-plans/{plan}/emergency-lock',headers=owner,json={'confirmed':True,'reason':'Synthetic emergency revocation'})
  self.assertEqual(locked.status_code,200,locked.text)
  self.assertEqual(locked.json()['state'],'management_locked')
  self.assertFalse(adapter.peer_present)
  self.assertFalse(locked.json()['on_router_cleanup_verified'])
  with self.app.state.factory() as s:
   actions={row.action for row in s.scalars(select(Audit))}
   self.assertTrue({'magic_connect_technician_approved','magic_connect_enrollment_bound','hub_peer_provisioned','hub_management_emergency_lock'}<=actions)

 def test_magic_connect_denial_cancellation_and_expiration(self):
  _,owner,_,site,tenant=self.setup_hub()
  def create(name):return self.client.post(f'/v1/sites/{site}/magic-connect/attempts',headers=owner,json={'router_name':name}).json()
  denied=create('Denied');claim=self.client.post('/v1/magic-connect/claim',json={'code':denied['manual_code']}).json()
  self.assertEqual(self.client.post(f"/v1/magic-connect/attempts/{denied['id']}/deny",headers=owner).json()['status'],'denied')
  self.assertEqual(self.client.get('/v1/magic-connect/technician/status',headers={'Authorization':'Bearer '+claim['technician_session']}).status_code,401)
  cancelled=create('Cancelled');self.assertEqual(self.client.post(f"/v1/sites/{site}/magic-connect/attempts",headers=owner,json={'router_name':'Cancelled'}).status_code,409)
  self.assertEqual(self.client.post(f"/v1/magic-connect/attempts/{cancelled['id']}/cancel",headers=owner).json()['router_changes_reverted'],False)
  expired=create('Expired')
  with patch('backend.magic_connect.time.time',return_value=expired['expires']+1):
   self.assertEqual(self.client.post('/v1/magic-connect/claim',json={'code':expired['manual_code']}).status_code,410)
   listed=self.client.get(f'/v1/sites/{site}/magic-connect/attempts',headers=owner).json()
  self.assertEqual(next(x for x in listed if x['id']==expired['id'])['status'],'expired')
  with self.app.state.factory() as s:self.assertEqual(s.get(MagicConnectAttempt,expired['id']).tenant_id,tenant)
