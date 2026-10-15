import base64,time,unittest
from unittest.mock import patch
import test_backend
from sqlalchemy import select,func
from backend.app import HASHER
from backend.models import User,StaffGrant,SessionToken,Order
KEY=base64.b64encode(bytes([9])*32).decode()
class StaffTests(unittest.TestCase):
 setUp=test_backend.AccountPaymentTests.setUp
 tearDown=test_backend.AccountPaymentTests.tearDown
 login=test_backend.AccountPaymentTests.login
 package=test_backend.AccountPaymentTests.package
 order=test_backend.AccountPaymentTests.order
 def legacy(self,profile):
  now=int(time.time())
  with self.app.state.factory() as s:
   o=s.get(User,self.users['owner']);a=User(username='staff-'+profile,password_hash=HASHER.hash('test-password-only'),role='sme',tenant_id=o.tenant_id,active=True);s.add(a);s.flush()
   s.add(StaffGrant(user_id=a.id,tenant_id=o.tenant_id,profile=profile,revision=1,created_by=o.id,request_key='legacy-staff-'+profile,request_hash='0'*64,created=now,updated=now));s.commit();return a.id,self.login('staff-'+profile)
 def test_new_staff_accounts_are_closed(self):
  owner=self.login('owner')
  with self.app.state.factory() as s:before=s.scalar(select(func.count()).select_from(User))
  r=self.client.post('/v1/staff',headers=owner,json={'username':'staff-new','profile':'cashier','request_key':'staff-request-key-new'});self.assertEqual(r.status_code,410);self.assertNotIn('temporary_password',r.text)
  with self.app.state.factory() as s:self.assertEqual(s.scalar(select(func.count()).select_from(User)),before);self.assertIsNone(s.scalar(select(User).where(User.username=='staff-new')))
  self.assertEqual(self.client.post('/v1/staff',headers=self.login('guest'),json={'username':'staff-new','profile':'cashier','request_key':'staff-request-key-new'}).status_code,403)
 def test_every_legacy_profile_is_denied_business_authority(self):
  reads=['sites','routers','hubs','router-plans','orders','vouchers','packages','revenue','audit','tenants','appearance/effective','staff','review-credentials','platform/businesses','account/sessions']
  writes={'routers/missing/plan':{'hub_id':'missing','router_public_key':KEY},'router-plans/missing/review':{'confirmed_review':True},'routers/missing/preflight':None,'routers/missing/wireguard-evidence':None,'routers/missing/changes/preview':{'persistent_keepalive_seconds':25},'router-plans/missing/hub-peer/provision':None,'sites':{'name':'Staff site'},'orders/missing/decision':{'decision':'approved','expected_receipt_revision':0},'orders/missing/refund':{'reason':'Not allowed'},'vouchers':{'package_id':'missing','request_key':'staff-voucher-test-001'}}
  for profile in ['manager','cashier','technician']:
   with self.subTest(profile=profile):
    sid,h=self.legacy(profile);me=self.client.get('/v1/me',headers=h);self.assertEqual(me.status_code,200);self.assertEqual(me.json()['staff_profile'],profile)
    for path in reads:self.assertEqual(self.client.get('/v1/'+path,headers=h).status_code,403,path)
    for path,body in writes.items():self.assertEqual(self.client.post('/v1/'+path,headers=h,json=body).status_code,403,path)
    with self.app.state.factory() as s:staff_before=s.get(User,sid).password_hash;owner_before=s.get(User,self.users['owner']).password_hash
    changed=self.client.post('/v1/auth/password',headers=h,json={'current_password':'test-password-only','new_password':'staff-test-personal-password'})
    self.assertEqual(changed.status_code,200,changed.text)
    with self.app.state.factory() as s:self.assertNotEqual(s.get(User,sid).password_hash,staff_before);self.assertEqual(s.get(User,self.users['owner']).password_hash,owner_before)
    self.assertEqual(self.client.post('/v1/auth/logout',headers=h).status_code,200);self.assertEqual(self.client.get('/v1/me',headers=h).status_code,401)
 def test_owner_checks_exclude_staff_even_if_allowlist_widens(self):
  _,h=self.legacy('manager')
  with patch('backend.app.staff_allowed',return_value=True):
   for path,body in {'routers/missing/plan':{'hub_id':'missing','router_public_key':KEY},'router-plans/missing/review':{'confirmed_review':True},'routers/missing/preflight':None,'routers/missing/wireguard-evidence':None,'routers/missing/changes/preview':{'persistent_keepalive_seconds':25}}.items():self.assertEqual(self.client.post('/v1/'+path,headers=h,json=body).status_code,403,path)
  owner=self.login('owner');self.assertEqual(self.client.post('/v1/router-plans/missing/review',headers=owner,json={'confirmed_review':True}).status_code,404)
 def test_owner_can_list_and_disable_legacy_staff(self):
  sid,h=self.legacy('cashier');owner=self.login('owner')
  listed=self.client.get('/v1/staff',headers=owner);self.assertEqual(listed.status_code,200);self.assertEqual([x['id'] for x in listed.json()],[sid])
  update={'expected_revision':1,'profile':'cashier','active':False,'reason':'Employment ended (test)'};r=self.client.post('/v1/staff/'+sid,headers=owner,json=update);self.assertEqual(r.status_code,200);self.assertEqual(r.json()['last_reason'],update['reason']);self.assertEqual(self.client.get('/v1/me',headers=h).status_code,401)
  self.assertEqual(self.client.post('/v1/staff/'+sid,headers=owner,json=update).status_code,409)
  with self.app.state.factory() as s:self.assertFalse(s.get(User,sid).active);self.assertEqual(s.scalar(select(func.count()).select_from(SessionToken).where(SessionToken.user_id==sid)),0)
  businesses=self.client.get('/v1/platform/businesses',headers=self.login('platform')).json();self.assertFalse(any(o['id']==sid for b in businesses for o in b['owners']))
 def test_recovery_requires_owner_confirmation_and_preserves_disable(self):
  sid,_=self.legacy('technician');owner=self.login('owner');url='/v1/staff/'+sid;body={'expected_revision':1,'profile':'technician','active':False,'reason':'Recovery test disable'};self.assertEqual(self.client.post(url,headers=owner,json=body).status_code,200)
  reset=body|{'expected_revision':2,'confirmed_authority':True};self.assertEqual(self.client.post(url+'/reset-password',headers=owner,json=reset|{'confirmed_authority':False}).status_code,422)
  r=self.client.post(url+'/reset-password',headers=owner,json=reset);self.assertEqual(r.status_code,200);self.assertFalse(r.json()['staff']['active']);self.assertTrue(r.json()['staff']['must_change_password']);self.assertEqual(r.json()['staff']['revision'],3)
  self.assertEqual(self.client.post('/v1/auth/login',json={'username':'staff-technician','password':r.json()['temporary_password']}).status_code,401)
 def test_former_cashier_cannot_review_payment_or_sell_voucher(self):
  _,h=self.legacy('cashier');p=self.package(self.login('owner'));o=self.order(self.login('guest'),p).json()
  self.assertEqual(self.client.post('/v1/orders/'+o['id']+'/decision',headers=h,json={'decision':'approved','expected_receipt_revision':0}).status_code,403)
  self.assertEqual(self.client.post('/v1/vouchers',headers=h,json={'package_id':p,'request_key':'cashier-voucher-test-001'}).status_code,403)
  with self.app.state.factory() as s:self.assertNotEqual(s.get(Order,o['id']).status,'approved')
