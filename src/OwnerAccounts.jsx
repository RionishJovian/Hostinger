import React,{useEffect,useState} from 'react';
const when=t=>t?new Date(t*1000).toLocaleString():'—';
const STATES={active:'Active',suspended:'Suspended',disabled:'Disabled'};
export default function OwnerAccounts({api}){
 const [rows,setRows]=useState(null),[id,setId]=useState(''),[history,setHistory]=useState(null),[state,setState]=useState('suspended'),[reason,setReason]=useState(''),[name,setName]=useState(''),[busy,setBusy]=useState(false),[notice,setNotice]=useState('');
 const selected=rows?.find(r=>r.id===id);
 async function load(){setRows(await api.request('developer/owners'))}
 useEffect(()=>{load().catch(e=>setNotice(e.message))},[api]);
 useEffect(()=>{setHistory(null);if(!id)return;let active=true;api.request('developer/owners/'+id+'/history').then(h=>{if(active)setHistory(h)}).catch(e=>{if(active)setNotice(e.message)});return ()=>{active=false}},[api,id,selected?.access_revision,selected?.business]);
 useEffect(()=>{if(selected)setState(selected.access_state==='active'?'suspended':'active')},[selected?.access_state]);
 function open(r){setId(r.id);setState(r.access_state==='active'?'suspended':'active');setReason('');setName(r.business);setNotice('')}
 async function run(path,body,done){setBusy(true);setNotice('');try{const result=await api.request(path,body);await load();setNotice(done(result))}catch(e){setNotice(e.message)}finally{setBusy(false)}}
 return <section className="panel"><h2>SME owner accounts</h2><p>One Owner/Admin account per business. Suspending or disabling ends the owner's sessions immediately. A suspended owner sees your reason when signing in; a disabled owner gets the ordinary sign-in failure. Guest Wi-Fi on their routers is not changed.</p>
  <div className="tablewrap"><table><thead><tr><th>Business / owner</th><th>Access</th><th>Subscription</th><th>Last sign-in</th><th></th></tr></thead><tbody>
   {(rows||[]).map(r=><tr key={r.id}><td>{r.business}<small>{r.username}{r.must_change_password&&' · temporary password pending'}</small></td><td>{STATES[r.access_state]}{r.access_reason&&<small>{r.access_reason}</small>}</td><td>{r.subscription.plan||'No plan'}<small>{r.subscription.expires_on?(r.subscription.restricted?'Expired '+r.subscription.expires_on:'Until '+r.subscription.expires_on):r.subscription.state}</small></td><td>{when(r.last_sign_in)}<small>{r.active_sessions} active session{r.active_sessions===1?'':'s'}</small></td><td><button className="button secondary" disabled={busy} onClick={()=>open(r)}>Manage</button></td></tr>)}
   {!rows?.length&&<tr><td colSpan={5}>{rows?'No business owners yet.':'Loading…'}</td></tr>}
  </tbody></table></div>
  {notice&&<p role="status">{notice}</p>}
  {selected&&<div className="callout"><h3>{selected.business} · {selected.username}</h3>
   <form onSubmit={e=>{e.preventDefault();run('developer/owners/'+selected.id+'/access',{expected_revision:selected.access_revision,state,reason},r=>`Account is now ${STATES[r.access_state].toLowerCase()}.${r.sessions_ended?` ${r.sessions_ended} session${r.sessions_ended===1?'':'s'} ended.`:''}`).then(()=>setReason(''))}}>
    <h4>Account access · currently {STATES[selected.access_state].toLowerCase()}</h4>
    <div className="formgrid"><label className="field"><span>Change to</span><select value={state} onChange={e=>setState(e.target.value)}>{Object.entries(STATES).filter(([k])=>k!==selected.access_state).map(([k,v])=><option key={k} value={k}>{v}</option>)}</select></label></div>
    <label className="field"><span>{state==='suspended'?'Reason — shown to the owner when they sign in':'Reason — kept in the account history'}</span><textarea required maxLength={1000} value={reason} onChange={e=>setReason(e.target.value)}/></label>
    <button className="button" disabled={busy||!reason.trim()}>{state==='active'?'Restore access':state==='suspended'?'Suspend account':'Disable account'}</button>
   </form>
   <form onSubmit={e=>{e.preventDefault();run('developer/businesses/'+selected.business_id+'/name',{expected_name:selected.business,name},()=>'Business name saved.')}}>
    <h4>Business name</h4><label className="field"><span>Name</span><input required maxLength={160} value={name} onChange={e=>setName(e.target.value)}/></label><button className="button secondary" disabled={busy||!name.trim()||name===selected.business}>Save name</button>
   </form>
   <p className="muted">Password resets use the secure temporary-password flow in the business list below; you never see the owner's own password.</p>
   <h4>Account history</h4>{!history?<p role="status">Loading…</p>:<>
    {history.access.map((e,i)=><p key={'a'+i}>{when(e.time)} · {STATES[e.from]} → {STATES[e.to]} by {e.actor}{e.sessions_ended>0&&` · ${e.sessions_ended} session(s) ended`}<small>{e.reason}</small></p>)}
    {history.resets.map((e,i)=><p key={'r'+i}>{when(e.time)} · Password reset by {e.actor}<small>{e.reason}</small></p>)}
    <h4>Sign-ins (last {history.sign_in_retention_days} days)</h4>{history.sign_ins.length?history.sign_ins.map((e,i)=><p key={'s'+i}>{when(e.time)} · {e.outcome==='success'?'Signed in':'Failed or blocked sign-in'}<small>{[e.device,e.browser,e.approximate_source].filter(Boolean).join(' · ')}</small></p>):<p className="muted">No sign-ins recorded.</p>}
    <h4>Recent activity</h4>{history.activity.length?history.activity.slice(0,50).map((e,i)=><p key={'v'+i}>{when(e.time)} · {e.action.replaceAll('_',' ')}<small>{e.actor}</small></p>):<p className="muted">No activity recorded.</p>}
   </>}
  </div>}
 </section>
}
