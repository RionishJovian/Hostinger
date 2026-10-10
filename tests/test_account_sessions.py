import unittest
import time
import test_backend
from unittest.mock import patch
from sqlalchemy import select
from backend.models import LoginHistory,SessionToken
class AccountSessionTests(unittest.TestCase):
 setUp=test_backend.AccountPaymentTests.setUp
 tearDown=test_backend.AccountPaymentTests.tearDown
 login=test_backend.AccountPaymentTests.login
 def test_own_session_listing_and_scoped_revoke(self):
  first=self.login('owner');second=self.login('owner');other=self.login('other');rows=self.client.get('/v1/account/sessions',headers=first).json();self.assertEqual(len(rows),2);self.assertEqual(sum(r['current'] for r in rows),1);target=next(r for r in rows if not r['current'])
  self.assertEqual(self.client.post('/v1/account/sessions/revoke',headers=other,json={'session_ref':target['session_ref']}).status_code,404)
  self.assertEqual(self.client.post('/v1/account/sessions/revoke',headers=first,json={'session_ref':target['session_ref']}).status_code,200)
  self.assertEqual(self.client.get('/v1/me',headers=second).status_code,401);self.assertEqual(self.client.get('/v1/me',headers=first).status_code,200)
  self.assertEqual(self.client.post('/v1/account/sessions/revoke',headers=first,json={'session_ref':next(r for r in rows if r['current'])['session_ref']}).status_code,409)
 def test_end_others_requires_confirmation_and_preserves_current(self):
  for role in ['platform','guest']:
   first=self.login(role);second=self.login(role)
   self.assertEqual(self.client.post('/v1/account/sessions/revoke-others',headers=first,json={'confirmed':False}).status_code,422)
   r=self.client.post('/v1/account/sessions/revoke-others',headers=first,json={'confirmed':True});self.assertEqual(r.json()['revoked_count'],1);self.assertFalse(r.json()['service_credentials_changed']);self.assertEqual(self.client.get('/v1/me',headers=first).status_code,200);self.assertEqual(self.client.get('/v1/me',headers=second).status_code,401)
 def test_owner_session_details_and_login_history_are_persisted_and_redacted(self):
  self.client.close();self.client=test_backend.TestClient(self.app,client=('198.51.100.29',51000))
  ua='Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/130.0.0.0 Mobile/15E148 Safari/604.1'
  failed=self.client.post('/v1/auth/login',json={'username':'owner','password':'wrong-secret'},headers={'user-agent':ua})
  self.assertEqual(failed.status_code,401)
  login=self.client.post('/v1/auth/login',json={'username':'owner','password':'test-password-only'},headers={'user-agent':ua})
  self.assertEqual(login.status_code,200);token=login.json()['access_token'];headers={'Authorization':'Bearer '+token}
  rows=self.client.get('/v1/account/sessions',headers=headers).json();self.assertEqual(len(rows),1)
  session=rows[0];self.assertTrue(session['current']);self.assertEqual(session['device'],'Reported mobile');self.assertEqual(session['browser'],'Chrome');self.assertEqual(session['login_at'],session['last_active'])
  history=self.client.get('/v1/account/login-history',headers=headers)
  self.assertEqual(history.status_code,200);self.assertEqual({row['outcome'] for row in history.json()},{'success','failure'})
  self.assertEqual(history.json()[0]['device'],'Reported mobile');self.assertEqual(history.json()[0]['browser'],'Chrome')
  self.assertRegex(history.json()[0]['approximate_source'],r'/24$|/48$')
  self.assertNotIn(token,history.text);self.assertNotIn('wrong-secret',history.text);self.assertNotIn('CriOS',history.text)
  with self.app.state.factory() as db:
   stored=db.scalar(select(SessionToken).where(SessionToken.user_id==self.users['owner']))
   entries=list(db.scalars(select(LoginHistory).where(LoginHistory.user_id==self.users['owner'])))
   self.assertIsNotNone(stored.login_at);self.assertEqual(len(entries),2)
   self.assertTrue(all('wrong-secret' not in row.browser+row.device+row.source for row in entries))
 def test_owner_login_history_is_account_scoped_and_forbidden_to_nonowners(self):
  owner=self.login('owner');other=self.login('other');guest=self.login('guest');platform=self.login('platform')
  with self.app.state.factory() as db:
   owner_user=db.get(test_backend.User,self.users['owner']);db.add(LoginHistory(user_id=owner_user.id,tenant_id=owner_user.tenant_id,outcome='failure',created=int(time.time()),device='OWNER_PRIVATE_MARKER',browser='Private',source='192.0.2.0/24'));db.commit()
  self.assertEqual(self.client.get('/v1/account/login-history',headers=owner).status_code,200)
  other_rows=self.client.get('/v1/account/login-history',headers=other).json()
  self.assertEqual(len(other_rows),1);self.assertNotIn('OWNER_PRIVATE_MARKER',str(other_rows))
  self.assertEqual(self.client.get('/v1/account/login-history',headers=guest).status_code,403)
  self.assertEqual(self.client.get('/v1/account/login-history',headers=platform).status_code,403)
 def test_owner_login_history_one_week_retention_and_preupgrade_sessions_are_honest(self):
  first=self.login('owner')
  with self.app.state.factory() as db:
   current=db.scalar(select(SessionToken).where(SessionToken.user_id==self.users['owner']));current.login_at=None;current.last_active=None;current.device=None;current.browser=None;current.source=None
   old=LoginHistory(user_id=self.users['owner'],tenant_id=db.get(test_backend.Tenant,db.get(test_backend.User,self.users['owner']).tenant_id).id,outcome='failure',created=1,device='Unavailable',browser='Unavailable',source='Unavailable');db.add(old);db.commit()
  rows=self.client.get('/v1/account/sessions',headers=first).json()
  self.assertIn('before device history was enabled',rows[0]['device']);self.assertIsNone(rows[0]['login_at'])
  next_login=self.login('owner')
  history=self.client.get('/v1/account/login-history',headers=next_login).json()
  self.assertTrue(all(row['time']>1 for row in history))
  with self.app.state.factory() as db:self.assertEqual(db.scalar(select(LoginHistory).where(LoginHistory.created==1)),None)
