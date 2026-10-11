import unittest
from io import BytesIO
import test_backend
from PIL import Image
from sqlalchemy import select
from backend.models import User,Audit

def image_bytes(fmt='PNG',size=(600,300),frames=1):
 im=Image.new('RGBA' if fmt!='JPEG' else 'RGB',size,(20,90,70));out=BytesIO()
 if frames>1:im.save(out,format='PNG',save_all=True,append_images=[Image.new('RGBA',size,(200,0,0))])
 else:im.save(out,format=fmt)
 return out.getvalue()

class ApplicationSettingsTests(unittest.TestCase):
 setUp=test_backend.AccountPaymentTests.setUp
 tearDown=test_backend.AccountPaymentTests.tearDown
 login=test_backend.AccountPaymentTests.login
 def developer(self):
  with self.app.state.factory() as db:db.get(User,self.users['platform']).platform_owner=True;db.commit()
  return self.login('platform')
 def body(self,revision,**kw):return {'expected_revision':revision,'app_name':'MegaMagic','default_language':'en','languages':['en','my'],'announcement':None,**kw}
 def upload(self,headers,data,key='logo-upload-key-0001'):return self.client.post('/v1/developer/application/logo',headers={**headers,'Content-Type':'application/octet-stream','X-Upload-Key':key},content=data)

 def test_defaults_are_public_and_settings_are_owner_only(self):
  r=self.client.get('/v1/branding');self.assertEqual(r.status_code,200)
  self.assertEqual(r.json(),{'app_name':'MikroMagic','default_language':'my','languages':['my','en'],'logo':None})
  self.assertEqual(self.client.get('/v1/branding/logo').status_code,404)
  for h in [self.login('platform'),self.login('owner'),self.login('guest')]:
   self.assertEqual(self.client.get('/v1/developer/application',headers=h).status_code,403)
   self.assertEqual(self.client.post('/v1/developer/application',headers=h,json=self.body(0)).status_code,403)
   self.assertEqual(self.upload(h,image_bytes()).status_code,403)
   self.assertEqual(self.client.post('/v1/developer/application/logo/remove',headers=h).status_code,403)

 def test_owner_saves_name_languages_and_announcement_with_revisions(self):
  dev=self.developer();self.assertEqual(self.client.get('/v1/developer/application',headers=dev).json()['revision'],0)
  r=self.client.post('/v1/developer/application',headers=dev,json=self.body(0,app_name='  MegaMagic  '));self.assertEqual(r.status_code,200,r.text)
  self.assertEqual((r.json()['revision'],r.json()['app_name'],r.json()['languages']),(1,'MegaMagic',['my','en']))
  self.assertEqual(self.client.post('/v1/developer/application',headers=dev,json=self.body(0)).status_code,409)
  self.assertEqual(self.client.get('/v1/branding').json()['app_name'],'MegaMagic');self.assertEqual(self.client.get('/v1/branding').json()['default_language'],'en')
  for bad in [self.body(1,app_name='   '),self.body(1,languages=['my']),self.body(1,languages=['en','en']),self.body(1,languages=[]),self.body(1,default_language='fr'),self.body(1,announcement={'text':'','level':'info'}),self.body(1,announcement={'text':'x','level':'urgent'})]:
   self.assertEqual(self.client.post('/v1/developer/application',headers=dev,json=bad).status_code,422,bad)
  owner=self.login('owner');self.assertIsNone(self.client.get('/v1/announcement',headers=owner).json())
  r=self.client.post('/v1/developer/application',headers=dev,json=self.body(1,languages=['en'],announcement={'text':'Maintenance on Sunday 02:00','level':'warning'}));self.assertEqual(r.status_code,200,r.text)
  self.assertEqual(self.client.get('/v1/branding').json()['languages'],['en'])
  self.assertEqual(self.client.get('/v1/announcement',headers=owner).json(),{'text':'Maintenance on Sunday 02:00','level':'warning','revision':2})
  for h in [self.login('guest'),dev]:self.assertIsNone(self.client.get('/v1/announcement',headers=h).json())
  with self.app.state.factory() as db:self.assertEqual(db.scalars(select(Audit.action).where(Audit.action=='application_settings_saved')).all(),['application_settings_saved']*2)

 def test_logo_is_reencoded_bounded_and_removable(self):
  dev=self.developer()
  for fmt in ['PNG','JPEG','WEBP']:
   r=self.upload(dev,image_bytes(fmt)+(b'<script>alert(1)</script>' if fmt=='PNG' else b''));self.assertEqual(r.status_code,200,(fmt,r.text))
   self.assertEqual((r.json()['logo']['width'],r.json()['logo']['height']),(256,128))
  url=self.client.get('/v1/branding').json()['logo'];self.assertTrue(url.startswith('/v1/branding/logo?v='))
  logo=self.client.get(url);self.assertEqual(logo.headers['content-type'],'image/png');self.assertNotIn(b'<script>',logo.content)
  self.assertEqual(Image.open(BytesIO(logo.content)).format,'PNG')
  self.assertEqual(self.upload(dev,b'<svg xmlns="http://www.w3.org/2000/svg"/>').status_code,422)
  self.assertEqual(self.upload(dev,image_bytes(frames=2)).status_code,422)
  self.assertEqual(self.upload(dev,b'x'*(1024*1024+1)).status_code,413)
  self.assertEqual(self.upload(dev,image_bytes(),key='bad key').status_code,422)
  self.assertEqual(self.client.post('/v1/developer/application/logo/remove',headers=dev).json()['logo'],None)
  self.assertIsNone(self.client.get('/v1/branding').json()['logo']);self.assertEqual(self.client.get('/v1/branding/logo').status_code,404)
  with self.app.state.factory() as db:
   actions=db.scalars(select(Audit.action).where(Audit.action.like('application_logo%'))).all()
   self.assertEqual(sorted(set(actions)),['application_logo_removed','application_logo_uploaded'])

if __name__=='__main__':unittest.main()
