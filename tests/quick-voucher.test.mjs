import {test} from 'node:test';
import assert from 'node:assert/strict';
import {prioritizePackages} from '../src/quick-voucher.mjs';

test('Quick Voucher ranks tenant-provided packages by existing voucher frequency then recency',()=>{
 const packages=[{id:'new',name:'New'},{id:'popular',name:'Popular'},{id:'recent',name:'Recent'}];
 const vouchers=[
  {package_id:'popular',created:10},{package_id:'popular',created:20},
  {package_id:'recent',created:30},
 ];
 assert.deepEqual(prioritizePackages(packages,vouchers).map(p=>p.id),['popular','recent','new']);
});

test('Quick Voucher preserves package ordering when history is empty',()=>{
 const packages=[{id:'a'},{id:'b'}];
 assert.deepEqual(prioritizePackages(packages,[]).map(p=>p.id),['a','b']);
});

test('vouchers without package identifiers do not affect package ranking',()=>{
 const packages=[{id:'a'},{id:'b'}];
 assert.deepEqual(prioritizePackages(packages,[{created:99}]).map(p=>p.id),['a','b']);
});
