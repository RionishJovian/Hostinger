import React,{useMemo,useRef,useState} from 'react';
import {prioritizePackages} from './quick-voucher.mjs';

export default function QuickVoucher({packages=[],sites=[],vouchers=[],act,busy,selectedSite=''}){
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
  const text=`MikroMagic Wi-Fi voucher ${issued.code}`;
  try{
   if(navigator.share)await navigator.share({title:'Wi-Fi voucher',text});
   else if(navigator.clipboard?.writeText){await navigator.clipboard.writeText(text);setMessage('Voucher copied. Share it only with its intended recipient.')}
   else setMessage('Sharing is unavailable in this browser. Select and copy the code above.');
  }catch(error){if(error?.name!=='AbortError')setMessage('Could not share this voucher. The code remains available above.')}
 }
 const commonCount=choices[0]?.quickVoucherCount||0,recentPackage=choices.reduce((best,p)=>p.quickVoucherRecent>(best?.quickVoucherRecent||0)?p:best,null),recentId=recentPackage?.quickVoucherRecent?recentPackage.id:null;
 return <section className="panel quickvoucher" aria-labelledby="quick-voucher-title">
  <div className="panelhead"><h2 id="quick-voucher-title">Quick Voucher</h2></div>
  <p>Choose a saved Wi-Fi package to issue one voucher. The code is shown once; package and site access are checked by your account.</p>
  {!choices.length?<p className="callout">Create a Wi-Fi package before issuing a voucher.</p>:<form onSubmit={generate}>
   <div className="formgrid">
    <label className="field"><span>Wi-Fi package</span><select aria-label="Wi-Fi package" required value={selected} onChange={e=>{setPackageId(e.target.value);setIssued(null);attempt.current=null}}>
     {choices.map((p,index)=><option key={p.id} value={p.id}>{p.name}{p.quickVoucherCount>0&&p.quickVoucherCount===commonCount?' · Common':''}{p.id===recentId?' · Recent':''}{index===0&&p.quickVoucherCount===0&&p.id!==recentId?' · Suggested':''}</option>)}
    </select></label>
    <label className="field"><span>Site</span><select aria-label="Site" value={siteId} onChange={e=>{setSiteId(e.target.value);setIssued(null);attempt.current=null}}><option value="">Business-wide</option>{sites.map(site=><option key={site.id} value={site.id}>{site.name}</option>)}</select></label>
   </div>
   <button className="button" disabled={busy||!selected}>Generate voucher</button>
  </form>}
  {message&&<p role="status" className="muted">{message}</p>}
  {issued&&<div className="voucher quickvoucher-result" aria-live="polite">
   <small>{issued.policy?.name||'Wi-Fi voucher'} · Generated</small>
   {issued.code?<><strong aria-label="Voucher code">{issued.code}</strong><p>Redeem by {new Date(issued.expires*1000).toLocaleString()}</p><div className="buttons quickvoucher-actions"><button type="button" className="button secondary" onClick={()=>window.print()}>Print</button><button type="button" className="button secondary" onClick={share}>Share</button></div></>:<p>{issued.message||'This code was already issued and can no longer be shown. Check voucher inventory.'}</p>}
   {issued.code&&<div className="callout quickvoucher-qr"><button type="button" className="button secondary" disabled aria-describedby="quick-voucher-qr-note">QR unavailable — portal deployment pending</button><p id="quick-voucher-qr-note">A verified site-specific guest portal address is not available. No QR is shown; scanning must not activate a voucher.</p></div>}
   <small>Generated · not marked sold · MikroTik activation is unverified. Internet access is not confirmed.</small>
  </div>}
  <p className="muted">Issuing creates a voucher record only. Payment/sale and MikroTik activation are tracked separately.</p>
 </section>
}
