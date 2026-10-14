import {build} from 'esbuild';
import {mkdir,rm,writeFile} from 'node:fs/promises';
import assert from 'node:assert/strict';
const folder='.ui-check';await mkdir(folder,{recursive:true});
try{
 const bundle=await build({stdin:{contents:"export {default as OverviewHealth,OverviewNetwork} from './src/OverviewHealth.jsx'; export {SMELocalizationProvider} from './src/SMELocalization.jsx';",resolveDir:process.cwd(),loader:'jsx'},loader:{'.css':'empty'},bundle:true,platform:'node',format:'esm',external:['react','@phosphor-icons/react'],write:false});await writeFile(folder+'/overview.mjs',bundle.outputFiles[0].text);
 const c=await import('../'+folder+'/overview.mjs'),React=await import('react'),{renderToStaticMarkup}=await import('react-dom/server');
 const render=(component,props,language='en')=>renderToStaticMarkup(React.createElement(c.SMELocalizationProvider,{languages:['en','my'],defaultLanguage:language},React.createElement(component,{navigate:()=>{},...props})));
 const count=(html,text)=>html.split(text).length-1;
 const shop=[{id:'s1',name:'Golden Cafe',timezone:'Asia/Yangon'}];
 const noRouter=render(c.OverviewHealth,{sites:shop,routers:[],pendingPayments:0});
 assert.equal(count(noRouter,'No router is registered. Wi-Fi status and connected customers cannot be checked.'),1,'router message appears once');
 assert.match(noRouter,/Not Connected/);assert.doesNotMatch(noRouter,/Unable to Verify/);
 assert.match(noRouter,/class="button"[^>]*>Open Routers/);assert.match(noRouter,/Get help/);
 assert.match(noRouter,/Nothing else needs your attention right now\./);assert.doesNotMatch(noRouter,/Wi-Fi health is still unverified/);
 const noShop=render(c.OverviewHealth,{sites:[],routers:[]});assert.match(noShop,/Add a shop before connecting a router\./);assert.match(noShop,/class="button"[^>]*>Open Shops/);
 const unverified=render(c.OverviewHealth,{sites:shop,routers:[{id:'r1',connection_state:'pending'}],pendingPayments:2});
 assert.equal(count(unverified,'The registered router connection is not verified.'),1);assert.match(unverified,/Unable to Verify/);
 assert.match(unverified,/2 payment reviews waiting/);assert.doesNotMatch(unverified,/Nothing else needs your attention/);
 const mixed=render(c.OverviewHealth,{sites:shop,routers:[{id:'r1',connection_state:'connected',connection_verified:true},{id:'r2',connection_state:'unverified'}]});
 assert.match(mixed,/Unable to Verify/);assert.doesNotMatch(mixed,/>Connected</);
 const connected=render(c.OverviewHealth,{sites:shop,routers:[{id:'r1',connection_state:'connected',connection_verified:true},{id:'r2',connection_state:'connected',connection_verified:true}]});
 assert.match(connected,/>Connected</);assert.doesNotMatch(connected,/Unable to Verify/);
 assert.doesNotMatch(noRouter,/Network summary/,'network summary is a separate section');
 const network=render(c.OverviewNetwork,{sites:shop,routers:[],devices:[{kind:'access_point'}],vouchers:[{}],netCollections:'MMK 3,000'});
 for(const text of ['Network summary','Shops','Registered routers','Registered APs','Connected customers','Generated vouchers','Net confirmed collections','MMK 3,000','Details on Revenue'])assert.ok(network.includes(text),text);
 const burmese=render(c.OverviewNetwork,{sites:shop,netCollections:'MMK 0'},'my');assert.match(burmese,/အတည်ပြုပြီး အသားတင် ငွေလက်ခံရရှိမှု/);
 console.log('Overview UI checks passed: fleet connection aggregation, one router message with its action, attention list without repeats, network summary with collections link, English and Burmese.');
}finally{await rm(folder,{recursive:true,force:true})}
