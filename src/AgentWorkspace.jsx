import React,{useEffect,useRef,useState} from 'react';
import {LocationPin,REGIONS} from './AgentLocation.jsx';
export const AGENT_PAGES=['Agent overview','Registered businesses','Commissions','Withdrawals','Account'];
const METHOD_NAMES={kbzpay:'KBZPay',wavepay:'WavePay'};
const STATUS_TEXT={pending:'Your application is waiting for the platform owner to approve it. You can register businesses once it is approved.',approved:'Approved. You can register new businesses and request withdrawals.',rejected:'Your application was not approved.',suspended:'Your Agent account is suspended. You cannot register businesses or request withdrawals.'};
const money=(n,c='MMK')=>`${Number(n).toLocaleString()} ${c}`;
const day=t=>t?new Date(t*1000).toLocaleDateString():'—';

export function AgentApplication({onDone}){
 const [form,setForm]=useState({username:'',password:'',full_name:'',phone:'',region:'',city:'',township:'',note:''}),[pin,setPin]=useState(null),[busy,setBusy]=useState(false),[notice,setNotice]=useState('');
 const set=k=>e=>setForm({...form,[k]:e.target.value});
 async function submit(e){e.preventDefault();if(!pin){setNotice('Place your pin on the map, or type its coordinates.');return}setBusy(true);setNotice('');try{const r=await fetch('/v1/agent-applications',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...form,...pin,username:form.username.trim().toLowerCase(),note:form.note.trim()||null})});const data=await r.json().catch(()=>({}));if(!r.ok)throw Error(typeof data.detail==='string'?data.detail:Array.isArray(data.detail)?data.detail.map(x=>x.msg).join('; '):'Application failed');onDone(`Application received for ${data.username}. Sign in with it to see when it is approved.`)}catch(err){setNotice(err.message)}finally{setBusy(false)}}
 return <form onSubmit={submit}>
  <label className="field"><span>Username</span><input required minLength={3} maxLength={160} autoComplete="username" value={form.username} onChange={set('username')}/></label>
  <label className="field"><span>Password — at least 6 characters</span><input required type="password" minLength={6} maxLength={256} autoComplete="new-password" value={form.password} onChange={set('password')}/></label>
  <label className="field"><span>Full name</span><input required maxLength={160} value={form.full_name} onChange={set('full_name')}/></label>
  <label className="field"><span>Phone number</span><input required minLength={6} maxLength={40} inputMode="tel" value={form.phone} onChange={set('phone')}/></label>
  <fieldset className="plainset"><legend>Where you work</legend><p className="muted">MikroMagic uses this only to review your application. Your location is not tracked. The map comes from OpenStreetMap.</p>
   <label className="field"><span>State or region</span><select required value={form.region} onChange={set('region')}><option value="">Choose…</option>{REGIONS.map(r=><option key={r}>{r}</option>)}</select></label>
   <div className="formgrid"><label className="field"><span>City</span><input required maxLength={80} value={form.city} onChange={set('city')}/></label><label className="field"><span>Township</span><input required maxLength={80} value={form.township} onChange={set('township')}/></label></div>
   <LocationPin value={pin} onChange={setPin}/>
  </fieldset>
  <label className="field"><span>About you — optional</span><textarea maxLength={1000} value={form.note} onChange={set('note')}/></label>
  <button className="button" disabled={busy}>Apply to become an Agent</button>
  {notice&&<p role="alert">{notice}</p>}
 </form>;
}

function Overview({profile}){
 const b=profile.balances.find(x=>x.currency===profile.withdrawal_currency)||{earned:0,reversed:0,reserved:0,paid:0,available:0,currency:profile.withdrawal_currency};
 return <><section className="panel"><h2>{profile.full_name}</h2><p><span className={'pill'+(profile.status==='approved'?'':' warn')}>{profile.status}</span></p><p>{STATUS_TEXT[profile.status]}</p>{profile.reason&&<p>Reason: {profile.reason}</p>}<p className="muted">You earn {profile.rates.monthly}% of the list price of each approved monthly subscription payment and {profile.rates.annual}% of each approved annual payment made by businesses you registered. A refunded payment takes its commission back.</p></section>
  <div className="metrics"><div className="metric"><small>Available to withdraw</small><strong>{money(b.available,b.currency)}</strong><span>Minimum withdrawal {money(profile.minimum_withdrawal,profile.withdrawal_currency)}</span></div><div className="metric"><small>Commission earned</small><strong>{money(b.earned,b.currency)}</strong><span>{b.reversed?`${money(b.reversed,b.currency)} reversed by refunds`:'No refunds'}</span></div><div className="metric"><small>Registered businesses</small><strong>{profile.businesses}</strong><span>{money(b.paid,b.currency)} paid out · {money(b.reserved,b.currency)} in withdrawal requests</span></div></div>
  {profile.balances.filter(x=>x.currency!==profile.withdrawal_currency).map(x=><p key={x.currency} className="muted">{money(x.earned,x.currency)} earned in {x.currency}; withdrawals are paid in {profile.withdrawal_currency} only.</p>)}</>;
}

function Businesses({api,profile}){
 const [rows,setRows]=useState(null),[name,setName]=useState(''),[owner,setOwner]=useState(''),[busy,setBusy]=useState(false),[notice,setNotice]=useState(''),[created,setCreated]=useState(null);const key=useRef(null);
 const load=()=>api.request('agent/businesses').then(setRows).catch(e=>setNotice(e.message));
 useEffect(()=>{load()},[api]);
 async function submit(e){e.preventDefault();const body={name:name.trim(),owner_username:owner.trim().toLowerCase()};const fp=JSON.stringify(body);if(key.current?.fp!==fp)key.current={fp,key:crypto.randomUUID()};setBusy(true);setNotice('');try{const r=await api.request('agent/businesses',{...body,request_key:key.current.key});key.current=null;setCreated(r.shown_once?r:null);if(!r.shown_once)setNotice('This business was already registered; its temporary password was shown when it was created.');setName('');setOwner('');await load()}catch(err){setNotice(err.message)}finally{setBusy(false)}}
 return <><section className="panel"><h2>Register a new business</h2><p>Creates the business and its one Owner/Admin account. You receive a temporary password to hand to the owner; they must change it at their first sign-in. You do not get access to the business afterwards.</p>
  {profile.status==='approved'?<form onSubmit={submit}><div className="formgrid"><label className="field"><span>Business name</span><input required maxLength={160} value={name} onChange={e=>setName(e.target.value)}/></label><label className="field"><span>Owner username</span><input required minLength={3} maxLength={160} pattern="[a-zA-Z0-9][a-zA-Z0-9_.@+\-]{2,159}" value={owner} onChange={e=>setOwner(e.target.value)}/></label></div><button className="button" disabled={busy}>Register business</button></form>:<p className="muted">{STATUS_TEXT[profile.status]}</p>}
  {created&&<div className="callout" role="status"><h3>Owner sign-in handoff</h3><p>Business: {created.name} · Username: {created.owner.username}</p><label className="field"><span>Temporary password — shown once</span><input readOnly value={created.temporary_password} autoComplete="off" spellCheck={false}/></label><p>Shown only once. Give it to the owner of {created.name} privately; it expires in 24 hours and must be changed at the first sign-in. If it expires, MikroMagic support can issue a new one.</p><button className="button secondary" onClick={()=>setCreated(null)}>I have handed it over</button></div>}
  {notice&&<p role="status">{notice}</p>}</section>
  <section className="panel"><h2>Businesses you registered</h2>{rows===null?<p>Loading…</p>:<div className="tablewrap"><table><thead><tr><th>Business</th><th>Owner</th><th>Subscription</th><th>Your commission</th></tr></thead><tbody>{rows.map(r=><tr key={r.id}><td>{r.name}<small>Registered {day(r.registered)}</small></td><td>{r.owner_username}<small>{r.owner_signed_in?'Has signed in':'Has not signed in yet'}</small></td><td>{r.subscription.state}<small>{r.subscription.expires_on?`Expires ${r.subscription.expires_on}`:'No paid term yet'}</small></td><td>{money(r.commission_earned)}</td></tr>)}{!rows.length&&<tr><td colSpan={4}>No businesses yet.</td></tr>}</tbody></table></div>}</section></>;
}

function Commissions({api}){
 const [rows,setRows]=useState(null),[notice,setNotice]=useState('');
 useEffect(()=>{api.request('agent/commissions').then(setRows).catch(e=>setNotice(e.message))},[api]);
 return <section className="panel"><h2>Commission history</h2><p>One line per approved subscription payment from a business you registered.</p>{notice&&<p role="alert">{notice}</p>}{rows===null?<p>Loading…</p>:<div className="tablewrap"><table><thead><tr><th>Date</th><th>Business</th><th>Payment</th><th>Commission</th><th>Status</th></tr></thead><tbody>{rows.map(c=><tr key={c.id}><td>{day(c.created)}</td><td>{c.business}</td><td>{c.months===12?'Annual':'Monthly'}<small>List price {money(c.base_amount,c.currency)}</small></td><td>{money(c.amount,c.currency)}<small>{c.rate_percent}%</small></td><td>{c.state==='earned'?'Earned':'Reversed'}{c.state==='reversed'&&<small>Refunded {day(c.reversed_at)}: {c.reversal_reason}</small>}</td></tr>)}{!rows.length&&<tr><td colSpan={5}>No commission yet.</td></tr>}</tbody></table></div>}</section>;
}

function Wallet({api,method,wallet,onSaved}){
 const [name,setName]=useState(wallet?.account_name||''),[number,setNumber]=useState(wallet?.account_number||''),[busy,setBusy]=useState(false),[notice,setNotice]=useState('');
 async function save(e){e.preventDefault();setBusy(true);setNotice('');try{await api.request('agent/wallets',{method,account_name:name.trim(),account_number:number.trim()});setNotice('Saved.');onSaved()}catch(err){setNotice(err.message)}finally{setBusy(false)}}
 return <form onSubmit={save}><h3>{METHOD_NAMES[method]} wallet</h3><div className="formgrid"><label className="field"><span>Account name</span><input required maxLength={160} value={name} onChange={e=>setName(e.target.value)}/></label><label className="field"><span>Wallet phone number</span><input required minLength={6} maxLength={40} inputMode="tel" value={number} onChange={e=>setNumber(e.target.value)}/></label></div><button className="button secondary" disabled={busy}>Save {METHOD_NAMES[method]} wallet</button>{notice&&<p role="status">{notice}</p>}</form>;
}

function Withdrawals({api,profile,reloadProfile}){
 const [rows,setRows]=useState(null),[amount,setAmount]=useState(''),[method,setMethod]=useState(''),[busy,setBusy]=useState(false),[notice,setNotice]=useState('');const key=useRef(null);
 const load=()=>api.request('agent/withdrawals').then(setRows).catch(e=>setNotice(e.message));
 useEffect(()=>{load()},[api]);
 const saved=profile.wallets.map(w=>w.method),b=profile.balances.find(x=>x.currency===profile.withdrawal_currency)||{available:0};
 async function submit(e){e.preventDefault();const body={amount:Number(amount),method};const fp=JSON.stringify(body);if(key.current?.fp!==fp)key.current={fp,key:crypto.randomUUID()};setBusy(true);setNotice('');try{await api.request('agent/withdrawals',{...body,request_key:key.current.key});key.current=null;setAmount('');setNotice('Withdrawal requested. The platform owner reviews it and sends the money to your wallet.');await Promise.all([load(),reloadProfile()])}catch(err){setNotice(err.message)}finally{setBusy(false)}}
 async function cancel(id){setBusy(true);setNotice('');try{await api.request('agent/withdrawals/'+id+'/cancel',{});await Promise.all([load(),reloadProfile()])}catch(err){setNotice(err.message)}finally{setBusy(false)}}
 return <><section className="panel"><h2>Request a withdrawal</h2><p>Available: <strong>{money(b.available,profile.withdrawal_currency)}</strong>. Minimum {money(profile.minimum_withdrawal,profile.withdrawal_currency)}. The platform owner reviews each request and pays it manually to your own KBZPay or WavePay wallet; a request is not paid until it shows Paid.</p>
  {profile.status!=='approved'?<p className="muted">{STATUS_TEXT[profile.status]}</p>:!saved.length?<p className="muted">Save a KBZPay or WavePay wallet below first.</p>:<form onSubmit={submit}><div className="formgrid"><label className="field"><span>Amount ({profile.withdrawal_currency})</span><input required type="number" min={profile.minimum_withdrawal} max={Math.max(b.available,0)} step="1" value={amount} onChange={e=>setAmount(e.target.value)}/></label><label className="field"><span>Pay to</span><select required value={method} onChange={e=>setMethod(e.target.value)}><option value="">Choose wallet</option>{saved.map(m=><option key={m} value={m}>{METHOD_NAMES[m]}</option>)}</select></label></div><button className="button" disabled={busy||b.available<profile.minimum_withdrawal}>Request withdrawal</button></form>}
  {notice&&<p role="status">{notice}</p>}</section>
  <section className="panel"><h2>Your payout wallets</h2><p>Only KBZPay and WavePay are supported. Each request keeps the wallet details it was made with.</p>{['kbzpay','wavepay'].map(m=><Wallet key={m+(profile.wallets.find(w=>w.method===m)?.updated||0)} api={api} method={m} wallet={profile.wallets.find(w=>w.method===m)} onSaved={reloadProfile}/>)}</section>
  <section className="panel"><h2>Withdrawal history</h2>{rows===null?<p>Loading…</p>:<div className="tablewrap"><table><thead><tr><th>Requested</th><th>Amount</th><th>Wallet</th><th>Status</th><th></th></tr></thead><tbody>{rows.map(w=><tr key={w.id}><td>{day(w.requested)}</td><td>{money(w.amount,w.currency)}</td><td>{METHOD_NAMES[w.method]}<small>{w.wallet.account_name} · {w.wallet.account_number}</small></td><td>{w.status}{w.status==='paid'&&<small>Reference {w.payout_reference} · {day(w.paid_at)}</small>}{w.reason&&<small>{w.reason}</small>}</td><td>{w.status==='requested'&&<button className="button secondary" disabled={busy} onClick={()=>cancel(w.id)}>Cancel</button>}</td></tr>)}{!rows.length&&<tr><td colSpan={5}>No withdrawals yet.</td></tr>}</tbody></table></div>}</section></>;
}

export default function AgentWorkspace({api,page}){
 const [profile,setProfile]=useState(null),[notice,setNotice]=useState('');
 const reloadProfile=()=>api.request('agent/profile').then(setProfile).catch(e=>setNotice(e.message));
 useEffect(()=>{reloadProfile()},[api,page]);
 if(!profile)return <section className="panel"><p>{notice||'Loading…'}</p></section>;
 if(page==='Agent overview')return <Overview profile={profile}/>;
 if(page==='Registered businesses')return <Businesses api={api} profile={profile}/>;
 if(page==='Commissions')return <Commissions api={api}/>;
 if(page==='Withdrawals')return <Withdrawals api={api} profile={profile} reloadProfile={reloadProfile}/>;
 return null;
}
