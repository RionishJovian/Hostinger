import time,unittest
from datetime import date,timedelta
import test_backend
from sqlalchemy import select,func
from backend.models import User,TenantSubscription,SubscriptionInvoice,BillingEvent,Audit
from backend.subscriptions import add_months,midnight,local_date,term_status,renewal_term,is_restricted

class Row:
 def __init__(self,start,end):self.period_start=start;self.period_end=end

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
  self.assertTrue(is_restricted(row,at(expiry+timedelta(days=30))));self.assertFalse(is_restricted(None,at(expiry)))
 def test_early_renewal_keeps_remaining_days_and_late_renewal_starts_on_approval(self):
  row=Row(midnight(date(2026,9,20)),midnight(date(2026,10,20)))
  start,end,kept=renewal_term(row,1,midnight(date(2026,10,15))+3600)
  self.assertEqual((local_date(start),local_date(end),kept),(date(2026,10,20),date(2026,11,20),row.period_start))
  start,end,kept=renewal_term(row,3,midnight(date(2026,10,25))+3600)
  self.assertEqual((local_date(start),local_date(end)),(date(2026,10,25),date(2027,1,25)));self.assertEqual(kept,start)
  start,end,_=renewal_term(None,1,midnight(date(2026,10,25))+3600);self.assertEqual(local_date(end),date(2026,11,25))

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
 def set_term(self,tenant,plan,start,end):
  with self.app.state.factory() as db:
   db.add(TenantSubscription(tenant_id=tenant,revision=1,plan_id=plan['id'],plan_snapshot={},state='active',period_start=start,period_end=end,updated=start,reason='Test term'));db.commit()
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
  self.assertEqual(self.client.get('/v1/subscription',headers=o).json()['state'],'unassigned')
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

if __name__=='__main__':unittest.main()
