import unittest
import test_vouchers as fixture
from sqlalchemy import select
from backend.models import VoucherSale,Entitlement
class VoucherSaleTests(unittest.TestCase):
 setUp=fixture.VoucherTests.setUp
 tearDown=fixture.VoucherTests.tearDown
 login=fixture.VoucherTests.login
 package=fixture.VoucherTests.package
 setup_voucher=fixture.VoucherTests.setup_voucher
 redeem=fixture.VoucherTests.redeem
 def payment(self,id,headers=None,**overrides):return self.client.post('/v1/vouchers/'+id+'/sale',headers=headers or self.owner,json={'amount':3000,'method':'Cash','reference':'receipt-01','evidence':'Confirmed at test counter','confirmed_received':True,**overrides})
 def refund(self,id,**overrides):return self.client.post('/v1/vouchers/'+id+'/sale/refund',headers=self.owner,json={'reason':'Returned at counter','reference':'refund-01','confirmed_returned':True,**overrides})
 def test_sale_retries_count_once_and_redemption_does_not_add_revenue(self):
  v=self.setup_voucher();self.assertEqual(self.payment(v['id']).status_code,200);self.assertTrue(self.payment(v['id']).json()['replayed'])
  self.redeem(v['code']);r=self.client.get('/v1/revenue',headers=self.owner).json();self.assertEqual(r['net_collections'],3000);self.assertEqual(r['voucher_sales'],1);self.assertEqual(r['approved_orders'],0);self.assertEqual(r['by_service']['combined'],3000)
  self.assertEqual(self.payment(v['id'],reference='different').status_code,409)
  with self.app.state.factory() as s:self.assertEqual(len(list(s.scalars(select(VoucherSale)))),1);self.assertEqual(len(list(s.scalars(select(Entitlement)))),1)
 def test_refund_reduces_collections_and_revokes_redeemed_pass(self):
  v=self.setup_voucher();self.payment(v['id']);self.redeem(v['code']);self.assertEqual(self.refund(v['id']).status_code,200);self.assertTrue(self.refund(v['id']).json()['replayed'])
  r=self.client.get('/v1/revenue',headers=self.owner).json();self.assertEqual(r['net_collections'],0);self.assertEqual(r['gross_collections'],3000);self.assertEqual(r['refunds'],3000);self.assertTrue(self.client.get('/v1/entitlements',headers=self.guest).json()[0]['revoked']);self.assertEqual(self.refund(v['id'],reference='changed').status_code,409)
 def test_permissions_amount_and_receipt_confirmation(self):
  v=self.setup_voucher();other=self.login('other');self.assertEqual(self.payment(v['id'],headers=other).status_code,404);self.assertEqual(self.payment(v['id'],headers=self.guest).status_code,403)
  self.assertEqual(self.payment(v['id'],amount=2000).status_code,422);self.assertEqual(self.payment(v['id'],confirmed_received=False).status_code,422)
  for bad in [{'method':'Cash at counter'},{'method':'KBZPay','reference':''},{'method':'WavePay','reference':' '},{'method':'Other','evidence':''}]:
   self.assertEqual(self.payment(v['id'],**bad).status_code,422,bad)
  self.assertEqual(self.client.get('/v1/revenue',headers=self.owner).json()['net_collections'],0)
 def test_cash_needs_no_reference_and_methods_are_reported(self):
  v=self.setup_voucher();r=self.payment(v['id'],reference='',evidence='');self.assertEqual(r.status_code,200);self.assertEqual((r.json()['method'],r.json()['reference']),('Cash',''))
  w=self.client.post('/v1/vouchers',headers=self.owner,json={**self.body,'request_key':'wavepay-voucher-key'}).json()
  self.assertEqual(self.payment(w['id'],method='WavePay',reference='WP-778812',evidence='').status_code,200)
  methods={m['method']:m['net_collections'] for m in self.client.get('/v1/revenue',headers=self.owner).json()['by_method']}
  self.assertEqual(methods,{'Cash':3000,'WavePay':3000})
 def cancel(self,id,**overrides):return self.client.post('/v1/vouchers/'+id+'/sale/cancel',headers=self.owner,json={'reason':'Sold the wrong card','confirmed':True,**overrides})
 def test_cancel_sale_keeps_history_reverses_revenue_and_allows_resale(self):
  v=self.setup_voucher();first=self.payment(v['id']).json()
  r=self.cancel(v['id']);self.assertEqual(r.status_code,200);self.assertIsNotNone(r.json()['cancelled_at']);self.assertTrue(self.cancel(v['id']).json()['replayed'])
  self.assertEqual(self.cancel(v['id'],reason='Another reason').status_code,404)
  rev=self.client.get('/v1/revenue',headers=self.owner).json()
  self.assertEqual((rev['net_collections'],rev['gross_collections'],rev['refunds'],rev['voucher_sales'],rev['cancelled_sales']),(0,3000,3000,0,1))
  ledger=self.client.get('/v1/revenue/ledger',headers=self.owner).json()['items'];self.assertEqual([e['sale_cancelled'] for e in ledger if e['kind']=='refund'],[True])
  row=[x for x in self.client.get('/v1/vouchers',headers=self.owner).json() if x['id']==v['id']][0]
  self.assertIsNone(row['sale']);self.assertEqual(row['status'],'unused');self.assertEqual([c['id'] for c in row['cancelled_sales']],[first['id']])
  again=self.payment(v['id'],method='KBZPay',reference='KBZ-1001');self.assertEqual(again.status_code,200);self.assertNotEqual(again.json()['id'],first['id'])
  self.assertEqual(self.client.get('/v1/revenue',headers=self.owner).json()['net_collections'],3000)
  with self.app.state.factory() as s:self.assertEqual(len(list(s.scalars(select(VoucherSale)))),2)
  self.assertEqual(len(self.client.get('/v1/audit?action=voucher_sale_cancelled',headers=self.owner).json()),1)
 def test_cancel_sale_refused_after_use_refund_or_without_sale(self):
  v=self.setup_voucher();self.assertEqual(self.cancel(v['id']).status_code,404)
  self.payment(v['id']);self.redeem(v['code'])
  r=self.cancel(v['id']);self.assertEqual(r.status_code,409);self.assertIn('Record a refund',r.json()['detail'])
  self.assertEqual(self.refund(v['id']).status_code,200);self.assertEqual(self.cancel(v['id']).status_code,409)
  self.assertEqual(self.cancel(v['id'],confirmed=False).status_code,422);self.assertEqual(self.cancel(v['id'],reason='').status_code,422)
  self.assertEqual(self.client.post('/v1/vouchers/'+v['id']+'/sale/cancel',headers=self.guest,json={'reason':'x','confirmed':True}).status_code,403)
 def test_revocation_does_not_imply_refund_and_no_sale_for_revoked_code(self):
  v=self.setup_voucher();self.payment(v['id']);self.client.post('/v1/vouchers/'+v['id']+'/revoke',headers=self.owner,json={'reason':'Access stopped'})
  self.assertEqual(self.client.get('/v1/revenue',headers=self.owner).json()['net_collections'],3000);self.assertEqual(self.refund(v['id'],confirmed_returned=False).status_code,422)
  fresh=self.client.post('/v1/vouchers',headers=self.owner,json={**self.body,'request_key':'new-test-voucher-key'}).json();self.client.post('/v1/vouchers/'+fresh['id']+'/revoke',headers=self.owner,json={'reason':'Lost'})
  self.assertEqual(self.payment(fresh['id']).status_code,409)

 def test_concurrent_sale_does_not_duplicate_collections(self):
  from concurrent.futures import ThreadPoolExecutor
  v=self.setup_voucher()
  with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(lambda _:self.payment(v['id']),range(2)))
  self.assertTrue(any(r.status_code==200 for r in results));self.assertTrue(all(r.status_code in [200,409] for r in results))
  with self.app.state.factory() as s:self.assertEqual(len(list(s.scalars(select(VoucherSale)))),1)
  self.assertEqual(self.client.get('/v1/revenue',headers=self.owner).json()['net_collections'],3000)

 def test_daily_voucher_counts_per_shop_and_all_shops(self):
  self.setup_voucher();shops=[self.client.post('/v1/sites',headers=self.owner,json={'name':name,'timezone':'Asia/Yangon'}).json()['id'] for name in ['North','South']]
  issued=[self.client.post('/v1/vouchers',headers=self.owner,json={**self.body,'site_id':site,'request_key':'daily-count-key-'+str(i).zfill(4)}).json() for i,site in enumerate([shops[0],shops[0],shops[0],shops[1]])]
  self.payment(issued[0]['id']);self.payment(issued[1]['id'],method='KBZPay',reference='KBZ-1');self.payment(issued[2]['id']);self.payment(issued[3]['id'],method='WavePay',reference='WP-1')
  self.cancel(issued[1]['id'])
  self.assertEqual(self.refund(issued[2]['id']).status_code,200)
  self.client.post('/v1/vouchers',headers=self.owner,json={**self.body,'site_id':shops[1],'request_key':'daily-count-key-unsold'})
  r=self.client.get('/v1/revenue',headers=self.owner).json()
  self.assertEqual((r['vouchers_sold'],r['vouchers_cancelled'],r['vouchers_refunded']),(4,1,1))
  day=r['by_day'][-1];self.assertEqual((day['vouchers_sold'],day['vouchers_cancelled'],day['vouchers_refunded']),(4,1,1))
  self.assertEqual(day['methods'],{'Cash':3000,'KBZPay':0,'WavePay':3000})
  per_shop={x['site_name']:(x['vouchers_sold'],x['vouchers_cancelled'],x['vouchers_refunded']) for x in r['by_site']}
  self.assertEqual(per_shop,{'North':(3,1,1),'South':(1,0,0)})
  self.assertEqual({m['method']:m['vouchers_sold'] for m in r['by_method']},{'Cash':2,'KBZPay':1,'WavePay':1})
  south=self.client.get('/v1/revenue',headers=self.owner,params={'site_id':shops[1]}).json()
  self.assertEqual((south['vouchers_sold'],south['net_collections']),(1,3000));self.assertEqual(south['by_day'][-1]['methods'],{'WavePay':3000})
 def test_guest_order_and_voucher_sale_are_counted_separately(self):
  v=self.setup_voucher();self.payment(v['id'])
  order=self.client.post('/v1/orders',headers=self.guest,json={'package_id':self.pkg,'portal_revision':3,'method':'Cash','reference':'guest-payment','evidence':'Test guest receipt','request_key':'separate-guest-order-001'}).json()
  self.client.post('/v1/orders/'+order['id']+'/decision',headers=self.owner,json={'decision':'approved'})
  r=self.client.get('/v1/revenue',headers=self.owner).json();self.assertEqual(r['net_collections'],6000);self.assertEqual(r['by_source'],{'guest_orders':3000,'voucher_counter_sales':3000});self.assertEqual(r['by_service']['combined'],6000)
  self.client.post('/v1/orders/'+order['id']+'/refund',headers=self.owner,json={'reason':'Test manual return'})
  r=self.client.get('/v1/revenue',headers=self.owner).json();self.assertEqual(r['net_collections'],3000);self.assertEqual(r['refunds'],3000);self.assertEqual(r['voucher_sales'],1)
