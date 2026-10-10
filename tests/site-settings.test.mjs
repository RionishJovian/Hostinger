import test from 'node:test';
import assert from 'node:assert/strict';
import {shopSsid,ssidBytes,ssidForSite,ssidProblem} from '../src/site-settings.mjs';
import {voucherSheet} from '../src/voucher-stock.mjs';

const sites=[{id:'a',name:'Main',printed_ssid:'Golden Cafe WiFi'},{id:'b',name:'Branch',printed_ssid:null}];

test('printed Wi-Fi names are limited to 32 bytes, counting Burmese letters correctly',()=>{
 assert.equal(ssidProblem(''),'');
 assert.equal(ssidProblem('x'.repeat(32)),'');
 assert.match(ssidProblem('x'.repeat(33)),/32 bytes \(this one is 33\)/);
 assert.equal(ssidBytes('ရွှေ'),12);
 assert.equal(ssidProblem('ရွှေ'.repeat(2)),'');
 assert.match(ssidProblem('ရွှေ'.repeat(3)),/Burmese/);
 assert.match(ssidProblem('bad\nname'),/control characters/);
});

test('shop default fills the print run only when the owner has not typed a name',()=>{
 assert.equal(shopSsid(sites,'a'),'Golden Cafe WiFi');
 assert.equal(shopSsid(sites,''),'');
 assert.equal(ssidForSite('',sites,'','a'),'Golden Cafe WiFi');
 assert.equal(ssidForSite('Golden Cafe WiFi',sites,'a','b'),'');
 assert.equal(ssidForSite('Golden Cafe WiFi',sites,'a',''),'');
 assert.equal(ssidForSite('Typed Name',sites,'','a'),'Typed Name');
});

test('batch sheet prints the shop Wi-Fi name, escaped, and nothing for business-wide cards',()=>{
 const voucher={id:'v1',code:'CAFE-ABC123',expires:2e9,policy:{name:'1 Day',service:'internet',mode:'both',price:1500}};
 const withSsid=voucherSheet([{...voucher,site_id:'a'}],'Golden Cafe',[{id:'a',name:'Main',printed_ssid:'<b>Cafe</b>'}]);
 assert.match(withSsid,/Wi-Fi: &lt;b&gt;Cafe&lt;\/b&gt;/);
 assert.doesNotMatch(voucherSheet([{...voucher,site_id:null}],'Golden Cafe',sites),/Wi-Fi:/);
});
