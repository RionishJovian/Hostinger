import unittest
import test_backend
from backend.models import LoginHistory,User
class PlatformConsoleTests(unittest.TestCase):
 setUp=test_backend.AccountPaymentTests.setUp
 tearDown=test_backend.AccountPaymentTests.tearDown
 login=test_backend.AccountPaymentTests.login
 def make_owner(self,name='platform'):
  with self.app.state.factory() as db:db.get(User,self.users[name]).platform_owner=True;db.commit()
 def test_console_is_limited_to_the_platform_owner(self):
  headers={name:self.login(name) for name in ['owner','guest','platform']}
  for name,h in headers.items():
   self.assertFalse(self.client.get('/v1/me',headers=h).json()['platform_owner'])
   for path in ['/v1/platform/console/sessions','/v1/platform/console/sign-ins']:
    self.assertEqual(self.client.get(path,headers=h).status_code,403,(name,path))
  with self.app.state.factory() as db:db.get(User,self.users['owner']).platform_owner=True;db.commit()
  self.assertFalse(self.client.get('/v1/me',headers=headers['owner']).json()['platform_owner'])
  self.assertEqual(self.client.get('/v1/platform/console/sessions',headers=headers['owner']).status_code,403)
  self.make_owner()
  self.assertTrue(self.client.get('/v1/me',headers=headers['platform']).json()['platform_owner'])
  self.assertEqual(self.client.get('/v1/platform/console/sessions').status_code,401)
 def test_sessions_cover_every_account_without_tokens(self):
  self.make_owner();console=self.login('platform');owner=self.login('owner');self.login('other')
  r=self.client.get('/v1/platform/console/sessions',headers=console);self.assertEqual(r.status_code,200)
  rows=r.json();self.assertEqual({row['account'] for row in rows},{'platform','owner','other'})
  self.assertEqual([row['account'] for row in rows if row['current']],['platform'])
  self.assertEqual(next(row for row in rows if row['account']=='owner')['business'],'Cafe')
  self.assertNotIn(owner['Authorization'].split()[1],r.text);self.assertNotIn('token',r.text)
  self.client.post('/v1/auth/logout',headers=owner)
  self.assertNotIn('owner',{row['account'] for row in self.client.get('/v1/platform/console/sessions',headers=console).json()})
 def test_sign_in_activity_includes_platform_sign_ins_failures_and_sign_outs(self):
  self.make_owner();ua={'user-agent':'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Safari/605.1.15'}
  self.assertEqual(self.client.post('/v1/auth/login',json={'username':'platform','password':'wrong-secret'},headers=ua).status_code,401)
  first=self.client.post('/v1/auth/login',json={'username':'platform','password':'test-password-only'},headers=ua).json()['access_token']
  self.client.post('/v1/auth/logout',headers={'Authorization':'Bearer '+first})
  guest=self.login('guest');console=self.login('platform')
  r=self.client.get('/v1/platform/console/sign-ins',headers=console);self.assertEqual(r.status_code,200)
  body=r.json();self.assertEqual(body['retention_days'],7)
  mine=[e for e in body['events'] if e['account']=='platform']
  self.assertEqual(sorted(e['event'] for e in mine),['Failed sign-in','Signed in','Signed in','Signed out'])
  failed=next(e for e in mine if e['event']=='Failed sign-in');self.assertEqual((failed['outcome'],failed['browser']),('failure','Safari'))
  self.assertTrue(any(e['event']=='Signed in' and e['browser']=='Safari' for e in mine))
  self.assertTrue(any(e['account']=='guest' and e['event']=='Signed in' for e in body['events']))
  self.assertNotIn('wrong-secret',r.text);self.assertNotIn(first,r.text);self.assertNotIn(guest['Authorization'].split()[1],r.text)
  self.assertEqual(self.client.get('/v1/account/login-history',headers=console).status_code,403)
 def test_sign_in_activity_honors_seven_day_retention(self):
  self.make_owner();console=self.login('platform')
  with self.app.state.factory() as db:
   db.add(LoginHistory(user_id=self.users['owner'],tenant_id=db.get(User,self.users['owner']).tenant_id,outcome='failure',created=1,device='OLD_MARKER',browser='Old',source='192.0.2.0/24'));db.commit()
  self.assertNotIn('OLD_MARKER',self.client.get('/v1/platform/console/sign-ins',headers=console).text)
if __name__=='__main__':unittest.main()
