import time,unittest
from sqlalchemy import select
import test_backend
from backend.models import FinancialEvent,RevenueReconciliation

class ReconciliationTests(unittest.TestCase):
 setUp=test_backend.AccountPaymentTests.setUp
 tearDown=test_backend.AccountPaymentTests.tearDown
 login=test_backend.AccountPaymentTests.login
 def seed_events(self):
  with self.app.state.factory() as s:
   tenant=self.users['owner'];u=s.get(__import__('backend.models',fromlist=['User']).User,tenant)
   s.add_all([FinancialEvent(tenant_id=u.tenant_id,source='guest_order',source_id='source-a',kind='collection',amount=1000,currency='MMK',service='internet',package_name='Pass',method='Cash',reference='a',actor_id=u.id,occurred_at=int(time.time()),timestamp_basis='recorded_event'),FinancialEvent(tenant_id=u.tenant_id,source='voucher_sale',source_id='source-b',kind='refund',amount=200,currency='MMK',service='internet',package_name='Pass',method='Cash',reference='b',actor_id=u.id,occurred_at=int(time.time()),timestamp_basis='recorded_event')]);s.commit()
 def test_records_variance_and_replays_exact_key(self):
  self.seed_events();h=self.login('owner');body={'expected_collections':1100,'expected_refunds':200,'notes':'Counter close 1','request_key':'reconcile-test-key-01'};url='/v1/revenue/reconciliations?timezone=Asia%2FYangon'
  r=self.client.post(url,headers=h,json=body);self.assertEqual(r.status_code,201);self.assertEqual(r.json()['actual_collections'],1000);self.assertEqual(r.json()['variance'],100)
  replay=self.client.post(url,headers=h,json=body);self.assertEqual(replay.status_code,200);self.assertTrue(replay.json()['replayed'])
  self.assertEqual(self.client.post(url,headers=h,json=body|{'notes':'changed'}).status_code,409)
  with self.app.state.factory() as s:self.assertEqual(len(list(s.scalars(select(RevenueReconciliation)))),1)
 def test_tenant_isolation_and_validation(self):
  h=self.login('owner');self.assertEqual(self.client.get('/v1/revenue/reconciliations',headers=self.login('guest')).status_code,403);self.assertEqual(self.client.post('/v1/revenue/reconciliations?timezone=Asia%2FYangon',headers=h,json={'expected_collections':-1,'expected_refunds':0,'request_key':'reconcile-test-key-02'}).status_code,422)
