import test from 'node:test';
import assert from 'node:assert/strict';
import {getSmeMessage,LEGACY_OVERVIEW_LANGUAGE_STORAGE_KEY,persistSmeLanguage,readSmeLanguage,SME_LANGUAGE_STORAGE_KEY} from '../src/sme-localization.mjs';

function storage(values={}){
 const data=new Map(Object.entries(values));
 return {getItem:key=>data.get(key)??null,setItem:(key,value)=>data.set(key,String(value)),data};
}

test('SME language defaults to Burmese and reads the previous Overview preference',()=>{
 assert.equal(readSmeLanguage(storage()),'my');
 assert.equal(readSmeLanguage(storage({[LEGACY_OVERVIEW_LANGUAGE_STORAGE_KEY]:'en'})),'en');
 assert.equal(readSmeLanguage(storage({[SME_LANGUAGE_STORAGE_KEY]:'my',[LEGACY_OVERVIEW_LANGUAGE_STORAGE_KEY]:'en'})),'my');
});

test('language selection persists in shared and legacy preference keys',()=>{
 const local=storage();
 assert.equal(persistSmeLanguage('en',local),'en');
 assert.equal(local.data.get(SME_LANGUAGE_STORAGE_KEY),'en');
 assert.equal(local.data.get(LEGACY_OVERVIEW_LANGUAGE_STORAGE_KEY),'en');
 assert.equal(persistSmeLanguage('xx',local),'my');
});

test('message lookup supports navigation and Overview in both locales with English fallback',()=>{
 assert.equal(getSmeMessage('my','navigation','Overview'),'အနှစ်ချုပ်');
 assert.equal(getSmeMessage('en','navigation','Overview'),'Overview');
 assert.equal(getSmeMessage('my','overview','question'),'လုပ်ငန်း၏ Wi-Fi အလုပ်လုပ်နေပါသလား။');
 assert.equal(getSmeMessage('my','navigation','Unknown page'),'Unknown page');
});
