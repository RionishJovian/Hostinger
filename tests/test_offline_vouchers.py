import time
from test_backend import AccountPaymentTests
from backend.models import Site

class OfflineVoucherTests(AccountPaymentTests):
 def test_offline_event_is_idempotent_and_never_grants_access(self):
  with self.app.state.factory() as s:
   site=Site(tenant_id=self.users_tenant('owner'),name='Offline site',timezone='Asia/Yangon',created=int(time.time()));s.add(site);s.commit();site_id=site.id
  owner=self.login('owner')
  package=self.package(owner)
  issued=self.client.post('/v1/vouchers',headers=owner,json={'site_id':site_id,'package_id':package,'expires_days':30,'request_key':'offline-voucher-0001'});self.assertEqual(issued.status_code,201);code=issued.json()['code']
  body={'site_id':site_id,'event_key':'offline-event-000001','code':code,'event_type':'redemption','local_time':int(time.time()),'device_id':'local-controller-1'}
  first=self.client.post('/v1/vouchers/offline-events',headers=owner,json=body);self.assertEqual(first.status_code,201);self.assertFalse(first.json()['access_granted']);self.assertEqual(first.json()['status'],'pending_review')
  replay=self.client.post('/v1/vouchers/offline-events',headers=owner,json=body);self.assertEqual(replay.status_code,200);self.assertTrue(replay.json()['replayed'])
  self.assertEqual(self.client.get('/v1/vouchers/offline-events',headers=owner).status_code,200)
  self.assertEqual(self.client.post('/v1/vouchers/offline-events',headers=self.login('guest'),json=body).status_code,403)

 def test_unknown_offline_voucher_becomes_conflict(self):
  with self.app.state.factory() as s:
   site=Site(tenant_id=self.users_tenant('owner'),name='Conflict site',timezone='Asia/Yangon',created=int(time.time()));s.add(site);s.commit();site_id=site.id
  owner=self.login('owner');body={'site_id':site_id,'event_key':'offline-event-unknown','code':'A234567B234567C234567D2345','event_type':'redemption','local_time':int(time.time()),'device_id':'local-controller-1'}
  result=self.client.post('/v1/vouchers/offline-events',headers=owner,json=body);self.assertEqual(result.status_code,201);self.assertEqual(result.json()['status'],'conflict');self.assertIn('not part',result.json()['reason'])

 def users_tenant(self,name):
  from backend.models import User
  with self.app.state.factory() as s:return s.get(User,self.users[name]).tenant_id
