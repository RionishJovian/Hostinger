import React,{useEffect,useState} from 'react';
import {pinLink,placeText} from './AgentLocation.jsx';
const METHOD_NAMES={kbzpay:'KBZPay',wavepay:'WavePay'};
const ACTIONS={pending:[['approved','Approve'],['rejected','Reject']],approved:[['suspended','Suspend']],suspended:[['approved','Restore']],rejected:[['approved','Approve']]};
const money=(n,c='MMK')=>`${Number(n).toLocaleString()} ${c}`;
const day=t=>t?new Date(t*1000).toLocaleDateString():'—';
const mmk=a=>a.balances.find(b=>b.currency==='MMK')||{earned:0,available:0,paid:0};

function AgentDecision({api,agent,onDone}){
 const [reason,setReason]=useState(''),[busy,setBusy]=useState(false),[notice,setNotice]=useState('');
 async function decide(status){setBusy(true);setNotice('');try{await api.request('developer/agents/'+agent.id+'/decision',{expected_revision:agent.revision,status,reason});setReason('');onDone()}catch(e){setNotice(e.message)}finally{setBusy(false)}}
 return <div><input aria-label={'Reason for '+agent.username} placeholder="Reason (required to reject or suspend)" maxLength={1000} value={reason} onChange={e=>setReason(e.target.value)}/><div className="buttons">{ACTIONS[agent.status].map(([s,label])=><button key={s} className={'button'+(s==='approved'?'':' secondary')} disabled={busy||(s!=='approved'&&!reason.trim())} onClick={()=>decide(s)}>{label}</button>)}</div>{notice&&<p role="alert">{notice}</p>}</div>;
}

function WithdrawalReview({api,w,onDone}){
 const [reason,setReason]=useState(''),[reference,setReference]=useState(''),[sent,setSent]=useState(false),[busy,setBusy]=useState(false),[notice,setNotice]=useState('');
 async function decide(decision){setBusy(true);setNotice('');try{await api.request('developer/agent-withdrawals/'+w.id+'/decision',{expected_revision:w.revision,decision,reason,payout_reference:reference,confirmed_paid:sent});onDone()}catch(e){setNotice(e.message)}finally{setBusy(false)}}
 return <div>
  {w.status==='requested'&&<><input aria-label="Rejection reason" placeholder="Reason (required to reject)" maxLength={1000} value={reason} onChange={e=>setReason(e.target.value)}/><div className="buttons"><button className="button" disabled={busy} onClick={()=>decide('approved')}>Approve</button><button className="button secondary" disabled={busy||!reason.trim()} onClick={()=>decide('rejected')}>Reject</button></div></>}
  {w.status==='approved'&&<><input aria-label="Payout reference" placeholder={METHOD_NAMES[w.method]+' transaction ID'} maxLength={160} value={reference} onChange={e=>setReference(e.target.value)}/><label className="check"><input type="checkbox" checked={sent} onChange={e=>setSent(e.target.checked)}/> I sent {money(w.amount,w.currency)} to this wallet</label><div className="buttons"><button className="button" disabled={busy||!reference.trim()||!sent} onClick={()=>decide('paid')}>Mark as paid</button></div><input aria-label="Rejection reason" placeholder="Reason, if not paying" maxLength={1000} value={reason} onChange={e=>setReason(e.target.value)}/><div className="buttons"><button className="button secondary" disabled={busy||!reason.trim()} onClick={()=>decide('rejected')}>Reject instead</button></div></>}
  {notice&&<p role="alert">{notice}</p>}
 </div>;
}

export default function AgentManagement({api}){
 const [agents,setAgents]=useState(null),[withdrawals,setWithdrawals]=useState([]),[commissions,setCommissions]=useState([]),[links,setLinks]=useState([]),[notice,setNotice]=useState('');
 const load=()=>Promise.all([api.request('developer/agents'),api.request('developer/agent-withdrawals'),api.request('developer/agent-commissions'),api.request('developer/agent-businesses')]).then(([a,w,c,l])=>{setAgents(a);setWithdrawals(w);setCommissions(c);setLinks(l)}).catch(e=>setNotice(e.message));
 useEffect(()=>{load()},[api]);
 if(!agents)return <section className="panel"><h2>Agents</h2><p>{notice||'Loading…'}</p></section>;
 const open=withdrawals.filter(w=>['requested','approved'].includes(w.status));
 return <>
  <section className="panel"><h2>Agent accounts</h2><p>Anyone can apply from the sign-in page. Approved Agents register new SME businesses and earn 20% of each approved monthly and 30% of each approved annual subscription payment at list price. Refunding a payment on the Payment system tab reverses its commission.</p>{notice&&<p role="alert">{notice}</p>}
   <div className="tablewrap"><table><thead><tr><th>Agent</th><th>Status</th><th>Businesses</th><th>Commission (MMK)</th><th>Decision</th></tr></thead><tbody>{agents.map(a=><tr key={a.id}><td>{a.full_name}<small>{a.username} · {a.phone}</small>{a.location?<small>{placeText(a.location)} · <a href={pinLink(a.location)} target="_blank" rel="noopener noreferrer">View pin on map</a></small>:<small>No location — applied before location was required</small>}{a.note&&<small>{a.note}</small>}<small>Applied {day(a.applied)}</small></td><td>{a.status}{a.reason&&<small>{a.reason}</small>}</td><td>{a.businesses}</td><td>{money(mmk(a).earned)} earned<small>{money(mmk(a).available)} available · {money(mmk(a).paid)} paid</small></td><td><AgentDecision api={api} agent={a} onDone={load}/></td></tr>)}{!agents.length&&<tr><td colSpan={5}>No Agent applications yet.</td></tr>}</tbody></table></div></section>
  <section className="panel"><h2>Withdrawal requests</h2><p>Pay each approved request yourself to the wallet shown, then record the transaction ID. Nothing is transferred automatically.</p><div className="tablewrap"><table><thead><tr><th>Agent</th><th>Amount</th><th>Wallet</th><th>Status</th><th>Review</th></tr></thead><tbody>{withdrawals.map(w=><tr key={w.id}><td>{w.agent_name}<small>{w.agent} · requested {day(w.requested)}</small></td><td>{money(w.amount,w.currency)}{['requested','approved'].includes(w.status)&&<small>Balance after reservations: {money(w.available)}</small>}</td><td>{METHOD_NAMES[w.method]}<small>{w.wallet.account_name} · {w.wallet.account_number}</small></td><td>{w.status}{w.payout_reference&&<small>Reference {w.payout_reference} · {day(w.paid_at)}</small>}{w.reason&&<small>{w.reason}</small>}</td><td>{['requested','approved'].includes(w.status)?<WithdrawalReview api={api} w={w} onDone={load}/>:'—'}</td></tr>)}{!withdrawals.length&&<tr><td colSpan={5}>No withdrawal requests yet.</td></tr>}</tbody></table></div>{open.length>0&&<p className="muted">{open.length} request{open.length===1?'':'s'} waiting.</p>}</section>
  <section className="panel"><h2>Commission ledger</h2><div className="tablewrap"><table><thead><tr><th>Date</th><th>Agent</th><th>Business</th><th>Payment</th><th>Commission</th><th>Status</th></tr></thead><tbody>{commissions.map(c=><tr key={c.id}><td>{day(c.created)}</td><td>{c.agent}</td><td>{c.business}</td><td>{c.months===12?'Annual':'Monthly'}<small>List price {money(c.base_amount,c.currency)}</small></td><td>{money(c.amount,c.currency)}<small>{c.rate_percent}%</small></td><td>{c.state}{c.reversal_reason&&<small>{c.reversal_reason}</small>}</td></tr>)}{!commissions.length&&<tr><td colSpan={6}>No commission yet.</td></tr>}</tbody></table></div></section>
  <section className="panel"><h2>Businesses registered by Agents</h2><div className="tablewrap"><table><thead><tr><th>Business</th><th>Agent</th><th>Registered</th></tr></thead><tbody>{links.map(l=><tr key={l.business_id}><td>{l.business}</td><td>{l.agent}</td><td>{day(l.registered)}</td></tr>)}{!links.length&&<tr><td colSpan={3}>None yet.</td></tr>}</tbody></table></div></section>
 </>;
}
