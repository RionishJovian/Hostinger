import React,{useEffect,useState} from 'react';
import {useSmeCopy} from './SMELocalization.jsx';

export default function FirstSiteAcceptance({api,sites,routers}){
 const c=useSmeCopy('firstSite');
 const [siteId,setSiteId]=useState('');
 const [routerId,setRouterId]=useState('');
 const [result,setResult]=useState(null);
 const [error,setError]=useState('');
 const [busy,setBusy]=useState(false);
 const [publish,setPublish]=useState(null);
 const [confirmed,setConfirmed]=useState(false);
 const siteRouters=routers.filter(item=>item.site_id===siteId);
 useEffect(()=>{setRouterId('');setResult(null);setError('');setPublish(null);setConfirmed(false)},[siteId]);
 async function inspect(){
  setBusy(true);setError('');
  try{
   const query=routerId?'?router_id='+encodeURIComponent(routerId):'';
   setResult(await api.request('sites/'+encodeURIComponent(siteId)+'/first-site-acceptance'+query));
  }catch(e){setResult(null);setError(e.message)}finally{setBusy(false)}
 }
 async function prepareHotspot(serverId){
  setBusy(true);setError('');
  try{
   await api.request('routers/'+encodeURIComponent(result.selected_router_id)+'/hotspot-portal-plans',{
    evidence_id:result.hotspot_proposal.preflight_evidence_id,server_id:serverId,
   });
   await inspect();
  }catch(e){setError(e.message);setBusy(false)}
 }
 async function reviewHotspot(){
  setBusy(true);setError('');
  try{
   const plan=result.hotspot_proposal.plan;
   await api.request('hotspot-portal-plans/'+encodeURIComponent(plan.id)+'/review',{
    expected_revision:plan.revision,confirm_exact_scope:true,
   });
   await inspect();
  }catch(e){setError(e.message);setBusy(false)}
 }
 async function previewPublish(){
  setBusy(true);setError('');setConfirmed(false);
  try{
   const change=await api.request('routers/'+encodeURIComponent(result.selected_router_id)+'/changes/preview',{
    operation:'hotspot_portal_publish',hotspot_portal_plan_id:result.hotspot_proposal.plan.id,
   });
   setPublish(change);await inspect();
  }catch(e){setPublish(null);setError(e.message);setBusy(false)}
 }
 async function applyPublish(){
  setBusy(true);setError('');
  try{
   const change=await api.request('router-changes/'+encodeURIComponent(publish.id)+'/apply',{
    expected_revision:publish.revision,confirm_high_risk:true,
   });
   setPublish(change);setConfirmed(false);await inspect();
  }catch(e){setError(e.message);setBusy(false)}
 }
 const plan=result?.hotspot_proposal?.plan;
 const canPublish=plan?.status==='reviewed'&&!result?.portal_publish?.applied;
 const stageLabel=stage=>(c.stages&&c.stages[stage.key])||stage.label;
 const statusLabel=status=>status==='complete'?c.complete:status==='blocked'?c.blocked:c.pending;
 return <section className="panel">
  <div className="panelhead"><h2>{c.title}</h2>{result&&<span className="pill warn">{c.notReady}</span>}</div>
  <p>{c.path}</p>
  <div className="formgrid">
   <label className="field"><span>{c.shop}</span><select value={siteId} onChange={e=>setSiteId(e.target.value)}>
    <option value="">{c.selectShop}</option>{sites.map(site=><option key={site.id} value={site.id}>{site.name}</option>)}
   </select></label>
   <label className="field"><span>{c.router}</span><select disabled={!siteId} value={routerId} onChange={e=>{setRouterId(e.target.value);setResult(null);setPublish(null)}}>
    <option value="">{siteRouters.length===1?c.onlyRouter:c.selectRouter}</option>{siteRouters.map(router=><option key={router.id} value={router.id}>{router.name}</option>)}
   </select></label>
  </div>
  <button className="button secondary" disabled={busy||!siteId||(siteRouters.length>1&&!routerId)} onClick={inspect}>{busy?c.checking:c.reviewGates}</button>
  {error&&<p role="alert">{error}</p>}
  {result&&<>
   <div className="tablewrap"><table><thead><tr>{c.heads.map(h=><th key={h}>{h}</th>)}</tr></thead><tbody>
    {result.stages.map(stage=><tr key={stage.key}><td>{stageLabel(stage)}</td><td><span className={'pill '+(stage.status==='complete'?'good':'warn')}>{statusLabel(stage.status)}</span></td><td>{stage.detail}</td></tr>)}
   </tbody></table></div>
   <div className="callout"><b>{c.next}</b> {result.next_action}</div>
   {result.hotspot_proposal&&!result.hotspot_proposal.plan&&result.hotspot_proposal.available_servers.length>0&&<div className="portalpreview">
    <h3>{c.prepareTitle}</h3>
    <p className="muted">{c.prepareNote}</p>
    <div className="buttons">{result.hotspot_proposal.available_servers.map(server=><button className="button secondary" disabled={busy} key={server['.id']} onClick={()=>prepareHotspot(server['.id'])}>
     {c.prepareFor(server.name||server['.id'],server.profile||c.profileUnknown)}
    </button>)}</div>
   </div>}
   {plan&&<div className="portalpreview">
    <div className="panelhead"><h3>{c.proposalTitle}</h3><span className={'pill '+(plan.status==='reviewed'?'good':'warn')}>{plan.status}</span></div>
    <div className="details">
     <p><b>{c.profileDir}</b>{plan.diff.profile_html_directory.before} → {plan.diff.profile_html_directory.after}</p>
     <p><b>{c.sharedImpact}</b>{plan.impact.warning}</p>
    </div>
    <details><summary>{c.checksSummary}</summary>
     <ul>{plan.impact.pre_apply_checks.map(item=><li key={item}>{item}</li>)}</ul>
     <p><b>{c.excluded}</b> {plan.impact.excluded.join(', ')}.</p>
     <p><b>{c.rollback}</b> {plan.rollback.sequence.join(' → ')}.</p>
    </details>
    {plan.status==='prepared'&&<button className="button secondary" disabled={busy} onClick={reviewHotspot}>{c.confirmScope}</button>}
    {canPublish&&!publish&&<button className="button" disabled={busy} onClick={previewPublish}>{c.publishPreview}</button>}
    {publish&&<div className="safechange">
     <h3>{c.publishRisk(publish.risk.toUpperCase())}</h3>
     <div className="details">
      <p><b>{c.status}</b>{publish.status}</p>
      <p><b>{c.directory}</b>{publish.diff?.profile_html_directory?.before} → {publish.diff?.profile_html_directory?.after}</p>
      <p><b>{c.backupVerified}</b>{publish.safety_backup_verified?c.backupYes:c.backupRequired}</p>
      <p><b>{c.realAcceptance}</b>{publish.real_device_acceptance||'not_yet_performed'}</p>
     </div>
     {publish.status==='previewed'&&<>
      <label><input type="checkbox" checked={confirmed} onChange={e=>setConfirmed(e.target.checked)}/> {c.confirmApply}</label>
      <button className="button" disabled={busy||!confirmed} onClick={applyPublish}>{c.applyPublish}</button>
     </>}
     {publish.status==='applied'&&<p className="muted">{c.appliedNote}</p>}
     {publish.status==='rolled_back'&&<p role="alert">{c.rolledBack}</p>}
     {publish.status==='recovery_required'&&<p role="alert">{c.recoveryRequired}</p>}
    </div>}
    {result.portal_publish?.applied&&!publish&&<p className="muted">{c.alreadyApplied}</p>}
   </div>}
   <p className="muted">{c.foot}</p>
  </>}
 </section>;
}
