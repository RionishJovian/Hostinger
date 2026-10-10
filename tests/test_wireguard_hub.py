import base64,unittest
from types import SimpleNamespace
from backend.wireguard_hub import WireGuardHubAdapter,HubWireGuardError

KEY=base64.b64encode(bytes([7])*32).decode()
OTHER=base64.b64encode(bytes([8])*32).decode()

class Runner:
 def __init__(self):self.peers={};self.timestamps={};self.calls=[]
 def __call__(self,args,**kwargs):
  self.calls.append(args)
  if args[1]=='show':
   kind=args[-1]
   if kind=='public-key':out=KEY
   elif kind=='peers':out='\n'.join(self.peers)
   elif kind=='allowed-ips':out=''.join(f'{key}\t{ips}\n' for key,ips in self.peers.items())
   elif kind=='latest-handshakes':out=''.join(f'{key}\t{stamp}\n' for key,stamp in self.timestamps.items())
   else:out=''
   return SimpleNamespace(returncode=0,stdout=out,stderr='')
  if args[1]=='set' and args[-1]=='remove':self.peers.pop(args[4],None);self.timestamps.pop(args[4],None)
  elif args[1]=='set':self.peers[args[4]]=args[-1]
  return SimpleNamespace(returncode=0,stdout='',stderr='')

class HubAdapterTests(unittest.TestCase):
 def setUp(self):self.runner=Runner();self.adapter=WireGuardHubAdapter('/usr/bin/wg',self.runner,clock=lambda:2000)
 def test_assigned_hub_public_key_must_match_actual_interface(self):
  self.assertTrue(self.adapter.verify_hub_identity('wg-mm',KEY))
  with self.assertRaises(HubWireGuardError):self.adapter.verify_hub_identity('wg-mm',OTHER)
  self.assertFalse(any(call[1]=='set' for call in self.runner.calls))
 def test_provision_revoke_and_idempotency_are_narrowly_scoped(self):
  result=self.adapter.provision_peer('wg-mm',KEY,'10.90.1.2/32','10.90.1.0/24')
  self.assertEqual(result['result'],'provisioned');self.assertTrue(result['configuration_modified'])
  self.assertIn(['/usr/bin/wg','set','wg-mm','peer',KEY,'allowed-ips','10.90.1.2/32'],self.runner.calls)
  again=self.adapter.provision_peer('wg-mm',KEY,'10.90.1.2','10.90.1.0/24');self.assertEqual(again['result'],'already_present')
  self.assertEqual(self.adapter.revoke_peer('wg-mm',KEY,'10.90.1.2','10.90.1.0/24')['result'],'revoked')
  self.assertNotIn(KEY,self.runner.peers)
 def test_conflict_and_invalid_input_never_issue_writes(self):
  self.runner.peers[KEY]='10.90.1.2/32'
  with self.assertRaises(HubWireGuardError):self.adapter.provision_peer('wg-mm',KEY,'10.90.1.3','10.90.1.0/24')
  before=sum(call[1]=='set' for call in self.runner.calls)
  for interface,key,address in [('bad interface',OTHER,'10.90.1.3'),('wg-mm','not-a-key','10.90.1.3'),('wg-mm',OTHER,'10.90.1.1')]:
   with self.assertRaises(HubWireGuardError):self.adapter.provision_peer(interface,key,address,'10.90.1.0/24')
  self.assertEqual(sum(call[1]=='set' for call in self.runner.calls),before)
 def test_handshake_never_claims_management_connection(self):
  self.runner.peers[KEY]='10.90.1.2/32';self.runner.timestamps[KEY]=1990
  evidence=self.adapter.observe_peer('wg-mm',KEY,'10.90.1.2','10.90.1.0/24')
  self.assertTrue(evidence['fresh_handshake']);self.assertFalse(evidence['connection_verified']);self.assertFalse(evidence['management_read_verified'])
 def test_future_handshake_is_not_fresh(self):
  self.runner.peers[KEY]='10.90.1.2/32';self.runner.timestamps[KEY]=2100
  self.assertFalse(self.adapter.observe_peer('wg-mm',KEY,'10.90.1.2','10.90.1.0/24')['fresh_handshake'])

if __name__=='__main__':unittest.main()
