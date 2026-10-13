import React,{useMemo,useState} from 'react';
import {useSmeCopy} from './SMELocalization.jsx';

const Field=({label,children})=><label className="field"><span>{label}</span>{children}</label>;
const EMPTY={site_id:'',kind:'switch',name:'',vendor:'',model:'',serial_or_mac:'',location:'',firmware:''};
const DEFAULT_LIMITS={switch:1,access_point:5};

function kindLimit(devices,kind){
 const sample=devices.find(d=>d.kind===kind);
 return Number.isFinite(sample?.site_limit)?sample.site_limit:DEFAULT_LIMITS[kind];
}

export default function ManagedDevices({sites=[],devices=[],act,busy}){
 const c=useSmeCopy('networkDevices');
 const [form,setForm]=useState(EMPTY);
 const [filterSite,setFilterSite]=useState('');
 const siteName=id=>sites.find(s=>s.id===id)?.name||id;
 const rows=useMemo(()=>devices.filter(d=>!filterSite||d.site_id===filterSite),[devices,filterSite]);
 const countsFor=siteId=>{
  const scoped=devices.filter(d=>d.site_id===siteId);
  return {switch:scoped.filter(d=>d.kind==='switch').length,access_point:scoped.filter(d=>d.kind==='access_point').length};
 };
 const selectedCounts=form.site_id?countsFor(form.site_id):{switch:0,access_point:0};
 const switchLimit=kindLimit(devices,'switch');
 const apLimit=kindLimit(devices,'access_point');
 async function submit(e){
  e.preventDefault();
  const body={...form,serial_or_mac:form.serial_or_mac||null};
  const ok=await act('site-devices',body);
  if(ok)setForm(f=>({...EMPTY,site_id:f.site_id,kind:f.kind}));
 }
 return <>
  <section className="panel">
   <div className="panelhead"><h2>{c.title}</h2></div>
   <p>{c.intro}</p>
   <p className="muted">{c.honesty}</p>
   <div className="callout">{c.poeNote}</div>
   <p className="muted">{c.limitsNote(switchLimit,apLimit)}</p>
   <label className="field"><span>{c.filterShop}</span>
    <select value={filterSite} disabled={busy} onChange={e=>setFilterSite(e.target.value)}>
     <option value="">{c.allShops}</option>
     {sites.map(s=><option key={s.id} value={s.id}>{s.name}</option>)}
    </select>
   </label>
   <div className="tablewrap"><table><thead><tr>{c.heads.map(h=><th key={h}>{h}</th>)}</tr></thead><tbody>
    {rows.length?rows.map(d=><tr key={d.id}>
     <td>{siteName(d.site_id)}</td>
     <td>{d.kind==='switch'?c.kindSwitch:c.kindAp}</td>
     <td>{d.name}<small>{[d.vendor,d.model].filter(Boolean).join(' · ')}</small></td>
     <td>{d.location||c.locationEmpty}<small>{d.serial_or_mac||c.serialEmpty}</small></td>
     <td><span className="pill warn">{c.unverified}</span><small>{c.ownerReported}</small></td>
    </tr>):<tr><td colSpan={c.heads.length}>{c.empty}</td></tr>}
   </tbody></table></div>
  </section>
  <section className="panel">
   <h2>{c.registerTitle}</h2>
   {!sites.length?<p>{c.needShop}</p>:<form onSubmit={submit}>
    <div className="formgrid">
     <Field label={c.shop}><select required value={form.site_id} disabled={busy} onChange={e=>setForm({...form,site_id:e.target.value})}><option value="">{c.chooseShop}</option>{sites.map(s=><option key={s.id} value={s.id}>{s.name}</option>)}</select></Field>
     <Field label={c.kind}><select value={form.kind} disabled={busy} onChange={e=>setForm({...form,kind:e.target.value})}><option value="switch">{c.kindSwitch}</option><option value="access_point">{c.kindAp}</option></select></Field>
     <Field label={c.name}><input required maxLength={120} value={form.name} disabled={busy} onChange={e=>setForm({...form,name:e.target.value})}/></Field>
     <Field label={c.vendor}><input required maxLength={120} value={form.vendor} disabled={busy} onChange={e=>setForm({...form,vendor:e.target.value})}/></Field>
     <Field label={c.model}><input required maxLength={120} value={form.model} disabled={busy} onChange={e=>setForm({...form,model:e.target.value})}/></Field>
     <Field label={c.serial}><input maxLength={120} value={form.serial_or_mac} disabled={busy} onChange={e=>setForm({...form,serial_or_mac:e.target.value})}/></Field>
     <Field label={c.location}><input maxLength={160} value={form.location} disabled={busy} onChange={e=>setForm({...form,location:e.target.value})}/></Field>
     <Field label={c.firmware}><input maxLength={80} value={form.firmware} disabled={busy} onChange={e=>setForm({...form,firmware:e.target.value})}/></Field>
    </div>
    {form.site_id&&<p className="muted">{c.usage(selectedCounts.switch,switchLimit,selectedCounts.access_point,apLimit)}</p>}
    <button className="button" disabled={busy||!sites.length}>{c.register}</button>
   </form>}
   <p className="muted">{c.registerNote}</p>
  </section>
 </>;
}
