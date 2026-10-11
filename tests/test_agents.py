import unittest
import test_backend
from sqlalchemy import select
from backend.models import User,Audit,AgentCommission,LoginAttempt

class AgentTests(unittest.TestCase):
 setUp=test_backend.AccountPaymentTests.setUp
 tearDown=test_backend.AccountPaymentTests.tearDown
 login=test_backend.AccountPaymentTests.login
 def developer(self):
  with self.app.state.factory() as db:db.get(User,self.users['platform']).platform_owner=True;db.commit()
  return self.login('platform')
 def apply(self,username='agent.one',**kw):
  return self.client.post('/v1/agent-applications',json={'username':username,'password':'agent-test-pass','full_name':'Agent One (test)','phone':'09 123 4567','note':'Test application'}|kw)
 def agent_login(self,username='agent.one'):
  r=self.client.post('/v1/auth/login',json={'username':username,'password':'agent-test-pass'});self.assertEqual(r.status_code,200,r.text);return {'Authorization':'Bearer '+r.json()['access_token']}
 def decide(self,dev,agent_id,status,reason='',revision=None):
  if revision is None:revision=next(a for a in self.client.get('/v1/developer/agents',headers=dev).json() if a['id']==agent_id)['revision']
  return self.client.post('/v1/developer/agents/'+agent_id+'/decision',headers=dev,json={'expected_revision':revision,'status':status,'reason':reason})
 def approved_agent(self,dev,username='agent.one'):
  self.assertEqual(self.apply(username).status_code,201);h=self.agent_login(username);me=self.client.get('/v1/me',headers=h).json()
  self.assertEqual(self.decide(dev,me['id'],'approved').status_code,200);return h,me['id']
 def business(self,h,name='Agent Cafe',owner='agent.cafe.owner',key='agent-business-key-0001'):
  return self.client.post('/v1/agent/businesses',headers=h,json={'name':name,'owner_username':owner,'request_key':key})
 def activate_owner(self,created):
  r=self.client.post('/v1/auth/login',json={'username':created['owner']['username'],'password':created['temporary_password']});self.assertEqual(r.status_code,200,r.text)
  h={'Authorization':'Bearer '+r.json()['access_token']}
  r=self.client.post('/v1/auth/password',headers=h,json={'current_password':created['temporary_password'],'new_password':'owner-new-pass'});self.assertEqual(r.status_code,200,r.text);return h
 def plan(self,dev,price=30000):
  plan=self.client.post('/v1/platform/subscription-plans',headers=dev,json={'name':'Agent test plan','monthly_price':price,'currency':'MMK','site_limit':2,'router_limit':3}).json()
  self.assertEqual(self.client.post('/v1/platform/subscription-payment',headers=dev,json={'expected_revision':0,'destination':'Test platform account 000','instructions':'Test transfer only','methods':['KBZPay']}).status_code,200);return plan
 def pay(self,dev,owner,plan,months,key):
  v=self.client.post('/v1/subscription/requests',headers=owner,json={'plan_id':plan['id'],'months':months,'method':'KBZPay','reference':'agent-ref-'+key[-3:],'evidence':'Test receipt','request_key':key});self.assertEqual(v.status_code,201,v.text);v=v.json()
  r=self.client.post('/v1/platform/subscription-invoices/'+v['id']+'/decision',headers=dev,json={'expected_revision':v['revision'],'decision':'approved','reason':'Received (test)','confirmed_received':True});self.assertEqual(r.status_code,200,r.text);return r.json()
 def refund(self,h,v,**kw):
  return self.client.post('/v1/platform/subscription-invoices/'+v['id']+'/refund',headers=h,json={'expected_revision':v['revision'],'reason':'Refunded (test)','confirmed_returned':True}|kw)

 def test_applications_need_owner_approval_and_agents_stay_in_their_area(self):
  for bad in [{'username':'X'},{'phone':'call me'},{'password':'123'},{'full_name':''}]:self.assertEqual(self.apply(**bad).status_code,422,bad)
  self.assertEqual(self.apply('owner').status_code,409)
  r=self.apply();self.assertEqual(r.status_code,201,r.text);self.assertEqual(r.json(),{'username':'agent.one','status':'pending'})
  self.assertEqual(self.apply().status_code,409)
  h=self.agent_login();profile=self.client.get('/v1/agent/profile',headers=h).json()
  self.assertEqual((profile['status'],profile['rates'],profile['minimum_withdrawal']),('pending',{'monthly':20,'annual':30},10000))
  self.assertEqual(self.business(h).status_code,403)
  for path in ['/v1/tenants','/v1/packages','/v1/orders','/v1/platform/businesses','/v1/developer/agents','/v1/subscription','/v1/sites','/v1/audit']:
   self.assertEqual(self.client.get(path,headers=h).status_code,403,path)
  for who in ['owner','guest','platform']:
   x=self.login(who);self.assertEqual(self.client.get('/v1/agent/profile',headers=x).status_code,403);self.assertEqual(self.client.get('/v1/developer/agents',headers=x).status_code,403)
  dev=self.developer();agent_id=profile['id']
  self.assertEqual(self.decide(dev,agent_id,'rejected').status_code,422)
  self.assertEqual(self.decide(dev,agent_id,'suspended','x').status_code,409)
  self.assertEqual(self.decide(dev,agent_id,'approved',revision=5).status_code,409)
  self.assertEqual(self.decide(dev,agent_id,'approved').status_code,200)
  self.assertEqual(self.client.get('/v1/agent/profile',headers=h).json()['status'],'approved')
  self.assertEqual(self.decide(dev,agent_id,'suspended','Test suspension').status_code,200)
  self.assertEqual(self.business(h).json()['detail'],'Your Agent account is suspended')
  roles=self.client.get('/v1/developer/roles',headers=dev).json()['roles']
  self.assertEqual(next(r for r in roles if r['key']=='agent')['accounts'],[{'username':'agent.one','active':False,'status':'suspended'}])
  with self.app.state.factory() as db:self.assertEqual(sorted(db.scalars(select(Audit.action).where(Audit.action.like('agent_%'))).all()),['agent_applied','agent_approved','agent_suspended'])

 def test_applications_are_rate_limited_per_network(self):
  for i in range(5):self.assertEqual(self.apply('agent.rate'+str(i)).status_code,201)
  self.assertEqual(self.apply('agent.rate9').status_code,429)

 def test_agent_registers_a_business_with_a_one_time_password_and_no_access_to_it(self):
  dev=self.developer();h,agent_id=self.approved_agent(dev);other,_=self.approved_agent(dev,'agent.two')
  r=self.business(h);self.assertEqual(r.status_code,201,r.text);created=r.json()
  self.assertTrue(created['shown_once']);self.assertEqual(len(created['temporary_password']),24);self.assertTrue(created['owner']['must_change_password'])
  replay=self.business(h).json();self.assertTrue(replay['replayed']);self.assertNotIn('temporary_password',replay)
  self.assertEqual(self.business(h,name='Different').status_code,409)
  rows=self.client.get('/v1/agent/businesses',headers=h).json();self.assertEqual([(b['name'],b['owner_username'],b['owner_signed_in']) for b in rows],[('Agent Cafe','agent.cafe.owner',False)])
  self.assertEqual(self.client.get('/v1/agent/businesses',headers=other).json(),[])
  self.activate_owner(created)
  self.assertTrue(self.client.get('/v1/agent/businesses',headers=h).json()[0]['owner_signed_in'])
  self.assertEqual(self.client.get('/v1/tenants',headers=h).status_code,403)
  links=self.client.get('/v1/developer/agent-businesses',headers=dev).json();self.assertEqual([(l['business'],l['agent']) for l in links],[('Agent Cafe','agent.one')])
  with self.app.state.factory() as db:
   audit=' '.join(db.scalars(select(Audit.target)).all());self.assertNotIn(created['temporary_password'],audit)

 def test_commissions_follow_list_price_and_reverse_on_refund(self):
  dev=self.developer();h,agent_id=self.approved_agent(dev);plan=self.plan(dev)
  owner=self.activate_owner(self.business(h).json())
  monthly=self.pay(dev,owner,plan,1,'agent-pay-key-0000001');annual=self.pay(dev,owner,plan,12,'agent-pay-key-0000012')
  self.pay(dev,self.login('owner'),plan,1,'agent-pay-key-0000099')
  rows=self.client.get('/v1/agent/commissions',headers=h).json()
  self.assertEqual(sorted((c['months'],c['rate_percent'],c['base_amount'],c['amount'],c['state']) for c in rows),[(1,20,30000,6000,'earned'),(12,30,360000,108000,'earned')])
  self.assertEqual(self.client.get('/v1/agent/profile',headers=h).json()['balances'],[{'currency':'MMK','earned':114000,'reversed':0,'reserved':0,'paid':0,'available':114000}])
  self.assertEqual(self.refund(dev,monthly,confirmed_returned=False).status_code,422)
  operator=self.login('platform')
  with self.app.state.factory() as db:db.get(User,self.users['platform']).platform_owner=False;db.commit()
  self.assertEqual(self.refund(operator,monthly).status_code,403)
  dev=self.developer()
  r=self.refund(dev,monthly);self.assertEqual(r.status_code,200,r.text);self.assertEqual((r.json()['status'],r.json()['commission_reversed']),('refunded',True))
  self.assertEqual(self.refund(dev,r.json()).status_code,409)
  balance=self.client.get('/v1/agent/profile',headers=h).json()['balances'][0];self.assertEqual((balance['earned'],balance['reversed'],balance['available']),(108000,6000,108000))
  with self.app.state.factory() as db:
   self.assertEqual(db.scalar(select(AgentCommission.reversal_reason).where(AgentCommission.invoice_id==monthly['id'])),'Refunded (test)')
  self.assertEqual(len(self.client.get('/v1/developer/agent-commissions',headers=dev).json()),2)

 def test_withdrawals_are_reserved_reviewed_and_paid_manually(self):
  dev=self.developer();h,agent_id=self.approved_agent(dev);plan=self.plan(dev,price=50000)
  owner=self.activate_owner(self.business(h).json());v=self.pay(dev,owner,plan,1,'agent-pay-key-0000101')
  def ask(amount,key,method='kbzpay'):return self.client.post('/v1/agent/withdrawals',headers=h,json={'amount':amount,'method':method,'request_key':key})
  self.assertEqual(ask(10000,'withdraw-key-00000001').status_code,422)
  self.assertEqual(self.client.post('/v1/agent/wallets',headers=h,json={'method':'bank','account_name':'A','account_number':'0912345678'}).status_code,422)
  self.assertEqual(self.client.post('/v1/agent/wallets',headers=h,json={'method':'kbzpay','account_name':'Agent One','account_number':'09 123 4567'}).status_code,200)
  self.assertEqual(ask(9999,'withdraw-key-00000002').status_code,422)
  self.assertEqual(ask(10001,'withdraw-key-00000003').json()['detail'],'Only 10,000 MMK is available to withdraw')
  first=ask(10000,'withdraw-key-00000004');self.assertEqual(first.status_code,201,first.text);first=first.json()
  self.assertEqual(first['wallet'],{'account_name':'Agent One','account_number':'09 123 4567'})
  self.assertTrue(ask(10000,'withdraw-key-00000004').json()['replayed']);self.assertEqual(ask(12000,'withdraw-key-00000004').status_code,409)
  self.assertEqual(ask(10000,'withdraw-key-00000005').status_code,422)
  self.assertEqual(self.client.post('/v1/agent/withdrawals/'+first['id']+'/cancel',headers=h).json()['status'],'cancelled')
  second=ask(10000,'withdraw-key-00000006').json()
  def review(x,decision,**kw):return self.client.post('/v1/developer/agent-withdrawals/'+x['id']+'/decision',headers=dev,json={'expected_revision':x['revision'],'decision':decision}|kw)
  self.assertEqual(self.client.post('/v1/developer/agent-withdrawals/'+second['id']+'/decision',headers=self.login('owner'),json={'expected_revision':1,'decision':'approved'}).status_code,403)
  self.assertEqual(review(second,'paid',payout_reference='KBZ-TEST-1',confirmed_paid=True).status_code,409)
  approved=review(second,'approved');self.assertEqual(approved.status_code,200,approved.text);approved=approved.json()
  self.assertEqual(self.client.post('/v1/agent/withdrawals/'+second['id']+'/cancel',headers=h).status_code,409)
  self.assertEqual(review(approved,'paid',payout_reference='KBZ-TEST-1').status_code,422)
  paid=review(approved,'paid',payout_reference='KBZ-TEST-1',confirmed_paid=True);self.assertEqual(paid.status_code,200,paid.text)
  self.assertEqual((paid.json()['status'],paid.json()['payout_reference']),('paid','KBZ-TEST-1'))
  self.assertEqual(self.client.get('/v1/agent/profile',headers=h).json()['balances'][0]['available'],0)
  self.assertEqual(self.refund(dev,v).status_code,200)
  balance=self.client.get('/v1/agent/profile',headers=h).json()['balances'][0];self.assertEqual((balance['paid'],balance['available']),(10000,-10000))
  self.assertEqual(ask(10000,'withdraw-key-00000007').json()['detail'],'Only 0 MMK is available to withdraw')
  listed=self.client.get('/v1/developer/agent-withdrawals',headers=dev).json();self.assertEqual([w['status'] for w in listed if w['id']==second['id']],['paid'])

if __name__=='__main__':unittest.main()
