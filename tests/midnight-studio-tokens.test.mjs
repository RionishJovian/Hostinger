import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {mkdir,writeFile,rm} from 'node:fs/promises';
import {build} from 'esbuild';
import {execFileSync} from 'node:child_process';

test('G01 Midnight Studio dark default and contrast align frontend with backend',async()=>{
 const dir='.ui-check-g01';
 await mkdir(dir,{recursive:true});
 try{
  const bundle=await build({entryPoints:['src/AppearanceSettings.jsx'],bundle:true,platform:'node',format:'esm',external:['react'],write:false});
  await writeFile(`${dir}/appearance.mjs`,bundle.outputFiles[0].text);
  const {DEFAULT_THEMES,MIDNIGHT_STUDIO_DARK,contrastChecks}=await import(`../${dir}/appearance.mjs`);
  assert.deepEqual(MIDNIGHT_STUDIO_DARK,{
   background:'#12161f',surface:'#1c2333',text:'#ebe7df',primary:'#34d399',accent:'#456658',
  });
  assert.deepEqual(DEFAULT_THEMES.dark,MIDNIGHT_STUDIO_DARK);
  assert.equal(DEFAULT_THEMES.light.background,'#f0ece2');
  const checks=contrastChecks(DEFAULT_THEMES);
  assert.equal(checks.length,20);
  assert.ok(checks.every(c=>c.passes),JSON.stringify(checks.filter(c=>!c.passes)));
  const backend=JSON.parse(execFileSync('.venv/bin/python',['-c','import json;from backend.appearance import DEFAULT,contrast_checks;print(json.dumps({"dark":DEFAULT["dark"],"checks":contrast_checks(DEFAULT)}))'],{encoding:'utf8'}));
  assert.deepEqual(backend.dark,MIDNIGHT_STUDIO_DARK);
  checks.forEach((c,i)=>{
   assert.equal(c.mode,backend.checks[i].mode);
   assert.equal(c.passes,backend.checks[i].passes);
  });
 }finally{
  await rm(dir,{recursive:true,force:true});
 }
});

test('G01 styles carry Midnight Studio token and motion foundations',()=>{
 const css=readFileSync(new URL('../src/styles.css',import.meta.url),'utf8');
 assert.match(css,/G01 Midnight Studio tokens/);
 assert.match(css,/--mm-glass/);
 assert.match(css,/--mm-blur/);
 assert.match(css,/prefers-reduced-motion:reduce/);
 assert.match(css,/Noto Sans Myanmar/);
 assert.doesNotMatch(css,/font-family:Inter/);
 const loc=readFileSync(new URL('../src/sme-localization.css',import.meta.url),'utf8');
 assert.match(loc,/workspace-language\{background:var\(--mm-glass/);
});

test('G02 responsive shell foundations are present',()=>{
 const css=readFileSync(new URL('../src/styles.css',import.meta.url),'utf8');
 assert.match(css,/G02 responsive shell/);
 assert.match(css,/overflow-x:clip/);
 assert.match(css,/overflow-wrap:anywhere/);
 assert.match(css,/min-height:44px/);
 assert.match(css,/safe-area-inset-bottom/);
 assert.match(css,/app\.menuopen::before/);
});

test('G03–G05 presentation a11y polish foundations are present',()=>{
 const css=readFileSync(new URL('../src/styles.css',import.meta.url),'utf8');
 assert.match(css,/G03–G05 presentation/);
 assert.match(css,/\.skip-link/);
 assert.match(css,/knowledge-card details>summary/);
 const shell=readFileSync(new URL('../src/AccountWorkspace.jsx',import.meta.url),'utf8');
 assert.match(shell,/className="skip-link"/);
 assert.match(shell,/id="main-content"/);
});
