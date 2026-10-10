import time,unittest
from sqlalchemy import select
import test_backend as fixture
import test_vouchers
from backend.models import Audit,Entitlement,Voucher

class VoucherLifecycleTests(unittest.TestCase):
 setUp=fixture.AccountPaymentTests.setUp
 tearDown=fixture.AccountPaymentTests.tearDown
 login=fixture.AccountPaymentTests.login
 package=fixture.AccountPaymentTests.package
 setup_voucher=test_vouchers.VoucherTests.setup_voucher
 redeem=test_vouchers.VoucherTests.redeem
 def post(self,v,action,body=None,header=None):return self.client.post(f"/v1/vouchers/{v['id']}/{action}",headers=header or self.owner,json=body)
 def inventory(self):return {x['id']:x for x in self.client.get('/v1/vouchers',headers=self.owner).json()}
 def actions(self,target):
  with self.app.state.factory() as s:return [a.action for a in s.scalars(select(Audit).where(Audit.target==target))]

 def test_disable_blocks_redemption_and_reenable_restores_it(self):
  v=self.setup_voucher();self.assertEqual(self.post(v,'disable',{'reason':''}).status_code,422)
  r=self.post(v,'disable',{'reason':'Counted missing from dealer stock'});self.assertEqual(r.status_code,200)
  self.assertEqual(r.json()['status'],'disabled');self.assertEqual(r.json()['router_sync'],'disable')
  self.assertEqual(self.redeem(v['code']).status_code,400);self.assertEqual(self.post(v,'disable',{'reason':'again'}).status_code,409)
  r=self.post(v,'enable');self.assertEqual(r.status_code,200);self.assertEqual(r.json()['status'],'unused');self.assertEqual(r.json()['router_sync'],'enable')
  self.assertEqual(self.redeem(v['code']).status_code,200);self.assertEqual(self.post(v,'enable').status_code,409)
  self.assertEqual(self.actions(v['id'])[-3:],['voucher_disabled','voucher_reenabled','voucher_redeemed'])

 def test_activated_voucher_cannot_be_deleted_and_disable_preserves_history(self):
  v=self.setup_voucher();self.assertEqual(self.redeem(v['code']).status_code,200)
  with self.app.state.factory() as s:
   e=s.scalar(select(Entitlement).where(Entitlement.voucher_id==v['id']));e.activated=1000;e.used_bytes=4096;s.commit()
  self.assertEqual(self.post(v,'delete').status_code,409)
  self.assertEqual(self.post(v,'disable',{'reason':'Customer dispute'}).status_code,200)
  diagnosis=self.client.get('/v1/my-access/diagnosis',headers=self.guest).json()['items'][0];self.assertEqual(diagnosis['state'],'access_paused')
  self.assertEqual(self.post(v,'enable').status_code,200)
  with self.app.state.factory() as s:
   e=s.scalar(select(Entitlement).where(Entitlement.voucher_id==v['id']));self.assertEqual((e.activated,e.used_bytes,e.revoked),(1000,4096,False))
   self.assertEqual(s.get(Voucher,v['id']).redeemed_by,self.users['guest'])

 def test_revoked_is_permanent(self):
  v=self.setup_voucher();self.post(v,'disable',{'reason':'Lost sheet'})
  r=self.post(v,'revoke',{'reason':'Confirmed stolen'});self.assertEqual(r.status_code,200);self.assertEqual(r.json()['status'],'revoked');self.assertEqual(r.json()['router_sync'],'revoke')
  for action,body in [('enable',None),('disable',{'reason':'x'}),('delete',None)]:self.assertEqual(self.post(v,action,body).status_code,409)
  self.assertIn(v['id'],self.inventory())

 def test_delete_only_unused_unsold_and_hides_from_inventory(self):
  v=self.setup_voucher()
  sold=self.client.post('/v1/vouchers',headers=self.owner,json={**self.body,'request_key':'lifecycle-sold-000001'}).json()
  sale={'amount':3000,'method':'Cash','reference':'counter-1','evidence':'received','confirmed_received':True}
  self.assertEqual(self.client.post('/v1/vouchers/'+sold['id']+'/sale',headers=self.owner,json=sale).status_code,200)
  self.assertEqual(self.post(sold,'delete').status_code,409)
  r=self.post(v,'delete');self.assertEqual(r.status_code,200);self.assertEqual(r.json()['status'],'deleted');self.assertEqual(r.json()['router_sync'],'delete')
  self.assertNotIn(v['id'],self.inventory());self.assertEqual(self.redeem(v['code']).status_code,400)
  for action,body in [('delete',None),('enable',None),('disable',{'reason':'x'}),('revoke',{'reason':'x'})]:self.assertEqual(self.post(v,action,body).status_code,404)
  with self.app.state.factory() as s:self.assertIsNotNone(s.get(Voucher,v['id']).deleted_at)
  self.assertIn('voucher_deleted',self.actions(v['id']))

 def test_disabled_voucher_cannot_be_sold_and_expired_unused_cannot_be_disabled(self):
  v=self.setup_voucher();self.post(v,'disable',{'reason':'Hold'})
  sale={'amount':3000,'method':'Cash','reference':'counter-2','evidence':'received','confirmed_received':True}
  self.assertEqual(self.client.post('/v1/vouchers/'+v['id']+'/sale',headers=self.owner,json=sale).status_code,409)
  old=self.client.post('/v1/vouchers',headers=self.owner,json={**self.body,'request_key':'lifecycle-expired-0001'}).json()
  with self.app.state.factory() as s:row=s.get(Voucher,old['id']);row.created=int(time.time())-200;row.expires=int(time.time())-1;s.commit()
  self.assertEqual(self.post(old,'disable',{'reason':'late'}).status_code,409)

 def test_other_business_and_guests_cannot_change_lifecycle(self):
  v=self.setup_voucher();other=self.login('other')
  for header in [other,self.guest]:
   for action,body in [('disable',{'reason':'x'}),('enable',None),('delete',None)]:self.assertIn(self.post(v,action,body,header).status_code,[403,404])
  self.assertEqual(self.inventory()[v['id']]['status'],'unused')

if __name__=='__main__':unittest.main()
