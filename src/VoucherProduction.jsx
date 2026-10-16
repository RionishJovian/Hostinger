{/* NOTION-FIX RECONCILE 2026-10-16: Codex interrupted; reconciled screen (read-only audit verified) */}
import React,{useCallback,useEffect,useMemo,useRef,useState} from 'react';
import {LAYOUTS,MAGIC_TEMPLATES,PRODUCTION_STEPS,calibrationSheet,loadPrintPrefs,nextStep,paperSummary,plan,productionSheets,savePrintPrefs,serial} from './voucher-production.mjs';
import {shopSsid,ssidForSite} from './site-settings.mjs';
import QRCode from 'qrcode';
import {batchQrCodes} from './batch-link.mjs';
import {useSmeCopy} from './SMELocalization.jsx';
function Field({label,children}){return <label className="field"><span>{label}</span>{children}</label>}
const blank={package_id:'',site_id:'',quantity:40,expires_days:30,prefix:'',layout:'a4_economy',columns:5,rows:12,show_price:true,batch_qr:true,ssid:'',name:'',dealer_id:''};
const newKey=()=>'web-'+(globalThis.crypto?.randomUUID?.()||Math.random().toString(36).slice(2)+Date.now().toString(36));
function download(html,name){const url=URL.createObjectURL(new Blob([html],{type:'text/html;charset=utf-8'}));const a=document.createElement('a');a.href=url;a.download=name;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000)}
function body(form){
 const custom=form.layout==='a4_custom';
 return {package_id:form.package_id,site_id:form.site_id||null,quantity:Number(form.quantity),expires_days:Number(form.expires_days),layout:form.layout,show_price:!!form.show_price,batch_qr:form.batch_qr!==false,...(custom?{columns:Number(form.columns),rows:Number(form.rows)}:{}),...(form.prefix.trim()?{prefix:form.prefix}:{}),...(form.ssid.trim()?{ssid:form.ssid}:{})};
}
async function sheetFile(options,numbers){
 const qr=await batchQrCodes(text=>QRCode.toString(text,{type:'svg',errorCorrectionLevel:'M',margin:1}),window.location,options.job,numbers).catch(()=>({}));
 return productionSheets({...options,qr});
}
export default function VoucherProduction({api,sites=[],packages=[],business,refresh,openBatch=null,onBatchOpened}){
 const c=useSmeCopy('production');
 const [form,setForm]=useState(()=>({...blank,...loadPrintPrefs()})),[jobs,setJobs]=useState([]),[templates,setTemplates]=useState([]),[active,setActive]=useState(null),[codes,setCodes]=useState({}),[message,setMessage]=useState(''),[working,setWorking]=useState(false);
 const [confirmed,setConfirmed]=useState(false),[templateName,setTemplateName]=useState(''),[reason,setReason]=useState(''),[note,setNote]=useState(''),[dealers,setDealers]=useState([]),[handover,setHandover]=useState({dealer:'',price:''}),[loaded,setLoaded]=useState(false),[focusSheet,setFocusSheet]=useState(null),[reveal,setReveal]=useState(false);const jobPanel=useRef(null);
 const set=(k,v)=>setForm(f=>({...f,[k]:v}));
 const preview=useMemo(()=>plan(form,Number(form.quantity)),[form]);
 const job=jobs.find(j=>j.id===active)||null,items=codes[active]||null;
 const siteName=id=>sites.find(s=>s.id===id)?.name||c.businessWide,packageName=id=>packages.find(p=>p.id===id)?.name||c.fallbackPass;
 const dealerOf=id=>dealers.find(d=>d.id===id);
 const reload=useCallback(async()=>{const [j,t,d]=await Promise.all([api.request('voucher-jobs'),api.request('voucher-templates'),api.request('dealers')]);setJobs(j);setTemplates(t);setDealers(d);setLoaded(true)},[api]);
 useEffect(()=>{reload().catch(e=>setMessage(e.message))},[reload]);
 useEffect(()=>{
  if(!openBatch||!loaded)return;
  const found=jobs.find(j=>j.id===openBatch.jobId);
  if(found){setActive(found.id);setConfirmed(false);setHandover({dealer:found.settings.dealer_id||'',price:''});setFocusSheet(openBatch.sheet);setMessage(c.opened(found.ref,openBatch.sheet?` · ${found.plan.unit} ${openBatch.sheet}`:''));setReveal(true)}
  else setMessage(c.unknownBatch);
  onBatchOpened?.();
 },[openBatch,loaded,jobs,onBatchOpened]);
 useEffect(()=>{if(reveal&&jobPanel.current){jobPanel.current.scrollIntoView({block:'start'});setReveal(false)}},[reveal,active]);
 async function run(fn,done){setWorking(true);setMessage('');try{const result=await fn();await reload();if(done)setMessage(done);return result}catch(e){setMessage(e.message);return null}finally{setWorking(false)}}
 function apply(settings){setForm(f=>({...f,...Object.fromEntries(Object.entries(settings).filter(([,v])=>v!=null)),prefix:settings.prefix||'',ssid:settings.ssid||shopSsid(sites,settings.site_id||f.site_id),site_id:settings.site_id||f.site_id}));setMessage(c.applied)}
 async function createDraft(e){e.preventDefault();savePrintPrefs(form);const draft=await run(()=>api.request('voucher-jobs',{...body(form),...(form.name.trim()?{name:form.name}:{}),...(form.dealer_id?{dealer_id:form.dealer_id}:{})}),c.draftSaved);if(draft){setActive(draft.id);setConfirmed(false);setHandover({dealer:draft.settings.dealer_id||'',price:''})}}
 async function generate(){const result=await run(()=>api.request(`voucher-jobs/${job.id}/generate`,{confirm:true}));if(result){if(!result.replayed)setCodes(codes=>({...codes,[job.id]:result.items}));setMessage(result.replayed?result.message:c.generatedMsg(result.items.length));refresh?.()}}
 const sheetNumbers=job?Object.keys(job.sheets).map(Number).sort((a,b)=>a-b):[];
 const failed=sheetNumbers.filter(n=>job.sheets[n].state==='failed');
 const current=nextStep(job);
 return <section className="panel production"><div className="panelhead"><h2>{c.title}</h2></div>
  <p>{c.intro}</p>
  <ol className="production-steps">{PRODUCTION_STEPS.map((s,index)=><li key={s} className={s===current?'current':''}>{c.steps[index]}</li>)}</ol>
  {message&&<p role="status" className="callout">{message}</p>}
  <h3>{c.magic}</h3>
  <div className="buttons">{MAGIC_TEMPLATES.map(t=><button key={t.id} type="button" className="button secondary" title={c.hints[t.id]||t.hint} onClick={()=>apply(t.id==='custom'?blank:t.settings)}>{c.names[t.id]||t.name}</button>)}</div>
  <p className="muted">{c.suggest}</p>
  {templates.length>0&&<><h3>{c.myTemplates}</h3><div className="tablewrap"><table><thead><tr><th>{c.template}</th><th>{c.settings}</th><th>{c.actions}</th></tr></thead><tbody>{templates.map(t=><tr key={t.id}><td>{t.name}</td><td>{packageName(t.settings.package_id)} · {t.settings.quantity} · {c.layouts[t.settings.layout]||LAYOUTS[t.settings.layout]?.label}</td><td><div className="buttons"><button type="button" className="button secondary" onClick={()=>apply(t.settings)}>{c.use}</button><button type="button" className="button secondary" disabled={working} onClick={()=>run(()=>api.request(`voucher-templates/${t.id}/archive`,{}),c.archivedTemplate)}>{c.archive}</button></div></td></tr>)}</tbody></table></div></>}
  <form onSubmit={createDraft}><div className="formgrid">
   <Field label={c.pass}><select required value={form.package_id} onChange={e=>set('package_id',e.target.value)}><option value="">{c.choosePass}</option>{packages.map(p=><option key={p.id} value={p.id}>{p.name} · {p.price} MMK</option>)}</select></Field>
   <Field label={c.quantity}><input required type="number" min={1} max={1000} value={form.quantity} onChange={e=>set('quantity',e.target.value)}/></Field>
   <Field label={c.shop}><select value={form.site_id} onChange={e=>{const to=e.target.value;setForm(f=>({...f,site_id:to,ssid:ssidForSite(f.ssid,sites,f.site_id,to)}))}}><option value="">{c.businessWide}</option>{sites.map(s=><option key={s.id} value={s.id}>{s.name}</option>)}</select></Field>
   <Field label={c.dealer}><select value={form.dealer_id} onChange={e=>set('dealer_id',e.target.value)}><option value="">{c.notDealer}</option>{dealers.map(d=><option key={d.id} value={d.id}>{d.name}{d.short_code?` (${d.short_code})`:''}</option>)}</select></Field>
   <Field label={c.layout}><select value={form.layout} onChange={e=>set('layout',e.target.value)}>{Object.entries(LAYOUTS).map(([k,v])=><option key={k} value={k}>{c.layouts[k]||v.label}</option>)}</select></Field>
   {form.layout==='a4_custom'&&<><Field label="Columns per sheet"><input type="number" min={2} max={8} value={form.columns} onChange={e=>set('columns',e.target.value)}/></Field><Field label="Rows per sheet"><input type="number" min={4} max={16} value={form.rows} onChange={e=>set('rows',e.target.value)}/></Field></>}
   <Field label={c.redeem}><input required type="number" min={1} max={365} value={form.expires_days} onChange={e=>set('expires_days',e.target.value)}/></Field>
   <Field label={c.prefix}><input maxLength={8} pattern="[A-Za-z0-9]*" autoComplete="off" value={form.prefix} onChange={e=>set('prefix',e.target.value.toUpperCase())} placeholder={c.prefixHint}/></Field>
   <Field label={c.wifi}><input maxLength={32} value={form.ssid} onChange={e=>set('ssid',e.target.value)} placeholder={c.wifiHint}/>{shopSsid(sites,form.site_id)&&form.ssid.trim()===shopSsid(sites,form.site_id)&&<small>{c.fromShop}</small>}</Field>
   <Field label={c.jobLabel}><input maxLength={80} value={form.name} onChange={e=>set('name',e.target.value)} placeholder={c.jobHint}/></Field>
  </div>
  <label className="check"><input type="checkbox" checked={form.show_price} onChange={e=>set('show_price',e.target.checked)}/> {c.printPrice}</label>
  <label className="check"><input type="checkbox" checked={form.batch_qr!==false} onChange={e=>set('batch_qr',e.target.checked)}/> {c.batchQr}</label>
  <p className="muted">{c.preview(paperSummary(preview))}</p>
  <div className="buttons"><button className="button" disabled={working||!form.package_id||!preview}>{c.saveDraft}</button><input aria-label={c.templateName} maxLength={80} value={templateName} onChange={e=>setTemplateName(e.target.value)} placeholder={c.templateName}/><button type="button" className="button secondary" disabled={working||!form.package_id||!templateName.trim()||!preview} onClick={async()=>{if(await run(()=>api.request('voucher-templates',{name:templateName,settings:body(form)}),c.savedTemplate))setTemplateName('')}}>{c.saveTemplate}</button></div>
  </form>
  {job&&<div className="production-job" ref={jobPanel}>
   <h3>{job.ref}{job.name?' · '+job.name:''} · {job.status}</h3>
   <p>{packageName(job.package_id)} · {job.quantity} vouchers · {siteName(job.site_id)} · {(c.layouts[job.settings.layout]||LAYOUTS[job.settings.layout]?.label||'').split(' · ')[0]} · {paperSummary(job.plan)}{job.serial_start?` · Serial ${serial(job.serial_start)}–${serial(job.serial_end)}`:''}</p>
   {job.status==='draft'&&<>
    {job.calibration_required&&<div className="callout"><p><strong>{c.calibrateLead}</strong> {c.calibrate}</p><div className="buttons"><button type="button" className="button secondary" onClick={()=>download(calibrationSheet({settings:job.settings,business}),`MikroMagic-${job.ref}-calibration.html`)}>{c.downloadCal}</button><button type="button" className="button secondary" disabled={working} onClick={()=>run(()=>api.request(`voucher-jobs/${job.id}/calibration`,{}),c.calSaved)}>{c.calOk}</button></div></div>}
    <label className="check"><input type="checkbox" checked={confirmed} onChange={e=>setConfirmed(e.target.checked)}/> {c.confirm(job.quantity)}</label>
    <div className="buttons"><button type="button" className="button" disabled={working||!confirmed||job.calibration_required} onClick={generate}>{c.generate(job.quantity)}</button><button type="button" className="button secondary" disabled={working} onClick={()=>run(()=>api.request(`voucher-jobs/${job.id}/cancel`,{}),c.draftCancelled)}>{c.cancelDraft}</button></div>
   </>}
   {job.status!=='draft'&&job.status!=='cancelled'&&<>
    {items?<div className="callout"><p>{c.held(job.ref)}</p><div className="buttons"><button type="button" className="button" onClick={async()=>download(await sheetFile({job,items,business,siteName:siteName(job.site_id),dealerCode:dealerOf(job.settings.dealer_id)?.short_code},[...new Set(items.map(v=>v.sheet_no))]),`MikroMagic-${job.ref}-private-sheets.html`)}>{c.download(job.plan.unit)}</button><button type="button" className="button secondary" onClick={()=>{if(window.confirm(c.clearConfirm))setCodes(codes=>{const next={...codes};delete next[job.id];return next})}}>{c.clearScreen}</button></div></div>:job.status==='generated'&&<p className="callout">{c.gone(job.plan.unit)}</p>}
    <h4>{c.verify(job.plan.unit)}</h4>
    <div className="tablewrap"><table><thead><tr><th>{job.plan.unit==='run'?c.run:c.sheet}</th><th>{c.result}</th><th>{c.actions}</th></tr></thead><tbody>{sheetNumbers.map(n=>{const st=job.sheets[n];return <tr key={n} aria-current={n===focusSheet?'true':undefined}><td>{n}/{job.plan.sheets}</td><td>{st.state}{st.reprints?` · reprinted ${st.reprints}×`:''}{st.state==='lost'?` · ${st.disabled} unused disabled`:''}</td><td><div className="buttons">{job.status==='generated'&&st.state!=='lost'&&<><button type="button" className="button secondary" disabled={working||st.state==='printed'} onClick={()=>run(()=>api.request(`voucher-jobs/${job.id}/verify`,{sheets:[{sheet:n,result:'printed'}]}))}>{c.printedOk}</button><button type="button" className="button secondary" disabled={working||st.state==='failed'} onClick={()=>run(()=>api.request(`voucher-jobs/${job.id}/verify`,{sheets:[{sheet:n,result:'failed'}]}))}>{c.failed}</button></>}{st.state!=='lost'&&<button type="button" className="button secondary" disabled={working||!reason.trim()} onClick={()=>{if(window.confirm(c.lostConfirm(job.plan.unit,n)))run(()=>api.request(`voucher-jobs/${job.id}/sheets/${n}/lost`,{reason}),c.lostDone)}}>{c.markLost}</button>}</div></td></tr>})}</tbody></table></div>
    <Field label={c.reason}><input maxLength={500} value={reason} onChange={e=>setReason(e.target.value)} placeholder={c.reasonHint}/></Field>
    {failed.length>0&&<div className="callout"><p><strong>{c.reprintLead(job.plan.unit,failed.join(', '))}</strong> {c.reprintBody}</p><button type="button" className="button secondary" disabled={working||!items||!reason.trim()} onClick={async()=>{const r=await run(()=>api.request(`voucher-jobs/${job.id}/reprint`,{sheets:failed,reason}));if(r){download(await sheetFile({job:r,items,business,siteName:siteName(job.site_id),only:failed,reprint:true,dealerCode:dealerOf(job.settings.dealer_id)?.short_code},failed),`MikroMagic-${job.ref}-reprint.html`);setMessage(r.warning)}}}>{c.reprint(job.plan.unit)}</button></div>}
    {job.status==='verified'&&<><div className="formgrid"><Field label={c.hand}><select value={handover.dealer} onChange={e=>setHandover(h=>({...h,dealer:e.target.value}))}><option value="">{c.keep}</option>{dealers.map(d=><option key={d.id} value={d.id}>{d.name}</option>)}</select></Field>{handover.dealer&&<Field label={c.dealerPrice}><input type="number" min={0} value={handover.price} onChange={e=>setHandover(h=>({...h,price:e.target.value}))} placeholder={c.wholesale}/></Field>}<Field label={c.distNote}><input maxLength={200} value={note} onChange={e=>setNote(e.target.value)} placeholder={handover.dealer?c.stall:c.drawer}/></Field></div>
     {handover.dealer&&<p className="muted">{c.handNote(job.ref,dealerOf(handover.dealer)?.name)}</p>}
     <div className="buttons"><button type="button" className="button" disabled={working||(handover.dealer&&String(handover.price).trim()==='')} onClick={()=>run(()=>api.request(`voucher-jobs/${job.id}/distribute`,{...(note.trim()?{note}:{}),...(handover.dealer?{dealer_id:handover.dealer,unit_price:Number(handover.price),request_key:newKey()}:{dealer_id:null})}),handover.dealer?c.distributedDealer:c.distributed)}>{c.distribute}</button></div></>}
    {job.status==='distributed'&&<p>{c.distributedLine(job.settings.dealer_id&&dealerOf(job.settings.dealer_id)?c.toName(dealerOf(job.settings.dealer_id).name):'',job.distributed_note?' · '+job.distributed_note:'')}{c.counts(job.counts.unused||0,job.counts.redeemed||0,job.counts.disabled||0)}</p>}
   </>}
  </div>}
  <h3>{c.history}</h3>
  <div className="tablewrap"><table><thead><tr>{c.histCols.map(h=><th key={h}>{h}</th>)}</tr></thead><tbody>{jobs.map(j=><tr key={j.id}><td>{j.ref}<small>{j.name}</small></td><td>{packageName(j.package_id)}<small>{siteName(j.site_id)}</small></td><td>{j.quantity}<small>{Object.entries(j.counts).map(([k,v])=>`${k} ${v}`).join(' · ')}</small></td><td>{j.status}</td><td>{j.serial_start?`${serial(j.serial_start)}–${serial(j.serial_end)}`:c.assigned}</td><td><button type="button" className="button secondary" onClick={()=>{setActive(j.id);setConfirmed(false);setFocusSheet(null);setHandover({dealer:j.settings.dealer_id||'',price:''})}}>{c.open}</button></td></tr>)}{!jobs.length&&<tr><td colSpan={6}>{c.none}</td></tr>}</tbody></table></div>
  <p className="muted">{c.foot}</p>
 </section>
}
