import json,time
from test_backend import AccountPaymentTests
from backend.models import Site,User,Voucher
from backend.voucher_codes import scoped_hash

CODE='GOLD7K2Q9P'
WG_KEY='yAnz5TF+lXXJte14tji3zlMNq+hd2rYUIgJBgB3fBmk='

class SupportReportTests(AccountPaymentTests):
 def setup_shop(self):
  self.owner=self.login('owner')
  with self.app.state.factory() as s:
   tenant=s.get(User,self.users['owner']).tenant_id;self.tenant=tenant
   site=Site(tenant_id=tenant,name='Golden Downtown',timezone='Asia/Yangon',created=int(time.time()));s.add(site);s.commit();self.site=site.id
  pkg=self.package(self.owner);now=int(time.time())
  with self.app.state.factory() as s:
   s.add(Voucher(tenant_id=self.tenant,package_id=pkg,policy={},code_hash=scoped_hash(self.tenant,CODE),code_hint='9P',code_format='prefixed',issued_by=self.users['owner'],request_key='support-report-test-1',created=now,expires=now+86400));s.commit()
 def report(self,description='',headers=None):
  return self.client.post(f'/v1/sites/{self.site}/support-reports',headers=headers or self.owner,json={'description':description})

 def test_report_never_contains_secrets_or_voucher_codes(self):
  self.setup_shop()
  text=(f'Guest code GOLD-7K2Q9P and gold 7k2 q9p both fail. Wi-Fi password: hunter22 secret=abc '
        f'peer key {WG_KEY} token 0123456789abcdef0123456789abcdef. Kitchen AP blinking.')
  self.client.post('/v1/incidents',headers=self.owner,json={'site_id':self.site,'scope':'access_point','status':'open','started':int(time.time())-5400,'detection_source':'owner_report','symptoms':f'Guests with {CODE} cannot log in','suspected_root_cause':'Possible power cut'})
  r=self.report(text);self.assertEqual(r.status_code,201);body=r.json();dump=json.dumps(body)
  for secret in [CODE,'GOLD-7K2Q9P','7k2 q9p','hunter22','abc ',WG_KEY,'0123456789abcdef0123456789abcdef']:self.assertNotIn(secret,dump)
  description=body['report']['description']
  self.assertEqual(description.count('[voucher code removed]'),2);self.assertIn('password: [removed]',description);self.assertIn('[key removed]',description);self.assertIn('Kitchen AP blinking.',description)
  self.assertIn('[voucher code removed]',body['report']['outages'][0]['symptoms'])
  self.assertIn('Guests with',body['report']['outages'][0]['symptoms'])

 def test_report_states_evidence_based_causes(self):
  self.setup_shop();now=int(time.time())
  self.client.post('/v1/incidents',headers=self.owner,json={'site_id':self.site,'scope':'wan','status':'open','started':now-5400,'detection_source':'owner_report','symptoms':'No internet','suspected_root_cause':'ISP outage'})
  self.client.post('/v1/incidents',headers=self.owner,json={'site_id':self.site,'scope':'access_point','status':'resolved','started':now-7200,'ended':now-3600,'detection_source':'owner_report','symptoms':'AP down','confirmed_root_cause':'Unplugged'})
  report=self.report().json()['report']
  causes=[c['text'] for c in report['likely_causes']]
  self.assertTrue(any('No router is registered' in c for c in causes))
  self.assertTrue(any(c.startswith('Internet (WAN) outage ongoing for 1h 30m') and 'suspected (not confirmed): ISP outage' in c for c in causes))
  self.assertEqual([(o['scope'],o['ongoing'],o['duration']) for o in report['outages']],[('wan',True,'1h 30m'),('access_point',False,'1h')])
  self.assertEqual((report['shop']['name'],report['now']['network'],report['now']['business']),('Golden Downtown','on','not_set'))
  self.client.post('/v1/routers',headers=self.owner,json={'site_id':self.site,'name':'Front router','model':'hAP ax2','reported_routeros':'7.16'})
  self.client.post(f'/v1/sites/{self.site}/maintenance',headers=self.owner,json={'minutes':30,'reason':'Moving AP'})
  report=self.report().json()['report'];causes=[c['text'] for c in report['likely_causes']]
  self.assertTrue(any('No router has a verified connection' in c for c in causes))
  self.assertTrue(any(c.startswith('Planned maintenance is running until') and 'shop time' in c for c in causes))
  self.assertEqual(report['routers'][0]|{},{**report['routers'][0],'connection':'not_verified','magic_hub_assigned':False,'source':'owner_reported'})
  self.assertIn('site_maintenance_started',[e['action'] for e in report['recent_events']])
  self.assertTrue(all(set(e)=={'at','action'} for e in report['recent_events']))

 def test_owner_shares_and_only_platform_reads_shared_reports(self):
  self.setup_shop()
  kept=self.report('Just checking').json();shared=self.report('Customers cannot connect').json()
  other,guest,platform=self.login('other'),self.login('guest'),self.login('platform')
  self.assertEqual(self.client.post(f"/v1/support-reports/{shared['id']}/share",headers=other).status_code,404)
  self.assertEqual(self.client.get(f'/v1/sites/{self.site}/support-reports',headers=other).status_code,404)
  self.assertEqual(self.report('x',headers=other).status_code,404)
  self.assertEqual(self.report('x',headers=guest).status_code,403)
  self.assertEqual(self.report('x',headers=platform).status_code,403)
  self.assertEqual(self.client.get('/v1/support-reports',headers=self.owner).status_code,403)
  self.assertEqual(self.client.get('/v1/support-reports',headers=platform).json(),[])
  done=self.client.post(f"/v1/support-reports/{shared['id']}/share",headers=self.owner);self.assertEqual(done.status_code,200);self.assertIsNotNone(done.json()['shared_at'])
  again=self.client.post(f"/v1/support-reports/{shared['id']}/share",headers=self.owner).json();self.assertEqual(again['shared_at'],done.json()['shared_at'])
  inbox=self.client.get('/v1/support-reports',headers=platform).json()
  self.assertEqual([(x['id'],x['site_name'],x['report']['description']) for x in inbox],[(shared['id'],'Golden Downtown','Customers cannot connect')])
  mine=self.client.get(f'/v1/sites/{self.site}/support-reports',headers=self.owner).json()
  self.assertEqual({x['id']:x['shared_at'] is not None for x in mine},{kept['id']:False,shared['id']:True})
  actions=[a['action'] for a in self.client.get('/v1/audit',headers=self.owner).json() if a['target']==shared['id']]
  self.assertEqual(sorted(actions),['support_report_created','support_report_shared'])
