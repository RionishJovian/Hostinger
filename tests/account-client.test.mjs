import {test} from 'node:test';
import assert from 'node:assert/strict';
import {accountClient,revokeCurrentSession} from '../src/account-api.mjs';
test('private portal export uses authenticated POST and returns binary without token URLs',async()=>{
 let call;const archive=new Blob(['test-archive']);const client=accountClient(()=>{},async(url,options)=>{call={url,options};return {ok:true,blob:async()=>archive}});client.setToken('private-export-token');assert.equal(await client.download('portal/export',{expected_revision:3,public_origin:'https://app.example.com'}),archive);assert.equal(call.options.method,'POST');assert.equal(call.options.headers.Authorization,'Bearer private-export-token');assert.equal(JSON.parse(call.options.body).expected_revision,3);assert.equal(call.url,'/v1/portal/export');assert.ok(!call.url.includes('private-export-token'));
});
test('logout uses the authenticated POST contract and never reports transport success as revocation',async()=>{
 let call;const client=accountClient(()=>{},async(url,options)=>{call={url,options};return {ok:true,json:async()=>({signed_out:true})}});client.setToken('private-logout-token');await revokeCurrentSession(client);assert.equal(call.url,'/v1/auth/logout');assert.equal(call.options.method,'POST');assert.equal(call.options.headers.Authorization,'Bearer private-logout-token');assert.equal(call.options.body,'{}');
});
test('logout server errors and network interruptions do not clear local auth or resolve as success',async()=>{
 for(const failure of [async()=>({ok:false,status:503,json:async()=>({detail:'Sign-out unavailable'})}),async()=>({ok:true,json:async()=>({signed_out:false})}),async()=>{throw Error('Network unavailable')}]){
  const calls=[];const client=accountClient(()=>{},async(url,options)=>{calls.push({url,options});return failure()});client.setToken('private-logout-token');await assert.rejects(revokeCurrentSession(client));
  await client.request('me').catch(()=>{});assert.equal(calls[1].options.headers.Authorization,'Bearer private-logout-token');
 }
});
test('expired logout token is treated as expired, never as successful revocation',async()=>{
 let expired=0;const calls=[];const client=accountClient(()=>expired++,async(url,options)=>{calls.push({url,options});return calls.length===1?{ok:false,status:401,json:async()=>({detail:'Session expired'})}:{ok:true,json:async()=>({})}});client.setToken('expired-logout-token');await assert.rejects(revokeCurrentSession(client),/Session expired/);assert.equal(expired,1);await client.request('me');assert.equal(calls[1].options.headers.Authorization,undefined);
});
test('account client never targets demo and clears expired bearer',async()=>{
 const calls=[];let expired=0;
 const client=accountClient(()=>expired++,async(url,options)=>{calls.push({url,options});return {ok:calls.length!==2,status:calls.length===2?401:200,json:async()=>calls.length===2?{detail:'Session expired'}:{}}});
 client.setToken('private-test-session');await client.request('orders');await assert.rejects(client.request('me'),/Session expired/);await client.request('packages');
 assert.equal(expired,1);assert.ok(calls.every(c=>c.url.startsWith('/v1/')));assert.equal(calls[0].options.headers.Authorization,'Bearer private-test-session');assert.equal(calls[2].options.headers.Authorization,undefined);
});
test('validation errors reach the UI and login errors do not end another session',async()=>{
 let expired=0;const client=accountClient(()=>expired++,async()=>({ok:false,status:422,json:async()=>({detail:[{msg:'Positive quota required'}]})}));
 await assert.rejects(client.request('packages',{}),/Positive quota required/);assert.equal(expired,0);
});
test('receipt bytes use private bearer headers and upload keys, without JSON encoding',async()=>{
 const calls=[];const file=new Blob(['test-image'],{type:'image/png'});const client=accountClient(()=>{},async(url,options)=>{calls.push({url,options});return {ok:true,json:async()=>({id:'image-id'}),blob:async()=>file}});
 client.setToken('test-private-token');await client.upload('orders/order-id/receipts',file,'upload-key-123456');assert.equal(calls[0].options.body,file);assert.equal(calls[0].options.headers['Content-Type'],'application/octet-stream');assert.equal(calls[0].options.headers['X-Upload-Key'],'upload-key-123456');assert.equal(calls[0].options.headers.Authorization,'Bearer test-private-token');assert.equal(await client.blob('orders/order-id/receipts/image-id'),file);assert.ok(calls.every(c=>!c.url.includes('test-private-token')));
});
test('structured API errors surface the safe message and code instead of a generic failure',async()=>{
 const client=accountClient(()=>{},async()=>({ok:false,status:503,json:async()=>({detail:{code:'host_peer_writes_disabled',message:'Hub peer operation could not be completed safely'}})}));
 await assert.rejects(client.request('router-plans/p/hub-peer/provision',{confirmed:true}),{message:'Hub peer operation could not be completed safely (host_peer_writes_disabled)'});
});
test('structured API errors surface the safe message and code instead of a generic failure',async()=>{
 const client=accountClient(()=>{},async()=>({ok:false,status:503,json:async()=>({detail:{code:'host_peer_writes_disabled',message:'Hub peer operation could not be completed safely'}})}));
 await assert.rejects(client.request('router-plans/p/hub-peer/provision',{confirmed:true}),{message:'Hub peer operation could not be completed safely (host_peer_writes_disabled)'});
});
