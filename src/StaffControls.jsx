import React,{useEffect,useState} from 'react';
import {useSmeCopy} from './SMELocalization.jsx';

export default function StaffControls({api}){
 const c=useSmeCopy('account');
 const [staff,setStaff]=useState([]),[busy,setBusy]=useState(false),[notice,setNotice]=useState(''),[selected,setSelected]=useState(null),[active,setActive]=useState(true),[reason,setReason]=useState('');
 useEffect(()=>{api.request('staff').then(setStaff).catch(e=>setNotice(e.message))},[api]);
 async function save(e){e.preventDefault();setBusy(true);try{await api.request('staff/'+selected.id,{expected_revision:selected.revision,profile:selected.profile,active,reason});setSelected(null);setStaff(await api.request('staff'));setNotice(c.staffUpdated)}catch(e){setNotice(e.message)}finally{setBusy(false)}}
 if(!staff.length&&!notice)return null;
 return <section className="panel"><h2>{c.staffTitle}</h2><p>{c.staffIntro}</p>{notice&&<p role="status">{notice}</p>}{staff.length?<div className="tablewrap"><table><thead><tr>{c.staffHeads.map(h=><th key={h}>{h}</th>)}</tr></thead><tbody>{staff.map(s=><tr key={s.id}><td>{s.username}</td><td>{s.profile}</td><td>{s.active?c.staffActive:c.staffDisabled}</td><td><button className="button secondary" disabled={busy} onClick={()=>{setSelected(s);setActive(s.active);setReason('')}}>{c.changeState}</button></td></tr>)}</tbody></table></div>:<p className="muted">{c.noStaff}</p>}{selected&&<form onSubmit={save}><h3>{selected.username}</h3><label className="check"><input type="checkbox" checked={active} onChange={e=>setActive(e.target.checked)}/> {c.accountActive}</label><label className="field"><span>{c.reason}</span><textarea required maxLength={1000} value={reason} onChange={e=>setReason(e.target.value)}/></label><button className="button" disabled={busy}>{c.saveStaff}</button><button type="button" className="button secondary" onClick={()=>setSelected(null)}>{c.cancel}</button></form>}</section>;
}