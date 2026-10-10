import base64,tempfile,unittest
from pathlib import Path
import httpx
from backend.wireguard_hub import WireGuardHubAgentAdapter,HubWireGuardError

def key(n):return base64.b64encode(bytes([n])*32).decode()

class HubAgentClientTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.token=Path(self.temp.name)/'token';self.token.write_text('t'*48);self.calls=[]
 def tearDown(self):self.temp.cleanup()
 def adapter(self,handler):return WireGuardHubAgentAdapter('http://magic-hub:8790',str(self.token),transport=httpx.MockTransport(handler),clock=lambda:1000)
 def test_fixed_internal_endpoint_and_authenticated_operations(self):
  def handler(request):
   self.calls.append(request)
   self.assertEqual(request.headers['authorization'],'Bearer '+'t'*48)
   if request.url.path=='/v1/identity':return httpx.Response(200,json={'public_key':key(1)})
   if request.url.path=='/v1/peers/provision':return httpx.Response(200,json={'result':'provisioned','peer_present':True,'allowed_address':'10.90.1.2/32','configuration_modified':True})
   return httpx.Response(200,json={'evidence_source':'dedicated_hub_agent_live_read','peer_found':True,'allowed_address_match':True,'fresh_handshake':False})
  adapter=self.adapter(handler);self.assertTrue(adapter.verify_hub_identity('mm-prod-hub',key(1)))
  self.assertEqual(adapter.provision_peer('mm-prod-hub',key(2),'10.90.1.2/32','10.90.1.0/24')['result'],'provisioned')
  observed=adapter.observe_peer('mm-prod-hub',key(2),'10.90.1.2/32','10.90.1.0/24');self.assertFalse(observed['connection_verified']);self.assertFalse(observed['management_read_verified'])
  self.assertEqual([x.url.path for x in self.calls],['/v1/identity','/v1/peers/provision','/v1/peers/observe'])
 def test_rejects_public_or_malformed_agent_endpoints(self):
  for url in ['https://magic-hub:8790','http://127.0.0.1:8790','http://example.com:8790','http://magic-hub:8790/path']:
   with self.assertRaises(HubWireGuardError):WireGuardHubAgentAdapter(url,str(self.token))
 def test_identity_mismatch_and_agent_error_fail_closed(self):
  wrong=self.adapter(lambda r:httpx.Response(200,json={'public_key':key(3)}))
  with self.assertRaises(HubWireGuardError):wrong.verify_hub_identity('mm-prod-hub',key(1))
  denied=self.adapter(lambda r:httpx.Response(409,json={'detail':'operation rejected'}))
  with self.assertRaises(HubWireGuardError):denied.provision_peer('mm-prod-hub',key(2),'10.90.1.2/32','10.90.1.0/24')

