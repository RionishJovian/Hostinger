import React,{useMemo,useRef,useState} from 'react';
import {prioritizePackages} from './quick-voucher.mjs';
import {shopSsid} from './site-settings.mjs';
import {useSmeCopy} from './SMELocalization.jsx';

export default function QuickVoucher({packages=[],sites=[],vouchers=[],act,busy,selectedSite=''}){
 const c=useSmeCopy('quickVoucher');
 const choices=useMemo(()=>prioritizePackages(packages,vouchers),[packages,vouchers]);
 const [packageId,setPackageId]=useState(''),[siteId,setSiteId]=useState(selectedSite||''),[issued,setIssued]=useState(null),[message,setMessage]=useState('');const attempt=useRef(null);
 const selected=choices.some(p=>p.id===packageId)?packageId:choices[0]?.id||'';
 async function generate(e){
  e.preventDefault();setMessage('');
  const fingerprint=JSON.stringify({site_id:siteId||null,package_id:selected,expires_days:30});
  if(attempt.current?.fingerprint!==fingerprint)attempt.current={fingerprint,key:crypto.randomUUID()};
  const result=await act('vouchers',{site_id:siteId||null,package_id:selected,expires_days:30,request_key:attempt.current.key});
  if(result){attempt.current=null;setIssued(result)}
 }
 async function share(){
  if(!issued?.code)return;
  const wifi=shopSsid(sites,issued.site_id),text=`MikroMagic Wi-Fi voucher ${issued.code}${wifi?` · Wi-Fi: ${wifi}`:''}`;
  try{
   if(navigator.share)await navigator.share({title:c.shareTitle,text});
   else if(navigator.clipboard?.writeText){await navigator.clipboard.writeText(text);setMessage(c.copied)}
   else setMessage(c.shareUnavailable);
  }catch(error){if(error?.name!=='AbortError')setMessage(c.shareFailed)}
 }
 const commonCount=choices[0]?.quickVoucherCount||0,recentPackage=choices.reduce((best,p)=>p.quickVoucherRecent>(best?.quickVoucherRecent||0)?p:best,null),recentId=recentPackage?.quickVoucherRecent?recentPackage.id:null;
 return <section className="panel quickvoucher" aria-labelledby="quick-voucher-title">
  <div className="panelhead"><h2 id="quick-voucher-title">{c.title}</h2></div>
  <p>{c.intro}</p>
  {!choices.length?<p className="callout">{c.empty}</p>:<form onSubmit={generate}>
   <div className="formgrid">
    <label className="field"><span>{c.pass}</span><select aria-label={c.pass} required value={selected} onChange={e=>{setPackageId(e.target.value);setIssued(null);attempt.current=null}}>
     {choices.map((p,index)=><option key={p.id} value={p.id}>{p.name}{p.quickVoucherCount>0&&p.quickVoucherCount===commonCount?' · '+c.common:''}{p.id===recentId?' · '+c.recent:''}{index===0&&p.quickVoucherCount===0&&p.id!==recentId?' · '+c.suggested:''}</option>)}
    </select></label>
    <label className="field"><span>{c.shop}</span><select aria-label={c.shop} value={siteId} onChange={e=>{setSiteId(e.target.value);setIssued(null);attempt.current=null}}><option value="">{c.businessWide}</option>{sites.map(site=><option key={site.id} value={site.id}>{site.name}</option>)}</select></label>
   </div>
   <button className="button" disabled={busy||!selected}>{c.generate}</button>
  </form>}
  {message&&<p role="status" className="muted">{message}</p>}
  {issued&&<div className="voucher quickvoucher-result" aria-live="polite">
   <small>{issued.policy?.name||c.shareTitle} · {c.generated}</small>
   {issued.code?<><strong aria-label="Voucher code">{issued.code}</strong>{shopSsid(sites,issued.site_id)&&<p>{c.wifi}: {shopSsid(sites,issued.site_id)}</p>}<p>{c.redeemBy(new Date(issued.expires*1000).toLocaleString())}</p><div className="buttons quickvoucher-actions"><button type="button" className="button secondary" onClick={()=>window.print()}>{c.print}</button><button type="button" className="button secondary" onClick={share}>{c.share}</button></div></>:<p>{issued.message||c.already}</p>}
   {issued.code&&<div className="callout quickvoucher-qr"><button type="button" className="button secondary" disabled aria-describedby="quick-voucher-qr-note">{c.qr}</button><p id="quick-voucher-qr-note">{c.qrNote}</p></div>}
   <small>{c.footnote}</small>
  </div>}
  <p className="muted">{c.note}</p>
 </section>
}
