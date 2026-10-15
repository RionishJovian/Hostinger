import os,time,tempfile,unittest
from datetime import date,timedelta
from pathlib import Path
from unittest.mock import patch
import test_backend
import test_hub_agent
from fastapi.testclient import TestClient
from sqlalchemy import select,func
from backend.app import HASHER
from backend.models import User,Tenant,TenantSubscription,SubscriptionInvoice,BillingEvent,Audit,StaffGrant,RouterDevice,RouterPlan,MagicHub,HubAssignment,MagicConnectEnrollment,MagicConnectAttempt,Site
from backend.subscriptions import add_months,midnight,local_date,term_status,renewal_term,is_restricted
from backend.subscription_renewal import renewal_allowed,RESTRICTED_MESSAGE,staff_restricted_allowed
from backend.hub_orchestrator import HubPeerOrchestrator,HostOperationPolicy
from backend.hub_agent import WireGuardAgentService,make_agent
from backend.wireguard_hub import WireGuardHubAdapter

class Row:
  def __init__(self,start,end,state='active'):
    self.period_start=start
    self.period_end=end
    self.state=state

class TermRuleTests(unittest.TestCase):
 def test_months_clamp_to_the_last_day(self):
  self.assertEqual(add_months(date(2026,1,31),1),date(2026,2,28))
  self.assertEqual(add_months(date(2026,11,15),3),date(2027,2,15))
  self.assertEqual(add_months(date(2026,10,11),12),date(2027,10,11))
 def test_warning_starts_seven_days_before_and_restriction_on_the_expiry_date(self):
  expiry=date(2026,10,20);row=Row(midnight(date(2026,9,20)),midnight(expiry))
  def at(d):return midnight(d)+12*3600
  self.assertFalse(term_status(row,at(expiry-timedelta(days=8)))['warning'])
  seven=term_status(row,at(expiry-timedelta(days=7)));self.assertTrue(seven['warning']);self.assertEqual(seven['days_left'],7);self.assertEqual(seven['expires_on'],'2026-10-20')
  last=term_status(row,midnight(expiry)-1);self.assertTrue(last['warning']);self.assertFalse(last['restricted'])
  day=term_status(row,midnight(expiry));self.assertTrue(day['restricted']);self.assertFalse(day['warning']);self.assertEqual(day['days_left'],0)
  self.assertTrue(is_restricted(row,at(expiry+timedelta(days=30))));self.assertTrue(is_restricted(None,at(expiry)))
 def test_early_renewal_keeps_remaining_days_and_late_renewal_starts_on_approval(self):
  row=Row(midnight(date(2026,9,20)),midnight(date(2026,10,20)))
  start,end,kept=renewal_term(row,1,midnight(date(2026,10,15))+3600)
  self.assertEqual((local_date(start),local_date(end),kept),(date(2026,10,20),date(2026,11,20),row.period_start))
  start,end,kept=renewal_term(row,3,midnight(date(2026,10,25))+3600)
  self.assertEqual((local_date(start),local_date(end)),(date(2026,10,25),date(2027,1,25)));self.assertEqual(kept,start)
  start,end,_=renewal_term(None,1,midnight(date(2026,10,25))+3600);self.assertEqual(local_date(end),date(2026,11,25))

class RestrictionLogicTests(unittest.TestCase):
 def test_no_subscription_is_restricted(self):
  now = midnight(date(2026,10,15)) + 12*3600
  self.assertTrue(is_restricted(None, now))
 def test_trial_not_expired_is_not_restricted(self):
  row = Row(midnight(date(2026,9,20)), midnight(date(2026,10,20)))
  row.state = 'trial'
  now = midnight(date(2026,10,15)) + 12*3600
  self.assertFalse(is_restricted(row, now))
 def test_trial_expired_is_restricted(self):
  row = Row(midnight(date(2026,9,20)), midnight(date(2026,10,20)))
  row.state = 'trial'
  now = midnight(date(2026,10,20)) + 12*3600
  self.assertTrue(is_restricted(row, now))
 def test_active_not_expired_is_not_restricted(self):
  row = Row(midnight(date(2026,9,20)), midnight(date(2026,10,20)))
  row.state = 'active'
  now = midnight(date(2026,10,15)) + 12*3600
  self.assertFalse(is_restricted(row, now))
 def test_active_expired_is_restricted(self):
  row = Row(midnight(date(2026,9,20)), midnight(date(2026,10,20)))
  row.state = 'active'
  now = midnight(date(2026,10,20)) + 12*3600
  self.assertTrue(is_restricted(row, now))
 def test_past_due_is_restricted_even_before_period_end(self):
  row = Row(midnight(date(2026,9,20)), midnight(date(2026,10,20)))
  row.state = 'past_due'
  now = midnight(date(2026,10,15)) + 12*3600
  self.assertTrue(is_restricted(row, now))
 def test_suspended_is_restricted(self):
  row = Row(midnight(date(2026,9,20)), midnight(date(2026,10,20)))
  row.state = 'suspended'
  now = midnight(date(2026,10,15)) + 12*3600
  self.assertTrue(is_restricted(row, now))
 def test_cancelled_is_restricted(self):
  row = Row(midnight(date(2026,9,20)), midnight(date(2026,10,20)))
  row.state = 'cancelled'
  now = midnight(date(2026,10,15)) + 12*3600
  self.assertTrue(is_restricted(row, now))
 def test_renewal_allowed_paths(self):
  allowed = ['/v1/me','/v1/auth/logout','/v1/auth/password','/v1/subscription',
             '/v1/subscription/plans','/v1/subscription/requests','/v1/account/sessions',
             '/v1/account/mfa']
  for path in allowed:
    self.assertTrue(renewal_allowed(path), f'{path} should be allowed')
  blocked = ['/v1/packages','/v1/orders','/v1/entitlements','/v1/audit']
  for path in blocked:
    self.assertFalse(renewal_allowed(path), f'{path} should be blocked')
 def test_staff_restricted_allowed_paths(self):
  allowed = ['/v1/me','/v1/auth/logout','/v1/auth/password']
  for path in allowed:
    self.assertTrue(staff_restricted_allowed(path), f'{path} should be allowed for staff')
  blocked = ['/v1/subscription','/v1/subscription/plans','/v1/subscription/requests',
             '/v1/account/sessions','/v1/account/mfa','/v1/account/password',
             '/v1/packages','/v1/orders','/v1/entitlements','/v1/audit']
  for path in blocked:
    self.assertFalse(staff_restricted_allowed(path), f'{path} should be blocked for staff')

class RenewalApiTests(unittest.TestCase):
 setUp=test_backend.AccountPaymentTests.setUp
 tearDown=test_backend.AccountPaymentTests.tearDown
 login=test_backend.AccountPaymentTests.login
 def owner_platform(self):
  with self.app.state.factory() as db:db.get(User,self.users['platform']).platform_owner=True;db.commit()
  return self.login('platform')
 def setup_plan(self,price=10000):
  p=self.owner_platform();plan=self.client.post('/v1/platform/subscription-plans',headers=p,json={'name':'Renewal test','monthly_price':price,'currency':'MMK','site_limit':2,'router_limit':3}).json()
  r=self.client.post('/v1/platform/subscription-payment',headers=p,json={'expected_revision':0,'destination':'Test platform account 000','instructions':'Test transfer only','methods':['KBZPay','Bank transfer']});self.assertEqual(r.status_code,200,r.text)
  return p,plan
 def request(self,o,plan,months=1,key='renewal-request-key-001',**extra):
  return self.client.post('/v1/subscription/requests',headers=o,json={'plan_id':plan['id'],'months':months,'method':'KBZPay','reference':'renewal-ref','evidence':'Test transfer receipt','request_key':key}|extra)
 def approve(self,p,v,**extra):
  return self.client.post('/v1/platform/subscription-invoices/'+v['id']+'/decision',headers=p,json={'expected_revision':v['revision'],'decision':'approved','reason':'Transfer confirmed (test)','confirmed_received':True}|extra)
 def set_term(self,tenant,plan,start,end,state='active'):
  with self.app.state.factory() as db:
    existing=db.get(TenantSubscription,tenant)
    now=int(time.time())
    values={'plan_id':plan['id'],'plan_snapshot':{},'state':state,'period_start':start,'period_end':end,'updated':now,'reason':'Test term'}
    if existing:
      existing.revision+=1
      for k,v in values.items():
        setattr(existing,k,v)
    else:
      db.add(TenantSubscription(tenant_id=tenant,revision=1,**values))
    db.commit()
 def tenant(self,name='owner'):
  with self.app.state.factory() as db:return db.get(User,self.users[name]).tenant_id

 def test_payment_details_are_owner_only_and_revisioned(self):
  plain=self.login('platform');owner=self.login('owner')
  for h in [plain,owner]:
   self.assertEqual(self.client.get('/v1/platform/subscription-payment',headers=h).status_code,403)
   self.assertEqual(self.client.post('/v1/platform/subscription-payment',headers=h,json={'expected_revision':0,'destination':'x','instructions':'y','methods':['Cash']}).status_code,403)
  p,_=self.setup_plan();self.assertEqual(self.client.get('/v1/platform/subscription-payment',headers=p).json()['revision'],1)
  self.assertEqual(self.client.post('/v1/platform/subscription-payment',headers=p,json={'expected_revision':0,'destination':'x','instructions':'y','methods':['Cash']}).status_code,409)
  self.assertEqual(self.client.post('/v1/platform/subscription-payment',headers=p,json={'expected_revision':1,'destination':'x','instructions':'y','methods':['Cash','Cash']}).status_code,422)
  with self.app.state.factory() as db:self.assertEqual(db.scalar(select(func.count()).select_from(Audit).where(Audit.action=='subscription_payment_details_saved')),1)

 def test_request_needs_published_details_and_stays_pending_until_owner_approval(self):
  o=self.login('owner');p=self.owner_platform();plan=self.client.post('/v1/platform/subscription-plans',headers=p,json={'name':'Early','monthly_price':5000,'currency':'MMK','site_limit':1,'router_limit':1}).json()
  self.assertEqual(self.request(o,plan).status_code,409)
  p,plan=self.setup_plan();view=self.client.get('/v1/subscription/plans',headers=o).json();self.assertEqual(view['months'],[1,12]);self.assertEqual(view['payment']['methods'],['KBZPay','Bank transfer'])
  self.assertEqual(self.request(o,plan,months=2).status_code,422);self.assertEqual(self.request(o,plan,method='Cash').status_code,422)
  r=self.request(o,plan,months=12);self.assertEqual(r.status_code,201,r.text);v=r.json();self.assertEqual((v['status'],v['amount'],v['snapshot']['months']),('pending',120000,12))
  self.assertTrue(self.request(o,plan,months=12).json()['replayed']);self.assertEqual(self.request(o,plan,months=1).status_code,409);self.assertEqual(self.request(o,plan,months=3,key='renewal-request-key-003').status_code,422)
  self.assertEqual(self.request(o,plan,key='renewal-request-key-002').status_code,409)
  self.assertEqual(self.client.get('/v1/subscription',headers=o).json()['state'],'active')
  self.assertEqual(self.approve(p,v,confirmed_received=False).status_code,422)
  with self.app.state.factory() as db:db.get(User,self.users['platform']).platform_owner=False;db.commit()
  self.assertEqual(self.approve(p,v).status_code,403)
  with self.app.state.factory() as db:db.get(User,self.users['platform']).platform_owner=True;db.commit()
  self.assertEqual(self.client.get('/v1/subscription/invoices',headers=self.login('other')).json(),[])

 def test_late_renewal_restores_access_from_the_approval_date_and_cannot_extend_twice(self):
  tenant=self.tenant();now=int(time.time());today=local_date(now);p,plan=self.setup_plan();self.set_term(tenant,plan,midnight(today-timedelta(days=40)),midnight(today-timedelta(days=3)))
  o=self.login('owner');me=self.client.get('/v1/me',headers=o).json();self.assertTrue(me['subscription_restricted'])
  self.assertEqual(self.client.get('/v1/packages',headers=o).status_code,403);self.assertEqual(self.client.get('/v1/account/sessions',headers=o).status_code,200)
  self.assertTrue(self.client.get('/v1/subscription',headers=o).json()['restricted'])
  self.assertFalse(self.client.get('/v1/me',headers=self.login('other')).json()['subscription_restricted'])
  v=self.request(o,plan,months=1).json();r=self.approve(p,v);self.assertEqual(r.status_code,200,r.text)
  sub=self.client.get('/v1/subscription',headers=o).json();self.assertEqual(local_date(sub['period_start']),today);self.assertEqual(local_date(sub['period_end']),add_months(today,1));self.assertFalse(sub['restricted'])
  self.assertEqual(r.json()['period_end'],sub['period_end']);self.assertFalse(self.client.get('/v1/me',headers=o).json()['subscription_restricted']);self.assertEqual(self.client.get('/v1/packages',headers=o).status_code,200)
  self.assertTrue(self.approve(p,v).json()['replayed']);self.assertEqual(self.approve(p,v|{'revision':2}).status_code,409)
  self.assertEqual(self.client.get('/v1/subscription',headers=o).json()['period_end'],sub['period_end'])

 def test_early_renewal_extends_from_the_current_expiry(self):
  tenant=self.tenant();today=local_date(int(time.time()));start=midnight(today-timedelta(days=20));expiry=today+timedelta(days=5);p,plan=self.setup_plan();self.set_term(tenant,plan,start,midnight(expiry))
  o=self.login('owner');status=self.client.get('/v1/subscription',headers=o).json();self.assertTrue(status['warning']);self.assertEqual(status['days_left'],5)
  v=self.request(o,plan,months=12).json();self.assertEqual(local_date(v['period_end']),add_months(expiry,12))
  self.assertEqual(self.approve(p,v).status_code,200);sub=self.client.get('/v1/subscription',headers=o).json()
  self.assertEqual(sub['period_start'],start);self.assertEqual(local_date(sub['period_end']),add_months(expiry,12));self.assertFalse(sub['warning'])
  with self.app.state.factory() as db:self.assertEqual(db.scalar(select(func.count()).select_from(BillingEvent)),2)

class RestrictionRouteTests(unittest.TestCase):
 setUp=test_backend.AccountPaymentTests.setUp
 tearDown=test_backend.AccountPaymentTests.tearDown
 login=test_backend.AccountPaymentTests.login
 def setUp(self):
  test_backend.AccountPaymentTests.setUp(self)
  self.today = local_date(int(time.time()))
 def owner_platform(self):
  with self.app.state.factory() as db:
    db.get(User,self.users['platform']).platform_owner=True
    db.commit()
  return self.login('platform')
 def setup_plan(self,price=10000):
  p=self.owner_platform()
  plan=self.client.post('/v1/platform/subscription-plans',headers=p,json={'name':'Test plan','monthly_price':price,'currency':'MMK','site_limit':2,'router_limit':3}).json()
  r=self.client.post('/v1/platform/subscription-payment',headers=p,json={'expected_revision':0,'destination':'Test','instructions':'Test','methods':['KBZPay']})
  self.assertEqual(r.status_code,200,r.text)
  return p,plan
 def request(self,o,plan,months=1,key='renewal-request-key-001',**extra):
  return self.client.post('/v1/subscription/requests',headers=o,json={'plan_id':plan['id'],'months':months,'method':'KBZPay','reference':'renewal-ref','evidence':'Test transfer receipt','request_key':key}|extra)
 def approve(self,p,v,**extra):
  return self.client.post('/v1/platform/subscription-invoices/'+v['id']+'/decision',headers=p,json={'expected_revision':v['revision'],'decision':'approved','reason':'Transfer confirmed (test)','confirmed_received':True}|extra)
 def set_term(self,tenant,plan,start,end,state='active'):
  with self.app.state.factory() as db:
    existing=db.get(TenantSubscription,tenant)
    now=int(time.time())
    values={'plan_id':plan['id'],'plan_snapshot':{},'state':state,'period_start':start,'period_end':end,'updated':now,'reason':'Test'}
    if existing:
      existing.revision+=1
      for k,v in values.items():
        setattr(existing,k,v)
    else:
      db.add(TenantSubscription(tenant_id=tenant,revision=1,**values))
    db.commit()
 def tenant(self,name='owner'):
  with self.app.state.factory() as db:
    return db.get(User,self.users[name]).tenant_id
 def add_staff(self,username='staff',profile='manager'):
  with self.app.state.factory() as db:
    u=User(username=username,role='sme',tenant_id=self.users_tenant,password_hash=HASHER.hash('test'))
    db.add(u);db.flush()
    db.add(StaffGrant(user_id=u.id,tenant_id=self.users_tenant,profile=profile,revision=1,last_reason='',created_by=self.users['owner'],request_key='staff-key',request_hash='hash',created=int(time.time()),updated=int(time.time())))
    db.commit()
    return u.id
 @property
 def users_tenant(self):
  with self.app.state.factory() as db:
    return db.get(User,self.users['owner']).tenant_id
 def tenant_without_subscription(self):
  with self.app.state.factory() as db:
    t=Tenant(name='NoSubShop')
    db.add(t);db.flush()
    u=User(username='nosubowner',role='sme',tenant_id=t.id,password_hash=HASHER.hash('test'))
    db.add(u);db.flush()
    db.commit()
    return t.id, u.id
 def login_user(self, user_id):
  with self.app.state.factory() as db:
    u=db.get(User,user_id)
  return self.client.post('/v1/auth/login',json={'username':u.username,'password':'test'}).json()['access_token']

 def test_owner_expired_shop_allowed_routes(self):
  p,plan=self.setup_plan()
  self.set_term(self.tenant(),plan,midnight(self.today-timedelta(days=40)),midnight(self.today-timedelta(days=3)))
  o=self.login('owner')
  self.assertEqual(self.client.get('/v1/me',headers=o).status_code,200)
  self.assertTrue(self.client.get('/v1/me',headers=o).json()['subscription_restricted'])
  self.assertEqual(self.client.get('/v1/subscription',headers=o).status_code,200)
  self.assertEqual(self.client.get('/v1/account/sessions',headers=o).status_code,200)
  self.assertEqual(self.client.get('/v1/packages',headers=o).status_code,403)

 def test_owner_past_due_shop_allowed_routes(self):
  p,plan=self.setup_plan()
  self.set_term(self.tenant(),plan,midnight(self.today-timedelta(days=40)),midnight(self.today+timedelta(days=10)),state='past_due')
  o=self.login('owner')
  self.assertEqual(self.client.get('/v1/me',headers=o).status_code,200)
  self.assertTrue(self.client.get('/v1/me',headers=o).json()['subscription_restricted'])
  self.assertEqual(self.client.get('/v1/subscription',headers=o).status_code,200)
  self.assertEqual(self.client.get('/v1/packages',headers=o).status_code,403)

 def test_owner_suspended_shop_allowed_routes(self):
  p,plan=self.setup_plan()
  self.set_term(self.tenant(),plan,midnight(self.today-timedelta(days=40)),midnight(self.today+timedelta(days=10)),state='suspended')
  o=self.login('owner')
  self.assertEqual(self.client.get('/v1/me',headers=o).status_code,200)
  self.assertTrue(self.client.get('/v1/me',headers=o).json()['subscription_restricted'])
  self.assertEqual(self.client.get('/v1/subscription',headers=o).status_code,200)
  self.assertEqual(self.client.get('/v1/packages',headers=o).status_code,403)

 def test_owner_no_subscription_shop_allowed_routes(self):
  tenant_id, user_id = self.tenant_without_subscription()
  token = self.login_user(user_id)
  h = {'Authorization': 'Bearer ' + token}
  self.assertEqual(self.client.get('/v1/me', headers=h).status_code, 200)
  self.assertTrue(self.client.get('/v1/me', headers=h).json()['subscription_restricted'])
  self.assertEqual(self.client.get('/v1/subscription', headers=h).status_code, 200)
  self.assertEqual(self.client.get('/v1/subscription', headers=h).json()['state'], 'unassigned')
  self.assertEqual(self.client.get('/v1/packages', headers=h).status_code, 403)

 def test_staff_expired_shop_allowed_routes(self):
  p,plan=self.setup_plan()
  self.set_term(self.tenant(),plan,midnight(self.today-timedelta(days=40)),midnight(self.today-timedelta(days=3)))
  staff_id=self.add_staff()
  with self.app.state.factory() as db:
    u=db.get(User,staff_id)
  staff_token=self.client.post('/v1/auth/login',json={'username':'staff','password':'test'}).json()['access_token']
  h={'Authorization':'Bearer '+staff_token}
  self.assertEqual(self.client.get('/v1/me',headers=h).status_code,200)
  self.assertTrue(self.client.get('/v1/me',headers=h).json()['subscription_restricted'])
  self.assertEqual(self.client.get('/v1/subscription',headers=h).status_code,403)
  self.assertEqual(self.client.post('/v1/subscription/requests',headers=h,json={'plan_id':plan['id'],'months':1,'method':'KBZPay','reference':'r','evidence':'e','request_key':'staff-req-1'}).status_code,403)
  self.assertEqual(self.client.get('/v1/packages',headers=h).status_code,403)
  self.assertEqual(self.client.get('/v1/account/sessions',headers=h).status_code,403)

 def test_locked_staff_with_temporary_password_can_change_it_and_reach_me(self):
  p,plan=self.setup_plan()
  self.set_term(self.tenant(),plan,midnight(self.today-timedelta(days=40)),midnight(self.today-timedelta(days=3)))
  staff_id=self.add_staff()
  with self.app.state.factory() as db:
    u=db.get(User,staff_id);u.must_change_password=True;u.temporary_password_expires=int(time.time())+86400;db.commit()
  response=self.client.post('/v1/auth/login',json={'username':'staff','password':'test'})
  self.assertEqual(response.status_code,200,response.text)
  h={'Authorization':'Bearer '+response.json()['access_token']}
  self.assertTrue(self.client.get('/v1/me',headers=h).json()['must_change_password'])
  changed=self.client.post('/v1/auth/password',headers=h,json={'current_password':'test','new_password':'locked-staff-personal-password'})
  self.assertEqual(changed.status_code,200,changed.text)
  me=self.client.get('/v1/me',headers=h)
  self.assertEqual(me.status_code,200,me.text);self.assertFalse(me.json()['must_change_password']);self.assertTrue(me.json()['subscription_restricted'])

 def test_staff_past_due_shop_allowed_routes(self):
  p,plan=self.setup_plan()
  self.set_term(self.tenant(),plan,midnight(self.today-timedelta(days=40)),midnight(self.today+timedelta(days=10)),state='past_due')
  self.add_staff()
  staff_token=self.client.post('/v1/auth/login',json={'username':'staff','password':'test'}).json()['access_token']
  h={'Authorization':'Bearer '+staff_token}
  self.assertEqual(self.client.get('/v1/me',headers=h).status_code,200)
  self.assertTrue(self.client.get('/v1/me',headers=h).json()['subscription_restricted'])
  self.assertEqual(self.client.get('/v1/subscription',headers=h).status_code,403)

 def test_staff_suspended_shop_allowed_routes(self):
  p,plan=self.setup_plan()
  self.set_term(self.tenant(),plan,midnight(self.today-timedelta(days=40)),midnight(self.today+timedelta(days=10)),state='suspended')
  self.add_staff()
  staff_token=self.client.post('/v1/auth/login',json={'username':'staff','password':'test'}).json()['access_token']
  h={'Authorization':'Bearer '+staff_token}
  self.assertEqual(self.client.get('/v1/me',headers=h).status_code,200)
  self.assertTrue(self.client.get('/v1/me',headers=h).json()['subscription_restricted'])
  self.assertEqual(self.client.get('/v1/subscription',headers=h).status_code,403)

 def test_staff_no_subscription_shop_allowed_routes(self):
  tenant_id, owner_id = self.tenant_without_subscription()
  with self.app.state.factory() as db:
    u = User(username='nosubstaff', role='sme', tenant_id=tenant_id, password_hash=HASHER.hash('test'))
    db.add(u); db.flush()
    db.add(StaffGrant(user_id=u.id, tenant_id=tenant_id, profile='manager', revision=1, last_reason='', created_by=owner_id, request_key='staff-key', request_hash='hash', created=int(time.time()), updated=int(time.time())))
    db.commit()
    staff_id = u.id
  staff_token = self.client.post('/v1/auth/login', json={'username': 'nosubstaff', 'password': 'test'}).json()['access_token']
  h = {'Authorization': 'Bearer ' + staff_token}
  self.assertEqual(self.client.get('/v1/me', headers=h).status_code, 200)
  self.assertTrue(self.client.get('/v1/me', headers=h).json()['subscription_restricted'])
  self.assertEqual(self.client.get('/v1/subscription', headers=h).status_code, 403)

 def test_owner_active_shop_fully_allowed(self):
  p,plan=self.setup_plan()
  self.set_term(self.tenant(),plan,midnight(self.today-timedelta(days=20)),midnight(self.today+timedelta(days=10)))
  o=self.login('owner')
  self.assertEqual(self.client.get('/v1/me',headers=o).status_code,200)
  self.assertFalse(self.client.get('/v1/me',headers=o).json()['subscription_restricted'])
  self.assertEqual(self.client.get('/v1/subscription',headers=o).status_code,200)
  self.assertEqual(self.client.get('/v1/packages',headers=o).status_code,200)
  self.assertEqual(self.client.get('/v1/account/sessions',headers=o).status_code,200)

 def test_owner_trial_shop_not_expired_fully_allowed(self):
  p,plan=self.setup_plan()
  self.set_term(self.tenant(),plan,midnight(self.today-timedelta(days=20)),midnight(self.today+timedelta(days=10)),state='trial')
  o=self.login('owner')
  self.assertEqual(self.client.get('/v1/me',headers=o).status_code,200)
  self.assertFalse(self.client.get('/v1/me',headers=o).json()['subscription_restricted'])
  self.assertEqual(self.client.get('/v1/packages',headers=o).status_code,200)

 def test_staff_active_shop_fully_allowed(self):
  p,plan=self.setup_plan()
  self.set_term(self.tenant(),plan,midnight(self.today-timedelta(days=20)),midnight(self.today+timedelta(days=10)))
  self.add_staff()
  staff_token=self.client.post('/v1/auth/login',json={'username':'staff','password':'test'}).json()['access_token']
  h={'Authorization':'Bearer '+staff_token}
  self.assertEqual(self.client.get('/v1/me',headers=h).status_code,200)
  self.assertFalse(self.client.get('/v1/me',headers=h).json()['subscription_restricted'])
  self.assertEqual(self.client.get('/v1/packages',headers=h).status_code,403)
  self.assertEqual(self.client.get('/v1/account/sessions',headers=h).status_code,403)
  self.assertEqual(self.client.post('/v1/auth/logout',headers=h).status_code,200)

 def test_platform_user_unaffected(self):
  p,plan=self.setup_plan()
  plat=self.login('platform')
  self.assertEqual(self.client.get('/v1/me',headers=plat).status_code,200)
  self.assertFalse(self.client.get('/v1/me',headers=plat).json().get('subscription_restricted',False))
  self.assertEqual(self.client.get('/v1/platform/subscriptions',headers=plat).status_code,200)

 def test_past_due_renewal_extends_from_period_end(self):
  p,plan=self.setup_plan()
  tenant=self.tenant()
  today=self.today
  self.set_term(tenant,plan,midnight(today-timedelta(days=40)),midnight(today+timedelta(days=10)),state='past_due')
  o=self.login('owner')
  self.assertTrue(self.client.get('/v1/me',headers=o).json()['subscription_restricted'])
  v=self.request(o,plan,months=1).json()
  r=self.approve(p,v)
  self.assertEqual(r.status_code,200,r.text)
  sub=self.client.get('/v1/subscription',headers=o).json()
  self.assertEqual(local_date(sub['period_start']),today-timedelta(days=40))
  self.assertEqual(local_date(sub['period_end']),add_months(today+timedelta(days=10),1))
  self.assertFalse(sub['restricted'])

 def test_locked_shop_voucher_redeem_succeeds(self):
  p,plan=self.setup_plan()
  o=self.login('owner')
  state=self.client.get('/v1/portal',headers=o).json()
  cfg={**state['draft'],'voucher_login':True}
  self.client.post('/v1/portal/draft',headers=o,json={'expected_revision':state['revision'],'settings':cfg})
  self.client.post('/v1/portal/publish',headers=o,json={'expected_revision':state['revision']+1})
  r=self.client.post('/v1/packages',headers=o,json={'name':'Combo','service':'internet','mode':'both','price':3000,'gb':5,'hours':3});self.assertEqual(r.status_code,201);pkg=r.json()['id']
  body={'package_id':pkg,'expires_days':30,'request_key':'voucher-locked-test-001'}
  v=self.client.post('/v1/vouchers',headers=o,json=body).json()
  self.assertTrue(v['code'])
  self.set_term(self.tenant(),plan,midnight(self.today-timedelta(days=40)),midnight(self.today-timedelta(days=3)))
  self.assertTrue(self.client.get('/v1/me',headers=o).json()['subscription_restricted'])
  guest_token=self.client.post('/v1/auth/login',json={'username':'guest','password':'test-password-only'}).json()['access_token']
  h={'Authorization':'Bearer '+guest_token}
  r=self.client.post('/v1/vouchers/redeem',headers=h,json={'code':v['code']})
  self.assertEqual(r.status_code,200,r.text)
  self.assertEqual(r.json()['fulfillment'],'pending_adapter')

 def test_locked_shop_hub_peer_unchanged(self):
  p,plan=self.setup_plan()
  o=self.login('owner')
  self.app.state.magic_connect_pairing_enabled=True
  with self.app.state.factory() as db:
    owner_user=db.get(User,self.users['owner'])
    t=owner_user.tenant_id
    hub=MagicHub(name='Test Hub',endpoint='https://hub.test',port=51820,public_key='A'*44,pool='10.90.0.0/24',next_host=2,interface_name='wg-mm',created=int(time.time()))
    db.add(hub);db.flush()
    db.add(HubAssignment(tenant_id=t,hub_id=hub.id,created=int(time.time())))
    site=Site(name='Main',tenant_id=t,created=int(time.time()))
    db.add(site);db.flush()
    router=RouterDevice(name='Test Router',tenant_id=t,site_id=site.id,registered_by=self.users['owner'],created=int(time.time()))
    db.add(router);db.flush()
    plan_obj=RouterPlan(tenant_id=t,router_id=router.id,hub_id=hub.id,router_public_key='B'*44,address='10.90.0.2',snapshot={'version':1,'hub':{'id':hub.id,'endpoint':hub.endpoint,'port':hub.port,'public_key':hub.public_key,'hub_address':'10.90.0.1'},'router':{'id':router.id,'site_id':site.id,'public_key':'B'*44,'interface':'wg-mm','address':'10.90.0.2/32','peer_allowed_addresses':['10.90.0.1/32'],'routes':[{'destination':'10.90.0.1/32','interface':'wg-mm'}],'persistent_keepalive_seconds':25},'hub_peer':{'public_key':'B'*44,'allowed_addresses':['10.90.0.2/32']},'private_key_location':'router_only','guest_traffic_via_hub':False},created=int(time.time()),reviewed_at=int(time.time()),lifecycle_state='awaiting_bootstrap')
    db.add(plan_obj);db.flush()
    attempt=MagicConnectAttempt(tenant_id=t,site_id=site.id,owner_id=self.users['owner'],router_name='Test Router',code_hash='hash',comparison_code='123456',status='approved',enrollment_state='pairing_approved',state_changed_at=int(time.time()),created=int(time.time()),expires=int(time.time())+3600,approved_at=int(time.time()),claimed_at=int(time.time()),router_id=router.id)
    db.add(attempt);db.flush()
    enrollment=MagicConnectEnrollment(plan_id=plan_obj.id,attempt_id=attempt.id,tenant_id=t,site_id=site.id,owner_id=self.users['owner'],expected_serial_digest='serial',created=int(time.time()))
    db.add(enrollment);db.commit()
    plan_id=plan_obj.id
  class FakeAdapter(WireGuardHubAdapter):
   def __init__(self):
    self.peer_present=False
    self.last_provision=None
    self.revoke_calls=[]
   def verify_hub_identity(self,interface,expected_public_key):
    return True
   def provision_peer(self,interface,public_key,address,pool):
    self.peer_present=True
    self.last_provision=(interface,public_key,address,pool)
    return {'result':'provisioned','peer_present':True,'allowed_address':address,'configuration_modified':True}
   def observe_peer(self,interface,public_key,address,pool,recent_seconds=180):
    return {'evidence_source':'dedicated_hub_agent_live_read','observed_at':int(time.time()),'peer_found':self.peer_present,'allowed_address_match':self.peer_present,'last_handshake_at':int(time.time())-10,'handshake_age_seconds':10,'fresh_handshake':True,'recent_threshold_seconds':recent_seconds}
   def revoke_peer(self,interface,public_key,address,pool):
    self.revoke_calls.append((interface,public_key,address,pool))
    self.peer_present=False
    return {'result':'revoked','peer_present':False,'configuration_modified':True}
  with patch.dict(os.environ,{'MIKROMAGIC_ENVIRONMENT':'isolated-magic-connect-test','MIKROMAGIC_HUB_DEDICATED_INTERFACE':'wg-mm'},clear=False):
    adapter=FakeAdapter()
    self.app.state.magic_hub_orchestrator=HubPeerOrchestrator(adapter,HostOperationPolicy('isolated-magic-connect-test',True,True,'wg-mm'))
    provision=self.client.post(f'/v1/router-plans/{plan_id}/hub-peer/provision',headers=o,json={'confirmed':True,'idempotency_key':'hub-peer-test-001'})
    self.assertEqual(provision.status_code,200,provision.text)
    self.assertTrue(adapter.peer_present)
  with self.app.state.factory() as db:
   row=db.get(RouterPlan,plan_id)
   peer_state=(row.hub_id,row.router_public_key,row.address,row.snapshot,row.lifecycle_state,row.peer_operation_key,row.last_failure_code,row.handshake_verified_at)
  self.set_term(self.tenant(),plan,midnight(self.today-timedelta(days=40)),midnight(self.today-timedelta(days=3)))
  o=self.login('owner')
  self.assertTrue(self.client.get('/v1/me',headers=o).json()['subscription_restricted'])
  with patch.dict(os.environ,{'MIKROMAGIC_ENVIRONMENT':'isolated-magic-connect-test','MIKROMAGIC_HUB_DEDICATED_INTERFACE':'wg-mm'},clear=False):
    self.app.state.magic_hub_orchestrator=HubPeerOrchestrator(adapter,HostOperationPolicy('isolated-magic-connect-test',True,True,'wg-mm'))
    observed=self.client.post(f'/v1/router-plans/{plan_id}/hub-peer/observe',headers=o)
    self.assertEqual(observed.status_code,403,observed.text)
  self.assertTrue(adapter.peer_present)
  self.assertEqual(adapter.revoke_calls,[])
  with self.app.state.factory() as db:
   row=db.get(RouterPlan,plan_id)
   self.assertEqual((row.hub_id,row.router_public_key,row.address,row.snapshot,row.lifecycle_state,row.peer_operation_key,row.last_failure_code,row.handshake_verified_at),peer_state)

 def test_locked_shop_hub_checkin_succeeds(self):
  p,plan=self.setup_plan()
  self.set_term(self.tenant(),plan,midnight(self.today-timedelta(days=40)),midnight(self.today-timedelta(days=3)))
  o=self.login('owner');self.assertTrue(self.client.get('/v1/me',headers=o).json()['subscription_restricted'])
  with tempfile.TemporaryDirectory() as name:
   root=Path(name);private=root/'private';private.write_text('synthetic-test-only')
   runner=test_hub_agent.Runner();service=WireGuardAgentService('mm-prod-hub',private,root/'state'/'peers.json',runner=runner,clock=lambda:1000)
   service.initialize('10.90.1.1/24',51820);service.provision(test_hub_agent.key(2),'10.90.1.2/32','10.90.1.0/24');runner.handshake=950
   client=TestClient(make_agent(service,'t'*48));payload={'interface':'mm-prod-hub','public_key':test_hub_agent.key(2),'address':'10.90.1.2/32','pool':'10.90.1.0/24'}
   response=client.post('/v1/peers/observe',headers={'Authorization':'Bearer '+'t'*48},json=payload)
   self.assertEqual(response.status_code,200,response.text);self.assertTrue(response.json()['peer_found']);self.assertTrue(response.json()['fresh_handshake'])

 def test_locked_shop_router_list_blocked(self):
  p,plan=self.setup_plan()
  self.set_term(self.tenant(),plan,midnight(self.today-timedelta(days=40)),midnight(self.today-timedelta(days=3)))
  o=self.login('owner')
  self.assertEqual(self.client.get('/v1/routers',headers=o).status_code,403)
  self.add_staff()
  staff_token=self.client.post('/v1/auth/login',json={'username':'staff','password':'test'}).json()['access_token']
  h={'Authorization':'Bearer '+staff_token}
  self.assertEqual(self.client.get('/v1/routers',headers=h).status_code,403)

 def test_active_shop_staff_allowed_same_as_locked(self):
  p,plan=self.setup_plan()
  self.set_term(self.tenant(),plan,midnight(self.today-timedelta(days=20)),midnight(self.today+timedelta(days=10)))
  self.add_staff()
  staff_token=self.client.post('/v1/auth/login',json={'username':'staff','password':'test'}).json()['access_token']
  h={'Authorization':'Bearer '+staff_token}
  self.assertEqual(self.client.get('/v1/me',headers=h).status_code,200)
  self.assertFalse(self.client.get('/v1/me',headers=h).json()['subscription_restricted'])
  self.assertEqual(self.client.post('/v1/auth/logout',headers=h).status_code,200)
  staff_token=self.client.post('/v1/auth/login',json={'username':'staff','password':'test'}).json()['access_token']
  h={'Authorization':'Bearer '+staff_token}
  self.assertEqual(self.client.get('/v1/account/sessions',headers=h).status_code,403)

if __name__=='__main__':unittest.main()
