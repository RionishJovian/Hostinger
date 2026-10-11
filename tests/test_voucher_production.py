import unittest
from sqlalchemy import select
import test_backend as fixture
import test_vouchers
from backend.models import Audit,Voucher

class VoucherProductionTests(unittest.TestCase):
 setUp=fixture.AccountPaymentTests.setUp
 tearDown=fixture.AccountPaymentTests.tearDown
 login=fixture.AccountPaymentTests.login
 package=fixture.AccountPaymentTests.package
 setup_voucher=test_vouchers.VoucherTests.setup_voucher
 redeem=test_vouchers.VoucherTests.redeem
 def draft(self,**fields):
  return self.client.post('/v1/voucher-jobs',headers=self.owner,json={'package_id':self.pkg,'quantity':10,'layout':'a4_economy'}|fields)
 def job(self,job,action,body=None,header=None):return self.client.post(f"/v1/voucher-jobs/{job['id']}/{action}",headers=header or self.owner,json=body)
 def generate(self,job):return self.job(job,'generate',{'confirm':True})
 def actions(self):
  with self.app.state.factory() as s:return [a.action for a in s.scalars(select(Audit))]

 def test_codes_are_created_only_after_confirmation_with_serials_and_sheets(self):
  self.setup_voucher()
  self.assertEqual(self.draft(layout='a4_custom').status_code,422)
  r=self.draft(quantity=130,layout='a4_ultra',prefix='cafe',ssid='Cafe WiFi');self.assertEqual(r.status_code,201);job=r.json()
  self.assertEqual((job['ref'],job['status'],job['plan']),('PJ-0001','draft',{'unit':'sheet','per_sheet':60,'sheets':3,'last_sheet_count':10}))
  self.assertEqual(job['settings']['prefix'],'CAFE');self.assertTrue(job['calibration_required'])
  with self.app.state.factory() as s:self.assertEqual(s.scalar(select(Voucher).where(Voucher.production_job_id==job['id'])),None)
  self.assertEqual(self.job(job,'generate',{'confirm':False}).status_code,422)
  self.assertEqual(self.generate(job).status_code,409)
  self.assertEqual(self.job(job,'calibration').json()['calibration_required'],False)
  r=self.generate(job);self.assertEqual(r.status_code,200);out=r.json();items=out['items']
  self.assertEqual(len(items),130);self.assertEqual(len({x['code'] for x in items}),130)
  self.assertTrue(all(x['code'].startswith('CAFE-') for x in items))
  self.assertEqual([x['serial_no'] for x in items],list(range(1,131)))
  self.assertEqual([items[i]['sheet_no'] for i in (0,59,60,119,120,129)],[1,1,2,2,3,3])
  self.assertEqual((out['job']['serial_start'],out['job']['serial_end'],out['job']['status']),(1,130,'generated'))
  self.assertEqual(set(out['job']['sheets']),{'1','2','3'})
  self.assertEqual(self.redeem(items[5]['code'].lower()).status_code,200)
  again=self.generate(job).json();self.assertTrue(again['replayed']);self.assertTrue(all(x['code'] is None for x in again['items']))
  with self.app.state.factory() as s:self.assertEqual(len(list(s.scalars(select(Voucher).where(Voucher.production_job_id==job['id'])))),130)
  serials={v['serial_no'] for v in self.client.get('/v1/vouchers',headers=self.owner).json()};self.assertIn(130,serials)

 def test_calibration_is_once_per_layout_and_serials_continue(self):
  self.setup_voucher()
  first=self.draft(quantity=80);self.job(first.json(),'calibration');self.generate(first.json())
  second=self.draft(quantity=50).json();self.assertFalse(second['calibration_required'])
  self.assertEqual(self.generate(second).json()['job']['serial_start'],81)
  thermal=self.draft(quantity=60,layout='thermal_80').json();self.assertTrue(thermal['calibration_required']);self.assertEqual(thermal['plan']['unit'],'run')
  single=self.draft(quantity=5,layout='a4_premium').json();self.assertFalse(single['calibration_required'])
  self.assertEqual(self.generate(single).json()['items'][0]['serial_no'],131)

 def test_print_verification_reprint_lost_sheet_and_distribution(self):
  self.setup_voucher()
  job=self.draft(quantity=30,layout='thermal_58').json();self.job(job,'calibration');items=self.generate(job).json()['items']
  self.assertEqual(self.job(job,'distribute',{}).status_code,409)
  r=self.job(job,'verify',{'sheets':[{'sheet':1,'result':'printed'},{'sheet':2,'result':'failed'}]});self.assertEqual(r.json()['status'],'generated')
  self.assertEqual(self.job(job,'verify',{'sheets':[{'sheet':3,'result':'printed'}]}).status_code,422)
  self.assertEqual(self.job(job,'reprint',{'sheets':[1],'reason':'Smudged'}).status_code,409)
  self.assertEqual(self.job(job,'reprint',{'sheets':[2],'reason':''}).status_code,422)
  r=self.job(job,'reprint',{'sheets':[2],'reason':'Paper jam'});self.assertEqual(r.status_code,200);self.assertIn('duplicates',r.json()['warning'])
  self.assertEqual(r.json()['sheets']['2'],{'state':'reprinted','reprints':1,'reprint_reason':'Paper jam'})
  r=self.job(job,'verify',{'sheets':[{'sheet':2,'result':'printed'}]});self.assertEqual(r.json()['status'],'verified');self.assertIsNotNone(r.json()['verified_at'])
  self.assertEqual(self.job(job,'reprint',{'sheets':[2],'reason':'again'}).status_code,409)
  self.assertEqual(self.redeem(items[0]['code']).status_code,200)
  r=self.job(job,'sheets/1/lost',{'reason':'Left on bus'});self.assertEqual(r.status_code,200);self.assertEqual(r.json()['disabled'],24)
  self.assertEqual(self.job(job,'sheets/1/lost',{'reason':'again'}).status_code,409)
  self.assertEqual(self.redeem(items[1]['code'],self.second).status_code,400)
  self.assertEqual(r.json()['counts'],{'redeemed':1,'disabled':24,'unused':5})
  with self.app.state.factory() as s:
   self.assertIsNone(s.get(Voucher,items[0]['id']).disabled_at)
   lost=s.get(Voucher,items[1]['id']);self.assertEqual(lost.router_sync,'disable');self.assertIn('Lost sheet 1 of PJ-0001',lost.disabled_reason)
   self.assertIsNone(s.get(Voucher,items[25]['id']).disabled_at)
  r=self.job(job,'distribute',{'note':'Front counter'});self.assertEqual((r.json()['status'],r.json()['distributed_note']),('distributed','Front counter'))
  for action in ['voucher_job_drafted','voucher_job_calibrated','voucher_job_generated','voucher_job_reprinted','voucher_job_verified','voucher_job_sheet_lost','voucher_job_distributed']:self.assertIn(action,self.actions())

 def test_only_drafts_can_be_cancelled(self):
  self.setup_voucher();job=self.draft().json()
  self.assertEqual(self.job(job,'cancel').json()['status'],'cancelled');self.assertEqual(self.generate(job).status_code,409)
  done=self.draft().json();self.generate(done)
  self.assertEqual(self.job(done,'cancel').status_code,409);self.assertEqual(self.job(done,'calibration').status_code,409)

 def test_templates_are_saved_per_business_and_archived(self):
  self.setup_voucher();settings={'package_id':self.pkg,'quantity':60,'layout':'a4_ultra','prefix':'nbr','expires_days':60}
  r=self.client.post('/v1/voucher-templates',headers=self.owner,json={'name':'Neighborhood sheet','settings':settings});self.assertEqual(r.status_code,201)
  self.assertEqual(r.json()['settings']['prefix'],'NBR')
  self.assertEqual(self.client.post('/v1/voucher-templates',headers=self.owner,json={'name':'neighborhood SHEET','settings':settings}).status_code,409)
  other=self.login('other');self.assertEqual(self.client.get('/v1/voucher-templates',headers=other).json(),[])
  self.assertEqual(self.client.post('/v1/voucher-templates',headers=other,json={'name':'Steal','settings':settings}).status_code,404)
  self.assertEqual(self.client.post(f"/v1/voucher-templates/{r.json()['id']}/archive",headers=other).status_code,404)
  self.assertEqual(self.client.post(f"/v1/voucher-templates/{r.json()['id']}/archive",headers=self.owner).status_code,200)
  self.assertEqual(self.client.get('/v1/voucher-templates',headers=self.owner).json(),[])

 def test_batch_qr_is_a_print_setting_on_by_default(self):
  self.setup_voucher()
  self.assertTrue(self.draft().json()['settings']['batch_qr'])
  off=self.draft(batch_qr=False).json();self.assertFalse(off['settings']['batch_qr'])
  self.assertFalse(self.client.get(f"/v1/voucher-jobs/{off['id']}",headers=self.owner).json()['settings']['batch_qr'])
  t=self.client.post('/v1/voucher-templates',headers=self.owner,json={'name':'No QR sheet','settings':{'package_id':self.pkg,'quantity':60,'layout':'a4_ultra','batch_qr':False}})
  self.assertFalse(t.json()['settings']['batch_qr'])
  self.assertEqual(self.draft(batch_qr='yes please').status_code,422)
  other=self.login('other');self.assertEqual(self.client.get(f"/v1/voucher-jobs/{off['id']}",headers=other).status_code,404)

 def test_other_business_and_guests_cannot_use_production_jobs(self):
  self.setup_voucher();job=self.draft().json();other=self.login('other')
  self.assertEqual(self.client.post('/v1/voucher-jobs',headers=other,json={'package_id':self.pkg,'quantity':5}).status_code,404)
  for header in [other,self.guest]:
   self.assertIn(self.client.get('/v1/voucher-jobs/'+job['id'],headers=header).status_code,[403,404])
   self.assertIn(self.job(job,'generate',{'confirm':True},header).status_code,[403,404])
  self.assertEqual(self.client.get('/v1/voucher-jobs',headers=other).json(),[])
  self.assertEqual(self.client.get('/v1/voucher-jobs/'+job['id'],headers=self.owner).json()['status'],'draft')

if __name__=='__main__':unittest.main()
