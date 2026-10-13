#!/usr/bin/env node
/** Open the Lantern Leaf guest-page preview in headless Chrome and capture each page. */
import {spawn} from 'node:child_process';
import {mkdir,writeFile} from 'node:fs/promises';
import assert from 'node:assert/strict';
import {previewHotspotPages,GUEST_PREVIEW_PAGE_IDS} from '../src/lantern-leaf-preview.mjs';

const outDir='/opt/cursor/artifacts';
const folder='.ui-check';
await mkdir(outDir,{recursive:true});
await mkdir(folder,{recursive:true});

const settings={
 business_name:'Golden Cafe (demo)',
 welcome:'Welcome to Golden Cafe Wi-Fi.',
 language:'both',
 terms:'Please share the Wi-Fi fairly.',
 direct_purchase:true,
 payment_destination:'KBZPay 09-000 000 000 (sample)',
 payment_instructions:'Send the exact amount, then enter the transaction ID.',
 payment_methods:['Cash at counter','KBZPay','WavePay']
};
const pages=previewHotspotPages(settings);
const html=`<!doctype html><html lang="my"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Guest page preview</title>
<style>
 body{margin:0;background:#f0ece2;color:#16382b;font:16px/1.45 "Noto Sans Myanmar",system-ui,sans-serif}
 main{max-width:420px;margin:0 auto;padding:16px}
 h1{font-size:22px;margin:0 0 8px}
 p{margin:0 0 12px}
 .guest-preview-pages{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 12px}
 button{min-height:44px;border-radius:12px;border:1px solid #16382b33;background:#fff;padding:8px 12px;font:inherit}
 button[aria-selected="true"]{background:#145C45;color:#FBF4E4;border-color:#145C45}
 .guest-phone{width:min(100%,340px);height:640px;margin:0 auto;padding:10px;border-radius:36px;background:#12161f}
 iframe{display:block;width:100%;height:100%;border:0;border-radius:26px;background:#0A1210}
</style></head><body><main>
<h1>ဧည့်သည် စာမျက်နှာ ကြိုကြည့်</h1>
<p>ဤသည်မှာ router တွင် ဧည့်သည်မြင်ရမည့် HotSpot စာမျက်နှာ ဖြစ်ပါသည်။</p>
<div class="guest-preview-pages" role="tablist">${GUEST_PREVIEW_PAGE_IDS.map((id,i)=>`<button type="button" role="tab" data-page="${id}" aria-selected="${i===0?'true':'false'}">${{login:'ဝင်ရန်',connected:'ချိတ်ဆက်ပြီး',failed:'ချိတ်ဆက် မရပါ',status:'အခြေအနေ',signedOut:'ထွက်ပြီး'}[id]}</button>`).join('')}</div>
<div class="guest-phone"><iframe id="frame" title="Guest page preview · Login"></iframe></div>
<script>
const pages=${JSON.stringify(pages).replace(/</g,'\\u003c')};
const frame=document.getElementById('frame');
function show(id){
 frame.srcdoc=pages[id];
 document.querySelectorAll('[data-page]').forEach(b=>b.setAttribute('aria-selected',b.dataset.page===id?'true':'false'));
}
document.querySelectorAll('[data-page]').forEach(b=>b.addEventListener('click',()=>show(b.dataset.page)));
show('login');
</script></main></body></html>`;
await writeFile(folder+'/guest-page-preview.html',html);

const chrome=process.env.CHROME_PATH||'/usr/local/bin/google-chrome';
const port=9330+Math.floor(Math.random()*200);
const userData=`/tmp/mm-chrome-preview-${process.pid}`;
const child=spawn(chrome,[
 '--headless=new','--disable-gpu','--no-sandbox','--disable-dev-shm-usage',
 `--remote-debugging-port=${port}`,`--user-data-dir=${userData}`,
 '--window-size=390,900',
 `file://${process.cwd()}/${folder}/guest-page-preview.html`
],{stdio:['ignore','pipe','pipe']});

async function waitReady(ms=20000){
 const start=Date.now();
 while(Date.now()-start<ms){
  try{const res=await fetch(`http://127.0.0.1:${port}/json/version`);if(res.ok)return}catch{}
  await new Promise(r=>setTimeout(r,200));
 }
 throw new Error('Chrome debug port did not open');
}
class Cdp{
 constructor(url){this.url=url;this.id=0;this.pending=new Map();this.ws=null}
 async connect(){
  this.ws=new WebSocket(this.url);
  await new Promise((resolve,reject)=>{this.ws.addEventListener('open',resolve,{once:true});this.ws.addEventListener('error',reject,{once:true})});
  this.ws.addEventListener('message',ev=>{
   const msg=JSON.parse(String(ev.data));
   if(msg.id!=null&&this.pending.has(msg.id)){const {resolve,reject}=this.pending.get(msg.id);this.pending.delete(msg.id);msg.error?reject(new Error(JSON.stringify(msg.error))):resolve(msg.result)}
  });
 }
 send(method,params={}){const id=++this.id;return new Promise((resolve,reject)=>{this.pending.set(id,{resolve,reject});this.ws.send(JSON.stringify({id,method,params}))})}
 async eval(expression){
  const r=await this.send('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true});
  if(r.exceptionDetails)throw new Error(r.exceptionDetails.exception?.description||r.exceptionDetails.text||'eval failed');
  return r.result?.value;
 }
 async shot(path){const {data}=await this.send('Page.captureScreenshot',{format:'png'});await writeFile(path,Buffer.from(data,'base64'))}
 close(){try{this.ws?.close()}catch{}try{child.kill('SIGTERM')}catch{}}
}

try{
 await waitReady();
 await new Promise(r=>setTimeout(r,800));
 const targets=await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
 const page=targets.find(t=>t.type==='page');
 if(!page?.webSocketDebuggerUrl)throw new Error('No page websocket');
 const cdp=new Cdp(page.webSocketDebuggerUrl);
 await cdp.connect();
 await cdp.send('Page.enable');
 await cdp.send('Runtime.enable');
 await cdp.send('Emulation.setDeviceMetricsOverride',{width:390,height:900,deviceScaleFactor:2,mobile:true});
 async function frameText(){
  return cdp.eval(`(async()=>{const frame=document.getElementById('frame');for(let i=0;i<20;i++){const doc=frame.contentDocument;if(doc&&doc.body&&doc.body.innerText.trim())return doc.body.innerText;await new Promise(r=>setTimeout(r,100))}return ''})()`);
 }
 const probe=await cdp.eval(`(()=>{const frame=document.getElementById('frame');return {ready:document.readyState,buttons:document.querySelectorAll('[data-page]').length,srcLen:(frame&&frame.srcdoc||'').length,title:document.title,text:(document.body.innerText||'').slice(0,180)}})()`);
 if(!probe?.srcLen)throw new Error('Preview frame was not filled: '+JSON.stringify(probe));
 const loginText=await frameText();
 assert.match(loginText,/Golden Cafe/);
 assert.match(loginText,/ချိတ်ဆက်ရန်/);
 assert.match(loginText,/KBZPay/);
 await cdp.shot(`${outDir}/guest-preview-login.png`);
 await cdp.eval(`document.querySelector('[data-page="failed"]').click()`);
 await new Promise(r=>setTimeout(r,400));
 const failedText=await frameText();
 assert.match(failedText,/ကုဒ် မှားနေပါသည်|Wrong code/);
 await cdp.shot(`${outDir}/guest-preview-failed.png`);
 await cdp.eval(`document.querySelector('[data-page="status"]').click()`);
 await new Promise(r=>setTimeout(r,300));
 const statusText=await frameText();
 assert.match(statusText,/1h12m/);
 assert.match(statusText,/800\.0MiB/);
 await cdp.shot(`${outDir}/guest-preview-status.png`);
 await cdp.eval(`document.querySelector('[data-page="connected"]').click()`);
 await new Promise(r=>setTimeout(r,300));
 assert.match(await frameText(),/အင်တာနက် သုံးနိုင်ပါပြီ|You are connected/);
 await cdp.shot(`${outDir}/guest-preview-connected.png`);
 cdp.close();
 console.log('Guest page preview shows login, connected, failed and status pages.');
}finally{
 try{child.kill('SIGTERM')}catch{}
}
