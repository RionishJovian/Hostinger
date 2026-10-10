"""Local development API. Explicit demo sessions; never expose as production service."""
import json, sqlite3, secrets, time, os, hmac, hashlib
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
DB=Path(os.environ.get('MIKROMAGIC_DB',str(Path(__file__).parent/'demo.sqlite3')))
SESSIONS={}
COLORS={'primary':'#2c6252','accent':'#90b69c','background':'#f0ece2','surface':'#faf8f1','text':'#16382b'}
def seed():
 return {'businesses':[{'id':'cafe','name':'Golden Cafe','plan':'Business','site':'Main branch'},{'id':'lotus','name':'Lotus Guesthouse','plan':'Starter','site':'Lobby'}], 'packages':[
 {'id':'p1','tenant':'cafe','name':'Quick internet','service':'internet','mode':'data','gb':1,'hours':0,'clock':'elapsed','speed':10,'devices':1,'price':1000},
 {'id':'p2','tenant':'cafe','name':'Work & browse','service':'internet','mode':'both','gb':5,'hours':3,'clock':'elapsed','speed':20,'devices':1,'price':3000},
 {'id':'p3','tenant':'cafe','name':'Cinema day','service':'media','mode':'library','gb':0,'hours':24,'clock':'elapsed','speed':0,'devices':1,'price':2000},
 {'id':'p4','tenant':'cafe','name':'One movie','service':'media','mode':'title','title':'river','gb':0,'hours':48,'clock':'elapsed','speed':0,'devices':1,'price':1500},
 {'id':'p5','tenant':'cafe','name':'Browse + cinema','service':'combined','mode':'both','gb':5,'hours':3,'mediaHours':24,'clock':'elapsed','speed':20,'devices':1,'price':4000}],
 'orders':[], 'vouchers':[], 'entitlements':[], 'audit':[], 'routers':[],
 'portal':{'cafe':{'name':'Golden Cafe','hostname':'guest.goldencafe.test','interface':'bridge-guests','subnet':'192.168.50.0/24','language':'English','welcome':'Connect, relax, and enjoy.','paymentDestination':'Ask the counter for transfer details','walledGarden':'portal.local, media.local','isolation':True,'ipv6':'Block until validated','devices':1}},
 'wan':{'cafe':{'budget':500,'used':320,'resetDay':20,'warn':80,'action':'Notify owner','failover':True,'balancing':'Off'}},
 'themes':{'light':COLORS,'dark':{'primary':'#90b69c','accent':'#90b69c','background':'#062322','surface':'#10332f','text':'#f7f8f3'}},'previousThemes':None,'scope':['platform','sme','guest'],'override':True,
 'media':[{'id':'river','name':'Rivers of our land','kind':'Demo catalogue • no stream attached','minutes':52},{'id':'cooking','name':'Flavors of home','kind':'Demo catalogue • no stream attached','minutes':28}], 'costs':{'cafe':{'starlink':0,'platform':0,'media':0}}, 'outbox':[]}
def conn():
 c=sqlite3.connect(DB,timeout=10);c.execute('CREATE TABLE IF NOT EXISTS state (id INTEGER PRIMARY KEY, data TEXT)');c.execute('CREATE TABLE IF NOT EXISTS nonce (value TEXT PRIMARY KEY, ts INTEGER)');return c
def read():
 with conn() as c:
  row=c.execute('SELECT data FROM state WHERE id=1').fetchone()
  if not row:
   s=seed();c.execute('INSERT INTO state VALUES(1,?)',(json.dumps(s),));return s
  return json.loads(row[0])
def mutate(fn):
 with conn() as c:
  c.execute('BEGIN IMMEDIATE');row=c.execute('SELECT data FROM state WHERE id=1').fetchone();s=json.loads(row[0]) if row else seed();result=fn(s);c.execute('INSERT OR REPLACE INTO state VALUES(1,?)',(json.dumps(s),));return result
class Error(Exception):
 def __init__(self,msg,code=400):self.msg,self.code=msg,code

def check(ok,msg,code=400):
 if not ok:raise Error(msg,code)
def ident(prefix):return prefix+'_'+secrets.token_hex(5)
def audit(s,user,action,target):s['audit'].insert(0,{'id':ident('a'),'time':time.time(),'actor':user['role'],'tenant':user['tenant'],'action':action,'target':target})
def owner(user):check(user['role'] in ['sme','platform'],'Owner permission required',403)
def tenantcheck(user,t):check(user['tenant']==t or user['role']=='platform','Different business',403)
def publicstate(s,user):
 t=user['tenant'];r=dict(s)
 for key in ['packages','orders','vouchers','entitlements','routers','audit']:
  r[key]=[x for x in s[key] if (user['role']=='platform' or x.get('tenant')==t)]
 if user['role']=='guest':
  r['orders']=[x for x in r['orders'] if x['guest']==user['guest']];r['entitlements']=[x for x in r['entitlements'] if x['guest']==user['guest']];r['vouchers']=[];r['audit']=[];r['routers']=[]
  r['portal']={t:s['portal'].get(t,{})};r['wan']={};r['costs']={};r['outbox']=[]
 elif user['role']=='sme':
  r['businesses']=[x for x in s['businesses'] if x['id']==t];r['portal']={t:s['portal'].get(t,{})};r['wan']={t:s['wan'].get(t,{})};r['costs']={t:s['costs'].get(t,{})};r['outbox']=[x for x in s['outbox'] if x['tenant']==t]
 return r

def grant(s,tenant,guest,p,order):
 existing=next((e for e in s['entitlements'] if e['source']==order),None)
 if existing:return existing
 e={'id':ident('e'),'tenant':tenant,'guest':guest,'package':p.copy(),'source':order,'activated':None,'usedBytes':0,'connectedSeconds':0,'revoked':False,'created':time.time()};s['entitlements'].append(e);return e

def access(e,service,title=None,now=None):
 now=now or time.time();p=e['package'];check(not e['revoked'],'Access revoked',403);check(e['activated'] is not None,'Activate your pass first',403)
 age=now-e['activated']
 if service=='internet':
  check(p['service'] in ['internet','combined'],'No internet entitlement',403)
  if p['mode'] in ['data','both']:check(e['usedBytes']<p['gb']*1_000_000_000,'Data quota exhausted',403)
  if p['mode'] in ['time','both']:
   used=e['connectedSeconds'] if p.get('clock')=='connected' else age;check(used<p['hours']*3600,'Time quota expired',403)
 else:
  check(p['service'] in ['media','combined'],'No media entitlement',403)
  hours=p.get('mediaHours',24) if p['service']=='combined' else p['hours'];check(age<hours*3600,'Media viewing window expired',403)
  if p['mode']=='title':check(title==p.get('title'),'This movie is not included',403)
 return {'allowed':True,'adapter':'simulated','message':'Entitlement allowed. No real network or media stream is attached.'}

def decision(s,user,body):
 owner(user);o=next((x for x in s['orders'] if x['id']==body.get('id')),None);check(o is not None,'Order not found',404);tenantcheck(user,o['tenant']);d=body.get('decision');check(d in ['approved','rejected','needs_evidence'],'Invalid decision')
 if o['status']==d:return {'order':o,'replayed':True}
 check(o['status']=='pending','Order is not awaiting review',409)
 check(d=='approved' or body.get('reason','').strip(),'A reason is required')
 o.update(status=d,reviewer=user['role'],reason=body.get('reason',''),decided=time.time())
 if d=='approved':
  e=grant(s,o['tenant'],o['guest'],o['package'],o['id']);o['fulfillment']='demo_granted';o['entitlement']=e['id']
 audit(s,user,'Payment '+d,o['id']);s['outbox'].append({'id':ident('event'),'tenant':o['tenant'],'event':'payment.'+d,'order':o['id'],'delivery':'Not sent — adapter credentials needed'});return {'order':o}

class Handler(BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def send(self,status,data):
  b=json.dumps(data).encode();self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(b)
 def do_GET(self):self.handle_api()
 def do_POST(self):self.handle_api()
 def handle_api(self):
  try:
   raw=self.rfile.read(int(self.headers.get('Content-Length','0')));check(len(raw)<1_000_000,'Request too large',413);b=json.loads(raw or '{}');path=self.path.split('?')[0]
   if path=='/api/health':return self.send(200,{'mode':'development','adapters':'simulated'})
   if path=='/api/demo-session':
    check(self.command=='POST','Method not allowed',405);role=b.get('role');check(role in ['platform','sme','guest'],'Invalid role');t=b.get('tenant','cafe');check(t in ['cafe','lotus'],'Unknown tenant');token=secrets.token_urlsafe(32);SESSIONS[token]={'role':role,'tenant':t,'guest':b.get('guest','guest-demo')};return self.send(200,{'token':token,'user':SESSIONS[token],'mode':'demo'})
   user=SESSIONS.get(self.headers.get('Authorization','').removeprefix('Bearer '))
   if path=='/api/hooks/payment-decision':
    key=os.environ.get('PAYMENT_HOOK_SECRET');check(bool(key),'Webhook adapter is not configured',503)
    stamp=self.headers.get('X-Timestamp','');nonce=self.headers.get('X-Nonce','');check(stamp.isdigit() and abs(time.time()-int(stamp))<300 and len(nonce)>=16,'Expired or invalid callback',401)
    expected=hmac.new(key.encode(),stamp.encode()+b'.'+nonce.encode()+b'.'+raw,hashlib.sha256).hexdigest();check(hmac.compare_digest(expected,self.headers.get('X-Signature','')),'Invalid signature',401)
    t=os.environ.get('PAYMENT_HOOK_TENANT');check(t in ['cafe','lotus'],'Webhook tenant scope missing',503)
    with conn() as c:
     c.execute('DELETE FROM nonce WHERE ts<?',(int(time.time())-600,))
     try:c.execute('INSERT INTO nonce VALUES(?,?)',(nonce,int(time.time())))
     except sqlite3.IntegrityError:raise Error('Callback replay blocked',409)
    user={'role':'sme','tenant':t};return self.send(200,mutate(lambda s:decision(s,user,b)))
   check(user is not None,'Session required',401)
   if path=='/api/state':return self.send(200,publicstate(read(),user))
   check(self.command=='POST','Method not allowed',405)
   def action(s):
    t=user['tenant']
    if path=='/api/orders':
     check(user['role']=='guest','Guest session required',403);p=next((x for x in s['packages'] if x['id']==b.get('package') and x['tenant']==t),None);check(p is not None,'Package unavailable',404)
     check(b.get('method') and b.get('reference') and b.get('evidence'),'Method, transaction reference and evidence are required')
     duplicate=any(o['reference']==b['reference'] and o['tenant']==t for o in s['orders'])
     o={'id':ident('order'),'tenant':t,'guest':user['guest'],'package':p.copy(),'amount':p['price'],'currency':'MMK','method':b['method'],'reference':b['reference'],'evidence':b['evidence'],'destination':s['portal'].get(t,{}).get('paymentDestination',''),'created':time.time(),'status':'pending','fulfillment':'pending','duplicateReference':duplicate};s['orders'].append(o);audit(s,user,'Payment evidence submitted',o['id']);return o
    if path=='/api/orders/evidence':
     o=next((x for x in s['orders'] if x['id']==b.get('id') and x['tenant']==t and x['guest']==user.get('guest')),None);check(o is not None,'Order not found',404);check(o['status']=='needs_evidence','Evidence not requested',409);check(b.get('evidence'),'Evidence required');o['evidence']=b['evidence'];o['status']='pending';return o
    if path=='/api/orders/decision':return decision(s,user,b)
    if path=='/api/orders/refund':
     owner(user);o=next((x for x in s['orders'] if x['id']==b.get('id')),None);check(o is not None,'Order not found',404);tenantcheck(user,o['tenant']);check(o['status']=='approved','Only approved orders can be marked refunded',409);check(b.get('reason'),'Refund reason required');o['status']='refunded';o['refundReason']=b['reason']
     for e in s['entitlements']:
      if e['source']==o['id']:e['revoked']=True
     audit(s,user,'Refund recorded and access revoked',o['id']);return o
    if path=='/api/vouchers/redeem':
     check(user['role']=='guest','Guest session required',403);v=next((x for x in s['vouchers'] if x['code']==b.get('code','').strip().upper() and x['tenant']==t),None);check(v is not None,'Invalid voucher',404);check(not v.get('redeemed'),'Voucher already redeemed',409);check(v['expires']>time.time(),'Voucher expired',403);v['redeemed']=user['guest'];e=grant(s,t,user['guest'],v['package'],v['id']);audit(s,user,'Voucher redeemed',v['id']);return e
    if path in ['/api/activate','/api/check-access','/api/demo-usage']:
     e=next((x for x in s['entitlements'] if x['id']==b.get('id')),None);check(e is not None,'Pass not found',404);tenantcheck(user,e['tenant']);check(user['role']!='guest' or e['guest']==user['guest'],'Different guest',403)
     if path=='/api/activate':
      check(not e['revoked'],'Access revoked',403);e['activated']=e['activated'] or time.time();return e
     if path=='/api/demo-usage':
      owner(user);e['usedBytes']+=max(0,float(b.get('gb',0)))*1_000_000_000;e['connectedSeconds']+=max(0,float(b.get('seconds',0)));return e
     return access(e,b.get('service','internet'),b.get('title'))
    owner(user)
    if path=='/api/packages':
     p=b.copy();p['tenant']=t;p['id']=ident('p');check(p.get('name') and p.get('service') in ['internet','media','combined'],'Name and service required');check(p.get('mode') in ['data','time','both','library','title'],'Invalid mode');check(float(p.get('price',0))>0,'Price must be positive');check(p['mode'] not in ['data','both'] or float(p.get('gb',0))>0,'Data quota must be positive');check(p['mode']=='data' or float(p.get('hours',0))>0,'Duration must be positive');s['packages'].append(p);audit(s,user,'Package created',p['id']);return p
    if path=='/api/vouchers':
     p=next((x for x in s['packages'] if x['id']==b.get('package') and x['tenant']==t),None);check(p is not None,'Package unavailable',404);v={'id':ident('v'),'tenant':t,'code':secrets.token_hex(6).upper(),'package':p.copy(),'expires':time.time()+30*86400,'redeemed':None};s['vouchers'].append(v);audit(s,user,'Voucher generated (not recorded as paid)',v['id']);return v
    if path in ['/api/portal','/api/wan','/api/costs']:
     key=path.split('/')[-1];s[key][t]=b; audit(s,user,key+' draft saved (not applied to router)',t);return b
    if path=='/api/routers':
     check(b.get('name'),'Router name required');r={'id':ident('router'),'tenant':t,'name':b['name'],'model':b.get('model','Unknown'),'site':b.get('site','Main branch'),'status':'Pending real connection','hub':'Magic Hub','verified':False};s['routers'].append(r);audit(s,user,'Router registered, verification pending',r['id']);return r
    if path=='/api/themes':
     check(user['role']=='platform','Platform owner only',403);import re
     for palette in b['themes'].values():
      for val in palette.values():check(bool(re.fullmatch(r'#[0-9a-fA-F]{6}',val)),'Invalid color')
     s['previousThemes']=s['themes'];s['themes']=b['themes'];s['scope']=b.get('scope',['platform','sme','guest']);s['override']=bool(b.get('override',True));audit(s,user,'Theme published','theme');return s['themes']
    if path=='/api/themes/restore':
     check(user['role']=='platform','Platform owner only',403);check(s['previousThemes'] is not None,'No prior theme');s['themes'],s['previousThemes']=s['previousThemes'],s['themes'];return s['themes']
    raise Error('Endpoint not found',404)
   return self.send(200,mutate(action))
  except Error as e:self.send(e.code,{'error':e.msg})
  except (ValueError,KeyError,TypeError) as e:self.send(400,{'error':'Invalid request: '+str(e)})
  except Exception:self.send(500,{'error':'Internal error'})
if __name__=='__main__':
 read();print('Development API listening on 127.0.0.1:8787',flush=True);ThreadingHTTPServer(('127.0.0.1',8787),Handler).serve_forever()
