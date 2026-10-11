import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {SME_MESSAGES} from '../src/sme-localization.mjs';

const backend=readFileSync(new URL('../backend/notifications.py',import.meta.url),'utf8');
const kinds=new Set([...backend.matchAll(/entry\([^,]+,[^,]+,'([a-z_]+)'/g)].map(m=>m[1]).filter(k=>!k.endsWith('_')));
for(const m of backend.matchAll(/'(maintenance_[a-z]+)'/g))kinds.add(m[1]);
for(const m of backend.matchAll(/'change_'\+x\.status/g))['change_recovery_required','change_conflict'].forEach(k=>kinds.add(k));

test('every backend notification kind, scope and summary reason has English and Burmese text',()=>{
 assert.ok(kinds.size>=8,[...kinds].join());
 for(const lang of ['en','my']){
  const n=SME_MESSAGES[lang].notifications;
  assert.deepEqual(Object.keys(n).sort(),Object.keys(SME_MESSAGES.en.notifications).sort());
  for(const k of kinds){assert.equal(typeof n.kinds[k],'function',lang+' '+k);assert.ok(n.kinds[k]({site:'S',scope:'W',router:'R',time:'T',expires_on:'2026-10-20',days_left:3},2).length>5)}
  for(const s of ['control_plane','gateway','wan','switch','access_point','dns_portal','dependency'])assert.ok(n.scopes[s],lang+' '+s);
  for(const r of ['incidents_started','critical_outstanding','refunds_recorded'])assert.ok(n.reasons[r],lang+' '+r);
  assert.ok(SME_MESSAGES[lang].navigation.Notifications);
 }
});

test('the summary never labels redeemed vouchers as sold and names unmeasured router facts',()=>{
 assert.match(SME_MESSAGES.en.notifications.redeemedNote,/not the same as sold/);
 assert.match(SME_MESSAGES.en.notifications.notMeasured,/peak customers.*internet availability.*access point health/);
 assert.match(SME_MESSAGES.en.notifications.inApp,/not connected yet/);
});
