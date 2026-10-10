import React,{useState} from 'react';
import {PAYMENT_METHODS,canCancelSale,saleFields,saleProblem} from './voucher-sales.mjs';
const money=x=>new Intl.NumberFormat('en',{style:'currency',currency:'MMK',maximumFractionDigits:0}).format(x||0);
const when=t=>new Date(t*1000).toLocaleString();
function Field({label,children}){return <label className="field"><span>{label}</span>{children}</label>}
function RecordSale({voucher,act,busy}){
 const [method,setMethod]=useState('Cash'),[reference,setReference]=useState(''),[evidence,setEvidence]=useState(''),[confirmed,setConfirmed]=useState(false);
 const f=saleFields(method),problem=saleProblem({method,reference,evidence}),price=money(voucher.policy.price);
 return <form onSubmit={e=>{e.preventDefault();act('vouchers/'+voucher.id+'/sale',{amount:voucher.policy.price,method,reference,evidence,confirmed_received:true})}}>
  <div className="formgrid"><Field label="Paid with"><select value={method} onChange={e=>setMethod(e.target.value)}>{PAYMENT_METHODS.map(m=><option key={m}>{m}</option>)}</select></Field>
  <Field label={f.reference}><input required={f.referenceRequired} maxLength={160} value={reference} onChange={e=>setReference(e.target.value)}/></Field></div>
  <Field label={f.note}><textarea required={f.noteRequired} maxLength={4000} value={evidence} onChange={e=>setEvidence(e.target.value)}/></Field>
  <label className="check"><input type="checkbox" checked={confirmed} onChange={e=>setConfirmed(e.target.checked)}/>I received {price}</label>
  <button className="button" disabled={busy||!confirmed||!!problem||['revoked','expired','disabled'].includes(voucher.status)}>Record sale · {price}</button>
  {problem&&<p className="muted" role="status">{problem}</p>}
  <p className="muted">Full package price only. This records the payment; it does not collect money.</p>
 </form>
}
function CancelSale({voucher,act,busy}){
 const [reason,setReason]=useState(''),[confirmed,setConfirmed]=useState(false);
 return <details className="dealer-action"><summary>Cancel sale</summary><form onSubmit={e=>{e.preventDefault();act('vouchers/'+voucher.id+'/sale/cancel',{reason,confirmed:true})}}>
  <p>Use this when the sale was a mistake or the customer gave the card back unused. The sale stays in history, revenue is reversed, and the voucher returns to unsold stock.</p>
  <Field label="Reason"><input required maxLength={500} value={reason} onChange={e=>setReason(e.target.value)} placeholder="e.g. Sold the wrong card"/></Field>
  <label className="check"><input type="checkbox" checked={confirmed} onChange={e=>setConfirmed(e.target.checked)}/>No money was kept for this sale</label>
  <button className="button secondary" disabled={busy||!confirmed||!reason.trim()}>Cancel sale</button>
 </form></details>
}
function RefundSale({sale,voucher,act,busy}){
 const [reason,setReason]=useState(''),[reference,setReference]=useState(''),[returned,setReturned]=useState(false);
 return <details className="dealer-action"><summary>Refund and stop the voucher</summary><form onSubmit={e=>{e.preventDefault();act('vouchers/'+voucher.id+'/sale/refund',{reason,reference,confirmed_returned:returned})}}>
  <p>Use this when the voucher was used, or must never work again. The pass is revoked permanently.</p>
  <Field label="Refund reason"><textarea required maxLength={1000} value={reason} onChange={e=>setReason(e.target.value)}/></Field>
  <Field label="Refund receipt / reference"><input required maxLength={160} value={reference} onChange={e=>setReference(e.target.value)}/></Field>
  <label className="check"><input type="checkbox" checked={returned} onChange={e=>setReturned(e.target.checked)}/>I returned {money(sale.amount)}</label>
  <button className="button secondary" disabled={busy||!returned}>Record full refund & revoke pass</button>
  <p className="muted">This records a refund already handled outside the app. Live access revocation awaits the adapter.</p>
 </form></details>
}
export function VoucherPayment({voucher,act,busy}){
 const sale=voucher.sale,cancelled=voucher.cancelled_sales||[];
 return <section className="panel"><div className="panelhead"><h2>Sale for •••• {voucher.code_hint}</h2></div><p>{voucher.policy.name} · {money(voucher.policy.price)} · {voucher.status}</p>
  {!sale?<RecordSale voucher={voucher} act={act} busy={busy}/>:<>
   <div className="details">{[['Amount',money(sale.amount)],['Paid with',sale.method],['Reference',sale.reference||'—'],['Note',sale.evidence||'—'],['Recorded',when(sale.created)]].map(([k,v])=><p key={k}><b>{k}</b>{v}</p>)}</div>
   {sale.refunded_at?<p>Refund recorded {when(sale.refunded_at)} · {sale.refund_reference} · {sale.refund_reason}</p>:<>
    {canCancelSale(voucher)&&<CancelSale voucher={voucher} act={act} busy={busy}/>}
    <RefundSale sale={sale} voucher={voucher} act={act} busy={busy}/>
   </>}
  </>}
  {cancelled.length>0&&<><h3>Cancelled sales</h3><ul>{cancelled.map(c=><li key={c.id}>{when(c.cancelled_at)} · {c.method} {money(c.amount)} · {c.cancel_reason}</li>)}</ul></>}
 </section>
}
