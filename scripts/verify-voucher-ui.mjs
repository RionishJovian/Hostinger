import {build} from 'esbuild';
import {mkdir,writeFile,rm} from 'node:fs/promises';
import assert from 'node:assert/strict';
const folder='.ui-check';await mkdir(folder,{recursive:true});
try{
 const bundle=await build({stdin:{contents:"export * from './src/Vouchers.jsx'; export * from './src/VoucherPayments.jsx';",resolveDir:process.cwd(),loader:'jsx'},bundle:true,platform:'node',format:'esm',external:['react'],write:false});await writeFile(folder+'/vouchers.mjs',bundle.outputFiles[0].text);
 const {VoucherInventory,RedeemVoucher,VoucherPayment}=await import('../'+folder+'/vouchers.mjs');const React=await import('react');const {renderToStaticMarkup}=await import('react-dom/server');
 const html=renderToStaticMarkup(React.createElement(VoucherInventory,{packages:[],vouchers:[{id:'test-voucher',policy:{name:'Test cinema'},status:'redeemed',code_hint:'ABCD',expires:1}],act:()=>{},busy:true}));
 assert.match(html,/Open sale/);assert.match(html,/Not sold/);assert.match(html,/Generate voucher/);assert.match(html,/Revoke permanently/);assert.match(html,/Issuing or redeeming a voucher does not record revenue/);assert.match(html,/•••• ABCD/);assert.doesNotMatch(html,/code_hash/);
 const guest=renderToStaticMarkup(React.createElement(RedeemVoucher,{act:()=>{},busy:true,go:()=>{}}));assert.match(guest,/Voucher code/);assert.match(guest,/Redeem voucher/);assert.match(guest,/await the site adapters/);
 const payment=renderToStaticMarkup(React.createElement(VoucherPayment,{voucher:{id:'test',policy:{name:'Test',price:3000},code_hint:'ABCD',status:'unused',sale:null},busy:false,act:()=>{}}));assert.match(payment,/Paid with/);assert.match(payment,/<option[^>]*>KBZPay<\/option>/);assert.match(payment,/I received/);assert.match(payment,/<button class="button" disabled="">Record sale/);
 const sold=renderToStaticMarkup(React.createElement(VoucherPayment,{voucher:{id:'test',policy:{name:'Test',price:3000},code_hint:'ABCD',status:'unused',sale:{id:'s',amount:3000,method:'WavePay',reference:'WP-1',evidence:'',created:1},cancelled_sales:[{id:'c',amount:3000,method:'Cash',cancelled_at:1,cancel_reason:'Wrong card'}]},busy:false,act:()=>{}}));assert.match(sold,/Cancel sale/);assert.match(sold,/Refund and stop the voucher/);assert.match(sold,/Wrong card/);
 const used=renderToStaticMarkup(React.createElement(VoucherPayment,{voucher:{id:'test',policy:{name:'Test',price:3000},code_hint:'ABCD',status:'redeemed',sale:{id:'s',amount:3000,method:'Cash',reference:'',evidence:'',created:1}},busy:false,act:()=>{}}));assert.doesNotMatch(used,/Cancel sale/);assert.match(used,/Refund and stop the voucher/);
 console.log('Voucher UI checks passed: issuance, masked inventory, revocation reason, guest redemption, sale methods, cancel and refund.');
}finally{await rm(folder,{recursive:true,force:true})}
