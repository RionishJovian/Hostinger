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
 def __init__(self,credential:RouterOSCredential,transport=None,timeout=8.0,router_id:str|None=None):
  """REST client. Pass router_id so the session holds the per-router REST lock.

  RouterOS serves one REST request at a time per router; aborted sockets do not
  free the queue. Every production call site must pass router_id.
  """
  proxy=None if transport else management_proxy_from_environment()
  verify=pinned_tls_context(credential.verify) if isinstance(credential.verify,str) else credential.verify
  self.credential=credential;self.router_id=router_id;self._lock_cm=None
  # Cap a single HTTP call at 60s (RouterOS session limit); default stays short for probes.
  timeout=min(float(timeout),60.0)
  self.client=httpx.Client(base_url=credential.base_url,auth=(credential.username,credential.password),verify=verify,timeout=timeout,transport=transport,proxy=proxy,trust_env=False,follow_redirects=False,headers={'Accept':'application/json','User-Agent':'MikroMagic-Build21/1.0'})
 def close(self):self.client.close()
 def __enter__(self):
  if self.router_id:
   from .routeros_lock import hold_router_rest_lock
   self._lock_cm=hold_router_rest_lock(self.router_id)
   self._lock_cm.__enter__()
  return self
 def __exit__(self,exc_type,exc,tb):
  try:self.close()
  finally:
   if self._lock_cm is not None:
    cm=self._lock_cm;self._lock_cm=None
    cm.__exit__(exc_type,exc,tb)
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
  # RouterOS rejects a DELETE that carries a body.
  try:r=self.client.request(method,'/rest/'+path.lstrip('/'),json=None if method=='DELETE' else payload)
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
  if not isinstance(text,str) or not text.strip():
   # RouterOS 7 REST answers `export` with an empty list; `execute as-string` returns the text, secrets hidden by default.
   value=self.write('POST','execute',{'script':'/export terse','as-string':''})
   text=value.get('ret') if isinstance(value,dict) else None
   if not isinstance(text,str) or not text.startswith('# '):text=None
  if not isinstance(text,str) or not text.strip():raise RouterOSError('backup_invalid','Router did not return a usable sensitive-redacted configuration export')
  return text.encode('utf-8')

# Without .proplist RouterOS REST inlines file contents, and binary files break JSON.
FILE_LIST='file?.proplist=name,type,size,last-modified'

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
 files=client.get(FILE_LIST,optional=True)
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
 # RouterOS rejects a percent-encoded `*` in resource ids.
 return client.write('PATCH','interface/wireguard/peers/'+resource_id,{'persistent-keepalive':str(seconds)})

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
 files=client.get(FILE_LIST,optional=True)
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
 state_files=client.get(FILE_LIST,optional=True)
 if _destination_files(state_files,destination):raise RouterOSError('file_collision','Destination portal directory already exists; refusing to overwrite',409)
 for name,contents in files.items():
  if not isinstance(name,str) or '/' in name or name in ('.','..') or not re.fullmatch(r'[A-Za-z0-9._-]+',name):
   raise RouterOSError('package_invalid','Portal package file name is unsafe',409)
  if not isinstance(contents,str):raise RouterOSError('package_invalid','Portal package file contents must be text',409)
  path=destination.rstrip('/')+'/'+name
  # RouterOS creates the parent directory and refuses to replace an existing file.
  client.write('PUT','file',{'name':path,'contents':contents})
 after=client.get(FILE_LIST,optional=True)
 missing=[name for name in files if not any(item.get('name')==destination.rstrip('/')+'/'+name for item in _destination_files(after,destination))]
 if missing:raise RouterOSError('install_incomplete','Portal files were not all present after create-only upload',409)
 return {'destination':destination,'files':sorted(files)}

def set_hotspot_profile_html_directory(client:RouterOSClient,resource_id:str,directory:str):
 if not isinstance(resource_id,str) or not re.fullmatch(r'\*[A-Fa-f0-9]+',resource_id):raise RouterOSError('resource_invalid','Router resource identifier is invalid',409)
 if not isinstance(directory,str) or not directory or len(directory)>200 or '..' in directory.split('/'):
  raise RouterOSError('resource_invalid','HotSpot html-directory value is invalid',409)
 return client.write('PATCH','ip/hotspot/profile/'+resource_id,{'html-directory':directory})

def remove_hotspot_portal_files(client:RouterOSClient,destination:str,names:list[str]):
 """Delete only MikroMagic-created portal files after the profile no longer points at them."""
 for name in names:
  path=destination.rstrip('/')+'/'+name
  try:client.write('DELETE','file/'+quote(path,safe=''),{})
  except RouterOSError as error:
   if error.code not in ('router_write_failed',):raise
 remaining=_destination_files(client.get(FILE_LIST,optional=True),destination)
 directory=next((item for item in remaining if item.get('name')==destination and item.get('type')=='directory' and item.get('.id')),None)
 if directory and len(remaining)==1:
  client.write('POST','file/remove',{'.id':directory['.id']})
  remaining=_destination_files(client.get(FILE_LIST,optional=True),destination)
 if remaining:raise RouterOSError('cleanup_incomplete','Newly created portal files remain after rollback cleanup',409)
 return {'destination':destination,'removed':list(names)}


# --- Guest Wi-Fi / guest network Safe Change helpers (RouterOS 7 /interface/wifi) ---

_WIFI_ID=re.compile(r'\*[A-Fa-f0-9]+')
_IFACE_NAME=re.compile(r'^[A-Za-z0-9_.-]{1,64}$')
HUB_MGMT_NETWORK='10.90.0.0/16'


def _truthy(value):
 return str(value).lower() in ('true','yes','1')


def _iface_name_ok(name):
 return isinstance(name,str) and bool(_IFACE_NAME.fullmatch(name))


def _resource_path(kind,resource_id):
 if not isinstance(resource_id,str) or not _WIFI_ID.fullmatch(resource_id):
  raise RouterOSError('resource_invalid','Router resource identifier is invalid',409)
 return f'{kind}/{resource_id}'


def list_wifi_interfaces(client:RouterOSClient):
 rows=client.get('interface/wifi',optional=True)
 if rows is None:
  rows=client.get('interface/wifiwave2',optional=True)
 return _records(rows)


def list_wifi_configurations(client:RouterOSClient):
 rows=client.get('interface/wifi/configuration',optional=True)
 if rows is None:rows=client.get('interface/wifiwave2/configuration',optional=True)
 return _records(rows)


def list_wifi_securities(client:RouterOSClient):
 rows=client.get('interface/wifi/security',optional=True)
 if rows is None:rows=client.get('interface/wifiwave2/security',optional=True)
 return _records(rows)


def list_bridge_ports(client:RouterOSClient):
 return _records(client.get('interface/bridge/port',optional=True))


def list_ip_addresses(client:RouterOSClient):
 return _records(client.get('ip/address',optional=True))


def list_ip_pools(client:RouterOSClient):
 return _records(client.get('ip/pool',optional=True))


def list_dhcp_servers(client:RouterOSClient):
 return _records(client.get('ip/dhcp-server',optional=True))


def list_dhcp_networks(client:RouterOSClient):
 return _records(client.get('ip/dhcp-server/network',optional=True))


def list_hotspot_servers(client:RouterOSClient):
 return _records(client.get('ip/hotspot',optional=True))


def list_hotspot_profiles(client:RouterOSClient):
 return _records(client.get('ip/hotspot/profile',optional=True))


def _wifi_mode(iface:dict):
 for key in ('configuration.mode','mode'):
  value=iface.get(key)
  if isinstance(value,str) and value.strip():return value.strip().lower()
 return ''


def _wifi_ssid(iface:dict,configurations:list[dict]|None=None):
 for key in ('configuration.ssid','ssid'):
  value=iface.get(key)
  if isinstance(value,str):return value
 config_name=iface.get('configuration')
 if isinstance(config_name,str) and config_name.strip() and configurations:
  match=next((c for c in configurations if c.get('name')==config_name),None)
  if match and isinstance(match.get('ssid'),str):return match['ssid']
 return ''


def _wifi_auth_types(iface:dict,securities:list[dict]|None=None):
 for key in ('security.authentication-types','authentication-types'):
  value=iface.get(key)
  if isinstance(value,str):return value
  if isinstance(value,list):return ','.join(str(x) for x in value)
 sec_name=iface.get('security')
 if isinstance(sec_name,str) and sec_name.strip() and securities:
  match=next((s for s in securities if s.get('name')==sec_name),None)
  if match:
   value=match.get('authentication-types')
   if isinstance(value,str):return value
   if isinstance(value,list):return ','.join(str(x) for x in value)
 return ''


def _wifi_passphrase_value(iface:dict,securities:list[dict]|None=None):
 """Return the live passphrase when RouterOS includes it; never log this value."""
 for key in ('security.passphrase','passphrase'):
  value=iface.get(key)
  if isinstance(value,str) and value and value not in ('*','****','********'):
   return value
 sec_name=iface.get('security')
 if isinstance(sec_name,str) and sec_name.strip() and securities:
  match=next((s for s in securities if s.get('name')==sec_name),None)
  if match:
   value=match.get('passphrase')
   if isinstance(value,str) and value and value not in ('*','****','********'):
    return value
 return None


def _wifi_passphrase_present(iface:dict,securities:list[dict]|None=None):
 return _wifi_passphrase_value(iface,securities) is not None or any(
  isinstance(iface.get(key),str) and iface.get(key) for key in ('security.passphrase','passphrase')
 )


def _named_profile_users(interfaces:list[dict],field:str,name:str):
 return [i for i in interfaces if isinstance(i.get(field),str) and i.get(field)==name]


def wifi_interface_state(client:RouterOSClient,interface_name:str):
 """Return secret-free wifi interface state for Safe Change fingerprinting."""
 if not _iface_name_ok(interface_name):raise RouterOSError('resource_invalid','Wi-Fi interface name is invalid',409)
 interfaces=list_wifi_interfaces(client)
 if not interfaces:raise RouterOSError('wifi_unsupported','This router has no /interface/wifi package',409)
 iface=next((i for i in interfaces if i.get('name')==interface_name),None)
 if not iface or not iface.get('.id'):raise RouterOSError('wifi_missing','The selected Wi-Fi interface is not present',409)
 configurations=list_wifi_configurations(client)
 securities=list_wifi_securities(client)
 config_name=iface.get('configuration') if isinstance(iface.get('configuration'),str) and iface.get('configuration') and not str(iface.get('configuration')).startswith('{') else None
 # Named profile when `configuration` is a plain profile name (no nested ssid on the interface itself).
 if config_name and iface.get('configuration.ssid') is None:
  users=_named_profile_users(interfaces,'configuration',config_name)
  config_shared=len(users)>1
 else:
  config_name=None;config_shared=False
 sec_name=iface.get('security') if isinstance(iface.get('security'),str) and iface.get('security') and iface.get('security.authentication-types') is None and iface.get('authentication-types') is None else None
 if sec_name:
  users=_named_profile_users(interfaces,'security',sec_name)
  security_shared=len(users)>1
 else:
  sec_name=None;security_shared=False
 auth=_wifi_auth_types(iface,securities)
 mode=_wifi_mode(iface)
 open_network=not auth or auth.strip() in ('','none')
 secret=_wifi_passphrase_value(iface,securities)
 state={
  'resource_id':str(iface['.id']),
  'interface':interface_name,
  'ssid':_wifi_ssid(iface,configurations) or '',
  'mode':mode or 'ap',
  'security_mode':'open' if open_network else 'wpa2_wpa3_psk',
  'authentication_types':auth or '',
  'passphrase_set':bool(secret) or (not open_network and _wifi_passphrase_present(iface,securities)),
  'configuration_binding':'named' if config_name else 'inline',
  'configuration_name':config_name,
  'configuration_shared':config_shared,
  'security_binding':'named' if sec_name else 'inline',
  'security_name':sec_name,
  'security_shared':security_shared,
  'disabled':_truthy(iface.get('disabled',False)),
 }
 # Ephemeral only — callers must encrypt or drop before persisting.
 if secret:state['_passphrase_secret']=secret
 return state


def apply_wifi_settings(client:RouterOSClient,state:dict,*,ssid:str,security_mode:str,passphrase:str|None,touch_security:bool=True):
 """Write SSID/security. Named profiles only when used solely by this interface.

 When touch_security is False, only the SSID is changed (rollback-safe without the passphrase).
 """
 if state.get('configuration_shared') or state.get('security_shared'):
  raise RouterOSError('shared_wifi_profile','The Wi-Fi configuration or security profile is shared with another interface; refusing to change it',409)
 resource_id=state['resource_id']
 payload={}
 if state.get('configuration_binding')=='named' and state.get('configuration_name'):
  configs=list_wifi_configurations(client)
  match=next((c for c in configs if c.get('name')==state['configuration_name'] and c.get('.id')),None)
  if not match:raise RouterOSError('wifi_config_missing','Named Wi-Fi configuration profile is missing',409)
  client.write('PATCH',_resource_path('interface/wifi/configuration',str(match['.id'])),{'ssid':ssid})
 else:
  payload['configuration.ssid']=ssid
 if touch_security:
  if security_mode=='open':
   sec_payload={'authentication-types':'','passphrase':''}
  else:
   if not isinstance(passphrase,str) or not (8<=len(passphrase)<=63):
    raise RouterOSError('passphrase_invalid','WPA passphrase must be 8–63 characters',409)
   sec_payload={'authentication-types':'wpa2-psk,wpa3-psk','passphrase':passphrase}
  if state.get('security_binding')=='named' and state.get('security_name'):
   secs=list_wifi_securities(client)
   match=next((s for s in secs if s.get('name')==state['security_name'] and s.get('.id')),None)
   if not match:raise RouterOSError('wifi_security_missing','Named Wi-Fi security profile is missing',409)
   client.write('PATCH',_resource_path('interface/wifi/security',str(match['.id'])),sec_payload)
  else:
   payload['security.authentication-types']=sec_payload['authentication-types']
   payload['security.passphrase']=sec_payload['passphrase']
 if payload:
  client.write('PATCH',_resource_path('interface/wifi',resource_id),payload)
 return wifi_interface_state(client,state['interface'])


def guest_network_objects(client:RouterOSClient,interface_name:str):
 """Collect address/pool/DHCP/HotSpot objects bound to the guest HotSpot interface."""
 if not _iface_name_ok(interface_name):raise RouterOSError('resource_invalid','Interface name is invalid',409)
 addresses=[a for a in list_ip_addresses(client) if a.get('interface')==interface_name and a.get('.id')]
 if not addresses:raise RouterOSError('address_missing','No IP address is configured on the guest HotSpot interface',409)
 if len(addresses)>1:raise RouterOSError('address_ambiguous','Multiple IP addresses on the guest interface; refuse until only one remains',409)
 address=addresses[0]
 servers=[s for s in list_hotspot_servers(client) if s.get('interface')==interface_name]
 if not servers:raise RouterOSError('hotspot_missing','No HotSpot server is bound to this interface',409)
 if len(servers)>1:raise RouterOSError('hotspot_ambiguous','Multiple HotSpot servers on this interface',409)
 server=servers[0]
 profile_name=server.get('profile')
 profiles=list_hotspot_profiles(client)
 profile=next((p for p in profiles if p.get('name')==profile_name and p.get('.id')),None)
 if not profile:raise RouterOSError('hotspot_profile_missing','HotSpot profile for this server is missing',409)
 dhcp_servers=[d for d in list_dhcp_servers(client) if d.get('interface')==interface_name and d.get('.id')]
 if not dhcp_servers:raise RouterOSError('dhcp_missing','No DHCP server is bound to the guest interface',409)
 if len(dhcp_servers)>1:raise RouterOSError('dhcp_ambiguous','Multiple DHCP servers on the guest interface',409)
 dhcp=dhcp_servers[0]
 pool_name=dhcp.get('address-pool')
 pools=list_ip_pools(client)
 pool=next((p for p in pools if p.get('name')==pool_name and p.get('.id')),None)
 if not pool:raise RouterOSError('pool_missing','DHCP address pool is missing',409)
 networks=list_dhcp_networks(client)
 # Match by gateway pointing at the interface address or by network covering it.
 iface_addr=str(address.get('address') or '')
 network=None
 for item in networks:
  if item.get('gateway') and iface_addr.startswith(str(item.get('gateway')).split('/')[0]):
   network=item;break
 if network is None and networks:
  # Fall back: single network whose address contains the interface IP network.
  import ipaddress as _ip
  try:iface_net=_ip.ip_interface(iface_addr).network
  except ValueError:iface_net=None
  candidates=[]
  if iface_net is not None:
   for item in networks:
    raw=item.get('address')
    if not isinstance(raw,str):continue
    try:net=_ip.ip_network(raw,strict=False)
    except ValueError:continue
    if iface_net.network_address in net or net.network_address==iface_net.network_address:
     candidates.append(item)
   if len(candidates)==1:network=candidates[0]
 if not network or not network.get('.id'):raise RouterOSError('dhcp_network_missing','DHCP server network for the guest subnet is missing',409)
 return {
  'interface':interface_name,
  'address':{'.id':str(address['.id']),'address':iface_addr,'network':address.get('network'),'interface':interface_name},
  'pool':{'.id':str(pool['.id']),'name':pool.get('name'),'ranges':pool.get('ranges')},
  'dhcp_server':{'.id':str(dhcp['.id']),'name':dhcp.get('name'),'interface':interface_name,'address-pool':pool_name},
  'dhcp_network':{'.id':str(network['.id']),'address':network.get('address'),'gateway':network.get('gateway'),'dns-server':network.get('dns-server') or network.get('dns')},
  'hotspot_server':{'.id':str(server['.id']),'name':server.get('name'),'interface':interface_name,'profile':profile_name},
  'hotspot_profile':{'.id':str(profile['.id']),'name':profile.get('name'),'hotspot-address':profile.get('hotspot-address')},
 }


def guest_network_state(client:RouterOSClient,interface_name:str):
 objects=guest_network_objects(client,interface_name)
 return {
  'resource_id':objects['address']['.id'],
  'interface':interface_name,
  'address':objects['address']['address'],
  'pool_name':objects['pool']['name'],
  'pool_ranges':objects['pool']['ranges'],
  'dhcp_server_name':objects['dhcp_server']['name'],
  'dhcp_network_address':objects['dhcp_network']['address'],
  'dhcp_gateway':objects['dhcp_network']['gateway'],
  'dhcp_dns':objects['dhcp_network'].get('dns-server'),
  'hotspot_profile_name':objects['hotspot_profile']['name'],
  'hotspot_address':objects['hotspot_profile'].get('hotspot-address'),
  'ids':{
   'address':objects['address']['.id'],
   'pool':objects['pool']['.id'],
   'dhcp_network':objects['dhcp_network']['.id'],
   'hotspot_profile':objects['hotspot_profile']['.id'],
  },
 }


def apply_guest_network_addressing(client:RouterOSClient,before_ids:dict,*,address:str,pool_ranges:str,network_address:str,gateway:str,dns:str,hotspot_address:str):
 """Apply guest addressing in a safe order; caller verifies and rolls back."""
 for key in ('pool','address','dhcp_network','hotspot_profile'):
  if key not in before_ids or not _WIFI_ID.fullmatch(str(before_ids[key])):
   raise RouterOSError('resource_invalid','Guest network resource id is invalid',409)
 # 1) pool ranges (new hosts can be allocated after address/network catch up)
 client.write('PATCH',_resource_path('ip/pool',before_ids['pool']),{'ranges':pool_ranges})
 # 2) interface address
 client.write('PATCH',_resource_path('ip/address',before_ids['address']),{'address':address})
 # 3) dhcp network
 client.write('PATCH',_resource_path('ip/dhcp-server/network',before_ids['dhcp_network']),{
  'address':network_address,'gateway':gateway,'dns-server':dns,
 })
 # 4) hotspot profile address
 client.write('PATCH',_resource_path('ip/hotspot/profile',before_ids['hotspot_profile']),{'hotspot-address':hotspot_address})


def restore_guest_network_addressing(client:RouterOSClient,before:dict):
 ids=before['ids']
 client.write('PATCH',_resource_path('ip/hotspot/profile',ids['hotspot_profile']),{'hotspot-address':before['hotspot_address']})
 client.write('PATCH',_resource_path('ip/dhcp-server/network',ids['dhcp_network']),{
  'address':before['dhcp_network_address'],'gateway':before['dhcp_gateway'],'dns-server':before.get('dhcp_dns') or before['dhcp_gateway'],
 })
 client.write('PATCH',_resource_path('ip/address',ids['address']),{'address':before['address']})
 client.write('PATCH',_resource_path('ip/pool',ids['pool']),{'ranges':before['pool_ranges']})


# --- Guest VLAN for external AP Safe Change helpers ---

_ETHER_NAME=re.compile(r'^(ether|sfp|sfpplus|qsfp)[0-9]+$',re.I)
_WG_TYPE=re.compile(r'wireguard',re.I)
GUEST_BRIDGE_NAME='mm-guest-br'


def list_interfaces(client:RouterOSClient):
 return _records(client.get('interface',optional=True))


def list_vlans(client:RouterOSClient):
 return _records(client.get('interface/vlan',optional=True))


def list_bridges(client:RouterOSClient):
 return _records(client.get('interface/bridge',optional=True))


def list_dhcp_clients(client:RouterOSClient):
 return _records(client.get('ip/dhcp-client',optional=True))


def list_pppoe_clients(client:RouterOSClient):
 return _records(client.get('interface/pppoe-client',optional=True))


def _is_bridge_type(iface:dict):
 kind=str(iface.get('type') or '').lower()
 return kind=='bridge' or bool(iface.get('actual-mtu') is not None and kind=='bridge')


def _interface_by_name(interfaces:list[dict],name:str):
 return next((i for i in interfaces if i.get('name')==name),None)


def assert_ethernet_port_allowed(client:RouterOSClient,ethernet_port:str,*,hotspot_interface:str):
 """Refuse WAN/uplink/wifi/Hub WireGuard and the HotSpot interface itself."""
 if not _iface_name_ok(ethernet_port) or not _ETHER_NAME.fullmatch(ethernet_port):
  raise RouterOSError('ethernet_invalid','Choose a router Ethernet port (etherN / sfpN), not Wi-Fi or WireGuard',422)
 if ethernet_port==hotspot_interface:
  raise RouterOSError('ethernet_is_hotspot','The HotSpot interface cannot be the external-AP Ethernet port',409)
 if ethernet_port.lower() in ('wifi1',) or ethernet_port.lower().startswith('wifi'):
  raise RouterOSError('wifi_forbidden','Wi-Fi interfaces cannot be used as the external-AP Ethernet port',409)
 interfaces=list_interfaces(client)
 iface=_interface_by_name(interfaces,ethernet_port)
 if not iface or not iface.get('.id'):
  raise RouterOSError('ethernet_missing','The selected Ethernet port is not present on this router',409)
 kind=str(iface.get('type') or '').lower()
 if kind in ('wireguard','wg','vlan','bridge','pppoe-out','lte','wwan') or _WG_TYPE.search(kind):
  raise RouterOSError('ethernet_type_forbidden','Selected interface is not a physical Ethernet port',409)
 if ethernet_port.startswith('mm-'):
  raise RouterOSError('hub_tunnel_forbidden','Hub WireGuard / MikroMagic tunnel interfaces must never be changed',409)
 if kind and 'ether' not in kind and 'sfp' not in kind and kind not in ('','ether'):
  # Allow blank/unknown type when the name matches etherN/sfpN; refuse clear non-ethernet types.
  if kind in ('wlan','wifi','wwan','ovpn','l2tp','sstp','gre','ipip'):
   raise RouterOSError('ethernet_type_forbidden','Selected interface is not a physical Ethernet port',409)
 for client_row in list_dhcp_clients(client):
  if client_row.get('interface')==ethernet_port and not _truthy(client_row.get('disabled',False)):
   raise RouterOSError('wan_dhcp_forbidden','Ethernet ports with an active DHCP client (WAN/uplink) are refused',409)
 for ppp in list_pppoe_clients(client):
  if ppp.get('interface')==ethernet_port and not _truthy(ppp.get('disabled',False)):
   raise RouterOSError('wan_pppoe_forbidden','Ethernet ports with PPPoE (WAN/uplink) are refused',409)
 # Station wifi uplink is never an ethernet name; still refuse if somehow aliased.
 wifi=list_wifi_interfaces(client)
 for w in wifi:
  if w.get('name')==ethernet_port:
   raise RouterOSError('wifi_forbidden','Wi-Fi interfaces cannot be used as the external-AP Ethernet port',409)
  mode=str(w.get('configuration.mode') or w.get('mode') or '').lower()
  if 'station' in mode and w.get('name')=='wifi1':
   pass  # informational only
 return iface


def _parse_vlan_id(value)->int:
 try:vid=int(value)
 except (TypeError,ValueError) as error:
  raise RouterOSError('vlan_id_invalid','VLAN id must be an integer from 2 to 4094',422) from error
 if not (2<=vid<=4094):
  raise RouterOSError('vlan_id_invalid','VLAN id must be an integer from 2 to 4094',422)
 return vid


def guest_vlan_state(client:RouterOSClient,*,ethernet_port:str,vlan_id:int,vlan_name:str,hotspot_interface:str):
 """Read live guest-VLAN / HotSpot-bridge membership for Safe Change fingerprinting."""
 vlan_id=_parse_vlan_id(vlan_id)
 if not _iface_name_ok(vlan_name):
  raise RouterOSError('vlan_name_invalid','VLAN interface name is invalid',422)
 assert_ethernet_port_allowed(client,ethernet_port,hotspot_interface=hotspot_interface)
 interfaces=list_interfaces(client)
 hotspot_iface=_interface_by_name(interfaces,hotspot_interface)
 if not hotspot_iface:
  raise RouterOSError('hotspot_interface_missing','HotSpot guest interface is not present',409)
 hotspot_is_bridge=str(hotspot_iface.get('type') or '').lower()=='bridge'
 bridges=list_bridges(client)
 bridge_ports=list_bridge_ports(client)
 vlans=list_vlans(client)
 existing=next((v for v in vlans if v.get('name')==vlan_name),None)
 if existing is None:
  existing=next((v for v in vlans if str(v.get('vlan-id'))==str(vlan_id) and v.get('interface')==ethernet_port),None)
 if existing and existing.get('interface') not in (None,ethernet_port):
  raise RouterOSError('vlan_conflict','A VLAN with this name already exists on a different parent interface',409)
 if existing and str(existing.get('vlan-id')) not in (None,str(vlan_id)) and existing.get('name')==vlan_name:
  raise RouterOSError('vlan_conflict','A VLAN with this name already exists with a different vlan-id',409)

 guest_bridge=None
 if hotspot_is_bridge:
  guest_bridge=hotspot_interface
 else:
  # Prefer an existing MikroMagic guest bridge that already contains the HotSpot iface.
  for port in bridge_ports:
   if port.get('interface')==hotspot_interface and isinstance(port.get('bridge'),str):
    guest_bridge=port['bridge'];break
  if guest_bridge is None:
   named=next((b for b in bridges if b.get('name')==GUEST_BRIDGE_NAME),None)
   if named:guest_bridge=GUEST_BRIDGE_NAME

 vlan_bridge_port=None
 if existing and guest_bridge:
  vlan_bridge_port=next((p for p in bridge_ports if p.get('interface')==existing.get('name') and p.get('bridge')==guest_bridge),None)
 hotspot_bridge_port=None
 if guest_bridge and not hotspot_is_bridge:
  hotspot_bridge_port=next((p for p in bridge_ports if p.get('interface')==hotspot_interface and p.get('bridge')==guest_bridge),None)

 # Addresses / DHCP / HotSpot currently bound to guest side (interface or bridge).
 addresses=[a for a in list_ip_addresses(client) if a.get('interface') in (hotspot_interface,guest_bridge) and a.get('.id')]
 dhcp_servers=[d for d in list_dhcp_servers(client) if d.get('interface') in (hotspot_interface,guest_bridge) and d.get('.id')]
 hotspot_servers=[s for s in list_hotspot_servers(client) if s.get('interface')==hotspot_interface or (guest_bridge and s.get('interface')==guest_bridge)]
 if not hotspot_servers:
  hotspot_servers=[s for s in list_hotspot_servers(client) if s.get('interface')==hotspot_interface]
 if not hotspot_servers:
  raise RouterOSError('hotspot_missing','No HotSpot server is bound to the guest interface',409)

 address_row=addresses[0] if len(addresses)==1 else (addresses[0] if addresses else None)
 dhcp_row=dhcp_servers[0] if len(dhcp_servers)==1 else (dhcp_servers[0] if dhcp_servers else None)
 hs_row=hotspot_servers[0]
 bridge_row=next((b for b in bridges if b.get('name')==guest_bridge),None) if guest_bridge else None

 migration_needed=not hotspot_is_bridge and (guest_bridge is None or hs_row.get('interface')!=guest_bridge or (address_row and address_row.get('interface')!=guest_bridge))
 target_bridge=guest_bridge or (hotspot_interface if hotspot_is_bridge else GUEST_BRIDGE_NAME)

 return {
  'resource_id':str(existing['.id']) if existing and existing.get('.id') else f'pending:{vlan_name}',
  'ethernet_port':ethernet_port,
  'vlan_id':vlan_id,
  'vlan_name':vlan_name,
  'vlan_exists':bool(existing and existing.get('.id')),
  'vlan_interface_parent':existing.get('interface') if existing else None,
  'hotspot_interface_original':hotspot_interface,
  'hotspot_server_interface':hs_row.get('interface'),
  'hotspot_server_name':hs_row.get('name'),
  'guest_bridge':target_bridge,
  'guest_bridge_exists':bool(bridge_row) or hotspot_is_bridge,
  'hotspot_is_bridge':hotspot_is_bridge,
  'migration_needed':bool(migration_needed),
  'vlan_on_guest_bridge':bool(vlan_bridge_port),
  'hotspot_iface_on_guest_bridge':bool(hotspot_is_bridge or hotspot_bridge_port),
  'address_interface':address_row.get('interface') if address_row else None,
  'dhcp_interface':dhcp_row.get('interface') if dhcp_row else None,
  'ids':{
   'vlan':str(existing['.id']) if existing and existing.get('.id') else None,
   'guest_bridge':str(bridge_row['.id']) if bridge_row and bridge_row.get('.id') else (str(hotspot_iface['.id']) if hotspot_is_bridge else None),
   'bridge_port_vlan':str(vlan_bridge_port['.id']) if vlan_bridge_port and vlan_bridge_port.get('.id') else None,
   'bridge_port_hotspot_iface':str(hotspot_bridge_port['.id']) if hotspot_bridge_port and hotspot_bridge_port.get('.id') else None,
   'address':str(address_row['.id']) if address_row and address_row.get('.id') else None,
   'dhcp_server':str(dhcp_row['.id']) if dhcp_row and dhcp_row.get('.id') else None,
   'hotspot_server':str(hs_row['.id']) if hs_row.get('.id') else None,
  },
 }


def apply_guest_vlan_external_ap(client:RouterOSClient,before:dict,desired:dict):
 """Create VLAN + guest-bridge membership so an external AP feeds HotSpot.

 Order: guest bridge (if needed) → migrate HotSpot/IP/DHCP onto bridge → VLAN → bridge port.
 """
 ethernet=desired['ethernet_port'];vlan_id=desired['vlan_id'];vlan_name=desired['vlan_name']
 hotspot_iface=desired['hotspot_interface_original'];guest_bridge=desired['guest_bridge']
 created={'guest_bridge':False,'bridge_port_hotspot_iface':False,'vlan':False,'bridge_port_vlan':False,
          'retargeted_address':False,'retargeted_dhcp':False,'retargeted_hotspot':False}
 ids=dict(before.get('ids') or {})

 if desired.get('migration_needed') and not desired.get('hotspot_is_bridge'):
  if not before.get('guest_bridge_exists'):
   created_bridge=client.write('PUT','interface/bridge',{'name':guest_bridge,'comment':'MikroMagic guest HotSpot bridge'})
   # PUT may return the row or empty; re-read.
   bridges=list_bridges(client)
   row=next((b for b in bridges if b.get('name')==guest_bridge and b.get('.id')),None)
   if not row:
    rid=created_bridge.get('.id') if isinstance(created_bridge,dict) else None
    if not rid:raise RouterOSError('bridge_create_failed','Guest HotSpot bridge could not be created',409)
    ids['guest_bridge']=str(rid)
   else:
    ids['guest_bridge']=str(row['.id'])
   created['guest_bridge']=True
  # Add original HotSpot interface as bridge port when missing.
  ports=list_bridge_ports(client)
  hs_port=next((p for p in ports if p.get('interface')==hotspot_iface and p.get('bridge')==guest_bridge),None)
  if not hs_port:
   client.write('PUT','interface/bridge/port',{'bridge':guest_bridge,'interface':hotspot_iface,'comment':'MikroMagic guest radio'})
   ports=list_bridge_ports(client)
   hs_port=next((p for p in ports if p.get('interface')==hotspot_iface and p.get('bridge')==guest_bridge and p.get('.id')),None)
   if not hs_port:raise RouterOSError('bridge_port_failed','Could not add the HotSpot interface to the guest bridge',409)
   ids['bridge_port_hotspot_iface']=str(hs_port['.id']);created['bridge_port_hotspot_iface']=True
  # Retarget IP / DHCP / HotSpot onto the guest bridge.
  if ids.get('address') and before.get('address_interface')==hotspot_iface:
   client.write('PATCH',_resource_path('ip/address',ids['address']),{'interface':guest_bridge})
   created['retargeted_address']=True
  if ids.get('dhcp_server') and before.get('dhcp_interface')==hotspot_iface:
   client.write('PATCH',_resource_path('ip/dhcp-server',ids['dhcp_server']),{'interface':guest_bridge})
   created['retargeted_dhcp']=True
  if ids.get('hotspot_server') and before.get('hotspot_server_interface')==hotspot_iface:
   client.write('PATCH',_resource_path('ip/hotspot',ids['hotspot_server']),{'interface':guest_bridge})
   created['retargeted_hotspot']=True

 # Create or verify VLAN.
 vlans=list_vlans(client)
 existing=next((v for v in vlans if v.get('name')==vlan_name),None)
 if not existing:
  client.write('PUT','interface/vlan',{
   'name':vlan_name,'vlan-id':str(vlan_id),'interface':ethernet,
   'comment':'MikroMagic guest VLAN for external AP',
  })
  vlans=list_vlans(client)
  existing=next((v for v in vlans if v.get('name')==vlan_name and v.get('.id')),None)
  if not existing:raise RouterOSError('vlan_create_failed','Guest VLAN interface could not be created',409)
  ids['vlan']=str(existing['.id']);created['vlan']=True
 else:
  if str(existing.get('vlan-id'))!=str(vlan_id) or existing.get('interface')!=ethernet:
   raise RouterOSError('vlan_conflict','Existing VLAN does not match the previewed ethernet/vlan-id',409)
  ids['vlan']=str(existing['.id'])
  # Ensure enabled
  if _truthy(existing.get('disabled',False)):
   client.write('PATCH',_resource_path('interface/vlan',ids['vlan']),{'disabled':'false'})

 # Add VLAN to guest bridge.
 ports=list_bridge_ports(client)
 vport=next((p for p in ports if p.get('interface')==vlan_name and p.get('bridge')==guest_bridge),None)
 if not vport:
  client.write('PUT','interface/bridge/port',{'bridge':guest_bridge,'interface':vlan_name,'comment':'MikroMagic external AP guest VLAN'})
  ports=list_bridge_ports(client)
  vport=next((p for p in ports if p.get('interface')==vlan_name and p.get('bridge')==guest_bridge and p.get('.id')),None)
  if not vport:raise RouterOSError('bridge_port_failed','Could not add the guest VLAN to the HotSpot bridge',409)
  ids['bridge_port_vlan']=str(vport['.id']);created['bridge_port_vlan']=True
 else:
  ids['bridge_port_vlan']=str(vport['.id'])

 # Stash creation flags on desired for rollback of brand-new objects only.
 desired_flags=dict(desired)
 desired_flags['ids']=ids
 desired_flags['_created']=created
 return desired_flags


def restore_guest_vlan_external_ap(client:RouterOSClient,before:dict,desired:dict|None=None):
 """Roll back guest VLAN / bridge membership to the preview snapshot.

 Uses the before-snapshot as authority so partial applies still reverse:
 remove VLAN membership/interface we did not have, restore HotSpot/IP/DHCP
 interfaces, and drop a guest bridge we created.
 """
 hotspot_iface=before['hotspot_interface_original']
 vlan_name=before['vlan_name']
 guest_bridge=before.get('guest_bridge') or (desired or {}).get('guest_bridge') or GUEST_BRIDGE_NAME
 live_ids=((desired or {}).get('ids') or {})
 # Refresh live ids when possible.
 try:live=guest_vlan_state(client,ethernet_port=before['ethernet_port'],vlan_id=before['vlan_id'],vlan_name=vlan_name,hotspot_interface=hotspot_iface)
 except RouterOSError:
  live=None
 ids=dict(before.get('ids') or {})
 if live:ids={**ids,**{k:v for k,v in (live.get('ids') or {}).items() if v}}
 ids={**ids,**{k:v for k,v in live_ids.items() if v}}

 # 1) Remove VLAN from guest bridge when it was not a member before.
 if not before.get('vlan_on_guest_bridge'):
  ports=list_bridge_ports(client)
  for port in ports:
   if port.get('interface')==vlan_name and port.get('bridge')==guest_bridge and port.get('.id'):
    try:client.write('DELETE',_resource_path('interface/bridge/port',str(port['.id'])),None)
    except RouterOSError:pass
 # 2) Delete VLAN when it did not exist before.
 if not before.get('vlan_exists'):
  for vlan in list_vlans(client):
   if vlan.get('name')==vlan_name and vlan.get('.id'):
    try:client.write('DELETE',_resource_path('interface/vlan',str(vlan['.id'])),None)
    except RouterOSError:pass
 # 3) Restore HotSpot / DHCP / address interfaces to the before snapshot.
 if ids.get('hotspot_server') and before.get('hotspot_server_interface'):
  try:client.write('PATCH',_resource_path('ip/hotspot',ids['hotspot_server']),{'interface':before['hotspot_server_interface']})
  except RouterOSError:pass
 if ids.get('dhcp_server') and before.get('dhcp_interface'):
  try:client.write('PATCH',_resource_path('ip/dhcp-server',ids['dhcp_server']),{'interface':before['dhcp_interface']})
  except RouterOSError:pass
 if ids.get('address') and before.get('address_interface'):
  try:client.write('PATCH',_resource_path('ip/address',ids['address']),{'interface':before['address_interface']})
  except RouterOSError:pass
 # 4) Remove HotSpot-iface bridge port when it was not a member before.
 if not before.get('hotspot_iface_on_guest_bridge') and not before.get('hotspot_is_bridge'):
  ports=list_bridge_ports(client)
  for port in ports:
   if port.get('interface')==hotspot_iface and port.get('bridge')==guest_bridge and port.get('.id'):
    try:client.write('DELETE',_resource_path('interface/bridge/port',str(port['.id'])),None)
    except RouterOSError:pass
 # 5) Delete guest bridge when we created it for this change.
 if not before.get('guest_bridge_exists') and guest_bridge==GUEST_BRIDGE_NAME:
  for bridge in list_bridges(client):
   if bridge.get('name')==guest_bridge and bridge.get('.id'):
    try:client.write('DELETE',_resource_path('interface/bridge',str(bridge['.id'])),None)
    except RouterOSError:pass
 return guest_vlan_state(
  client,
  ethernet_port=before['ethernet_port'],
  vlan_id=before['vlan_id'],
  vlan_name=before['vlan_name'],
  hotspot_interface=hotspot_iface,
 )
