"""Private control plane for one isolated WireGuard Hub container."""
from __future__ import annotations
import base64,hmac,ipaddress,json,os,re,subprocess,tempfile,time
from pathlib import Path
from fastapi import FastAPI,Header,HTTPException
from pydantic import BaseModel,ConfigDict,Field,field_validator

class AgentError(RuntimeError):pass
def valid_key(value):
 try:raw=base64.b64decode(value,validate=True)
 except Exception:raise AgentError('invalid public key')
 if len(raw)!=32 or raw==bytes(32) or base64.b64encode(raw).decode()!=value:raise AgentError('invalid public key')
 return value
def valid_interface(value):
 if not isinstance(value,str) or not re.fullmatch(r'[A-Za-z0-9_.-]{1,15}',value):raise AgentError('invalid interface')
 return value
def valid_address(address,pool):
 try:a=ipaddress.ip_interface(address);n=ipaddress.ip_network(pool,strict=True)
 except (ValueError,TypeError):raise AgentError('invalid address')
 if a.version!=4 or a.network.prefixlen!=32 or a.ip not in n or a.ip in (n.network_address,n.broadcast_address,n.network_address+1):raise AgentError('invalid address')
 return str(a)

class WireGuardAgentService:
 def __init__(self,interface,private_key_file,state_file,runner=subprocess.run,clock=time.time):
  self.interface=valid_interface(interface);self.private_key_file=Path(private_key_file);self.state_file=Path(state_file);self.runner=runner;self.clock=clock;self.pool=None
 def _run(self,*args):
  result=self.runner(list(args),capture_output=True,text=True,timeout=5,check=False)
  if result.returncode:raise AgentError('wireguard operation failed')
  return result.stdout
 def initialize(self,address,port):
  if not self.private_key_file.is_file():raise AgentError('private key is unavailable')
  configured=ipaddress.ip_interface(address)
  if configured.version!=4 or configured.network.prefixlen!=24 or configured.ip!=configured.network.network_address+1:raise AgentError('Hub address must be the first host of a private /24')
  if not configured.network.is_private:raise AgentError('Hub pool must be private')
  if not 1<=port<=65535:raise AgentError('Hub port is invalid')
  self.pool=configured.network
  self._run('ip','link','show',self.interface) if self._exists() else self._run('ip','link','add',self.interface,'type','wireguard')
  self._run('wg','set',self.interface,'private-key',str(self.private_key_file),'listen-port',str(port))
  self._run('ip','address','replace',address,'dev',self.interface);self._run('ip','link','set','up','dev',self.interface)
  for key,allowed in self._load().items():self._run('wg','set',self.interface,'peer',key,'allowed-ips',allowed)
 def _exists(self):
  result=self.runner(['ip','link','show',self.interface],capture_output=True,text=True,timeout=5,check=False);return result.returncode==0
 def _load(self):
  if not self.state_file.exists():return {}
  try:data=json.loads(self.state_file.read_text())
  except (OSError,ValueError):raise AgentError('peer state is unreadable')
  if not isinstance(data,dict):raise AgentError('peer state is invalid')
  state={valid_key(k):str(ipaddress.ip_network(v,strict=True)) for k,v in data.items()}
  if self.pool:
   for allowed in state.values():valid_address(allowed,str(self.pool))
  return state
 def _pool(self,pool):
  try:value=ipaddress.ip_network(pool,strict=True)
  except (ValueError,TypeError):raise AgentError('invalid pool')
  if self.pool is None or value!=self.pool:raise AgentError('pool differs from the configured Hub network')
  return str(value)
 def _save(self,state):
  self.state_file.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
  fd,name=tempfile.mkstemp(dir=self.state_file.parent,prefix='.peers-',text=True)
  try:
   os.fchmod(fd,0o600)
   with os.fdopen(fd,'w') as handle:json.dump(state,handle,sort_keys=True,separators=(',',':'));handle.flush();os.fsync(handle.fileno())
   os.replace(name,self.state_file)
  finally:
   try:os.unlink(name)
   except FileNotFoundError:pass
 def public_key(self):return valid_key(self._run('wg','show',self.interface,'public-key').strip())
 def provision(self,key,address,pool):
  pool=self._pool(pool);key=valid_key(key);allowed=valid_address(address,pool);state=self._load()
  if key in state:
   if state[key]==allowed:return {'result':'already_present','peer_present':True,'allowed_address':allowed,'configuration_modified':False}
   raise AgentError('peer key conflict')
  if allowed in state.values():raise AgentError('address conflict')
  self._run('wg','set',self.interface,'peer',key,'allowed-ips',allowed)
  try:self._save(state|{key:allowed})
  except Exception:self._run('wg','set',self.interface,'peer',key,'remove');raise
  return {'result':'provisioned','peer_present':True,'allowed_address':allowed,'configuration_modified':True}
 def revoke(self,key,address,pool):
  pool=self._pool(pool);key=valid_key(key);allowed=valid_address(address,pool);state=self._load()
  if key not in state:return {'result':'already_absent','peer_present':False,'configuration_modified':False}
  if state[key]!=allowed:raise AgentError('peer address conflict')
  self._run('wg','set',self.interface,'peer',key,'remove')
  try:self._save({k:v for k,v in state.items() if k!=key})
  except Exception:self._run('wg','set',self.interface,'peer',key,'allowed-ips',allowed);raise
  return {'result':'revoked','peer_present':False,'configuration_modified':True}
 def observe(self,key,address,pool,recent_seconds):
  pool=self._pool(pool);key=valid_key(key);allowed=valid_address(address,pool);state=self._load();found=key in state;match=found and state[key]==allowed
  handshakes={}
  for line in self._run('wg','show',self.interface,'latest-handshakes').splitlines():
   parts=line.split('\t')
   if len(parts)==2:
    try:handshakes[parts[0]]=int(parts[1])
    except ValueError:pass
  stamp=handshakes.get(key) if found else None;age=int(self.clock())-stamp if stamp else None
  return {'evidence_source':'dedicated_hub_agent_live_read','observed_at':int(self.clock()),'peer_found':found,'allowed_address_match':match,'last_handshake_at':stamp,'handshake_age_seconds':age,'fresh_handshake':bool(match and age is not None and 0<=age<=recent_seconds),'recent_threshold_seconds':recent_seconds}

class Request(BaseModel):
 model_config=ConfigDict(extra='forbid')
 interface:str=Field(min_length=1,max_length=15)
 public_key:str|None=None
 address:str|None=None
 pool:str|None=None
 recent_seconds:int=Field(default=180,ge=30,le=900)

def make_agent(service,token):
 app=FastAPI(docs_url=None,redoc_url=None,openapi_url=None)
 def auth(value):
  if not value or not value.startswith('Bearer ') or not hmac.compare_digest(value[7:],token):raise HTTPException(401,'unauthorized')
 def call(fn):
  try:return fn()
  except AgentError:raise HTTPException(409,'operation rejected')
 def scope(body):
  if body.interface!=service.interface:raise HTTPException(404,'interface unavailable')
 @app.get('/health')
 def health():
  call(service.public_key)
  return {'service':'mikromagic-hub-agent','ready':True}
 @app.post('/v1/identity')
 def identity(body:Request,authorization:str|None=Header(default=None)):
  auth(authorization)
  scope(body)
  return call(lambda:{'public_key':service.public_key()})
 @app.post('/v1/peers/provision')
 def provision(body:Request,authorization:str|None=Header(default=None)):
  auth(authorization);scope(body);return call(lambda:service.provision(body.public_key,body.address,body.pool))
 @app.post('/v1/peers/revoke')
 def revoke(body:Request,authorization:str|None=Header(default=None)):
  auth(authorization);scope(body);return call(lambda:service.revoke(body.public_key,body.address,body.pool))
 @app.post('/v1/peers/observe')
 def observe(body:Request,authorization:str|None=Header(default=None)):
  auth(authorization);scope(body);return call(lambda:service.observe(body.public_key,body.address,body.pool,body.recent_seconds))
 return app

def application():
 token=Path(os.environ['MIKROMAGIC_HUB_AGENT_TOKEN_FILE']).read_text().strip()
 if not re.fullmatch(r'[A-Za-z0-9_-]{40,160}',token):raise RuntimeError('Invalid Hub agent token')
 service=WireGuardAgentService(os.environ['MIKROMAGIC_HUB_INTERFACE'],os.environ['MIKROMAGIC_HUB_PRIVATE_KEY_FILE'],os.environ['MIKROMAGIC_HUB_STATE_FILE'])
 service.initialize(os.environ['MIKROMAGIC_HUB_ADDRESS'],int(os.environ['MIKROMAGIC_HUB_PORT']))
 return make_agent(service,token)

