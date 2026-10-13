import React,{useEffect,useState} from 'react';
import {useSmeCopy} from './SMELocalization.jsx';
import './magic-hub-connect.css';

const STEPS=['reported','peer_added','awaiting_handshake','management_applied','connected'];
const STEP_ALIAS={waiting:'reported',finishing:'management_applied',peer_added:'peer_added'};

function CodeFrame({title,text,copyLabel,copiedLabel}){
 const [copied,setCopied]=useState(false);
 if(!text)return null;
 const copy=()=>navigator.clipboard?.writeText(text).then(()=>{setCopied(true);setTimeout(()=>setCopied(false),2000)}).catch(()=>{});
 return <div className="mm-hub-code"><div className="mm-hub-code-head"><b>{title}</b><button type="button" className="button secondary" onClick={copy}>{copied?copiedLabel:copyLabel}</button></div><pre><code>{text}</code></pre></div>;
}

export function MagicHubConnectPopup({router,api,busy,onClose,onConnected}){
 const c=useSmeCopy('routersPage');
 const [session,setSession]=useState(null);
 const [progress,setProgress]=useState(null);
 const [error,setError]=useState('');
 const [starting,setStarting]=useState(false);
 const [replace,setReplace]=useState(false);

 async function start(force=false){
  setStarting(true);setError('');
  try{
   const body={replace_existing:force||replace,reason:force||replace?'Owner re-run one-paste Magic Hub connect':undefined};
   const data=await api.request(`routers/${encodeURIComponent(router.id)}/magic-hub-connect`,body);
   setSession(data);setProgress(data.progress||null);
  }catch(e){
   const msg=e.message||'';
   if(msg.includes('plan_exists')||msg.includes('already has a Magic Hub plan')){
    setError(c.hubConnectReplaceHint);setReplace(true);
   }else setError(msg);
  }finally{setStarting(false)}
 }

 useEffect(()=>{start(false)},[router.id]);

 useEffect(()=>{
  if(!session?.token_id)return;
  let live=true;
  const tick=async()=>{
   try{
    const p=await api.request(`routers/${encodeURIComponent(router.id)}/magic-hub-connect/${encodeURIComponent(session.token_id)}`);
    if(!live)return;
    setProgress(p);
    if(p.connection_verified||p.status==='connected'){onConnected?.();return}
    if(p.status==='failed'||p.status==='expired'||p.status==='revoked')setError(p.failure_message||c.hubConnectFailed(p.failure_code||p.status));
   }catch(e){if(live)setError(e.message)}
  };
  tick();
  const timer=setInterval(tick,4000);
  return()=>{live=false;clearInterval(timer)};
 },[session?.token_id,router.id,api]);

 const status=progress?.status||'waiting';
 const mapped=STEP_ALIAS[status]||status;
 const activeIdx=status==='waiting'?-1:STEPS.indexOf(mapped);
 const waiting=status==='waiting';

 return <div className="mm-hub-modal" role="dialog" aria-modal="true" aria-labelledby="mm-hub-title">
  <div className="mm-hub-modal-card">
   <div className="mm-hub-modal-head">
    <h2 id="mm-hub-title">{c.hubConnectTitle}</h2>
    <button type="button" className="button secondary" onClick={onClose}>{c.close}</button>
   </div>
   <p>{c.hubConnectIntro(router.name)}</p>
   {!session&&<div className="buttons">
    <button className="button" disabled={starting||busy} onClick={()=>start(replace)}>{starting?c.hubConnectStarting:(replace?c.hubConnectReplace:c.hubConnectStart)}</button>
   </div>}
   {session&&<>
    {waiting&&<p className="muted" role="status">{c.hubConnectWaiting}</p>}
    <ol className="mm-hub-steps">{STEPS.map((step,i)=>{
     const label=c.hubConnectSteps[step]||step;
     const state=status==='failed'&&i===Math.max(activeIdx,0)?'is-failed':i<activeIdx?'is-done':i===activeIdx?'is-active':'is-todo';
     return <li key={step} className={'mm-hub-step '+state}>{label}</li>;
    })}</ol>
    <CodeFrame title={c.hubConnectScript} text={session.script} copyLabel={c.hubConnectCopy} copiedLabel={c.hubConnectCopied}/>
    <p className="muted">{c.hubConnectPaste}</p>
    <details className="mm-hub-rollback"><summary>{c.hubConnectRollback}</summary>
     <CodeFrame title={c.hubConnectRollback} text={session.rollback_script} copyLabel={c.hubConnectCopy} copiedLabel={c.hubConnectCopied}/>
    </details>
    <p className="muted">{session.fetch_certificate_note}</p>
   </>}
   {error&&<p className="callout" role="alert">{error}</p>}
   {(progress?.model_mismatch||progress?.version_mismatch)&&<p className="muted" role="status">{c.hubConnectMismatch}</p>}
  </div>
 </div>;
}

export function MagicHubConnectButton({router,api,busy,setupAvailable,onChanged}){
 const c=useSmeCopy('routersPage');
 const [open,setOpen]=useState(false);
 if(!setupAvailable)return null;
 const connected=router.connection_state==='connected'||router.connection_verified;
 return <>
  <button type="button" className="button" disabled={busy} onClick={()=>setOpen(true)}>
   {connected?c.hubConnectAgain:c.hubConnectButton}
  </button>
  {open&&<MagicHubConnectPopup router={router} api={api} busy={busy} onClose={()=>setOpen(false)} onConnected={()=>{onChanged?.();}}/>}
 </>;
}
