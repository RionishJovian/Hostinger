import React,{useEffect,useState} from 'react';
import {useSmeCopy} from './SMELocalization.jsx';

export function SafeRouterChanges({routers,plans,changes,act,busy,api,localize=true}){
 const c=useSmeCopy('routersPage',localize);
 const [router,setRouter]=useState('');
 const [seconds,setSeconds]=useState(25);
 const [selected,setSelected]=useState(changes[0]?.id||'');
 const [confirmed,setConfirmed]=useState(false);
 const [resolutionConfirmed,setResolutionConfirmed]=useState(false);
 const [settingsAvailable,setSettingsAvailable]=useState(false);
 const [wifiIface,setWifiIface]=useState('wifi2');
 const [ssid,setSsid]=useState('');
 const [security,setSecurity]=useState('open');
 const [passphrase,setPassphrase]=useState('');
 const [netCidr,setNetCidr]=useState('10.5.50.0/24');
 const [gateway,setGateway]=useState('10.5.50.1');
 const [poolStart,setPoolStart]=useState('10.5.50.10');
 const [poolEnd,setPoolEnd]=useState('10.5.50.254');
 const [dns,setDns]=useState('10.5.50.1');
 const [etherPort,setEtherPort]=useState('ether3');
 const [vlanId,setVlanId]=useState('50');
 const [vlanName,setVlanName]=useState('mm-guest-vlan-50');
 const change=changes.find(x=>x.id===selected);
 const eligible=routers.filter(r=>plans.some(p=>p.router_id===r.id&&p.reviewed_at));
 const portal=change?.operation==='hotspot_portal_publish';
 const guestWifi=change?.operation==='guest_wifi_settings';
 const guestNet=change?.operation==='guest_network_addressing';
 const guestVlan=change?.operation==='guest_vlan_external_ap';
 const phase=c.phases[change?.phase]||c.statuses[change?.status]||change?.status;
 const summary=x=>{
  if(x.operation==='hotspot_portal_publish')
   return x.diff?.profile_html_directory?`${x.diff.profile_html_directory.before} → ${x.diff.profile_html_directory.after}`:'portal publish';
  if(x.operation==='guest_wifi_settings')
   return `${x.diff?.ssid?.before||'?'} → ${x.diff?.ssid?.after||'?'} (${x.diff?.security_mode?.after||''})`;
  if(x.operation==='guest_network_addressing')
   return `${x.diff?.interface_address?.before||'?'} → ${x.diff?.interface_address?.after||'?'}`;
  if(x.operation==='guest_vlan_external_ap')
   return `${x.diff?.ethernet_port||'?'} vlan ${x.diff?.vlan_id?.after||x.desired?.vlan_id||'?'} → ${x.diff?.guest_bridge?.after||x.desired?.guest_bridge||'?'}`;
  return `${x.before?.persistent_keepalive_seconds} → ${x.desired?.persistent_keepalive_seconds} ${c.sec}`;
 };

 useEffect(()=>{
  if(!api?.request){setSettingsAvailable(false);return}
  let live=true;
  api.request('magic-connect/capability').then(x=>{
   if(live)setSettingsAvailable(x.router_settings_changes_available===true);
  }).catch(()=>{if(live)setSettingsAvailable(false)});
  return()=>{live=false};
 },[api]);

 async function preview(e){
  e.preventDefault();
  const result=await act('routers/'+router+'/changes/preview',{persistent_keepalive_seconds:Number(seconds)});
  if(result){setSelected(result.id);setConfirmed(false)}
 }
 async function previewWifi(e){
  e.preventDefault();
  const body={
   operation:'guest_wifi_settings',wifi_interface:wifiIface,ssid,security_mode:security,
  };
  if(security==='wpa2_wpa3_psk'&&passphrase)body.passphrase=passphrase;
  const result=await act('routers/'+router+'/changes/preview',body);
  if(result){setSelected(result.id);setConfirmed(false);setPassphrase('')}
 }
 async function previewNet(e){
  e.preventDefault();
  const result=await act('routers/'+router+'/changes/preview',{
   operation:'guest_network_addressing',wifi_interface:wifiIface,
   network_cidr:netCidr,gateway,pool_start:poolStart,pool_end:poolEnd,dns:dns||undefined,
  });
  if(result){setSelected(result.id);setConfirmed(false)}
 }
 async function previewVlan(e){
  e.preventDefault();
  const body={
   operation:'guest_vlan_external_ap',ethernet_port:etherPort,vlan_id:Number(vlanId),
  };
  if(vlanName)body.vlan_name=vlanName;
  if(wifiIface)body.hotspot_interface=wifiIface;
  const result=await act('routers/'+router+'/changes/preview',body);
  if(result){setSelected(result.id);setConfirmed(false)}
 }
 async function apply(){
  const result=await act('router-changes/'+change.id+'/apply',{expected_revision:change.revision,confirm_high_risk:true});
  if(result){setSelected(result.id);setConfirmed(false)}
 }
 async function resolve(choice){
  const result=await act('router-changes/'+change.id+'/resolve-conflict',{
   expected_revision:change.revision,choice,confirm_high_risk:choice==='keep_mikromagic'&&resolutionConfirmed,
  });
  if(result){setSelected(result.id);setResolutionConfirmed(false)}
 }

 return <section className="panel">
  <div className="panelhead"><h2>{c.safeTitle}</h2></div>
  <p>{c.safeIntro}</p>
  <form onSubmit={preview}>
   <div className="formgrid">
    <label className="field"><span>{c.reviewedRouter}</span>
     <select required value={router} onChange={e=>setRouter(e.target.value)}>
      <option value="">{c.selectRouter}</option>
      {eligible.map(r=><option key={r.id} value={r.id}>{r.name}</option>)}
     </select>
    </label>
    <label className="field"><span>{c.keepalive}</span>
     <input required type="number" min="1" max="3600" value={seconds} onChange={e=>setSeconds(e.target.value)}/>
    </label>
   </div>
   <button className="button secondary" disabled={busy||!router}>{c.inspect}</button>
  </form>
  <p className="muted">HotSpot portal publish is started from Guided first-shop acceptance after the owner reviews the exact proposal.</p>

  {settingsAvailable&&<>
   <h3>{c.guestWifiTitle}</h3>
   <p>{c.guestWifiIntro}</p>
   <form onSubmit={previewWifi}>
    <div className="formgrid">
     <label className="field"><span>{c.wifiInterface}</span>
      <input required maxLength={64} value={wifiIface} onChange={e=>setWifiIface(e.target.value)}/>
     </label>
     <label className="field"><span>{c.ssidLabel}</span>
      <input required maxLength={32} value={ssid} onChange={e=>setSsid(e.target.value)}/>
     </label>
     <label className="field"><span>{c.securityLabel}</span>
      <select value={security} onChange={e=>setSecurity(e.target.value)}>
       <option value="open">{c.securityOpen}</option>
       <option value="wpa2_wpa3_psk">{c.securityWpa}</option>
      </select>
     </label>
     {security==='wpa2_wpa3_psk'&&<label className="field"><span>{c.passphraseLabel}</span>
      <input type="password" autoComplete="new-password" minLength={8} maxLength={63} value={passphrase} onChange={e=>setPassphrase(e.target.value)}/>
     </label>}
    </div>
    <button className="button secondary" disabled={busy||!router}>{c.inspectWifi}</button>
   </form>

   <h3>{c.guestNetTitle}</h3>
   <p>{c.guestNetIntro}</p>
   <form onSubmit={previewNet}>
    <div className="formgrid">
     <label className="field"><span>{c.wifiInterface}</span>
      <input required maxLength={64} value={wifiIface} onChange={e=>setWifiIface(e.target.value)}/>
     </label>
     <label className="field"><span>{c.networkCidr}</span>
      <input required value={netCidr} onChange={e=>setNetCidr(e.target.value)}/>
     </label>
     <label className="field"><span>{c.gatewayLabel}</span>
      <input required value={gateway} onChange={e=>setGateway(e.target.value)}/>
     </label>
     <label className="field"><span>{c.poolStart}</span>
      <input required value={poolStart} onChange={e=>setPoolStart(e.target.value)}/>
     </label>
     <label className="field"><span>{c.poolEnd}</span>
      <input required value={poolEnd} onChange={e=>setPoolEnd(e.target.value)}/>
     </label>
     <label className="field"><span>{c.dnsLabel}</span>
      <input value={dns} onChange={e=>setDns(e.target.value)}/>
     </label>
    </div>
    <button className="button secondary" disabled={busy||!router}>{c.inspectNet}</button>
   </form>

   <h3>{c.guestVlanTitle}</h3>
   <p>{c.guestVlanIntro}</p>
   <form onSubmit={previewVlan}>
    <div className="formgrid">
     <label className="field"><span>{c.ethernetPort}</span>
      <input required maxLength={64} value={etherPort} onChange={e=>setEtherPort(e.target.value)}/>
     </label>
     <label className="field"><span>{c.vlanIdLabel}</span>
      <input required type="number" min={2} max={4094} value={vlanId} onChange={e=>setVlanId(e.target.value)}/>
     </label>
     <label className="field"><span>{c.vlanNameLabel}</span>
      <input maxLength={64} value={vlanName} onChange={e=>setVlanName(e.target.value)}/>
     </label>
     <label className="field"><span>{c.hotspotInterface}</span>
      <input required maxLength={64} value={wifiIface} onChange={e=>setWifiIface(e.target.value)}/>
     </label>
    </div>
    <button className="button secondary" disabled={busy||!router}>{c.inspectVlan}</button>
   </form>
  </>}

  {change&&<div className="safechange">
   <h3>{c.risk(change.risk.toUpperCase())}{portal?' · portal publish':''}{guestWifi?` · ${c.guestWifiTitle}`:''}{guestNet?` · ${c.guestNetTitle}`:''}{guestVlan?` · ${c.guestVlanTitle}`:''}</h3>
   <div className="details">
    <p><b>{c.phase}</b>{phase}</p>
    {portal?<>
     <p><b>Profile directory</b>{change.diff?.profile_html_directory?.before} → {change.diff?.profile_html_directory?.after}</p>
     <p><b>Package</b>revision {change.desired?.published_revision}</p>
    </>:guestWifi?<>
     <p><b>{c.ssidLabel}</b>{change.diff?.ssid?.before} → {change.diff?.ssid?.after}</p>
     <p><b>{c.securityLabel}</b>{change.diff?.security_mode?.before} → {change.diff?.security_mode?.after}</p>
     <p><b>{c.passphraseLabel}</b>{change.diff?.passphrase?.before} → {change.diff?.passphrase?.after}</p>
    </>:guestNet?<>
     <p><b>{c.networkCidr}</b>{change.diff?.interface_address?.before} → {change.diff?.interface_address?.after}</p>
     <p><b>{c.poolStart}</b>{change.diff?.pool_ranges?.before} → {change.diff?.pool_ranges?.after}</p>
     <p><b>HotSpot</b>{change.diff?.hotspot_address?.before} → {change.diff?.hotspot_address?.after}</p>
    </>:guestVlan?<>
     <p><b>{c.ethernetPort}</b>{change.diff?.ethernet_port}</p>
     <p><b>{c.vlanIdLabel}</b>{change.diff?.vlan_id?.before ?? '—'} → {change.diff?.vlan_id?.after}</p>
     <p><b>{c.vlanNameLabel}</b>{change.diff?.vlan_name?.before ?? '—'} → {change.diff?.vlan_name?.after}</p>
     <p><b>{c.guestBridge}</b>{change.diff?.guest_bridge?.before ?? '—'} → {change.diff?.guest_bridge?.after}</p>
    </>:<>
     <p><b>{c.before}</b>{c.seconds(change.before.persistent_keepalive_seconds)}</p>
     <p><b>{c.mmVersion}</b>{c.seconds(change.desired.persistent_keepalive_seconds)}</p>
    </>}
    <p><b>{c.impact}</b>{change.diff.impact}</p>
    <p><b>{c.backup}</b>{change.safety_backup_verified?c.backupYes:c.backupNo}</p>
    {!portal&&!guestWifi&&!guestNet&&!guestVlan&&<p><b>{c.actual}</b>{change.actual?.persistent_keepalive_seconds==null?c.notYet:c.seconds(change.actual.persistent_keepalive_seconds)}</p>}
    {change.gateway_deadline&&change.status==='verifying'&&<p><b>{c.deadline}</b>{new Date(change.gateway_deadline*1000).toLocaleString()}</p>}
   </div>
   {change.status==='previewed'&&<>
    <label><input type="checkbox" checked={confirmed} onChange={e=>setConfirmed(e.target.checked)}/> {c.confirm}</label>
    <button className="button" disabled={busy||!confirmed} onClick={apply}>{c.apply}</button>
   </>}
   {change.status==='conflict'&&<div className="conflict-resolution">
    <h3>{c.choose}</h3>
    <p>{c.merge}</p>
    <button className="button secondary" disabled={busy} onClick={()=>resolve('keep_router')}>{c.keepRouter}</button>
    <p className="muted">{c.keepRouterNote}</p>
    <label><input type="checkbox" checked={resolutionConfirmed} onChange={e=>setResolutionConfirmed(e.target.checked)}/> {c.keepMm}</label>
    <button className="button" disabled={busy||!resolutionConfirmed} onClick={()=>resolve('keep_mikromagic')}>{c.keepMmButton}</button>
    <p className="muted">{c.week}</p>
   </div>}
   {change.status==='recovery_required'&&<p role="alert"><b>{c.recoveryLead}</b> {c.recovery}</p>}
   <p className="muted">{c.proof}</p>
  </div>}
  <div className="tablewrap"><table>
   <thead><tr>{c.changeCols.map(h=><th key={h}>{h}</th>)}</tr></thead>
   <tbody>
    {changes.map(x=><tr key={x.id}>
     <td>{routers.find(r=>r.id===x.router_id)?.name||x.router_id}</td>
     <td>{summary(x)}</td>
     <td>{x.risk}</td>
     <td>{c.statuses[x.status]||x.status}</td>
     <td><button className="button secondary" onClick={()=>{setSelected(x.id);setConfirmed(false);setResolutionConfirmed(false)}}>{c.view}</button></td>
    </tr>)}
    {!changes.length&&<tr><td colSpan="5">{c.noChanges}</td></tr>}
   </tbody>
  </table></div>
 </section>;
}
