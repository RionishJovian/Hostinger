import unittest
import test_backend as fixture
from sqlalchemy import select
from backend.models import Site,RouterDevice
class SiteTests(unittest.TestCase):
 setUp=fixture.AccountPaymentTests.setUp
 tearDown=fixture.AccountPaymentTests.tearDown
 login=fixture.AccountPaymentTests.login
 package=fixture.AccountPaymentTests.package
 def site(self,owner,name):
  response=self.client.post('/v1/sites',headers=owner,json={'name':name,'timezone':'Asia/Yangon'});self.assertEqual(response.status_code,201);return response.json()['id']
 def publish(self,owner,site,recipient):
  cfg=self.client.get('/v1/sites/'+site+'/portal',headers=owner).json()['draft'];cfg.update(direct_purchase=True,voucher_login=True,payment_destination=recipient,payment_instructions='Test receipt only',payment_methods=['Cash'])
  self.assertEqual(self.client.post('/v1/sites/'+site+'/portal/draft',headers=owner,json={'expected_revision':0,'settings':cfg}).status_code,200)
  self.assertEqual(self.client.post('/v1/sites/'+site+'/portal/publish',headers=owner,json={'expected_revision':1}).status_code,200)
 def test_registry_is_scoped_and_cannot_claim_live_state(self):
  owner=self.login('owner');other=self.login('other');guest=self.login('guest');platform=self.login('platform');site=self.site(owner,'Main branch')
  self.assertEqual(self.client.post('/v1/sites',headers=guest,json={'name':'Bad'}).status_code,403);self.assertEqual(self.client.post('/v1/sites',headers=owner,json={'name':'Main branch'}).status_code,409)
  body={'site_id':site,'name':'Gateway','model':'hAP ax3','reported_routeros':'owner reported'}
  self.assertEqual(self.client.post('/v1/routers',headers=other,json=body).status_code,404)
  self.assertEqual(self.client.post('/v1/routers',headers=owner,json={**body,'connection_state':'online'}).status_code,422)
  response=self.client.post('/v1/routers',headers=owner,json=body);self.assertEqual(response.status_code,201);self.assertEqual(response.json()['connection_state'],'unverified');self.assertFalse(response.json()['connection_verified'])
  self.assertEqual(self.client.get('/v1/routers',headers=other).json(),[]);self.assertEqual(self.client.get('/v1/routers',headers=guest).status_code,403)
  fleet=self.client.get('/v1/routers',headers=platform).json();self.assertEqual(len(fleet),1);self.assertIsNone(fleet[0]['last_handshake']);self.assertIsNone(fleet[0]['hub_id']);self.assertFalse(fleet[0]['connection_verified']);self.assertIsNone(fleet[0]['lifecycle_state'])
 def test_router_list_connection_state_follows_plan_freshness(self):
  import base64,time
  from backend.models import RouterPlan,MagicHub,HubAssignment,User
  from sqlalchemy import select
  owner=self.login('owner');platform=self.login('platform');site=self.site(owner,'Cafe')
  router=self.client.post('/v1/routers',headers=owner,json={'site_id':site,'name':'Gateway','model':'hAP ax2','reported_routeros':'7.24'}).json()['id']
  key=lambda n:base64.b64encode(bytes([n])*32).decode()
  hub=self.client.post('/v1/hubs',headers=platform,json={'name':'Hub','endpoint':'hub.example.com','pool':'10.90.1.0/24','public_key':key(1),'interface_name':'wg-mm'}).json()['id']
  with self.app.state.factory() as s:tenant=s.get(User,self.users['owner']).tenant_id
  self.client.post('/v1/hubs/'+hub+'/assignments',headers=platform,json={'tenant_id':tenant})
  plan=self.client.post('/v1/routers/'+router+'/plan',headers=owner,json={'hub_id':hub,'router_public_key':key(2)}).json()['id']
  listed=self.client.get('/v1/routers',headers=owner).json()[0]
  self.assertEqual(listed['hub_id'],hub);self.assertEqual(listed['connection_state'],'unverified');self.assertFalse(listed['connection_verified']);self.assertIsNone(listed['last_handshake'])
  now=int(time.time())
  with self.app.state.factory() as s:
   row=s.get(RouterPlan,plan);row.lifecycle_state='connected';row.handshake_verified_at=now-30;row.management_read_verified_at=now-20;s.commit()
  fresh=self.client.get('/v1/routers',headers=owner).json()[0]
  self.assertEqual(fresh['connection_state'],'verified');self.assertTrue(fresh['connection_verified']);self.assertEqual(fresh['lifecycle_state'],'connected');self.assertEqual(fresh['last_handshake'],now-30);self.assertEqual(fresh['management_read_verified_at'],now-20)
  with self.app.state.factory() as s:
   row=s.get(RouterPlan,plan);row.handshake_verified_at=now-600;row.management_read_verified_at=now-500;s.commit()
  stale=self.client.get('/v1/routers',headers=owner).json()[0]
  self.assertEqual(stale['connection_state'],'unverified');self.assertFalse(stale['connection_verified']);self.assertEqual(stale['lifecycle_state'],'connected');self.assertEqual(stale['last_handshake'],now-600)
 def test_site_portals_are_independent_and_do_not_replace_legacy(self):
  owner=self.login('owner');guest=self.login('guest');other=self.login('other');a=self.site(owner,'A');b=self.site(owner,'B');self.publish(owner,a,'Counter A');self.publish(owner,b,'Counter B')
  def public(site):return self.client.get('/v1/portal/public',headers=guest,params={'site_id':site}).json()
  self.assertEqual(public(a)['settings']['payment_destination'],'Counter A');self.assertEqual(public(b)['settings']['payment_destination'],'Counter B');self.assertNotIn('guest_interface',public(a)['settings'])
  self.assertEqual(self.client.get('/v1/portal/public',headers=guest).json()['settings']['payment_destination'],'Test counter')
  self.assertEqual(self.client.get('/v1/sites/'+a+'/portal',headers=other).status_code,404);self.assertEqual(self.client.get('/v1/sites/'+a+'/portal',headers=guest).status_code,403)
  self.assertEqual(len(self.client.get('/v1/guest-sites',headers=guest).json()),2)
 def test_branch_order_and_entitlement_retain_site(self):
  owner=self.login('owner');guest=self.login('guest');other=self.login('other');a=self.site(owner,'A');foreign=self.site(other,'Other');self.publish(owner,a,'Counter A');p=self.package(owner)
  body={'site_id':a,'package_id':p,'portal_revision':2,'method':'Cash','reference':'branch-receipt','evidence':'Test evidence','request_key':'branch-order-test-001'}
  order=self.client.post('/v1/orders',headers=guest,json=body);self.assertEqual(order.status_code,201);self.assertEqual(order.json()['site_id'],a);self.assertEqual(order.json()['payment_context']['destination'],'Counter A')
  self.assertEqual(self.client.post('/v1/orders',headers=guest,json={**body,'site_id':foreign,'request_key':'foreign-order-test-001'}).status_code,404)
  self.client.post('/v1/orders/'+order.json()['id']+'/decision',headers=owner,json={'decision':'approved'});self.assertEqual(self.client.get('/v1/entitlements',headers=guest).json()[0]['site_id'],a)
  self.assertEqual(self.client.get('/v1/revenue',headers=owner,params={'site_id':a}).json()['net_collections'],3000)
  self.assertEqual(self.client.get('/v1/revenue/ledger',headers=owner).json()['items'][0]['site_id'],a)
 def test_branch_voucher_cannot_redeem_at_another_portal(self):
  owner=self.login('owner');guest=self.login('guest');a=self.site(owner,'A');b=self.site(owner,'B');self.publish(owner,a,'A');self.publish(owner,b,'B');p=self.package(owner)
  voucher=self.client.post('/v1/vouchers',headers=owner,json={'site_id':a,'package_id':p,'expires_days':1,'request_key':'site-voucher-test-001'}).json()
  sale=self.client.post('/v1/vouchers/'+voucher['id']+'/sale',headers=owner,json={'amount':3000,'method':'Cash','reference':'branch-sale','evidence':'Confirmed receipt','confirmed_received':True});self.assertEqual(sale.status_code,200)
  self.assertEqual(self.client.get('/v1/revenue',headers=owner,params={'site_id':a}).json()['net_collections'],3000)
  self.assertEqual(self.client.get('/v1/revenue',headers=owner,params={'site_id':b}).json()['net_collections'],0)
  self.assertEqual(self.client.post('/v1/vouchers/redeem',headers=guest,json={'site_id':b,'code':voucher['code']}).status_code,400)
  right=self.client.post('/v1/vouchers/redeem',headers=guest,json={'site_id':a,'code':voucher['code']});self.assertEqual(right.status_code,200);self.assertEqual(self.client.get('/v1/entitlements',headers=guest).json()[0]['site_id'],a)
 def test_printed_wifi_name_is_an_owner_shop_setting(self):
  owner=self.login('owner');other=self.login('other');guest=self.login('guest');a=self.site(owner,'A')
  created=self.client.post('/v1/sites',headers=owner,json={'name':'B','printed_ssid':'  Golden Cafe B  '});self.assertEqual(created.json()['printed_ssid'],'Golden Cafe B')
  def setting(value,header=owner):return self.client.post('/v1/sites/'+a+'/settings',headers=header,json={'printed_ssid':value})
  self.assertEqual(setting('Golden Cafe WiFi').json()['printed_ssid'],'Golden Cafe WiFi')
  self.assertEqual({x['name']:x['printed_ssid'] for x in self.client.get('/v1/sites',headers=owner).json()},{'A':'Golden Cafe WiFi','B':'Golden Cafe B'})
  self.assertEqual(setting('ရွှေ'*2).status_code,200)
  self.assertEqual(setting('ရွှေ'*3).status_code,422)
  self.assertEqual(setting('x'*33).status_code,422);self.assertEqual(setting('bad\nname').status_code,422)
  self.assertEqual(setting('Hacked',other).status_code,404);self.assertEqual(setting('Hacked',guest).status_code,403)
  self.assertIsNone(setting('   ').json()['printed_ssid'])
  self.assertEqual(len(self.client.get('/v1/audit',headers=owner,params={'action':'site_printed_ssid_updated'}).json()),3)
 def test_bad_timezone_and_unpublished_sites(self):
  owner=self.login('owner');guest=self.login('guest');self.assertEqual(self.client.post('/v1/sites',headers=owner,json={'name':'Invalid','timezone':'not/a-zone'}).status_code,422)
  a=self.site(owner,'Unpublished');self.assertEqual(self.client.get('/v1/guest-sites',headers=guest).json(),[]);self.assertIsNone(self.client.get('/v1/portal/public',headers=guest,params={'site_id':a}).json()['settings'])
