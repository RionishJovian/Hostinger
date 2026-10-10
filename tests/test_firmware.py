import time
from test_backend import AccountPaymentTests
from backend.models import Site

class FirmwareTests(AccountPaymentTests):
 def test_firmware_plan_is_staged_and_adapter_pending(self):
  with self.app.state.factory() as s:
   site=Site(tenant_id=self.users_tenant('owner'),name='Firmware site',timezone='Asia/Yangon',created=int(time.time()));s.add(site);s.commit();site_id=site.id
  owner=self.login('owner');now=int(time.time());body={'site_id':site_id,'device_id':'device-1','current_version':'1.0','target_version':'1.1','minimum_safe_version':'0.9','window_start':now+3600,'window_end':now+7200,'notes':'Staged test'}
  result=self.client.post('/v1/firmware-plans',headers=owner,json=body);self.assertEqual(result.status_code,201);self.assertEqual(result.json()['status'],'scheduled');self.assertEqual(result.json()['execution_state'],'adapter_pending')
  self.assertEqual(self.client.get('/v1/firmware-plans',headers=self.login('guest')).status_code,403)
 def test_firmware_plan_rejects_same_version(self):
  with self.app.state.factory() as s:
   site=Site(tenant_id=self.users_tenant('owner'),name='Same firmware',timezone='Asia/Yangon',created=int(time.time()));s.add(site);s.commit();site_id=site.id
  owner=self.login('owner');now=int(time.time());body={'site_id':site_id,'device_id':'device-1','current_version':'1.0','target_version':'1.0','minimum_safe_version':'0.9','window_start':now+1,'window_end':now+2}
  self.assertEqual(self.client.post('/v1/firmware-plans',headers=owner,json=body).status_code,422)
 def users_tenant(self,name):
  from backend.models import User
  with self.app.state.factory() as s:return s.get(User,self.users[name]).tenant_id
