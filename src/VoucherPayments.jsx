import React,{useState} from 'react';
import {PAYMENT_METHODS,canCancelSale,saleFields,saleProblem} from './voucher-sales.mjs';
import {useSmeCopy} from './SMELocalization.jsx';
const money=x=>new Intl.NumberFormat('en',{style:'currency',currency:'MMK',maximumFractionDigits:0}).format(x||0);
const when=t=>new Date(t*1000).toLocaleString();
function Field({label,children}){return <label className="field"><span>{label}</span>{children}</label>}
function RecordSale({voucher,act,busy}){
 const c=useSmeCopy('vouchers');
 const [method,setMethod]=useState('Cash'),[reference,setReference]=useState(''),[evidence,setEvidence]=useState(''),[confirmed,setConfirmed]=useState(false);
 const f=saleFields(method),problem=saleProblem({method,reference,evidence}),price=money(voucher.policy.price);
 return <form onSubmit={e=>{e.preventDefault();act('vouchers/'+voucher.id+'/sale',{amount:voucher.policy.price,method,reference,evidence,confirmed_received:true})}}>
  <div className="formgrid"><Field label={c.paidWith}><select value={method} onChange={e=>setMethod(e.target.value)}>{PAYMENT_METHODS.map(m=><option key={m}>{m}</option>)}</select></Field>
  <Field label={f.reference}><input required={f.referenceRequired} maxLength={160} value={reference} onChange={e=>setReference(e.target.value)}/></Field></div>
  <Field label={f.note}><textarea required={f.noteRequired} maxLength={4000} value={evidence} onChange={e=>setEvidence(e.target.value)}/></Field>
  <label className="check"><input type="checkbox" checked={confirmed} onChange={e=>setConfirmed(e.target.checked)}/>{c.received(price)}</label>
  <button className="button" disabled={busy||!confirmed||!!problem||['revoked','expired','disabled'].includes(voucher.status)}>{c.recordSale(price)}</button>
  {problem&&<p className="muted" role="status">{problem}</p>}
  <p className="muted">{c.fullPrice}</p>
 </form>
}
function CancelSale({voucher,act,busy}){
 const c=useSmeCopy('vouchers');
 const [reason,setReason]=useState(''),[confirmed,setConfirmed]=useState(false);
 return <details className="dealer-action"><summary>{c.cancelSale}</summary><form onSubmit={e=>{e.preventDefault();act('vouchers/'+voucher.id+'/sale/cancel',{reason,confirmed:true})}}>
  <p>{c.cancelBody}</p>
  <Field label={c.reason}><input required maxLength={500} value={reason} onChange={e=>setReason(e.target.value)} placeholder={c.reasonHint}/></Field>
  <label className="check"><input type="checkbox" checked={confirmed} onChange={e=>setConfirmed(e.target.checked)}/>{c.noMoney}</label>
  <button className="button secondary" disabled={busy||!confirmed||!reason.trim()}>{c.cancelSale}</button>
 </form></details>
}
function RefundSale({sale,voucher,act,busy}){
 const c=useSmeCopy('vouchers');
 const [reason,setReason]=useState(''),[reference,setReference]=useState(''),[returned,setReturned]=useState(false);
 return <details className="dealer-action"><summary>{c.refund}</summary><form onSubmit={e=>{e.preventDefault();act('vouchers/'+voucher.id+'/sale/refund',{reason,reference,confirmed_returned:returned})}}>
  <p>{c.refundBody}</p>
  <Field label={c.refundReason}><textarea required maxLength={1000} value={reason} onChange={e=>setReason(e.target.value)}/></Field>
  <Field label={c.refundRef}><input required maxLength={160} value={reference} onChange={e=>setReference(e.target.value)}/></Field>
  <label className="check"><input type="checkbox" checked={returned} onChange={e=>setReturned(e.target.checked)}/>{c.returned(money(sale.amount))}</label>
  <button className="button secondary" disabled={busy||!returned}>{c.recordRefund}</button>
  <p className="muted">{c.refundNote}</p>
 </form></details>
}
export function VoucherPayment({voucher,act,busy}){
 const c=useSmeCopy('vouchers');
 const sale=voucher.sale,cancelled=voucher.cancelled_sales||[];
 return <section className="panel"><div className="panelhead"><h2>{c.saleTitle(voucher.code_hint)}</h2></div><p>{voucher.policy.name} · {money(voucher.policy.price)} · {c.status[voucher.status]||voucher.status}</p>
  {!sale?<RecordSale voucher={voucher} act={act} busy={busy}/>:<>
   <div className="details">{[[c.amount,money(sale.amount)],[c.paidWith,sale.method],[c.reference,sale.reference||c.none],[c.note,sale.evidence||c.none],[c.recorded,when(sale.created)]].map(([k,v])=><p key={k}><b>{k}</b>{v}</p>)}</div>
   {sale.refunded_at?<p>{c.refundRecorded(when(sale.refunded_at),sale.refund_reference,sale.refund_reason)}</p>:<>
    {canCancelSale(voucher)&&<CancelSale voucher={voucher} act={act} busy={busy}/>}
    <RefundSale sale={sale} voucher={voucher} act={act} busy={busy}/>
   </>}
  </>}
  {cancelled.length>0&&<><h3>{c.cancelledSales}</h3><ul>{cancelled.map(item=><li key={item.id}>{when(item.cancelled_at)} · {item.method} {money(item.amount)} · {item.cancel_reason}</li>)}</ul></>}
 </section>
}
