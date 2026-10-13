import React from 'react';
import {ArrowRight,Broadcast as Gateway,Buildings,Coins,HardDrives,Ticket,UsersThree,WarningCircle,WifiHigh} from '@phosphor-icons/react';
import {useSMELocalization} from './SMELocalization.jsx';

function SummaryCard({icon:Icon,label,value,note,onClick}){
 const content=<><span className="overview-stat-icon"><Icon size={20}/></span><span className="overview-stat-label">{label}</span><strong>{value}</strong><small>{note}</small></>;
 return onClick?<button className="overview-stat" onClick={onClick}>{content}<span className="overview-stat-link"><ArrowRight size={16}/></span></button>:<div className="overview-stat">{content}</div>;
}

function useOverviewText(){
 const {t:message}=useSMELocalization();
 const t={};
 for(const key of ['health','question','attention','summary','shops','gateways','switches','aps','customers','vouchers','notConnected','unable','connected','noRouter','unverified','connectedBody','siteNeeded','payments','paymentsHint','noKnown','routerAction','siteAction','paymentAction','networkAction','maintenance','maintenanceHint','getHelp','getHelpHint','countNote','apNote','switchNote','customerNote','voucherNote','unavailable','netCollections','revenueNote'])t[key]=message('overview',key);
 return t;
}

function routerConnectionTone(routers){
 const fresh=routers.some(router=>router.connection_state==='connected'||router.connection_verified);
 const ever=routers.some(router=>router.lifecycle_state==='connected'||router.management_read_verified_at||router.connection_state==='connected'||router.connection_verified);
 if(fresh)return 'connected';
 if(ever||routers.length)return 'unable';
 return 'offline';
}

export default function OverviewHealth({sites=[],routers=[],pendingPayments,navigate}){
 const t=useOverviewText();
 const noRouter=routers.length===0;
 const tone=routerConnectionTone(routers);
 const fix=noRouter&&!sites.length?{message:`${t.siteNeeded} ${t.noRouter}`,action:t.siteAction,page:'Sites'}:tone==='connected'?{message:t.connectedBody,action:t.routerAction,page:'Routers'}:{message:noRouter?t.noRouter:t.unverified,action:t.routerAction,page:'Routers'};
 const healthLabel=noRouter?t.notConnected:tone==='connected'?t.connected:t.unable;
 const healthDot=noRouter?'is-offline':tone==='connected'?'is-online':'is-unknown';
 const issues=[];
 const now=Date.now()/1000;
 for(const site of sites)if(site.maintenance_until>now)issues.push({message:t.maintenance(site.name,new Date(site.maintenance_until*1000).toLocaleTimeString('en-GB',{timeZone:site.timezone,hour:'2-digit',minute:'2-digit'})),detail:t.maintenanceHint,action:t.siteAction,page:'Sites'});
 if(Number.isFinite(pendingPayments)&&pendingPayments>0)issues.push({message:t.payments(pendingPayments),detail:t.paymentsHint,action:t.paymentAction,page:'Payments'});
 return <section className="overview-priorities" aria-label={t.health}>
  <div className="overview-health panel">
   <div><span className="overview-kicker"><WifiHigh size={18}/>{t.health}</span><h2>{t.question}</h2><div className="overview-health-state"><span className={'overview-health-dot '+healthDot}/><strong>{healthLabel}</strong></div><p>{fix.message}</p><div className="buttons"><button type="button" className="button" onClick={()=>navigate(fix.page)}>{fix.action}<ArrowRight size={16}/></button><button type="button" className="button secondary" title={t.getHelpHint} onClick={()=>navigate('Get help')}>{t.getHelp}</button></div></div>
  </div>
  <section className="overview-attention panel" aria-labelledby="overview-attention-title">
   <div className="panelhead"><h2 id="overview-attention-title"><WarningCircle size={20}/>{t.attention}</h2></div>
   {issues.length?issues.map((issue,index)=><div className="overview-issue" key={`${issue.page}-${index}`}><div><strong>{issue.message}</strong>{issue.detail&&<small>{issue.detail}</small>}</div><button type="button" className="button secondary" onClick={()=>navigate(issue.page)}>{issue.action}<ArrowRight size={16}/></button></div>):<p className="muted">{t.noKnown}</p>}
  </section>
 </section>;
}

export function OverviewNetwork({sites=[],routers=[],devices=[],vouchers=[],netCollections,sessionSummary,navigate}){
 const t=useOverviewText();
 const apCount=devices.filter(device=>device.kind==='access_point').length;
 const switchCount=devices.filter(device=>device.kind==='switch').length;
 const sessions=sessionSummary||{};
 const customersVerified=sessions.status==='verified'&&Number.isFinite(sessions.active_count);
 const customersValue=customersVerified?sessions.active_count:t.unavailable;
 const customersNote=customersVerified?(sessions.detail||t.customerNote):(sessions.detail||t.customerNote);
 return <section className="overview-network panel" aria-labelledby="overview-network-title">
  <div className="panelhead"><h2 id="overview-network-title">{t.summary}</h2></div>
  <div className="overview-stat-grid">
   <SummaryCard icon={Buildings} label={t.shops} value={sites.length} note={t.countNote} onClick={()=>navigate('Sites')}/>
   <SummaryCard icon={Gateway} label={t.gateways} value={routers.length} note={t.countNote} onClick={()=>navigate('Routers')}/>
   <SummaryCard icon={HardDrives} label={t.switches} value={switchCount} note={t.switchNote} onClick={()=>navigate('Network')}/>
   <SummaryCard icon={WifiHigh} label={t.aps} value={apCount} note={t.apNote} onClick={()=>navigate('Network')}/>
   <SummaryCard icon={UsersThree} label={t.customers} value={customersValue} note={customersNote} onClick={()=>navigate('Routers')}/>
   <SummaryCard icon={Ticket} label={t.vouchers} value={vouchers.length} note={t.voucherNote} onClick={()=>navigate('Vouchers')}/>
   <SummaryCard icon={Coins} label={t.netCollections} value={netCollections} note={t.revenueNote} onClick={()=>navigate('Revenue')}/>
  </div>
 </section>;
}
