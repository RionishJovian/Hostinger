import time
from test_backend import AccountPaymentTests
from backend.models import Site

class IncidentTests(AccountPaymentTests):
 def site(self,name):
  with self.app.state.factory() as s:
   x=Site(tenant_id=self.users_tenant('owner'),name=name,timezone='Asia/Yangon',created=int(time.time()));s.add(x);s.commit();return x.id
 def test_incident_history_requires_evidence_label_and_resolves(self):
  owner=self.login('owner');site_id=self.site('Incident site');now=int(time.time())
  body={'site_id':site_id,'scope':'wan','status':'open','started':now-60,'detection_source':'owner_report','symptoms':'Starlink unavailable','suspected_root_cause':'Possible upstream outage','notes':'Observed locally'}
  created=self.client.post('/v1/incidents',headers=owner,json=body);self.assertEqual(created.status_code,201);incident=created.json();self.assertEqual(incident['status'],'open')
  resolved={**body,'status':'resolved','ended':now,'confirmed_root_cause':'Provider outage confirmed','remediation':'Switched to backup link'}
  result=self.client.post('/v1/incidents/'+incident['id']+'/resolve',headers=owner,json=resolved);self.assertEqual(result.status_code,200);self.assertEqual(result.json()['status'],'resolved')
  self.assertEqual(self.client.get('/v1/incidents',headers=self.login('guest')).status_code,403)
 def test_incident_rejects_invalid_time_range(self):
  owner=self.login('owner');site_id=self.site('Bad incident');now=int(time.time())
  body={'site_id':site_id,'scope':'gateway','status':'resolved','started':now,'ended':now-1,'detection_source':'test','symptoms':'Bad range'}
  self.assertEqual(self.client.post('/v1/incidents',headers=owner,json=body).status_code,422)
 def users_tenant(self,name):
  from backend.models import User
  with self.app.state.factory() as s:return s.get(User,self.users[name]).tenant_id
