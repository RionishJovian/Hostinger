import React,{useCallback,useEffect,useState} from 'react';
import {serial} from './voucher-production.mjs';
import {LEDGER,MOVEMENTS,PAYMENT_METHODS,STOCK_REASONS,balanceText,compressSerials,handoverPreview,mmk,movementDetail,newKey,parseSerials} from './dealers.mjs';
function Field({label,children}){return <label className="field"><span>{label}</span>{children}</label>}
const blankDealer={name:'',location:'',phone:'',short_code:'',settlement:'credit',credit_limit:''};
const when=t=>new Date(t*1000).toLocaleString();
function dealerBody(f){return {name:f.name,settlement:f.settlement,...(f.location.trim()?{location:f.location}:{}),...(f.phone.trim()?{phone:f.phone}:{}),...(f.short_code.trim()?{short_code:f.short_code}:{}),...(f.settlement==='credit'&&String(f.credit_limit).trim()!==''?{credit_limit:Number(f.credit_limit)}:{})}}
function DealerFields({form,set}){
 return <div className="formgrid">
  <Field label="Dealer name"><input required maxLength={120} value={form.name} onChange={e=>set('name',e.target.value)} placeholder="e.g. Ko Aung (Market stall)"/></Field>
  <Field label="Location (optional)"><input maxLength={160} value={form.location} onChange={e=>set('location',e.target.value)}/></Field>
  <Field label="Phone (optional)"><input maxLength={40} value={form.phone} onChange={e=>set('phone',e.target.value)}/></Field>
  <Field label="Short code on sheets (optional)"><input maxLength={6} pattern="[A-Za-z0-9]*" value={form.short_code} onChange={e=>set('short_code',e.target.value.toUpperCase())} placeholder="e.g. KA"/></Field>
  <Field label="Settlement"><select value={form.settlement} onChange={e=>set('settlement',e.target.value)}><option value="credit">Credit · pays after receiving stock</option><option value="prepaid">Prepaid · pays before receiving stock</option></select></Field>
  {form.settlement==='credit'&&<Field label="Credit limit, MMK (optional)"><input type="number" min={0} value={form.credit_limit} onChange={e=>set('credit_limit',e.target.value)} placeholder="No limit"/></Field>}
 </div>
}
export default function Dealers({api,refresh}){
 const [dealers,setDealers]=useState([]),[jobs,setJobs]=useState([]),[active,setActive]=useState(null),[detail,setDetail]=useState(null),[message,setMessage]=useState(''),[working,setWorking]=useState(false);
 const [form,setForm]=useState(blankDealer),[edit,setEdit]=useState(null);
 const [give,setGive]=useState({source:'range',job:'',from:'',to:'',price:'',note:''}),[back,setBack]=useState({from:'',to:'',target:'',price:'',credit:true,note:''});
 const [check,setCheck]=useState({counted:'',missing:'',reason:'',note:'',disable:false}),[pay,setPay]=useState({amount:'',method:'Cash',reference:'',note:''}),[fix,setFix]=useState({direction:'credit',amount:'',reason:''});
 const name=id=>dealers.find(d=>d.id===id)?.name||detail?.id===id&&detail.name||'another dealer';
 const reload=useCallback(async()=>{const [d,j]=await Promise.all([api.request('dealers'),api.request('voucher-jobs')]);setDealers(d);setJobs(j.filter(x=>['generated','verified','distributed'].includes(x.status)))},[api]);
 const open=useCallback(async id=>{setActive(id);setEdit(null);if(id)setDetail(await api.request('dealers/'+id))},[api]);
 useEffect(()=>{reload().catch(e=>setMessage(e.message))},[reload]);
 async function run(fn,done){setWorking(true);setMessage('');try{const r=await fn();if(r?.id===active)setDetail(r);await reload();refresh?.();setMessage(r?.replayed?'Already recorded.':r?.message||done||'');return r}catch(e){setMessage(e.message);return null}finally{setWorking(false)}}
 const at=path=>`dealers/${active}/${path}`;
 async function add(e){e.preventDefault();const d=await run(()=>api.request('dealers',dealerBody(form)),'Dealer added.');if(d){setForm(blankDealer);open(d.id)}}
 const giveCount=give.source==='job'?(jobs.find(j=>j.id===give.job)?.available??0):(Number(give.to)>=Number(give.from)&&Number(give.from)>0?Number(give.to)-Number(give.from)+1:0);
 const preview=handoverPreview(giveCount,give.price),missing=parseSerials(check.missing);
 async function handOver(e){e.preventDefault();const sel=give.source==='job'?{production_job_id:give.job}:{serial_from:Number(give.from),serial_to:Number(give.to)};if(await run(()=>api.request(at('assign'),{...sel,unit_price:Number(give.price),...(give.note.trim()?{note:give.note}:{}),request_key:newKey()}),'Stock handed over and charged at the dealer price.'))setGive(g=>({...g,from:'',to:'',note:''}))}
 async function takeBack(e){e.preventDefault();const body={serial_from:Number(back.from),serial_to:Number(back.to),credit:back.credit,...(back.target?{to_dealer_id:back.target,unit_price:Number(back.price)}:{}),...(back.note.trim()?{note:back.note}:{}),request_key:newKey()};if(await run(()=>api.request(at('return'),body),back.target?'Stock moved to the other dealer.':'Unused vouchers returned to your stock.'))setBack(b=>({...b,from:'',to:'',note:''}))}
 async function stockCheck(e){e.preventDefault();if(check.disable&&!window.confirm(`Disable ${missing.length} missing voucher(s)? They stop working at the next router sync.`))return;const body={counted:Number(check.counted),missing_serials:missing||[],disable_missing:check.disable,...(check.reason?{reason:check.reason}:{}),...(check.note.trim()?{note:check.note}:{}),request_key:newKey()};if(await run(()=>api.request(at('stock-check'),body)))setCheck({counted:'',missing:'',reason:'',note:'',disable:false})}
 async function payment(e){e.preventDefault();if(await run(()=>api.request(at('payments'),{amount:Number(pay.amount),method:pay.method,...(pay.reference.trim()?{reference:pay.reference}:{}),...(pay.note.trim()?{note:pay.note}:{}),request_key:newKey()}),'Payment recorded on the dealer ledger.'))setPay(p=>({...p,amount:'',reference:'',note:''}))}
 async function correction(e){e.preventDefault();if(await run(()=>api.request(at('adjustments'),{direction:fix.direction,amount:Number(fix.amount),reason:fix.reason,request_key:newKey()}),'Correction recorded.'))setFix(f=>({...f,amount:'',reason:''}))}
 function reverse(entry){const reason=window.prompt(`Reverse this ${LEDGER[entry.kind].toLowerCase()} of ${mmk(Math.abs(entry.delta))}? Enter the reason:`);if(reason?.trim())run(()=>api.request(at(`ledger/${entry.id}/reverse`),{reason,request_key:newKey()}),'Reversal recorded; the original entry stays in history.')}
 const d=detail&&detail.id===active?detail:null,others=dealers.filter(x=>x.id!==active);
 const unusedSerials=d?compressSerials(d.vouchers.filter(v=>v.status==='unused').map(v=>v.serial_no)):'';
 return <section className="panel dealers"><div className="panelhead"><h2>Dealers & physical stock</h2></div>
  <p>Track printed vouchers you hand to dealers, what they owe, payments, returns and stock checks. Dealers have no login; you record everything here. Dealer money is kept on its own ledger and never counted as counter sales.</p>
  {message&&<p role="status" className="callout">{message}</p>}
  <div className="tablewrap"><table><thead><tr>{['#','Dealer','Settlement','Unused held','Activated','Balance','Open'].map(h=><th key={h}>{h}</th>)}</tr></thead><tbody>{dealers.map(x=><tr key={x.id} className={x.id===active?'selected':''}><td>{x.rank}</td><td>{x.name}{x.short_code?` (${x.short_code})`:''}<small>{[x.location,x.phone].filter(Boolean).join(' · ')}</small></td><td>{x.settlement==='prepaid'?'Prepaid':'Credit'}{x.credit_limit!=null&&<small>Limit {mmk(x.credit_limit)}</small>}</td><td>{x.unused}{x.low_stock&&<small className="pill">Running low</small>}</td><td>{x.activated}</td><td>{balanceText(x.balance)}</td><td><button type="button" className="button secondary" onClick={()=>open(x.id).catch(e=>setMessage(e.message))}>Open</button></td></tr>)}{!dealers.length&&<tr><td colSpan={7}>No dealers yet. Add your first dealer below.</td></tr>}</tbody></table></div>
  <p className="muted">Ranked by activated vouchers. An activated voucher was used on your network; it is not proof of a sale or payment.</p>
  <details className="dealer-action"><summary>Add a dealer</summary><form onSubmit={add}><DealerFields form={form} set={(k,v)=>setForm(f=>({...f,[k]:v}))}/><button className="button" disabled={working||!form.name.trim()}>Add dealer</button></form></details>
  {d&&<div className="dealer-detail">
   <h3>{d.name}{d.archived_at?' · archived':''}</h3>
   <p><strong>{balanceText(d.balance)}</strong> · {d.settlement==='prepaid'?'Prepaid':'Credit'}{d.credit_limit!=null?` · limit ${mmk(d.credit_limit)}`:''} · received {d.received} · returned {d.returned} · {Object.entries(d.holding).map(([k,v])=>`${k==='redeemed'?'activated':k} ${v}`).join(' · ')||'no stock'}</p>
   {unusedSerials&&<p className="muted">Unused serials held: {unusedSerials}</p>}
   {d.low_stock&&<p className="callout">Running low: {d.unused} unused vouchers left. Hand over more stock if you choose — nothing is assigned automatically.</p>}
   {!d.archived_at&&<>
   <details className="dealer-action" open><summary>Hand over stock</summary><form onSubmit={handOver}><div className="formgrid">
    <Field label="Vouchers"><select value={give.source} onChange={e=>setGive(g=>({...g,source:e.target.value}))}><option value="range">Serial range</option><option value="job">All unused from a production job</option></select></Field>
    {give.source==='job'?<Field label="Production job"><select required value={give.job} onChange={e=>setGive(g=>({...g,job:e.target.value}))}><option value="">Choose job</option>{jobs.map(j=><option key={j.id} value={j.id} disabled={!j.available}>{j.ref} · {j.available} available · {serial(j.serial_start)}–{serial(j.serial_end)}</option>)}</select></Field>:<>
     <Field label="First serial"><input required type="number" min={1} value={give.from} onChange={e=>setGive(g=>({...g,from:e.target.value}))}/></Field>
     <Field label="Last serial"><input required type="number" min={1} value={give.to} onChange={e=>setGive(g=>({...g,to:e.target.value}))}/></Field></>}
    <Field label="Dealer price per voucher, MMK"><input required type="number" min={0} value={give.price} onChange={e=>setGive(g=>({...g,price:e.target.value}))} placeholder="Wholesale price you agreed"/></Field>
    <Field label="Note (optional)"><input maxLength={500} value={give.note} onChange={e=>setGive(g=>({...g,note:e.target.value}))}/></Field>
   </div><p className="muted">{preview?`${preview.count} voucher${preview.count===1?'':'s'} · dealer is charged ${mmk(preview.charge)}. Face (customer) prices stay on the vouchers.`:'Choose vouchers and enter the price you agreed with the dealer.'}{d.settlement==='prepaid'?' Prepaid dealers must have paid enough first.':''}</p><button className="button" disabled={working||!preview}>Hand over and charge</button></form></details>
   <details className="dealer-action"><summary>Return or move unused stock</summary><form onSubmit={takeBack}><div className="formgrid">
    <Field label="First serial"><input required type="number" min={1} value={back.from} onChange={e=>setBack(b=>({...b,from:e.target.value}))}/></Field>
    <Field label="Last serial"><input required type="number" min={1} value={back.to} onChange={e=>setBack(b=>({...b,to:e.target.value}))}/></Field>
    <Field label="Send to"><select value={back.target} onChange={e=>setBack(b=>({...b,target:e.target.value}))}><option value="">My stock</option>{others.map(x=><option key={x.id} value={x.id}>{x.name}</option>)}</select></Field>
    {back.target&&<Field label="New dealer price per voucher, MMK"><input required type="number" min={0} value={back.price} onChange={e=>setBack(b=>({...b,price:e.target.value}))}/></Field>}
    <Field label="Note (optional)"><input maxLength={500} value={back.note} onChange={e=>setBack(b=>({...b,note:e.target.value}))}/></Field>
   </div><label className="check"><input type="checkbox" checked={back.credit} onChange={e=>setBack(b=>({...b,credit:e.target.checked}))}/> Credit {d.name} the price they were charged</label><p className="muted">Only unused vouchers can come back. Activated, expired and revoked vouchers stay in this dealer's history.</p><button className="button secondary" disabled={working}>{back.target?'Move to dealer':'Return to my stock'}</button></form></details>
   <details className="dealer-action"><summary>Stock check</summary><form onSubmit={stockCheck}><p>The system expects <strong>{d.unused}</strong> unused vouchers with {d.name}. Count the physical cards and enter the result.</p><div className="formgrid">
    <Field label="Cards counted"><input required type="number" min={0} value={check.counted} onChange={e=>setCheck(c=>({...c,counted:e.target.value}))}/></Field>
    <Field label="Missing serials (optional)"><input value={check.missing} onChange={e=>setCheck(c=>({...c,missing:e.target.value}))} placeholder="e.g. 12-15, 20"/></Field>
    <Field label="Reason for a difference"><select value={check.reason} onChange={e=>setCheck(c=>({...c,reason:e.target.value}))}><option value="">No difference</option>{Object.entries(STOCK_REASONS).map(([k,v])=><option key={k} value={k}>{v}</option>)}</select></Field>
    <Field label="Note (optional)"><input maxLength={500} value={check.note} onChange={e=>setCheck(c=>({...c,note:e.target.value}))}/></Field>
   </div>{check.missing.trim()&&!missing&&<p role="alert">Write serials like 12-15, 20.</p>}<label className="check"><input type="checkbox" checked={check.disable} disabled={!missing?.length} onChange={e=>setCheck(c=>({...c,disable:e.target.checked}))}/> Disable the missing vouchers so nobody can use them</label><p className="muted">The balance does not change automatically. If you agree to credit missing stock, record a correction.</p><button className="button secondary" disabled={working||check.counted===''||(check.missing.trim()&&!missing)}>Record stock check</button></form></details>
   <details className="dealer-action"><summary>Record payment</summary><form onSubmit={payment}><div className="formgrid">
    <Field label="Amount received, MMK"><input required type="number" min={1} value={pay.amount} onChange={e=>setPay(p=>({...p,amount:e.target.value}))}/></Field>
    <Field label="Method"><select value={pay.method} onChange={e=>setPay(p=>({...p,method:e.target.value}))}>{PAYMENT_METHODS.map(m=><option key={m}>{m}</option>)}</select></Field>
    <Field label="Reference (optional)"><input maxLength={160} value={pay.reference} onChange={e=>setPay(p=>({...p,reference:e.target.value}))} placeholder="Transaction ID or receipt no."/></Field>
    <Field label="Note (optional)"><input maxLength={500} value={pay.note} onChange={e=>setPay(p=>({...p,note:e.target.value}))}/></Field>
   </div><button className="button" disabled={working||!(Number(pay.amount)>0)}>Record payment</button></form></details>
   <details className="dealer-action"><summary>Correction</summary><form onSubmit={correction}><div className="formgrid">
    <Field label="Type"><select value={fix.direction} onChange={e=>setFix(f=>({...f,direction:e.target.value}))}><option value="credit">Credit the dealer (reduce what they owe)</option><option value="charge">Charge the dealer (increase what they owe)</option></select></Field>
    <Field label="Amount, MMK"><input required type="number" min={1} value={fix.amount} onChange={e=>setFix(f=>({...f,amount:e.target.value}))}/></Field>
    <Field label="Reason"><input required maxLength={500} value={fix.reason} onChange={e=>setFix(f=>({...f,reason:e.target.value}))}/></Field>
   </div><button className="button secondary" disabled={working||!(Number(fix.amount)>0)||!fix.reason.trim()}>Record correction</button></form></details>
   <details className="dealer-action"><summary>Edit or archive dealer</summary>{edit?<form onSubmit={async e=>{e.preventDefault();if(await run(()=>api.request(at('update'),dealerBody(edit)),'Dealer details saved.'))setEdit(null)}}><DealerFields form={edit} set={(k,v)=>setEdit(f=>({...f,[k]:v}))}/><div className="buttons"><button className="button" disabled={working||!edit.name.trim()}>Save details</button><button type="button" className="button secondary" onClick={()=>setEdit(null)}>Cancel</button></div></form>:<div className="buttons"><button type="button" className="button secondary" onClick={()=>setEdit({...blankDealer,...Object.fromEntries(Object.entries(d).filter(([k])=>k in blankDealer).map(([k,v])=>[k,v??'']))})}>Edit details</button><button type="button" className="button secondary" disabled={working} onClick={()=>{if(window.confirm(`Archive ${d.name}? Their history is kept.`))run(()=>api.request(at('archive'),{}),'Dealer archived.')}}>Archive dealer</button></div>}<p className="muted">Archiving needs no unused stock and a settled balance.</p></details>
   </>}
   <h4>Ledger</h4>
   <div className="tablewrap"><table><thead><tr>{['When','Entry','Amount','Details',''].map(h=><th key={h}>{h}</th>)}</tr></thead><tbody>{d.ledger.map(e=><tr key={e.id}><td>{when(e.created)}</td><td>{LEDGER[e.kind]}{e.reversed&&<small>Reversed</small>}</td><td>{e.delta>0?'+':'−'}{mmk(Math.abs(e.delta))}</td><td>{[e.method,e.reference,e.note].filter(Boolean).join(' · ')}</td><td>{!d.archived_at&&['payment','adjustment'].includes(e.kind)&&!e.reversed&&<button type="button" className="button secondary" disabled={working} onClick={()=>reverse(e)}>Reverse</button>}</td></tr>)}{!d.ledger.length&&<tr><td colSpan={5}>No entries yet.</td></tr>}</tbody></table></div>
   <p className="muted">+ increases what the dealer owes; − reduces it. Entries are never edited; mistakes are fixed with a reversal or correction.</p>
   <h4>Stock movements</h4>
   <div className="tablewrap"><table><thead><tr>{['When','Movement','Vouchers','Details'].map(h=><th key={h}>{h}</th>)}</tr></thead><tbody>{d.movements.map(m=><tr key={m.id}><td>{when(m.created)}</td><td>{MOVEMENTS[m.kind]}{m.note&&<small>{m.note}</small>}</td><td>{m.count}</td><td>{movementDetail(m,name)}</td></tr>)}{!d.movements.length&&<tr><td colSpan={4}>No stock movements yet.</td></tr>}</tbody></table></div>
  </div>}
 </section>
}
