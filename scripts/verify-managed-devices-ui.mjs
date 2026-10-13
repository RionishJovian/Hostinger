import {build} from 'esbuild';
import {mkdir,writeFile,rm} from 'node:fs/promises';
import assert from 'node:assert/strict';
const dir='.ui-check';await mkdir(dir,{recursive:true});
try{
 const bundle=await build({entryPoints:['src/ManagedDevices.jsx'],bundle:true,platform:'node',format:'esm',external:['react'],loader:{'.css':'empty'},write:false});
 await writeFile(dir+'/managed.mjs',bundle.outputFiles[0].text);
 const {default:ManagedDevices}=await import('../'+dir+'/managed.mjs');
 const React=await import('react');
 const {renderToStaticMarkup}=await import('react-dom/server');
 const sites=[{id:'shop-1',name:'Downtown'}];
 const devices=[{id:'sw-1',site_id:'shop-1',kind:'switch',name:'Core switch',vendor:'MikroTik',model:'CRS328',serial_or_mac:'SN-1',location:'Rack',site_limit:1,connection_state:'unverified',metadata_source:'owner_reported',poe_power_cycle:'never',capabilities:[]}];
 const html=renderToStaticMarkup(React.createElement(ManagedDevices,{sites,devices,act:()=>Promise.resolve(null),busy:false}));
 assert.match(html,/Switches and access points/);
 assert.match(html,/Unverified/);
 assert.match(html,/Owner reported/);
 assert.match(html,/never offered/);
 assert.match(html,/1 switch and 5 access points|1 of 1 switches/);
 assert.match(html,/Register a switch or access point/);
 assert.doesNotMatch(html,/is Online|is Connected|power-cycle control is available/i);
 assert.match(html,/not live discovery or Connected status/);
 console.log('Managed devices UI checks passed: inventory, unverified honesty, limits and no-PoE safety copy.');
}finally{await rm(dir,{recursive:true,force:true})}
