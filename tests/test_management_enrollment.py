import datetime,ipaddress,json,os,stat,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import Encoding
from cryptography.x509.oid import NameOID
from backend.management_enrollment import ManagementSetupError,enrollment_password,provision_management_identities,serial_digest
from backend.routeros_adapter import RouterOSError,load_routeros_monitoring_credential,load_routeros_safe_change_credential

ROUTER='abcdef12-0000-4000-8000-000000000001';ENROLL='mm-enroll-abcdef12'
SNAPSHOT={'router':{'address':'10.90.1.5/32'},'hub':{'hub_address':'10.90.1.1'}}
SERIAL='HFA0ABC1234'

def certificate(address='10.90.1.5'):
 key=ec.generate_private_key(ec.SECP256R1());name=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,address)]);now=datetime.datetime.now(datetime.timezone.utc)
 return (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key()).serial_number(x509.random_serial_number())
  .not_valid_before(now-datetime.timedelta(minutes=5)).not_valid_after(now+datetime.timedelta(days=365))
  .add_extension(x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address(address))]),critical=False).sign(key,hashes.SHA256()).public_bytes(Encoding.DER))

class FakeRouter:
 """RouterOS REST stand-in that enforces logins, group rights and user records."""
 def __init__(self,serial=SERIAL,monitor_can_write=False):
  self.serial=serial;self.monitor_can_write=monitor_can_write;self.next=2;self.credentials=[]
  self.groups={'full':{'policy':'local,read,write,policy,rest-api'}};self.users={}
 def add_enrollment(self,password,name=ENROLL):self.users[name]={'.id':'*1','group':'full','password':password,'address':'10.90.1.1/32'}
 def client(self,credential):self.credentials.append(credential);return FakeClient(self,credential)

class FakeClient:
 def __init__(self,router,credential):self.router=router;self.credential=credential
 def __enter__(self):return self
 def __exit__(self,*args):pass
 def _user(self):
  user=self.router.users.get(self.credential.username)
  if not user or user['password']!=self.credential.password or user.get('disabled')=='true':raise RouterOSError('authentication_failed','rejected',401)
  return user
 def _policy(self):
  group=self._user()['group'];return {p for p in self.router.groups[group]['policy'].split(',') if not p.startswith('!')}
 def get(self,path,optional=False):
  self._user();menu,_,query=path.partition('?name=')
  if menu=='system/resource':return {'architecture-name':'arm64','version':'7.16'}
  if menu=='system/routerboard':return {'serial-number':self.router.serial,'model':'C52iG-5HaxD2HaxD'}
  if menu=='system/identity':return {'name':'Shop router'}
  if menu=='user/group':return [{'name':query,**g} for n,g in self.router.groups.items() if n==query]
  if menu=='user':return [{'name':n,'.id':u['.id'],'group':u['group']} for n,u in self.router.users.items() if n==query]
  raise AssertionError(path)
 def write(self,method,path,payload):
  policy=self._policy()
  if 'write' not in policy and not (self.router.monitor_can_write and self.credential.username.startswith('mm-monitor-')):raise RouterOSError('router_write_failed','denied')
  if path=='system/identity/set':return {}
  if 'policy' not in policy:raise RouterOSError('router_write_failed','denied')
  if (method,path)==('PUT','user/group'):self.router.groups[payload['name']]={'policy':payload['policy']};return {}
  if (method,path)==('PUT','user'):self.router.users[payload['name']]={'.id':f'*{self.router.next}',**{k:v for k,v in payload.items() if k!='name'}};self.router.next+=1;return {}
  name=next(n for n,u in self.router.users.items() if 'user/'+u['.id']==path)
  if method=='PATCH':self.router.users[name].update(payload);return {}
  if method=='DELETE':del self.router.users[name];return {}
  raise AssertionError((method,path))

class ManagementEnrollmentTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();root=Path(self.tmp.name);self.dirs={}
  for role in ('monitoring','safe-change','enroll'):
   path=root/role;path.mkdir(mode=0o700);self.dirs[role]=path
  self.env=patch.dict(os.environ,{'MIKROMAGIC_ROUTEROS_MONITORING_SECRETS_DIR':str(self.dirs['monitoring']),'MIKROMAGIC_ROUTEROS_SAFE_CHANGE_SECRETS_DIR':str(self.dirs['safe-change']),'MIKROMAGIC_ROUTEROS_ENROLL_SECRETS_DIR':str(self.dirs['enroll'])})
  self.env.start();self.cert=certificate()
 def tearDown(self):self.env.stop();self.tmp.cleanup()
 def run_setup(self,router,cert=None,serial=SERIAL):
  router.add_enrollment(enrollment_password(ROUTER,create=True))
  return provision_management_identities(ROUTER,SNAPSHOT,serial_digest(serial),fetch=lambda address:cert or self.cert,client_factory=router.client)

 def test_creates_both_logins_and_removes_the_enrollment_login(self):
  router=FakeRouter();shown=enrollment_password(ROUTER,create=True)
  self.assertEqual(enrollment_password(ROUTER,create=True),shown)
  evidence=self.run_setup(router)
  self.assertEqual(router.groups['mm-monitor']['policy'],'read,api,rest-api');self.assertEqual(router.groups['mm-safechange']['policy'],'read,write,api,rest-api')
  self.assertNotIn('write',router.groups['mm-monitor']['policy'].split(','))
  monitor,change=router.users['mm-monitor-abcdef12'],router.users['mm-safechange-abcdef12']
  self.assertEqual((monitor['group'],monitor['address']),('mm-monitor','10.90.1.1/32'));self.assertEqual((change['group'],change['address']),('mm-safechange','10.90.1.1/32'))
  self.assertNotIn(ENROLL,router.users);self.assertIsNone(enrollment_password(ROUTER))
  self.assertEqual(evidence['checks'],{'monitoring_write_denied':True,'safe_change_login':True,'enrollment_login_removed':True})
  self.assertEqual((evidence['model'],evidence['architecture']),('C52iG-5HaxD2HaxD','arm64'))
  text=json.dumps(evidence)
  for secret in (monitor['password'],change['password'],shown):self.assertNotIn(secret,text)
  self.assertNotEqual(monitor['password'],change['password'])
  for loader,directory in ((load_routeros_monitoring_credential,'monitoring'),(load_routeros_safe_change_credential,'safe-change')):
   credential=loader(ROUTER);self.assertEqual(credential.base_url,'https://10.90.1.5')
   self.assertEqual(Path(credential.verify).read_bytes().count(b'BEGIN CERTIFICATE'),1)
   self.assertEqual(stat.S_IMODE((self.dirs[directory]/(ROUTER+'.json')).stat().st_mode),0o600)
  self.assertTrue(all(isinstance(c.verify,str) and c.verify.endswith(ROUTER+'.pem') for c in router.credentials))

 def test_rerun_resets_existing_logins_in_the_right_groups(self):
  router=FakeRouter();router.groups['mm-monitor']={'policy':'read,api,rest-api,!write,!policy'}
  router.users['mm-monitor-abcdef12']={'.id':'*9','group':'mm-monitor','password':'old','address':'0.0.0.0/0'}
  self.run_setup(router)
  self.assertNotEqual(router.users['mm-monitor-abcdef12']['password'],'old');self.assertEqual(router.users['mm-monitor-abcdef12']['address'],'10.90.1.1/32')

 def test_stops_without_changes_on_wrong_router_or_certificate(self):
  for router,cert,code in [(FakeRouter(serial='OTHER12345'),None,'router_serial_mismatch'),(FakeRouter(),certificate('10.90.1.6'),'certificate_name_mismatch')]:
   with self.subTest(code=code):
    with self.assertRaises(ManagementSetupError) as raised:self.run_setup(router,cert)
    self.assertEqual(raised.exception.code,code);self.assertEqual(set(router.users),{ENROLL});self.assertEqual(set(router.groups),{'full'})

 def test_conflicts_and_unsafe_rights_stop_setup(self):
  router=FakeRouter();router.groups['mm-monitor']={'policy':'read,write,api,rest-api'}
  with self.assertRaises(ManagementSetupError) as raised:self.run_setup(router)
  self.assertEqual(raised.exception.code,'group_conflict')
  router=FakeRouter();router.groups['mm-monitor']={'policy':'read,rest-api'}
  with self.assertRaises(ManagementSetupError) as raised:self.run_setup(router)
  self.assertEqual(raised.exception.code,'group_conflict')
  router=FakeRouter();router.groups['mm-safechange']={'policy':'read,write,api,rest-api'};router.users['mm-safechange-abcdef12']={'.id':'*9','group':'full','password':'x'}
  with self.assertRaises(ManagementSetupError) as raised:self.run_setup(router)
  self.assertEqual(raised.exception.code,'user_conflict')
  router=FakeRouter(monitor_can_write=True)
  with self.assertRaises(ManagementSetupError) as raised:self.run_setup(router)
  self.assertEqual(raised.exception.code,'monitoring_write_not_denied');self.assertIn(ENROLL,router.users)

 def test_requires_storage_serial_and_a_shown_enrollment_login(self):
  with self.assertRaises(ManagementSetupError) as raised:provision_management_identities(ROUTER,SNAPSHOT,serial_digest(SERIAL),fetch=lambda a:self.cert,client_factory=FakeRouter().client)
  self.assertEqual(raised.exception.code,'enrollment_login_missing')
  enrollment_password(ROUTER,create=True)
  with self.assertRaises(ManagementSetupError) as raised:provision_management_identities(ROUTER,SNAPSHOT,None,fetch=lambda a:self.cert,client_factory=FakeRouter().client)
  self.assertEqual(raised.exception.code,'router_serial_required')
  self.dirs['enroll'].chmod(0o755)
  with self.assertRaises(ManagementSetupError) as raised:enrollment_password(ROUTER)
  self.assertEqual(raised.exception.code,'credential_storage_unavailable')
  self.assertEqual(serial_digest(' hfa0 abc1234 '),serial_digest(SERIAL));self.assertIsNone(serial_digest('bad!'))

class PinnedTlsTests(unittest.TestCase):
 def serve(self,der,key):
  import http.server,ssl,threading
  folder=tempfile.mkdtemp();cert,keyfile=Path(folder)/'c.pem',Path(folder)/'k.pem'
  cert.write_bytes(x509.load_der_x509_certificate(der).public_bytes(Encoding.PEM))
  from cryptography.hazmat.primitives.serialization import PrivateFormat,NoEncryption
  keyfile.write_bytes(key.private_bytes(Encoding.PEM,PrivateFormat.PKCS8,NoEncryption()))
  class Handler(http.server.BaseHTTPRequestHandler):
   def do_GET(self):self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(b'{"architecture-name":"arm64"}')
   def log_message(self,*args):pass
  server=http.server.HTTPServer(('127.0.0.1',0),Handler);context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);context.load_cert_chain(cert,keyfile)
  server.socket=context.wrap_socket(server.socket,server_side=True);threading.Thread(target=server.serve_forever,daemon=True).start()
  self.addCleanup(server.server_close);self.addCleanup(server.shutdown);return server.server_address[1],cert
 def routeros_style(self,address):
  key=ec.generate_private_key(ec.SECP256R1());name=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,address)]);now=datetime.datetime.now(datetime.timezone.utc)
  der=(x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key()).serial_number(x509.random_serial_number())
   .not_valid_before(now-datetime.timedelta(minutes=5)).not_valid_after(now+datetime.timedelta(days=3650))
   .add_extension(x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address(address))]),critical=False)
   .add_extension(x509.KeyUsage(digital_signature=True,content_commitment=False,key_encipherment=True,data_encipherment=False,key_agreement=False,key_cert_sign=True,crl_sign=False,encipher_only=False,decipher_only=False),critical=True)
   .add_extension(x509.ExtendedKeyUsage([x509.oid.ExtendedKeyUsageOID.SERVER_AUTH]),critical=False).sign(key,hashes.SHA256()).public_bytes(Encoding.DER))
  return der,key
 def test_client_trusts_only_the_pinned_self_signed_router_certificate(self):
  from backend.routeros_adapter import RouterOSClient,RouterOSCredential
  der,key=self.routeros_style('127.0.0.1');port,pem=self.serve(der,key)
  with patch.dict(os.environ,{'MIKROMAGIC_HUB_RELAY_URL':''}):
   with RouterOSClient(RouterOSCredential(f'https://127.0.0.1:{port}','mm-monitor-abcdef12','x',str(pem))) as client:
    self.assertEqual(client.get('system/resource'),{'architecture-name':'arm64'})
   other=Path(tempfile.mkdtemp())/'other.pem';other.write_bytes(x509.load_der_x509_certificate(self.routeros_style('127.0.0.1')[0]).public_bytes(Encoding.PEM))
   with RouterOSClient(RouterOSCredential(f'https://127.0.0.1:{port}','mm-monitor-abcdef12','x',str(other))) as client:
    with self.assertRaises(RouterOSError) as raised:client.get('system/resource')
   self.assertEqual(raised.exception.code,'tls_verification_failed')

if __name__=='__main__':unittest.main()
