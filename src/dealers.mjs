import {serial} from './voucher-production.mjs';
export const STOCK_REASONS={lost:'Lost',damaged:'Damaged',counting_difference:'Counting difference',other:'Other'};
export const PAYMENT_METHODS=['Cash','KBZPay','WavePay','Other'];
export const MAX_SERIALS=1000;
export function parseSerials(text){
 const out=new Set();
 for(const part of String(text||'').split(/[\s,]+/).filter(Boolean)){
  const m=part.match(/^(\d{1,9})(?:[-–](\d{1,9}))?$/);if(!m)return null;
  const a=Number(m[1]),b=m[2]?Number(m[2]):a;if(!a||b<a||b-a>=MAX_SERIALS)return null;
  for(let n=a;n<=b;n++)out.add(n);
  if(out.size>MAX_SERIALS)return null;
 }
 return [...out].sort((x,y)=>x-y);
}
export function compressSerials(numbers){
 const list=[...new Set(numbers.filter(n=>n!=null))].sort((a,b)=>a-b),parts=[];
 for(let i=0;i<list.length;){let j=i;while(j+1<list.length&&list[j+1]===list[j]+1)j++;parts.push(i===j?serial(list[i]):`${serial(list[i])}–${serial(list[j])}`);i=j+1}
 return parts.join(', ');
}
export const mmk=n=>`${Number(n||0).toLocaleString('en-US')} MMK`;
export function balanceText(balance){return balance>0?`Owes ${mmk(balance)}`:balance<0?`Prepaid credit ${mmk(-balance)}`:'Settled'}
export const MOVEMENTS={assign:'Handed over',return:'Returned to your stock',reassign_out:'Moved to another dealer',reassign_in:'Received from another dealer',stock_check:'Stock check'};
export const LEDGER={charge:'Stock charge',payment:'Payment received',return_credit:'Return credit',adjustment:'Correction',reversal:'Reversal'};
export function movementDetail(m,dealerName=id=>id,phrases){
 const p=phrases||{expected:'Expected',counted:'counted',difference:'difference',missing:'missing',disabled:'disabled',each:'each',face:'face',credited:'credited',noCredit:'no credit',from:'from',to:'to',reasons:STOCK_REASONS};
 const reasons=p.reasons||STOCK_REASONS;
 const d=m.details||{},who=m.counterpart_dealer_id?` · ${m.kind==='reassign_in'?p.from:p.to} ${dealerName(m.counterpart_dealer_id)}`:'';
 if(m.kind==='stock_check')return `${p.expected} ${d.expected} · ${p.counted} ${d.counted} · ${p.difference} ${d.difference>0?'+':''}${d.difference}${m.reason?` · ${reasons[m.reason]||m.reason}`:''}${d.missing_serials?.length?` · ${p.missing} ${compressSerials(d.missing_serials)}`:''}${d.disabled?` · ${d.disabled} ${p.disabled}`:''}`;
 if(m.kind==='assign'||m.kind==='reassign_in')return `${d.serials||''} · ${mmk(m.unit_price)} ${p.each} (${p.face} ${mmk(d.face_value)})${who}`;
 return `${d.serials||''}${d.credited?` · ${p.credited} ${mmk(d.credited)}`:` · ${p.noCredit}`}${who}`;
}
export function handoverPreview(count,price){
 const n=Number(count)||0,p=Number(price);
 if(!n||!(p>=0)||String(price).trim()==='')return null;
 return {count:n,charge:n*p};
}
export const newKey=()=>'web-'+(globalThis.crypto?.randomUUID?.()||Math.random().toString(36).slice(2)+Date.now().toString(36));
