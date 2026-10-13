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
 operation:Literal['wireguard_peer_keepalive','hotspot_portal_publish','guest_wifi_settings','guest_network_addressing','guest_vlan_external_ap']='wireguard_peer_keepalive'
 persistent_keepalive_seconds:int|None=Field(default=None,ge=1,le=3600)
 hotspot_portal_plan_id:str|None=Field(default=None,min_length=1,max_length=36)
 wifi_interface:str|None=Field(default=None,min_length=1,max_length=64)
 ssid:str|None=Field(default=None,max_length=64)
 security_mode:Literal['open','wpa2_wpa3_psk']|None=None
 passphrase:str|None=Field(default=None,min_length=8,max_length=63)
 network_cidr:str|None=Field(default=None,min_length=5,max_length=18)
 gateway:str|None=Field(default=None,min_length=7,max_length=15)
 pool_start:str|None=Field(default=None,min_length=7,max_length=15)
 pool_end:str|None=Field(default=None,min_length=7,max_length=15)
 dns:str|None=Field(default=None,min_length=7,max_length=15)
 ethernet_port:str|None=Field(default=None,min_length=1,max_length=64)
 vlan_id:int|None=Field(default=None,ge=2,le=4094)
 vlan_name:str|None=Field(default=None,min_length=1,max_length=64)
 hotspot_interface:str|None=Field(default=None,min_length=1,max_length=64)
 @field_validator('ssid')
 @classmethod
 def valid_change_ssid(cls,v):
  if v is None:return v
  return printed_ssid(v)
 @model_validator(mode='after')
 def validate_preview_fields(self):
  guest_fields=(self.wifi_interface,self.ssid,self.security_mode,self.passphrase,self.network_cidr,self.gateway,self.pool_start,self.pool_end,self.dns,self.ethernet_port,self.vlan_id,self.vlan_name,self.hotspot_interface)
  if self.operation=='wireguard_peer_keepalive':
   if self.persistent_keepalive_seconds is None:raise ValueError('persistent_keepalive_seconds is required for WireGuard keepalive')
   if self.hotspot_portal_plan_id is not None:raise ValueError('hotspot_portal_plan_id is only for portal publish')
   if any(x is not None for x in guest_fields):
    raise ValueError('guest Wi-Fi/addressing/VLAN fields are not valid for WireGuard keepalive')
  elif self.operation=='hotspot_portal_publish':
   if not self.hotspot_portal_plan_id:raise ValueError('hotspot_portal_plan_id is required for portal publish')
   if self.persistent_keepalive_seconds is not None:raise ValueError('persistent_keepalive_seconds is only for WireGuard keepalive')
   if any(x is not None for x in guest_fields):
    raise ValueError('guest Wi-Fi/addressing/VLAN fields are not valid for portal publish')
  elif self.operation=='guest_wifi_settings':
   if self.persistent_keepalive_seconds is not None or self.hotspot_portal_plan_id is not None:
    raise ValueError('keepalive and portal plan fields are not valid for guest Wi-Fi settings')
   if not self.wifi_interface:raise ValueError('wifi_interface is required for guest Wi-Fi settings')
   if not self.ssid:raise ValueError('ssid is required for guest Wi-Fi settings')
   if self.security_mode is None:raise ValueError('security_mode is required for guest Wi-Fi settings')
   # passphrase optional when leaving WPA unchanged (SSID-only); enforced against live state in preview
   if self.security_mode=='open' and self.passphrase is not None:
    raise ValueError('passphrase is not used for an open guest network')
   if any(x is not None for x in (self.network_cidr,self.gateway,self.pool_start,self.pool_end,self.dns,self.ethernet_port,self.vlan_id,self.vlan_name,self.hotspot_interface)):
    raise ValueError('guest addressing/VLAN fields are not valid for guest Wi-Fi settings')
  elif self.operation=='guest_network_addressing':
   if self.persistent_keepalive_seconds is not None or self.hotspot_portal_plan_id is not None:
    raise ValueError('keepalive and portal plan fields are not valid for guest network addressing')
   if any(x is not None for x in (self.ssid,self.security_mode,self.passphrase,self.ethernet_port,self.vlan_id,self.vlan_name,self.hotspot_interface)):
    raise ValueError('Wi-Fi SSID/security and VLAN fields are not valid for guest network addressing')
   if not self.wifi_interface:raise ValueError('wifi_interface is required for guest network addressing')
   if not self.network_cidr:raise ValueError('network_cidr is required for guest network addressing')
   if not self.gateway:raise ValueError('gateway is required for guest network addressing')
   if not self.pool_start or not self.pool_end:raise ValueError('pool_start and pool_end are required for guest network addressing')
  else:
   if self.persistent_keepalive_seconds is not None or self.hotspot_portal_plan_id is not None:
    raise ValueError('keepalive and portal plan fields are not valid for guest VLAN')
   if any(x is not None for x in (self.ssid,self.security_mode,self.passphrase,self.network_cidr,self.gateway,self.pool_start,self.pool_end,self.dns)):
    raise ValueError('Wi-Fi and addressing fields are not valid for guest VLAN external AP')
   if not self.ethernet_port:raise ValueError('ethernet_port is required for guest VLAN external AP')
   if self.vlan_id is None:raise ValueError('vlan_id is required for guest VLAN external AP')
  return self
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
 model:str|None=Field(default=None,max_length=120)
 reported_routeros:str|None=Field(default=None,max_length=40)
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
