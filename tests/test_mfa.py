import time,unittest
import test_backend
from backend.models import AccountMFA

class FrozenV1PasswordOnlyTests(unittest.TestCase):
 def setUp(self):test_backend.AccountPaymentTests.setUp(self)
 tearDown=test_backend.AccountPaymentTests.tearDown
 login=test_backend.AccountPaymentTests.login

 def test_existing_mfa_record_does_not_block_password_login_or_change_data(self):
  record=AccountMFA(user_id=self.users['owner'],enabled=True,encrypted_secret='encrypted-legacy-secret',enrollment_expires=None,last_step=42,recovery_hashes=['legacy-hash-a','legacy-hash-b'],updated=int(time.time()))
  with self.app.state.factory() as s:s.add(record);s.commit()
  response=self.client.post('/v1/auth/login',json={'username':'owner','password':'test-password-only'})
  self.assertEqual(response.status_code,200,response.text)
  with self.app.state.factory() as s:
   saved=s.get(AccountMFA,self.users['owner']);self.assertTrue(saved.enabled);self.assertEqual(saved.encrypted_secret,'encrypted-legacy-secret');self.assertEqual(saved.last_step,42);self.assertEqual(saved.recovery_hashes,['legacy-hash-a','legacy-hash-b'])

 def test_mfa_status_and_mutation_routes_are_not_registered(self):
  h=self.login('owner')
  for method,path in [('get','/v1/account/mfa'),('post','/v1/account/mfa/enroll'),('post','/v1/account/mfa/confirm'),('post','/v1/account/mfa/disable')]:
   response=self.client.get(path,headers=h) if method=='get' else self.client.post(path,headers=h,json={})
   self.assertEqual(response.status_code,404,(method,path,response.text))

 def test_legacy_login_mfa_field_is_rejected(self):
  response=self.client.post('/v1/auth/login',json={'username':'owner','password':'test-password-only','mfa_code':'123456'})
  self.assertEqual(response.status_code,422)

 def test_password_only_login_and_explicit_logout_still_work(self):
  h=self.login('owner')
  self.assertEqual(self.client.get('/v1/me',headers=h).status_code,200)
  self.assertEqual(self.client.post('/v1/auth/logout',headers=h).status_code,200)
  self.assertEqual(self.client.get('/v1/me',headers=h).status_code,401)

 def test_legacy_mfa_table_remains_available_without_implicit_rewrite(self):
  with self.app.state.factory() as s:
   row=AccountMFA(user_id=self.users['guest'],enabled=False,encrypted_secret=None,enrollment_expires=123,last_step=-1,recovery_hashes=[],updated=123)
   s.add(row);s.commit()
  self.assertEqual(self.client.post('/v1/auth/login',json={'username':'guest','password':'test-password-only'}).status_code,200)
  with self.app.state.factory() as s:
   row=s.get(AccountMFA,self.users['guest']);self.assertFalse(row.enabled);self.assertEqual(row.enrollment_expires,123);self.assertEqual(row.recovery_hashes,[])
