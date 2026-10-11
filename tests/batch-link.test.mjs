import test from 'node:test';
import assert from 'node:assert/strict';
import {batchLink,readBatchLink,withoutBatchLink,batchQrCodes} from '../src/batch-link.mjs';

const id='3f2489e3-dbb6-41cc-9d2d-e66befe42255';
const live={protocol:'https:',hostname:'megamagic.tech',origin:'https://megamagic.tech'};

test('batch links carry only the job id and sheet, on a secure origin', () => {
  assert.equal(batchLink(live, id, 3), `https://megamagic.tech/?batch=${id}&sheet=3`);
  assert.equal(batchLink({protocol:'http:',hostname:'example.com',origin:'http://example.com'}, id, 1), null);
  assert.equal(batchLink(live, 'PJ-0007', 1), null);
});

test('only well-formed batch links are read back', () => {
  assert.deepEqual(readBatchLink(`?batch=${id.toUpperCase()}&sheet=2`), {jobId:id, sheet:2});
  assert.deepEqual(readBatchLink(`?batch=${id}&sheet=0`), {jobId:id, sheet:null});
  assert.equal(readBatchLink('?batch=../../etc'), null);
  assert.equal(readBatchLink('?guest_site=abc'), null);
});

test('consumed batch parameters are removed but others stay', () => {
  assert.equal(withoutBatchLink({href:`https://megamagic.tech/?batch=${id}&sheet=2&lang=my`}), '/?lang=my');
});

test('QR codes are generated per sheet unless the job switched them off', async () => {
  const toSvg = async text => `<svg>${text}</svg>`;
  const codes = await batchQrCodes(toSvg, live, {id, settings:{}}, [1, 2]);
  assert.deepEqual(Object.keys(codes), ['1', '2']);
  assert.match(codes[2], /sheet=2/);
  assert.deepEqual(await batchQrCodes(toSvg, live, {id, settings:{batch_qr:false}}, [1]), {});
});
