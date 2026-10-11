import unittest
import test_backend
from sqlalchemy import select,func
from backend.models import User,OwnerAccessEvent,SessionToken

class DeveloperDashboardTests(unittest.TestCase):
 setUp=test_backend.AccountPaymentTests.setUp
 tearDown=test_backend.AccountPaymentTests.tearDown
 login=test_backend.AccountPaymentTests.login
 def developer(self):
  with self.app.state.factory() as db:db.get(User,self.users['platform']).platform_owner=True;db.commit()
  return self.login('platform')
 def sign_in(self,name):return self.client.post('/v1/auth/login',json={'username':name,'password':'test-password-only'})
 def owner_row(self,dev,name='owner'):return next(r for r in self.client.get('/v1/developer/owners',headers=dev).json() if r['username']==name)
 def change(self,dev,row,state,reason='Test reason'):
  return self.client.post('/v1/developer/owners/'+row['id']+'/access',headers=dev,json={'expected_revision':row['access_revision'],'state':state,'reason':reason})

 def test_dashboard_is_limited_to_the_platform_owner(self):
  for h in [self.login('platform'),self.login('owner'),self.login('guest')]:
   for path in ['/v1/developer/owners','/v1/developer/roles','/v1/developer/owners/'+self.users['owner']+'/history']:
    self.assertEqual(self.client.get(path,headers=h).status_code,403,path)
   self.assertEqual(self.client.post('/v1/developer/owners/'+self.users['owner']+'/access',headers=h,json={'expected_revision':0,'state':'disabled','reason':'x'}).status_code,403)
  dev=self.developer();rows=self.client.get('/v1/developer/owners',headers=dev).json()
  self.assertEqual(sorted(r['username'] for r in rows),['other','owner']);self.assertEqual(self.owner_row(dev)['access_state'],'active')
  self.assertEqual(self.client.post('/v1/developer/owners/'+self.users['guest']+'/access',headers=dev,json={'expected_revision':0,'state':'disabled','reason':'x'}).status_code,404)

 def test_suspension_ends_sessions_and_shows_the_reason_until_restored(self):
  dev=self.developer();owner=self.login('owner');row=self.owner_row(dev);self.assertEqual(row['active_sessions'],1)
  r=self.change(dev,row,'suspended','Unpaid invoice (test)');self.assertEqual(r.status_code,200,r.text);self.assertEqual(r.json()['sessions_ended'],1)
  self.assertEqual(self.client.get('/v1/me',headers=owner).status_code,401)
  blocked=self.sign_in('owner');self.assertEqual(blocked.status_code,403);self.assertIn('Unpaid invoice (test)',blocked.json()['detail'])
  wrong=self.client.post('/v1/auth/login',json={'username':'owner','password':'wrong-password'});self.assertEqual(wrong.status_code,401);self.assertNotIn('suspended',wrong.text)
  self.assertEqual(self.change(dev,row,'active').status_code,409)
  row=self.owner_row(dev);self.assertEqual((row['access_state'],row['access_reason']),('suspended','Unpaid invoice (test)'))
  self.assertEqual(self.change(dev,row,'suspended').status_code,409)
  self.assertEqual(self.change(dev,row,'active','Paid (test)').status_code,200);self.assertEqual(self.sign_in('owner').status_code,200)
  row=self.owner_row(dev);self.assertIsNone(row['access_reason'])
  history=self.client.get('/v1/developer/owners/'+row['id']+'/history',headers=dev).json()
  self.assertEqual([(e['from'],e['to']) for e in history['access']],[('suspended','active'),('active','suspended')]);self.assertEqual(history['access'][1]['actor'],'platform')
  self.assertIn('owner_access_suspended',[e['action'] for e in history['activity']])

 def test_disabled_owner_gets_the_generic_failure_and_other_businesses_are_untouched(self):
  dev=self.developer();other=self.login('other');row=self.owner_row(dev)
  self.assertEqual(self.change(dev,row,'disabled','Closed business (test)').status_code,200)
  r=self.sign_in('owner');self.assertEqual(r.status_code,401);self.assertNotIn('Closed business',r.text)
  self.assertEqual(self.client.get('/v1/me',headers=other).status_code,200)
  with self.app.state.factory() as db:
   self.assertFalse(db.get(User,self.users['owner']).active);self.assertEqual(db.scalar(select(func.count()).select_from(OwnerAccessEvent)),1)
   self.assertEqual(db.scalar(select(func.count()).select_from(SessionToken).where(SessionToken.user_id==self.users['owner'])),0)

 def test_business_rename_is_checked_against_the_current_name(self):
  dev=self.developer();row=self.owner_row(dev);url='/v1/developer/businesses/'+row['business_id']+'/name'
  self.assertEqual(self.client.post(url,headers=dev,json={'expected_name':'Stale name','name':'New name'}).status_code,409)
  self.assertEqual(self.client.post(url,headers=dev,json={'expected_name':row['business'],'name':'Renamed Cafe'}).status_code,200)
  self.assertEqual(self.owner_row(dev)['business'],'Renamed Cafe')
  self.assertEqual(self.client.post('/v1/developer/businesses/missing/name',headers=dev,json={'expected_name':'a','name':'b'}).status_code,404)

 def test_roles_overview_lists_the_developer_and_does_not_offer_custom_roles_yet(self):
  dev=self.developer();roles={r['key']:r for r in self.client.get('/v1/developer/roles',headers=dev).json()['roles']}
  self.assertEqual(roles['developer']['accounts'],[{'username':'platform','active':True}]);self.assertEqual(roles['user']['count'],2);self.assertFalse(roles['agent']['built'])
  self.assertFalse(self.client.get('/v1/developer/roles',headers=dev).json()['custom_roles']['available'])

if __name__=='__main__':unittest.main()
