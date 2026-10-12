import React, {useEffect, useState} from 'react';

export default function FirstSiteAcceptance({api, sites, routers}) {
  const [siteId,setSiteId]=useState('');
  const [routerId,setRouterId]=useState('');
  const [result,setResult]=useState(null);
  const [error,setError]=useState('');
  const [busy,setBusy]=useState(false);
  const siteRouters=routers.filter(item=>item.site_id===siteId);
  useEffect(()=>{setRouterId('');setResult(null);setError('')},[siteId]);
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
  return <section className="panel">
    <div className="panelhead"><h2>Guided first-shop acceptance</h2>{result&&<span className="pill warn">Not ready</span>}</div>
    <p>Connect → Inspect → Explain → Confirm → Back up → Configure → Verify → First Customer Test → Ready.</p>
    <div className="formgrid">
      <label className="field"><span>Shop</span><select value={siteId} onChange={e=>setSiteId(e.target.value)}>
        <option value="">Select a shop</option>{sites.map(site=><option key={site.id} value={site.id}>{site.name}</option>)}
      </select></label>
      <label className="field"><span>Router for this shop</span><select disabled={!siteId} value={routerId} onChange={e=>{setRouterId(e.target.value);setResult(null)}}>
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
        <h3>Prepare a proposal-only HotSpot change</h3>
        <p className="muted">Choose the exact server observed by the latest trusted pre-flight. This prepares a diff and rollback review only; it does not generate commands or contact the router.</p>
        <div className="buttons">{result.hotspot_proposal.available_servers.map(server=><button className="button secondary" disabled={busy} key={server['.id']} onClick={()=>prepareHotspot(server['.id'])}>
          Prepare for {server.name||server['.id']} · {server.profile||'profile unknown'}
        </button>)}</div>
      </div>}
      {result.hotspot_proposal?.plan&&<div className="portalpreview">
        <div className="panelhead"><h3>HotSpot proposal</h3><span className={'pill '+(result.hotspot_proposal.plan.status==='reviewed'?'good':'warn')}>{result.hotspot_proposal.plan.status}</span></div>
        <div className="details">
          <p><b>Profile directory</b>{result.hotspot_proposal.plan.diff.profile_html_directory.before} → {result.hotspot_proposal.plan.diff.profile_html_directory.after}</p>
          <p><b>Shared-profile impact</b>{result.hotspot_proposal.plan.impact.warning}</p>
        </div>
        <details><summary>Required pre-apply checks and exclusions</summary>
          <ul>{result.hotspot_proposal.plan.impact.pre_apply_checks.map(item=><li key={item}>{item}</li>)}</ul>
          <p><b>Excluded:</b> {result.hotspot_proposal.plan.impact.excluded.join(', ')}.</p>
          <p><b>Rollback:</b> {result.hotspot_proposal.plan.rollback.sequence.join(' → ')}.</p>
        </details>
        {result.hotspot_proposal.plan.status==='prepared'&&<button className="button secondary" disabled={busy} onClick={reviewHotspot}>Confirm exact proposal scope</button>}
        <p className="muted">Confirmation records owner review only. It is not authorization to write to RouterOS, upload files, or start a hardware session.</p>
      </div>}
      <p className="muted">This view reads durable records only. It cannot contact or modify a router, accept owner-reported metadata as telemetry, issue a premature test voucher, or mark the shop Ready without real device evidence.</p>
    </>}
  </section>;
}
