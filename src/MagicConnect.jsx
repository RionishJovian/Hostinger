import React,{useEffect,useState} from 'react';
import QRCode from 'qrcode';
import {isSecurePairingContext,technicianPairingUrl} from './magic-connect-url.mjs';
import {unconnectedRouters} from './router-setup.mjs';
import './magic-connect.css';
import {useSmeCopy} from './SMELocalization.jsx';

const Field=({label,children})=><label className="field"><span>{label}</span>{children}</label>;
const expiry=value=>new Date(value*1000).toLocaleTimeString();
const HANDSHAKE_STATES=['awaiting_handshake','verifying_management','connected'];

function OwnerRouterSetup({x,c,plan,hubs,api,busy,onChange}){
 const [hub,setHub]=useState(hubs[0]?.id||''),[reviewed,setReviewed]=useState(false),[serial,setSerial]=useState(''),[note,setNote]=useState(''),[working,setWorking]=useState(false);
 useEffect(()=>{if(!hubs.some(h=>h.id===hub))setHub(hubs[0]?.id||'')},[hubs,hub]);
 async function run(steps,done){setWorking(true);setNote('');try{let last;for(const step of steps)last=await step();setNote(done(last))}catch(e){setNote(e.message)}finally{setWorking(false);onChange()}}
 const id=encodeURIComponent(x.id),disabled=working||busy;
 if(!x.router_id)return <p className="muted">{c.setupNotLinked}</p>;
 if(!x.router_public_key)return <p className="muted">{c.setupWaitKey}</p>;
 const key=<span>{c.setupKey} <code className="magic-key">{x.router_public_key}</code></span>;
 if(!plan)return <div className="magic-setup">{key}<Field label={c.setupHub}><select value={hub} onChange={e=>setHub(e.target.value)}>{hubs.map(h=><option key={h.id} value={h.id}>{h.name}</option>)}</select></Field><button className="button" disabled={disabled||!hub} onClick={()=>run([()=>api.request(`magic-connect/attempts/${id}/plan`,{hub_id:hub})],()=>c.setupPlanCreated)}>{c.setupCreatePlan}</button>{note&&<p role="status">{note}</p>}</div>;
 const planId=encodeURIComponent(plan.id),snap=plan.snapshot;
 const summary=<span>{c.setupPlanSummary(`${snap.hub.endpoint}:${snap.hub.port}`,snap.router.address,snap.router.interface)}</span>;
 if(['awaiting_review','awaiting_bootstrap'].includes(plan.state))return <div className="magic-setup">{key}{summary}<Field label={c.setupSerial}><input maxLength={40} autoComplete="off" spellCheck={false} value={serial} onChange={e=>setSerial(e.target.value.toUpperCase())}/></Field><label><input type="checkbox" checked={reviewed} onChange={e=>setReviewed(e.target.checked)}/> {c.setupReviewed}</label><button className="button" disabled={disabled||!reviewed||serial.trim().length<6} onClick={()=>run([
  ()=>plan.reviewed_at?null:api.request(`router-plans/${planId}/review`,{confirmed_review:true}),
  ()=>api.request(`magic-connect/attempts/${id}/enrollment`,{plan_id:plan.id,router_serial:serial.trim()}),
  ()=>api.request(`router-plans/${planId}/hub-peer/provision`,{confirmed:true,idempotency_key:'magic-connect-'+plan.id})
 ],()=>c.setupApplied)}>{c.setupApply}</button>{note&&<p role="status">{note}</p>}</div>;
 const routerId=encodeURIComponent(plan.router_id);
 const verify=()=>run([
  ()=>api.request(`router-plans/${planId}/hub-peer/observe`,{}),
  ()=>plan.state==='connected'?null:api.request(`routers/${routerId}/management-setup`,{}).catch(e=>{if(!e.message.includes('management_already_set_up'))throw e}),
  ()=>api.request(`routers/${routerId}/preflight`,{})
 ],r=>r.connection?.connection_verified?c.setupConnected:c.setupNotVerified(r.next_gate||'unverified'));
 if(HANDSHAKE_STATES.includes(plan.state))return <div className="magic-setup">{summary}<div className="buttons"><button className={plan.state==='awaiting_handshake'?'button':'button secondary'} disabled={disabled} onClick={()=>run([()=>api.request(`router-plans/${planId}/hub-peer/observe`,{})],r=>r.state==='awaiting_handshake'?c.setupNoHandshake:c.setupHandshake)}>{c.setupCheck}</button>{plan.state!=='awaiting_handshake'&&<button className="button" disabled={disabled} onClick={verify}>{plan.state==='connected'?c.setupVerifyAgain:c.setupFinish}</button>}</div>{plan.state==='verifying_management'&&<p className="muted">{c.setupFinishHint}</p>}{note&&<p role="status">{note}</p>}</div>;
 if(plan.state==='failed_recovery_required')return <div className="magic-setup">{summary}<p className="callout">{c.setupFailed(plan.last_failure_code||'unknown')}</p><button className="button secondary" disabled={disabled} onClick={()=>run([()=>api.request(`router-plans/${planId}/hub-peer/recovery-check`,{confirmed:true})],r=>c.setupRecovered(r.recovery_readback))}>{c.setupRecover}</button>{note&&<p role="status">{note}</p>}</div>;
 return summary;
}

export function MagicConnectOwner({sites,api,busy=false,routers=[],hubs=[]}){
 const c=useSmeCopy('routersPage');
 const pending=unconnectedRouters(routers);
 const [routerId,setRouterId]=useState(pending[0]?.id||''),[items,setItems]=useState([]),[pair,setPair]=useState(null),[qr,setQr]=useState(''),[message,setMessage]=useState(''),[loading,setLoading]=useState(false),[pairingAvailable,setPairingAvailable]=useState(false),[routerSetup,setRouterSetup]=useState(false),[plans,setPlans]=useState([]),[picked,setPicked]=useState({});
 const chosen=pending.find(router=>router.id===routerId)||null;
 const site=chosen?.site_id||'';
 useEffect(()=>{let live=true;api.request('magic-connect/capability').then(x=>{if(live){setPairingAvailable(x.pairing_available===true);setRouterSetup(x.router_setup_available===true)}}).catch(()=>{if(live){setPairingAvailable(false);setRouterSetup(false)}});return()=>{live=false}},[api]);
 useEffect(()=>{if(!pending.some(router=>router.id===routerId))setRouterId(pending[0]?.id||'')},[routers,routerId]);
 const loadPlans=()=>routerSetup?api.request('router-plans').then(setPlans).catch(()=>{}):Promise.resolve();
 useEffect(()=>{loadPlans()},[api,routerSetup]);
 async function reload(){setItems(await api.request(`sites/${encodeURIComponent(site)}/magic-connect/attempts`));await loadPlans()}
 async function refresh(){if(!site)return;setLoading(true);try{await reload();setMessage(c.refreshed)}catch(e){setMessage(e.message)}finally{setLoading(false)}}
 const active=items.some(x=>['claimed','approved'].includes(x.status)&&x.expires*1000>Date.now());
 useEffect(()=>{if(!active||!site)return;const timer=setInterval(()=>reload().catch(()=>{}),10000);return()=>clearInterval(timer)},[active,site,routerSetup]);
 useEffect(()=>{let live=true;if(site)api.request(`sites/${encodeURIComponent(site)}/magic-connect/attempts`).then(x=>{if(live)setItems(x)}).catch(e=>{if(live)setMessage(e.message)});return()=>{live=false}},[api,site]);
 useEffect(()=>{let live=true;if(pair?.manual_code){if(!isSecurePairingContext(window.location)){setQr('');return()=>{live=false}}QRCode.toDataURL(technicianPairingUrl(window.location,pair.manual_code),{errorCorrectionLevel:'M',margin:2,width:240}).then(value=>{if(live)setQr(value)}).catch(()=>{if(live)setQr('')})}else setQr('');return()=>{live=false}},[pair]);
 async function create(e){e.preventDefault();if(!pairingAvailable||!chosen)return;setLoading(true);setMessage('');try{const created=await api.request(`sites/${encodeURIComponent(chosen.site_id)}/magic-connect/attempts`,{router_name:chosen.name});setPair(created);setItems(await api.request(`sites/${encodeURIComponent(chosen.site_id)}/magic-connect/attempts`));setMessage(c.created)}catch(err){setMessage(err.message)}finally{setLoading(false)}}
 async function action(id,verb,body){setLoading(true);setMessage('');try{await api.request(`magic-connect/attempts/${encodeURIComponent(id)}/${verb}`,body);await reload();setMessage(verb==='approve'?(body.router_id?c.setupApprovedMsg:c.approvedMsg):c.closed)}catch(e){setMessage(e.message)}finally{setLoading(false)}}
 const stateLabel=x=>x.enrollment_state==='connected'?c.states.connected:x.enrollment_state==='pairing_approved'?(routerSetup&&x.router_id?c.states.approvedSetup:c.states.approved):x.enrollment_state==='awaiting_bootstrap'?c.states.bootstrap:x.enrollment_state==='awaiting_handshake'?c.states.handshake:x.enrollment_state==='verifying_management'?c.states.verifying:x.enrollment_state==='failed_recovery_required'?c.states.failed:x.status;
 const eligible=x=>routers.filter(r=>r.site_id===x.site_id&&!r.hub_id&&!plans.some(p=>p.router_id===r.id));
 const approveControls=x=>{if(!routerSetup)return <button className="button" disabled={loading||busy} onClick={()=>action(x.id,'approve',{comparison_confirmed:true})}>{c.approve}</button>;const options=eligible(x);
  return options.length?<><select aria-label={c.setupPickRouter} value={picked[x.id]||''} onChange={e=>setPicked({...picked,[x.id]:e.target.value})}><option value="">{c.setupPickRouter}</option>{options.map(r=><option key={r.id} value={r.id}>{r.name}</option>)}</select><button className="button" disabled={loading||busy||!picked[x.id]} onClick={()=>action(x.id,'approve',{comparison_confirmed:true,router_id:picked[x.id]})}>{c.approve}</button></>:<span className="muted">{c.setupNoRouters}</span>};
 return <section className="panel magic-connect" id="magic-connect"><div className="panelhead"><h2>{c.pairTitle}</h2><button className="button secondary" type="button" disabled={loading||!site} onClick={refresh}>{c.refresh}</button></div>{pairingAvailable?<p>{c.pairIntro}</p>:<p className="callout" role="status">{c.pairUnavailable}</p>}
  {pairingAvailable&&!routers.length&&<p className="muted">{c.pairNeedRouter}</p>}
  {pairingAvailable&&routers.length>0&&!pending.length&&<p className="muted">{c.pairAllConnected}</p>}
  {pairingAvailable&&pending.length>0&&<form onSubmit={create}><Field label={c.pairRouter}><select required value={routerId} onChange={e=>{setRouterId(e.target.value);setPair(null)}}>{pending.map(router=><option key={router.id} value={router.id}>{router.name} · {sites.find(item=>item.id===router.site_id)?.name||c.selectedShop}</option>)}</select></Field><button className="button" disabled={loading||busy||!chosen}>{c.pairButton}</button></form>}
  {pairingAvailable&&pair&&<div className="magic-pair-card" role="status"><div><h3>{c.ready}</h3><p>{c.pairMeta(sites.find(x=>x.id===pair.site_id)?.name||c.selectedShop,pair.router_name)}</p><p>{c.expires(expiry(pair.expires))}</p>{qr?<img className="magic-pair-qr" src={qr} alt={c.qrAlt}/>:<p>{c.qrOff}</p>}<p className="magic-manual-code"><b>{c.manual}</b><code>{pair.manual_code}</code></p><p className="muted">{c.codeWarn}</p></div></div>}
  {items.length>0&&<div className="magic-attempt-list"><h3>{c.recent}</h3>{items.map(x=><article className="magic-attempt" key={x.id}><div><b>{x.router_name}</b><span>{sites.find(s=>s.id===x.site_id)?.name||x.site_id}</span><span className="pill warn">{stateLabel(x)}</span><span>{c.compareLabel} <code>{x.comparison_code}</code> · {c.expiresAt(expiry(x.expires))}</span>{x.router_id&&<span>{c.setupRouter(routers.find(r=>r.id===x.router_id)?.name||x.router_id)}</span>}{x.enrollment_state!=='connected'&&<span className="muted">{routerSetup?c.setupNotConnected:c.notVerifiedYet}</span>}{routerSetup&&x.status==='approved'&&<OwnerRouterSetup x={x} c={c} plan={plans.find(p=>p.router_id===x.router_id&&p.snapshot?.router?.public_key===x.router_public_key)} hubs={hubs} api={api} busy={loading||busy} onChange={()=>reload().catch(e=>setMessage(e.message))}/>}</div><div className="buttons">{pairingAvailable&&x.status==='claimed'&&approveControls(x)}{['pending','claimed'].includes(x.status)&&<button className="button secondary" disabled={loading||busy} onClick={()=>action(x.id,'deny',{})}>{c.deny}</button>}{['pending','claimed','approved'].includes(x.status)&&<button className="button secondary" disabled={loading||busy} onClick={()=>action(x.id,'cancel',{})}>{c.cancel}</button>}</div></article>)}</div>}
  {message&&<p role="status">{message}</p>}
  <div className="callout">{routerSetup?c.setupFoot:c.pairFoot}</div>
 </section>
}

function Commands({title,lines}){
 const [copied,setCopied]=useState(false);
 if(!lines?.length)return null;
 const copy=()=>navigator.clipboard?.writeText(lines.join('\n')).then(()=>{setCopied(true);setTimeout(()=>setCopied(false),2000)}).catch(()=>{});
 return <div className="magic-commands"><div className="magic-commands-head"><b>{title}</b><button type="button" className="button secondary" onClick={copy}>{copied?'Copied':'Copy'}</button></div><pre><code>{lines.join('\n')}</code></pre></div>;
}

function TechnicianRouterSetup({setup,session,onSubmitted}){
 const [key,setKey]=useState(''),[busy,setBusy]=useState(false),[note,setNote]=useState('');
 const cmd=setup.commands||{};
 async function submit(e){e.preventDefault();setBusy(true);setNote('');try{const response=await fetch('/v1/magic-connect/technician/router-key',{method:'POST',headers:{'Content-Type':'application/json',Authorization:'Bearer '+session},body:JSON.stringify({router_public_key:key.trim()})});const data=await response.json();if(!response.ok)throw Error(typeof data.detail==='string'?data.detail:'Router key was not accepted');setKey('');setNote('Router key sent. Waiting for the owner to review the connection plan.');onSubmitted()}catch(err){setNote(err.message)}finally{setBusy(false)}}
 const rollback=cmd.rollback?.length?<details className="magic-rollback"><summary>Undo these router changes</summary><Commands title="Rollback (removes only the MikroMagic tunnel)" lines={cmd.rollback}/></details>:null;
 if(setup.step==='router_not_linked')return <p className="callout">The owner approved without choosing a router. Ask the owner to cancel this request and start a new pairing.</p>;
 if(setup.step==='closed')return <><p className="callout">Router setup is closed for this pairing.</p>{rollback}</>;
 const stops=setup.stop_if?.length?<div className="callout"><b>Stop and contact the owner if:</b><ul>{setup.stop_if.map(x=><li key={x}>{x}</li>)}</ul></div>:null;
 if(setup.step==='generate_key')return <div className="magic-tech-setup"><h2>Step 1 · Check the router</h2><p>Open the RouterOS terminal (WinBox → New Terminal) and run these read-only commands.</p><Commands title="Read-only check" lines={cmd.inspect}/>{stops}<h2>Step 2 · Create the MikroMagic tunnel key</h2><p>This creates one new WireGuard interface. RouterOS generates the private key and keeps it on the router. The last line prints the public key.</p><Commands title="Create interface" lines={cmd.create_interface}/><form onSubmit={submit}><Field label="Router public key (44 characters)"><input required minLength={44} maxLength={44} autoComplete="off" spellCheck={false} value={key} onChange={e=>setKey(e.target.value.trim())}/></Field><button className="button" disabled={busy||key.length!==44}>Send router key to owner</button></form>{note&&<p role="status">{note}</p>}{rollback}</div>;
 if(setup.step==='owner_review')return <div className="magic-tech-setup"><p>Router key sent: <code className="magic-key">{setup.router_public_key}</code></p><p>Waiting for the owner to review the connection plan. This page refreshes on its own.</p>{rollback}</div>;
 if(setup.step==='management_access')return <div className="magic-tech-setup"><h2>Step 4 · Allow MikroMagic management</h2><p>The handshake works. First run the read-only check: <b>www-ssl</b> must be disabled and no user or group may start with <b>mm-</b>.</p><Commands title="Read-only check" lines={cmd.inspect_management}/>{stops}<p>These commands create an HTTPS certificate for {setup.router_address}, turn on HTTPS for the Hub address {setup.hub_address} only, add one firewall rule that accepts only the Hub, and add a temporary login <code>{setup.enrollment_user}</code>. MikroMagic uses that login once to create its own logins, then deletes it.</p><Commands title="Allow management" lines={cmd.management_access}/><p className="muted">Do not save or share this text. When it is done, tell the owner to press "Finish management setup and verify".</p>{rollback}</div>;
 if(setup.step==='management_ready')return <div className="magic-tech-setup"><h2>MikroMagic logins created</h2><p>MikroMagic created its read-only and Safe Change logins and removed the temporary login. The owner now verifies the connection. You do not need to do anything else on the router.</p>{rollback}</div>;
 if(setup.step==='management_storage_unavailable')return <div className="magic-tech-setup"><p className="callout">Management setup is not available on the server yet. Stop here; the tunnel can stay as it is.</p>{rollback}</div>;
 return <div className="magic-tech-setup"><h2>Step 3 · Connect to the Magic Hub</h2><p>{setup.step==='awaiting_handshake'?'The owner added this router to the Hub.':'The owner reviewed the plan.'} Run these commands on the router. They add only the Hub peer, the management address {setup.router_address} and one route to {setup.hub_address}.</p><Commands title="Connect to Hub" lines={cmd.connect_hub}/><p className="muted">The ping only answers after the owner has added the router to the Hub. The owner then checks the handshake. A handshake alone does not make the router Connected.</p>{rollback}</div>;
}

export function MagicConnectTechnician(){
 return <main className="magic-tech-page"><section className="panel"><h1>Connect with Magic Hub</h1><p className="callout" role="status">Technician QR pairing is not used. Sign in as the shop owner, open Routers, and press Connect with Magic Hub.</p><p className="muted">Magic Connect pairing is unavailable in this release.</p></section></main>
}
