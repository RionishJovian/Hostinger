import unittest
from pathlib import Path
from sqlalchemy import select
import test_backend as fixture
from backend import models
from backend.models import Order,Entitlement,Package
class MediaTests(unittest.TestCase):
 setUp=fixture.AccountPaymentTests.setUp
 tearDown=fixture.AccountPaymentTests.tearDown
 login=fixture.AccountPaymentTests.login
 def title(self,owner,name='Sample film'):
  r=self.client.post('/v1/media/titles',headers=owner,json={'name':name,'description':'A test film','genre':'Drama','runtime_minutes':90,'release_year':2020});self.assertEqual(r.status_code,201,r.text);return r.json()
 def state(self,h,t,operation):return self.client.post('/v1/media/titles/'+t['id']+'/state',headers=h,json={'expected_revision':t['revision'],'operation':operation})
 def package(self,h,title_id,mode='hybrid',**extra):return self.client.post('/v1/packages',headers=h,json={'name':'Media pass','service':'media','mode':mode,'price':2000,'hours':2,'title_hours':48,'title':title_id,**extra})
 def order(self,h,package,key='media-purchase-001'):return self.client.post('/v1/orders',headers=h,json={'package_id':package,'portal_revision':1,'method':'Cash','reference':'media-receipt','evidence':'Confirmed test receipt','request_key':key})
 def test_no_plex_schema_or_product_adapters(self):
  """Owner 2026-10-13: Jellyfin only. Inventory proves there is nothing Plex-specific to migrate away."""
  names=[]
  for table_name,table in models.Base.metadata.tables.items():
   names.append(table_name.lower())
   for col in table.columns:names.append(col.name.lower())
  joined=' '.join(names)
  self.assertNotIn('plex',joined)
  media_py=Path(__file__).resolve().parents[1]/'backend'/'media.py'
  text=media_py.read_text(encoding='utf-8')
  self.assertRegex(text,r'Plex is out of scope')
  self.assertIn('Jellyfin',text)
  # Docstring may name Plex only to record that it is unsupported; no adapter API remains.
  self.assertIsNone(__import__('re').search(r'Jellyfin/Plex|Jellyfin or Plex|Plex server|plex_',text,__import__('re').I))
 def test_catalogue_visibility_permissions_and_revision(self):
  owner=self.login('owner');guest=self.login('guest');other=self.login('other');platform=self.login('platform');t=self.title(owner)
  self.assertEqual(self.client.get('/v1/media/titles',headers=guest).json(),[]);self.assertEqual(self.client.get('/v1/media/titles',headers=other).json(),[]);self.assertEqual(self.client.get('/v1/media/titles',headers=platform).status_code,403)
  for h in [guest,platform]:self.assertEqual(self.state(h,t,'publish').status_code,403)
  self.assertEqual(self.state(other,t,'publish').status_code,404)
  pub=self.state(owner,t,'publish');self.assertEqual(pub.status_code,200);self.assertEqual(len(self.client.get('/v1/media/titles',headers=guest).json()),1)
  self.assertEqual(self.state(owner,t,'archive').status_code,409)
  archived=self.state(owner,pub.json(),'archive').json();self.assertTrue(archived['archived']);self.assertEqual(self.client.get('/v1/media/titles',headers=guest).json(),[])
  self.assertEqual(self.state(owner,archived,'publish').status_code,409)
  restored=self.state(owner,archived,'restore').json();self.assertFalse(restored['archived']);self.assertFalse(restored['published'])
 def test_hybrid_offer_and_immutable_payment_entitlement_snapshot(self):
  owner=self.login('owner');guest=self.login('guest');t=self.title(owner);p=self.package(owner,t['id']);self.assertEqual(p.status_code,201,p.text);p=p.json()
  self.assertEqual(p['title_snapshot']['name'],'Sample film');self.assertEqual(self.client.get('/v1/packages',headers=guest).json(),[]);self.assertEqual(self.order(guest,p['id']).status_code,409)
  t=self.state(owner,t,'publish').json();o=self.order(guest,p['id']);self.assertEqual(o.status_code,201,o.text);o=o.json()
  self.assertEqual(self.client.post('/v1/orders/'+o['id']+'/decision',headers=owner,json={'decision':'approved'}).status_code,200)
  e=self.client.get('/v1/entitlements',headers=guest).json()[0];self.assertEqual(e['media_policy']['library_hours'],2);self.assertEqual(e['media_policy']['title_hours'],48);self.assertEqual(e['media_policy']['playback'],'not_connected');self.assertIsNone(e['activation']);self.assertEqual(e['policy']['title_snapshot']['name'],'Sample film')
  settings={k:t[k] for k in ['name','description','genre','runtime_minutes','release_year']};settings['name']='Changed title'
  r=self.client.post('/v1/media/titles/'+t['id'],headers=owner,json={'expected_revision':t['revision'],'settings':settings});self.assertEqual(r.status_code,200);self.assertFalse(r.json()['published'])
  self.assertEqual(self.client.get('/v1/entitlements',headers=guest).json()[0]['policy']['title_snapshot']['name'],'Sample film');self.assertEqual(self.client.get('/v1/orders',headers=guest).json()[0]['snapshot']['title_snapshot']['name'],'Sample film')
  self.assertEqual(self.order(guest,p['id']).json()['id'],o['id']) # exact retry retains history after unpublication
  self.assertEqual(self.client.get('/v1/revenue',headers=owner).json()['by_service']['media'],2000)
 def test_foreign_title_policy_and_invalid_media_modes(self):
  owner=self.login('owner');other=self.login('other');t=self.title(other)
  self.assertEqual(self.package(owner,t['id']).status_code,404)
  for extra in [{'title':None},{'hours':0},{'title_hours':0},{'clock':'connected'},{'mode':'both'}]:
   self.assertEqual(self.package(owner,'missing',**extra).status_code,422)
  self.assertEqual(self.client.post('/v1/media/titles',headers=owner,json={'name':'Invalid','runtime_minutes':0}).status_code,422)
  self.assertEqual(self.client.post('/v1/media/titles',headers=owner,json={'name':'URL','runtime_minutes':90,'stream_url':'https://example.com/file'}).status_code,422)
 def test_archive_blocks_new_sales_and_approval_without_erasing_history(self):
  owner=self.login('owner');guest=self.login('guest');t=self.state(owner,self.title(owner),'publish').json();p=self.package(owner,t['id'],'title').json();o=self.order(guest,p['id']).json()
  self.state(owner,t,'archive')
  self.assertEqual(self.client.post('/v1/orders/'+o['id']+'/decision',headers=owner,json={'decision':'approved'}).status_code,409)
  self.assertEqual(self.client.post('/v1/vouchers',headers=owner,json={'package_id':p['id'],'request_key':'archived-media-voucher-001','expires_days':1}).status_code,409)
  self.assertEqual(self.client.get('/v1/packages',headers=guest).json(),[]);self.assertEqual(self.order(guest,p['id'],'other-media-order-002').status_code,409)
  self.assertEqual(self.client.post('/v1/orders/'+o['id']+'/decision',headers=owner,json={'decision':'rejected','reason':'Title withdrawn; payment not accepted'}).status_code,200)
  self.assertEqual(self.client.get('/v1/orders',headers=guest).json()[0]['snapshot']['title_snapshot']['name'],'Sample film')
 def test_media_voucher_retains_hybrid_policy_and_can_redeem_after_catalogue_withdrawal(self):
  owner=self.login('owner');guest=self.login('guest');t=self.state(owner,self.title(owner),'publish').json();p=self.package(owner,t['id']).json()
  cfg=self.client.get('/v1/portal',headers=owner).json()['draft'];cfg['voucher_login']=True
  self.client.post('/v1/portal/draft',headers=owner,json={'expected_revision':1,'settings':cfg});self.client.post('/v1/portal/publish',headers=owner,json={'expected_revision':2})
  v=self.client.post('/v1/vouchers',headers=owner,json={'package_id':p['id'],'expires_days':1,'request_key':'hybrid-media-voucher-001'});self.assertEqual(v.status_code,201,v.text);v=v.json();self.state(owner,t,'archive')
  redeemed=self.client.post('/v1/vouchers/redeem',headers=guest,json={'code':v['code']});self.assertEqual(redeemed.status_code,200,redeemed.text)
  pass_=self.client.get('/v1/entitlements',headers=guest).json()[0];self.assertEqual(pass_['media_policy']['mode'],'hybrid');self.assertEqual(pass_['media_policy']['title_hours'],48);self.assertEqual(pass_['source'],'voucher');self.assertEqual(self.client.get('/v1/revenue',headers=owner).json()['net_collections'],0)
 def test_library_window_and_legacy_combined_packages(self):
  owner=self.login('owner');guest=self.login('guest')
  self.state(owner,self.title(owner),'publish')
  p=self.client.post('/v1/packages',headers=owner,json={'name':'Library','service':'media','mode':'library','hours':24,'price':1000}).json();o=self.order(guest,p['id']).json();self.client.post('/v1/orders/'+o['id']+'/decision',headers=owner,json={'decision':'approved'})
  e=self.client.get('/v1/entitlements',headers=guest).json()[0];self.assertEqual(e['media_policy']['library_hours'],24);self.assertIsNone(e['media_policy']['title_hours']);self.assertIsNone(e['media_policy']['title'])

  r=self.client.post('/v1/packages',headers=owner,json={'name':'Combined','service':'combined','mode':'both','hours':3,'gb':5,'media_hours':72,'price':3000});self.assertEqual(r.status_code,422);self.assertIn('sold separately',r.text)
  policy={'name':'Combined','service':'combined','mode':'both','price':3000,'gb':5,'hours':3,'media_hours':72,'clock':'elapsed','devices':1,'speed':10,'title':None,'title_hours':48,'vip':False}
  with self.app.state.factory() as s:
   tenant=s.get(Order,o['id']).tenant_id;legacy=Package(tenant_id=tenant,policy=policy,active=True);s.add(legacy);s.flush()
   s.add(Order(tenant_id=tenant,guest_id=s.get(Order,o['id']).guest_id,package_id=legacy.id,snapshot=policy,amount=3000,method='Cash',reference='legacy-ref',evidence='legacy',status='pending',created=1,request_key='legacy-combined-order'));s.commit();legacy_id=legacy.id
  self.assertNotIn(legacy_id,[x['id'] for x in self.client.get('/v1/packages',headers=guest).json()])
  self.assertEqual(self.order(guest,legacy_id,'combined-media-order-001').status_code,409)
  self.assertEqual(self.client.post('/v1/vouchers',headers=owner,json={'package_id':legacy_id,'expires_days':7,'request_key':'legacy-combined-voucher'}).status_code,409)
  pending=next(x for x in self.client.get('/v1/orders',headers=owner).json() if x['snapshot']['name']=='Combined')
  self.assertEqual(self.client.post('/v1/orders/'+pending['id']+'/decision',headers=owner,json={'decision':'approved'}).status_code,200)
  m=next(e for e in self.client.get('/v1/entitlements',headers=guest).json() if e['policy']['name']=='Library')['media_policy'];self.assertEqual((m['activation'],m['state'],m['activated_at'],m['valid_until']),('starts_at_first_use','not_started',None,None))
  e=next(e for e in self.client.get('/v1/entitlements',headers=guest).json() if e['policy']['name']=='Combined');self.assertEqual((e['media_policy']['library_hours'],e['media_policy']['legacy_combined']),(72,True));self.assertEqual(e['policy']['hours'],3)
 def test_empty_library_cannot_sell_media_only_pass(self):
  owner=self.login('owner');guest=self.login('guest');p=self.client.post('/v1/packages',headers=owner,json={'name':'Library','service':'media','mode':'library','hours':24,'price':1000}).json()
  self.assertEqual(self.client.get('/v1/packages',headers=guest).json(),[]);self.assertEqual(self.order(guest,p['id']).status_code,409)
  t=self.state(owner,self.title(owner),'publish').json();self.assertEqual(len(self.client.get('/v1/packages',headers=guest).json()),1)
  self.state(owner,t,'unpublish');self.assertEqual(self.order(guest,p['id']).status_code,409)
