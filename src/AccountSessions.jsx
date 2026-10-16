import React,{useEffect,useState} from 'react';
import {useSmeCopy,useSmeFormat} from './SMELocalization.jsx';

export default function AccountSessions({api,ownerAdmin=false}){
 const c=useSmeCopy('account');
 const {when}=useSmeFormat();
 const [sessions,setSessions]=useState([]),[history,setHistory]=useState([]),[busy,setBusy]=useState(false),[notice,setNotice]=useState(''),[confirmed,setConfirmed]=useState(false);
 const date=value=>value?when(value):c.preUpgrade;
 async function refresh(){setBusy(true);try{setSessions(await api.request('account/sessions'));if(ownerAdmin)setHistory(await api.request('account/login-history'));setNotice('')}catch(e){setNotice(e.message)}finally{setBusy(false)}}
 useEffect(()=>{let active=true;Promise.all([api.request('account/sessions'),...(ownerAdmin?[api.request('account/login-history')]:[])]).then(([activeSessions,loginHistory])=>{if(active){setSessions(activeSessions);if(ownerAdmin)setHistory(loginHistory||[])}}).catch(e=>{if(active)setNotice(e.message)});return ()=>{active=false}},[api,ownerAdmin]);
 async function revoke(path,body){setBusy(true);try{await api.request(path,body);setNotice(c.othersEnded);setConfirmed(false);setSessions(await api.request('account/sessions'))}catch(e){setNotice(e.message)}finally{setBusy(false)}}
 return <>
  <section className="panel"><h2>{c.sessionsTitle}</h2><p>{c.sessionsIntro}</p><button className="button secondary" disabled={busy} onClick={refresh}>{c.refresh}</button><div className="tablewrap"><table><thead><tr>{c.heads.map(h=><th key={h}>{h}</th>)}</tr></thead><tbody>{sessions.map((s,i)=><tr key={s.session_ref}><td>{s.device||c.unavailable}<br/><small>{s.browser||c.unavailable}</small></td><td>{date(s.login_at)}</td><td>{date(s.last_active)}</td><td>{s.approximate_source||c.unavailable}</td><td>{s.current?c.currentSession:c.otherSession(i+1)}</td><td>{s.current?c.useSignOut:<button className="button secondary" disabled={busy} onClick={()=>revoke('account/sessions/revoke',{session_ref:s.session_ref})}>{c.endSession}</button>}</td></tr>)}{!sessions.length&&<tr><td colSpan={6}>{c.emptySessions}</td></tr>}</tbody></table></div><label className="check"><input type="checkbox" checked={confirmed} onChange={e=>setConfirmed(e.target.checked)}/> {c.endOthersCheck}</label><button className="button secondary" disabled={busy||!confirmed} onClick={()=>revoke('account/sessions/revoke-others',{confirmed:true})}>{c.endOthers}</button>{notice&&<p role="status">{notice}</p>}<p className="muted">{c.sessionsNote}</p></section>
  {ownerAdmin&&<section className="panel"><h2>{c.historyTitle}</h2><p>{c.historyIntro}</p><div className="tablewrap"><table><thead><tr>{c.historyHeads.map(h=><th key={h}>{h}</th>)}</tr></thead><tbody>{history.map(row=><tr key={row.id}><td>{row.outcome==='success'?c.success:c.failed}</td><td>{date(row.time)}</td><td>{row.device} · {row.browser}</td><td>{row.approximate_source}</td><td>{date(row.retained_until)}</td></tr>)}{!history.length&&<tr><td colSpan={5}>{c.emptyHistory}</td></tr>}</tbody></table></div></section>}
 </>;
}
