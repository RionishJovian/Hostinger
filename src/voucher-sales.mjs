export {PAYMENT_METHODS} from './dealers.mjs';

export function saleFields(method){
 if(method==='KBZPay'||method==='WavePay')return {reference:`${method} transaction ID`,referenceRequired:true,note:'Note (optional)',noteRequired:false};
 if(method==='Other')return {reference:'Reference (optional)',referenceRequired:false,note:'How did the customer pay?',noteRequired:true};
 return {reference:'Receipt number (optional)',referenceRequired:false,note:'Note (optional)',noteRequired:false};
}

export function saleProblem({method,reference='',evidence=''}){
 const f=saleFields(method);
 if(f.referenceRequired&&!reference.trim())return `Enter the ${method} transaction ID.`;
 if(f.noteRequired&&!evidence.trim())return 'Describe how the customer paid.';
 return '';
}

export function saleLabel(sale){
 if(!sale)return 'Not sold';
 if(sale.refunded_at)return 'Refunded';
 return `Sold · ${sale.method}`;
}

export function canCancelSale(voucher){
 return !!voucher.sale&&!voucher.sale.refunded_at&&voucher.status==='unused';
}
