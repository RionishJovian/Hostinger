import test from 'node:test';
import assert from 'node:assert/strict';
import {publishPortalContent} from '../src/portal-publishing.mjs';

test('one-click publish saves dirty content before publishing its returned revision',async()=>{
  const calls=[];
  const result=await publishPortalContent({portal:{revision:4},dirty:true,settings:{business_name:'Sample'},act:async(path,body)=>{calls.push([path,body]);return path.endsWith('/draft')?{revision:5}:{published_revision:6}}});
  assert.equal(result,true);
  assert.deepEqual(calls,[['portal/draft',{expected_revision:4,settings:{business_name:'Sample'}}],['portal/publish',{expected_revision:5}]]);
});

test('publish is not attempted if saving the draft fails',async()=>{
  const calls=[];
  const result=await publishPortalContent({portal:{revision:4},dirty:true,settings:{},act:async(path)=>{calls.push(path);return null}});
  assert.equal(result,false);
  assert.deepEqual(calls,['portal/draft']);
});

test('saved content publishes directly without creating an unnecessary draft revision',async()=>{
  const calls=[];
  const result=await publishPortalContent({portal:{revision:4},dirty:false,settings:{},act:async(path,body)=>{calls.push([path,body]);return {published_revision:5}}});
  assert.equal(result,true);
  assert.deepEqual(calls,[['portal/publish',{expected_revision:4}]]);
});
