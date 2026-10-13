import {build} from 'esbuild';
import {mkdir,writeFile,readFile,rm} from 'node:fs/promises';
import assert from 'node:assert/strict';
await mkdir('.ui-check',{recursive:true});
try{
 const bundle=await build({entryPoints:['src/GuestEntry.jsx'],bundle:true,platform:'node',format:'esm',external:['react'],write:false});await writeFile('.ui-check/guest-entry.mjs',bundle.outputFiles[0].text);
 const {default:GuestEntry}=await import('../.ui-check/guest-entry.mjs');const React=await import('react');const {renderToStaticMarkup}=await import('react-dom/server');
 const portal={site_name:'Sample cafe / Main branch',revision:1,settings:{business_name:'Golden Cafe',welcome:'Wi-Fi and movie passes for your visit.',contact:'Ask our counter for payment assistance.',terms:'Review your package limits before paying.'},packages:[{id:'sample',policy:{name:'Internet + movies',price:3000,service:'combined',mode:'both'}}]};
 const myHtml=renderToStaticMarkup(React.createElement(GuestEntry,{portal,busy:true,language:'my',onRegister:()=>{},onLogin:()=>{}}));
 assert.match(myHtml,/ဧည့်သည် အကောင့် ဖန်တီးရန်/);
 assert.match(myHtml,/ထုတ်ပြန်ထားသော စည်းမျဉ်းများ/);
 assert.match(myHtml,/new-password/);
 assert.match(myHtml,/disabled=""/);
 assert.match(myHtml,/aria-pressed="true"/);
 assert.doesNotMatch(myHtml,/role selector/);
 const enHtml=renderToStaticMarkup(React.createElement(GuestEntry,{portal,busy:false,language:'en',onRegister:()=>{},onLogin:()=>{}}));
 assert.match(enHtml,/Create guest account/);
 assert.match(enHtml,/published terms/);
 const css=await readFile('src/styles.css','utf8');await writeFile('.ui-check/Guest-onboarding-preview.html',`<!doctype html><html lang="my"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>MikroMagic guest onboarding</title><style>${css}body{padding:24px}main{max-width:900px;margin:auto}fieldset{border:0;padding:0}.langs{display:flex;gap:.5rem;margin:0 0 1rem}</style><body><main><h1>Guest portal (Burmese first).</h1><p>Static preview of the implemented component. Sample data and disabled controls.</p><fieldset disabled>${myHtml}</fieldset></main></body></html>`);console.log('Guest onboarding UI checks passed.');
}finally{await rm('.ui-check/guest-entry.mjs',{force:true})}
