import React from 'react';
import {ArrowRight,Broadcast as Gateway,Buildings,Ticket,UsersThree,WarningCircle,WifiHigh} from '@phosphor-icons/react';
import {useSMELocalization} from './SMELocalization.jsx';

function SummaryCard({icon:Icon,label,value,note,onClick}){
 const content=<><span className="overview-stat-icon"><Icon size={20}/></span><span className="overview-stat-label">{label}</span><strong>{value}</strong><small>{note}</small></>;
 return onClick?<button className="overview-stat" onClick={onClick}>{content}<span className="overview-stat-link"><ArrowRight size={16}/></span></button>:<div className="overview-stat">{content}</div>;
}

export default function OverviewHealth({sites=[],routers=[],devices=[],vouchers=[],pendingPayments,navigate}){
 const {t:message}=useSMELocalization();
 const t={};
 for(const key of ['health','question','attention','summary','shops','gateways','aps','customers','vouchers','notConnected','unable','noRouter','unverified','siteNeeded','payments','paymentsHint','noKnown','routerAction','siteAction','paymentAction','countNote','apNote','customerNote','voucherNote','unavailable'])t[key]=message('overview',key);
 const noRouter=routers.length===0;
 const apCount=devices.filter(device=>device.kind==='access_point').length;
 const issues=[];
 if(noRouter)issues.push({message:sites.length===0?`${t.siteNeeded} ${t.noRouter}`:t.noRouter,action:sites.length?t.routerAction:t.siteAction,page:sites.length?'Routers':'Sites'});
 else if(routers.every(router=>router.connection_state!=='connected'))issues.push({message:t.unverified,action:t.routerAction,page:'Routers'});
 if(Number.isFinite(pendingPayments)&&pendingPayments>0)issues.push({message:t.payments(pendingPayments),detail:t.paymentsHint,action:t.paymentAction,page:'Payments'});
 return <section className="overview-priorities" aria-label={t.health}>
  <div className="overview-health panel">
   <div><span className="overview-kicker"><WifiHigh size={18}/>{t.health}</span><h2>{t.question}</h2><div className="overview-health-state"><span className={'overview-health-dot '+(noRouter?'is-offline':'is-unknown')}/><strong>{noRouter?t.notConnected:t.unable}</strong>{noRouter&&<><span>·</span><strong>{t.unable}</strong></>}</div><p>{noRouter?t.noRouter:t.unverified}</p></div>
  </div>
  <section className="overview-attention panel" aria-labelledby="overview-attention-title">
   <div className="panelhead"><h2 id="overview-attention-title"><WarningCircle size={20}/>{t.attention}</h2></div>
   {issues.length?issues.map((issue,index)=><div className="overview-issue" key={`${issue.page}-${index}`}><div><strong>{issue.message}</strong>{issue.detail&&<small>{issue.detail}</small>}</div><button type="button" className="button secondary" onClick={()=>navigate(issue.page)}>{issue.action}<ArrowRight size={16}/></button></div>):<p className="muted">{t.noKnown}</p>}
  </section>
  <section className="overview-network panel" aria-labelledby="overview-network-title">
   <div className="panelhead"><h2 id="overview-network-title">{t.summary}</h2></div>
   <div className="overview-stat-grid">
    <SummaryCard icon={Buildings} label={t.shops} value={sites.length} note={t.countNote} onClick={()=>navigate('Sites')}/>
    <SummaryCard icon={Gateway} label={t.gateways} value={routers.length} note={t.countNote} onClick={()=>navigate('Routers')}/>
    <SummaryCard icon={WifiHigh} label={t.aps} value={apCount} note={t.apNote} onClick={()=>navigate('Network')}/>
    <SummaryCard icon={UsersThree} label={t.customers} value={t.unavailable} note={t.customerNote}/>
    <SummaryCard icon={Ticket} label={t.vouchers} value={vouchers.length} note={t.voucherNote} onClick={()=>navigate('Vouchers')}/>
   </div>
  </section>
 </section>;
}
