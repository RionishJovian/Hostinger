import hashlib,re,time,unittest
import test_backend as fixture
import test_vouchers
from backend.models import Voucher
from backend.voucher_codes import SUFFIX_ALPHABET

class VoucherCodeRuleTests(unittest.TestCase):
 setUp=fixture.AccountPaymentTests.setUp
 tearDown=fixture.AccountPaymentTests.tearDown
 login=fixture.AccountPaymentTests.login
 package=fixture.AccountPaymentTests.package
 setup_voucher=test_vouchers.VoucherTests.setup_voucher
 redeem=test_vouchers.VoucherTests.redeem
 def issue(self,key,**extra):return self.client.post('/v1/vouchers',headers=self.owner,json={'package_id':self.pkg,'expires_days':30,'request_key':'code-rule-test-'+key,**extra})
 def vip_package(self,owner):
  r=self.client.post('/v1/packages',headers=owner,json={'name':'VIP','service':'internet','mode':'time','price':9000,'hours':24,'vip':True});self.assertEqual(r.status_code,201);self.assertTrue(r.json()['vip']);return r.json()['id']

 def test_default_code_is_six_unambiguous_characters_with_short_hint(self):
  v=self.setup_voucher();self.assertRegex(v['code'],'^[%s]{6}$'%SUFFIX_ALPHABET);self.assertFalse(set('O0I1')&set(v['code']))
  self.assertEqual(v['code_format'],'standard');self.assertIsNone(v['code_prefix']);self.assertEqual(v['code_hint'],v['code'][-2:])
  with self.app.state.factory() as s:stored=s.get(Voucher,v['id']);self.assertNotEqual(stored.code_hash,hashlib.sha256(v['code'].encode()).hexdigest())
  spaced=' '.join(v['code'].lower());self.assertEqual(self.redeem(spaced).status_code,200)

 def test_prefix_is_normalized_and_matching_ignores_case_and_hyphens(self):
  self.setup_voucher();v=self.issue('prefix-0001',prefix='cafe').json()
  self.assertRegex(v['code'],'^CAFE-[%s]{6}$'%SUFFIX_ALPHABET);self.assertEqual(v['code_prefix'],'CAFE');self.assertEqual(v['code_format'],'prefixed')
  self.assertEqual(self.redeem(v['code'].replace('-','').lower()).status_code,200)
  for bad in ['TOOLONGPREFIX','CA FE!']:self.assertEqual(self.issue('prefix-bad-'+str(len(bad)),prefix=bad).status_code,422)
  self.assertEqual(self.issue('prefix-0001',prefix='SHOP').status_code,409)

 def test_custom_code_only_for_vip_packages_and_unique_within_business(self):
  self.setup_voucher();self.assertEqual(self.issue('custom-0001',custom_code='WELCOME-2026').status_code,422)
  vip=self.vip_package(self.owner);body=lambda key,code:{'package_id':vip,'expires_days':30,'request_key':'code-rule-test-'+key,'custom_code':code}
  r=self.client.post('/v1/vouchers',headers=self.owner,json=body('custom-0002','welcome-2026'));self.assertEqual(r.status_code,201)
  self.assertEqual(r.json()['code'],'WELCOME2026');self.assertEqual(r.json()['code_format'],'custom')
  self.assertEqual(self.client.post('/v1/vouchers',headers=self.owner,json=body('custom-0003','Welcome 2026')).status_code,409)
  self.assertEqual(self.client.post('/v1/vouchers',headers=self.owner,json=body('custom-0004','SHORT')).status_code,422)
  self.assertEqual(self.client.post('/v1/vouchers',headers=self.owner,json={**body('custom-0005','PREFIXED1'),'prefix':'VIP'}).status_code,422)
  other=self.login('other');other_vip=self.vip_package(other)
  same=self.client.post('/v1/vouchers',headers=other,json={**body('custom-0006','WELCOME2026'),'package_id':other_vip});self.assertEqual(same.status_code,201)
  self.assertEqual(self.redeem('welcome2026').status_code,200)

 def test_codes_issued_before_the_rule_still_redeem(self):
  v=self.setup_voucher();legacy='ABCDEFGHIJKLMNOPQRSTUVWXYZ'[:22]+'2345'
  with self.app.state.factory() as s:
   row=s.get(Voucher,v['id']);row.code_hash=hashlib.sha256(legacy.encode()).hexdigest();row.code_format='legacy';row.code_hint=legacy[-4:];s.commit()
  self.assertEqual(self.redeem('-'.join(legacy[i:i+5] for i in range(0,26,5)).lower()).status_code,200)

 def test_batch_codes_share_prefix_and_are_distinct(self):
  self.setup_voucher()
  r=self.client.post('/v1/vouchers/batch',headers=self.owner,json={'package_id':self.pkg,'expires_days':30,'request_key':'code-rule-batch-0001','count':40,'prefix':'Hotel'})
  self.assertEqual(r.status_code,201);codes=[x['code'] for x in r.json()['items']]
  self.assertEqual(len(set(codes)),40);self.assertTrue(all(re.fullmatch('HOTEL-[%s]{6}'%SUFFIX_ALPHABET,c) for c in codes))
  self.assertEqual(self.client.post('/v1/vouchers/batch',headers=self.owner,json={'package_id':self.pkg,'expires_days':30,'request_key':'code-rule-batch-0001','count':40,'prefix':'OTHER'}).status_code,409)
  self.assertEqual(self.client.post('/v1/vouchers/batch',headers=self.owner,json={'package_id':self.pkg,'expires_days':30,'request_key':'code-rule-batch-0002','count':2,'custom_code':'NOTALLOWED'}).status_code,422)

 def test_offline_event_matches_new_codes_and_replays(self):
  v=self.setup_voucher();site=self.client.post('/v1/sites',headers=self.owner,json={'name':'Code rule site','timezone':'Asia/Yangon'})
  self.assertEqual(site.status_code,201,site.text)
  body={'site_id':site.json()['id'],'event_key':'offline-code-rule-0001','code':v['code'].lower(),'local_time':int(time.time()),'device_id':'router-a'}
  first=self.client.post('/v1/vouchers/offline-events',headers=self.owner,json=body);self.assertEqual(first.status_code,201,first.text);self.assertEqual(first.json()['voucher_id'],v['id'])
  self.assertEqual(self.client.post('/v1/vouchers/offline-events',headers=self.owner,json=body).status_code,200)

if __name__=='__main__':unittest.main()
