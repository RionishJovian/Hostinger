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
 assert.equal(routers.scriptReported,'from setup script');
 assert.equal(routers.nameOnly,'name only');
 assert.equal(routers.hubConnectSteps.reported,'Router reported');
 assert.equal(routers.hubConnectSteps.awaiting_handshake,'Handshake');
 assert.equal(routers.hubConnectSteps.management_applied,'Management ready');
 assert.equal(routers.hubConnectSteps.connected,'Connected');
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
 assert.equal(routers.version,'RouterOS version');
 assert.equal(routers.hubConnectButton,'Connect with Magic Hub');
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

test('Revenue and Payments page copy exists in English and Burmese',()=>{
 assert.equal(getSmeMessage('en','revenue','filtersTitle'),'Report filters');
 assert.equal(getSmeMessage('en','payments','queueTitle'),'Payment review queue');
 assert.equal(getSmeMessage('en','payments','approve'),'Confirm receipt & approve');
 assert.match(getSmeMessage('my','revenue','filtersTitle'),/[\u1000-\u109F]/);
 assert.match(getSmeMessage('my','revenue','netCollections'),/[\u1000-\u109F]/);
 assert.match(getSmeMessage('my','revenue','reconcileTitle'),/[\u1000-\u109F]/);
 assert.match(getSmeMessage('my','payments','queueTitle'),/[\u1000-\u109F]/);
 assert.match(getSmeMessage('my','payments','approve'),/[\u1000-\u109F]/);
 assert.match(SME_MESSAGES.my.revenue.workloadBody(2,1,0,0),/၂|2/);
 assert.match(SME_MESSAGES.en.revenue.periodLine('All time','Asia/Yangon','All shops'),/All time/);
 assert.match(SME_MESSAGES.my.payments.reviewTitle('Cafe'),/Cafe/);
});

test('Packages / Passes page copy exists in English and Burmese',()=>{
 assert.equal(getSmeMessage('en','packages','listTitle'),'Passes');
 assert.equal(getSmeMessage('en','packages','create'),'Create pass');
 assert.equal(getSmeMessage('en','packages','internetPass'),'Internet Pass');
 assert.match(getSmeMessage('my','packages','listTitle'),/[\u1000-\u109F]/);
 assert.match(getSmeMessage('my','packages','create'),/[\u1000-\u109F]/);
 assert.match(getSmeMessage('my','packages','createTitle'),/[\u1000-\u109F]/);
 assert.equal(getSmeMessage('my','packages','internetPass'),'Internet Pass');
 assert.equal(SME_MESSAGES.my.packages.policyBoth(1,2),'1 GB / 2 နာရီ');
});

test('Sites and SiteHours page copy exists in English and Burmese',()=>{
 assert.equal(getSmeMessage('en','sites','listTitle'),'Shops');
 assert.equal(getSmeMessage('en','siteHours','title'),'Opening hours');
 assert.equal(getSmeMessage('en','siteHours','modes').always,'24×7 (always on)');
 assert.match(getSmeMessage('my','sites','listTitle'),/[\u1000-\u109F]/);
 assert.match(getSmeMessage('my','siteHours','title'),/[\u1000-\u109F]/);
 assert.match(getSmeMessage('my','siteHours','maintenanceTitle'),/[\u1000-\u109F]/);
 assert.match(SME_MESSAGES.my.siteHours.days.mon,/[\u1000-\u109F]/);
 assert.match(SME_MESSAGES.my.siteHours.needBusinessFirst,/[\u1000-\u109F]/);
});

test('Media and Account page copy exists in English and Burmese',()=>{
 assert.equal(getSmeMessage('en','media','catalogueTitle'),'Media catalogue');
 assert.equal(getSmeMessage('en','media','createDraft'),'Create draft title');
 assert.equal(getSmeMessage('en','media','startsFirstUse'),'Starts at your first use');
 assert.equal(getSmeMessage('en','account','sessionsTitle'),'Signed-in devices');
 assert.equal(getSmeMessage('en','account','setPassword'),'Set your personal password');
 assert.match(getSmeMessage('my','media','catalogueTitle'),/[\u1000-\u109F]/);
 assert.match(getSmeMessage('my','media','createDraft'),/[\u1000-\u109F]/);
 assert.match(getSmeMessage('my','media','rulesTitle'),/[\u1000-\u109F]/);
 assert.match(getSmeMessage('my','account','sessionsTitle'),/[\u1000-\u109F]/);
 assert.match(getSmeMessage('my','account','changePassword'),/[\u1000-\u109F]/);
 assert.match(SME_MESSAGES.my.media.libraryCombined(72),/[\u1000-\u109F]/);
 assert.equal(SME_MESSAGES.en.media.ops.publish,'Publish');
 assert.match(SME_MESSAGES.my.media.ops.publish,/[\u1000-\u109F]/);
});

test('Network Devices inventory copy exists in English and Burmese',()=>{
 assert.equal(getSmeMessage('en','networkDevices','title'),'Switches and access points');
 assert.match(getSmeMessage('en','networkDevices','poeNote'),/never offered/);
 assert.match(getSmeMessage('en','networkDevices','honesty'),/Unverified/);
 assert.match(getSmeMessage('my','networkDevices','title'),/[\u1000-\u109F]/);
 assert.match(getSmeMessage('my','networkDevices','register'),/[\u1000-\u109F]/);
 assert.match(SME_MESSAGES.en.networkDevices.limitsNote(1,5),/1 switch and 5 access points/);
 assert.doesNotMatch(getSmeMessage('en','networkDevices','intro'),/live discovery is connected/i);
});

test('Media catalogue copy is Jellyfin-only (no Plex product promise)',()=>{
 assert.match(getSmeMessage('en','media','rulesNote'),/Jellyfin/);
 assert.match(getSmeMessage('en','media','rulesNote'),/only supported local Media Server/);
 assert.equal(getSmeMessage('en','media','serverDisconnected'),'Jellyfin not connected');
 assert.match(getSmeMessage('en','media','playbackBody'),/Jellyfin credentials/);
 assert.match(getSmeMessage('my','media','rulesNote'),/Jellyfin/);
 assert.equal(getSmeMessage('my','media','serverDisconnected'),'Jellyfin မချိတ်ဆက်ရသေး');
 for(const locale of ['en','my']){
  const media=SME_MESSAGES[locale].media;
  for(const [key,value] of Object.entries(media)){
   const text=typeof value==='function'?String(value('x',1,'y')):String(value);
   assert.doesNotMatch(text,/\bPlex\b/i,`${locale}.media.${key} must not mention Plex`);
  }
 }
});

test('Integrations, Did you know?, first-site and Magic Boy copy exist in English and Burmese',()=>{
 assert.equal(getSmeMessage('en','integrations','create'),'Create credential');
 assert.match(getSmeMessage('en','integrations','connectNote'),/does not connect/);
 assert.equal(getSmeMessage('en','didYouKnow','explain'),'Explain with Magic Boy');
 assert.equal(getSmeMessage('en','firstSite','title'),'Set up your first shop');
 assert.equal(getSmeMessage('en','magicBoy','name'),'Magic Boy');
 assert.match(getSmeMessage('my','integrations','create'),/[\u1000-\u109F]/);
 assert.match(getSmeMessage('my','didYouKnow','title'),/[\u1000-\u109F]/);
 assert.match(getSmeMessage('my','firstSite','title'),/[\u1000-\u109F]/);
 assert.match(getSmeMessage('my','magicBoy','restrained'),/[\u1000-\u109F]/);
 assert.equal(SME_MESSAGES.en.firstSite.stages.site_ready,'Shop ready');
 assert.match(SME_MESSAGES.my.firstSite.stages.site_ready,/[\u1000-\u109F]/);
});
