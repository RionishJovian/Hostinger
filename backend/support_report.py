"""Frozen-v1 Magic Support Mode / Get Help: a safe diagnostic report for one shop.

The report is built only from allow-listed fields MikroMagic already holds: shop hours and maintenance,
owner-reported routers and devices with the connection evidence actually recorded, outages with their
durations, and recent audited actions (names and times only). Free text (the owner's description, outage
notes, names) is scrubbed of anything that looks like a password, token, key or one of this business's
voucher codes. Likely causes are stated only from that evidence. Reports are immutable; the owner decides
whether to share one with MikroMagic support, who can read it but not change anything. Full remote support
control is later.
"""
import re,time
from datetime import datetime
from zoneinfo import ZoneInfo
from fastapi import Depends,HTTPException
from pydantic import Field
from sqlalchemy import select,or_
from .models import Tenant,Site,RouterDevice,RouterPlan,ManagedDevice,SiteIncident,SiteMaintenance,Audit,SupportReport
from .schemas import Strict
from .site_hours import business_open,network_on,finish_due,active_window
from .voucher_codes import normalize,valid_redeemable,find_voucher

SCOPES={'control_plane':'MikroMagic cloud','gateway':'Gateway','wan':'Internet (WAN)','switch':'Switch','access_point':'Access point','dns_portal':'DNS / portal','dependency':'Dependency'}
RECENT_DAYS=7
MAX_EVENTS=15
SECRET_PATTERNS=[
 (re.compile(r'(?i)\b(pass(?:word)?|passwd|pwd|pin|secret|token|api[ _-]?key|private[ _-]?key)\s*[:=]\s*\S+'),r'\1: [removed]'),
 (re.compile(r'(?<![A-Za-z0-9+/])[A-Za-z0-9+/]{42,43}=(?![A-Za-z0-9+/=])'),'[key removed]'),
 (re.compile(r'-----BEGIN [A-Z ]+-----.*?(-----END [A-Z ]+-----|$)',re.S),'[key removed]'),
 (re.compile(r'\b[A-Za-z0-9_\-]{32,}\b'),'[secret removed]'),
]
WORD=re.compile(r'[A-Za-z0-9]+')
JOINER=re.compile(r'^[ -]$')

def scrub(s,tenant_id,text):
 """Remove secret-looking strings and this business's voucher codes, even when written with spaces or hyphens."""
 if not text:return text
 for pattern,repl in SECRET_PATTERNS:text=pattern.sub(repl,text)
 words=list(WORD.finditer(text));spans=[]
 for i in range(len(words)):
  for n in range(1,5):
   group=words[i:i+n]
   if len(group)<n or any(not JOINER.match(text[a.end():b.start()]) for a,b in zip(group,group[1:])):break
   code=normalize(text[group[0].start():group[-1].end()])
   if len(code)>40:break
   if valid_redeemable(code) and find_voucher(s,tenant_id,code):spans.append((group[0].start(),group[-1].end()))
 for start,end in sorted(merge(spans),reverse=True):text=text[:start]+'[voucher code removed]'+text[end:]
 return text
def merge(spans):
 out=[]
 for a,b in sorted(spans):
  if out and a<=out[-1][1]:out[-1]=(out[-1][0],max(b,out[-1][1]))
  else:out.append((a,b))
 return out
def shop_time(ts,tz):return datetime.fromtimestamp(ts,ZoneInfo(tz)).strftime('%d %b %H:%M')

class ReportIn(Strict):
 description:str=Field(default='',max_length=1000)

def duration(seconds):
 seconds=max(0,int(seconds));d,h,m=seconds//86400,seconds%86400//3600,seconds%3600//60
 return ' '.join(p for p in [f'{d}d' if d else '',f'{h}h' if h else '',f'{m}m' if m or not (d or h) else ''] if p)

def build_report(s,u,site,description,now):
 clean=lambda text:scrub(s,site.tenant_id,text)
 tenant=s.get(Tenant,site.tenant_id)
 routers=s.scalars(select(RouterDevice).where(RouterDevice.site_id==site.id).order_by(RouterDevice.name)).all()
 plans={p.router_id:p for p in s.scalars(select(RouterPlan).where(RouterPlan.router_id.in_([r.id for r in routers])))} if routers else {}
 devices=s.scalars(select(ManagedDevice).where(ManagedDevice.site_id==site.id).order_by(ManagedDevice.kind,ManagedDevice.name)).all()
 since=now-RECENT_DAYS*86400
 incidents=s.scalars(select(SiteIncident).where(SiteIncident.site_id==site.id,or_(SiteIncident.status!='resolved',SiteIncident.ended>=since)).order_by(SiteIncident.started.desc())).all()
 maintenance=active_window(s,site,now)
 windows=s.scalars(select(SiteMaintenance).where(SiteMaintenance.site_id==site.id)).all()
 targets=[site.id,*[r.id for r in routers],*[d.id for d in devices],*[i.id for i in incidents],*[w.id for w in windows]]
 events=s.scalars(select(Audit).where(Audit.tenant_id==site.tenant_id,Audit.target.in_(targets)).order_by(Audit.created.desc()).limit(MAX_EVENTS)).all()
 business=business_open(site,now);net=network_on(site,now)

 router_rows=[]
 for r in routers:
  p=plans.get(r.id)
  if getattr(r,'architecture',None) or getattr(r,'reported_serial',None):
   source='script_reported'
  elif r.model or r.reported_routeros:
   source='owner_reported'
  else:
   source='name_only'
  router_rows.append({'name':clean(r.name),'model':clean(r.model) if r.model else None,'reported_routeros':r.reported_routeros or None,'source':source,
   'connection':'verified_handshake' if p and p.handshake_verified_at else 'not_verified',
   'magic_hub_assigned':bool(p),'enrollment_state':p.lifecycle_state if p else None,
   'handshake_verified_at':p.handshake_verified_at if p else None,'management_read_verified_at':p.management_read_verified_at if p else None,
   'management_locked':bool(p and p.management_locked_at)})
 device_rows=[{'name':clean(d.name),'kind':d.kind,'vendor':clean(d.vendor),'model':clean(d.model),'location':clean(d.location),'firmware':d.firmware or None,'last_seen':d.last_seen,'source':'owner_reported'} for d in devices]
 outage_rows=[{'scope':i.scope,'status':i.status,'started':i.started,'ended':i.ended,'duration':duration((i.ended or now)-i.started),'ongoing':i.status!='resolved',
   'symptoms':clean(i.symptoms),'confirmed_cause':clean(i.confirmed_root_cause),'suspected_cause':clean(i.suspected_root_cause),'expected':i.expected_reason} for i in incidents]

 findings=[]
 if maintenance:findings.append({'text':f'Planned maintenance is running until {shop_time(maintenance.planned_end,site.timezone)} shop time; outages now are expected.','evidence':'Maintenance window recorded by the owner'})
 if not net:findings.append({'text':'The network is planned off right now (network operating hours).','evidence':'Shop network operating hours'})
 if not routers:findings.append({'text':'No router is registered for this shop, so MikroMagic cannot see this network at all.','evidence':'Router registry is empty for this shop'})
 elif not any(x['connection']=='verified_handshake' for x in router_rows):findings.append({'text':'No router has a verified connection to MikroMagic, so device and internet status cannot be checked remotely. Check that the router has power and internet at the shop.','evidence':'No verified Magic Hub handshake on record'})
 if any(x['management_locked'] for x in router_rows):findings.append({'text':'Remote management is locked for a router after a failed safety check; changes are paused until it is reviewed.','evidence':'Management lock recorded'})
 for o in outage_rows:
  if not o['ongoing']:continue
  cause=f"confirmed cause: {o['confirmed_cause']}" if o['confirmed_cause'] else f"suspected (not confirmed): {o['suspected_cause']}" if o['suspected_cause'] else 'cause not known'
  findings.append({'text':f"{SCOPES.get(o['scope'],o['scope'])} outage ongoing for {o['duration']}{' (expected: '+o['expected'].replace('_',' ')+')' if o['expected'] else ''}; {cause}.",'evidence':'Outage recorded in MikroMagic'})
 if not findings:findings.append({'text':'MikroMagic has no record of a problem at this shop. If customers still cannot connect, describe what they see.','evidence':'No open outage, maintenance or connection problem on record'})

 return {'version':1,'generated':now,'business':clean(tenant.name) if tenant else None,'shop':{'name':clean(site.name),'timezone':site.timezone},
  'description':clean(description.strip()),
  'now':{'business':'not_set' if business is None else 'open' if business else 'closed','network':'on' if net else 'off','maintenance_until':maintenance.planned_end if maintenance else None,'maintenance_reason':clean(maintenance.reason) if maintenance else None},
  'routers':router_rows,'devices':device_rows,'outages':outage_rows,
  'recent_events':[{'at':e.created,'action':e.action} for e in events],
  'likely_causes':findings,
  'excluded':'Passwords, voucher codes, API credentials, WireGuard keys, router addresses and payment details are never included. Free text is scrubbed of anything that looks like one.'}

def report_json(x,site_name=None,business=None):
 out={'id':x.id,'site_id':x.site_id,'created':x.created,'shared_at':x.shared_at,'report':x.report}
 if site_name is not None:out|={'site_name':site_name,'business':business}
 return out

def register_support_reports(app,current,db,owner,log):
 def shop(s,u,id):
  owner(u);site=s.get(Site,id)
  if not site or site.tenant_id!=u.tenant_id:raise HTTPException(404,'Site not found')
  return site
 @app.post('/v1/sites/{id}/support-reports',status_code=201)
 def create(id:str,b:ReportIn,u=Depends(current),s=Depends(db)):
  site=shop(s,u,id);now=int(time.time())
  if finish_due(s,site,now):s.flush()
  x=SupportReport(tenant_id=u.tenant_id,site_id=site.id,created=now,created_by=u.id,report=build_report(s,u,site,b.description,now));s.add(x);s.flush()
  log(s,u,'support_report_created',x.id);s.commit();return report_json(x)
 @app.get('/v1/sites/{id}/support-reports')
 def mine(id:str,u=Depends(current),s=Depends(db)):
  site=shop(s,u,id)
  return [report_json(x) for x in s.scalars(select(SupportReport).where(SupportReport.site_id==site.id).order_by(SupportReport.created.desc()).limit(20))]
 @app.post('/v1/support-reports/{rid}/share')
 def share(rid:str,u=Depends(current),s=Depends(db)):
  owner(u);x=s.get(SupportReport,rid)
  if not x or x.tenant_id!=u.tenant_id:raise HTTPException(404,'Report not found')
  if x.shared_at is None:x.shared_at=int(time.time());x.shared_by=u.id;log(s,u,'support_report_shared',x.id);s.commit()
  return report_json(x)
 @app.get('/v1/support-reports')
 def inbox(u=Depends(current),s=Depends(db)):
  if u.role!='platform':raise HTTPException(403,'Platform support access required')
  rows=s.execute(select(SupportReport,Site.name,Tenant.name).join(Site,Site.id==SupportReport.site_id).join(Tenant,Tenant.id==SupportReport.tenant_id).where(SupportReport.shared_at.is_not(None)).order_by(SupportReport.shared_at.desc()).limit(100)).all()
  return [report_json(x,site_name,business) for x,site_name,business in rows]
