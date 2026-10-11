import {build} from 'esbuild';import {mkdir,writeFile,rm} from 'node:fs/promises';import assert from 'node:assert/strict';
await mkdir('.ui-check',{recursive:true});
try{
 const b=await build({stdin:{contents:"export {AgentApplication} from './src/AgentWorkspace.jsx'; export {REGIONS,pinLink,placeText} from './src/AgentLocation.jsx';",loader:'jsx',resolveDir:process.cwd()},bundle:true,platform:'node',format:'esm',external:['react','leaflet','leaflet/*'],write:false});
 await writeFile('.ui-check/agent-location.mjs',b.outputFiles[0].text);
 const c=await import('../.ui-check/agent-location.mjs'),React=await import('react'),{renderToStaticMarkup}=await import('react-dom/server');
 const html=renderToStaticMarkup(React.createElement(c.AgentApplication,{onDone(){}}));
 for(const text of ['Where you work','State or region','City','Township','Map pin','Choose on map','Type coordinates instead','Your location is not tracked','No pin placed yet.'])assert.ok(html.includes(text),text);
 assert.equal(c.REGIONS.length,15);for(const r of c.REGIONS)assert.ok(html.includes(`<option value="${r}">${r}</option>`)||html.includes(`<option>${r}</option>`),r);
 assert.ok(!html.includes('leaflet-container'),'the map loads only after Choose on map');
 const pin={region:'Mandalay Region',city:'Mandalay',township:'Chanayethazan',latitude:21.97,longitude:96.08};
 assert.equal(c.placeText(pin),'Chanayethazan, Mandalay, Mandalay Region');
 assert.equal(c.pinLink(pin),'https://www.openstreetmap.org/?mlat=21.97&mlon=96.08#map=16/21.97/96.08');
 console.log('Agent location checks passed: region list, city, township, on-demand map pin and typed fallback.');
}finally{await rm('.ui-check/agent-location.mjs',{force:true})}
