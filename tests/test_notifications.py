import time,unittest
from datetime import timedelta
import test_backend
from sqlalchemy import select
from backend.models import User,Site,SiteIncident,SiteMaintenance,FinancialEvent,Audit
from backend.subscriptions import local_date,midnight

class NotificationTests(unittest.TestCase):
 setUp=test_backend.AccountPaymentTests.setUp
 tearDown=test_backend.AccountPaymentTests.tearDown
 login=test_backend.AccountPaymentTests.login
 package=test_backend.AccountPaymentTests.package
 order=test_backend.AccountPaymentTests.order
 def tenant(self,name='owner'):
  with self.app.state.factory() as s:return s.get(User,self.users[name]).tenant_id
 def site(self,name):
  with self.app.state.factory() as s:x=Site(tenant_id=self.tenant(),name=name,timezone='Asia/Yangon',created=int(time.time()));s.add(x);s.commit();return x.id
 def incident(self,site,scope,started,status='open',ended=None,expected=None,cause=None):
  with self.app.state.factory() as s:
   x=SiteIncident(tenant_id=self.tenant(),site_id=site,scope=scope,status=status,started=started,ended=ended,detection_source='test',symptoms='Test symptom',suspected_root_cause=cause,created_by=self.users['owner'],created=started,expected_reason=expected);s.add(x);s.commit();return x.id
 def feed(self,h):r=self.client.get('/v1/notifications',headers=h);self.assertEqual(r.status_code,200,r.text);return r.json()

 def test_owner_only_and_tenant_isolated(self):
  now=int(time.time());self.incident(self.site('Main'),'gateway',now-60)
  for name in ['guest','platform']:self.assertEqual(self.client.get('/v1/notifications',headers=self.login(name)).status_code,403)
  self.assertEqual(self.feed(self.login('other'))['items'],[])
  d=self.feed(self.login('owner'));self.assertEqual(d['delivery'],'in_app_only');self.assertEqual([x['kind'] for x in d['items']],['incident_open'])

 def test_downstream_faults_group_under_root_and_flapping_becomes_one_instability(self):
  now=int(time.time());main=self.site('Main');branch=self.site('Branch');quiet=self.site('Quiet')
  root=self.incident(main,'gateway',now-600,cause='ISP router lost power');self.incident(main,'access_point',now-500);self.incident(main,'dns_portal',now-400)
  self.incident(branch,'access_point',now-300);self.incident(quiet,'switch',now-200,expected='maintenance')
  for i in range(2):self.incident(branch,'wan',now-5000+i*1000,status='resolved',ended=now-4500+i*1000)
  self.incident(branch,'wan',now-100)
  self.incident(quiet,'access_point',now-90000,status='resolved',ended=now-3600)
  items=self.feed(self.login('owner'))['items'];by={(x['kind'],x['params'].get('site'),x['params'].get('scope')):x for x in items}
  g=by[('incident_open','Main','gateway')];self.assertEqual(g['key'],'incident:'+root);self.assertEqual((g['level'],g['count'],g['params']['related_scopes'],g['params']['root_cause'],g['params']['root_cause_confirmed']),('critical',3,['access_point','dns_portal'],'ISP router lost power',False))
  self.assertNotIn(('incident_open','Main','access_point'),by)
  self.assertEqual(by[('incident_open','Branch','access_point')]['level'],'attention')
  self.assertEqual(by[('incident_open','Quiet','switch')]['level'],'information')
  f=by[('instability','Branch','wan')];self.assertEqual((f['level'],f['count'],f['params']['open']),('critical',3,True))
  self.assertFalse([x for x in items if x['kind'] in ('incident_open','incident_recovered') and x['params'].get('scope')=='wan'])
  self.assertEqual(by[('incident_recovered','Quiet','access_point')]['level'],'information')
  self.assertEqual([x['level'] for x in items],sorted([x['level'] for x in items],key=['critical','attention','information'].index))

 def test_preferences_reads_and_updates_in_place(self):
  h=self.login('owner');now=int(time.time());main=self.site('Main');self.incident(main,'gateway',now-600)
  self.order(self.login('guest'),self.package(h))
  with self.app.state.factory() as s:s.add(SiteMaintenance(tenant_id=self.tenant(),site_id=main,reason='Test',started=now-60,planned_end=now+3600,created_by=self.users['owner']));s.commit()
  d=self.feed(h);self.assertEqual(d['counts'],{'critical':1,'attention':1,'information':1});self.assertEqual(d['unread'],3)
  pay=next(x for x in d['items'] if x['kind']=='payments_pending');self.assertEqual((pay['count'],pay['page']),(1,'Payments'))
  r=self.client.post('/v1/notifications/read',headers=h,json={'items':[{'key':x['key'],'version':x['version']} for x in d['items']]+[{'key':'incident:missing','version':'x'}]});self.assertEqual(r.status_code,200,r.text);self.assertEqual(r.json()['unread'],0)
  gateway=next(x for x in d['items'] if x['kind']=='incident_open')
  self.incident(main,'access_point',now-30)
  d=self.feed(h);g=next(x for x in d['items'] if x['key']==gateway['key']);self.assertEqual((g['count'],g['read'],d['unread']),(2,False,1))
  self.assertEqual(self.client.post('/v1/notifications/read',headers=h,json={'items':[{'key':g['key'],'version':gateway['version']}]}).json()['unread'],1)
  bad=self.client.post('/v1/notifications/preferences',headers=h,json={'expected_revision':3,'level':'critical','daily_summary':'off'});self.assertEqual(bad.status_code,409)
  r=self.client.post('/v1/notifications/preferences',headers=h,json={'expected_revision':0,'level':'critical','daily_summary':'important'});self.assertEqual(r.status_code,200,r.text)
  d=r.json();self.assertEqual((d['preferences'],d['hidden'],[x['level'] for x in d['items']]),({'level':'critical','daily_summary':'important','revision':1},2,['critical']))
  self.assertEqual(self.client.post('/v1/notifications/preferences',headers=h,json={'expected_revision':0,'level':'all','daily_summary':'off'}).status_code,409)
  self.assertEqual(self.client.post('/v1/notifications/preferences',headers=h,json={'expected_revision':1,'level':'all','daily_summary':'daily','extra':1}).status_code,422)
  with self.app.state.factory() as s:self.assertEqual(len(list(s.scalars(select(Audit).where(Audit.action=='notification_preferences_updated')))),1)

 def test_daily_summary_keeps_sold_separate_and_marks_router_metrics_unmeasured(self):
  h=self.login('owner');now=int(time.time());start=midnight(local_date(now))-86400+3600
  with self.app.state.factory() as s:
   base=dict(tenant_id=self.tenant(),currency='MMK',service='combined',package_name='Test',method='Cash',reference='test',timestamp_basis='server_recorded')
   s.add_all([FinancialEvent(source='voucher_sale',source_id='sale-1',kind='collection',amount=3000,occurred_at=start,**base),FinancialEvent(source='guest_order',source_id='order-1',kind='collection',amount=5000,occurred_at=start+60,**base),FinancialEvent(source='guest_order',source_id='order-1',kind='refund',amount=5000,occurred_at=start+120,**base),FinancialEvent(source='voucher_sale',source_id='sale-0',kind='collection',amount=9999,occurred_at=start-86400,**base)]);s.commit()
  d=self.client.get('/v1/notifications/daily-summary',headers=h).json()
  self.assertEqual(d['date'],(local_date(now)-timedelta(days=1)).isoformat())
  self.assertEqual(d['revenue'],[{'currency':'MMK','collected':8000,'refunded':5000,'net':3000,'payments':2}])
  self.assertEqual(d['vouchers'],{'sold':1,'redeemed_in_app':0});self.assertEqual((d['important'],d['reasons'],d['shown']),(True,['refunds_recorded'],True))
  self.assertIn('peak_customers',d['not_measured']);self.assertIn('router_voucher_activation',d['not_measured'])
  self.client.post('/v1/notifications/preferences',headers=h,json={'expected_revision':0,'level':'all','daily_summary':'off'})
  self.assertFalse(self.client.get('/v1/notifications/daily-summary',headers=h).json()['shown'])
  self.assertEqual(self.client.get('/v1/notifications/daily-summary',headers=self.login('other')).json()['revenue'],[])

if __name__=='__main__':unittest.main()
