"""Frozen-v1 Voucher Production Jobs and saved voucher templates.

Flow: Profile → Quantity → Coverage → Dealer → Print Layout → Preview → Generate → Print → Verify → Distribute.
A draft stores settings only. Secure codes are created by the final Generate confirmation and returned
once; only hashes are stored, so a failed sheet can be reprinted only while the owner's screen still holds
the codes. Serial numbers are inventory identity and never authenticate. Opening the browser print dialog
proves nothing: the owner records each sheet or thermal run as printed or failed.
"""
import math,time
from typing import Literal
from fastapi import Depends,HTTPException
from pydantic import Field,model_validator
from sqlalchemy import select,update,func
from sqlalchemy.exc import IntegrityError
from .models import Voucher,Package,VoucherProductionJob,VoucherTemplate,VoucherSale,Dealer
from .schemas import Strict
from .sites import allowed_site
from .media import ensure_media_offer
from .voucher_codes import new_code,normalize_prefix,display
from .vouchers import voucher_json

GRID={'a4_ultra':(5,12),'a4_economy':(4,10),'a4_standard':(3,8),'a4_premium':(2,5)}
THERMAL_RUN=25
MAX_QUANTITY=1000
MAX_TEMPLATES=50
Layout=Literal['a4_ultra','a4_economy','a4_standard','a4_premium','a4_custom','thermal_58','thermal_80']

class ProductionSettings(Strict):
 package_id:str=Field(min_length=1,max_length=36)
 site_id:str|None=Field(default=None,min_length=1,max_length=36)
 quantity:int=Field(ge=1,le=MAX_QUANTITY)
 expires_days:int=Field(default=30,ge=1,le=365)
 prefix:str|None=Field(default=None,max_length=16)
 layout:Layout='a4_economy'
 columns:int|None=Field(default=None,ge=2,le=8)
 rows:int|None=Field(default=None,ge=4,le=16)
 show_price:bool=True
 ssid:str|None=Field(default=None,max_length=32)
 @model_validator(mode='after')
 def custom_grid(self):
  if self.layout=='a4_custom':
   if not (self.columns and self.rows):raise ValueError('Custom density needs columns and rows')
  else:self.columns=self.rows=None
  return self
class JobIn(ProductionSettings):
 name:str|None=Field(default=None,max_length=80)
 dealer_id:str|None=Field(default=None,min_length=1,max_length=36)
class TemplateIn(Strict):
 name:str=Field(min_length=1,max_length=80)
 settings:ProductionSettings
class GenerateIn(Strict):confirm:Literal[True]
class SheetResult(Strict):
 sheet:int=Field(ge=1)
 result:Literal['printed','failed']
class VerifyIn(Strict):sheets:list[SheetResult]=Field(min_length=1,max_length=MAX_QUANTITY)
class ReprintIn(Strict):
 sheets:list[int]=Field(min_length=1,max_length=MAX_QUANTITY)
 reason:str=Field(min_length=1,max_length=500)
class ReasonIn(Strict):reason:str=Field(min_length=1,max_length=500)
class DistributeIn(Strict):
 note:str|None=Field(default=None,max_length=200)
 dealer_id:str|None=Field(default=None,min_length=1,max_length=36)
 unit_price:int|None=Field(default=None,ge=0,le=1_000_000_000)
 request_key:str|None=Field(default=None,min_length=8,max_length=72)

def plan(settings,quantity):
 layout=settings['layout']
 if layout.startswith('thermal'):per,unit=THERMAL_RUN,'run'
 else:
  columns,rows=(settings['columns'],settings['rows']) if layout=='a4_custom' else GRID[layout];per,unit=columns*rows,'sheet'
 sheets=math.ceil(quantity/per)
 return {'unit':unit,'per_sheet':per,'sheets':sheets,'last_sheet_count':quantity-(sheets-1)*per}

def print_settings(b):
 return {'expires_days':b.expires_days,'prefix':normalize_prefix(b.prefix),'layout':b.layout,'columns':b.columns,'rows':b.rows,'show_price':b.show_price,'ssid':b.ssid or None}

def ref(job):return f'PJ-{job.number:04d}'

def register_voucher_production(app,current,db,owner,log):
 def load(s,u,id,lock=False):
  job=s.get(VoucherProductionJob,id,with_for_update=lock)
  if not job or job.tenant_id!=u.tenant_id:raise HTTPException(404,'Production job not found')
  return job
 def package_for(s,u,package_id,site_id):
  if site_id:allowed_site(s,u,site_id)
  p=s.get(Package,package_id)
  if not p or p.tenant_id!=u.tenant_id or not p.active:raise HTTPException(404,'Package not available')
  return p
 def dealer_for(s,u,id,lock=False):
  d=s.get(Dealer,id,with_for_update=lock)
  if not d or d.tenant_id!=u.tenant_id or d.archived_at:raise HTTPException(404,'Dealer not available')
  return d
 def calibration_required(s,job,p):
  if job.calibrated_at or p['sheets']<2:return False
  calibrated=s.scalars(select(VoucherProductionJob.settings).where(VoucherProductionJob.tenant_id==job.tenant_id,VoucherProductionJob.calibrated_at.is_not(None),VoucherProductionJob.id!=job.id))
  return not any(x.get('layout')==job.settings['layout'] for x in calibrated)
 def job_json(s,job,vouchers=None):
  p=plan(job.settings,job.quantity);counts={};free=[]
  for v in vouchers if vouchers is not None else s.scalars(select(Voucher).where(Voucher.production_job_id==job.id)):
   status=voucher_json(v)['status'];counts[status]=counts.get(status,0)+1
   if status=='unused' and not v.dealer_id:free.append(v.id)
  sold=len(list(s.scalars(select(VoucherSale.id).where(VoucherSale.voucher_id.in_(free),VoucherSale.cancelled_at.is_(None))))) if free else 0
  return {k:getattr(job,k) for k in ['id','number','name','site_id','package_id','quantity','settings','status','serial_start','serial_end','created','generated_at','calibrated_at','verified_at','distributed_at','distributed_note','cancelled_at']}|{'ref':ref(job),'plan':p,'sheets':job.sheets or {},'calibration_required':job.status=='draft' and calibration_required(s,job,p),'counts':counts,'available':len(free)-sold}
 def transition(s,job,status_from,values,message):
  result=s.execute(update(VoucherProductionJob).where(VoucherProductionJob.id==job.id,VoucherProductionJob.status.in_(status_from)).values(**values))
  if result.rowcount!=1:s.rollback();raise HTTPException(409,message)

 @app.get('/v1/voucher-jobs')
 def jobs(u=Depends(current),s=Depends(db)):
  owner(u);by_job={}
  for v in s.scalars(select(Voucher).where(Voucher.tenant_id==u.tenant_id,Voucher.production_job_id.is_not(None))):by_job.setdefault(v.production_job_id,[]).append(v)
  return [job_json(s,j,by_job.get(j.id,[])) for j in s.scalars(select(VoucherProductionJob).where(VoucherProductionJob.tenant_id==u.tenant_id).order_by(VoucherProductionJob.number.desc()))]

 @app.get('/v1/voucher-jobs/{id}')
 def job_detail(id:str,u=Depends(current),s=Depends(db)):
  owner(u);job=load(s,u,id);vouchers=list(s.scalars(select(Voucher).where(Voucher.production_job_id==job.id).order_by(Voucher.serial_no)))
  return job_json(s,job,vouchers)|{'vouchers':[voucher_json(v) for v in vouchers]}

 @app.post('/v1/voucher-jobs',status_code=201)
 def draft(b:JobIn,u=Depends(current),s=Depends(db)):
  owner(u);p=package_for(s,u,b.package_id,b.site_id);settings=print_settings(b)
  if b.dealer_id:settings['dealer_id']=dealer_for(s,u,b.dealer_id).id
  number=(s.scalar(select(func.max(VoucherProductionJob.number)).where(VoucherProductionJob.tenant_id==u.tenant_id)) or 0)+1
  job=VoucherProductionJob(tenant_id=u.tenant_id,number=number,name=b.name or None,site_id=b.site_id,package_id=p.id,quantity=b.quantity,settings=settings,status='draft',sheets={},created_by=u.id,created=int(time.time()));s.add(job)
  try:s.flush();log(s,u,'voucher_job_drafted',job.id);s.commit()
  except IntegrityError:s.rollback();raise HTTPException(409,'Another production job was created at the same time; try again')
  return job_json(s,job,[])

 @app.post('/v1/voucher-jobs/{id}/cancel')
 def cancel(id:str,u=Depends(current),s=Depends(db)):
  owner(u);job=load(s,u,id);transition(s,job,['draft'],{'status':'cancelled','cancelled_at':int(time.time())},'Only draft jobs can be cancelled; generated vouchers stay in history')
  log(s,u,'voucher_job_cancelled',job.id);s.commit();s.refresh(job);return job_json(s,job,[])

 @app.post('/v1/voucher-jobs/{id}/calibration')
 def calibrated(id:str,u=Depends(current),s=Depends(db)):
  owner(u);job=load(s,u,id);transition(s,job,['draft'],{'calibrated_at':int(time.time())},'Calibration is recorded before generating codes')
  log(s,u,'voucher_job_calibrated',job.id);s.commit();s.refresh(job);return job_json(s,job,[])

 @app.post('/v1/voucher-jobs/{id}/generate')
 def generate(id:str,b:GenerateIn,u=Depends(current),s=Depends(db)):
  owner(u);job=load(s,u,id)
  if job.status=='cancelled':raise HTTPException(409,'This production job was cancelled')
  def replay():
   vouchers=list(s.scalars(select(Voucher).where(Voucher.production_job_id==job.id).order_by(Voucher.serial_no)))
   return {'replayed':True,'job':job_json(s,job,vouchers),'items':[voucher_json(v)|{'code':None} for v in vouchers],'message':'Already generated. Codes are shown only once; mark lost sheets to disable their unused vouchers and create a replacement job.'}
  if job.status!='draft':return replay()
  p=plan(job.settings,job.quantity)
  if calibration_required(s,job,p):raise HTTPException(409,'Print and check the calibration test page for this layout before generating real vouchers')
  package=package_for(s,u,job.package_id,job.site_id);ensure_media_offer(s,u.tenant_id,package.policy)
  now=int(time.time());result=s.execute(update(VoucherProductionJob).where(VoucherProductionJob.id==job.id,VoucherProductionJob.status=='draft').values(status='generated',generated_at=now))
  if result.rowcount!=1:s.rollback();s.refresh(job);return replay()
  start=(s.scalar(select(func.max(Voucher.serial_no)).where(Voucher.tenant_id==u.tenant_id)) or 0)+1;prefix=job.settings.get('prefix');expires=now+job.settings['expires_days']*86400;items=[];codes=set()
  for i in range(job.quantity):
   code,code_hash,hint=new_code(s,u.tenant_id,prefix,exclude=codes);codes.add(code)
   v=Voucher(site_id=job.site_id,tenant_id=u.tenant_id,package_id=package.id,policy=package.policy.copy(),code_hash=code_hash,code_hint=hint,code_format='prefixed' if prefix else 'standard',code_prefix=prefix,issued_by=u.id,request_key=f'job:{job.id}:{i:04d}',created=now,expires=expires,serial_no=start+i,production_job_id=job.id,sheet_no=i//p['per_sheet']+1)
   s.add(v);items.append((v,display(code,prefix)))
  job.serial_start=start;job.serial_end=start+job.quantity-1;job.sheets={str(n):{'state':'pending','reprints':0} for n in range(1,p['sheets']+1)}
  try:
   s.flush()
   for v,_ in items:log(s,u,'voucher_job_issued',v.id)
   log(s,u,'voucher_job_generated',job.id);s.commit()
  except IntegrityError:s.rollback();raise HTTPException(409,'Serial numbers or codes were taken at the same time; press Generate again')
  return {'replayed':False,'job':job_json(s,job,[v for v,_ in items]),'items':[voucher_json(v)|{'code':code} for v,code in items]}

 def sheet_states(job,numbers):
  sheets={k:dict(v) for k,v in (job.sheets or {}).items()}
  for n in numbers:
   if str(n) not in sheets:raise HTTPException(422,f'Sheet {n} is not part of this job')
  return sheets
 def settle(job,sheets):
  job.sheets=sheets
  if job.status=='generated' and all(x['state'] in ('printed','lost') for x in sheets.values()):job.status='verified';job.verified_at=int(time.time())

 @app.post('/v1/voucher-jobs/{id}/verify')
 def verify(id:str,b:VerifyIn,u=Depends(current),s=Depends(db)):
  owner(u);job=load(s,u,id,lock=True)
  if job.status!='generated':raise HTTPException(409,'Only generated jobs awaiting print verification can be checked')
  sheets=sheet_states(job,[x.sheet for x in b.sheets])
  for x in b.sheets:
   if sheets[str(x.sheet)]['state']=='lost':raise HTTPException(409,f'Sheet {x.sheet} was marked lost')
   sheets[str(x.sheet)]['state']=x.result
  settle(job,sheets);log(s,u,'voucher_job_verified' if job.status=='verified' else 'voucher_job_print_checked',job.id);s.commit();s.refresh(job);return job_json(s,job)

 @app.post('/v1/voucher-jobs/{id}/reprint')
 def reprint(id:str,b:ReprintIn,u=Depends(current),s=Depends(db)):
  owner(u);job=load(s,u,id,lock=True)
  if job.status!='generated':raise HTTPException(409,'Reprints are only for sheets that failed before the job was verified')
  sheets=sheet_states(job,b.sheets)
  for n in b.sheets:
   if sheets[str(n)]['state']!='failed':raise HTTPException(409,f'Only failed sheets can be reprinted; sheet {n} is {sheets[str(n)]["state"]}')
   sheets[str(n)]|={'state':'reprinted','reprints':sheets[str(n)]['reprints']+1,'reprint_reason':b.reason}
  settle(job,sheets);log(s,u,'voucher_job_reprinted',job.id);s.commit();s.refresh(job)
  return job_json(s,job)|{'warning':'Destroy the failed copies. A reprint duplicates the same codes, so any surviving failed copy can still be used.'}

 @app.post('/v1/voucher-jobs/{id}/sheets/{sheet}/lost')
 def lost(id:str,sheet:int,b:ReasonIn,u=Depends(current),s=Depends(db)):
  owner(u);job=load(s,u,id,lock=True)
  if job.status not in ('generated','verified','distributed'):raise HTTPException(409,'Only generated jobs have printed sheets')
  sheets=sheet_states(job,[sheet])
  if sheets[str(sheet)]['state']=='lost':raise HTTPException(409,'Sheet is already marked lost')
  now=int(time.time());unused=(Voucher.production_job_id==job.id,Voucher.sheet_no==sheet,Voucher.redeemed_by.is_(None),Voucher.revoked==False,Voucher.disabled_at.is_(None),Voucher.deleted_at.is_(None),Voucher.expires>now)
  ids=list(s.scalars(select(Voucher.id).where(*unused)))
  if ids:s.execute(update(Voucher).where(Voucher.id.in_(ids),*unused).values(disabled_at=now,disabled_reason=f'Lost sheet {sheet} of {ref(job)}: {b.reason}',router_sync='disable'))
  for vid in ids:log(s,u,'voucher_disabled',vid)
  sheets[str(sheet)]|={'state':'lost','lost_reason':b.reason,'disabled':len(ids)}
  settle(job,sheets);log(s,u,'voucher_job_sheet_lost',job.id);s.commit();s.refresh(job)
  return job_json(s,job)|{'disabled':len(ids),'recommendation':'Generate replacement vouchers in a new job rather than reprinting the same codes.'}

 @app.post('/v1/voucher-jobs/{id}/distribute')
 def distribute(id:str,b:DistributeIn,u=Depends(current),s=Depends(db)):
  owner(u);job=load(s,u,id);handed=0
  dealer_id=b.dealer_id if 'dealer_id' in b.model_fields_set else job.settings.get('dealer_id')
  if job.status!='verified':raise HTTPException(409,'Verify every printed sheet before distributing')
  if dealer_id:
   if b.unit_price is None or not b.request_key:raise HTTPException(422,'Enter the dealer price for this handover')
   from .dealers import hand_over
   dealer=dealer_for(s,u,dealer_id,lock=True);now=int(time.time())
   candidates=list(s.scalars(select(Voucher).where(Voucher.production_job_id==job.id,Voucher.dealer_id.is_(None),Voucher.redeemed_by.is_(None),Voucher.revoked==False,Voucher.disabled_at.is_(None),Voucher.deleted_at.is_(None),Voucher.expires>now).order_by(Voucher.serial_no)))
   sold=set(s.scalars(select(VoucherSale.voucher_id).where(VoucherSale.voucher_id.in_([v.id for v in candidates]),VoucherSale.cancelled_at.is_(None))))
   stock=[v for v in candidates if v.id not in sold]
   if not stock:raise HTTPException(409,'No unused vouchers are left in this job to hand to the dealer')
   hand_over(s,u,log,dealer,stock,b.unit_price,b.request_key,note=b.note,job_id=job.id);handed=len(stock)
  settings={k:v for k,v in job.settings.items() if k!='dealer_id'}|({'dealer_id':dealer_id} if dealer_id else {})
  transition(s,job,['verified'],{'status':'distributed','distributed_at':int(time.time()),'distributed_note':b.note or None,'settings':settings},'Verify every printed sheet before distributing')
  log(s,u,'voucher_job_distributed',job.id);s.commit();s.refresh(job);return job_json(s,job)|{'dealer_id':dealer_id,'handed_to_dealer':handed}

 @app.get('/v1/voucher-templates')
 def templates(u=Depends(current),s=Depends(db)):
  owner(u);return [{'id':t.id,'name':t.name,'settings':t.settings,'created':t.created} for t in s.scalars(select(VoucherTemplate).where(VoucherTemplate.tenant_id==u.tenant_id,VoucherTemplate.archived_at.is_(None)).order_by(VoucherTemplate.name))]

 @app.post('/v1/voucher-templates',status_code=201)
 def save_template(b:TemplateIn,u=Depends(current),s=Depends(db)):
  owner(u);package_for(s,u,b.settings.package_id,b.settings.site_id)
  active=list(s.scalars(select(VoucherTemplate).where(VoucherTemplate.tenant_id==u.tenant_id,VoucherTemplate.archived_at.is_(None))))
  if any(t.name.casefold()==b.name.casefold() for t in active):raise HTTPException(409,'A template with this name already exists')
  if len(active)>=MAX_TEMPLATES:raise HTTPException(409,f'Archive a template first; up to {MAX_TEMPLATES} are kept')
  t=VoucherTemplate(tenant_id=u.tenant_id,name=b.name,settings={'package_id':b.settings.package_id,'site_id':b.settings.site_id,'quantity':b.settings.quantity}|print_settings(b.settings),created_by=u.id,created=int(time.time()));s.add(t)
  s.flush();log(s,u,'voucher_template_saved',t.id);s.commit();return {'id':t.id,'name':t.name,'settings':t.settings,'created':t.created}

 @app.post('/v1/voucher-templates/{id}/archive')
 def archive_template(id:str,u=Depends(current),s=Depends(db)):
  owner(u);t=s.get(VoucherTemplate,id)
  if not t or t.tenant_id!=u.tenant_id or t.archived_at:raise HTTPException(404,'Template not found')
  t.archived_at=int(time.time());log(s,u,'voucher_template_archived',t.id);s.commit();return {'id':t.id,'archived':True}
