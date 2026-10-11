import test from 'node:test';
import assert from 'node:assert/strict';
import {todayIn,methodSummary,voucherReturns} from '../src/revenue-days.mjs';

test('today follows the reporting timezone, not the device clock', () => {
  const lateUtc = new Date('2026-10-11T20:00:00Z');
  assert.equal(todayIn('Asia/Yangon', lateUtc), '2026-10-12');
  assert.equal(todayIn('UTC', lateUtc), '2026-10-11');
  assert.equal(todayIn('Not/AZone', lateUtc), null);
});

test('daily method summary hides methods that net to zero', () => {
  assert.deepEqual(methodSummary({WavePay: 3000, KBZPay: 0, Cash: 6000}), [['Cash', 6000], ['WavePay', 3000]]);
  assert.deepEqual(methodSummary(undefined), []);
});

test('cancelled and refunded vouchers are combined for display', () => {
  assert.equal(voucherReturns({vouchers_cancelled: 1, vouchers_refunded: 2}), 3);
  assert.equal(voucherReturns({}), 0);
});
