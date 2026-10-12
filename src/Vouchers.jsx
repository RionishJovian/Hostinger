import React,{useRef,useState} from 'react';
import {VoucherPayment} from './VoucherPayments.jsx';
import {saleLabel} from './voucher-sales.mjs';
import {passServiceName} from './sme-terms.mjs';
import {useSmeCopy,useSmeFormat} from './SMELocalization.jsx';
function Field({label,children}){return <label className="field"><span>{label}</span>{children}</label>}
function VoucherActions({v,reason,setReason,act,busy}){
 const c=useSmeCopy('vouchers');
 const id='vouchers/'+v.id,why=reason.trim();
 return <>{v.status==='disabled'&&<small>{c.disabled(v.disabled_reason)}</small>}<Field label={c.reasonFor(v.code_hint)}><input maxLength={1000} value={reason} onChange={e=>setReason(e.target.value)}/></Field><div className="buttons">
  {['unused','redeemed'].includes(v.status)&&<button className="button secondary" disabled={busy||!why} onClick={()=>act(id+'/disable',{reason})}>{c.disable}</button>}
  {v.status==='disabled'&&<button className="button secondary" disabled={busy} onClick={()=>act(id+'/enable',{})}>{c.enable}</button>}
  {['unused','expired'].includes(v.status)&&!v.sale&&<button className="button secondary" disabled={busy} onClick={()=>{if(window.confirm(c.deleteConfirm))act(id+'/delete',{})}}>{c.deleteUnused}</button>}
  <button className="button secondary" disabled={busy||!why} onClick={()=>{if(window.confirm(c.revokeConfirm))act(id+'/revoke',{reason})}}>{v.redeemed_at?c.revokePass:c.revoke}</button>
 </div></>}
export function VoucherInventory({sites=[],packages,vouchers,act,busy,view='all'}){
 const c=useSmeCopy('vouchers');const {when}=useSmeFormat();
 const [site,setSite]=useState('');
 const [selected,setSelected]=useState(''),[days,setDays]=useState(30),[issued,setIssued]=useState(null),[reasons,setReasons]=useState({});const attempt=useRef(null);
 const [review,setReview]=useState('');const reviewed=vouchers.find(v=>v.id===review);
 const [prefix,setPrefix]=useState(''),[custom,setCustom]=useState('');const vip=!!packages.find(p=>p.id===selected)?.vip;
 const redeemed=vouchers.filter(v=>v.redeemed_at).length;
 const issue=view!=='list',list=view!=='issue';
 const status=v=>c.status[v]||v;
 return <>
  <div className="callout"><strong>{c.calloutLead}</strong> {c.callout}</div>
  {list&&<div className="metrics"><div className="metric"><small>{c.generated}</small><strong>{vouchers.length}</strong></div><div className="metric"><small>{c.redeemed}</small><strong>{redeemed}</strong></div><div className="metric"><small>{c.rate}</small><strong>{vouchers.length?Math.round(redeemed/vouchers.length*100)+'%':'—'}</strong></div></div>}
  {issue&&<section className="panel"><div className="panelhead"><h2>{c.issueTitle}</h2></div><p>{c.issueIntro}</p><form onSubmit={async e=>{e.preventDefault();const fields={site_id:site||null,package_id:selected,expires_days:days,...(vip&&custom.trim()?{custom_code:custom}:prefix.trim()?{prefix}:{})};const fingerprint=JSON.stringify(fields);if(attempt.current?.fingerprint!==fingerprint)attempt.current={fingerprint,key:crypto.randomUUID()};const result=await act('vouchers',{...fields,request_key:attempt.current.key});if(result){attempt.current=null;setIssued(result)}}}><div className="formgrid"><Field label={c.shop}><select value={site} onChange={e=>setSite(e.target.value)}><option value="">{c.businessWide}</option>{sites.map(s=><option key={s.id} value={s.id}>{s.name}</option>)}</select></Field><Field label={c.pass}><select required value={selected} onChange={e=>setSelected(e.target.value)}><option value="">{c.selectPass}</option>{packages.map(p=><option key={p.id} value={p.id}>{p.name} · {passServiceName(p.service)}</option>)}</select></Field><Field label={c.redeemDays}><input type="number" min={1} max={365} required value={days} onChange={e=>setDays(Number(e.target.value))}/></Field><Field label={c.prefix}><input maxLength={8} pattern="[A-Za-z0-9]*" autoComplete="off" disabled={vip&&!!custom.trim()} value={prefix} onChange={e=>setPrefix(e.target.value.toUpperCase())} placeholder={c.prefixHint}/></Field>{vip&&<Field label={c.vip}><input minLength={6} maxLength={32} autoComplete="off" spellCheck={false} value={custom} onChange={e=>setCustom(e.target.value.toUpperCase())} placeholder={c.vipHint}/></Field>}</div><p className="muted">{c.codeHelp}{vip?c.vipHelp:''}</p><button className="button" disabled={busy||!selected}>{c.generate}</button></form><p className="muted">{c.once}</p>{issued&&<div className="voucher"><small>{issued.policy.name}</small>{issued.code?<><strong>{issued.code}</strong><p>{c.redeemBefore(when(issued.expires))}</p><button className="button secondary" onClick={()=>window.print()}>{c.print}</button></>:<p>{issued.message}</p>}<small>{c.generatedOnly}</small></div>}<div className="callout">{c.revenue}{view==='issue'?c.revenueWhere:c.revenueInventory}.</div></section>}
  {list&&<><section className="panel"><div className="panelhead"><h2>{c.inventory}</h2></div><div className="tablewrap"><table><thead><tr>{[c.colCode,c.colStatus,c.colDeadline,c.colPayment,c.colActions].map(h=><th key={h}>{h}</th>)}</tr></thead><tbody>{vouchers.map(v=><tr key={v.id}><td>{v.code_prefix?v.code_prefix+'-':''}•••• {v.code_hint}<small>{v.policy.name}{v.serial_no!=null?' · SN '+String(v.serial_no).padStart(6,'0'):''}</small><small>{sites.find(s=>s.id===v.site_id)?.name||v.site_id||c.businessWide}</small><small>{v.id}</small></td><td>{status(v.status)}<small>{c.activation}</small></td><td>{when(v.expires)}</td><td><small>{saleLabel(v.sale)}{v.cancelled_sales?.length?c.cancelled(v.cancelled_sales.length):''}</small><button className="button secondary" onClick={()=>setReview(v.id)}>{c.openSale}</button></td><td>{v.status!=='revoked'?<VoucherActions v={v} reason={reasons[v.id]||''} setReason={value=>setReasons({...reasons,[v.id]:value})} act={act} busy={busy}/>:v.reason}{v.router_sync&&<small>{c.pending(v.router_sync)}</small>}</td></tr>)}{!vouchers.length&&<tr><td colSpan={5}>{c.empty}</td></tr>}</tbody></table></div></section>{reviewed&&<VoucherPayment key={reviewed.id} voucher={reviewed} act={act} busy={busy}/>}</>}
 </>
}
export function RedeemVoucher({act,busy,go,siteId=null}){
 const [code,setCode]=useState('');return <section className="voucher-redeem"><h3>Already have a voucher?</h3><form onSubmit={async e=>{e.preventDefault();if(await act('vouchers/redeem',{code,site_id:siteId})){setCode('');go('My access')}}}><Field label="Voucher code"><input required minLength={6} maxLength={64} autoComplete="off" spellCheck={false} value={code} onChange={e=>setCode(e.target.value.toUpperCase())} placeholder="Enter the complete code"/></Field><button className="button" disabled={busy||!code.trim()}>Redeem voucher</button></form><p className="muted">Redemption creates your stored pass. Internet and playback access await the shop's router.</p></section>
}
