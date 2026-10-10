import time
from sqlalchemy import select
from backend.models import Site,ManagedDevice,User
from test_backend import AccountPaymentTests

class ManagedDeviceTests(AccountPaymentTests):
 def test_sme_can_register_switch_and_ap_with_unverified_metadata(self):
  with self.app.state.factory() as s:
   site=Site(tenant_id=self.users_tenant('owner'),name='Main site',timezone='Asia/Yangon',created=int(time.time()));s.add(site);s.commit();site_id=site.id
  owner=self.login('owner')
  switch={'site_id':site_id,'kind':'switch','name':'Core switch','vendor':'Example','model':'ES-24','serial_or_mac':'SN-1','location':'Rack 1','firmware':'1.0'}
  ap={**switch,'kind':'access_point','name':'AP-01','model':'AP-01','location':'Lobby'}
  self.assertEqual(self.client.post('/v1/site-devices',headers=owner,json=switch).status_code,201)
  self.assertEqual(self.client.post('/v1/site-devices',headers=owner,json=ap).status_code,201)
  rows=self.client.get('/v1/site-devices',headers=owner).json();self.assertEqual({r['kind'] for r in rows},{'switch','access_point'})
  self.assertTrue(all(r['connection_state']=='unverified' for r in rows));self.assertTrue(all(r['metadata_source']=='owner_reported' for r in rows))
  with self.app.state.factory() as s:self.assertEqual(s.scalar(select(ManagedDevice).where(ManagedDevice.name=='Core switch')).model,'ES-24')
  self.assertEqual(self.client.get('/v1/site-devices',headers=self.login('guest')).status_code,403)

 def test_default_site_limit_allows_five_aps_and_rejects_sixth(self):
  with self.app.state.factory() as s:
   site=Site(tenant_id=self.users_tenant('owner'),name='Five AP site',timezone='Asia/Yangon',created=int(time.time()));s.add(site);s.commit();site_id=site.id
  owner=self.login('owner')
  for n in range(1,6):
   body={'site_id':site_id,'kind':'access_point','name':f'AP-{n}','vendor':'Example','model':'AP','location':'Room'}
   self.assertEqual(self.client.post('/v1/site-devices',headers=owner,json=body).status_code,201)
  body={'site_id':site_id,'kind':'access_point','name':'AP-6','vendor':'Example','model':'AP','location':'Room'}
  self.assertEqual(self.client.post('/v1/site-devices',headers=owner,json=body).status_code,409)

 def users_tenant(self,name):
  with self.app.state.factory() as s:return s.get(User,self.users[name]).tenant_id
