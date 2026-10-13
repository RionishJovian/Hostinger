import test from 'node:test';
import assert from 'node:assert/strict';
import {demoClient,DEMO_PAGES,DEMO_BLOCKED,scrubDemoText,inSchedule} from '../src/demo-api.mjs';

const SME_LOAD=['tenants','packages','orders','entitlements','audit','appearance/effective','media/titles','event-deliveries','review-credentials','external-review-actions','knowledge','revenue','vouchers','sites','routers','hubs','router-plans','router-changes','site-devices','hotspot-sessions/summary','portal'];

async function withoutNetwork(run){
 const original=globalThis.fetch;let calls=0;
 globalThis.fetch=()=>{calls++;throw Error('demo must not use the network')};
 try{await run()}finally{globalThis.fetch=original}
 assert.equal(calls,0);
}

test('the demo serves the whole owner workspace without any network call',()=>withoutNetwork(async()=>{
 const api=demoClient();
 const login=await api.request('auth/login',{username:'demo-owner',password:'demo'});
 assert.ok(login.access_token);
 const me=await api.request('me');
 assert.equal(me.role,'sme');assert.equal(me.staff_profile,null);assert.equal(me.platform_owner,false);
 for(const path of SME_LOAD)assert.notEqual(await api.request(path),undefined,path);
 const [tenant]=await api.request('tenants');
 assert.match(tenant.name,/demo/i);
 const site=(await api.request('sites'))[0];
 const pkg=(await api.request('packages'))[1];
 const voucher=await api.request('vouchers',{site_id:site.id,package_id:pkg.id,expires_days:30,request_key:'demo-test-0000001'});
 await api.request('vouchers/'+voucher.id+'/sale',{amount:pkg.price,method:'Cash',reference:'',evidence:'Counted',confirmed_received:true});
 await api.request('sites/'+site.id+'/maintenance',{minutes:30,reason:'Test'});
 await api.request('sites/'+site.id+'/support-reports',{description:'Slow'});
 await api.logout();
}));

test('demo voucher codes are clearly marked and never returned again after issue',async()=>{
 const api=demoClient(),pkg=(await api.request('packages'))[0];
 const one=await api.request('vouchers',{package_id:pkg.id,expires_days:30,prefix:'CAFE',request_key:'demo-test-0000002'});
 assert.match(one.code,/^DEMO-CAFE-[A-Z2-9]{6}$/);
 const batch=await api.request('vouchers/batch',{package_id:pkg.id,count:5,expires_days:7,request_key:'demo-test-0000003'});
 assert.equal(batch.items.length,5);
 for(const item of batch.items)assert.match(item.code,/^DEMO-[A-Z2-9]{6}$/);
 for(const listed of await api.request('vouchers'))assert.equal(listed.code,undefined);
});

test('every demo visit starts from the same fresh sample data',async()=>{
 const first=demoClient(),pkg=(await first.request('packages'))[0];
 const before=(await first.request('vouchers')).length;
 await first.request('vouchers',{package_id:pkg.id,expires_days:30,request_key:'demo-test-0000004'});
 await first.request('packages',{name:'Visitor package',service:'internet',mode:'time',price:100,gb:1,hours:1});
 assert.equal((await first.request('vouchers')).length,before+1);
 const second=demoClient();
 assert.equal((await second.request('vouchers')).length,before);
 assert.ok(!(await second.request('packages')).some(p=>p.name==='Visitor package'));
});

test('revenue follows recorded sales, approvals and refunds',async()=>{
 const api=demoClient(),start=await api.request('revenue');
 assert.equal(start.pending_orders,2);
 const order=(await api.request('orders')).find(o=>o.status==='pending');
 await api.request('orders/'+order.id+'/decision',{decision:'approved',reason:'',expected_receipt_revision:0});
 const approved=await api.request('revenue');
 assert.equal(approved.net_collections,start.net_collections+order.amount);
 assert.equal(approved.pending_orders,1);
 await api.request('orders/'+order.id+'/refund',{reason:'Guest left'});
 const refunded=await api.request('revenue');
 assert.equal(refunded.net_collections,start.net_collections);
 assert.equal(refunded.refunds,order.amount);
 const close=await api.request('revenue/reconciliations?timezone=Asia%2FYangon',{expected_collections:refunded.gross_collections+500,expected_refunds:refunded.refunds,notes:'',request_key:'reconcile-demo-000001'});
 assert.equal(close.variance,500);
 const ledger=await api.request('revenue/ledger?limit=2');
 assert.equal(ledger.items.length,2);assert.equal(ledger.has_more,true);
});

test('actions outside the demo are refused without changing anything',async()=>{
 const api=demoClient(),site=(await api.request('sites'))[0],router=(await api.request('routers'))[0];
 const report=await api.request('sites/'+site.id+'/support-reports',{});
 const audit=(await api.request('audit')).length;
 await assert.rejects(api.request('support-reports/'+report.id+'/share',{}),/never sent to MikroMagic support/);
 await assert.rejects(api.request('routers/'+router.id+'/preflight',{}),/no real router/);
 await assert.rejects(api.request('routers/'+router.id+'/hotspot-sessions/collect',{}),/no live HotSpot sessions/);
 const sessions=await api.request('hotspot-sessions/summary');
 assert.equal(sessions.status,'unable_to_verify');
 assert.equal(sessions.active_count,null);
 await assert.rejects(api.request('vouchers/redeem',{code:'DEMO-ABCDEF'}),/never work on a real network/);
 await assert.rejects(api.request('staff',{username:'x'}),new RegExp(DEMO_BLOCKED));
 await assert.rejects(api.request('subscriptions/requests',{}),new RegExp(DEMO_BLOCKED));
 await assert.rejects(api.request('platform/businesses'),new RegExp(DEMO_BLOCKED));
 await assert.rejects(api.download('vouchers/production',{}),new RegExp(DEMO_BLOCKED));
 assert.equal((await api.request('audit')).length,audit);
 assert.equal((await api.request(`sites/${site.id}/support-reports`))[0].shared_at,null);
});

test('help reports remove issued demo codes and password-like text',async()=>{
 const api=demoClient(),site=(await api.request('sites'))[0],pkg=(await api.request('packages'))[0];
 const v=await api.request('vouchers',{package_id:pkg.id,expires_days:30,request_key:'demo-test-0000005'});
 const spaced=v.code.replace('-',' ');
 const item=await api.request('sites/'+site.id+'/support-reports',{description:`Code ${spaced} failed, password: hunter2. The demo is slow.`});
 const text=item.report.description;
 assert.ok(!text.includes(v.code.slice(5)));assert.ok(!text.includes('hunter2'));
 assert.match(text,/The demo is slow/);
 assert.equal(scrubDemoText('pin=1234 ok'),'pin: [removed] ok');
});

test('shop schedules handle overnight hours in the shop timezone',()=>{
 const week=Object.fromEntries(['mon','tue','wed','thu','fri','sat','sun'].map(d=>[d,{open:'18:00',close:'02:00'}]));
 const at=iso=>Math.floor(Date.parse(iso)/1000);
 assert.equal(inSchedule(week,'Asia/Yangon',at('2026-10-12T01:30:00+06:30')),true);
 assert.equal(inSchedule(week,'Asia/Yangon',at('2026-10-12T12:00:00+06:30')),false);
 assert.equal(inSchedule(week,'Asia/Yangon',at('2026-10-12T19:00:00+06:30')),true);
});

test('the demo navigation is limited to sample-safe pages',async()=>{
 for(const page of ['Staff','Subscription','Integrations','Media','Account','Audit','Network','Internet'])assert.ok(!DEMO_PAGES.includes(page),page);
 assert.deepEqual(DEMO_PAGES,['Overview','Revenue','Sites','Routers','Captive portal','Packages','Vouchers','Payments','Get help','Did you know?']);
 assert.ok(DEMO_PAGES.includes('Did you know?'));
 assert.ok(DEMO_PAGES.includes('Captive portal'));
 const knowledge=await demoClient().request('knowledge');
 assert.ok(knowledge.length>=2);
 assert.ok(knowledge.every(c=>c.published&&!c.archived&&c.fact&&c.title));
 assert.ok(knowledge.some(c=>/torch/i.test(c.title)));
 const capability=await demoClient().request('magic-connect/capability');
 assert.equal(capability.router_setup_available,true);
 assert.equal(capability.pairing_available,false);
});
