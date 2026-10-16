"""Create a router's MikroMagic monitoring and Safe Change logins over the tunnel.

The technician adds only a temporary enrollment login that accepts the Hub
address alone. MikroMagic uses it once, through the Hub relay and the pinned
router certificate, to create both dedicated logins with passwords no person
sees, verifies them, and deletes the enrollment login. D1/S1 stay unverified
until this runs on real hardware.
"""
import hashlib,hmac,ipaddress,json,os,re,secrets,tempfile,time
from datetime import datetime,timezone
from pathlib import Path
from cryptography import x509
from cryptography.hazmat.primitives.serialization import Encoding
from .bootstrap_security import POLICIES
from .enrollment import router_identity_digest
from .routeros_adapter import RouterOSClient,RouterOSCredential,RouterOSError,fetch_router_certificate,load_routeros_monitoring_credential,load_routeros_safe_change_credential

ENROLL_PREFIX='mm-enroll-'
CERTIFICATE_PREFIX='mm-mgmt-'
# Technician session length once the owner has added the router's Hub peer.
TECHNICIAN_SETUP_SECONDS=1800
GROUPS={'monitoring':'mm-monitor','safe_change':'mm-safechange'}
USER_PREFIX={'monitoring':'mm-monitor-','safe_change':'mm-safechange-'}
STORES={'monitoring':('MIKROMAGIC_ROUTEROS_MONITORING_SECRETS_DIR','/run/routeros-monitoring-secrets'),
 'safe_change':('MIKROMAGIC_ROUTEROS_SAFE_CHANGE_SECRETS_DIR','/run/routeros-safe-change-secrets'),
 'enroll':('MIKROMAGIC_ROUTEROS_ENROLL_SECRETS_DIR','/run/routeros-enroll-secrets')}

class ManagementSetupError(RuntimeError):
 def __init__(self,code,message,status=409):super().__init__(message);self.code=code;self.status=status

def serial_digest(serial):
 normalized=re.sub(r'\s+','',serial or '').upper()
 if not re.fullmatch(r'[A-Z0-9-]{6,32}',normalized):return None
 return hashlib.sha256(('mikromagic-router-serial-v1:'+normalized).encode()).hexdigest()

def store(role):
 env,default=STORES[role];root=Path(os.environ.get(env,default))
 try:
  if not root.is_dir() or root.is_symlink() or root.stat().st_mode&0o077:raise OSError()
 except OSError:raise ManagementSetupError('credential_storage_unavailable','Router credential storage is not configured on this server',503) from None
 return root.resolve()

def _write(root,name,text):
 fd,tmp=tempfile.mkstemp(dir=root,prefix='.tmp-')
 try:
  os.fchmod(fd,0o600)
  with os.fdopen(fd,'w',encoding='utf-8') as handle:handle.write(text)
  os.replace(tmp,root/name)
 except BaseException:
  Path(tmp).unlink(missing_ok=True);raise

def enrollment_password(router_id,create=False):
 """Temporary enrollment secret shown only on the technician's setup step."""
 root=store('enroll');path=root/(router_id+'.json')
 try:return json.loads(path.read_text(encoding='utf-8'))['password']
 except FileNotFoundError:pass
 except (OSError,ValueError,KeyError,TypeError):raise ManagementSetupError('credential_storage_unavailable','Temporary enrollment secret cannot be read',503) from None
 if not create:return None
 password=secrets.token_urlsafe(24);_write(root,router_id+'.json',json.dumps({'password':password}));return password

def discard_enrollment(router_id):
 root=store('enroll')
 for name in (router_id+'.json',router_id+'.pem'):(root/name).unlink(missing_ok=True)

def certificate_pem(der,address,now=None):
 try:cert=x509.load_der_x509_certificate(der)
 except ValueError:raise ManagementSetupError('certificate_invalid','Router presented an unreadable certificate') from None
 try:names=cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value.get_values_for_type(x509.IPAddress)
 except x509.ExtensionNotFound:names=[]
 if ipaddress.ip_address(address) not in names:raise ManagementSetupError('certificate_name_mismatch','Router certificate does not name the MikroMagic management address; recreate it with the shown command')
 moment=datetime.fromtimestamp(time.time() if now is None else now,timezone.utc)
 if not cert.not_valid_before_utc<=moment<cert.not_valid_after_utc:raise ManagementSetupError('certificate_expired','Router certificate is not currently valid; check the router clock')
 return cert.public_bytes(Encoding.PEM).decode()

def _row(value):
 if isinstance(value,list):
  if len(value)>1:raise ManagementSetupError('router_response_invalid','Router returned more than one matching record')
  value=value[0] if value else None
 if value is not None and not isinstance(value,dict):raise ManagementSetupError('router_response_invalid','Router returned an invalid record')
 return value

def _policy(value):return {p for p in str(value or '').split(',') if p and not p.startswith('!')}

def provision_management_identities(router_id,snapshot,expected_serial_digest,*,fetch=fetch_router_certificate,client_factory=RouterOSClient,now=None):
 """Return secret-free evidence; raise ManagementSetupError or RouterOSError on any stop."""
 id8=router_id[:8];router_ip=str(ipaddress.ip_interface(snapshot['router']['address']).ip);hub=snapshot['hub']['hub_address']
 roots={role:store(role) for role in STORES}
 password=enrollment_password(router_id)
 if not password:raise ManagementSetupError('enrollment_login_missing','Show the management step to the technician before finishing setup')
 if not expected_serial_digest:raise ManagementSetupError('router_serial_required','Enter the serial number from the router label when approving the plan')
 der=fetch(router_ip);pem=certificate_pem(der,router_ip,now);ca=router_id+'.pem'
 for role in STORES:_write(roots[role],ca,pem)
 base='https://'+router_ip;enroll=RouterOSCredential(base,ENROLL_PREFIX+id8,password,str(roots['enroll']/ca))
 with client_factory(enroll,router_id=router_id) as admin:
  resource=_row(admin.get('system/resource')) or {};board=_row(admin.get('system/routerboard')) or {}
  identity={'serial_number':board.get('serial-number'),'model':board.get('model'),'architecture-name':resource.get('architecture-name')}
  if not hmac.compare_digest(serial_digest(identity['serial_number']) or '',expected_serial_digest):
   raise ManagementSetupError('router_serial_mismatch','This router\'s serial number does not match the one entered by the owner; nothing was created')
  digest=router_identity_digest(identity)
  if not digest:raise ManagementSetupError('router_identity_unavailable','Router did not report its serial number, model and architecture')
  for role in ('monitoring','safe_change'):
   group=GROUPS[role];name=USER_PREFIX[role]+id8;existing=_row(admin.get('user/group?name='+group))
   if existing and _policy(existing.get('policy'))!=set(POLICIES[role]):raise ManagementSetupError('group_conflict',f'RouterOS group {group} already exists with different rights')
   if not existing:admin.write('PUT','user/group',{'name':group,'policy':','.join(POLICIES[role]),'comment':'MikroMagic'})
   secret=secrets.token_urlsafe(32);user=_row(admin.get('user?name='+name))
   if user and user.get('group')!=group:raise ManagementSetupError('user_conflict',f'RouterOS user {name} already exists in another group')
   fields={'password':secret,'address':hub+'/32','disabled':'false'}
   if user:admin.write('PATCH','user/'+user['.id'],fields)
   else:admin.write('PUT','user',{'name':name,'group':group,'comment':'MikroMagic '+role.replace('_',' '),**fields})
   _write(roots[role],router_id+'.json',json.dumps({'base_url':base,'username':name,'password':secret,'ca_bundle':ca}))
 checks={}
 with client_factory(load_routeros_monitoring_credential(router_id,str(roots['monitoring'])),router_id=router_id) as monitor:
  current=(_row(monitor.get('system/identity')) or {}).get('name')
  try:monitor.write('POST','system/identity/set',{'name':current});checks['monitoring_write_denied']=False
  except RouterOSError:checks['monitoring_write_denied']=True
 if not checks['monitoring_write_denied']:raise ManagementSetupError('monitoring_write_not_denied','The monitoring login could write to the router; setup stopped before removing the enrollment login')
 with client_factory(load_routeros_safe_change_credential(router_id,str(roots['safe_change'])),router_id=router_id) as change:change.get('system/resource');checks['safe_change_login']=True
 with client_factory(enroll,router_id=router_id) as admin:
  user=_row(admin.get('user?name='+ENROLL_PREFIX+id8))
  if user:
   try:admin.write('DELETE','user/'+user['.id'],None)
   except RouterOSError:pass
 try:
  with client_factory(enroll,router_id=router_id) as admin:admin.get('system/resource')
  raise ManagementSetupError('enrollment_login_not_removed','The temporary enrollment login still works; remove it with the rollback command')
 except RouterOSError as error:
  if error.code!='authentication_failed':raise ManagementSetupError('enrollment_cleanup_unverified','Could not confirm the temporary enrollment login was removed') from None
 checks['enrollment_login_removed']=True;discard_enrollment(router_id)
 return {'identity_digest':digest,'model':identity['model'],'architecture':identity['architecture-name'],
  'certificate_sha256':hashlib.sha256(der).hexdigest(),'usernames':[USER_PREFIX[r]+id8 for r in ('monitoring','safe_change')],'checks':checks}
