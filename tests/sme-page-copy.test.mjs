import test from 'node:test';
import assert from 'node:assert/strict';
import {getSmeMessage,SME_MESSAGES} from '../src/sme-localization.mjs';
import {passServiceName} from '../src/sme-terms.mjs';

test('owner-facing pass names stay separate from API service values',()=>{
 assert.equal(passServiceName('internet'),'Internet Pass');
 assert.equal(passServiceName('media'),'Media Pass');
 assert.equal(passServiceName('combined'),'Internet + Media (no longer sold)');
});

test('English SME page copy keeps the phrases the UI checks require',()=>{
 assert.equal(getSmeMessage('en','vouchers','generate'),'Generate voucher');
 assert.equal(getSmeMessage('en','vouchers','openSale'),'Open sale');
 assert.equal(getSmeMessage('en','vouchers','inventory'),'Voucher inventory');
 assert.equal(getSmeMessage('en','overview','gateways'),'Registered routers');
 assert.equal(getSmeMessage('en','overview','noRouter'),'No router is registered. Wi-Fi status and connected customers cannot be checked.');
 assert.equal(getSmeMessage('en','overview','siteNeeded'),'Add a shop before connecting a router.');
 const routers=SME_MESSAGES.en.routersPage;
 assert.equal(routers.register,'Register router');
 assert.equal(routers.unverified,'Unverified');
 assert.equal(routers.notAssigned,'Not assigned');
 assert.equal(routers.ownerReported,'owner reported');
 assert.equal(routers.fleetTitle,'Platform router fleet');
 assert.equal(routers.createPlan,'Create connection plan');
 assert.match(routers.connectIntro,/private key stays on the router/);
 assert.equal(routers.markReviewed,'Mark plan reviewed');
 assert.equal(routers.inspect,'Inspect actual state & preview');
 assert.equal(routers.apply,'Create safety backup & apply');
 assert.equal(routers.recoveryLead,'Recovery Required.');
 assert.match(routers.recovery,/could not execute or verify rollback/);
 assert.match(routers.recovery,/only when the actual configuration is verified/);
 assert.equal(routers.keepRouter,'Keep Router Version');
 assert.equal(routers.keepMmButton,'Back up & Keep MikroMagic Version');
 assert.match(routers.merge,/Per-setting merge is not available/);
 assert.match(routers.week,/view-only for one week/);
 assert.equal(routers.keepalive,'Persistent keepalive seconds');
 assert.equal(routers.version,'Reported RouterOS version');
 assert.equal(routers.mmVersion,'MikroMagic version');
 assert.equal(routers.expiresAt('18:00'),'Expires 18:00');
 assert.equal(routers.compareLabel,'Compare phrase:');
});

test('Burmese SME copy covers Overview, Vouchers and the Routers sections under the guide',()=>{
 assert.match(getSmeMessage('my','overview','noRouter'),/Router/);
 assert.match(getSmeMessage('my','overview','siteNeeded'),/ဆိုင်/);
 assert.match(getSmeMessage('my','overview','gateways'),/Router/);
 assert.match(getSmeMessage('my','notifications','redeemedNote'),/Sold/);
 assert.match(getSmeMessage('my','notifications','redeemedNote'),/Activated/);
 const vouchers=SME_MESSAGES.my.vouchers;
 assert.match(vouchers.generate,/Voucher/);
 assert.match(vouchers.inventory,/Voucher/);
 assert.match(vouchers.openSale,/အရောင်း/);
 assert.match(vouchers.revoke,/ရုပ်သိမ်း/);
 assert.match(vouchers.status.redeemed,/Activated/);
 const routers=SME_MESSAGES.my.routersPage;
 for(const key of ['registerTitle','listTitle','pairTitle','hubsTitle','connectTitle','plansTitle','safeTitle','registerNote','pairFoot','planNote','recovery','confirm']){
  assert.equal(typeof routers[key],'string',key);
  assert.match(routers[key],/[\u1000-\u109F]/,key);
 }
 assert.equal(routers.recoveryLead,'Recovery Required.');
 assert.equal(routers.expiresAt('18:00'),'18:00 တွင် သက်တမ်းကုန်သည်');
});
