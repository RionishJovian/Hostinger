import assert from 'node:assert/strict';
import {mkdtemp,readFile,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {build} from 'esbuild';
import {chromium} from 'playwright';

const repoRoot=new URL('../',import.meta.url);
const evidenceDir=process.env.MM_UI_EVIDENCE_DIR||'';
const launch={headless:process.env.MM_HEADLESS!=='false',...(process.env.MM_CHROME_PATH?{executablePath:process.env.MM_CHROME_PATH}:{})};
const temp=await mkdtemp(join(tmpdir(),'mikromagic-router-card-'));
const bundle=join(temp,'router-card.cjs');
const componentPath=fileURLToPath(new URL('src/NetworkRegistry.jsx',repoRoot));
const copyPath=fileURLToPath(new URL('src/sme-page-copy.mjs',repoRoot));

await build({
 stdin:{
  resolveDir:new URL('.',repoRoot).pathname,
  sourcefile:'router-card-acceptance.jsx',
  loader:'jsx',
  contents:`
   import React from 'react';
   import {renderToStaticMarkup} from 'react-dom/server';
   import {RouterCard} from ${JSON.stringify(componentPath)};
   import {SME_PAGE_COPY} from ${JSON.stringify(copyPath)};
   const noop=()=>{};
   const router={id:'router-acceptance',site_id:'site-acceptance',name:'Downtown Counter Router',model:'hAP ax2',reported_routeros:'7.16.2',architecture:'arm64',reported_serial:'TEST-SERIAL',connection_state:'connected',connection_verified:true,hub_id:'hub-acceptance'};
   const props={router,sites:[{id:'site-acceptance',name:'Downtown Shop'}],c:SME_PAGE_COPY.en.routersPage,act:async()=>null,api:{request:async()=>({})},busy:false,setupAvailable:true,onRefresh:noop,setPreflight:noop,setSync:noop,setSessions:noop,setHealth:noop,setWan:noop};
   module.exports=renderToStaticMarkup(<main><section className="panel"><h2>Your routers</h2><div className="router-cards"><RouterCard {...props}/></div></section></main>);
  `
 },
 bundle:true,
 platform:'node',
 format:'cjs',
 outfile:bundle,
 plugins:[{name:'ignore-css',setup(builder){builder.onLoad({filter:/\\.css$/},()=>({contents:'',loader:'js'}));}}],
 logLevel:'silent'
});

const [{default:markup},baseCss,localizationCss,hubCss]=await Promise.all([
 import(pathToFileURL(bundle).href),
 readFile(new URL('src/styles.css',repoRoot),'utf8'),
 readFile(new URL('src/sme-localization.css',repoRoot),'utf8'),
 readFile(new URL('src/magic-hub-connect.css',repoRoot),'utf8')
]);

const html=`<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"><style>:root{--background:#f4f0e6;--surface:#fffaf0;--text:#173b2d;--primary:#176b4d;--accent:#d8b95f}${baseCss}\n${localizationCss}\n${hubCss}</style></head><body><div class="app">${markup}</div></body></html>`;
const results=[];
const browser=await chromium.launch(launch);
try{
 for(const viewport of [{width:375,height:812},{width:430,height:932}]){
  const page=await browser.newPage({viewport,isMobile:true,hasTouch:true});
  await page.setContent(html,{waitUntil:'domcontentloaded'});
  await page.locator('.router-card').waitFor();
  const primary=page.locator('.router-primary-action .button');
  await primary.waitFor();
  assert.match((await primary.textContent())?.trim()||'',/^(?:Connect|Reconnect) with Magic Hub$/,`${viewport.width}px: primary Magic Hub action missing`);
  assert.equal(await page.locator('table').count(),0,`${viewport.width}px: owner router card rendered a table`);
  await page.locator('details.router-card-more summary').click();
  const measurement=await page.evaluate(()=>{
   const visible=element=>{const style=getComputedStyle(element),box=element.getBoundingClientRect();return style.display!=='none'&&style.visibility!=='hidden'&&box.width>0&&box.height>0};
   const label=element=>(element.innerText||element.getAttribute('aria-label')||element.tagName).trim().replace(/\s+/g,' ').slice(0,100);
   const targets=[...document.querySelectorAll('button:not(:disabled),summary')].filter(visible).map(element=>{const box=element.getBoundingClientRect();return{label:label(element),width:Number(box.width.toFixed(1)),height:Number(box.height.toFixed(1))}});
   const secondary=[...document.querySelectorAll('small,.muted,.pill,dt,.router-card-label')].filter(visible).map(element=>({label:label(element),font_px:parseFloat(getComputedStyle(element).fontSize)}));
   return{
    viewport:{width:innerWidth,height:innerHeight},
    horizontal_overflow:document.documentElement.scrollWidth>innerWidth||document.body.scrollWidth>innerWidth,
    undersized_targets:targets.filter(item=>item.width<44||item.height<44),
    sub_14px_secondary:secondary.filter(item=>item.font_px<14),
    operational_action_count:document.querySelectorAll('.router-operational-actions .button').length
   };
  });
  assert.equal(measurement.horizontal_overflow,false,`${viewport.width}px: page has horizontal overflow`);
  assert.deepEqual(measurement.undersized_targets,[],`${viewport.width}px: touch target below 44x44px`);
  assert.deepEqual(measurement.sub_14px_secondary,[],`${viewport.width}px: secondary text below 14px`);
  assert.equal(measurement.operational_action_count,5,`${viewport.width}px: secondary router actions missing`);
  if(evidenceDir)await page.screenshot({path:`${evidenceDir}/local-router-card-${viewport.width}.png`,fullPage:true});
  results.push(measurement);
  await page.close();
 }
 console.log(JSON.stringify({status:'PASS',results},null,2));
}finally{
 await browser.close();
 await rm(temp,{recursive:true,force:true});
}
