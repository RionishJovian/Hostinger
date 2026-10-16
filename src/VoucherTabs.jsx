{/* NOTION-FIX RECONCILE 2026-10-16: Codex interrupted; reconciled screen (read-only audit verified) */}
import React,{useState} from 'react';
// Inactive tabs stay mounted: a just-issued code exists only in the page's memory.
export default function VoucherTabs({tabs,initial,label}){
 const shown=tabs.filter(Boolean),[tab,setTab]=useState(shown.some(([id])=>id===initial)?initial:shown[0]?.[0]);
 return <>
  <div className="tabs voucher-tabs" role="tablist" aria-label={label}>{shown.map(([id,name])=><button key={id} type="button" role="tab" id={'voucher-tab-'+id} aria-controls={'voucher-panel-'+id} aria-selected={tab===id} className={tab===id?'selected':''} onClick={()=>setTab(id)}>{name}</button>)}</div>
  {shown.map(([id,,content])=><div key={id} role="tabpanel" id={'voucher-panel-'+id} aria-labelledby={'voucher-tab-'+id} hidden={tab!==id}>{content}</div>)}
 </>
}
