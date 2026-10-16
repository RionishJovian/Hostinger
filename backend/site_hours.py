"""Frozen-v1 shop Business Hours, Network Operating Hours and Planned Maintenance Mode.

Hours are owner-entered weekly schedules in the shop timezone; a closing time earlier than the opening
time runs past midnight. Maintenance is a timed window with an optional reason that can be extended or
ended early. Outage incidents that start during maintenance or network-off hours are labelled expected;
nothing here proves device state. The post-maintenance Magic Check reports only evidence MikroMagic
actually holds, so without a verified router connection it says the network could not be checked.
"""
import time
from datetime import datetime
from typing import Literal
from zoneinfo import ZoneInfo
from fastapi import Depends,HTTPException
from pydantic import Field,field_validator,model_validator
from sqlalchemy import select,func
from .models import Site,SiteMaintenance,SiteIncident,RouterDevice
from .schemas import Strict

DAYS=('mon','tue','wed','thu','fri','sat','sun')
MAX_WINDOW=24*3600
HHMM=r'^([01]\d|2[0-3]):[0-5]\d$'

def minutes(hhmm):h,m=hhmm.split(':');return int(h)*60+int(m)

class DayHours(Strict):
 open:str=Field(pattern=HHMM)
 close:str=Field(pattern=r'^(([01]\d|2[0-3]):[0-5]\d|24:00)$')
 @model_validator(mode='after')
 def distinct(self):
  if minutes(self.open)==minutes(self.close):raise ValueError('Opening and closing times must differ; use 00:00 to 24:00 for all day')
  return self
class WeekHours(Strict):
 mon:DayHours|None
 tue:DayHours|None
 wed:DayHours|None
 thu:DayHours|None
 fri:DayHours|None
 sat:DayHours|None
 sun:DayHours|None
class HoursIn(Strict):
 business_hours:WeekHours|None=None
 network_hours_mode:Literal['business','always','custom']
 network_hours:WeekHours|None=None
 @model_validator(mode='after')
 def consistent(self):
  if self.network_hours_mode=='business' and self.business_hours is None:raise ValueError('Set business hours before using them as network operating hours')
  if self.network_hours_mode=='custom' and self.network_hours is None:raise ValueError('Custom network operating hours need a weekly schedule')
  if self.network_hours_mode!='custom':self.network_hours=None
  return self
class MaintenanceIn(Strict):
 minutes:int=Field(ge=5,le=MAX_WINDOW//60)
 reason:str=Field(default='',max_length=300)
 @field_validator('reason')
 @classmethod
 def clean(cls,v):return v.strip()
class ExtendIn(Strict):
 minutes:int=Field(ge=5,le=MAX_WINDOW//60)

def in_schedule(week,tz,ts):
 local=datetime.fromtimestamp(ts,ZoneInfo(tz));now=local.hour*60+local.minute;day=local.weekday()
 today,prev=week.get(DAYS[day]),week.get(DAYS[(day-1)%7])
 if today:
  o,c=minutes(today['open']),minutes(today['close'])
  if (o<c and o<=now<c) or (c<o and now>=o):return True
 if prev:
  o,c=minutes(prev['open']),minutes(prev['close'])
  if c<o and now<c:return True
 return False
def business_open(site,ts):return None if not site.business_hours else in_schedule(site.business_hours,site.timezone,ts)
def network_on(site,ts):
 if site.network_hours_mode=='business' and site.business_hours:return in_schedule(site.business_hours,site.timezone,ts)
 if site.network_hours_mode=='custom' and site.network_hours:return in_schedule(site.network_hours,site.timezone,ts)
 return True

def magic_check(s,site,at):
 routers=s.scalar(select(func.count()).select_from(RouterDevice).where(RouterDevice.site_id==site.id)) or 0
 open_incidents=s.scalar(select(func.count()).select_from(SiteIncident).where(SiteIncident.site_id==site.id,SiteIncident.status!='resolved')) or 0
 summary=('No router is registered for this shop, so the network could not be checked.' if not routers else 'The network could not be checked: no router has a verified connection to MikroMagic yet.')
 return {'checked':at,'result':'unable','summary':summary,'routers':routers,'open_incidents':open_incidents}
def finish_due(s,site,now):
 changed=False
 for m in s.scalars(select(SiteMaintenance).where(SiteMaintenance.site_id==site.id,SiteMaintenance.ended.is_(None),SiteMaintenance.planned_end<=now)):
  m.ended=m.planned_end;m.post_check=magic_check(s,site,now);changed=True
 return changed
def active_window(s,site,now):
 return s.scalar(select(SiteMaintenance).where(SiteMaintenance.site_id==site.id,SiteMaintenance.ended.is_(None),SiteMaintenance.planned_end>now))
def expected_reason(s,site,scope,started):
 if scope=='control_plane':return None
 covering=s.scalar(select(func.count()).select_from(SiteMaintenance).where(SiteMaintenance.site_id==site.id,SiteMaintenance.started<=started,func.coalesce(SiteMaintenance.ended,SiteMaintenance.planned_end)>started))
 if covering:return 'maintenance'
 return None if network_on(site,started) else 'network_off_hours'
def maintenance_json(m):return {k:getattr(m,k) for k in ['id','site_id','reason','started','planned_end','ended','extensions','post_check']}
def hours_json(s,site,now):
 active=active_window(s,site,now)
 history=s.scalars(select(SiteMaintenance).where(SiteMaintenance.site_id==site.id).order_by(SiteMaintenance.started.desc()).limit(20)).all()
 business=business_open(site,now)
 return {'site_id':site.id,'timezone':site.timezone,'business_hours':site.business_hours,'network_hours_mode':site.network_hours_mode,'network_hours':site.network_hours,
  'now':{'at':now,'business':'not_set' if business is None else 'open' if business else 'closed','network':'on' if network_on(site,now) else 'off'},
  'maintenance':maintenance_json(active) if active else None,'history':[maintenance_json(m) for m in history]}

def register_site_hours(app,current,db,owner,log):
 def shop(s,u,id):
  owner(u);site=s.get(Site,id)
  if not site or site.tenant_id!=u.tenant_id:raise HTTPException(404,'Site not found')
  return site
 def settle(s,site,now):
  if finish_due(s,site,now):s.commit()
 @app.get('/v1/sites/{id}/hours')
 def hours(id:str,u=Depends(current),s=Depends(db)):
  site=shop(s,u,id);now=int(time.time());settle(s,site,now);return hours_json(s,site,now)
 @app.post('/v1/sites/{id}/hours')
 def save_hours(id:str,b:HoursIn,u=Depends(current),s=Depends(db)):
  site=shop(s,u,id);now=int(time.time());settle(s,site,now)
  data=b.model_dump()
  site.business_hours,site.network_hours_mode,site.network_hours=data['business_hours'],data['network_hours_mode'],data['network_hours']
  log(s,u,'site_hours_updated',site.id);s.commit();return hours_json(s,site,now)
 @app.post('/v1/sites/{id}/maintenance',status_code=201)
 def start(id:str,b:MaintenanceIn,u=Depends(current),s=Depends(db)):
  site=shop(s,u,id);now=int(time.time());settle(s,site,now)
  if active_window(s,site,now):raise HTTPException(409,'Maintenance is already running for this shop; extend or end it instead')
  m=SiteMaintenance(tenant_id=u.tenant_id,site_id=site.id,reason=b.reason,started=now,planned_end=now+b.minutes*60,created_by=u.id);s.add(m);s.flush()
  log(s,u,'site_maintenance_started',m.id);s.commit();return hours_json(s,site,now)
 def running(s,site,mid,now):
  m=s.get(SiteMaintenance,mid)
  if not m or m.site_id!=site.id:raise HTTPException(404,'Maintenance window not found')
  if m.ended is not None or m.planned_end<=now:raise HTTPException(409,'This maintenance window has already ended')
  return m
 @app.post('/v1/sites/{id}/maintenance/{mid}/extend')
 def extend(id:str,mid:str,b:ExtendIn,u=Depends(current),s=Depends(db)):
  site=shop(s,u,id);now=int(time.time());settle(s,site,now);m=running(s,site,mid,now)
  if m.planned_end+b.minutes*60-m.started>MAX_WINDOW:raise HTTPException(422,'A maintenance window cannot run longer than 24 hours; end it and start a new one if needed')
  m.planned_end+=b.minutes*60;m.extensions+=1;log(s,u,'site_maintenance_extended',m.id);s.commit();return hours_json(s,site,now)
 @app.post('/v1/sites/{id}/maintenance/{mid}/end')
 def end(id:str,mid:str,u=Depends(current),s=Depends(db)):
  site=shop(s,u,id);now=int(time.time());settle(s,site,now);m=running(s,site,mid,now)
  m.ended=now;m.ended_by=u.id;m.post_check=magic_check(s,site,now);log(s,u,'site_maintenance_ended',m.id);s.commit();return hours_json(s,site,now)
