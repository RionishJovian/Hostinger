import test from 'node:test';
import assert from 'node:assert/strict';
import {formatMmk,formatSmeDateTime,formatSmePhone,smeIntlLocale,toMyanmarDigits} from '../src/sme-format.mjs';

test('SME intl locale maps Burmese to my-MM',()=>{
 assert.equal(smeIntlLocale('my'),'my-MM');
 assert.equal(smeIntlLocale('en'),'en');
 assert.equal(smeIntlLocale('xx'),'my-MM');
});

test('toMyanmarDigits maps ASCII digits only',()=>{
 assert.equal(toMyanmarDigits('19,000'),'၁၉,၀၀၀');
 assert.equal(toMyanmarDigits('MMK 0'),'MMK ၀');
});

test('MMK formatting uses English digits for en and Myanmar digits for my',()=>{
 assert.match(formatMmk(15000,'en'),/15,?000/);
 assert.match(formatMmk(15000,'en'),/MMK/);
 const my=formatMmk(15000,'my');
 assert.equal(my,'၁၅,၀၀၀ ကျပ်');
 assert.match(my,/[၀-၉]/);
 assert.doesNotMatch(my,/[0-9]/);
});

test('date/time formatting follows the SME language',()=>{
 const sample=1728000000; // 2024-10-04 UTC
 const en=formatSmeDateTime(sample,'en');
 const my=formatSmeDateTime(sample,'my');
 assert.match(en,/2024|Oct/);
 assert.match(my,/[၀-၉]/);
 assert.notEqual(en,my);
 assert.equal(formatSmeDateTime(null,'en'),'');
 assert.equal(formatSmeDateTime('bad','en'),'');
});

test('Myanmar phone display soft-formats common local forms',()=>{
 assert.equal(formatSmePhone('09123456789'),'09 123 456 789');
 assert.equal(formatSmePhone('+959123456789'),'09 123 456 789');
 assert.equal(formatSmePhone('959123456789'),'09 123 456 789');
 assert.equal(formatSmePhone('09-123-456-789'),'09 123 456 789');
 assert.equal(formatSmePhone('not-a-phone'),'not-a-phone');
 assert.equal(formatSmePhone(''),'');
});
