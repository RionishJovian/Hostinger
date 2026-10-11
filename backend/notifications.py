"""Smart Notification Center and Daily Owner Summary for the SME Owner/Admin (in-app only).

Notifications are derived from current business records on every request, so one issue is one entry that
updates in place (dedupe) and disappears when resolved. Only per-owner preferences and read markers are stored.
Downstream faults at a site are grouped under the most upstream open incident; three or more incidents of the
same scope within 24 hours become one instability entry. Router-measured facts (peak customers, internet
availability, access point health, router voucher activation) are reported as not measured, never estimated.
"""
import hashlib,json,time
from datetime import timedelta
from typing import Literal
from fastapi import Depends,HTTPException
from pydantic import Field
from sqlalchemy import select,func,delete
from sqlalchemy.exc import IntegrityError
from .schemas import Strict
from .models import NotificationPreference,NotificationRead,RouterChange,RouterDevice,SiteIncident,SiteMaintenance,Site,Order,EventDelivery,TenantSubscription,FinancialEvent,Voucher
from .subscriptions import term_status,local_date,midnight

LEVELS=('critical','attention','information')
VISIBLE={'critical':('critical',),'attention':('critical','attention'),'all':LEVELS}
UPSTREAM=('wan','gateway','switch','access_point','dns_portal')
CRITICAL_SCOPES=('wan','gateway')
FLAP_WINDOW=86400;FLAP_COUNT=3;RECOVERED_WINDOW=86400
NOT_MEASURED=('peak_customers','internet_availability','access_point_health','router_voucher_activation')
class ReadItem(Strict):
 key:str=Field(min_length=1,max_length=120)
 version:str=Field(min_length=1,max_length=32)
class ReadIn(Strict):
 items:list[ReadItem]=Field(min_length=1,max_length=100)
class PreferenceIn(Strict):
 expected_revision:int=Field(ge=0)
 level:Literal['critical','attention','all']
 daily_summary:Literal['daily','important','off']
def entry(key,level,kind,page,updated,params,count=1):
 version=hashlib.sha256(json.dumps([level,kind,params,count,updated],sort_keys=True).encode()).hexdigest()[:16]
 return {'key':key,'level':level,'kind':kind,'page':page,'updated':updated,'count':count,'params':params,'version':version}
def incident_level(x):
 if x.expected_reason:return 'information'
 if x.status=='unknown':return 'attention'
 return 'critical' if x.scope in CRITICAL_SCOPES else 'attention'
def incident_items(s,tenant,names,now):
 rows=list(s.scalars(select(SiteIncident).where(SiteIncident.tenant_id==tenant,(SiteIncident.status!='resolved')|(SiteIncident.started>=now-FLAP_WINDOW)|(SiteIncident.ended>=now-RECOVERED_WINDOW))))
 out=[];flapping=set();groups={}
 for x in rows:
  if x.started>=now-FLAP_WINDOW:groups.setdefault((x.site_id,x.scope),[]).append(x)
 for (site,scope),xs in groups.items():
  if len(xs)<FLAP_COUNT:continue
  flapping.add((site,scope));active=[x for x in xs if x.status!='resolved'];level='critical' if active and scope in CRITICAL_SCOPES and not all(x.expected_reason for x in active) else 'attention'
  out.append(entry(f'instability:{site}:{scope}',level,'instability','Sites',max(max(x.started,x.ended or 0) for x in xs),{'site':names.get(site,''),'scope':scope,'open':bool(active)},len(xs)))
 open_by_site={}
 for x in rows:
  if x.status!='resolved' and (x.site_id,x.scope) not in flapping:open_by_site.setdefault(x.site_id,[]).append(x)
 for site,xs in open_by_site.items():
  chain=sorted([x for x in xs if x.scope in UPSTREAM],key=lambda x:(UPSTREAM.index(x.scope),x.started))
  if chain:
   root=chain[0];related=chain[1:]
   out.append(entry(f'incident:{root.id}',incident_level(root),'incident_open','Sites',max(x.started for x in chain),{'site':names.get(site,''),'scope':root.scope,'root_cause':root.confirmed_root_cause or root.suspected_root_cause,'root_cause_confirmed':bool(root.confirmed_root_cause),'related_scopes':sorted({x.scope for x in related}),'expected_reason':root.expected_reason,'started':root.started},len(chain)))
  for x in xs:
   if x.scope not in UPSTREAM:out.append(entry(f'incident:{x.id}',incident_level(x),'incident_open','Sites',x.started,{'site':names.get(site,''),'scope':x.scope,'root_cause':x.confirmed_root_cause or x.suspected_root_cause,'root_cause_confirmed':bool(x.confirmed_root_cause),'related_scopes':[],'expected_reason':x.expected_reason,'started':x.started}))
 for x in rows:
  if x.status=='resolved' and x.ended and x.ended>=now-RECOVERED_WINDOW and (x.site_id,x.scope) not in flapping:out.append(entry(f'incident:{x.id}','information','incident_recovered','Sites',x.ended,{'site':names.get(x.site_id,''),'scope':x.scope,'started':x.started,'ended':x.ended}))
 return out
def feed(s,u,now):
 tenant=u.tenant_id;names={x.id:x.name for x in s.scalars(select(Site).where(Site.tenant_id==tenant))};out=[]
 routers={x.id:x.name for x in s.scalars(select(RouterDevice).where(RouterDevice.tenant_id==tenant))}
 for x in s.scalars(select(RouterChange).where(RouterChange.tenant_id==tenant,RouterChange.status.in_(('recovery_required','conflict')))):
  out.append(entry(f'change:{x.id}','critical' if x.status=='recovery_required' else 'attention','change_'+x.status,'Routers',x.updated,{'router':routers.get(x.router_id,'')}))
 out+=incident_items(s,tenant,names,now)
 pending,latest=s.execute(select(func.count(),func.max(Order.created)).where(Order.tenant_id==tenant,Order.status=='pending')).one()
 if pending:out.append(entry('payments:pending','attention','payments_pending','Payments',latest,{},pending))
 failed,=s.execute(select(func.count()).where(EventDelivery.tenant_id==tenant,EventDelivery.state=='failed')).one()
 if failed:out.append(entry('deliveries:failed','attention','deliveries_failed','Integrations',0,{},failed))
 row=s.scalar(select(TenantSubscription).where(TenantSubscription.tenant_id==tenant));term=term_status(row,now)
 if term['warning']:out.append(entry(f'subscription:{term["expires_on"]}','attention','subscription_expiring','Subscription',0,{'expires_on':term['expires_on'],'days_left':term['days_left']}))
 for x in s.scalars(select(SiteMaintenance).where(SiteMaintenance.tenant_id==tenant,SiteMaintenance.ended.is_(None))):
  overdue=x.planned_end<=now
  out.append(entry(f'maintenance:{x.id}','attention' if overdue else 'information','maintenance_overdue' if overdue else 'maintenance_active','Sites',x.started,{'site':names.get(x.site_id,''),'planned_end':x.planned_end,'extensions':x.extensions}))
 return sorted(out,key=lambda x:(LEVELS.index(x['level']),-x['updated'],x['key']))
def preference(s,u):return s.get(NotificationPreference,u.id)
def preference_json(p):return {'level':p.level if p else 'all','daily_summary':p.daily_summary if p else 'daily','revision':p.revision if p else 0}
def feed_json(s,u,now):
 items=feed(s,u,now);prefs=preference_json(preference(s,u));reads={r.key:r.version for r in s.scalars(select(NotificationRead).where(NotificationRead.user_id==u.id))}
 visible=[x|{'read':reads.get(x['key'])==x['version']} for x in items if x['level'] in VISIBLE[prefs['level']]]
 return {'preferences':prefs,'items':visible,'unread':sum(not x['read'] for x in visible),'hidden':len(items)-len(visible),'counts':{l:sum(x['level']==l for x in visible) for l in LEVELS},'delivery':'in_app_only','generated':now}
def summary(s,u,now):
 today=local_date(now);day=today-timedelta(days=1);start=midnight(day);end=midnight(today);tenant=u.tenant_id
 events=list(s.scalars(select(FinancialEvent).where(FinancialEvent.tenant_id==tenant,FinancialEvent.occurred_at>=start,FinancialEvent.occurred_at<end)))
 money={}
 for e in events:
  m=money.setdefault(e.currency,{'currency':e.currency,'collected':0,'refunded':0,'net':0,'payments':0})
  if e.kind=='collection':m['collected']+=e.amount;m['net']+=e.amount;m['payments']+=1
  else:m['refunded']+=e.amount;m['net']-=e.amount
 sold=sum(e.source=='voucher_sale' and e.kind=='collection' for e in events);refunds=sum(e.kind=='refund' for e in events)
 redeemed=s.scalar(select(func.count()).where(Voucher.tenant_id==tenant,Voucher.redeemed_at>=start,Voucher.redeemed_at<end))
 started=s.scalar(select(func.count()).where(SiteIncident.tenant_id==tenant,SiteIncident.started>=start,SiteIncident.started<end))
 open_now=s.scalar(select(func.count()).where(SiteIncident.tenant_id==tenant,SiteIncident.status!='resolved'))
 items=feed(s,u,now);outstanding={l:sum(x['level']==l for x in items) for l in ('critical','attention')}
 reasons=[r for r,c in (('incidents_started',started),('critical_outstanding',outstanding['critical']),('refunds_recorded',refunds)) if c]
 prefs=preference_json(preference(s,u));shown=prefs['daily_summary']=='daily' or (prefs['daily_summary']=='important' and bool(reasons))
 return {'date':day.isoformat(),'timezone':'Asia/Yangon','window':{'start':start,'end':end},'preference':prefs['daily_summary'],'shown':shown,'important':bool(reasons),'reasons':reasons,
  'revenue':sorted(money.values(),key=lambda m:m['currency']),'vouchers':{'sold':sold,'redeemed_in_app':redeemed},'incidents':{'started':started,'open_now':open_now},'outstanding':outstanding,
  'not_measured':list(NOT_MEASURED),'not_measured_reason':'router_monitoring_not_connected'}
def register_notifications(app,current,db,owner,log):
 @app.get('/v1/notifications')
 def notifications(u=Depends(current),s=Depends(db)):
  owner(u);return feed_json(s,u,int(time.time()))
 @app.post('/v1/notifications/read')
 def mark_read(b:ReadIn,u=Depends(current),s=Depends(db)):
  owner(u);now=int(time.time());current_items={x['key']:x['version'] for x in feed(s,u,now)}
  s.execute(delete(NotificationRead).where(NotificationRead.user_id==u.id,NotificationRead.key.not_in(list(current_items) or [''])))
  for x in b.items:
   if current_items.get(x.key)!=x.version:continue
   row=s.get(NotificationRead,(u.id,x.key))
   if row:row.version=x.version;row.read_at=now
   else:s.add(NotificationRead(user_id=u.id,key=x.key,version=x.version,read_at=now))
  s.commit();return feed_json(s,u,now)
 @app.post('/v1/notifications/preferences')
 def save_preferences(b:PreferenceIn,u=Depends(current),s=Depends(db)):
  owner(u);now=int(time.time());p=preference(s,u)
  if (p.revision if p else 0)!=b.expected_revision:raise HTTPException(409,'Notification settings changed elsewhere. Refresh and try again.')
  if p:p.level=b.level;p.daily_summary=b.daily_summary;p.revision+=1;p.updated=now
  else:p=NotificationPreference(user_id=u.id,tenant_id=u.tenant_id,level=b.level,daily_summary=b.daily_summary,revision=1,updated=now);s.add(p)
  log(s,u,'notification_preferences_updated',u.id)
  try:s.commit()
  except IntegrityError:s.rollback();raise HTTPException(409,'Notification settings changed elsewhere. Refresh and try again.')
  return feed_json(s,u,now)
 @app.get('/v1/notifications/daily-summary')
 def daily_summary(u=Depends(current),s=Depends(db)):
  owner(u);return summary(s,u,int(time.time()))
