// In-memory stand-in for the account API, used by the public demo. It must never call fetch:
// demo visitors may not reach production data, payments, subscriptions or routers.
// Every demoClient() starts from fresh sample data; changes are discarded with the client.
import {shopTime} from './support-report.mjs';

export const DEMO_PAGES=['Overview','Revenue','Sites','Routers','Packages','Vouchers','Payments','Get help'];
export const DEMO_BLOCKED='Not available in the demo — nothing was changed.';
export const DEMO_CODE_PREFIX='DEMO';
const ALPHABET='ABCDEFGHJKLMNPQRSTUVWXYZ23456789';
const DAYS=['mon','tue','wed','thu','fri','sat','sun'];
const THEMES={light:{background:'#f0ece2',surface:'#fffaf0',text:'#16382b',primary:'#2d6554',accent:'#91b29d'},dark:{background:'#062320',surface:'#123c33',text:'#f3f3ed',primary:'#93b99e',accent:'#6e9e88'},source:'default',published_revision:null};

class DemoError extends Error{}
const fail=message=>{throw new DemoError(message)};
const id=()=>globalThis.crypto.randomUUID();
const clone=value=>value==null?value:JSON.parse(JSON.stringify(value));
function randomCode(length=6){const bytes=new Uint8Array(length);globalThis.crypto.getRandomValues(bytes);return [...bytes].map(b=>ALPHABET[b%ALPHABET.length]).join('')}

function localParts(ts,tz){
 const parts=Object.fromEntries(new Intl.DateTimeFormat('en-GB',{timeZone:tz,year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit',weekday:'short',hourCycle:'h23'}).formatToParts(new Date(ts*1000)).map(p=>[p.type,p.value]));
 return {...parts,date:`${parts.year}-${parts.month}-${parts.day}`,minutes:Number(parts.hour)*60+Number(parts.minute),weekday:['Mon','Tue','Wed','Thu','Fri','Sat','Sun'].indexOf(parts.weekday)};
}
function localIso(ts,tz){
 const p=localParts(ts,tz),offset=Math.round((Date.UTC(p.year,p.month-1,p.day,p.hour,p.minute,p.second)-ts*1000)/60000),sign=offset<0?'-':'+',abs=Math.abs(offset);
 return `${p.date}T${p.hour}:${p.minute}:${p.second}${sign}${String(Math.floor(abs/60)).padStart(2,'0')}:${String(abs%60).padStart(2,'0')}`;
}
const toMinutes=hhmm=>{const [h,m]=hhmm.split(':').map(Number);return h*60+m};
export function inSchedule(week,tz,ts){
 const p=localParts(ts,tz),today=week[DAYS[p.weekday]],prev=week[DAYS[(p.weekday+6)%7]];
 if(today){const o=toMinutes(today.open),c=toMinutes(today.close);if((o<c&&o<=p.minutes&&p.minutes<c)||(c<o&&p.minutes>=o))return true}
 if(prev){const o=toMinutes(prev.open),c=toMinutes(prev.close);if(c<o&&p.minutes<c)return true}
 return false;
}

function seed(now){
 const tenant={id:id(),name:'Golden Cafe (demo)'};
 const user={id:id(),username:'demo-owner',role:'sme',tenant_id:tenant.id,must_change_password:false,temporary_password_expires:null,staff_profile:null,platform_owner:false};
 const week=Object.fromEntries(DAYS.map(d=>[d,{open:'07:00',close:'22:00'}]));
 const site=(name,ssid,hours)=>({id:id(),tenant_id:tenant.id,name,timezone:'Asia/Yangon',created:now-30*86400,printed_ssid:ssid,business_hours:hours,network_hours_mode:hours?'business':'always',network_hours:null});
 const sites=[site('Downtown','Golden Cafe WiFi',week),site('Riverside','Golden Cafe Riverside',null)];
 const routers=[{id:id(),tenant_id:tenant.id,site_id:sites[0].id,name:'Front counter gateway',model:'hAP ax²',reported_routeros:'7.16',created:now-20*86400}];
 const pkg=(name,mode,gb,hours,price,extra={})=>({id:id(),name,service:'internet',mode,price,gb,hours,media_hours:24,clock:'elapsed',devices:1,speed:10,title:null,title_hours:48,vip:false,...extra});
 const packages=[pkg('2 Hour Pass','time',1,2,500),pkg('1 Day Pass','both',5,24,1500),pkg('Weekly 20 GB','both',20,168,6000,{devices:2,speed:20}),pkg('VIP Guest','both',50,720,0,{vip:true,devices:3,speed:50})];
 const db={now,tenant,user,sites,routers,packages,vouchers:[],sales:[],orders:[],events:[],audit:[],maintenance:[],reports:[],reconciliations:[]};
 const methods=['Cash','KBZPay','WavePay','Cash','KBZPay','Cash','AYA Pay'];
 [[0,1,0.2],[1,0,0.5],[1,1,1.1],[0,1,1.6],[2,0,2.3],[1,1,3.4],[0,0,4.2],[1,0,5.1]].forEach(([p,s,daysAgo],i)=>{
  const at=Math.round(now-daysAgo*86400),v=addVoucher(db,{package_id:packages[p].id,site_id:sites[s].id,expires_days:30},at);
  if(i<6)addSale(db,v,{amount:v.policy.price,method:methods[i],reference:v.policy.price&&methods[i]!=='Cash'?'TXN-'+(48210+i*7):'',evidence:methods[i]==='Cash'?'Counted at the counter':'Payment screenshot checked'},at+300);
  if(i===1){v.redeemed_at=at+900;v.redeemed_by='demo-guest'}
 });
 const order=(p,s,method,reference,status,hoursAgo)=>{const o={id:id(),tenant_id:tenant.id,guest_id:'demo-guest-'+(db.orders.length+1),site_id:sites[s].id,snapshot:policy(packages[p]),payment_context:{portal_revision:1,destination:'KBZPay 09-000 000 000 (sample)',instructions:'Send the exact amount, then enter the transaction ID.',business_name:tenant.name},amount:packages[p].price,currency:'MMK',method,reference,evidence:'Transaction ID entered by the guest',status,fulfillment:status==='approved'?'pending_adapter':'pending',reviewer_id:status==='approved'?user.id:null,reason:null,created:Math.round(now-hoursAgo*3600),receipt_revision:0};db.orders.unshift(o);if(status==='approved')event(db,{source:'guest_order',record:o,site_id:o.site_id,at:o.created+600});return o};
 order(1,0,'KBZPay','TXN-77120','approved',50);order(2,1,'WavePay','WP-30418','approved',26);order(1,0,'KBZPay','TXN-77981','pending',1.5);order(0,1,'WavePay','WP-31002','pending',0.4);
 db.audit.push(...[['site_registered',sites[0].id,30],['site_registered',sites[1].id,29],['router_registered',routers[0].id,20],['site_hours_updated',sites[0].id,7]].map(([action,target,daysAgo])=>({id:id(),actor_id:user.id,action,target,created:now-daysAgo*86400})));
 return db;
}
const policy=p=>{const {id:_,...rest}=p;return clone(rest)};
function event(db,{source,record,site_id,kind='collection',reference,at}){
 db.events.push({id:id(),site_id,source,source_id:record.id,kind,amount:record.amount,currency:'MMK',service:record.snapshot.service,package_name:record.snapshot.name,method:record.method,reference:reference??record.reference,actor_id:db.user.id,occurred_at:at,timestamp_basis:'recorded_event'});
}
function log(db,action,target,at=nowOf(db)){db.audit.push({id:id(),actor_id:db.user.id,action,target,created:at})}
const nowOf=db=>Math.max(db.now,Math.floor(Date.now()/1000));
function addVoucher(db,b,at=nowOf(db)){
 const p=db.packages.find(x=>x.id===b.package_id)||fail('Choose a package from this business');
 if(b.site_id&&!db.sites.some(x=>x.id===b.site_id))fail('Site not found');
 const days=Number(b.expires_days??30);if(!(days>=1&&days<=365))fail('Redeem deadline must be between 1 and 365 days');
 if(b.custom_code&&!p.vip)fail('Custom codes are allowed only for VIP packages');
 const extra=b.custom_code?String(b.custom_code).toUpperCase().replace(/[^A-Z0-9]/g,''):'';
 const prefix=b.prefix?`${DEMO_CODE_PREFIX}-${String(b.prefix).toUpperCase()}`:DEMO_CODE_PREFIX;
 const code=extra?`${DEMO_CODE_PREFIX}-${extra}`:`${prefix}-${randomCode()}`;
 const v={id:id(),site_id:b.site_id||null,package_id:p.id,policy:policy(p),code_hint:code.slice(-2),code_prefix:extra?DEMO_CODE_PREFIX:prefix,code_format:extra?'custom':'standard',created:at,expires:at+days*86400,redeemed_at:null,redeemed_by:null,reason:null,disabled_at:null,disabled_reason:null,router_sync:null,serial_no:null,production_job_id:null,sheet_no:null,dealer_id:null,revoked:false,deleted:false,code};
 db.vouchers.unshift(v);return v;
}
function addSale(db,v,b,at=nowOf(db)){
 const sale={id:id(),voucher_id:v.id,snapshot:clone(v.policy),amount:b.amount,currency:'MMK',method:b.method,reference:b.reference||'',evidence:b.evidence||'',recorded_by:db.user.id,created:at,refunded_at:null,refunded_by:null,refund_reason:null,refund_reference:null,cancelled_at:null,cancelled_by:null,cancel_reason:null};
 db.sales.push(sale);event(db,{source:'voucher_sale',record:sale,site_id:v.site_id,at});return sale;
}
function voucherStatus(v,now){return v.revoked?'revoked':v.disabled_at?'disabled':v.redeemed_by?'redeemed':v.expires<=now?'expired':'unused'}
function voucherJson(db,v,withCode=false){
 const {code,revoked,deleted,...rest}=v,active=db.sales.find(x=>x.voucher_id===v.id&&!x.cancelled_at);
 return {...clone(rest),status:voucherStatus(v,nowOf(db)),enforcement:'not_connected',...(withCode?{code,replayed:false}:{sale:clone(active)||null,cancelled_sales:clone(db.sales.filter(x=>x.voucher_id===v.id&&x.cancelled_at))})};
}
const findVoucher=(db,vid)=>db.vouchers.find(x=>x.id===vid&&!x.deleted)||fail('Voucher not found');

function revenueFilters(db,q){
 const start=q.get('start')||null,end=q.get('end')||null,timezone=q.get('timezone')||'Asia/Yangon',site_id=q.get('site_id')||null;
 if(!!start!==!!end)fail('Provide both start and end dates, or neither for all time');
 if(start&&end<start)fail('Date range must be ordered and no longer than 366 days');
 const keep=(siteId,ts)=>(!site_id||(site_id==='unassigned'?siteId==null:siteId===site_id))&&(!start||(()=>{const d=localParts(ts,timezone).date;return d>=start&&d<=end})());
 return {timezone,keep,applied:{start,end,timezone,site_id,date_basis:'financial_event_time',pending_date_basis:'order_submission_time'}};
}
function cancelledSaleIds(db){return new Set(db.sales.filter(x=>x.cancelled_at).map(x=>x.id))}
function revenue(db,q){
 const {timezone,keep,applied}=revenueFilters(db,q),events=db.events.filter(e=>keep(e.site_id,e.occurred_at)),pending=db.orders.filter(o=>o.status==='pending'&&keep(o.site_id,o.created));
 const collect=events.filter(e=>e.kind==='collection'),refund=events.filter(e=>e.kind==='refund'),signed=e=>e.kind==='collection'?e.amount:-e.amount,sum=(list,f)=>list.reduce((a,x)=>a+f(x),0);
 const cancelled=cancelledSaleIds(db),counted=e=>e.source!=='voucher_sale'?null:e.kind==='collection'?'vouchers_sold':cancelled.has(e.source_id)?'vouchers_cancelled':'vouchers_refunded';
 const days={},methods={},sites={};
 for(const e of events){
  const day=localParts(e.occurred_at,timezone).date,c=counted(e);
  for(const [group,key] of [[days,day],[methods,e.method],[sites,e.site_id||'unassigned']]){
   const b=group[key]??={gross_collections:0,refunds:0,net_collections:0,collection_count:0,refund_count:0,vouchers_sold:0,vouchers_cancelled:0,vouchers_refunded:0};
   b[e.kind==='collection'?'gross_collections':'refunds']+=e.amount;b[e.kind==='collection'?'collection_count':'refund_count']+=1;b.net_collections+=signed(e);if(c)b[c]+=1;
  }
  const m=days[day].methods??={};m[e.method]=(m[e.method]||0)+signed(e);
 }
 const countSource=source=>Math.max(0,sum(events.filter(e=>e.source===source),e=>e.kind==='collection'?1:-1)),gross=sum(collect,e=>e.amount),returned=sum(refund,e=>e.amount);
 const names=Object.fromEntries(db.sites.map(s=>[s.id,s.name])),now=nowOf(db);
 return {currency:'MMK',...Object.fromEntries(['vouchers_sold','vouchers_cancelled','vouchers_refunded'].map(k=>[k,events.filter(e=>counted(e)===k).length])),filters:applied,net_collections:gross-returned,gross_collections:gross,refunds:returned,collection_count:collect.length,refund_count:refund.length,cancelled_sales:refund.filter(e=>cancelled.has(e.source_id)).length,average_receipt:collect.length?Math.round(gross/collect.length*100)/100:0,approved_orders:countSource('guest_order'),confirmed_payments:Math.max(0,collect.length-refund.length),voucher_sales:countSource('voucher_sale'),pending_orders:pending.length,pending_amount:sum(pending,o=>o.amount),pending_over_24h:pending.filter(o=>o.created<now-86400).length,estimated_timestamp_events:0,by_source:{guest_orders:sum(events.filter(e=>e.source==='guest_order'),signed),voucher_counter_sales:sum(events.filter(e=>e.source==='voucher_sale'),signed)},by_service:Object.fromEntries([...new Set(['combined','internet','media',...events.map(e=>e.service)])].sort().map(k=>[k,sum(events.filter(e=>e.service===k),signed)])),by_day:Object.keys(days).sort().map(date=>({date,...days[date]})),by_method:Object.keys(methods).sort().map(method=>({method,...methods[method]})),by_site:Object.keys(sites).sort().map(k=>({site_id:k==='unassigned'?null:k,site_name:names[k]||'Business-wide / unassigned',...sites[k]}))};
}
function ledger(db,q){
 const {timezone,keep,applied}=revenueFilters(db,q),limit=Math.min(10000,Number(q.get('limit')||100)),offset=Number(q.get('offset')||0),cancelled=cancelledSaleIds(db),names=Object.fromEntries(db.sites.map(s=>[s.id,s.name]));
 const rows=db.events.filter(e=>keep(e.site_id,e.occurred_at)).sort((a,b)=>b.occurred_at-a.occurred_at);
 return {filters:applied,total:rows.length,offset,limit,has_more:rows.length>offset+limit,items:rows.slice(offset,offset+limit).map(e=>({...clone(e),site_name:names[e.site_id]||'Business-wide / unassigned',signed_amount:e.kind==='collection'?e.amount:-e.amount,sale_cancelled:e.kind==='refund'&&cancelled.has(e.source_id),local_time:localIso(e.occurred_at,timezone)}))};
}

const findSite=(db,sid)=>db.sites.find(x=>x.id===sid)||fail('Site not found');
function settleMaintenance(db,site,now){for(const m of db.maintenance)if(m.site_id===site.id&&!m.ended&&m.planned_end<=now){m.ended=m.planned_end;m.post_check=magicCheck(db,site,now)}}
function magicCheck(db,site,at){const routers=db.routers.filter(r=>r.site_id===site.id).length;return {checked:at,result:'unable',summary:routers?'The network could not be checked: no router has a verified connection to MikroMagic yet.':'No router is registered for this shop, so the network could not be checked.',routers,open_incidents:0}}
const activeWindow=(db,site,now)=>db.maintenance.find(m=>m.site_id===site.id&&!m.ended&&m.planned_end>now);
const businessOpen=(site,now)=>site.business_hours?inSchedule(site.business_hours,site.timezone,now):null;
const networkOn=(site,now)=>site.network_hours_mode==='business'&&site.business_hours?inSchedule(site.business_hours,site.timezone,now):site.network_hours_mode==='custom'&&site.network_hours?inSchedule(site.network_hours,site.timezone,now):true;
function hoursJson(db,site,now){
 const open=businessOpen(site,now),active=activeWindow(db,site,now);
 return clone({site_id:site.id,timezone:site.timezone,business_hours:site.business_hours,network_hours_mode:site.network_hours_mode,network_hours:site.network_hours,now:{at:now,business:open===null?'not_set':open?'open':'closed',network:networkOn(site,now)?'on':'off'},maintenance:active||null,history:db.maintenance.filter(m=>m.site_id===site.id).sort((a,b)=>b.started-a.started).slice(0,20)});
}
function siteJson(db,site){const now=nowOf(db);settleMaintenance(db,site,now);return {...clone(site),maintenance_until:activeWindow(db,site,now)?.planned_end??null}}
function checkWeek(week){
 if(week==null)return null;
 for(const d of DAYS){const h=week[d];if(h&&(!/^([01]\d|2[0-3]):[0-5]\d$/.test(h.open)||!/^(([01]\d|2[0-3]):[0-5]\d|24:00)$/.test(h.close)||toMinutes(h.open)===toMinutes(h.close)))fail('Opening and closing times must differ; use 00:00 to 24:00 for all day')}
 return Object.fromEntries(DAYS.map(d=>[d,week[d]?{open:week[d].open,close:week[d].close}:null]));
}
const minutesIn=m=>Number.isInteger(m)&&m>=5&&m<=1440?m:fail('Choose between 5 minutes and 24 hours');

export function scrubDemoText(text,codes=[]){
 if(!text)return text;
 let clean=text.replace(/\b(pass(?:word)?|passwd|pwd|pin|secret|token|api[ _-]?key|private[ _-]?key)\s*[:=]\s*\S+/gi,'$1: [removed]');
 for(const code of codes){const chars=code.replace(/-/g,'').split('');clean=clean.replace(new RegExp('(?<![A-Za-z0-9])'+chars.join('[\\s-]*')+'(?![A-Za-z0-9])','gi'),'[voucher code removed]')}
 return clean;
}
function supportReport(db,site,description){
 const now=nowOf(db);settleMaintenance(db,site,now);
 const maintenance=activeWindow(db,site,now),open=businessOpen(site,now),net=networkOn(site,now),routers=db.routers.filter(r=>r.site_id===site.id);
 const causes=[];
 if(maintenance)causes.push({text:`Planned maintenance is running until ${shopTime(maintenance.planned_end,site.timezone)} shop time; outages now are expected.`,evidence:'Maintenance window recorded by the owner'});
 if(!net)causes.push({text:'The network is planned off right now (network operating hours).',evidence:'Shop network operating hours'});
 if(!routers.length)causes.push({text:'No router is registered for this shop, so MikroMagic cannot see this network at all.',evidence:'Router registry is empty for this shop'});
 else causes.push({text:'No router has a verified connection to MikroMagic, so device and internet status cannot be checked remotely. Check that the router has power and internet at the shop.',evidence:'No verified Magic Hub handshake on record'});
 const targets=new Set([site.id,...routers.map(r=>r.id),...db.maintenance.filter(m=>m.site_id===site.id).map(m=>m.id)]);
 const report={version:1,generated:now,business:db.tenant.name,shop:{name:site.name,timezone:site.timezone},description:scrubDemoText(String(description||'').trim(),db.vouchers.map(v=>v.code))||null,now:{business:open===null?'not_set':open?'open':'closed',network:net?'on':'off',maintenance_until:maintenance?.planned_end??null,maintenance_reason:maintenance?.reason||null},routers:routers.map(r=>({name:r.name,model:r.model,reported_routeros:r.reported_routeros,source:'owner_reported',connection:'not_verified',magic_hub_assigned:false,enrollment_state:null,handshake_verified_at:null,management_read_verified_at:null,management_locked:false})),devices:[],outages:[],recent_events:db.audit.filter(a=>targets.has(a.target)&&a.created>=now-7*86400).sort((a,b)=>a.created-b.created).slice(-15).map(a=>({at:a.created,action:a.action})),likely_causes:causes,excluded:'Passwords, voucher codes, API credentials, WireGuard keys, router addresses and payment details are never included. Free text is scrubbed of anything that looks like one.'};
 const item={id:id(),site_id:site.id,created:now,shared_at:null,report};db.reports.unshift(item);log(db,'support_report_created',item.id);return item;
}

function route(db,method,path,body){
 const [raw,query='']=path.split('?'),q=new URLSearchParams(query),parts=raw.split('/'),now=nowOf(db),is=(m,pattern)=>{if(m!==method||pattern.length!==parts.length)return false;return pattern.every((x,i)=>x==='*'||x===parts[i])};
 if(method==='GET'){
  const lists={entitlements:[],'media/titles':[],'event-deliveries':[],'review-credentials':[],'external-review-actions':[],knowledge:[],hubs:[],'router-plans':[],'router-changes':[],'site-devices':[]};
  if(raw in lists)return lists[raw];
  if(raw==='health')return {status:'ok'};
  if(raw==='appearance/public'||raw==='appearance/effective')return clone(THEMES);
  if(raw==='me')return clone(db.user);
  if(raw==='tenants')return [clone(db.tenant)];
  if(raw==='packages')return clone(db.packages);
  if(raw==='orders')return clone(db.orders);
  if(raw==='audit')return clone([...db.audit].sort((a,b)=>b.created-a.created));
  if(raw==='revenue')return revenue(db,q);
  if(raw==='revenue/ledger')return ledger(db,q);
  if(raw==='revenue/reconciliations')return clone(db.reconciliations);
  if(raw==='vouchers')return db.vouchers.filter(v=>!v.deleted).map(v=>voucherJson(db,v));
  if(raw==='sites')return db.sites.map(s=>siteJson(db,s));
  if(raw==='routers')return db.routers.map(r=>({...clone(r),connection_state:'unverified',connection_verified:false,hub_id:null,last_handshake:null,lifecycle_state:null,management_read_verified_at:null,metadata_source:'owner_reported'}));
  if(raw==='hotspot-sessions/summary')return {status:'unable_to_verify',freshness:'none',active_count:null,routers_observed:0,detail:'The demo has no live HotSpot sessions. Connected customers stay Unable to Verify.',real_device_acceptance:'not_yet_performed'};
  if(raw==='portal'||is('GET',['sites','*','portal']))return {revision:1,draft:{business_name:db.tenant.name,welcome:'Welcome to Golden Cafe Wi-Fi.',language:'both',terms:'',contact:'',direct_purchase:true,voucher_login:true,payment_destination:'KBZPay 09-000 000 000 (sample)',payment_instructions:'Send the exact amount, then enter the transaction ID.',payment_methods:['Cash at counter','KBZPay','WavePay'],hostname:'',guest_interface:'',guest_subnet:'',tls_required:true,isolate_guests:true,allowed_hosts:[]},published:null,published_revision:null,local_portal_package:{status:'not_published',published_revision:null,sha256:null},router_deployment_status:'pending',router_apply_state:'not_connected'};
  if(is('GET',['orders','*','receipts']))return [];
  if(is('GET',['sites','*','hours'])){const site=findSite(db,parts[1]);settleMaintenance(db,site,now);return hoursJson(db,site,now)}
  if(is('GET',['sites','*','support-reports'])){findSite(db,parts[1]);return clone(db.reports.filter(r=>r.site_id===parts[1]))}
  fail(DEMO_BLOCKED);
 }
 if(raw==='auth/login')return {access_token:'demo-session',token_type:'bearer',user:clone(db.user)};
 if(raw==='auth/logout')return {signed_out:true};
 if(raw==='packages'){
  const name=String(body.name||'').trim();if(!name)fail('Enter a package name');if(!(Number(body.price)>=0))fail('Price must be zero or more');
  if(body.service!=='internet')fail('Media packages need a published title; the demo has no media library.');
  const p={id:id(),name,service:'internet',mode:body.mode||'both',price:Number(body.price),gb:Number(body.gb??1),hours:Number(body.hours??1),media_hours:Number(body.media_hours??24),clock:body.clock||'elapsed',devices:Number(body.devices??1),speed:Number(body.speed??10),title:null,title_hours:Number(body.title_hours??48),vip:!!body.vip};
  db.packages.push(p);log(db,'package_created',p.id);return clone(p);
 }
 if(raw==='vouchers'){const v=addVoucher(db,body);log(db,'voucher_issued',v.id);return voucherJson(db,v,true)}
 if(raw==='vouchers/batch'){
  const count=Number(body.count);if(!(Number.isInteger(count)&&count>=1&&count<=100))fail('Create between 1 and 100 vouchers at a time');
  const items=Array.from({length:count},()=>addVoucher(db,{...body,custom_code:undefined}));log(db,'voucher_batch_issued',items[0].id);
  return {replayed:false,items:items.map(v=>voucherJson(db,v,true))};
 }
 if(raw==='vouchers/redeem')fail('Guests redeem codes on the shop Wi-Fi page. Demo codes never work on a real network.');
 if(is('POST',['vouchers','*','sale'])){
  const v=findVoucher(db,parts[1]);if(db.sales.some(x=>x.voucher_id===v.id&&!x.cancelled_at))fail('Voucher already has a payment record; refresh and check it');
  if(v.revoked||v.disabled_at)fail('This voucher cannot be sold in its current state');
  const sale=addSale(db,v,body);log(db,'voucher_payment_recorded',v.id);return {...clone(sale),replayed:false};
 }
 if(is('POST',['vouchers','*','sale','refund'])){
  const v=findVoucher(db,parts[1]),sale=db.sales.find(x=>x.voucher_id===v.id&&!x.cancelled_at)||fail('No confirmed voucher payment');
  if(sale.refunded_at)fail('Refund already processed; refresh and check it');
  Object.assign(sale,{refunded_at:now,refunded_by:db.user.id,refund_reason:body.reason,refund_reference:body.reference||null});v.revoked=true;v.reason=body.reason;
  event(db,{source:'voucher_sale',record:sale,site_id:v.site_id,kind:'refund',reference:body.reference||'',at:now});log(db,'voucher_refund_recorded',v.id);return {...clone(sale),replayed:false};
 }
 if(is('POST',['vouchers','*','sale','cancel'])){
  const v=findVoucher(db,parts[1]),sale=db.sales.find(x=>x.voucher_id===v.id&&!x.cancelled_at)||fail('No active sale to cancel for this voucher');
  if(sale.refunded_at)fail('This sale was already refunded');if(v.redeemed_by)fail('This voucher was already used; record a refund instead');
  Object.assign(sale,{cancelled_at:now,cancelled_by:db.user.id,cancel_reason:body.reason});
  event(db,{source:'voucher_sale',record:sale,site_id:v.site_id,kind:'refund',reference:sale.reference,at:now});log(db,'voucher_sale_cancelled',v.id);return {...clone(sale),replayed:false};
 }
 if(is('POST',['vouchers','*','disable'])){const v=findVoucher(db,parts[1]);if(v.revoked)fail('Revoked vouchers are permanent and cannot be disabled');if(v.disabled_at)fail('Voucher is already disabled');v.disabled_at=now;v.disabled_reason=body.reason;log(db,'voucher_disabled',v.id);return voucherJson(db,v)}
 if(is('POST',['vouchers','*','enable'])){const v=findVoucher(db,parts[1]);if(!v.disabled_at)fail('Voucher is not disabled');v.disabled_at=null;v.disabled_reason=null;log(db,'voucher_reenabled',v.id);return voucherJson(db,v)}
 if(is('POST',['vouchers','*','revoke'])){const v=findVoucher(db,parts[1]);v.revoked=true;v.reason=body.reason;log(db,'voucher_revoked',v.id);return voucherJson(db,v)}
 if(is('POST',['vouchers','*','delete'])){const v=findVoucher(db,parts[1]);if(v.redeemed_by)fail('Activated vouchers cannot be deleted; disable it instead');if(db.sales.some(x=>x.voucher_id===v.id&&!x.cancelled_at))fail('Sold vouchers cannot be deleted; cancel the sale first');v.deleted=true;log(db,'voucher_deleted',v.id);return {deleted:true}}
 if(is('POST',['orders','*','decision'])){
  const o=db.orders.find(x=>x.id===parts[1])||fail('Order not found');if(o.status!=='pending')fail('Order no longer pending');
  if(!['approved','needs_evidence','rejected'].includes(body.decision))fail('Choose a decision');
  Object.assign(o,{status:body.decision,reason:body.reason||null,reviewer_id:db.user.id});
  if(body.decision==='approved'){o.fulfillment='pending_adapter';event(db,{source:'guest_order',record:o,site_id:o.site_id,at:now})}
  log(db,'payment_'+body.decision,o.id);return clone(o);
 }
 if(is('POST',['orders','*','refund'])){
  const o=db.orders.find(x=>x.id===parts[1])||fail('Order not found');if(o.status!=='approved')fail('Order not approved');
  Object.assign(o,{status:'refunded',reason:body.reason});event(db,{source:'guest_order',record:o,site_id:o.site_id,kind:'refund',at:now});log(db,'refund_recorded',o.id);return clone(o);
 }
 if(raw==='revenue/reconciliations'){
  const {keep,applied}=revenueFilters(db,q),events=db.events.filter(e=>keep(e.site_id,e.occurred_at)),actual_collections=events.filter(e=>e.kind==='collection').reduce((a,e)=>a+e.amount,0),actual_refunds=events.filter(e=>e.kind==='refund').reduce((a,e)=>a+e.amount,0);
  const expected_collections=Number(body.expected_collections),expected_refunds=Number(body.expected_refunds||0);if(!(expected_collections>=0&&expected_refunds>=0))fail('Enter counted amounts of zero or more');
  const row={id:id(),site_id:applied.site_id,start_date:applied.start,end_date:applied.end,timezone:applied.timezone,expected_collections,expected_refunds,actual_collections,actual_refunds,variance:(expected_collections-expected_refunds)-(actual_collections-actual_refunds),notes:body.notes||'',actor_id:db.user.id,created:now};
  db.reconciliations.unshift(row);return clone(row);
 }
 if(raw==='sites'){
  const name=String(body.name||'').trim();if(!name)fail('Enter a shop name');if(db.sites.some(s=>s.name.toLowerCase()===name.toLowerCase()))fail('A shop with this name already exists');
  const site={id:id(),tenant_id:db.tenant.id,name,timezone:body.timezone||'Asia/Yangon',created:now,printed_ssid:body.printed_ssid||null,business_hours:null,network_hours_mode:'always',network_hours:null};
  db.sites.push(site);log(db,'site_registered',site.id);return siteJson(db,site);
 }
 if(is('POST',['sites','*','settings'])){const site=findSite(db,parts[1]);site.printed_ssid=body.printed_ssid||null;log(db,'site_settings_updated',site.id);return siteJson(db,site)}
 if(is('POST',['sites','*','hours'])){
  const site=findSite(db,parts[1]),mode=body.network_hours_mode;if(!['business','always','custom'].includes(mode))fail('Choose when the network runs');
  const business=checkWeek(body.business_hours),network=mode==='custom'?checkWeek(body.network_hours):null;
  if(mode==='business'&&!business)fail('Set business hours before using them as network operating hours');if(mode==='custom'&&!network)fail('Custom network operating hours need a weekly schedule');
  Object.assign(site,{business_hours:business,network_hours_mode:mode,network_hours:network});log(db,'site_hours_updated',site.id);return hoursJson(db,site,now);
 }
 if(is('POST',['sites','*','maintenance'])){
  const site=findSite(db,parts[1]);settleMaintenance(db,site,now);if(activeWindow(db,site,now))fail('Maintenance is already running for this shop; extend or end it instead');
  const m={id:id(),site_id:site.id,reason:String(body.reason||'').trim(),started:now,planned_end:now+minutesIn(body.minutes)*60,ended:null,extensions:0,post_check:null};
  db.maintenance.push(m);log(db,'site_maintenance_started',m.id);return hoursJson(db,site,now);
 }
 if(is('POST',['sites','*','maintenance','*','extend'])){
  const site=findSite(db,parts[1]),m=activeWindow(db,site,now)||fail('This maintenance window has already ended');if(m.id!==parts[3])fail('This maintenance window has already ended');
  const end=m.planned_end+minutesIn(body.minutes)*60;if(end-m.started>24*3600)fail('Maintenance cannot run longer than 24 hours in total');m.planned_end=end;m.extensions+=1;log(db,'site_maintenance_extended',m.id);return hoursJson(db,site,now);
 }
 if(is('POST',['sites','*','maintenance','*','end'])){
  const site=findSite(db,parts[1]),m=activeWindow(db,site,now)||fail('This maintenance window has already ended');if(m.id!==parts[3])fail('This maintenance window has already ended');
  m.ended=now;m.post_check=magicCheck(db,site,now);log(db,'site_maintenance_ended',m.id);return hoursJson(db,site,now);
 }
 if(raw==='routers'){
  findSite(db,body.site_id);const name=String(body.name||'').trim();if(!name)fail('Enter a router name');
  const r={id:id(),tenant_id:db.tenant.id,site_id:body.site_id,name,model:body.model||'',reported_routeros:body.reported_routeros||'',created:now};db.routers.push(r);log(db,'router_registered',r.id);
  return {id:r.id,connection_state:'unverified',connection_verified:false,hub_id:null,lifecycle_state:null};
 }
 if(is('POST',['routers','*','preflight']))fail('The demo has no real router to check. Preflight runs against your own router after you sign up.');
 if(is('POST',['routers','*','hotspot-sessions','collect']))fail('The demo has no live HotSpot sessions to collect.');
 if(is('POST',['routers','*','hotspot-sync']))fail('The demo has no real router for HotSpot voucher sync.');
 if(is('POST',['sites','*','support-reports']))return clone(supportReport(db,findSite(db,parts[1]),body.description));
 if(is('POST',['support-reports','*','share']))fail('Demo reports are never sent to MikroMagic support.');
 fail(DEMO_BLOCKED);
}

export function demoClient(now=Math.floor(Date.now()/1000)){
 const db=seed(now);
 const call=(method,path,body)=>{try{return Promise.resolve(clone(route(db,method,path,body??{})))}catch(error){return Promise.reject(error instanceof DemoError?new Error(error.message):error)}};
 const blocked=()=>Promise.reject(new Error(DEMO_BLOCKED));
 return {demo:true,setToken(){},clear(){},request:(path,body)=>call(body===undefined?'GET':'POST',path,body),logout:()=>Promise.resolve({signed_out:true}),download:blocked,upload:blocked,blob:blocked};
}
