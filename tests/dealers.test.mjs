import test from 'node:test';
import assert from 'node:assert/strict';
import {balanceText,compressSerials,handoverPreview,movementDetail,parseSerials} from '../src/dealers.mjs';
import {productionSheets} from '../src/voucher-production.mjs';

test('missing serial lists accept ranges and reject unsafe input',()=>{
 assert.deepEqual(parseSerials('12-15, 20 9'),[9,12,13,14,15,20]);
 assert.deepEqual(parseSerials(''),[]);
 for(const bad of ['12-3','abc','0','1-1001','5;6'])assert.equal(parseSerials(bad),null,bad);
});

test('serials compress into readable ranges',()=>{
 assert.equal(compressSerials([3,1,2,8,10,9,20]),'000001–000003, 000008–000010, 000020');
 assert.equal(compressSerials([]),'');
});

test('balance wording never calls dealer stock a sale',()=>{
 assert.equal(balanceText(25000),'Owes 25,000 MMK');
 assert.equal(balanceText(-500),'Prepaid credit 500 MMK');
 assert.equal(balanceText(0),'Settled');
 assert.deepEqual(handoverPreview(10,'2500'),{count:10,charge:25000});
 assert.deepEqual(handoverPreview(10,'0'),{count:10,charge:0});
 assert.equal(handoverPreview(10,''),null);
 assert.equal(handoverPreview(0,'100'),null);
});

test('movement details explain handovers, returns and stock checks',()=>{
 const names=id=>({b:'Ma Hla'})[id];
 assert.equal(movementDetail({kind:'assign',unit_price:2500,details:{serials:'000001–000010',face_value:30000}}),'000001–000010 · 2,500 MMK each (face 30,000 MMK)');
 assert.equal(movementDetail({kind:'reassign_out',counterpart_dealer_id:'b',details:{serials:'000006–000007',credited:5000}},names),'000006–000007 · credited 5,000 MMK · to Ma Hla');
 assert.equal(movementDetail({kind:'stock_check',reason:'lost',details:{expected:5,counted:3,difference:-2,missing_serials:[9,10],disabled:2}}),'Expected 5 · counted 3 · difference -2 · Lost · missing 000009–000010 · 2 disabled');
});

test('dealer short code is marked on printed sheets',()=>{
 const job={ref:'PJ-0001',plan:{unit:'sheet',per_sheet:40,sheets:1},settings:{layout:'a4_economy',show_price:false},sheets:{}};
 const items=[{code:'ABCD-EF',serial_no:1,sheet_no:1,expires:1900000000,policy:{name:'Day'}}];
 assert.match(productionSheets({job,items,business:'Cafe',dealerCode:'KA'}),/Sheet 1\/1 · Serial 000001–000001 · Dealer KA/);
 assert.doesNotMatch(productionSheets({job,items,business:'Cafe'}),/Dealer/);
});
