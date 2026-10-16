import React,{useEffect,useRef,useState} from 'react';
import {useSMELocalization} from './SMELocalization.jsx';
export default function SubscriptionRenewal({api,onChanged}){
 const {t}=useSMELocalization();const m=k=>t('renewal',k);
 const [view,setView]=useState(null),[invoices,setInvoices]=useState([]),[plan,setPlan]=useState(''),[months,setMonths]=useState(1),[method,setMethod]=useState(''),[reference,setReference]=useState(''),[evidence,setEvidence]=useState(''),[busy,setBusy]=useState(false),[notice,setNotice]=useState('');const pending=useRef(null);
 async function load(){const [v,rows]=await Promise.all([api.request('subscription/plans'),api.request('subscription/invoices')]);setView(v);setInvoices(rows);setMethod(x=>x||v.payment?.methods?.[0]||'')}
 useEffect(()=>{load().catch(e=>setNotice(e.message))},[api]);
 async function refresh(){setBusy(true);setNotice('');try{await load();await onChanged?.()}catch(e){setNotice(e.message)}finally{setBusy(false)}}
 async function submit(e){e.preventDefault();const body={plan_id:plan,months:Number(months),method,reference,evidence};const fingerprint=JSON.stringify(body);if(pending.current?.fingerprint!==fingerprint)pending.current={fingerprint,key:crypto.randomUUID()};setBusy(true);setNotice('');try{await api.request('subscription/requests',{...body,request_key:pending.current.key});pending.current=null;setReference('');setEvidence('');await load();await onChanged?.();setNotice(m('submitted'))}catch(err){setNotice(err.message)}finally{setBusy(false)}}
 if(!view)return <section className="panel"><h2>{m('title')}</h2>{notice?<p role="alert">{notice}</p>:<p role="status">…</p>}</section>;
 const sub=view.subscription,chosen=view.plans.find(p=>p.id===plan),open=invoices.some(v=>['pending','needs_evidence'].includes(v.status));
 return <section className="panel renewal"><h2>{m('title')}</h2>
  <div className="tablewrap"><table><thead><tr><th>{m('plan')}</th><th>{m('expires')}</th><th>{m('daysLeft')}</th></tr></thead><tbody><tr><td>{sub.plan_snapshot?.name||m('none')}</td><td>{sub.expires_on||'—'}</td><td>{sub.expires_on?sub.days_left:'—'}</td></tr></tbody></table></div>
  {sub.restricted&&<p className="callout" role="alert">{m('restricted')(sub.expires_on)}</p>}
  {open&&<p className="callout" role="status">{m('pending')}</p>}
  {!view.payment?<p role="status">{m('noPayment')}</p>:!view.plans.length?<p role="status">{m('noPlans')}</p>:!open&&<form onSubmit={submit}>
   <div className="formgrid">
    <label className="field"><span>{m('plan')}</span><select required value={plan} onChange={e=>setPlan(e.target.value)}><option value="">—</option>{view.plans.map(p=><option key={p.id} value={p.id}>{p.name} · {p.monthly_price} {p.currency}</option>)}</select></label>
    <label className="field"><span>{m('months')}</span><select value={months} onChange={e=>setMonths(Number(e.target.value))}>{view.months.map(n=><option key={n} value={n}>{m('monthOption')(n)}</option>)}</select></label>
   </div>
   {chosen&&<p><strong>{m('total')}: {chosen.monthly_price*months} {chosen.currency}</strong></p>}
   <p className="muted">{sub.expires_on&&!sub.restricted?m('termEarly'):m('termLate')}</p>
   <div className="callout"><p>{m('payTo')}: <strong>{view.payment.destination}</strong></p><p className="preserve-lines">{view.payment.instructions}</p></div>
   <div className="formgrid">
    <label className="field"><span>{m('method')}</span><select required value={method} onChange={e=>setMethod(e.target.value)}>{view.payment.methods.map(x=><option key={x}>{x}</option>)}</select></label>
    <label className="field"><span>{m('reference')}</span><input required maxLength={160} value={reference} onChange={e=>setReference(e.target.value)}/></label>
   </div>
   <label className="field"><span>{m('evidence')}</span><textarea required maxLength={4000} value={evidence} onChange={e=>setEvidence(e.target.value)}/></label>
   <button className="button" disabled={busy||!plan}>{m('submit')}</button>
  </form>}
  {notice&&<p role="status">{notice}</p>}
  <button className="button secondary" disabled={busy} onClick={refresh}>{m('refresh')}</button>
 </section>
}
