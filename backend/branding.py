"""Application settings owned by the platform owner: app name, logo, languages and the SME announcement.

The name and logo are public because the sign-in page shows them. The logo is re-encoded as a
pixel-only PNG of at most 256×256, so SVG, scripts, metadata and appended data never reach browsers.
"""
import base64,hashlib,time
from io import BytesIO
from typing import Literal
from fastapi import Depends,HTTPException,Body,Header,Response
from pydantic import Field,model_validator
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from PIL import Image,UnidentifiedImageError
from .schemas import Strict
from .models import PlatformSetting,StaffGrant

SETTINGS_KEY='application';LOGO_KEY='application_logo'
LANGUAGES=('my','en')
DEFAULT={'app_name':'MikroMagic','default_language':'my','languages':list(LANGUAGES),'announcement':None}
MAX_LOGO_INPUT=1024*1024;MAX_LOGO_PIXELS=4_000_000;LOGO_SIZE=256

class AnnouncementIn(Strict):
 text:str=Field(min_length=1,max_length=500)
 level:Literal['info','warning']
class ApplicationIn(Strict):
 expected_revision:int=Field(ge=0)
 app_name:str=Field(min_length=1,max_length=40)
 default_language:Literal['my','en']
 languages:list[Literal['my','en']]=Field(min_length=1,max_length=2)
 announcement:AnnouncementIn|None=None
 @model_validator(mode='after')
 def consistent(self):
  self.app_name=self.app_name.strip()
  if not self.app_name:raise ValueError('Enter an app name')
  if len(set(self.languages))!=len(self.languages):raise ValueError('Choose each language once')
  if self.default_language not in self.languages:raise ValueError('The default language must be one of the offered languages')
  self.languages=[x for x in LANGUAGES if x in self.languages]
  return self

def normalize_logo(raw):
 if not raw or len(raw)>MAX_LOGO_INPUT:raise HTTPException(413,'Choose a PNG, JPEG or WebP image up to 1 MiB')
 try:
  with Image.open(BytesIO(raw),formats=['PNG','JPEG','WEBP']) as im:
   if im.width*im.height>MAX_LOGO_PIXELS or getattr(im,'n_frames',1)!=1:raise HTTPException(422,'Use a single-frame image with at most 4 million pixels')
   im.load();converted=im.convert('RGBA');converted.thumbnail((LOGO_SIZE,LOGO_SIZE))
   clean=Image.new('RGBA',converted.size);clean.paste(converted)
   out=BytesIO();clean.save(out,format='PNG');return out.getvalue(),clean.width,clean.height
 except (UnidentifiedImageError,OSError,ValueError,Image.DecompressionBombError) as e:raise HTTPException(422,'The logo must be a valid PNG, JPEG or WebP image') from e

def settings_value(row):return row.value if row else DEFAULT
def public_json(s):
 row=s.get(PlatformSetting,SETTINGS_KEY);logo=s.get(PlatformSetting,LOGO_KEY);v=settings_value(row)
 return {'app_name':v['app_name'],'default_language':v['default_language'],'languages':v['languages'],'logo':f"/v1/branding/logo?v={logo.value['sha256'][:16]}" if logo else None}
def admin_json(s):
 row=s.get(PlatformSetting,SETTINGS_KEY);logo=s.get(PlatformSetting,LOGO_KEY)
 return {'revision':row.revision if row else 0,**settings_value(row),'logo':{'url':public_json(s)['logo'],'width':logo.value['width'],'height':logo.value['height'],'updated':logo.updated} if logo else None}

def register_branding(app,current,db,log):
 def owner_only(u):
  if u.role!='platform' or not u.platform_owner:raise HTTPException(403,'Application settings are limited to the platform owner')
 @app.get('/v1/branding')
 def branding(response:Response,s=Depends(db)):
  response.headers['Cache-Control']='no-store';return public_json(s)
 @app.get('/v1/branding/logo')
 def logo(s=Depends(db)):
  row=s.get(PlatformSetting,LOGO_KEY)
  if not row:raise HTTPException(404,'No custom logo')
  return Response(base64.b64decode(row.value['png']),media_type='image/png',headers={'Content-Security-Policy':"default-src 'none'"})
 @app.get('/v1/announcement')
 def announcement(u=Depends(current),s=Depends(db)):
  if u.role!='sme' or s.get(StaffGrant,u.id):return None
  row=s.get(PlatformSetting,SETTINGS_KEY);a=settings_value(row)['announcement']
  return a|{'revision':row.revision} if a else None
 @app.get('/v1/developer/application')
 def settings(u=Depends(current),s=Depends(db)):
  owner_only(u);return admin_json(s)
 @app.post('/v1/developer/application')
 def save(b:ApplicationIn,u=Depends(current),s=Depends(db)):
  owner_only(u);row=s.get(PlatformSetting,SETTINGS_KEY);now=int(time.time());value=b.model_dump(exclude={'expected_revision'})
  if (row.revision if row else 0)!=b.expected_revision:raise HTTPException(409,'Application settings changed; refresh')
  if row:
   if not s.execute(update(PlatformSetting).where(PlatformSetting.key==SETTINGS_KEY,PlatformSetting.revision==b.expected_revision).values(value=value,revision=b.expected_revision+1,updated=now,updated_by=u.id)).rowcount:raise HTTPException(409,'Application settings changed; refresh')
  else:s.add(PlatformSetting(key=SETTINGS_KEY,value=value,revision=1,updated=now,updated_by=u.id))
  log(s,u,'application_settings_saved',SETTINGS_KEY)
  try:s.commit()
  except IntegrityError:s.rollback();raise HTTPException(409,'Application settings changed; refresh')
  s.expire_all();return admin_json(s)
 @app.post('/v1/developer/application/logo')
 def upload(data:bytes=Body(media_type='application/octet-stream'),key:str=Header(alias='X-Upload-Key',min_length=16,max_length=80,pattern=r'^[A-Za-z0-9-]+$'),u=Depends(current),s=Depends(db)):
  owner_only(u);png,width,height=normalize_logo(data);now=int(time.time())
  value={'png':base64.b64encode(png).decode(),'sha256':hashlib.sha256(png).hexdigest(),'width':width,'height':height}
  row=s.get(PlatformSetting,LOGO_KEY)
  if row:
   if row.value['sha256']==value['sha256']:return admin_json(s)
   row.value=value;row.revision+=1;row.updated=now;row.updated_by=u.id
  else:s.add(PlatformSetting(key=LOGO_KEY,value=value,revision=1,updated=now,updated_by=u.id))
  log(s,u,'application_logo_uploaded',LOGO_KEY)
  try:s.commit()
  except IntegrityError:s.rollback();raise HTTPException(409,'The logo changed at the same time; refresh')
  return admin_json(s)
 @app.post('/v1/developer/application/logo/remove')
 def remove(u=Depends(current),s=Depends(db)):
  owner_only(u);row=s.get(PlatformSetting,LOGO_KEY)
  if row:s.delete(row);log(s,u,'application_logo_removed',LOGO_KEY);s.commit()
  return admin_json(s)
