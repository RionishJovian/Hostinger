import test from 'node:test';
import assert from 'node:assert/strict';
import {reportText,reportFileName,shopTime,firstSentence} from '../src/support-report.mjs';

const report={generated:1791700000,business:'Golden Cafe',shop:{name:'Golden Downtown',timezone:'Asia/Yangon'},description:'Guest code [voucher code removed] fails',
 now:{business:'closed',network:'off',maintenance_until:1791701800,maintenance_reason:'Moving AP'},
 routers:[{name:'Front router',model:'hAP ax2',reported_routeros:'7.16',connection:'not_verified',magic_hub_assigned:false,management_locked:false}],
 devices:[{name:'Kitchen AP',kind:'access_point',vendor:'MikroTik',model:'cAP ax',location:'Kitchen',last_seen:null}],
 outages:[{scope:'wan',ongoing:true,duration:'1h 30m',started:1791694600,expected:null,symptoms:'No internet',suspected_cause:'ISP outage',confirmed_cause:null},
  {scope:'access_point',ongoing:false,duration:'45m',started:1791690000,expected:'maintenance',symptoms:'AP down',confirmed_cause:'Unplugged',suspected_cause:null}],
 recent_events:[{at:1791699000,action:'site_maintenance_started'}],
 likely_causes:[{text:'No router has a verified connection to MikroMagic.',evidence:'No verified Magic Hub handshake on record'}],
 excluded:'Passwords, voucher codes, API credentials, WireGuard keys, router addresses and payment details are never included.'};

test('help report text covers every section in shop time and labels evidence',()=>{
 const text=reportText(report);
 for(const part of ['Business: Golden Cafe','Shop: Golden Downtown (Asia/Yangon)','Guest code [voucher code removed] fails',
  '- No router has a verified connection to MikroMagic. [based on: No verified Magic Hub handshake on record]',
  '- Closed now; network planned off','Planned maintenance until','(Moving AP)',
  '- Front router: hAP ax2, RouterOS 7.16; No verified connection to MikroMagic',
  '- Kitchen AP (access point): MikroTik cAP ax, Kitchen; last seen never reported',
  '- Internet (WAN): ongoing for 1h 30m','Suspected (not confirmed): ISP outage.','- Access point: lasted 45m','(expected: maintenance)','Confirmed cause: Unplugged.',
  'site maintenance started','never included'])assert.ok(text.includes(part),part);
 assert.doesNotMatch(text,/undefined|null|NaN/);
 assert.equal(shopTime(1791700000,'Asia/Yangon'),new Date(1791700000*1000).toLocaleString('en-GB',{timeZone:'Asia/Yangon',day:'numeric',month:'short',year:'numeric',hour:'2-digit',minute:'2-digit'}));
});

test('empty sections read clearly and the file name is safe',()=>{
 const text=reportText({...report,description:'',routers:[],devices:[],outages:[],recent_events:[],now:{business:'not_set',network:'on'}});
 for(const part of ['(nothing written)','- None registered','- None recorded','- Business hours not set; network planned on'])assert.ok(text.includes(part),part);
 assert.doesNotMatch(text,/Planned maintenance until/);
 assert.match(reportFileName(report),/^mikromagic-help-golden-downtown-\d{12}\.txt$/);
 assert.match(reportFileName({...report,shop:{name:'မြို့လယ်',timezone:'Asia/Yangon'}}),/^mikromagic-help-shop-\d{12}\.txt$/);
});

test('report lists show only the first clause of the likely cause',()=>{
 assert.equal(firstSentence('No router has a verified connection to MikroMagic, so device status cannot be checked.'),'No router has a verified connection to MikroMagic…');
 assert.equal(firstSentence('Planned maintenance is running. Outages are expected.'),'Planned maintenance is running.');
 assert.equal(firstSentence('Internet (WAN) outage ongoing for 1h 15m; suspected (not confirmed): ISP outage.'),'Internet (WAN) outage ongoing for 1h 15m…');
 assert.equal(firstSentence(undefined),'');
});
