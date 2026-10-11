import time,unittest
import test_backend as fixture
from sqlalchemy import select
from backend.models import Entitlement,Audit

class MediaPassRuleTests(unittest.TestCase):
 setUp=fixture.AccountPaymentTests.setUp
 tearDown=fixture.AccountPaymentTests.tearDown
 login=fixture.AccountPaymentTests.login
 def title(self,h,name,genre,publish=True):
  t=self.client.post('/v1/media/titles',headers=h,json={'name':name,'description':'Test only','genre':genre,'runtime_minutes':90});self.assertEqual(t.status_code,201,t.text);t=t.json()
  return self.state(h,t,'publish') if publish else t
 def state(self,h,t,operation):r=self.client.post('/v1/media/titles/'+t['id']+'/state',headers=h,json={'expected_revision':t['revision'],'operation':operation});self.assertEqual(r.status_code,200,r.text);return r.json()
 def voucher_login(self,h):
  state=self.client.get('/v1/portal',headers=h).json()
  self.client.post('/v1/portal/draft',headers=h,json={'expected_revision':state['revision'],'settings':{**state['draft'],'voucher_login':True}})
  self.assertEqual(self.client.post('/v1/portal/publish',headers=h,json={'expected_revision':state['revision']+1}).status_code,200)
 def titles(self,h):return sorted(t['name'] for t in self.client.get('/v1/media/titles',headers=h).json())

 def test_category_pass_is_validated_against_the_catalogue(self):
  owner=self.login('owner');guest=self.login('guest');self.title(owner,'Comedy one','Comedy');draft=self.title(owner,'Drama draft','Drama',publish=False)
  base={'name':'Comedy pass','service':'media','mode':'category','price':1500,'hours':24}
  for bad in [{'categories':[]},{'categories':['Comedy','comedy']},{'mode':'library','categories':['Comedy']},{'service':'internet','mode':'both','gb':1,'categories':['Comedy']}]:
   self.assertEqual(self.client.post('/v1/packages',headers=owner,json=base|bad).status_code,422,bad)
  self.assertEqual(self.client.post('/v1/packages',headers=owner,json=base|{'categories':['Horror']}).status_code,404)
  p=self.client.post('/v1/packages',headers=owner,json=base|{'categories':['comedy']});self.assertEqual(p.status_code,201,p.text)
  d=self.client.post('/v1/packages',headers=owner,json=base|{'name':'Drama pass','categories':['Drama']});self.assertEqual(d.status_code,201,d.text)
  offered=[x['name'] for x in self.client.get('/v1/packages',headers=guest).json()];self.assertIn('Comedy pass',offered);self.assertNotIn('Drama pass',offered)
  self.state(owner,draft,'publish');self.assertIn('Drama pass',[x['name'] for x in self.client.get('/v1/packages',headers=guest).json()])

 def test_voucher_pass_starts_at_first_redemption_with_one_device_rule(self):
  owner=self.login('owner');guest=self.login('guest');self.title(owner,'Comedy one','Comedy');self.voucher_login(owner)
  p=self.client.post('/v1/packages',headers=owner,json={'name':'Comedy day','service':'media','mode':'category','categories':['Comedy'],'price':1500,'hours':24}).json()
  v=self.client.post('/v1/vouchers',headers=owner,json={'package_id':p['id'],'expires_days':7,'request_key':'media-category-voucher-01'});self.assertEqual(v.status_code,201,v.text);v=v.json()
  before=int(time.time());r=self.client.post('/v1/vouchers/redeem',headers=guest,json={'code':v['code']});self.assertEqual(r.status_code,200,r.text)
  activated=r.json()['media_activated_at'];self.assertGreaterEqual(activated,before)
  again=self.client.post('/v1/vouchers/redeem',headers=guest,json={'code':v['code']});self.assertTrue(again.json()['replayed'])
  m=self.client.get('/v1/entitlements',headers=guest).json()[0]['media_policy']
  self.assertEqual((m['activation'],m['activated_at'],m['valid_until'],m['state'],m['categories'],m['device_limit'],m['device_transfer'],m['playback']),('redeemed_in_portal',activated,activated+86400,'active',['Comedy'],1,'not_allowed_until_expiry','not_connected'))
  with self.app.state.factory() as s:e=s.scalar(select(Entitlement));e.activated=activated-90000;s.commit()
  self.assertEqual(self.client.get('/v1/entitlements',headers=guest).json()[0]['media_policy']['state'],'expired')
  internet=self.client.post('/v1/packages',headers=owner,json={'name':'Internet hour','service':'internet','mode':'time','price':500,'hours':1}).json()
  iv=self.client.post('/v1/vouchers',headers=owner,json={'package_id':internet['id'],'expires_days':7,'request_key':'internet-voucher-test-01'}).json()
  self.assertIsNone(self.client.post('/v1/vouchers/redeem',headers=guest,json={'code':iv['code']}).json()['media_activated_at'])

 def test_featured_preview_hides_other_titles_until_the_guest_holds_a_pass(self):
  owner=self.login('owner');guest=self.login('guest');other=self.login('other')
  a=self.title(owner,'Alpha','Drama');self.title(owner,'Beta','Drama');self.voucher_login(owner)
  self.assertEqual(self.client.get('/v1/media/settings',headers=owner).json(),{'catalog_preview':'full','revision':0})
  for h in [guest,self.login('platform')]:self.assertEqual(self.client.get('/v1/media/settings',headers=h).status_code,403)
  self.assertEqual(self.client.post('/v1/media/settings',headers=owner,json={'expected_revision':1,'catalog_preview':'featured'}).status_code,409)
  r=self.client.post('/v1/media/settings',headers=owner,json={'expected_revision':0,'catalog_preview':'featured'});self.assertEqual(r.json(),{'catalog_preview':'featured','revision':1})
  self.assertEqual(self.titles(guest),[])
  a=self.state(owner,a,'feature');self.assertTrue(a['featured']);self.assertEqual(self.titles(guest),['Alpha'])
  self.assertEqual(self.client.get('/v1/media/settings',headers=other).json()['catalog_preview'],'full')
  p=self.client.post('/v1/packages',headers=owner,json={'name':'Library day','service':'media','mode':'library','price':1000,'hours':24}).json()
  v=self.client.post('/v1/vouchers',headers=owner,json={'package_id':p['id'],'expires_days':7,'request_key':'media-library-voucher-1'}).json()
  self.client.post('/v1/vouchers/redeem',headers=guest,json={'code':v['code']});self.assertEqual(self.titles(guest),['Alpha','Beta'])
  self.assertEqual(self.titles(self.login('guest2')),['Alpha'])
  archived=self.state(owner,a,'archive');self.assertFalse(archived['featured'])
  with self.app.state.factory() as s:self.assertEqual(len(list(s.scalars(select(Audit).where(Audit.action.in_(['media_settings_updated','media_title_feature']))))),2)

if __name__=='__main__':unittest.main()
