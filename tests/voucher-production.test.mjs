import test from 'node:test';
import assert from 'node:assert/strict';
import {plan,paperSummary,serial,nextStep,loadPrintPrefs,savePrintPrefs,productionSheets,calibrationSheet,MAGIC_TEMPLATES,PRODUCTION_STEPS} from '../src/voucher-production.mjs';

test('layout plans match the backend sheet and run sizes',()=>{
 assert.deepEqual(plan({layout:'a4_ultra'},130),{unit:'sheet',per_sheet:60,sheets:3,last_sheet_count:10});
 assert.deepEqual(plan({layout:'thermal_58'},30),{unit:'run',per_sheet:25,sheets:2,last_sheet_count:5});
 assert.equal(plan({layout:'a4_custom',columns:8,rows:16},200).per_sheet,128);
 assert.equal(plan({layout:'a4_custom'},10),null);assert.equal(plan({layout:'a4_economy'},0),null);
 assert.match(paperSummary(plan({layout:'a4_economy'},41)),/2 A4 sheets · 40 per sheet · last sheet 1\/40/);
 assert.equal(serial(61),'000061');assert.equal(serial(null),'—');
});

test('flow and templates follow the frozen production order without business values',()=>{
 assert.deepEqual(PRODUCTION_STEPS,['Profile','Quantity','Coverage','Dealer','Print layout','Preview','Generate','Print','Verify','Distribute']);
 assert.equal(nextStep({status:'draft'}),'Generate');assert.equal(nextStep({status:'generated'}),'Verify');
 for(const t of MAGIC_TEMPLATES)for(const key of ['price','package_id','speed'])assert.ok(!(key in t.settings));
});

test('printer preferences are remembered without codes or packages',()=>{
 const store=new Map(),storage={getItem:k=>store.get(k)??null,setItem:(k,v)=>store.set(k,v)};
 savePrintPrefs({layout:'thermal_80',columns:null,rows:null,show_price:false,ssid:'Cafe',package_id:'p',quantity:5},storage);
 assert.deepEqual(loadPrintPrefs(storage),{layout:'thermal_80',columns:null,rows:null,show_price:false,ssid:'Cafe'});
 assert.deepEqual(loadPrintPrefs({getItem:()=>'{broken'}),{});
});

const job={ref:'PJ-0007',plan:{unit:'sheet',per_sheet:2,sheets:2,last_sheet_count:1},settings:{layout:'a4_custom',columns:2,rows:1,show_price:true,ssid:'Cafe <WiFi>'},sheets:{1:{state:'printed',reprints:0},2:{state:'failed',reprints:1}}};
const items=[1,2,3].map(n=>({code:'CAFE-AB'+n,serial_no:n,sheet_no:n<3?1:2,expires:1800000000,policy:{name:'Day Pass',price:1000}}));

test('sheets carry batch, sheet and serial identity and escape text',()=>{
 const html=productionSheets({job,items,business:'Golden <Cafe>'});
 assert.match(html,/Batch PJ-0007 · Sheet 1\/2 · Serial 000001–000002/);assert.match(html,/Sheet 2\/2 · Serial 000003–000003/);
 assert.match(html,/Golden &lt;Cafe&gt;/);assert.match(html,/Cafe &lt;WiFi&gt;/);assert.doesNotMatch(html,/<WiFi>/);
 assert.match(html,/1000 MMK/);assert.match(html,/Guest QR codes on vouchers are off/);assert.doesNotMatch(html,/class="page withqr"|opens this batch/);
 const reprint=productionSheets({job,items,business:'Cafe',only:[2],reprint:true});
 assert.doesNotMatch(reprint,/CAFE-AB1/);assert.match(reprint,/CAFE-AB3/);assert.match(reprint,/REPRINT 1/);assert.match(reprint,/destroy the failed copies/);
 const thermal=productionSheets({job:{...job,settings:{layout:'thermal_58',show_price:false},plan:{unit:'run',per_sheet:25,sheets:1,last_sheet_count:3}},items:items.map(v=>({...v,sheet_no:1})),business:'Cafe'});
 assert.match(thermal,/Print run PJ-0007-R1 · 1\/1 · Seq 000001–000003/);assert.match(thermal,/size:58mm auto/);assert.doesNotMatch(thermal,/MMK/);
});

test('calibration page uses sample cards that can never be redeemed',()=>{
 const html=calibrationSheet({settings:{layout:'a4_ultra'},business:'Cafe'});
 assert.equal((html.match(/NOT·A·CODE/g)||[]).length,60);assert.match(html,/should measure 100 mm/);
 assert.doesNotMatch('NOT·A·CODE'.replace(/[\s-]+/g,''),/^[A-Z0-9]{6,40}$/);
 assert.match(calibrationSheet({settings:{layout:'thermal_80'},business:'Cafe'}),/should measure 40 mm/);
});

test('batch QR sits in the sheet or run header only when one was generated',()=>{
 const svg='<svg data-test="qr"></svg>';
 const html=productionSheets({job,items,business:'Cafe',qr:{1:svg}});
 assert.equal((html.match(/data-test="qr"/g)||[]).length,1);assert.match(html,/class="page withqr"/);assert.match(html,/sign-in required/);assert.match(html,/opens this batch in MikroMagic for the signed-in owner only/);
 const thermal=productionSheets({job:{...job,settings:{layout:'thermal_58'},plan:{unit:'run',per_sheet:25,sheets:1,last_sheet_count:3}},items:items.map(v=>({...v,sheet_no:1})),business:'Cafe',qr:{1:svg}});
 assert.match(thermal,/class="runqr"><svg data-test="qr">/);
 assert.match(calibrationSheet({settings:{layout:'a4_economy'},business:'Cafe'}),/class="page withqr"[\s\S]*batch QR/);
 assert.doesNotMatch(calibrationSheet({settings:{layout:'a4_economy',batch_qr:false},business:'Cafe'}),/class="page withqr"|>batch QR</);
});

