"""Catalogue metadata, Media Pass rules and sales policies. No media files or playback authorization.

Media Pass rules (owner decisions Q36–Q49): Internet and Media passes are sold separately; a pass covers the whole
library, one title (optionally with the library) or selected categories; a voucher pass starts its clock at the first
successful redemption in the guest portal; one device, no transfer until expiry. Playback and device enforcement need
the SME's local Jellyfin/Plex connection, which does not exist yet, so passes report playback 'not_connected'.
"""
import time
from typing import Literal
from pydantic import Field
from fastapi import Depends,HTTPException
from sqlalchemy import select,update,func
from sqlalchemy.exc import IntegrityError
from .models import MediaTitle,MediaSettings,Entitlement
from .schemas import Strict
class MediaIn(Strict):
 name:str=Field(min_length=1,max_length=120)
 description:str=Field(default='',max_length=4000)
 genre:str=Field(default='',max_length=80)
 runtime_minutes:int=Field(gt=0,le=1440)
 release_year:int|None=Field(default=None,ge=1888,le=2100)
class MediaUpdate(Strict):
 expected_revision:int=Field(gt=0)
 settings:MediaIn
class MediaState(Strict):
 expected_revision:int=Field(gt=0)
 operation:Literal['publish','unpublish','archive','restore','feature','unfeature']
class MediaSettingsIn(Strict):
 expected_revision:int=Field(ge=0)
 catalog_preview:Literal['full','featured']

def title_json(t):return {k:getattr(t,k) for k in ['id','name','description','genre','runtime_minutes','release_year','published','archived','featured','revision','updated']}
def targeted(policy):return policy.get('service')=='media' and policy.get('mode') in ['title','hybrid']
def by_category(policy):return policy.get('service')=='media' and policy.get('mode')=='category'
def title_for(s,tenant,id,public=False):
 if not id:return None
 t=s.get(MediaTitle,id)
 if not t or t.tenant_id!=tenant or t.archived or (public and not t.published):return None
 return t
def category_title(s,tenant,categories,public=False):
 q=select(MediaTitle).where(MediaTitle.tenant_id==tenant,MediaTitle.archived==False,func.lower(MediaTitle.genre).in_([c.casefold() for c in categories]))
 if public:q=q.where(MediaTitle.published==True)
 return s.scalar(q.limit(1))
def package_snapshot(s,tenant,policy):
 if targeted(policy):
  t=title_for(s,tenant,policy['title'])
  if not t:raise HTTPException(404,'Choose an active title in your own catalogue')
  policy={**policy,'title_snapshot':{k:getattr(t,k) for k in ['id','name','runtime_minutes','release_year']}}
 if by_category(policy):
  missing=[c for c in policy['categories'] if not category_title(s,tenant,[c])]
  if missing:raise HTTPException(404,'No active title in your catalogue has the category: '+', '.join(missing))
 return policy
def library_title(s,tenant):return s.scalar(select(MediaTitle).where(MediaTitle.tenant_id==tenant,MediaTitle.published==True,MediaTitle.archived==False).limit(1))
def media_offer_available(s,tenant,policy):
 if policy.get('service')=='combined':return False
 if policy.get('service')=='media' and policy.get('mode')=='library':return bool(library_title(s,tenant))
 if by_category(policy):return bool(category_title(s,tenant,policy['categories'],public=True))
 return not targeted(policy) or bool(title_for(s,tenant,policy.get('title'),public=True))
def ensure_sold_separately(policy):
 if policy.get('service')=='combined':raise HTTPException(409,'Combined Internet + Media packages are no longer sold. Use separate Internet and Media packages.')
def ensure_media_offer(s,tenant,policy):
 if by_category(policy):
  if not category_title(s,tenant,policy['categories'],public=True):raise HTTPException(409,'Media offer is withdrawn or has no published titles. Ask the owner for an available package.')
  return
 candidate=title_for(s,tenant,policy.get('title'),public=True) if targeted(policy) else library_title(s,tenant) if policy.get('service')=='media' and policy.get('mode')=='library' else None
 if not targeted(policy) and not (policy.get('service')=='media' and policy.get('mode')=='library'):return
 if not candidate or not s.execute(update(MediaTitle).where(MediaTitle.id==candidate.id,MediaTitle.tenant_id==tenant,MediaTitle.published==True,MediaTitle.archived==False).values(revision=MediaTitle.revision)).rowcount:raise HTTPException(409,'Media offer is withdrawn or has no published titles. Ask the owner for an available package.')
def media_policy(p,activated=None,revoked=False,now=None):
 if p.get('service') not in ['media','combined']:return None
 if p['service']=='combined':return {'mode':'library','library_hours':p.get('media_hours',24),'title_hours':None,'title':None,'legacy_combined':True,'activation':'awaiting_adapter','playback':'not_connected'}
 mode=p['mode']
 out={'mode':mode,'library_hours':p['hours'] if mode in ['library','hybrid'] else None,'title_hours':p.get('title_hours',48) if mode=='hybrid' else p['hours'] if mode=='title' else None,'title':p.get('title_snapshot') or ({'id':p.get('title'),'name':p.get('title'),'legacy_unresolved':True} if mode in ['title','hybrid'] else None),
  'category_hours':p['hours'] if mode=='category' else None,'categories':p.get('categories') or [],'device_limit':1,'device_transfer':'not_allowed_until_expiry','device_binding':'not_connected','playback':'not_connected'}
 if not activated:return out|{'activation':'awaiting_redemption','activated_at':None,'valid_until':None,'state':'revoked' if revoked else 'not_activated'}
 windows={k:activated+int(out[k]*3600) for k in ['library_hours','title_hours','category_hours'] if out[k]}
 until=max(windows.values());now=now or int(time.time())
 return out|{'activation':'redeemed_in_portal','activated_at':activated,'valid_until':until,'windows':{k.replace('_hours','_until'):v for k,v in windows.items()},'state':'revoked' if revoked else 'expired' if until<=now else 'active'}
def holds_media_pass(s,u,now):
 for e in s.scalars(select(Entitlement).where(Entitlement.tenant_id==u.tenant_id,Entitlement.guest_id==u.id,Entitlement.revoked==False)):
  m=media_policy(e.policy,e.activated,now=now)
  if m and m.get('state')!='expired':return True
 return False
def settings_json(x):return {'catalog_preview':x.catalog_preview if x else 'full','revision':x.revision if x else 0}

def register_media(app,current,db,owner,log):
 def own(s,u,id):
  owner(u);t=s.get(MediaTitle,id)
  if not t or t.tenant_id!=u.tenant_id:raise HTTPException(404,'Media title not found')
  return t
 @app.get('/v1/media/titles')
 def catalogue(u=Depends(current),s=Depends(db)):
  if u.role not in ['sme','guest']:raise HTTPException(403,'Business catalogue permission required')
  q=select(MediaTitle).where(MediaTitle.tenant_id==u.tenant_id)
  if u.role=='guest':
   q=q.where(MediaTitle.published==True,MediaTitle.archived==False);settings=s.get(MediaSettings,u.tenant_id)
   if settings and settings.catalog_preview=='featured' and not holds_media_pass(s,u,int(time.time())):q=q.where(MediaTitle.featured==True)
  return [title_json(t) for t in s.scalars(q.order_by(MediaTitle.name))]
 @app.get('/v1/media/settings')
 def media_settings(u=Depends(current),s=Depends(db)):
  owner(u);return settings_json(s.get(MediaSettings,u.tenant_id))
 @app.post('/v1/media/settings')
 def save_media_settings(b:MediaSettingsIn,u=Depends(current),s=Depends(db)):
  owner(u);x=s.get(MediaSettings,u.tenant_id);now=int(time.time())
  if (x.revision if x else 0)!=b.expected_revision:raise HTTPException(409,'Media settings changed elsewhere. Refresh and try again.')
  if x:x.catalog_preview=b.catalog_preview;x.revision+=1;x.updated=now
  else:x=MediaSettings(tenant_id=u.tenant_id,catalog_preview=b.catalog_preview,revision=1,updated=now);s.add(x)
  log(s,u,'media_settings_updated',u.tenant_id)
  try:s.commit()
  except IntegrityError:s.rollback();raise HTTPException(409,'Media settings changed elsewhere. Refresh and try again.')
  return settings_json(x)
 @app.post('/v1/media/titles',status_code=201)
 def create(b:MediaIn,u=Depends(current),s=Depends(db)):
  owner(u);t=MediaTitle(tenant_id=u.tenant_id,**b.model_dump(),published=False,archived=False,featured=False,revision=1,updated=int(time.time()));s.add(t);s.flush();log(s,u,'media_title_created',t.id);s.commit();return title_json(t)
 @app.post('/v1/media/titles/{id}')
 def edit(id:str,b:MediaUpdate,u=Depends(current),s=Depends(db)):
  own(s,u,id);changed=s.execute(update(MediaTitle).where(MediaTitle.id==id,MediaTitle.revision==b.expected_revision,MediaTitle.archived==False).values(**b.settings.model_dump(),published=False,revision=b.expected_revision+1,updated=int(time.time()))).rowcount
  if not changed:raise HTTPException(409,'Title changed or is archived. Refresh before editing.')
  log(s,u,'media_title_updated',id);s.commit();return title_json(s.get(MediaTitle,id))
 @app.post('/v1/media/titles/{id}/state')
 def state(id:str,b:MediaState,u=Depends(current),s=Depends(db)):
  t=own(s,u,id)
  if not t.archived and b.operation=='restore':raise HTTPException(409,'Title is not archived')
  if t.archived and b.operation!='restore':raise HTTPException(409,'Restore the archived title first')
  values={'revision':b.expected_revision+1,'updated':int(time.time())}
  if b.operation=='publish':values['published']=True
  elif b.operation=='unpublish':values['published']=False
  elif b.operation=='feature':values['featured']=True
  elif b.operation=='unfeature':values['featured']=False
  elif b.operation=='archive':values.update(archived=True,published=False,featured=False)
  else:values.update(archived=False,published=False)
  changed=s.execute(update(MediaTitle).where(MediaTitle.id==id,MediaTitle.revision==b.expected_revision).values(**values)).rowcount
  if not changed:raise HTTPException(409,'Title changed. Refresh before changing publication.')
  log(s,u,'media_title_'+b.operation,id);s.commit();return title_json(s.get(MediaTitle,id))
