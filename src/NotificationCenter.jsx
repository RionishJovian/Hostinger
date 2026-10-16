import React,{useCallback,useEffect,useState} from 'react';
import {useSMELocalization,useSmeFormat} from './SMELocalization.jsx';
import {formatMmk,formatSmeDateTime} from './sme-format.mjs';
function Panel({title,children}){return <section className="panel"><div className="panelhead"><h2>{title}</h2></div>{children}</section>}
function Metric({title,value}){return <div className="metric"><small>{title}</small><strong>{value}</strong></div>}
export function notificationText(t,x,language='en'){
 const when=seconds=>seconds?formatSmeDateTime(seconds,language):'';
 const p={...x.params,router:x.params.router||t('notifications','someRouter'),site:x.params.site||t('notifications','someSite'),scope:t('notifications','scopes')[x.params.scope]||x.params.scope,time:when(x.params.planned_end)};
 const text=t('notifications','kinds')[x.kind];return text?text(p,x.count):x.kind;
}
export function NotificationCenter({api,go,onChange}){
 const {t,language}=useSMELocalization();const {when}=useSmeFormat();const n=k=>t('notifications',k);
 const [data,setData]=useState(null),[prefs,setPrefs]=useState(null),[busy,setBusy]=useState(false),[notice,setNotice]=useState('');
 const apply=useCallback(r=>{setData(r);setPrefs(r.preferences);onChange?.(r)},[onChange]);
 const load=useCallback(()=>api.request('notifications').then(apply).catch(e=>setNotice(e.message)),[api,apply]);
 useEffect(()=>{load()},[load]);
 async function run(path,body){setBusy(true);setNotice('');try{apply(await api.request(path,body))}catch(e){setNotice(e.message);load()}finally{setBusy(false)}}
 const read=items=>run('notifications/read',{items:items.slice(0,100).map(x=>({key:x.key,version:x.version}))});
 if(!data)return <Panel title={n('title')}><p role={notice?'alert':'status'}>{notice||'…'}</p></Panel>;
 const unread=data.items.filter(x=>!x.read);
 return <>
  <Panel title={n('title')}>
   <p className="muted">{n('inApp')}</p>
   {notice&&<p role="alert">{notice}</p>}
   {data.items.length?<ul className="notification-list">{data.items.map(x=><li key={x.key} className={'notification '+x.level+(x.read?' read':'')}>
    <div className="notification-head"><span className={'pill '+(x.level==='critical'?'critical':x.level==='attention'?'warn':'')}>{n(x.level)}</span>{!x.read&&<b className="count">{n('newBadge')}</b>}<small className="muted">{when(x.updated)}</small></div>
    <p>{notificationText(t,x,language)}</p>
    {x.params.root_cause&&<small>{n(x.params.root_cause_confirmed?'rootConfirmed':'rootSuspected')}: {x.params.root_cause}</small>}
    {x.params.expected_reason&&<small>{n('expected')}</small>}
    <div className="buttons"><button className="button secondary" onClick={()=>go(x.page)}>{n('open')}</button>{!x.read&&<button className="button secondary" disabled={busy} onClick={()=>read([x])}>{n('markRead')}</button>}</div>
   </li>)}</ul>:<p>{n('empty')}</p>}
   {data.hidden>0&&<p className="muted">{n('hidden')(data.hidden)}</p>}
   {unread.length>0&&<button className="button" disabled={busy} onClick={()=>read(unread)}>{n('markAllRead')}</button>}
  </Panel>
  <Panel title={n('settings')}>
   <form className="notification-settings" onSubmit={e=>{e.preventDefault();run('notifications/preferences',{expected_revision:prefs.revision,level:prefs.level,daily_summary:prefs.daily_summary})}}>
    <label>{n('show')}<select value={prefs.level} onChange={e=>setPrefs({...prefs,level:e.target.value})}><option value="critical">{n('levelCritical')}</option><option value="attention">{n('levelAttention')}</option><option value="all">{n('levelAll')}</option></select></label>
    <label>{n('summaryLabel')}<select value={prefs.daily_summary} onChange={e=>setPrefs({...prefs,daily_summary:e.target.value})}><option value="daily">{n('summaryDaily')}</option><option value="important">{n('summaryImportant')}</option><option value="off">{n('summaryOff')}</option></select></label>
    <button className="button" disabled={busy}>{n('save')}</button>
   </form>
  </Panel>
 </>;
}
export function DailySummary({api,go}){
 const {t,language}=useSMELocalization();const n=k=>t('notifications',k);const [d,setD]=useState(null);
 useEffect(()=>{let active=true;api.request('notifications/daily-summary').then(r=>{if(active)setD(r)}).catch(()=>{});return ()=>{active=false}},[api]);
 if(!d?.shown)return null;
 const money=(n,c)=>c&&c!=='MMK'?`${Number(n).toLocaleString(language==='my'?'my-MM':'en')} ${c}`:formatMmk(n,language);
 return <Panel title={n('summaryTitle')(d.date)}>
  {d.important&&<p><span className="pill warn">{n('importantDay')}</span> {d.reasons.map(r=>n('reasons')[r]||r).join(' · ')}</p>}
  <div className="metrics metrics-4">
   <Metric title={n('revenue')} value={d.revenue.length?d.revenue.map(m=>money(m.net,m.currency)).join(' · '):n('noRevenue')}/>
   <Metric title={n('payments')} value={d.revenue.reduce((a,m)=>a+m.payments,0)}/>
   <Metric title={n('sold')} value={d.vouchers.sold}/>
   <Metric title={n('redeemed')} value={d.vouchers.redeemed_in_app}/>
  </div>
  <div className="metrics">
   <Metric title={n('incidents')} value={d.incidents.started}/>
   <Metric title={n('openNow')} value={d.incidents.open_now}/>
   <Metric title={n('outstanding')} value={`${d.outstanding.critical} / ${d.outstanding.attention}`}/>
  </div>
  <p className="muted">{n('redeemedNote')}</p>
  <p className="muted">{n('notMeasured')}</p>
  <button className="button secondary" onClick={()=>go('Notifications')}>{n('title')}</button>
 </Panel>;
}
