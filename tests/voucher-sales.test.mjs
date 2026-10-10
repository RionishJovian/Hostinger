import test from 'node:test';
import assert from 'node:assert/strict';
import {PAYMENT_METHODS,canCancelSale,saleFields,saleLabel,saleProblem} from '../src/voucher-sales.mjs';

test('offers exactly Cash, KBZPay, WavePay and Other', () => {
 assert.deepEqual(PAYMENT_METHODS, ['Cash', 'KBZPay', 'WavePay', 'Other']);
});

test('requires a transaction ID only for mobile wallets and a description for Other', () => {
 assert.equal(saleProblem({method: 'Cash'}), '');
 assert.equal(saleProblem({method: 'KBZPay', reference: ' '}), 'Enter the KBZPay transaction ID.');
 assert.equal(saleProblem({method: 'WavePay', reference: 'WP-1'}), '');
 assert.equal(saleProblem({method: 'Other', evidence: ''}), 'Describe how the customer paid.');
 assert.equal(saleFields('WavePay').reference, 'WavePay transaction ID');
 assert.equal(saleFields('Cash').referenceRequired, false);
});

test('labels sales and allows Cancel Sale only for unused, unrefunded vouchers', () => {
 const sale = {method: 'Cash', refunded_at: null};
 assert.equal(saleLabel(null), 'Not sold');
 assert.equal(saleLabel(sale), 'Sold · Cash');
 assert.equal(saleLabel({...sale, refunded_at: 5}), 'Refunded');
 assert.equal(canCancelSale({status: 'unused', sale}), true);
 assert.equal(canCancelSale({status: 'redeemed', sale}), false);
 assert.equal(canCancelSale({status: 'unused', sale: {...sale, refunded_at: 5}}), false);
 assert.equal(canCancelSale({status: 'unused', sale: null}), false);
});
