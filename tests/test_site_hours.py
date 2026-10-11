import time
from datetime import datetime
from zoneinfo import ZoneInfo
from test_backend import AccountPaymentTests
from backend.models import Site,SiteMaintenance,User
from backend.site_hours import in_schedule

YANGON=ZoneInfo('Asia/Yangon')
DAYS=('mon','tue','wed','thu','fri','sat','sun')
def at(*args):return int(datetime(*args,tzinfo=YANGON).timestamp())
def week(open_,close,closed=()):return {d:None if d in closed else {'open':open_,'close':close} for d in DAYS}

class SiteHoursTests(AccountPaymentTests):
 def site(self,name):
  with self.app.state.factory() as s:
   tenant=s.get(User,self.users['owner']).tenant_id
   x=Site(tenant_id=tenant,name=name,timezone='Asia/Yangon',created=int(time.time()));s.add(x);s.commit();return x.id
 def hours(self,site,headers):return self.client.get(f'/v1/sites/{site}/hours',headers=headers)

 def test_schedule_handles_overnight_all_day_and_closed_days(self):
  late=week('18:00','02:00',closed=('sat','sun'))
  self.assertTrue(in_schedule(late,'Asia/Yangon',at(2026,10,9,23,0)))   # Friday night
  self.assertTrue(in_schedule(late,'Asia/Yangon',at(2026,10,10,1,59)))  # spills into closed Saturday
  self.assertFalse(in_schedule(late,'Asia/Yangon',at(2026,10,10,2,0)))
  self.assertFalse(in_schedule(late,'Asia/Yangon',at(2026,10,9,17,59)))
  self.assertFalse(in_schedule(late,'Asia/Yangon',at(2026,10,11,23,0)))  # Sunday closed
  self.assertTrue(in_schedule(week('00:00','24:00'),'Asia/Yangon',at(2026,10,11,23,59)))
  self.assertTrue(in_schedule(week('08:00','22:00'),'Asia/Yangon',at(2026,10,12,8,0)))
  self.assertFalse(in_schedule(week('08:00','22:00'),'Asia/Yangon',at(2026,10,12,22,0)))

 def test_owner_sets_business_and_network_hours(self):
  owner=self.login('owner');site=self.site('Hours cafe')
  first=self.hours(site,owner);self.assertEqual(first.status_code,200);body=first.json()
  self.assertEqual((body['business_hours'],body['network_hours_mode'],body['now']['business'],body['now']['network'],body['maintenance']),(None,'always','not_set','on',None))
  put=lambda b:self.client.post(f'/v1/sites/{site}/hours',headers=owner,json=b)
  self.assertEqual(put({'network_hours_mode':'business'}).status_code,422)
  self.assertEqual(put({'network_hours_mode':'custom'}).status_code,422)
  self.assertEqual(put({'business_hours':week('08:00','08:00'),'network_hours_mode':'always'}).status_code,422)
  self.assertEqual(put({'business_hours':week('8:00','22:00'),'network_hours_mode':'always'}).status_code,422)
  partial=week('08:00','22:00');partial.pop('sun')
  self.assertEqual(put({'business_hours':partial,'network_hours_mode':'always'}).status_code,422)
  saved=put({'business_hours':week('08:00','22:00',closed=('sun',)),'network_hours_mode':'business','network_hours':week('00:00','24:00')})
  self.assertEqual(saved.status_code,200);saved=saved.json()
  self.assertEqual(saved['business_hours']['sun'],None);self.assertEqual(saved['business_hours']['mon'],{'open':'08:00','close':'22:00'})
  self.assertEqual(saved['network_hours_mode'],'business');self.assertIsNone(saved['network_hours'])
  self.assertIn(saved['now']['business'],['open','closed'])
  custom=put({'business_hours':None,'network_hours_mode':'custom','network_hours':week('06:00','23:30')}).json()
  self.assertEqual((custom['business_hours'],custom['network_hours']['fri']['close']),(None,'23:30'))
  listed=next(x for x in self.client.get('/v1/sites',headers=owner).json() if x['id']==site)
  self.assertEqual((listed['network_hours_mode'],listed['maintenance_until']),('custom',None))
  self.assertEqual(self.hours(site,self.login('other')).status_code,404)
  self.assertEqual(self.hours(site,self.login('guest')).status_code,403)
  self.assertEqual(self.client.post(f'/v1/sites/{site}/hours',headers=self.login('other'),json={'network_hours_mode':'always'}).status_code,404)

 def test_maintenance_runs_extends_ends_and_checks_honestly(self):
  owner=self.login('owner');site=self.site('Maintenance cafe');now=int(time.time())
  started=self.client.post(f'/v1/sites/{site}/maintenance',headers=owner,json={'minutes':30,'reason':' Replacing the switch '})
  self.assertEqual(started.status_code,201);m=started.json()['maintenance']
  self.assertEqual(m['reason'],'Replacing the switch');self.assertAlmostEqual(m['planned_end']-m['started'],1800);self.assertGreaterEqual(m['started'],now)
  self.assertEqual(self.client.post(f'/v1/sites/{site}/maintenance',headers=owner,json={'minutes':15}).status_code,409)
  self.assertEqual(self.client.post(f'/v1/sites/{site}/maintenance',headers=owner,json={'minutes':2}).status_code,422)
  listed=next(x for x in self.client.get('/v1/sites',headers=owner).json() if x['id']==site);self.assertEqual(listed['maintenance_until'],m['planned_end'])
  other=self.login('other')
  self.assertEqual(self.client.post(f"/v1/sites/{site}/maintenance/{m['id']}/end",headers=other).status_code,404)
  self.assertEqual(self.client.get('/v1/sites',headers=other).json(),[])
  extended=self.client.post(f"/v1/sites/{site}/maintenance/{m['id']}/extend",headers=owner,json={'minutes':15}).json()['maintenance']
  self.assertEqual((extended['planned_end']-m['planned_end'],extended['extensions']),(900,1))
  self.assertEqual(self.client.post(f"/v1/sites/{site}/maintenance/{m['id']}/extend",headers=owner,json={'minutes':1440}).status_code,422)
  ended=self.client.post(f"/v1/sites/{site}/maintenance/{m['id']}/end",headers=owner);self.assertEqual(ended.status_code,200);ended=ended.json()
  self.assertIsNone(ended['maintenance']);last=ended['history'][0]
  self.assertIsNotNone(last['ended']);self.assertEqual(last['post_check']['result'],'unable');self.assertIn('No router is registered',last['post_check']['summary'])
  self.assertEqual(self.client.post(f"/v1/sites/{site}/maintenance/{m['id']}/end",headers=owner).status_code,409)
  actions=[a['action'] for a in self.client.get('/v1/audit',headers=owner).json() if a['target']==m['id']]
  self.assertEqual(sorted(actions),['site_maintenance_ended','site_maintenance_extended','site_maintenance_started'])

 def test_window_that_ran_out_closes_itself_with_a_check(self):
  owner=self.login('owner');site=self.site('Timer cafe')
  m=self.client.post(f'/v1/sites/{site}/maintenance',headers=owner,json={'minutes':15}).json()['maintenance']
  with self.app.state.factory() as s:
   row=s.get(SiteMaintenance,m['id']);row.started-=3600;row.planned_end=int(time.time())-60;s.commit();due=row.planned_end
  body=self.hours(site,owner).json()
  self.assertIsNone(body['maintenance']);self.assertEqual(body['history'][0]['ended'],due);self.assertEqual(body['history'][0]['post_check']['result'],'unable')
  self.assertEqual(self.client.post(f"/v1/sites/{site}/maintenance/{m['id']}/extend",headers=owner,json={'minutes':15}).status_code,409)
  self.assertEqual(self.client.post(f'/v1/sites/{site}/maintenance',headers=owner,json={'minutes':15}).status_code,201)

 def test_incidents_during_maintenance_or_network_off_hours_are_expected(self):
  owner=self.login('owner');now=int(time.time())
  incident=lambda site,scope,started:self.client.post('/v1/incidents',headers=owner,json={'site_id':site,'scope':scope,'status':'open','started':started,'detection_source':'owner_report','symptoms':'AP offline'}).json()['expected_reason']
  busy=self.site('Busy cafe')
  self.assertIsNone(incident(busy,'access_point',now-60))
  self.client.post(f'/v1/sites/{busy}/maintenance',headers=owner,json={'minutes':30})
  self.assertEqual(incident(busy,'access_point',int(time.time())),'maintenance')
  self.assertIsNone(incident(busy,'control_plane',int(time.time())))
  self.assertIsNone(incident(busy,'gateway',now-3600))
  night=self.site('Night cafe');local=datetime.fromtimestamp(now,YANGON)
  hhmm=lambda h:f'{(local.hour+h)%24:02d}:{local.minute:02d}'
  self.client.post(f'/v1/sites/{night}/hours',headers=owner,json={'network_hours_mode':'custom','network_hours':week(hhmm(2),hhmm(3))})
  self.assertEqual(self.hours(night,owner).json()['now']['network'],'off')
  self.assertEqual(incident(night,'wan',now),'network_off_hours')
  listed=[x['expected_reason'] for x in self.client.get('/v1/incidents',headers=owner).json()]
  self.assertEqual(sorted(x for x in listed if x),['maintenance','network_off_hours'])
