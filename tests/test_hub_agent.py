import base64,json,tempfile,unittest
from pathlib import Path
from fastapi.testclient import TestClient
from backend.hub_agent import WireGuardAgentService,make_agent,AgentError

def key(n):return base64.b64encode(bytes([n])*32).decode()

class Result:
 def __init__(self,returncode=0,stdout=''):self.returncode=returncode;self.stdout=stdout

class Runner:
 def __init__(self):self.calls=[];self.exists=True;self.handshake=0
 def __call__(self,args,**kwargs):
  self.calls.append(args)
  if args[:4]==['ip','link','show','mm-prod-hub']:return Result(0 if self.exists else 1)
  if args[:4]==['wg','show','mm-prod-hub','public-key']:return Result(stdout=key(1)+'\n')
  if args[:4]==['wg','show','mm-prod-hub','latest-handshakes']:
   return Result(stdout=(key(2)+'\t'+str(self.handshake)+'\n') if self.handshake else '')
  return Result()

class HubAgentTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();root=Path(self.temp.name);self.private=root/'private';self.private.write_text('synthetic-test-only')
  self.runner=Runner();self.service=WireGuardAgentService('mm-prod-hub',self.private,root/'state'/'peers.json',runner=self.runner,clock=lambda:1000)
  self.service.initialize('10.90.1.1/24',51820)
 def tearDown(self):self.temp.cleanup()
 def test_peer_state_is_scoped_persistent_idempotent_and_revocable(self):
  first=self.service.provision(key(2),'10.90.1.2/32','10.90.1.0/24');self.assertTrue(first['configuration_modified'])
  again=self.service.provision(key(2),'10.90.1.2/32','10.90.1.0/24');self.assertFalse(again['configuration_modified'])
  with self.assertRaises(AgentError):self.service.provision(key(3),'10.90.1.2/32','10.90.1.0/24')
  with self.assertRaises(AgentError):self.service.provision(key(3),'10.91.1.2/32','10.91.1.0/24')
  state=json.loads(self.service.state_file.read_text());self.assertEqual(state,{key(2):'10.90.1.2/32'})
  self.runner.handshake=950;observed=self.service.observe(key(2),'10.90.1.2/32','10.90.1.0/24',180);self.assertTrue(observed['fresh_handshake'])
  removed=self.service.revoke(key(2),'10.90.1.2/32','10.90.1.0/24');self.assertTrue(removed['configuration_modified']);self.assertEqual(json.loads(self.service.state_file.read_text()),{})
 def test_control_api_requires_token_and_fixed_interface(self):
  client=TestClient(make_agent(self.service,'t'*48));payload={'interface':'mm-prod-hub','public_key':key(2),'address':'10.90.1.2/32','pool':'10.90.1.0/24'}
  self.assertEqual(client.post('/v1/peers/provision',json=payload).status_code,401)
  headers={'Authorization':'Bearer '+'t'*48}
  self.assertEqual(client.post('/v1/identity',headers=headers,json={'interface':'other'}).status_code,404)
  response=client.post('/v1/peers/provision',headers=headers,json=payload);self.assertEqual(response.status_code,200,response.text)
  self.assertNotIn(key(2),response.text)

