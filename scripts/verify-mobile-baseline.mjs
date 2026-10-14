import assert from 'node:assert/strict';
import {mkdir,writeFile} from 'node:fs/promises';
import {chromium} from 'playwright';

const origin=(process.env.MM_UI_ORIGIN||'http://127.0.0.1:5173').replace(/\/$/,'');
const evidenceDir=process.env.MM_UI_EVIDENCE_DIR||'';
const launch={headless:true,...(process.env.MM_CHROME_PATH?{executablePath:process.env.MM_CHROME_PATH}:{})};
const viewports=[{width:375,height:812},{width:430,height:932}];
const result={origin,viewports:[],source_sha:process.env.MM_SOURCE_SHA||null};

async function measure(page,name){
 const data=await page.evaluate(()=>{
  const visible=element=>{const style=getComputedStyle(element),box=element.getBoundingClientRect();return style.display!=='none'&&style.visibility!=='hidden'&&box.width>0&&box.height>0};
  const label=element=>(element.innerText||element.getAttribute('aria-label')||element.tagName).trim().replace(/\s+/g,' ').slice(0,100);
  const targets=[...document.querySelectorAll('button:not(:disabled),a[href],input:not(:disabled),select:not(:disabled),textarea:not(:disabled),summary')].filter(visible).map(element=>{const box=element.getBoundingClientRect();return{label:label(element),tag:element.tagName,width:Number(box.width.toFixed(1)),height:Number(box.height.toFixed(1))}});
  const fields=[...document.querySelectorAll('input,select,textarea')].filter(visible).map(element=>({label:label(element),tag:element.tagName,font_px:parseFloat(getComputedStyle(element).fontSize)}));
  const bodyText=[...document.querySelectorAll('p,li,dd,td,.actionrows span,.notice')].filter(element=>visible(element)&&!element.matches('.muted,.pill')).map(element=>({label:label(element),tag:element.tagName,font_px:parseFloat(getComputedStyle(element).fontSize)}));
  const secondary=[...document.querySelectorAll('small,.muted,.pill,dt,th,.field>span')].filter(visible).map(element=>({label:label(element),tag:element.tagName,font_px:parseFloat(getComputedStyle(element).fontSize)}));
  return{
   viewport:{width:innerWidth,height:innerHeight},
   document_scroll_width:document.documentElement.scrollWidth,
   body_scroll_width:document.body.scrollWidth,
   horizontal_overflow:document.documentElement.scrollWidth>innerWidth||document.body.scrollWidth>innerWidth,
   undersized_targets:targets.filter(item=>item.width<44||item.height<44),
   sub_16px_fields:fields.filter(item=>item.font_px<16),
   sub_16px_body_text:bodyText.filter(item=>item.font_px<16),
   sub_14px_secondary:secondary.filter(item=>item.font_px<14),
  };
 });
 if(evidenceDir)await page.screenshot({path:`${evidenceDir}/${data.viewport.width}-${name}.png`,fullPage:true});
 return{name,...data};
}

function assertState(state){
 assert.equal(state.horizontal_overflow,false,`${state.name}: page has horizontal overflow`);
 assert.deepEqual(state.undersized_targets,[],`${state.name}: touch target below 44x44px`);
 assert.deepEqual(state.sub_16px_fields,[],`${state.name}: form control below 16px`);
 assert.deepEqual(state.sub_16px_body_text,[],`${state.name}: body text below 16px`);
 assert.deepEqual(state.sub_14px_secondary,[],`${state.name}: secondary text below 14px`);
}

if(evidenceDir)await mkdir(evidenceDir,{recursive:true});
const browser=await chromium.launch(launch);
try{
 for(const viewport of viewports){
  const context=await browser.newContext({viewport,deviceScaleFactor:1,isMobile:true,hasTouch:true});
  const page=await context.newPage();
  await page.goto(origin+'/?demo=1',{waitUntil:'domcontentloaded',timeout:45000});
  await page.locator('.demo-banner').waitFor();
  const states=[];
  states.push(await measure(page,'my-light-overview'));
  await page.getByRole('button',{name:'English',exact:true}).click();
  states.push(await measure(page,'en-light-overview'));
  await page.locator('button.iconbutton').first().click();
  await page.locator('button.mobilemenu').click();
  await page.getByRole('button',{name:'Routers',exact:true}).click();
  await page.locator('#router-list').waitFor();
  states.push(await measure(page,'en-dark-routers'));
  await page.getByRole('button',{name:'မြန်မာ',exact:true}).click();
  states.push(await measure(page,'my-dark-routers'));
  result.viewports.push({viewport,states});
  states.forEach(assertState);
  await context.close();
 }
 result.status='PASS';
}catch(error){
 result.status='FAIL';
 result.failure=error instanceof Error?error.message.split('\n')[0]:String(error);
 process.exitCode=1;
}finally{
 await browser.close();
 const output=JSON.stringify(result,null,2)+'\n';
 if(evidenceDir)await writeFile(`${evidenceDir}/mobile-baseline.json`,output);
 console.log(output);
}
