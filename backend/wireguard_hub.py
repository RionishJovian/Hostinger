"""Narrow host WireGuard peer adapter for a preconfigured dedicated interface.

It never creates interfaces/keys, routes or firewall rules, and never accepts
arbitrary command fragments. The application must gate mutations on the
separately approved Magic Connect enrollment flow before calling this adapter.
"""
from __future__ import annotations
import base64,ipaddress,os,re,shutil,subprocess,time,hmac
from urllib.parse import urlparse
import httpx

class HubWireGuardError(RuntimeError):pass

def _interface(value:str)->str:
 if not isinstance(value,str) or not re.fullmatch(r'[A-Za-z0-9_.-]{1,15}',value):raise HubWireGuardError('Hub WireGuard interface name is invalid')
 return value

def _key(value:str)->str:
 try:
  raw=base64.b64decode(value,validate=True)
  if len(raw)!=32 or raw==bytes(32) or base64.b64encode(raw).decode()!=value:raise ValueError()
 except (ValueError,TypeError):raise HubWireGuardError('WireGuard public key is invalid')
 return value

def _address(value:str,pool:str)->str:
 try:
  address=ipaddress.ip_interface(value)
  network=ipaddress.ip_network(pool,strict=True)
 except ValueError:raise HubWireGuardError('Hub peer address or pool is invalid')
 if address.version!=4 or address.network.prefixlen!=32 or address.ip not in network or address.ip in (network.network_address,network.broadcast_address,network.network_address+1):
  raise HubWireGuardError('Peer address must be a reserved host inside the assigned hub pool')
 return str(address)

class WireGuardHubAdapter:
 def __init__(self,binary:str|None=None,runner=subprocess.run,clock=time.time):
  configured=binary or os.environ.get('MIKROMAGIC_WG_BINARY') or shutil.which('wg')
  self.binary=configured if configured and os.path.isabs(configured) else None
  self.runner=runner;self.clock=clock
 def verify_hub_identity(self,interface,expected_public_key):
  expected=_key(expected_public_key)
  actual=self._run(interface,'public-key').strip()
  if not hmac.compare_digest(actual,expected):raise HubWireGuardError('Assigned Hub identity does not match the dedicated interface; no change was made')
  return True
 def _run(self,interface,*args):
  interface=_interface(interface)
  if not self.binary:raise HubWireGuardError('Host WireGuard utility is unavailable; no peer operation was attempted')
  try:
   result=self.runner([self.binary,'show',interface,*args],capture_output=True,text=True,timeout=5,check=False)
  except (OSError,subprocess.TimeoutExpired):raise HubWireGuardError('Hub WireGuard query failed')
  if result.returncode!=0:raise HubWireGuardError('Hub WireGuard query failed')
  return result.stdout
 def _peers(self,interface):
  peers=[line.strip() for line in self._run(interface,'peers').splitlines() if line.strip()]
  key_to_ips={};ip_to_key={}
  for line in self._run(interface,'allowed-ips').splitlines():
   parts=line.split('\t')
   if len(parts)!=2:continue
   key,raw_ips=parts
   try:ips={str(ipaddress.ip_network(x,strict=False)) for x in raw_ips.split(',') if x}
   except ValueError:continue
   key_to_ips[key]=ips
   for ip in ips:ip_to_key[ip]=key
  return peers,key_to_ips,ip_to_key
 def provision_peer(self,interface,public_key,address,pool):
  interface=_interface(interface);key=_key(public_key);peer_ip=_address(address,pool)
  peers,key_ips,ip_keys=self._peers(interface)
  if key in peers:
   if key_ips.get(key)=={peer_ip}:return {'result':'already_present','peer_present':True,'allowed_address':peer_ip,'configuration_modified':False}
   raise HubWireGuardError('Existing peer key has a conflicting allowed address; no change was made')
  if peer_ip in ip_keys:raise HubWireGuardError('Tunnel address is already assigned to another peer; no change was made')
  try:result=self.runner([self.binary,'set',interface,'peer',key,'allowed-ips',peer_ip],capture_output=True,text=True,timeout=5,check=False)
  except (OSError,subprocess.TimeoutExpired):raise HubWireGuardError('Hub peer provisioning failed')
  if result.returncode!=0:raise HubWireGuardError('Hub peer provisioning failed')
  _,verified,_=self._peers(interface)
  if verified.get(key)!={peer_ip}:raise HubWireGuardError('Hub peer read-back did not match the requested /32; inspect before retrying')
  return {'result':'provisioned','peer_present':True,'allowed_address':peer_ip,'configuration_modified':True}
 def revoke_peer(self,interface,public_key,address,pool):
  interface=_interface(interface);key=_key(public_key);peer_ip=_address(address,pool)
  peers,key_ips,_=self._peers(interface)
  if key not in peers:return {'result':'already_absent','peer_present':False,'configuration_modified':False}
  if key_ips.get(key)!={peer_ip}:raise HubWireGuardError('Peer allowed address differs from the recorded allocation; no change was made')
  try:result=self.runner([self.binary,'set',interface,'peer',key,'remove'],capture_output=True,text=True,timeout=5,check=False)
  except (OSError,subprocess.TimeoutExpired):raise HubWireGuardError('Hub peer revocation failed')
  if result.returncode!=0:raise HubWireGuardError('Hub peer revocation failed')
  after,_,_=self._peers(interface)
  if key in after:raise HubWireGuardError('Hub peer remains present after revocation; inspect before retrying')
  return {'result':'revoked','peer_present':False,'configuration_modified':True}
 def observe_peer(self,interface,public_key,address,pool,recent_seconds=180):
  interface=_interface(interface);key=_key(public_key);peer_ip=_address(address,pool)
  peers,key_ips,_=self._peers(interface);found=key in peers;allowed_match=found and key_ips.get(key)=={peer_ip}
  handshakes={}
  for line in self._run(interface,'latest-handshakes').splitlines():
   parts=line.split('\t')
   if len(parts)==2:
    try:handshakes[parts[0]]=int(parts[1])
    except ValueError:continue
  timestamp=handshakes.get(key) if found else None;age=int(self.clock())-timestamp if timestamp else None
  fresh=bool(allowed_match and age is not None and 0<=age<=recent_seconds)
  return {'evidence_source':'host_wireguard_live_read','observed_at':int(self.clock()),'peer_found':found,'allowed_address_match':bool(allowed_match),'last_handshake_at':timestamp,'handshake_age_seconds':age,'fresh_handshake':fresh,'recent_threshold_seconds':recent_seconds,'connection_verified':False,'management_read_verified':False,'configuration_modified':False}

class WireGuardHubAgentAdapter:
 """Narrow client for the isolated Hub agent; never accepts public URLs."""
 def __init__(self,base_url:str,token_file:str,transport=None,clock=time.time):
  parsed=urlparse(base_url)
  if parsed.scheme!='http' or parsed.hostname!='magic-hub' or parsed.port!=8790 or parsed.path not in ('','/') or parsed.query or parsed.fragment:
   raise HubWireGuardError('Dedicated Hub agent URL is not the fixed internal endpoint')
  if not os.path.isabs(token_file):raise HubWireGuardError('Dedicated Hub agent token path must be absolute')
  self.base_url=base_url.rstrip('/');self.token_file=token_file;self.transport=transport;self.clock=clock
 def _token(self):
  try:
   with open(self.token_file, encoding='utf-8') as token_handle:
    value=token_handle.read().strip()
  except OSError:raise HubWireGuardError('Dedicated Hub agent credential is unavailable')
  if not re.fullmatch(r'[A-Za-z0-9_-]{40,160}',value):raise HubWireGuardError('Dedicated Hub agent credential is invalid')
  return value
 def _request(self,path,payload):
  try:
   with httpx.Client(base_url=self.base_url,timeout=5,trust_env=False,follow_redirects=False,transport=self.transport) as client:
    response=client.post(path,json=payload,headers={'Authorization':'Bearer '+self._token(),'Accept':'application/json'})
  except httpx.HTTPError:raise HubWireGuardError('Dedicated Hub agent request failed')
  if response.status_code!=200:raise HubWireGuardError('Dedicated Hub agent rejected the operation')
  try:return response.json()
  except ValueError:raise HubWireGuardError('Dedicated Hub agent returned an invalid response')
 def verify_hub_identity(self,interface,expected_public_key):
  result=self._request('/v1/identity',{'interface':_interface(interface)})
  actual=_key(result.get('public_key'))
  if not hmac.compare_digest(actual,_key(expected_public_key)):raise HubWireGuardError('Assigned Hub identity does not match the dedicated agent')
  return True
 def provision_peer(self,interface,public_key,address,pool):
  return self._request('/v1/peers/provision',{'interface':_interface(interface),'public_key':_key(public_key),'address':_address(address,pool),'pool':str(ipaddress.ip_network(pool,strict=True))})
 def revoke_peer(self,interface,public_key,address,pool):
  return self._request('/v1/peers/revoke',{'interface':_interface(interface),'public_key':_key(public_key),'address':_address(address,pool),'pool':str(ipaddress.ip_network(pool,strict=True))})
 def observe_peer(self,interface,public_key,address,pool,recent_seconds=180):
  result=self._request('/v1/peers/observe',{'interface':_interface(interface),'public_key':_key(public_key),'address':_address(address,pool),'pool':str(ipaddress.ip_network(pool,strict=True)),'recent_seconds':recent_seconds})
  result['connection_verified']=False;result['management_read_verified']=False;result['configuration_modified']=False
  return result

def hub_adapter_from_environment():
 if os.environ.get('MIKROMAGIC_HUB_MODE')=='dedicated-agent':
  return WireGuardHubAgentAdapter(os.environ.get('MIKROMAGIC_HUB_AGENT_URL',''),os.environ.get('MIKROMAGIC_HUB_AGENT_TOKEN_FILE',''))
 return WireGuardHubAdapter()
