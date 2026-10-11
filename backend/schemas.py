from pydantic import BaseModel, Field, ConfigDict, model_validator
from typing import Literal,Annotated
class Strict(BaseModel):model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
class Login(Strict):
 model_config=ConfigDict(extra="forbid",str_strip_whitespace=False)
 username:str=Field(min_length=1,max_length=160)
 password:str=Field(min_length=1,max_length=256)
class PackageIn(Strict):
 name:str=Field(min_length=1,max_length=120)
 service:Literal['internet','media','combined']
 mode:Literal['data','time','both','library','title','hybrid','category']
 price:int=Field(gt=0,le=1_000_000_000)
 gb:float=Field(default=0,ge=0,le=100000)
 hours:float=Field(default=0,ge=0,le=8760)
 media_hours:float=Field(default=24,gt=0,le=8760)
 clock:Literal['elapsed','connected']='elapsed'
 devices:int=Field(default=1,ge=1,le=100)
 speed:int=Field(default=10,ge=1,le=10000)
 title:str|None=Field(default=None,max_length=160)
 title_hours:float=Field(default=48,gt=0,le=8760)
 categories:list[Annotated[str,Field(min_length=1,max_length=80)]]=Field(default_factory=list,max_length=10)
 vip:bool=False
 @model_validator(mode='after')
 def validate_policy(self):
  if self.service=='combined':raise ValueError('Internet and Media passes are sold separately. Create one Internet package and one Media package.')
  if self.mode!='category' and self.categories:raise ValueError('Categories apply only to category passes')
  if self.service=='media':
   if self.mode not in ['library','title','hybrid','category'] or self.clock!='elapsed' or self.hours<=0:raise ValueError('Media needs a timed viewing window and library/title/hybrid/category mode')
   if self.mode in ['title','hybrid'] and not self.title:raise ValueError('Select the purchased title')
   if self.mode=='category' and not self.categories:raise ValueError('Select at least one category')
   if len({c.casefold() for c in self.categories})!=len(self.categories):raise ValueError('Each category can be selected once')
  else:
   if self.mode not in ['data','time','both']:raise ValueError('Internet needs data/time/both mode')
   if self.mode in ['data','both'] and self.gb<=0:raise ValueError('Positive data quota required')
   if self.mode in ['time','both'] and self.hours<=0:raise ValueError('Positive time quota required')
  return self
class OrderIn(Strict):
 site_id:str|None=Field(default=None,min_length=1,max_length=36)
 portal_revision:int=Field(gt=0)
 package_id:str
 method:str=Field(min_length=1,max_length=80)
 reference:str=Field(min_length=1,max_length=160)
 evidence:str=Field(min_length=1,max_length=4000)
 request_key:str=Field(min_length=16,max_length=80)
class Decision(Strict):
 expected_receipt_revision:int|None=Field(default=None,ge=0)
 decision:Literal['approved','rejected','needs_evidence']
 reason:str=Field(default='',max_length=1000)
 @model_validator(mode='after')
 def reasons(self):
  if self.decision!='approved' and not self.reason:raise ValueError('Reason required')
  return self
class EvidenceIn(Strict):evidence:str=Field(min_length=1,max_length=4000)
class Refund(Strict):reason:str=Field(min_length=1,max_length=1000)

from pydantic import field_validator
import ipaddress,re

def host_value(value):
 value=value.lower().rstrip('.')
 try:return str(ipaddress.ip_address(value))
 except ValueError:pass
 if len(value)>253 or '.' not in value or not all(re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?',part) for part in value.split('.')) or value.replace('.','').isdigit():
  raise ValueError('Use an explicit DNS hostname or IP address, without wildcard, port, path or URL scheme')
 return value

class PortalConfig(Strict):
 business_name:str=Field(default='My business',min_length=1,max_length=120)
 welcome:str=Field(default='Welcome. Choose internet or media access.',max_length=1000)
 language:Literal['en','my','both']='both'
 terms:str=Field(default='',max_length=4000)
 contact:str=Field(default='',max_length=200)
 direct_purchase:bool=False
 voucher_login:bool=True
 payment_destination:str=Field(default='',max_length=500)
 payment_instructions:str=Field(default='',max_length=2000)
 payment_methods:list[str]=Field(default_factory=lambda:['Cash at counter'],max_length=10)
 hostname:str=Field(default='',max_length=253)
 guest_interface:str=Field(default='',max_length=80,pattern=r'^[A-Za-z0-9_.:-]*$')
 guest_subnet:str=Field(default='',max_length=43)
 tls_required:bool=True
 isolate_guests:bool=True
 allowed_hosts:list[str]=Field(default_factory=list,max_length=50)
 @field_validator('hostname')
 @classmethod
 def hostname_valid(cls,v):return host_value(v) if v else v
 @field_validator('guest_subnet')
 @classmethod
 def subnet_valid(cls,v):
  if not v:return v
  try:n=ipaddress.ip_network(v,strict=True)
  except ValueError:raise ValueError('Use a network subnet, for example 192.168.50.0/24')
  if n.version!=4 or n.prefixlen<16 or n.prefixlen>30:raise ValueError('Guest IPv4 subnet must use /16 through /30; IPv6 policy requires router verification')
  return str(n)
 @field_validator('allowed_hosts')
 @classmethod
 def hosts_valid(cls,v):return list(dict.fromkeys(host_value(x.strip()) for x in v))
 @field_validator('payment_methods')
 @classmethod
 def methods_valid(cls,v):
  values=[x.strip() for x in v]
  if any(not x or len(x)>80 for x in values) or len(set(values))!=len(values):raise ValueError('Payment methods must be unique nonempty names, up to 80 characters each')
  return values
class PortalDraftIn(Strict):
 expected_revision:int=Field(ge=0)
 settings:PortalConfig
class PortalPublishIn(Strict):expected_revision:int=Field(gt=0)

class VoucherIssue(Strict):
 site_id:str|None=Field(default=None,min_length=1,max_length=36)
 package_id:str
 expires_days:int=Field(default=30,ge=1,le=365)
 request_key:str=Field(min_length=16,max_length=80)
 prefix:str|None=Field(default=None,max_length=16)
 custom_code:str|None=Field(default=None,max_length=64)
class VoucherRedeem(Strict):
 site_id:str|None=Field(default=None,min_length=1,max_length=36)
 code:str=Field(min_length=6,max_length=64)
 @field_validator('code')
 @classmethod
 def normalize(cls,v):
  from .voucher_codes import normalize,valid_redeemable
  value=normalize(v)
  if not valid_redeemable(value):raise ValueError('Enter the complete voucher code')
  return value
class VoucherRevoke(Strict):reason:str=Field(min_length=1,max_length=1000)
class OfflineVoucherEventIn(Strict):
 site_id:str=Field(min_length=1,max_length=36)
 event_key:str=Field(min_length=16,max_length=120)
 code:str=Field(min_length=6,max_length=64)
 event_type:Literal['redemption','usage']='redemption'
 local_time:int=Field(gt=0)
 device_id:str=Field(min_length=1,max_length=120)
 @field_validator('code')
 @classmethod
 def normalize_code(cls,v):
  from .voucher_codes import normalize,valid_redeemable
  value=normalize(v)
  if not valid_redeemable(value):raise ValueError('Enter the complete voucher code')
  return value
class IncidentIn(Strict):
 site_id:str=Field(min_length=1,max_length=36)
 scope:Literal['control_plane','gateway','wan','switch','access_point','dns_portal','dependency']
 status:Literal['open','resolved','unknown']='open'
 started:int=Field(gt=0)
 ended:int|None=Field(default=None,gt=0)
 detection_source:str=Field(min_length=1,max_length=80)
 symptoms:str=Field(min_length=1,max_length=2000)
 suspected_root_cause:str|None=Field(default=None,max_length=1000)
 confirmed_root_cause:str|None=Field(default=None,max_length=1000)
 remediation:str|None=Field(default=None,max_length=2000)
 notes:str=Field(default='',max_length=2000)
class BackupIn(Strict):
 site_id:str|None=Field(default=None,max_length=36)
 kind:Literal['control_plane','router_export','device_config']
 version:str=Field(min_length=1,max_length=80)
 checksum:str=Field(min_length=16,max_length=128)
 encrypted:bool=True
 status:Literal['created','healthy','failed','expired']='created'
 restore_verified:bool=False
 storage_ref:str=Field(min_length=1,max_length=400)
 retention_until:int|None=Field(default=None,gt=0)
class RouterChangePreviewIn(Strict):
 persistent_keepalive_seconds:int=Field(ge=1,le=3600)
class RouterChangeApplyIn(Strict):
 expected_revision:int=Field(gt=0)
 confirm_high_risk:bool=False
class RouterConflictResolutionIn(Strict):
 expected_revision:int=Field(gt=0)
 choice:Literal['keep_router','keep_mikromagic']
 confirm_high_risk:bool=False
class HotspotPortalProposalIn(Strict):
 evidence_id:str=Field(min_length=1,max_length=36)
 server_id:str=Field(min_length=1,max_length=80)
class HotspotPortalReviewIn(Strict):
 expected_revision:int=Field(gt=0)
 confirm_exact_scope:Literal[True]
class FirmwarePlanIn(Strict):
 site_id:str=Field(min_length=1,max_length=36)
 device_id:str=Field(min_length=1,max_length=36)
 current_version:str=Field(min_length=1,max_length=80)
 target_version:str=Field(min_length=1,max_length=80)
 minimum_safe_version:str=Field(min_length=1,max_length=80)
 window_start:int=Field(gt=0)
 window_end:int=Field(gt=0)
 notes:str=Field(default='',max_length=1000)

class VoucherSaleIn(Strict):
 amount:int=Field(gt=0,le=1_000_000_000)
 method:Literal['Cash','KBZPay','WavePay','Other']
 reference:str=Field(default='',max_length=160)
 evidence:str=Field(default='',max_length=4000)
 confirmed_received:Literal[True]
 @model_validator(mode='after')
 def method_details(self):
  if self.method in ('KBZPay','WavePay') and not self.reference:raise ValueError(f'Enter the {self.method} transaction ID')
  if self.method=='Other' and not self.evidence:raise ValueError('Describe how the customer paid')
  return self
class VoucherSaleCancel(Strict):
 reason:str=Field(min_length=1,max_length=500)
 confirmed:Literal[True]
class VoucherSaleRefund(Strict):
 reason:str=Field(min_length=1,max_length=1000)
 reference:str=Field(min_length=1,max_length=160)
 confirmed_returned:Literal[True]

def printed_ssid(v):
 v=(v or '').strip()
 if not v:return None
 if any(ord(c)<32 or ord(c)==127 for c in v):raise ValueError('The Wi-Fi name cannot contain control characters')
 if len(v.encode())>32:raise ValueError('Wi-Fi names are limited to 32 bytes; Burmese letters use about 3 bytes each')
 return v
class SiteIn(Strict):
 name:str=Field(min_length=1,max_length=120)
 timezone:str=Field(default='Asia/Yangon',max_length=80)
 printed_ssid:str|None=Field(default=None,max_length=64)
 @field_validator('timezone')
 @classmethod
 def valid_zone(cls,v):
  from zoneinfo import ZoneInfo,ZoneInfoNotFoundError
  try:ZoneInfo(v)
  except (ZoneInfoNotFoundError,ValueError):raise ValueError('Use a recognized IANA timezone')
  return v
 @field_validator('printed_ssid')
 @classmethod
 def valid_ssid(cls,v):return printed_ssid(v)
class SiteSettingsIn(Strict):
 printed_ssid:str|None=Field(default=None,max_length=64)
 @field_validator('printed_ssid')
 @classmethod
 def valid_ssid(cls,v):return printed_ssid(v)
class RouterIn(Strict):
 site_id:str=Field(min_length=1,max_length=36)
 name:str=Field(min_length=1,max_length=120)
 model:str=Field(min_length=1,max_length=120)
 reported_routeros:str=Field(default='',max_length=40)
class ManagedDeviceIn(Strict):
 site_id:str=Field(min_length=1,max_length=36)
 kind:Literal['switch','access_point']
 name:str=Field(min_length=1,max_length=120)
 vendor:str=Field(min_length=1,max_length=120)
 model:str=Field(min_length=1,max_length=120)
 serial_or_mac:str|None=Field(default=None,max_length=120)
 location:str=Field(default='',max_length=160)
 firmware:str=Field(default='',max_length=80)
 image_asset:str|None=Field(default=None,max_length=400)
