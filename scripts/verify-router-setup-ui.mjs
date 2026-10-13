import {build} from 'esbuild';
import {mkdir,rm,writeFile} from 'node:fs/promises';
import assert from 'node:assert/strict';
const folder='.ui-check';await mkdir(folder,{recursive:true});
try{
 const bundle=await build({stdin:{contents:"export * from './src/RouterSetup.jsx'; export {SMELocalizationProvider} from './src/SMELocalization.jsx';",resolveDir:process.cwd(),loader:'jsx'},loader:{'.css':'empty'},bundle:true,platform:'node',format:'esm',external:['react','@phosphor-icons/react'],write:false});await writeFile(folder+'/router-setup.mjs',bundle.outputFiles[0].text);
 const c=await import('../'+folder+'/router-setup.mjs'),React=await import('react'),{renderToStaticMarkup}=await import('react-dom/server');
 const render=(component,props,language='en',children)=>renderToStaticMarkup(React.createElement(c.SMELocalizationProvider,{languages:['en','my'],defaultLanguage:language},React.createElement(component,props,children)));
 const states=input=>c.routerSetupSteps(input).map(step=>step.state).join(',');
 assert.equal(states({sites:[],routers:[]}),'next,later,later,later');
 assert.equal(states({sites:[{}],routers:[]}),'done,next,later,later');
 assert.equal(states({sites:[{}],routers:[{connection_state:'unverified'}]}),'done,done,next,later','an unverified router is not connected');
 assert.equal(states({sites:[{}],routers:[{connection_state:'connected'}]}),'done,done,done,done','a fresh Connected router completes the check step');
 const html=render(c.RouterSetupSteps,{sites:[{id:'s'}],routers:[],navigate:()=>{}});
 for(const text of ['Connect your router','1. Add your shop','1 shop added.','2. Register your router','Go to the form','3. Connect with Magic Hub','Paste the one script into WinBox','4. Check the connection','Run post-connection preflight'])assert.ok(html.includes(text),text);
 assert.doesNotMatch(html,/Connect it with a technician|Do not paste a separate WinBox script|Go to pairing/);
 assert.equal(html.split('<button').length-1,1,'only the next step has a button');
 assert.doesNotMatch(html,/Connected ·|is connected\./);
 const burmese=render(c.RouterSetupSteps,{sites:[],routers:[],navigate:()=>{}},'my');assert.match(burmese,/Router ချိတ်ဆက်ရန်/);assert.match(burmese,/ဆိုင်များ ဖွင့်ရန်/);
 assert.equal(c.changeNeedsAttention([{phase:'reconnected'}]),false);assert.equal(c.changeNeedsAttention([{phase:'reconnected'},{phase:'configuration_conflict'}]),true);assert.equal(c.changeNeedsAttention([]),false);
 const closed=render(c.RouterAdvanced,{},'en',React.createElement('p',null,'hub table'));assert.match(closed,/^<details class="router-advanced"><summary>Advanced: Magic Hub details and Safe Change<\/summary>/);assert.match(closed,/hub table/);
 assert.doesNotMatch(closed,/technician|pairing|connection plans/i);
 assert.match(render(c.RouterAdvanced,{open:true}),/<details class="router-advanced" open="">/);
 console.log('Router setup UI checks passed: Magic Hub one-paste guide, step states, Advanced section, English and Burmese.');
}finally{await rm(folder,{recursive:true,force:true})}
