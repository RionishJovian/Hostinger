import React,{useCallback,useEffect,useState} from 'react';
import {serial} from './voucher-production.mjs';
import {PAYMENT_METHODS,balanceText,compressSerials,handoverPreview,mmk,movementDetail,newKey,parseSerials} from './dealers.mjs';
import {useSmeCopy} from './SMELocalization.jsx';
function Field({label,children}){return <label className="field"><span>{label}</span>{children}</label>}
const blankDealer={name:'',location:'',phone:'',short_code:'',settlement:'credit',credit_limit:''};
const when=t=>new Date(t*1000).toLocaleString();
function dealerBody(f){return {name:f.name,settlement:f.settlement,...(f.location.trim()?{location:f.location}:{}),...(f.phone.trim()?{phone:f.phone}:{}),...(f.short_code.trim()?{short_code:f.short_code}:{}),...(f.settlement==='credit'&&String(f.credit_limit).trim()!==''?{credit_limit:Number(f.credit_limit)}:{})}}
function DealerFields({form,set,c}){
 return <div className="formgrid">
  <Field label={c.name}><input required maxLength={120} value={form.name} onChange={e=>set('name',e.target.value)} placeholder={c.nameHint}/></Field>
  <Field label={c.location}><input maxLength={160} value={form.location} onChange={e=>set('location',e.target.value)}/></Field>
  <Field label={c.phone}><input maxLength={40} value={form.phone} onChange={e=>set('phone',e.target.value)}/></Field>
  <Field label={c.short}><input maxLength={6} pattern="[A-Za-z0-9]*" value={form.short_code} onChange={e=>set('short_code',e.target.value.toUpperCase())} placeholder={c.shortHint}/></Field>
  <Field label={c.settlement}><select value={form.settlement} onChange={e=>set('settlement',e.target.value)}><option value="credit">{c.creditOption}</option><option value="prepaid">{c.prepaidOption}</option></select></Field>
  {form.settlement==='credit'&&<Field label={c.creditLimit}><input type="number" min={0} value={form.credit_limit} onChange={e=>set('credit_limit',e.target.value)} placeholder={c.noLimit}/></Field>}
 </div>
}
export default function Dealers({api,refresh}){
 const c=useSmeCopy('dealers');
 const [dealers,setDealers]=useState([]),[jobs,setJobs]=useState([]),[active,setActive]=useState(null),[detail,setDetail]=useState(null),[message,setMessage]=useState(''),[working,setWorking]=useState(false);
 const [form,setForm]=useState(blankDealer),[edit,setEdit]=useState(null);
 const [give,setGive]=useState({source:'range',job:'',from:'',to:'',price:'',note:''}),[back,setBack]=useState({from:'',to:'',target:'',price:'',credit:true,note:''});
 const [check,setCheck]=useState({counted:'',missing:'',reason:'',note:'',disable:false}),[pay,setPay]=useState({amount:'',method:'Cash',reference:'',note:''}),[fix,setFix]=useState({direction:'credit',amount:'',reason:''});
 const name=id=>dealers.find(d=>d.id===id)?.name||detail?.id===id&&detail.name||c.another;
 const reload=useCallback(async()=>{const [d,j]=await Promise.all([api.request('dealers'),api.request('voucher-jobs')]);setDealers(d);setJobs(j.filter(x=>['generated','verified','distributed'].includes(x.status)))},[api]);
 const open=useCallback(async id=>{setActive(id);setEdit(null);if(id)setDetail(await api.request('dealers/'+id))},[api]);
 useEffect(()=>{reload().catch(e=>setMessage(e.message))},[reload]);
 async function run(fn,done){setWorking(true);setMessage('');try{const r=await fn();if(r?.id===active)setDetail(r);await reload();refresh?.();setMessage(r?.replayed?c.already:r?.message||done||'');return r}catch(e){setMessage(e.message);return null}finally{setWorking(false)}}
 const at=path=>`dealers/${active}/${path}`;
 async function add(e){e.preventDefault();const d=await run(()=>api.request('dealers',dealerBody(form)),c.added);if(d){setForm(blankDealer);open(d.id)}}
 const giveCount=give.source==='job'?(jobs.find(j=>j.id===give.job)?.available??0):(Number(give.to)>=Number(give.from)&&Number(give.from)>0?Number(give.to)-Number(give.from)+1:0);
 const preview=handoverPreview(giveCount,give.price),missing=parseSerials(check.missing);
 async function handOver(e){e.preventDefault();const sel=give.source==='job'?{production_job_id:give.job}:{serial_from:Number(give.from),serial_to:Number(give.to)};if(await run(()=>api.request(at('assign'),{...sel,unit_price:Number(give.price),...(give.note.trim()?{note:give.note}:{}),request_key:newKey()}),c.handed))setGive(g=>({...g,from:'',to:'',note:''}))}
 async function takeBack(e){e.preventDefault();const body={serial_from:Number(back.from),serial_to:Number(back.to),credit:back.credit,...(back.target?{to_dealer_id:back.target,unit_price:Number(back.price)}:{}),...(back.note.trim()?{note:back.note}:{}),request_key:newKey()};if(await run(()=>api.request(at('return'),body),back.target?c.moved:c.returned))setBack(b=>({...b,from:'',to:'',note:''}))}
 async function stockCheck(e){e.preventDefault();if(check.disable&&!window.confirm(c.disableConfirm(missing.length)))return;const body={counted:Number(check.counted),missing_serials:missing||[],disable_missing:check.disable,...(check.reason?{reason:check.reason}:{}),...(check.note.trim()?{note:check.note}:{}),request_key:newKey()};if(await run(()=>api.request(at('stock-check'),body)))setCheck({counted:'',missing:'',reason:'',note:'',disable:false})}
 async function payment(e){e.preventDefault();if(await run(()=>api.request(at('payments'),{amount:Number(pay.amount),method:pay.method,...(pay.reference.trim()?{reference:pay.reference}:{}),...(pay.note.trim()?{note:pay.note}:{}),request_key:newKey()}),c.paid))setPay(p=>({...p,amount:'',reference:'',note:''}))}
 async function correction(e){e.preventDefault();if(await run(()=>api.request(at('adjustments'),{direction:fix.direction,amount:Number(fix.amount),reason:fix.reason,request_key:newKey()}),c.corrected))setFix(f=>({...f,amount:'',reason:''}))}
 function reverse(entry){const reason=window.prompt(c.reversePrompt((c.ledgerKinds[entry.kind]||entry.kind).toLowerCase(),mmk(Math.abs(entry.delta))));if(reason?.trim())run(()=>api.request(at(`ledger/${entry.id}/reverse`),{reason,request_key:newKey()}),c.reversedDone)}
 const d=detail&&detail.id===active?detail:null,others=dealers.filter(x=>x.id!==active);
 const unusedSerials=d?compressSerials(d.vouchers.filter(v=>v.status==='unused').map(v=>v.serial_no)):'';
 const phrases={...c.phrases,reasons:c.reasons};
 return <section className="panel dealers"><div className="panelhead"><h2>{c.title}</h2></div>
  <p>{c.intro}</p>
  {message&&<p role="status" className="callout">{message}</p>}
  <div className="tablewrap"><table><thead><tr>{c.cols.map(h=><th key={h}>{h}</th>)}</tr></thead><tbody>{dealers.map(x=><tr key={x.id} className={x.id===active?'selected':''}><td>{x.rank}</td><td>{x.name}{x.short_code?` (${x.short_code})`:''}<small>{[x.location,x.phone].filter(Boolean).join(' · ')}</small></td><td>{x.settlement==='prepaid'?c.prepaid:c.credit}{x.credit_limit!=null&&<small>{c.limit(mmk(x.credit_limit))}</small>}</td><td>{x.unused}{x.low_stock&&<small className="pill">{c.low}</small>}</td><td>{x.activated}</td><td>{balanceText(x.balance)}</td><td><button type="button" className="button secondary" onClick={()=>open(x.id).catch(e=>setMessage(e.message))}>{c.open}</button></td></tr>)}{!dealers.length&&<tr><td colSpan={7}>{c.empty}</td></tr>}</tbody></table></div>
  <p className="muted">{c.rank}</p>
  <details className="dealer-action"><summary>{c.add}</summary><form onSubmit={add}><DealerFields form={form} set={(k,v)=>setForm(f=>({...f,[k]:v}))} c={c}/><button className="button" disabled={working||!form.name.trim()}>{c.addButton}</button></form></details>
  {d&&<div className="dealer-detail">
   <h3>{d.name}{d.archived_at?c.archived:''}</h3>
   <p><strong>{balanceText(d.balance)}</strong> · {d.settlement==='prepaid'?c.prepaid:c.credit}{d.credit_limit!=null?` · ${c.limit(mmk(d.credit_limit))}`:''} · {c.holding(d.received,d.returned,Object.entries(d.holding).map(([k,v])=>`${k==='redeemed'?c.activatedWord:k} ${v}`).join(' · '))}</p>
   {unusedSerials&&<p className="muted">{c.unusedSerials(unusedSerials)}</p>}
   {d.low_stock&&<p className="callout">{c.lowStock(d.unused)}</p>}
   {!d.archived_at&&<>
   <details className="dealer-action" open><summary>{c.hand}</summary><form onSubmit={handOver}><div className="formgrid">
    <Field label={c.vouchers}><select value={give.source} onChange={e=>setGive(g=>({...g,source:e.target.value}))}><option value="range">{c.range}</option><option value="job">{c.fromJob}</option></select></Field>
    {give.source==='job'?<Field label={c.job}><select required value={give.job} onChange={e=>setGive(g=>({...g,job:e.target.value}))}><option value="">{c.chooseJob}</option>{jobs.map(j=><option key={j.id} value={j.id} disabled={!j.available}>{j.ref} · {j.available} available · {serial(j.serial_start)}–{serial(j.serial_end)}</option>)}</select></Field>:<>
     <Field label={c.first}><input required type="number" min={1} value={give.from} onChange={e=>setGive(g=>({...g,from:e.target.value}))}/></Field>
     <Field label={c.last}><input required type="number" min={1} value={give.to} onChange={e=>setGive(g=>({...g,to:e.target.value}))}/></Field></>}
    <Field label={c.dealerPrice}><input required type="number" min={0} value={give.price} onChange={e=>setGive(g=>({...g,price:e.target.value}))} placeholder={c.wholesale}/></Field>
    <Field label={c.note}><input maxLength={500} value={give.note} onChange={e=>setGive(g=>({...g,note:e.target.value}))}/></Field>
   </div><p className="muted">{preview?c.preview(preview.count,mmk(preview.charge)):c.previewEmpty}{d.settlement==='prepaid'?c.prepaidFirst:''}</p><button className="button" disabled={working||!preview}>{c.handButton}</button></form></details>
   <details className="dealer-action"><summary>{c.take}</summary><form onSubmit={takeBack}><div className="formgrid">
    <Field label={c.first}><input required type="number" min={1} value={back.from} onChange={e=>setBack(b=>({...b,from:e.target.value}))}/></Field>
    <Field label={c.last}><input required type="number" min={1} value={back.to} onChange={e=>setBack(b=>({...b,to:e.target.value}))}/></Field>
    <Field label={c.sendTo}><select value={back.target} onChange={e=>setBack(b=>({...b,target:e.target.value}))}><option value="">{c.myStock}</option>{others.map(x=><option key={x.id} value={x.id}>{x.name}</option>)}</select></Field>
    {back.target&&<Field label={c.newPrice}><input required type="number" min={0} value={back.price} onChange={e=>setBack(b=>({...b,price:e.target.value}))}/></Field>}
    <Field label={c.note}><input maxLength={500} value={back.note} onChange={e=>setBack(b=>({...b,note:e.target.value}))}/></Field>
   </div><label className="check"><input type="checkbox" checked={back.credit} onChange={e=>setBack(b=>({...b,credit:e.target.checked}))}/> {c.creditThem(d.name)}</label><p className="muted">{c.takeNote}</p><button className="button secondary" disabled={working}>{back.target?c.move:c.returnMine}</button></form></details>
   <details className="dealer-action"><summary>{c.check}</summary><form onSubmit={stockCheck}><p>{c.expect(d.unused,d.name)}</p><div className="formgrid">
    <Field label={c.counted}><input required type="number" min={0} value={check.counted} onChange={e=>setCheck(s=>({...s,counted:e.target.value}))}/></Field>
    <Field label={c.missing}><input value={check.missing} onChange={e=>setCheck(s=>({...s,missing:e.target.value}))} placeholder={c.missingHint}/></Field>
    <Field label={c.diffReason}><select value={check.reason} onChange={e=>setCheck(s=>({...s,reason:e.target.value}))}><option value="">{c.noDiff}</option>{Object.entries(c.reasons).map(([k,v])=><option key={k} value={k}>{v}</option>)}</select></Field>
    <Field label={c.note}><input maxLength={500} value={check.note} onChange={e=>setCheck(s=>({...s,note:e.target.value}))}/></Field>
   </div>{check.missing.trim()&&!missing&&<p role="alert">{c.serialFormat}</p>}<label className="check"><input type="checkbox" checked={check.disable} disabled={!missing?.length} onChange={e=>setCheck(s=>({...s,disable:e.target.checked}))}/> {c.disableMissing}</label><p className="muted">{c.checkNote}</p><button className="button secondary" disabled={working||check.counted===''||(check.missing.trim()&&!missing)}>{c.recordCheck}</button></form></details>
   <details className="dealer-action"><summary>{c.pay}</summary><form onSubmit={payment}><div className="formgrid">
    <Field label={c.amount}><input required type="number" min={1} value={pay.amount} onChange={e=>setPay(p=>({...p,amount:e.target.value}))}/></Field>
    <Field label={c.method}><select value={pay.method} onChange={e=>setPay(p=>({...p,method:e.target.value}))}>{PAYMENT_METHODS.map(m=><option key={m}>{m}</option>)}</select></Field>
    <Field label={c.payRef}><input maxLength={160} value={pay.reference} onChange={e=>setPay(p=>({...p,reference:e.target.value}))} placeholder={c.payRefHint}/></Field>
    <Field label={c.note}><input maxLength={500} value={pay.note} onChange={e=>setPay(p=>({...p,note:e.target.value}))}/></Field>
   </div><button className="button" disabled={working||!(Number(pay.amount)>0)}>{c.recordPay}</button></form></details>
   <details className="dealer-action"><summary>{c.fix}</summary><form onSubmit={correction}><div className="formgrid">
    <Field label={c.type}><select value={fix.direction} onChange={e=>setFix(f=>({...f,direction:e.target.value}))}><option value="credit">{c.creditDealer}</option><option value="charge">{c.chargeDealer}</option></select></Field>
    <Field label={c.fixAmount}><input required type="number" min={1} value={fix.amount} onChange={e=>setFix(f=>({...f,amount:e.target.value}))}/></Field>
    <Field label={c.fixReason}><input required maxLength={500} value={fix.reason} onChange={e=>setFix(f=>({...f,reason:e.target.value}))}/></Field>
   </div><button className="button secondary" disabled={working||!(Number(fix.amount)>0)||!fix.reason.trim()}>{c.recordFix}</button></form></details>
   <details className="dealer-action"><summary>{c.edit}</summary>{edit?<form onSubmit={async e=>{e.preventDefault();if(await run(()=>api.request(at('update'),dealerBody(edit)),c.saved))setEdit(null)}}><DealerFields form={edit} set={(k,v)=>setEdit(f=>({...f,[k]:v}))} c={c}/><div className="buttons"><button className="button" disabled={working||!edit.name.trim()}>{c.save}</button><button type="button" className="button secondary" onClick={()=>setEdit(null)}>{c.cancel}</button></div></form>:<div className="buttons"><button type="button" className="button secondary" onClick={()=>setEdit({...blankDealer,...Object.fromEntries(Object.entries(d).filter(([k])=>k in blankDealer).map(([k,v])=>[k,v??'']))})}>{c.editDetails}</button><button type="button" className="button secondary" disabled={working} onClick={()=>{if(window.confirm(c.archiveConfirm(d.name)))run(()=>api.request(at('archive'),{}),c.archivedDone)}}>{c.archive}</button></div>}<p className="muted">{c.archiveNote}</p></details>
   </>}
   <h4>{c.ledger}</h4>
   <div className="tablewrap"><table><thead><tr>{c.ledgerCols.map(h=><th key={h}>{h}</th>)}</tr></thead><tbody>{d.ledger.map(e=><tr key={e.id}><td>{when(e.created)}</td><td>{c.ledgerKinds[e.kind]||e.kind}{e.reversed&&<small>{c.reversed}</small>}</td><td>{e.delta>0?'+':'−'}{mmk(Math.abs(e.delta))}</td><td>{[e.method,e.reference,e.note].filter(Boolean).join(' · ')}</td><td>{!d.archived_at&&['payment','adjustment'].includes(e.kind)&&!e.reversed&&<button type="button" className="button secondary" disabled={working} onClick={()=>reverse(e)}>{c.reverse}</button>}</td></tr>)}{!d.ledger.length&&<tr><td colSpan={5}>{c.noEntries}</td></tr>}</tbody></table></div>
   <p className="muted">{c.ledgerNote}</p>
   <h4>{c.movements}</h4>
   <div className="tablewrap"><table><thead><tr>{c.moveCols.map(h=><th key={h}>{h}</th>)}</tr></thead><tbody>{d.movements.map(m=><tr key={m.id}><td>{when(m.created)}</td><td>{c.kinds[m.kind]||m.kind}{m.note&&<small>{m.note}</small>}</td><td>{m.count}</td><td>{movementDetail(m,name,phrases)}</td></tr>)}{!d.movements.length&&<tr><td colSpan={4}>{c.noMoves}</td></tr>}</tbody></table></div>
  </div>}
 </section>
}
