import React, {useEffect, useState} from 'react';

export default function FirstSiteAcceptance({api, sites, routers}) {
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
  return <section className="panel">
    <div className="panelhead"><h2>Guided first-shop acceptance</h2>{result&&<span className="pill warn">Not ready</span>}</div>
    <p>Connect → Inspect → Explain → Confirm → Back up → Configure → Verify → First Customer Test → Ready.</p>
    <div className="formgrid">
      <label className="field"><span>Shop</span><select value={siteId} onChange={e=>setSiteId(e.target.value)}>
        <option value="">Select a shop</option>{sites.map(site=><option key={site.id} value={site.id}>{site.name}</option>)}
      </select></label>
      <label className="field"><span>Router for this shop</span><select disabled={!siteId} value={routerId} onChange={e=>{setRouterId(e.target.value);setResult(null);setPublish(null)}}>
        <option value="">{siteRouters.length===1?'Use the only registered router':'Select a router'}</option>{siteRouters.map(router=><option key={router.id} value={router.id}>{router.name}</option>)}
      </select></label>
    </div>
    <button className="button secondary" disabled={busy||!siteId||(siteRouters.length>1&&!routerId)} onClick={inspect}>{busy?'Checking evidence…':'Review acceptance gates'}</button>
    {error&&<p role="alert">{error}</p>}
    {result&&<>
      <div className="tablewrap"><table><thead><tr><th>Stage</th><th>Status</th><th>Evidence boundary</th></tr></thead><tbody>
        {result.stages.map(stage=><tr key={stage.key}><td>{stage.label}</td><td><span className={'pill '+(stage.status==='complete'?'good':'warn')}>{stage.status==='complete'?'Complete':stage.status==='blocked'?'Blocked':'Pending'}</span></td><td>{stage.detail}</td></tr>)}
      </tbody></table></div>
      <div className="callout"><b>Next:</b> {result.next_action}</div>
      {result.hotspot_proposal&&!result.hotspot_proposal.plan&&result.hotspot_proposal.available_servers.length>0&&<div className="portalpreview">
        <h3>Prepare a HotSpot portal change</h3>
        <p className="muted">Choose the exact server observed by the latest trusted pre-flight. This prepares the diff for Publish to MikroTik; it does not write to the router yet.</p>
        <div className="buttons">{result.hotspot_proposal.available_servers.map(server=><button className="button secondary" disabled={busy} key={server['.id']} onClick={()=>prepareHotspot(server['.id'])}>
          Prepare for {server.name||server['.id']} · {server.profile||'profile unknown'}
        </button>)}</div>
      </div>}
      {plan&&<div className="portalpreview">
        <div className="panelhead"><h3>HotSpot proposal</h3><span className={'pill '+(plan.status==='reviewed'?'good':'warn')}>{plan.status}</span></div>
        <div className="details">
          <p><b>Profile directory</b>{plan.diff.profile_html_directory.before} → {plan.diff.profile_html_directory.after}</p>
          <p><b>Shared-profile impact</b>{plan.impact.warning}</p>
        </div>
        <details><summary>Required pre-apply checks and exclusions</summary>
          <ul>{plan.impact.pre_apply_checks.map(item=><li key={item}>{item}</li>)}</ul>
          <p><b>Excluded:</b> {plan.impact.excluded.join(', ')}.</p>
          <p><b>Rollback:</b> {plan.rollback.sequence.join(' → ')}.</p>
        </details>
        {plan.status==='prepared'&&<button className="button secondary" disabled={busy} onClick={reviewHotspot}>Confirm exact proposal scope</button>}
        {canPublish&&!publish&&<button className="button" disabled={busy} onClick={previewPublish}>Publish to MikroTik (preview Safe Change)</button>}
        {publish&&<div className="safechange">
          <h3>Publish to MikroTik · {publish.risk.toUpperCase()} risk</h3>
          <div className="details">
            <p><b>Status</b>{publish.status}</p>
            <p><b>Directory</b>{publish.diff?.profile_html_directory?.before} → {publish.diff?.profile_html_directory?.after}</p>
            <p><b>Backup verified</b>{publish.safety_backup_verified?'Yes':'Required before apply'}</p>
            <p><b>Real-router acceptance</b>{publish.real_device_acceptance||'not_yet_performed'}</p>
          </div>
          {publish.status==='previewed'&&<>
            <label><input type="checkbox" checked={confirmed} onChange={e=>setConfirmed(e.target.checked)}/> I confirm backup, create-only install, selected-profile switch, verify and rollback</label>
            <button className="button" disabled={busy||!confirmed} onClick={applyPublish}>Apply Publish to MikroTik</button>
          </>}
          {publish.status==='applied'&&<p className="muted">Simulated or live router evidence recorded for this package. First Customer Test and Site Ready still require a real phone on a real router.</p>}
          {publish.status==='rolled_back'&&<p role="alert">Publish failed and the profile directory was restored.</p>}
          {publish.status==='recovery_required'&&<p role="alert">Recovery required: rollback could not be confirmed.</p>}
        </div>}
        {result.portal_publish?.applied&&!publish&&<p className="muted">A verified Safe Change already applied this package on the selected router. Real-router acceptance remains pending.</p>}
      </div>}
      <p className="muted">This view cannot mark the shop Ready without real device evidence. Offline simulated apply is software progress only.</p>
    </>}
  </section>;
}
