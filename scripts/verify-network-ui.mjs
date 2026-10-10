import {build} from 'esbuild';
import {mkdir,writeFile,rm} from 'node:fs/promises';
import assert from 'node:assert/strict';
const dir='.ui-check';await mkdir(dir,{recursive:true});
try{
 const bundle=await build({entryPoints:['src/NetworkRegistry.jsx'],bundle:true,platform:'node',format:'esm',external:['react'],write:false});await writeFile(dir+'/network.mjs',bundle.outputFiles[0].text);
 const {SiteRegistry,RouterRegistry}=await import('../'+dir+'/network.mjs');const React=await import('react');const {renderToStaticMarkup}=await import('react-dom/server');
 const sites=[{id:'test-site',name:'Sample cafe',timezone:'Asia/Yangon'}];const routers=[{id:'test-router',site_id:'test-site',name:'Gateway',model:'hAP ax3',reported_routeros:'Test version'}];
 const owner=renderToStaticMarkup(React.createElement(RouterRegistry,{sites,routers,act:()=>{},busy:true}));assert.match(owner,/Unverified/);assert.match(owner,/Not assigned/);assert.match(owner,/owner reported/);assert.match(owner,/Register router/);assert.doesNotMatch(owner,/Online/);
 const platform=renderToStaticMarkup(React.createElement(RouterRegistry,{sites,routers,platform:true}));assert.doesNotMatch(platform,/Register router/);assert.match(platform,/Platform router fleet/);
 const site=renderToStaticMarkup(React.createElement(SiteRegistry,{sites,busy:true}));assert.match(site,/Reporting timezone/);assert.match(site,/Create site/);
 const safeBundle=await build({entryPoints:['src/SafeRouterChanges.jsx'],bundle:true,platform:'node',format:'esm',external:['react'],write:false});await writeFile(dir+'/safe.mjs',safeBundle.outputFiles[0].text);const {SafeRouterChanges}=await import('../'+dir+'/safe.mjs');
 const plans=[{router_id:'test-router',reviewed_at:1}],changes=[{id:'change',router_id:'test-router',risk:'high',status:'previewed',revision:1,before:{persistent_keepalive_seconds:15},desired:{persistent_keepalive_seconds:25},actual:{persistent_keepalive_seconds:15},diff:{impact:'Management tunnel risk'},safety_backup_verified:false}];const safe=renderToStaticMarkup(React.createElement(SafeRouterChanges,{routers,plans,changes,act:()=>{},busy:false}));assert.match(safe,/Inspect actual state/);assert.match(safe,/HIGH/);assert.match(safe,/Create safety backup &amp; apply/);assert.match(safe,/Recovery Required/);assert.doesNotMatch(safe,/password|private key/i);
 const conflict=renderToStaticMarkup(React.createElement(SafeRouterChanges,{routers,plans,changes:[{...changes[0],status:'conflict',phase:'configuration_conflict'}],act:()=>{},busy:false}));assert.match(conflict,/Keep Router Version/);assert.match(conflict,/Back up &amp; Keep MikroMagic Version/);assert.match(conflict,/Per-setting merge is not available/);assert.match(conflict,/view-only for one week/);
 const recovery=renderToStaticMarkup(React.createElement(SafeRouterChanges,{routers,plans,changes:[{...changes[0],status:'recovery_required',phase:'recovery_required'}],act:()=>{},busy:false}));assert.match(recovery,/could not execute or verify rollback/);assert.match(recovery,/only when the actual configuration is verified/);assert.doesNotMatch(recovery,/password|private key/i);
 console.log('Network UI checks passed: registry, Safe Change phases, whole-version conflict choices, backup, verification and Recovery Required messaging.');
}finally{await rm(dir,{recursive:true,force:true})}
