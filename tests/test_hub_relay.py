import asyncio,base64,os,tempfile,threading,unittest
from pathlib import Path
from unittest.mock import patch
from backend.hub_agent import AgentError,ManagementRelay
from backend.routeros_adapter import RouterOSClient,RouterOSCredential,RouterOSError,management_proxy_from_environment

TOKEN='t'*48
def auth(token=TOKEN):return 'Basic '+base64.b64encode(f'mikromagic:{token}'.encode()).decode()

class Peers:
 def __init__(self,addresses=('10.90.1.2',),broken=False):self.addresses=set(addresses);self.broken=broken
 def peer_addresses(self):
  if self.broken:raise AgentError('peer state is unreadable')
  return self.addresses

class RelayTests(unittest.IsolatedAsyncioTestCase):
 async def asyncSetUp(self):
  async def echo(reader,writer):
   while data:=await reader.read(1024):writer.write(data);await writer.drain()
   writer.close()
  self.upstream=await asyncio.start_server(echo,'127.0.0.1',0);self.upstream_port=self.upstream.sockets[0].getsockname()[1]
  self.dialed=[]
 async def asyncTearDown(self):
  self.upstream.close();await self.upstream.wait_closed()
  if getattr(self,'server',None):self.server.close();await self.server.wait_closed()
 async def start(self,peers=None,fail=False,**limits):
  async def connect(host,port):
   self.dialed.append((host,port))
   if fail:raise OSError('unreachable')
   return await asyncio.open_connection('127.0.0.1',self.upstream_port)
  self.server=await ManagementRelay(peers or Peers(),TOKEN,connect=connect,**limits).serve('127.0.0.1',0)
  return self.server.sockets[0].getsockname()[1]
 async def send(self,port,head):
  reader,writer=await asyncio.open_connection('127.0.0.1',port);writer.write(head.encode());await writer.drain()
  status=(await asyncio.wait_for(reader.readuntil(b'\r\n\r\n'),5)).decode()
  return status.split(' ')[1],reader,writer
 def connect_head(self,target='10.90.1.2:443',authorization=None):
  return f'CONNECT {target} HTTP/1.1\r\nHost: {target}\r\nProxy-Authorization: {authorization or auth()}\r\n\r\n'

 async def test_provisioned_peer_on_https_is_relayed_end_to_end(self):
  port=await self.start();status,reader,writer=await self.send(port,self.connect_head())
  self.assertEqual(status,'200');writer.write(b'tls-bytes');await writer.drain()
  self.assertEqual(await reader.readexactly(9),b'tls-bytes');self.assertEqual(self.dialed,[('10.90.1.2',443)])
  writer.close()

 async def test_rejects_bad_credentials_targets_and_methods_without_dialing(self):
  port=await self.start()
  cases=[(self.connect_head(authorization=auth('x'*48)),'407'),(self.connect_head(authorization='Bearer '+TOKEN),'407'),
   ('CONNECT 10.90.1.2:443 HTTP/1.1\r\n\r\n','407'),(self.connect_head('10.90.1.3:443'),'403'),(self.connect_head('10.90.1.2:22'),'403'),
   (self.connect_head('10.90.1.2:80'),'403'),(self.connect_head('router.example.com:443'),'403'),(self.connect_head('8.8.8.8:443'),'403'),
   ('GET http://10.90.1.2/ HTTP/1.1\r\n\r\n','405')]
  for head,expected in cases:
   with self.subTest(head=head.splitlines()[0]):
    status,_,writer=await self.send(port,head);self.assertEqual(status,expected);writer.close()
  self.assertEqual(self.dialed,[])

 async def test_unreadable_peer_state_and_unreachable_router_fail_closed(self):
  port=await self.start(Peers(broken=True))
  self.assertEqual((await self.send(port,self.connect_head()))[0],'403')
  self.server.close();await self.server.wait_closed()
  port=await self.start(fail=True)
  self.assertEqual((await self.send(port,self.connect_head()))[0],'502')

 async def test_concurrent_tunnels_are_bounded(self):
  port=await self.start(max_tunnels=1)
  first,_,held=await self.send(port,self.connect_head());self.assertEqual(first,'200')
  second,_,writer=await self.send(port,self.connect_head());self.assertEqual(second,'503')
  held.close();writer.close()

class RelayConfigurationTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.token=Path(self.tmp.name)/'hub_agent_token';self.token.write_text(TOKEN)
 def tearDown(self):self.tmp.cleanup()
 def test_relay_url_is_fixed_and_token_comes_from_the_mounted_file(self):
  with patch.dict(os.environ,{'MIKROMAGIC_HUB_RELAY_URL':'','MIKROMAGIC_HUB_AGENT_TOKEN_FILE':str(self.token)}):
   self.assertIsNone(management_proxy_from_environment())
  with patch.dict(os.environ,{'MIKROMAGIC_HUB_RELAY_URL':'http://magic-hub:8791','MIKROMAGIC_HUB_AGENT_TOKEN_FILE':str(self.token)}):
   self.assertEqual(management_proxy_from_environment(),f'http://mikromagic:{TOKEN}@magic-hub:8791')
  for url in ['https://magic-hub:8791','http://evil.example:8791','http://magic-hub:8790','http://user:pw@magic-hub:8791','http://magic-hub:8791/x']:
   with self.subTest(url=url),patch.dict(os.environ,{'MIKROMAGIC_HUB_RELAY_URL':url,'MIKROMAGIC_HUB_AGENT_TOKEN_FILE':str(self.token)}):
    with self.assertRaises(RouterOSError):management_proxy_from_environment()
  with patch.dict(os.environ,{'MIKROMAGIC_HUB_RELAY_URL':'http://magic-hub:8791','MIKROMAGIC_HUB_AGENT_TOKEN_FILE':'/missing/token'}):
   with self.assertRaises(RouterOSError) as raised:management_proxy_from_environment()
   self.assertEqual(raised.exception.code,'relay_unavailable')

 def test_routeros_client_authenticates_to_the_relay_with_connect(self):
  seen=[];ready=threading.Event();state={}
  async def run():
   async def connect(host,port):seen.append((host,port));raise OSError('no router in test')
   server=await ManagementRelay(Peers(),TOKEN,connect=connect).serve('127.0.0.1',0)
   state['port']=server.sockets[0].getsockname()[1];state['loop']=asyncio.get_running_loop();state['stop']=asyncio.Event();ready.set()
   await state['stop'].wait();server.close();await server.wait_closed()
  thread=threading.Thread(target=lambda:asyncio.run(run()));thread.start();ready.wait(5)
  try:
   with patch('backend.routeros_adapter.management_proxy_from_environment',return_value=f"http://mikromagic:{TOKEN}@127.0.0.1:{state['port']}"):
    with RouterOSClient(RouterOSCredential('https://10.90.1.2','mm-monitor-abcdef12','test-only')) as client:
     with self.assertRaises(RouterOSError):client.get('system/resource')
  finally:
   state['loop'].call_soon_threadsafe(state['stop'].set);thread.join(5)
  self.assertEqual(seen,[('10.90.1.2',443)])

if __name__=='__main__':unittest.main()
