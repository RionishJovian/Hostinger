"""Real RouterOS REST read-only discovery transport.

Credentials are loaded from operator-mounted files, never accepted from browser
requests or persisted in the control-plane database. A successful pre-flight is
evidence of that request only; it is not WireGuard/HotSpot acceptance.
"""
from __future__ import annotations
import base64,json,os,socket,time,ssl
from dataclasses import dataclass,field
from pathlib import Path
from urllib.parse import urlparse
from urllib.parse import quote
from datetime import datetime,timezone
import hashlib,re
import httpx
from .routeros_compatibility import classify_routeros_compatibility

class RouterOSError(RuntimeError):
 def __init__(self,code,message,status=503):super().__init__(message);self.code=code;self.status=status

def _connection_error(error):
 cause=error;seen=set()
 while cause is not None and id(cause) not in seen:
  seen.add(id(cause))
  if isinstance(cause,ssl.SSLCertVerificationError) or 'CERTIFICATE_VERIFY_FAILED' in str(cause):
   return RouterOSError('tls_verification_failed','Router certificate validation failed; no insecure retry is permitted')
  cause=cause.__cause__ or cause.__context__
 return RouterOSError('unreachable','Router management endpoint is unreachable')

@dataclass(frozen=True)
class RouterOSCredential:
 base_url:str
 username:str
 password:str=field(repr=False)
 verify:bool|str=True

def _load_routeros_identity(router_id:str,identity:str,directory:str|None=None)->RouterOSCredential:
 if identity not in ('monitoring','safe-change'):raise RouterOSError('credential_invalid','Router management identity is invalid',500)
 env='MIKROMAGIC_ROUTEROS_MONITORING_SECRETS_DIR' if identity=='monitoring' else 'MIKROMAGIC_ROUTEROS_SAFE_CHANGE_SECRETS_DIR'
 default='/run/routeros-monitoring-secrets' if identity=='monitoring' else '/run/routeros-safe-change-secrets'
 root=Path(directory or os.environ.get(env,default)).resolve()
 candidate=root/(router_id+'.json')
 if candidate.is_symlink():raise RouterOSError('credential_invalid','Router credential reference is invalid',500)
 path=candidate.resolve()
 if path.parent!=root:raise RouterOSError('credential_invalid','Router credential reference is invalid',500)
 try:data=json.loads(path.read_text(encoding='utf-8'))
 except FileNotFoundError:raise RouterOSError('credential_missing','Router credential is not installed',409)
 except (OSError,UnicodeDecodeError,json.JSONDecodeError):raise RouterOSError('credential_invalid','Router credential cannot be read',500)
 try:
  if root.stat().st_mode&0o007 or path.stat().st_mode&0o007:raise RouterOSError('credential_permissions','Router credential is accessible to other users',500)
 except OSError:raise RouterOSError('credential_invalid','Router credential permissions cannot be checked',500)
 if not isinstance(data,dict) or set(data)-{'base_url','username','password','ca_bundle'}:raise RouterOSError('credential_invalid','Router credential has unsupported fields',500)
 if not all(isinstance(data.get(k),str) and data[k] for k in ['base_url','username','password']):raise RouterOSError('credential_invalid','Router credential is incomplete',500)
 expected='mm-monitor-'+router_id[:8] if identity=='monitoring' else 'mm-safechange-'+router_id[:8]
 if data['username']!=expected:raise RouterOSError('credential_identity','Credential does not match the dedicated '+identity+' RouterOS identity',500)
 url=data['base_url'].rstrip('/');parsed=urlparse(url);allow_http=os.environ.get('MIKROMAGIC_ROUTEROS_ALLOW_HTTP','').lower()=='true'
 if parsed.scheme!='https' and not (allow_http and parsed.scheme=='http'):raise RouterOSError('transport_policy','RouterOS REST requires HTTPS; HTTP is allowed only in an explicitly isolated acceptance lab',409)
 if parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in ('','/'):raise RouterOSError('credential_invalid','Router base URL must contain only scheme, host and optional port',500)
 verify:bool|str=True
 if data.get('ca_bundle'):
  ca_candidate=root/data['ca_bundle']
  if ca_candidate.is_symlink():raise RouterOSError('credential_invalid','Router CA bundle is unavailable',500)
  ca=ca_candidate.resolve()
  if ca.parent!=root or not ca.is_file():raise RouterOSError('credential_invalid','Router CA bundle is unavailable',500)
  verify=str(ca)
 return RouterOSCredential(url,data['username'],data['password'],verify)

def load_routeros_monitoring_credential(router_id:str,directory:str|None=None)->RouterOSCredential:
 return _load_routeros_identity(router_id,'monitoring',directory)

def load_routeros_safe_change_credential(router_id:str,directory:str|None=None)->RouterOSCredential:
 return _load_routeros_identity(router_id,'safe-change',directory)

# Compatibility name remains read-only by default; write paths must call the
# explicit Safe Change loader so monitoring credentials can never authorize writes.
def load_routeros_credential(router_id:str,directory:str|None=None)->RouterOSCredential:
 return load_routeros_monitoring_credential(router_id,directory)

def management_proxy_from_environment():
 """Return the Hub relay proxy URL, or None when routers are reached directly."""
 url=os.environ.get('MIKROMAGIC_HUB_RELAY_URL','')
 if not url:return None
 parsed=urlparse(url)
 if parsed.scheme!='http' or parsed.hostname!='magic-hub' or parsed.port!=8791 or parsed.username or parsed.path not in ('','/') or parsed.query or parsed.fragment:
  raise RouterOSError('relay_invalid','Hub management relay is not the fixed internal endpoint',500)
 token_file=os.environ.get('MIKROMAGIC_HUB_AGENT_TOKEN_FILE','')
 try:token=Path(token_file).read_text(encoding='utf-8').strip() if os.path.isabs(token_file) else ''
 except OSError:token=''
 if not re.fullmatch(r'[A-Za-z0-9_-]{40,160}',token):raise RouterOSError('relay_unavailable','Hub management relay credential is unavailable',503)
 return f'http://mikromagic:{token}@magic-hub:8791'

def pinned_tls_context(ca_bundle:str)->ssl.SSLContext:
 """Trust exactly the pinned router certificate, which RouterOS self-signs."""
 context=ssl.create_default_context(cafile=ca_bundle)
 context.verify_flags|=ssl.VERIFY_X509_PARTIAL_CHAIN
 context.verify_flags&=~getattr(ssl,'VERIFY_X509_STRICT',0)
 return context

def fetch_router_certificate(address:str,port:int=443,timeout:float=8.0):
 """Read the router's TLS certificate over the Hub relay without trusting it.

 The caller pins it only after checking it names the management address; the
 relay reaches only provisioned WireGuard peers, so the tunnel key binds it.
 """
 proxy=management_proxy_from_environment()
 try:
  if proxy:
   parsed=urlparse(proxy);sock=socket.create_connection((parsed.hostname,parsed.port),timeout)
   auth=base64.b64encode(f'{parsed.username}:{parsed.password}'.encode()).decode()
   sock.sendall(f'CONNECT {address}:{port} HTTP/1.1\r\nHost: {address}:{port}\r\nProxy-Authorization: Basic {auth}\r\n\r\n'.encode())
   head=b''
   while b'\r\n\r\n' not in head and len(head)<4096:
    chunk=sock.recv(1024)
    if not chunk:break
    head+=chunk
   if not head.startswith(b'HTTP/1.1 200'):sock.close();raise RouterOSError('unreachable','Hub relay refused the router management connection')
  else:sock=socket.create_connection((address,port),timeout)
  context=ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT);context.check_hostname=False;context.verify_mode=ssl.CERT_NONE
  with context.wrap_socket(sock) as tls:der=tls.getpeercert(binary_form=True)
 except (OSError,ssl.SSLError):raise RouterOSError('unreachable','Router management endpoint is unreachable')
 if not der:raise RouterOSError('tls_verification_failed','Router did not present a certificate')
 return der

class RouterOSClient:
 def __init__(self,credential:RouterOSCredential,transport=None,timeout=8.0):
  proxy=None if transport else management_proxy_from_environment()
  verify=pinned_tls_context(credential.verify) if isinstance(credential.verify,str) else credential.verify
  self.credential=credential;self.client=httpx.Client(base_url=credential.base_url,auth=(credential.username,credential.password),verify=verify,timeout=timeout,transport=transport,proxy=proxy,trust_env=False,follow_redirects=False,headers={'Accept':'application/json','User-Agent':'MikroMagic-Build21/1.0'})
 def close(self):self.client.close()
 def __enter__(self):return self
 def __exit__(self,*args):self.close()
 def get(self,path,optional=False):
  try:r=self.client.get('/rest/'+path.lstrip('/'))
  except httpx.TimeoutException:raise RouterOSError('timeout','Router did not answer before the pre-flight timeout')
  except httpx.ConnectError as error:raise _connection_error(error) from None
  except httpx.HTTPError:raise RouterOSError('transport_error','Router management transport failed')
  if optional and r.status_code in (400,404):return None
  if r.status_code in (401,403):raise RouterOSError('authentication_failed','Router rejected the installed management credential',401)
  if r.status_code>=400:raise RouterOSError('router_error','Router rejected a read-only pre-flight request')
  try:return r.json()
  except ValueError:raise RouterOSError('invalid_response','Router returned an invalid management response')
 def write(self,method,path,payload):
  try:r=self.client.request(method,'/rest/'+path.lstrip('/'),json=payload)
  except httpx.TimeoutException:raise RouterOSError('timeout','Router did not answer before the change timeout')
  except httpx.ConnectError:raise RouterOSError('unreachable','Router management endpoint is unreachable')
  except httpx.HTTPError:raise RouterOSError('transport_error','Router management transport failed')
  if r.status_code in (401,403):raise RouterOSError('authentication_failed','Router rejected the installed management credential',401)
  if r.status_code>=400:raise RouterOSError('router_write_failed','Router rejected the controlled configuration request')
  if not r.content:return {}
  try:return r.json()
  except ValueError:return {'accepted':True}
 def export_configuration(self):
  value=self.write('POST','export',{'show-sensitive':'no','terse':'yes'})
  if isinstance(value,dict):text=value.get('ret') or value.get('output') or value.get('value')
  else:text=None
  if not isinstance(text,str) or not text.strip():raise RouterOSError('backup_invalid','Router did not return a usable sensitive-redacted configuration export')
  return text.encode('utf-8')

def _first(value):
 if isinstance(value,list):return value[0] if value else {}
 return value if isinstance(value,dict) else {}

def _records(value):
 if isinstance(value,list):return [x for x in value if isinstance(x,dict)]
 return [value] if isinstance(value,dict) else []

def hotspot_portal_inventory(servers,profiles,walled_garden,files):
 """Return a read-only, secret-minimized HotSpot portal inventory.

 This is planning evidence only. It deliberately does not return file contents,
 RADIUS fields, credentials, or any executable RouterOS operation.
 """
 servers=_records(servers);profiles=_records(profiles);rules=_records(walled_garden);files=_records(files)
 usage={}
 for server in servers:
  profile=server.get('profile')
  if isinstance(profile,str):usage[profile]=usage.get(profile,0)+1
 directories=set()
 safe_profiles=[]
 for profile in profiles:
  item={k:profile[k] for k in ['.id','name','dns-name','hotspot-address','login-by','html-directory','html-directory-override','html-override-directory'] if k in profile}
  item['server_count']=usage.get(profile.get('name'),0)
  for key in ('html-directory','html-directory-override','html-override-directory'):
   value=profile.get(key)
   if isinstance(value,str) and value.strip():directories.add(value.strip().strip('/'))
  safe_profiles.append(item)
 active_files=[]
 flash_present=False
 for file in files:
  name=file.get('name')
  if not isinstance(name,str):continue
  normalized=name.strip().strip('/')
  if normalized=='flash':flash_present=True
  if any(normalized==directory or normalized.startswith(directory+'/') for directory in directories):
   active_files.append({k:file[k] for k in ['name','type','size','last-modified'] if k in file})
 safe_servers=[]
 for server in servers:
  item={k:server[k] for k in ['.id','name','interface','profile','disabled'] if k in server}
  item['profile_server_count']=usage.get(server.get('profile'),0)
  safe_servers.append(item)
 safe_rules=[{k:rule[k] for k in ['.id','server','action','dst-host','path','dst-port'] if k in rule} for rule in rules]
 return {'evidence_source':'routeros_rest_live_read','write_operations_enabled':False,
  'servers':safe_servers,'profiles':safe_profiles,'walled_garden_rules':safe_rules,
  'storage':{'flash_directory_present':flash_present,'configured_portal_files':active_files}}

def read_hotspot_portal_inventory(client):
 """Collect HotSpot profile/file metadata using GET requests only."""
 servers=client.get('ip/hotspot',optional=True)
 if not servers:return hotspot_portal_inventory([],[],[],[])
 profiles=client.get('ip/hotspot/profile',optional=True)
 garden=client.get('ip/hotspot/walled-garden',optional=True)
 files=client.get('file',optional=True)
 return hotspot_portal_inventory(servers,profiles,garden,files)

def discover_routeros(client:RouterOSClient):
 checked=int(time.time());resource=_first(client.get('system/resource'));board=_first(client.get('system/routerboard',optional=True))
 probes={
  'wireguard':'interface/wireguard',
  'hotspot':'ip/hotspot',
  'hotspot_users':'ip/hotspot/user',
  'dhcp_server':'ip/dhcp-server',
  'ntp_client':'system/ntp/client',
 }
 capabilities={};counts={}
 for name,path in probes.items():
  value=client.get(path,optional=True);capabilities[name]=value is not None
  if isinstance(value,list):counts[name]=len(value)
 identity={k:resource.get(k) for k in ['platform','version','architecture-name','board-name','cpu-count','total-memory','free-memory','free-hdd-space','uptime'] if resource.get(k) is not None}
 if board:
  identity['routerboard']=board.get('routerboard');identity['model']=board.get('model');identity['serial_number']=board.get('serial-number');identity['factory_firmware']=board.get('factory-firmware');identity['current_firmware']=board.get('current-firmware');identity['upgrade_firmware']=board.get('upgrade-firmware')
 portal_inventory=read_hotspot_portal_inventory(client) if capabilities.get('hotspot') else hotspot_portal_inventory([],[],[],[])
 transport={'scheme':urlparse(client.credential.base_url).scheme,'tls_verified':client.credential.verify is not False}
 compatibility=classify_routeros_compatibility(identity,capabilities,transport,read_access_verified=True)
 return {'checked_at':checked,'evidence_source':'routeros_rest_live_read','transport':transport,'identity':identity,'capabilities':capabilities,'compatibility':compatibility,'inventory_counts':counts,'hotspot_portal_inventory':portal_inventory,'connection_claim':'preflight_reachable_only','wireguard_handshake_verified':False,'hotspot_enforcement_verified':False,'configuration_modified':False}

def _duration_seconds(value:str):
 """Parse RouterOS duration or an ISO timestamp into an approximate age."""
 if not isinstance(value,str) or not value.strip():return None
 value=value.strip().lower()
 if value in ('never','none','0s'):return None
 try:
  stamp=datetime.fromisoformat(value.replace('z','+00:00'))
  if stamp.tzinfo is None:stamp=stamp.replace(tzinfo=timezone.utc)
  return max(0,int((datetime.now(timezone.utc)-stamp).total_seconds()))
 except ValueError:pass
 total=0;rest=value
 units={'w':604800,'d':86400,'h':3600,'m':60,'s':1,'ms':.001,'us':.000001,'ns':.000000001}
 for number,unit in re.findall(r'(\d+(?:\.\d+)?)(ms|us|ns|w|d|h|m|s)',value):
  total+=float(number)*units[unit];rest=rest.replace(number+unit,'',1)
 match=re.fullmatch(r'(?:(\d+):)?(\d+):(\d+(?:\.\d+)?)',rest)
 if match:total+=int(match.group(1) or 0)*3600+int(match.group(2))*60+float(match.group(3));rest=''
 return int(total) if total and not rest else None

def _key_fingerprint(value):return hashlib.sha256(str(value).encode()).hexdigest()[:12] if value else None

def observe_wireguard_peer(client:RouterOSClient,plan:dict,recent_seconds:int|None=None):
 """Read router-side peer state; this never proves the hub side or tunnel reachability."""
 checked=int(time.time());recent_seconds=recent_seconds or int(os.environ.get('MIKROMAGIC_WIREGUARD_RECENT_SECONDS','180'))
 peers=client.get('interface/wireguard/peers',optional=True) or []
 if not isinstance(peers,list):peers=[peers] if isinstance(peers,dict) else []
 hub=(plan or {}).get('hub') or {};router=(plan or {}).get('router') or {};expected_key=hub.get('public_key');expected_interface=router.get('interface')
 peer=next((p for p in peers if isinstance(p,dict) and p.get('public-key')==expected_key),None)
 age=_duration_seconds(peer.get('last-handshake')) if peer else None
 interface_match=bool(peer and peer.get('interface')==expected_interface)
 observed=bool(peer and interface_match and age is not None and age<=recent_seconds)
 return {'observed_at':checked,'evidence_source':'routeros_rest_live_read','peer_found':bool(peer),'planned_hub_key_match':bool(peer),'planned_hub_key_fingerprint':_key_fingerprint(expected_key),'interface_match':interface_match,'expected_interface':expected_interface,'observed_interface':peer.get('interface') if peer else None,'last_handshake_raw':peer.get('last-handshake') if peer else None,'handshake_age_seconds':age,'recent_threshold_seconds':recent_seconds,'router_side_handshake_observed':observed,'rx_bytes':peer.get('rx') if peer else None,'tx_bytes':peer.get('tx') if peer else None,'hub_side_handshake_verified':False,'management_reachability_verified':False,'hotspot_enforcement_verified':False,'configuration_modified':False,'acceptance_complete':False}

def wireguard_peer_state(client:RouterOSClient,hub_public_key:str):
 peers=client.get('interface/wireguard/peers')
 if not isinstance(peers,list):raise RouterOSError('invalid_response','Router returned an invalid WireGuard peer list')
 peer=next((x for x in peers if isinstance(x,dict) and x.get('public-key')==hub_public_key),None)
 if not peer or not peer.get('.id'):raise RouterOSError('peer_missing','The planned Magic Hub peer is not present on this router',409)
 return {'resource_id':str(peer['.id']),'interface':peer.get('interface'),'persistent_keepalive_seconds':int(peer.get('persistent-keepalive') or 0),'disabled':str(peer.get('disabled','false')).lower()=='true','public_key_fingerprint':_key_fingerprint(hub_public_key)}

def set_wireguard_keepalive(client:RouterOSClient,resource_id:str,seconds:int):
 if not isinstance(resource_id,str) or not re.fullmatch(r'\*[A-Fa-f0-9]+',resource_id):raise RouterOSError('resource_invalid','Router resource identifier is invalid',409)
 return client.write('PATCH','interface/wireguard/peers/'+quote(resource_id,safe=''),{'persistent-keepalive':str(seconds)})

def _int_field(value):
 if value is None or value=='':return 0
 try:return max(0,int(float(str(value))))
 except (TypeError,ValueError):return 0

def list_hotspot_active(client:RouterOSClient):
 """Return sanitized HotSpot active sessions (read-only)."""
 rows=client.get('ip/hotspot/active',optional=True)
 guests=[]
 for item in _records(rows):
  user=item.get('user')
  if not isinstance(user,str) or not user:continue
  guests.append({
   'resource_id':str(item.get('.id') or ''),
   'user':user,
   'mac':item.get('mac-address') or item.get('mac'),
   'address':item.get('address'),
   'server':item.get('server'),
   'uptime_seconds':_duration_seconds(str(item.get('uptime') or '')) or 0,
   'bytes_in':_int_field(item.get('bytes-in')),
   'bytes_out':_int_field(item.get('bytes-out')),
  })
 return guests

def list_mikromagic_hotspot_users(client:RouterOSClient,comment_prefix:str):
 """Return MikroMagic-owned HotSpot users with usage and comment markers."""
 rows=client.get('ip/hotspot/user',optional=True)
 users=[]
 for item in _records(rows):
  comment=str(item.get('comment') or '')
  if not comment.startswith(comment_prefix):continue
  name=item.get('name')
  if not isinstance(name,str) or not name:continue
  users.append({
   'resource_id':str(item.get('.id') or ''),
   'name':name,
   'comment':comment,
   'disabled':str(item.get('disabled','false')).lower()=='true',
   'bytes_in':_int_field(item.get('bytes-in')),
   'bytes_out':_int_field(item.get('bytes-out')),
   'uptime_seconds':_duration_seconds(str(item.get('uptime') or '')) or 0,
  })
 return users

def _profile_html_directory(profile:dict):
 for key in ('html-directory-override','html-override-directory','html-directory'):
  value=profile.get(key)
  if isinstance(value,str) and value.strip():return value.strip()
 return 'hotspot'

def _destination_files(files,destination:str):
 prefix=destination.rstrip('/')+'/'
 matches=[]
 for item in _records(files):
  name=item.get('name')
  if not isinstance(name,str):continue
  if name==destination or name.startswith(prefix):matches.append(item)
 return matches

def hotspot_portal_publish_state(client:RouterOSClient,*,profile_name:str,destination:str,expected_files:list[str]|None=None):
 """Read selected HotSpot profile directory and destination file presence for Safe Change."""
 if not isinstance(profile_name,str) or not profile_name or len(profile_name)>120:raise RouterOSError('resource_invalid','HotSpot profile name is invalid',409)
 if not isinstance(destination,str) or not re.fullmatch(r'(?:flash/)?mm-b21-[A-Za-z0-9_-]{1,8}-r[1-9][0-9]{0,8}',destination):
  raise RouterOSError('resource_invalid','Portal destination directory is invalid',409)
 profiles=client.get('ip/hotspot/profile')
 profile=next((item for item in _records(profiles) if item.get('name')==profile_name),None)
 if not profile or not profile.get('.id'):raise RouterOSError('profile_missing','The selected HotSpot profile is not present on this router',409)
 files=client.get('file',optional=True)
 present=_destination_files(files,destination)
 installed=[]
 expected=list(expected_files or [])
 for name in expected:
  path=destination.rstrip('/')+'/'+name
  match=next((item for item in present if item.get('name')==path),None)
  if match:installed.append({'name':name,'size':match.get('size')})
 return {
  'resource_id':str(profile['.id']),
  'profile_name':profile_name,
  'html_directory':_profile_html_directory(profile),
  'destination':destination,
  'destination_present':bool(present),
  'installed_files':installed,
 }

def install_hotspot_portal_files(client:RouterOSClient,destination:str,files:dict[str,str]):
 """Create-only upload of portal servlet files into a new unique directory."""
 if not files:raise RouterOSError('package_invalid','Portal package has no installable files',409)
 state_files=client.get('file',optional=True)
 if _destination_files(state_files,destination):raise RouterOSError('file_collision','Destination portal directory already exists; refusing to overwrite',409)
 for name,contents in files.items():
  if not isinstance(name,str) or '/' in name or name in ('.','..') or not re.fullmatch(r'[A-Za-z0-9._-]+',name):
   raise RouterOSError('package_invalid','Portal package file name is unsafe',409)
  if not isinstance(contents,str):raise RouterOSError('package_invalid','Portal package file contents must be text',409)
  path=destination.rstrip('/')+'/'+name
  client.write('PUT','file/'+quote(path,safe=''),{'contents':contents})
 after=client.get('file',optional=True)
 missing=[name for name in files if not any(item.get('name')==destination.rstrip('/')+'/'+name for item in _destination_files(after,destination))]
 if missing:raise RouterOSError('install_incomplete','Portal files were not all present after create-only upload',409)
 return {'destination':destination,'files':sorted(files)}

def set_hotspot_profile_html_directory(client:RouterOSClient,resource_id:str,directory:str):
 if not isinstance(resource_id,str) or not re.fullmatch(r'\*[A-Fa-f0-9]+',resource_id):raise RouterOSError('resource_invalid','Router resource identifier is invalid',409)
 if not isinstance(directory,str) or not directory or len(directory)>200 or '..' in directory.split('/'):
  raise RouterOSError('resource_invalid','HotSpot html-directory value is invalid',409)
 return client.write('PATCH','ip/hotspot/profile/'+quote(resource_id,safe=''),{'html-directory':directory})

def remove_hotspot_portal_files(client:RouterOSClient,destination:str,names:list[str]):
 """Delete only MikroMagic-created portal files after the profile no longer points at them."""
 for name in names:
  path=destination.rstrip('/')+'/'+name
  try:client.write('DELETE','file/'+quote(path,safe=''),{})
  except RouterOSError as error:
   if error.code not in ('router_write_failed',):raise
 remaining=_destination_files(client.get('file',optional=True),destination)
 if remaining:raise RouterOSError('cleanup_incomplete','Newly created portal files remain after rollback cleanup',409)
 return {'destination':destination,'removed':list(names)}
