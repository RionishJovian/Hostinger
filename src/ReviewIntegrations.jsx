import React,{useState} from 'react';
import {useSmeCopy,useSmeFormat} from './SMELocalization.jsx';

export default function ReviewIntegrations({credentials,actions,deliveries=[],act,busy}){
 const c=useSmeCopy('integrations');
 const {when}=useSmeFormat();
 const initial={label:'',provider:'custom',reviewer_identity:'',expires_days:30,can_decide:false,receive_events:false,authorize_service:false};
 const [draft,setDraft]=useState(initial),[secret,setSecret]=useState(null),[reason,setReason]=useState(''),[copyStatus,setCopyStatus]=useState('');
 return <>
  <section className="panel"><h2>{c.connectTitle}</h2><p>{c.connectIntro}</p><p className="muted">{c.connectNote}</p>
   <form onSubmit={async e=>{e.preventDefault();const r=await act('review-credentials',draft);if(r){setSecret(r);setDraft(initial);setCopyStatus('')}}}>
    <div className="formgrid">
     <label className="field"><span>{c.serviceName}</span><input required maxLength={120} value={draft.label} onChange={e=>setDraft({...draft,label:e.target.value})}/></label>
     <label className="field"><span>{c.adapterType}</span><select value={draft.provider} onChange={e=>setDraft({...draft,provider:e.target.value})}>{['custom','telegram','discord'].map(x=><option key={x}>{x}</option>)}</select></label>
     <label className="field"><span>{c.reviewerIdentity}</span><input required maxLength={160} placeholder={c.reviewerPlaceholder} value={draft.reviewer_identity} onChange={e=>setDraft({...draft,reviewer_identity:e.target.value})}/></label>
     <label className="field"><span>{c.expiresDays}</span><input type="number" min={1} max={90} required value={draft.expires_days} onChange={e=>setDraft({...draft,expires_days:Number(e.target.value)})}/></label>
    </div>
    <label className="check"><input type="checkbox" checked={draft.receive_events} onChange={e=>setDraft({...draft,receive_events:e.target.checked})}/> {c.queueEvents}</label>
    <label className="check"><input type="checkbox" checked={draft.can_decide} onChange={e=>setDraft({...draft,can_decide:e.target.checked})}/> {c.allowDecide}</label>
    <label className="check"><input type="checkbox" checked={draft.authorize_service} onChange={e=>setDraft({...draft,authorize_service:e.target.checked})}/> {c.authorize}</label>
    <button className="button" disabled={busy||!draft.authorize_service}>{c.create}</button>
   </form>
  </section>
  {secret&&<section className="panel"><h2>{c.saveTokenTitle}</h2><p>{c.saveTokenBody}</p>
   <label className="field"><span>{c.privateToken(secret.label)}</span><input readOnly value={secret.token} autoComplete="off" spellCheck={false}/></label>
   <div className="buttons">
    <button className="button secondary" onClick={async()=>{try{await navigator.clipboard.writeText(secret.token);setCopyStatus(c.copied)}catch{setCopyStatus(c.copyUnavailable)}}}>{c.copyToken}</button>
    <button className="button secondary" onClick={()=>setSecret(null)}>{c.hideToken}</button>
   </div>
   <p role="status">{copyStatus}</p>
  </section>}
  <section className="panel"><h2>{c.credentialsTitle}</h2>
   <label className="field"><span>{c.reasonLabel}</span><textarea maxLength={1000} value={reason} onChange={e=>setReason(e.target.value)}/></label>
   <div className="tablewrap"><table><thead><tr>{c.heads.map(x=><th key={x}>{x}</th>)}</tr></thead><tbody>
    {credentials.map(cred=><tr key={cred.id}><td>{cred.label}<small>{cred.provider} · {cred.id}</small></td><td>{cred.reviewer_identity}</td><td>{cred.can_decide?c.readDecide:c.readOnly}<small>{cred.receive_events?c.eventsOn:c.eventsOff}</small></td><td>{cred.revoked_at?c.revoked:when(cred.expires)}{cred.revoke_reason&&<small>{cred.revoke_reason}</small>}</td><td>{!cred.revoked_at&&<button className="button secondary" disabled={busy||cred.expires<=Date.now()/1000} onClick={()=>act('review-credentials/'+cred.id+'/events',{receive_events:!cred.receive_events})}>{cred.receive_events?c.pauseEvents:c.enableEvents}</button>}{!cred.revoked_at&&<button className="button secondary" disabled={busy||!reason.trim()} onClick={async()=>{if(await act('review-credentials/'+cred.id+'/revoke',{reason})){if(secret?.id===cred.id)setSecret(null);setReason('')}}}>{c.revoke}</button>}</td></tr>)}
    {!credentials.length&&<tr><td colSpan={5}>{c.emptyCredentials}</td></tr>}
   </tbody></table></div>
  </section>
  <section className="panel"><h2>{c.deliveryTitle}</h2><p>{c.deliveryIntro}</p><p className="muted">{c.deliveryNote}</p>
   <div className="tablewrap"><table><thead><tr>{c.deliveryHeads.map(x=><th key={x}>{x}</th>)}</tr></thead><tbody>
    {deliveries.map(d=><tr key={d.id}><td>{d.service_label}<small>{d.order_id}</small></td><td>{d.event}<small>{c.sequence(d.event_revision)}</small></td><td>{d.state}{!d.subscription_enabled&&<small>{c.eventsPaused}</small>}{!d.credential_available&&<small>{c.credUnavailable}</small>}</td><td>{d.attempts}<small>{c.cycleAttempts(d.cycle_attempts)}</small></td><td>{d.last_error||c.dash}</td><td>{d.state==='failed'&&<button className="button secondary" disabled={busy||!reason.trim()||!d.credential_available||!d.subscription_enabled} onClick={()=>act('event-deliveries/'+d.id+'/retry',{reason})}>{c.retry}</button>}</td></tr>)}
    {!deliveries.length&&<tr><td colSpan={6}>{c.emptyDeliveries}</td></tr>}
   </tbody></table></div>
   <p className="muted">{c.retryNote}</p>
  </section>
  <section className="panel"><h2>{c.historyTitle}</h2>
   <div className="tablewrap"><table><thead><tr>{c.historyHeads.map(x=><th key={x}>{x}</th>)}</tr></thead><tbody>
    {actions.map(a=><tr key={a.id}><td>{when(a.created)}</td><td>{a.service_label}<small>{a.provider} · {a.reviewer_identity}</small></td><td>{a.order_id}</td><td>{a.decision}<small>{a.reason}</small></td></tr>)}
    {!actions.length&&<tr><td colSpan={4}>{c.emptyHistory}</td></tr>}
   </tbody></table></div>
   <p className="muted">{c.historyNote}</p>
  </section>
 </>;
}
