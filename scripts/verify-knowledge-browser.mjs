#!/usr/bin/env node
/** Headless Chrome walkthrough of demo Did you know? (G05/G06). */
import {spawn} from 'node:child_process';
import {mkdir,writeFile} from 'node:fs/promises';
import assert from 'node:assert/strict';

const BASE=process.env.MM_UI_BASE||'http://127.0.0.1:5173';
const outDir='/opt/cursor/artifacts';
await mkdir(outDir,{recursive:true});

const chrome=process.env.CHROME_PATH||'/usr/local/bin/google-chrome';
const script=`
const puppeteer = await import('data:text/javascript,export default null').catch(()=>null);
`;

// Prefer CDP via chrome --headless=new --dump-dom is too weak; use chrome remote debugging + fetch protocol.
const port=9229+Math.floor(Math.random()*200);
const userData=`/tmp/mm-chrome-g05-${process.pid}`;
const child=spawn(chrome,[
 '--headless=new','--disable-gpu','--no-sandbox','--disable-dev-shm-usage',
 `--remote-debugging-port=${port}`,`--user-data-dir=${userData}`,
 `${BASE}/?demo=1`
],{stdio:['ignore','pipe','pipe']});

async function waitReady(ms=20000){
 const start=Date.now();
 while(Date.now()-start<ms){
  try{
   const res=await fetch(`http://127.0.0.1:${port}/json/version`);
   if(res.ok)return await res.json();
  }catch{}
  await new Promise(r=>setTimeout(r,200));
 }
 throw new Error('Chrome debug port did not open');
}

function wsUrlFrom(list){
 const page=list.find(t=>t.type==='page'&&/5173/.test(t.url))||list.find(t=>t.type==='page');
 if(!page?.webSocketDebuggerUrl)throw new Error('No page websocket');
 return page.webSocketDebuggerUrl;
}

class Cdp{
 constructor(url){this.url=url;this.id=0;this.pending=new Map();this.buf='';this.ws=null}
 async connect(){
  this.ws=new WebSocket(this.url);
  await new Promise((resolve,reject)=>{this.ws.addEventListener('open',resolve,{once:true});this.ws.addEventListener('error',reject,{once:true})});
  this.ws.addEventListener('message',ev=>{
   const msg=JSON.parse(String(ev.data));
   if(msg.id!=null&&this.pending.has(msg.id)){const {resolve,reject}=this.pending.get(msg.id);this.pending.delete(msg.id);msg.error?reject(new Error(JSON.stringify(msg.error))):resolve(msg.result)}
  });
 }
 send(method,params={}){
  const id=++this.id;
  return new Promise((resolve,reject)=>{
   this.pending.set(id,{resolve,reject});
   this.ws.send(JSON.stringify({id,method,params}));
  });
 }
 async eval(expression){
  const r=await this.send('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true});
  if(r.exceptionDetails)throw new Error(r.exceptionDetails.text||'eval failed');
  return r.result?.value;
 }
 async shot(path){
  const {data}=await this.send('Page.captureScreenshot',{format:'png'});
  await writeFile(path,Buffer.from(data,'base64'));
 }
 close(){try{this.ws?.close()}catch{};try{child.kill('SIGTERM')}catch{}}
}

try{
 await waitReady();
 // Give the SPA a moment, then attach to the page target.
 await new Promise(r=>setTimeout(r,1500));
 const targets=await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
 const cdp=new Cdp(wsUrlFrom(targets));
 await cdp.connect();
 await cdp.send('Page.enable');
 await cdp.send('Runtime.enable');
 // Wait for demo shell
 await cdp.eval(`new Promise(r=>{const t=setInterval(()=>{if(document.body?.innerText.includes('Golden Cafe')||document.querySelector('nav')){clearInterval(t);r(true)}},200);setTimeout(()=>{clearInterval(t);r(false)},15000)})`);
 // Navigate via UI: click Did you know / သိကောင်းစရာ
 const clicked=await cdp.eval(`(()=>{const b=[...document.querySelectorAll('nav button,button')].find(el=>/Did you know|သိကောင်းစရာ/i.test(el.textContent||''));if(!b)return false;b.click();return true})()`);
 assert.equal(clicked,true,'Did you know nav button missing');
 await new Promise(r=>setTimeout(r,800));
 const hasCards=await cdp.eval(`document.querySelectorAll('.knowledge-card').length`);
 assert.ok(hasCards>=2,`expected knowledge cards, got ${hasCards}`);
 await cdp.shot(`${outDir}/g05-did-you-know-cards.png`);

 // Search nonsense via React-friendly native value setter + InputEvent
 await cdp.eval(`(()=>{const input=document.querySelector('input[type=search]');const proto=Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value').set;proto.call(input,'zzzznoresult');input.dispatchEvent(new InputEvent('input',{bubbles:true,data:'zzzznoresult',inputType:'insertText'}));})()`);
 await new Promise(r=>setTimeout(r,400));
 const emptyVisible=await cdp.eval(`!!document.querySelector('.knowledge-empty') && document.querySelectorAll('.knowledge-card').length===0`);
 assert.equal(emptyVisible,true,'empty recovery not shown');
 await cdp.shot(`${outDir}/g05-did-you-know-empty.png`);

 const cleared=await cdp.eval(`(()=>{const b=[...document.querySelectorAll('button')].find(el=>/Clear search|ရှင်းရန်/i.test(el.textContent||''));if(!b)return false;b.click();return true})()`);
 assert.equal(cleared,true,'clear filters button missing');
 await new Promise(r=>setTimeout(r,400));
 assert.ok((await cdp.eval(`document.querySelectorAll('.knowledge-card').length`))>=2,'cards did not return after clear');

 await cdp.eval(`(()=>{const input=document.querySelector('input[type=search]');const proto=Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value').set;proto.call(input,'torch');input.dispatchEvent(new InputEvent('input',{bubbles:true,data:'torch',inputType:'insertText'}));})()`);
 await new Promise(r=>setTimeout(r,400));
 const torchCount=await cdp.eval(`document.querySelectorAll('.knowledge-card').length`);
 const torchTitle=await cdp.eval(`document.querySelector('.knowledge-card h2')?.textContent||''`);
 assert.equal(torchCount,1,'torch filter should leave one card');
 assert.match(torchTitle,/torch/i);
 await cdp.shot(`${outDir}/g05-did-you-know-torch.png`);

 await cdp.eval(`(()=>{const input=document.querySelector('input[type=search]');const proto=Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value').set;proto.call(input,'');input.dispatchEvent(new InputEvent('input',{bubbles:true,inputType:'deleteContentBackward'}));})()`);
 await new Promise(r=>setTimeout(r,300));
 await cdp.eval(`document.querySelector('.knowledge-card details summary')?.click()`);
 await new Promise(r=>setTimeout(r,300));
 const open=await cdp.eval(`!!document.querySelector('.knowledge-card details[open]')`);
 assert.equal(open,true,'details did not expand');
 const detailText=await cdp.eval(`document.querySelector('.knowledge-card details[open]')?.innerText||''`);
 assert.match(detailText,/Why it matters|အရေးကြီး|not checked|မစစ်ဆေး/i);
 await cdp.shot(`${outDir}/g05-did-you-know-expanded.png`);
 console.log('Did you know? browser checks passed: cards, empty recovery, torch filter, expandable details.');
 cdp.close();
 process.exit(0);
}catch(err){
 console.error(err);
 try{child.kill('SIGTERM')}catch{}
 process.exit(1);
}
