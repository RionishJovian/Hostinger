import React,{useState} from 'react';

const labels={awaiting_review:'Awaiting payment review',evidence_needed:'More evidence needed',payment_rejected:'Payment rejected',provisioning_pending:'Provisioning pending',access_stopped:'Access stopped',quota_exhausted:'Allowance exhausted',locally_active_unverified:'Activation recorded · network unverified',unknown:'Status unavailable'};
const formatBytes=value=>value>=1_000_000_000?(value/1_000_000_000).toFixed(2)+' GB':Math.max(0,value/1_000_000).toFixed(0)+' MB';
const formatTime=value=>value>=3600?(value/3600).toFixed(1)+' h':Math.ceil(value/60)+' min';

export default function GuestAccessStatus({api,diagnosis,sites=[]}){
 const [current,setCurrent]=useState(diagnosis),[busy,setBusy]=useState(false),[error,setError]=useState('');
 async function refresh(){setBusy(true);setError('');try{setCurrent(await api.request('my-access/diagnosis'))}catch(e){setError(e.message)}finally{setBusy(false)}}
 const evidence=current?.network_evidence;
 return <section className="panel"><div className="panelhead"><h2>Access check</h2><button className="button secondary" type="button" disabled={busy} onClick={refresh}>{busy?'Checking…':'Check again'}</button></div>
  <div className="callout"><b>{evidence?.status==='unavailable'?'Live network check unavailable':'Network evidence available'}</b><p>{evidence?.detail||'No diagnosis has been loaded.'}</p><small>Freshness: {evidence?.freshness||'unknown'} · The app will not guess whether a MikroTik session is online.</small></div>
  {error&&<p role="alert">{error}</p>}
  {current?.items?.map(item=><article className="pass" key={item.kind+item.id}><h3>{item.name}</h3><p><span className="pill warn">{labels[item.state]||item.state}</span></p><small>{sites.find(site=>site.id===item.site_id)?.name||item.site_id||'Business-wide'} · Reference {item.id}</small><p>{item.detail}</p>{item.voucher_code_hint&&<p>Voucher ending: ••••{item.voucher_code_hint}</p>}{item.quota?.data&&<p>Stored data record: {formatBytes(item.quota.data.remaining_bytes)} remaining of {formatBytes(item.quota.data.limit_bytes)}.</p>}{item.quota?.time&&<p>Stored time record: {formatTime(item.quota.time.remaining_seconds)} remaining of {formatTime(item.quota.time.limit_seconds)}.</p>}<p><b>What you can do:</b> {item.safe_action}</p>{item.quota&&<small>Usage source: MikroMagic record, not router verified. Last router observation: unavailable.</small>}</article>)}
  {!current?.items?.length&&<p>No payment or pass records are attached to this guest account.</p>}
 </section>;
}
