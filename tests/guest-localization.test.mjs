import test from 'node:test';
import assert from 'node:assert/strict';
import {GUEST_MESSAGES,getGuestMessage,normalizeGuestLanguage,persistGuestLanguage,readGuestLanguage} from '../src/guest-localization.mjs';

test('guest language defaults to Myanmar',()=>{
 assert.equal(normalizeGuestLanguage('xx'),'my');
 assert.equal(normalizeGuestLanguage('en'),'en');
 assert.equal(getGuestMessage('my','entry','createAccount'),'ဧည့်သည် အကောင့် ဖန်တီးရန်');
 assert.equal(getGuestMessage('en','entry','createAccount'),'Create guest account');
});

test('guest messages cover entry purchase redeem access',()=>{
 for(const lang of ['en','my']){
  for(const section of ['entry','purchase','redeem','access','nav','shell']){
   assert.ok(GUEST_MESSAGES[lang][section],`${lang}.${section}`);
  }
  assert.match(String(getGuestMessage(lang,'entry','eyebrow')('Shop')),/Shop|ဆိုင်|ဧည့်သည်/);
 }
});

test('guest language persistence uses provided storage',()=>{
 const store=new Map();
 const storage={getItem:k=>store.has(k)?store.get(k):null,setItem:(k,v)=>store.set(k,v)};
 assert.equal(persistGuestLanguage('en',storage),'en');
 assert.equal(readGuestLanguage(storage),'en');
 assert.equal(persistGuestLanguage('nope',storage),'my');
 assert.equal(readGuestLanguage(storage),'my');
});
