import unittest,uuid
from sqlalchemy import select
import test_backend as fixture
import test_vouchers
from backend.models import Audit,Voucher,DealerLedgerEntry

class DealerTests(unittest.TestCase):
 setUp=fixture.AccountPaymentTests.setUp
 tearDown=fixture.AccountPaymentTests.tearDown
 login=fixture.AccountPaymentTests.login
 package=fixture.AccountPaymentTests.package
 setup_voucher=test_vouchers.VoucherTests.setup_voucher
 redeem=test_vouchers.VoucherTests.redeem
 def stock(self,quantity=30,**fields):
  self.setup_voucher()
  job=self.client.post('/v1/voucher-jobs',headers=self.owner,json={'package_id':self.pkg,'quantity':quantity,'layout':'a4_economy'}|fields).json()
  self.job=job;self.items=self.client.post(f"/v1/voucher-jobs/{job['id']}/generate",headers=self.owner,json={'confirm':True}).json()['items']
  self.code={x['serial_no']:x['code'] for x in self.items};self.vid={x['serial_no']:x['id'] for x in self.items}
 def dealer(self,name='Ko Aung',settlement='credit',header=None,**fields):
  return self.client.post('/v1/dealers',headers=header or self.owner,json={'name':name,'settlement':settlement}|fields)
 def act(self,dealer,action,body,header=None):
  return self.client.post(f"/v1/dealers/{dealer['id']}/{action}",headers=header or self.owner,json=body)
 def key(self):return 'test-'+uuid.uuid4().hex
 def assign(self,dealer,first,last,price,key=None):return self.act(dealer,'assign',{'serial_from':first,'serial_to':last,'unit_price':price,'request_key':key or self.key()})
 def show(self,dealer):return self.client.get(f"/v1/dealers/{dealer['id']}",headers=self.owner).json()
 def actions(self):
  with self.app.state.factory() as s:return [a.action for a in s.scalars(select(Audit))]

 def test_handover_charges_dealer_price_with_prepaid_and_credit_rules(self):
  self.stock();credit=self.dealer(location='Market St',phone='09 123',short_code='ka',credit_limit=50000).json()
  self.assertEqual((credit['short_code'],credit['balance'],credit['unused']),('KA',0,0))
  self.assertEqual(self.dealer('ko aung').status_code,409)
  prepaid=self.dealer('Ma Hla','prepaid').json()
  key=self.key();r=self.assign(credit,1,10,2500,key);self.assertEqual(r.status_code,200);d=r.json()
  self.assertEqual((d['balance'],d['unused'],d['received']),(25000,10,10))
  self.assertEqual(d['movements'][0]['details'],{'serials':'000001–000010','face_value':30000})
  self.assertEqual(d['ledger'][0]['kind'],'charge');self.assertEqual({v['dealer_price'] for v in d['vouchers']},{2500})
  again=self.assign(credit,1,10,2500,key).json();self.assertTrue(again['replayed']);self.assertEqual(again['balance'],25000)
  r=self.assign(credit,5,12,2500);self.assertEqual(r.status_code,409);self.assertIn('already with a dealer: 000005',r.json()['detail'])
  r=self.assign(credit,11,20,3000);self.assertEqual(r.status_code,409);self.assertIn('credit limit',r.json()['detail'])
  r=self.assign(prepaid,11,15,2000);self.assertEqual(r.status_code,409);self.assertIn('at least 10000 MMK',r.json()['detail'])
  self.assertEqual(self.act(prepaid,'payments',{'amount':10000,'method':'KBZPay','reference':'TX-1','request_key':self.key()}).json()['balance'],-10000)
  self.assertEqual(self.assign(prepaid,11,15,2000).json()['balance'],0)
  self.assertEqual(self.assign(prepaid,40,41,2000).status_code,404)
  sale={'amount':3000,'method':'Cash','reference':'counter','evidence':'cash','confirmed_received':True}
  r=self.client.post(f"/v1/vouchers/{self.vid[1]}/sale",headers=self.owner,json=sale);self.assertEqual(r.status_code,409);self.assertIn('with a dealer',r.json()['detail'])
  self.assertEqual(self.client.post(f"/v1/vouchers/{self.vid[1]}/delete",headers=self.owner).status_code,409)
  self.assertEqual(self.client.post(f"/v1/vouchers/{self.vid[30]}/sale",headers=self.owner,json=sale).status_code,200)
  r=self.assign(credit,30,30,2500);self.assertEqual(r.status_code,409);self.assertIn('sold at the counter',r.json()['detail'])
  self.assertEqual(self.client.get('/v1/revenue',headers=self.owner).json()['net_collections'],3000)
  self.assertEqual(self.client.post(f"/v1/vouchers/{self.vid[29]}/sale",headers=self.owner,json=sale).status_code,200)
  self.assertEqual(self.client.post(f"/v1/vouchers/{self.vid[29]}/sale/cancel",headers=self.owner,json={'reason':'Wrong card','confirmed':True}).status_code,200)
  self.assertEqual(self.assign(credit,29,29,500).status_code,200)
  stock={v['serial_no']:v['dealer_id'] for v in self.client.get('/v1/vouchers',headers=self.owner).json() if v['serial_no']}
  self.assertEqual((stock[1],stock[11],stock[20]),(credit['id'],prepaid['id'],None))
  for action in ['dealer_created','dealer_stock_assigned','dealer_payment_recorded']:self.assertIn(action,self.actions())

 def test_returns_reassignment_stock_check_and_activated_ranking(self):
  self.stock();a=self.dealer().json();b=self.dealer('Ma Hla').json()
  self.assign(a,1,10,2500)
  self.assertEqual(self.redeem(self.code[3]).status_code,200)
  r=self.act(a,'return',{'serial_from':3,'serial_to':4,'request_key':self.key()});self.assertEqual(r.status_code,409);self.assertIn('already activated: 000003',r.json()['detail'])
  r=self.act(a,'return',{'serial_from':4,'serial_to':5,'note':'Unsold','request_key':self.key()}).json()
  self.assertEqual((r['balance'],r['returned'],r['movements'][0]['details']['credited']),(20000,2,5000))
  self.assertEqual(self.act(a,'return',{'serial_from':6,'serial_to':7,'to_dealer_id':b['id'],'request_key':self.key()}).status_code,422)
  r=self.act(a,'return',{'serial_from':6,'serial_to':7,'to_dealer_id':b['id'],'unit_price':2000,'request_key':self.key()}).json()
  self.assertEqual((r['balance'],r['movements'][0]['kind']),(15000,'reassign_out'))
  moved=self.show(b);self.assertEqual((moved['balance'],moved['unused'],moved['movements'][0]['kind']),(4000,2,'reassign_in'))
  r=self.act(a,'stock-check',{'counted':3,'missing_serials':[9,10],'request_key':self.key()});self.assertEqual(r.status_code,422)
  self.assertEqual(self.act(a,'stock-check',{'counted':5,'missing_serials':[4],'reason':'lost','request_key':self.key()}).status_code,409)
  r=self.act(a,'stock-check',{'counted':3,'missing_serials':[9,10],'reason':'lost','note':'Shop flooded','disable_missing':True,'request_key':self.key()})
  self.assertEqual(r.status_code,200);out=r.json()
  self.assertEqual(out['check'],{'expected':5,'counted':3,'difference':-2,'missing_serials':[9,10],'disabled':2})
  self.assertEqual((out['balance'],out['unused'],out['holding']),(15000,3,{'unused':3,'redeemed':1,'disabled':2}))
  self.assertIn('balance is unchanged',out['message'])
  with self.app.state.factory() as s:
   v=s.get(Voucher,self.vid[9]);self.assertEqual(v.router_sync,'disable');self.assertIn('Dealer stock check · Lost · Ko Aung: Shop flooded',v.disabled_reason)
  self.assertEqual(self.redeem(self.code[9],self.second).status_code,400)
  r=self.act(a,'stock-check',{'counted':3,'request_key':self.key()});self.assertEqual(r.json()['check']['difference'],0)
  ranking=self.client.get('/v1/dealers',headers=self.owner).json()
  self.assertEqual([(x['name'],x['rank'],x['activated']) for x in ranking],[('Ko Aung',1,1),('Ma Hla',2,0)])
  self.assertEqual(self.client.post(f"/v1/dealers/{a['id']}/archive",headers=self.owner).status_code,409)
  job=self.client.get(f"/v1/voucher-jobs/{self.job['id']}",headers=self.owner).json();self.assertEqual(job['available'],22)
  r=self.act(b,'assign',{'production_job_id':self.job['id'],'unit_price':100,'request_key':self.key()}).json()
  self.assertEqual((r['unused'],r['balance'],r['low_stock']),(24,6200,False))
  self.assertEqual(r['movements'][0]['details']['serials'],'000004–000005, 000011–000030')
  self.assertEqual(self.act(b,'assign',{'production_job_id':self.job['id'],'unit_price':100,'request_key':self.key()}).status_code,409)
  for action in ['dealer_stock_returned','dealer_stock_checked','voucher_disabled']:self.assertIn(action,self.actions())

 def test_payments_corrections_reversals_and_archive(self):
  self.stock(10);d=self.dealer().json()
  paid=self.act(d,'payments',{'amount':5000,'method':'Cash','request_key':self.key()}).json();self.assertEqual(paid['balance'],-5000)
  self.assertEqual(self.act(d,'payments',{'amount':5000,'method':'Bitcoin','request_key':self.key()}).status_code,422)
  self.assertEqual(self.act(d,'adjustments',{'direction':'charge','amount':1000,'reason':'','request_key':self.key()}).status_code,422)
  self.assertEqual(self.act(d,'adjustments',{'direction':'charge','amount':1000,'reason':'Cover sheet','request_key':self.key()}).json()['balance'],-4000)
  payment=paid['ledger'][0]['id'];key=self.key()
  r=self.act(d,f'ledger/{payment}/reverse',{'reason':'Entered twice','request_key':key}).json();self.assertEqual(r['balance'],1000)
  self.assertTrue(next(x for x in r['ledger'] if x['id']==payment)['reversed'])
  self.assertTrue(self.act(d,f'ledger/{payment}/reverse',{'reason':'Entered twice','request_key':key}).json()['replayed'])
  self.assertEqual(self.act(d,f'ledger/{payment}/reverse',{'reason':'again','request_key':self.key()}).status_code,409)
  charge=self.assign(d,1,2,500).json()['ledger'][0];self.assertEqual(charge['kind'],'charge')
  self.assertEqual(self.act(d,f"ledger/{charge['id']}/reverse",{'reason':'x','request_key':self.key()}).status_code,409)
  self.act(d,'return',{'serial_from':1,'serial_to':2,'request_key':self.key()})
  self.assertEqual(self.client.post(f"/v1/dealers/{d['id']}/archive",headers=self.owner).status_code,409)
  self.assertEqual(self.act(d,'adjustments',{'direction':'credit','amount':1000,'reason':'Settled in cash outside','request_key':self.key()}).json()['balance'],0)
  self.assertEqual(self.client.post(f"/v1/dealers/{d['id']}/archive",headers=self.owner).status_code,200)
  self.assertEqual(self.client.get('/v1/dealers',headers=self.owner).json(),[])
  self.assertEqual(len(self.client.get('/v1/dealers?include_archived=true',headers=self.owner).json()),1)
  self.assertEqual(self.act(d,'payments',{'amount':5,'method':'Cash','request_key':self.key()}).status_code,409)
  self.assertEqual(self.dealer().status_code,201)
  with self.app.state.factory() as s:self.assertEqual(len(list(s.scalars(select(DealerLedgerEntry).where(DealerLedgerEntry.dealer_id==d['id'])))),6)

 def test_production_job_dealer_step_hands_over_at_distribution(self):
  self.setup_voucher();d=self.dealer(short_code='KA').json()
  other=self.login('other');foreign=self.dealer('Foreign',header=other).json()
  self.assertEqual(self.client.post('/v1/voucher-jobs',headers=self.owner,json={'package_id':self.pkg,'quantity':12,'dealer_id':foreign['id']}).status_code,404)
  job=self.client.post('/v1/voucher-jobs',headers=self.owner,json={'package_id':self.pkg,'quantity':12,'dealer_id':d['id']}).json()
  self.assertEqual(job['settings']['dealer_id'],d['id'])
  items=self.client.post(f"/v1/voucher-jobs/{job['id']}/generate",headers=self.owner,json={'confirm':True}).json()['items']
  self.client.post(f"/v1/voucher-jobs/{job['id']}/verify",headers=self.owner,json={'sheets':[{'sheet':1,'result':'printed'}]})
  self.assertEqual(self.redeem(items[0]['code']).status_code,200)
  self.assertEqual(self.client.post(f"/v1/voucher-jobs/{job['id']}/distribute",headers=self.owner,json={}).status_code,422)
  r=self.client.post(f"/v1/voucher-jobs/{job['id']}/distribute",headers=self.owner,json={'note':'Market stall','unit_price':2000,'request_key':self.key()})
  self.assertEqual(r.status_code,200);self.assertEqual((r.json()['status'],r.json()['handed_to_dealer']),('distributed',11))
  shown=self.show(d);self.assertEqual((shown['balance'],shown['unused'],shown['movements'][0]['production_job_id']),(22000,11,job['id']))
  self.assertEqual(r.json()['settings']['dealer_id'],d['id'])
  kept=self.client.post('/v1/voucher-jobs',headers=self.owner,json={'package_id':self.pkg,'quantity':3,'dealer_id':d['id']}).json()
  self.client.post(f"/v1/voucher-jobs/{kept['id']}/generate",headers=self.owner,json={'confirm':True})
  self.client.post(f"/v1/voucher-jobs/{kept['id']}/verify",headers=self.owner,json={'sheets':[{'sheet':1,'result':'printed'}]})
  r=self.client.post(f"/v1/voucher-jobs/{kept['id']}/distribute",headers=self.owner,json={'dealer_id':None,'note':'Counter'}).json()
  self.assertEqual((r['status'],r['handed_to_dealer'],r['settings'].get('dealer_id')),('distributed',0,None))
  self.assertEqual(self.show(d)['unused'],11)

 def test_dealers_are_private_to_the_owner_business(self):
  self.stock(5);d=self.dealer().json();other=self.login('other')
  self.assertEqual(self.client.get('/v1/dealers',headers=other).json(),[])
  self.assertEqual(self.client.get(f"/v1/dealers/{d['id']}",headers=other).status_code,404)
  self.assertEqual(self.act(d,'payments',{'amount':5,'method':'Cash','request_key':self.key()},other).status_code,404)
  mine=self.dealer('Mine',header=other).json()
  self.assertEqual(self.client.post(f"/v1/dealers/{mine['id']}/assign",headers=other,json={'serial_from':1,'serial_to':5,'unit_price':1,'request_key':self.key()}).status_code,404)
  self.assertEqual(self.client.post(f"/v1/dealers/{mine['id']}/assign",headers=other,json={'voucher_ids':[self.vid[1]],'unit_price':1,'request_key':self.key()}).status_code,404)
  self.assertEqual(self.client.get('/v1/dealers',headers=self.guest).status_code,403)
  self.assertEqual(self.act(d,'return',{'serial_from':1,'serial_to':2,'to_dealer_id':mine['id'],'unit_price':1,'request_key':self.key()}).status_code,404)

if __name__=='__main__':unittest.main()
