import React, { useState } from 'react';
import { ssidProblem } from './site-settings.mjs';
import { useSmeCopy } from './SMELocalization.jsx';

function Field({ label, children }) {
  return <label className="field"><span>{label}</span>{children}</label>;
}

function ShopSettings({ sites, act, busy }) {
  const [site, setSite] = useState('');
  const [ssid, setSsid] = useState('');
  const chosen = sites.find(item => item.id === site);
  const problem = ssidProblem(ssid);
  return <section className="panel">
    <h2>Shop settings</h2>
    <form onSubmit={async event => {
      event.preventDefault();
      await act(`sites/${site}/settings`, { printed_ssid: ssid.trim() || null });
    }}>
      <div className="formgrid">
        <Field label="Shop"><select required value={site} onChange={event => { setSite(event.target.value); setSsid(sites.find(item => item.id === event.target.value)?.printed_ssid || ''); }}>
          <option value="">Select a shop</option>{sites.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}
        </select></Field>
        <Field label="Default printed Wi-Fi name (optional)"><input value={ssid} disabled={!site} onChange={event => setSsid(event.target.value)} placeholder="e.g. Golden Cafe WiFi" /></Field>
      </div>
      {problem && <p className="muted" role="status">{problem}</p>}
      <button className="button" disabled={busy || !site || !!problem || ssid.trim() === (chosen?.printed_ssid || '')}>Save shop settings</button>
    </form>
    <p className="muted">Printed on this shop's voucher cards and filled in for new print runs; you can still change it per print run. Leave it empty to print no Wi-Fi name. This label does not change the Wi-Fi network on your router or access points.</p>
  </section>;
}

export function SiteRegistry({ sites, act, busy }) {
  const [name, setName] = useState('');
  const [timezone, setTimezone] = useState('Asia/Yangon');
  const [ssid, setSsid] = useState('');
  const problem = ssidProblem(ssid);

  return <>
    <section className="panel">
      <div className="panelhead"><h2>Shops</h2></div>
      <div className="tablewrap">
        <table>
          <thead><tr><th>Shop</th><th>Timezone</th><th>Printed Wi-Fi name</th><th>Identifier</th></tr></thead>
          <tbody>{sites.map(site => <tr key={site.id}>
            <td>{site.name}</td><td>{site.timezone}</td><td>{site.printed_ssid || <small>Not set</small>}</td><td>{site.id}</td>
          </tr>)}</tbody>
        </table>
      </div>
    </section>
    {sites.length > 0 && <ShopSettings sites={sites} act={act} busy={busy} />}
    <section className="panel">
      <h2>Add a shop</h2>
      <form onSubmit={async event => {
        event.preventDefault();
        if (await act('sites', { name, timezone, printed_ssid: ssid.trim() || null })) { setName(''); setSsid(''); }
      }}>
        <div className="formgrid">
          <Field label="Shop name"><input required maxLength={120} value={name} onChange={event => setName(event.target.value)} /></Field>
          <Field label="Reporting timezone"><input required maxLength={80} value={timezone} onChange={event => setTimezone(event.target.value)} /></Field>
          <Field label="Printed Wi-Fi name (optional)"><input value={ssid} onChange={event => setSsid(event.target.value)} placeholder="e.g. Golden Cafe WiFi" /></Field>
        </div>
        {problem && <p className="muted" role="status">{problem}</p>}
        <button className="button" disabled={busy || !!problem}>Create shop</button>
      </form>
    </section>
  </>;
}

export function RouterRegistry({ sites, routers, act, busy, platform = false, localize = false }) {
  const c = useSmeCopy('routersPage', localize);
  const [site, setSite] = useState('');
  const [name, setName] = useState('');
  const [model, setModel] = useState('');
  const [version, setVersion] = useState('');
  const [preflight, setPreflight] = useState(null);
  const [sync, setSync] = useState(null);

  return <>
    {!platform && <section className="panel" id="register-router">
      <div className="panelhead"><h2>{c.registerTitle}</h2></div>
      <form onSubmit={async event => {
        event.preventDefault();
        if (await act('routers', { site_id: site, name, model, reported_routeros: version })) setName('');
      }}>
        <div className="formgrid">
          <Field label={c.shop}><select required value={site} onChange={event => setSite(event.target.value)}>
            <option value="">{c.selectShop}</option>{sites.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}
          </select></Field>
          <Field label={c.routerName}><input required maxLength={120} value={name} onChange={event => setName(event.target.value)} /></Field>
          <Field label={c.model}><input required maxLength={120} value={model} onChange={event => setModel(event.target.value)} placeholder={c.modelHint} /></Field>
          <Field label={c.version}><input maxLength={40} value={version} onChange={event => setVersion(event.target.value)} placeholder={c.versionHint} /></Field>
        </div>
        <button className="button" disabled={busy || !site}>{c.register}</button>
      </form>
      <p className="muted">{c.registerNote}</p>
    </section>}
    <section className="panel">
      <div className="panelhead"><h2>{platform ? c.fleetTitle : c.listTitle}</h2></div>
      <div className="tablewrap">
        <table>
          <thead><tr>{(platform ? c.cols.slice(0, 5) : c.cols).map(label => <th key={label}>{label}</th>)}</tr></thead>
          <tbody>{routers.map(router => <tr key={router.id}>
            <td>{router.name}</td>
            <td>{sites.find(item => item.id === router.site_id)?.name || router.site_id}</td>
            <td>{router.model}<small>{router.reported_routeros || c.versionMissing} · {c.ownerReported}</small></td>
            <td><span className="pill warn">{c.unverified}</span></td>
            <td>{router.hub_id ? <>{c.assigned}<small>{router.hub_id}</small></> : c.notAssigned}</td>
            {!platform && <td><button className="button secondary" disabled={busy} onClick={async () => {
              const result = await act(`routers/${router.id}/preflight`, {});
              if (result) setPreflight(result);
            }}>{c.preflight}</button> <button className="button secondary" disabled={busy} onClick={async () => {
              const result = await act(`routers/${router.id}/hotspot-sync`, {});
              if (result) setSync({ ...result, router: router.name });
            }}>{c.syncVouchers}</button></td>}
          </tr>)}
          {!routers.length && <tr><td colSpan={platform ? 5 : 6}>{c.empty}</td></tr>}</tbody>
        </table>
      </div>
    </section>
    {sync && <section className="panel">
      <div className="panelhead"><h2>{c.syncTitle} · {sync.router}</h2><button className="button secondary" onClick={() => setSync(null)}>{c.close}</button></div>
      <div className="details">
        <p><b>{c.syncApplied}</b>{sync.applied}</p>
        <p><b>{c.syncInSync}</b>{sync.in_sync}</p>
        <p><b>{c.syncPending}</b>{sync.pending}</p>
        <p><b>{c.syncFailed}</b>{sync.failed}</p>
        {Object.entries(sync.skipped || {}).map(([reason, count]) => <p key={reason}><b>{c.syncSkipped}</b>{count} · {c.syncReasons[reason] || reason}</p>)}
      </div>
      {sync.aborted && <div className="callout">{c.syncAborted}</div>}
      <div className="callout">{c.syncNote}</div>
    </section>}
    {preflight && <section className="panel">
      <div className="panelhead"><h2>{c.preflightTitle}</h2><button className="button secondary" onClick={() => setPreflight(null)}>{c.close}</button></div>
      {(() => {
        const evidence = preflight.evidence || {};
        const compatibility = evidence.compatibility || { status: 'needs_review', reasons: [c.unavailable] };
        const compatible = compatibility.status === 'compatible_for_safe_change';
        return <>
          <div className="details">
            <p><b>{c.compatibility}</b><span className={'pill ' + (compatible ? 'good' : compatibility.status === 'unsupported' ? 'danger' : 'warn')}>{compatible ? c.compatible : compatibility.status === 'unsupported' ? c.unsupported : c.needsReview}</span></p>
            <p><b>{c.detectedModel}</b>{evidence.identity?.model || evidence.identity?.['board-name'] || c.notReported}</p>
            <p><b>{c.routeros}</b>{evidence.identity?.version || c.notReported}</p>
            <p><b>{c.cpu}</b>{compatibility.architecture || c.notReported}{compatibility.architecture && !compatibility.architecture_recognized_for_routeros7 ? c.reviewRequired : ''}</p>
            <p><b>{c.wireguard}</b>{compatibility.wireguard_detected ? c.wgYes : c.wgNo}</p>
            <p><b>{c.permissions}</b>{c.permissionsBody(compatibility.management_permissions?.monitoring_read)}</p>
            <p><b>{c.hotspot}</b>{evidence.capabilities?.hotspot ? c.detected : c.notDetected}</p>
            <p><b>{c.change}</b>{c.changeNone}</p>
            <p><b>{c.connection}</b>{preflight.connection?.connection_verified ? c.verified : c.notVerified}</p>
          </div>
          {compatibility.reasons?.length > 0 && <div className="callout">{c.guidance}{compatibility.reasons.join(' ')}</div>}
          <div className="callout">{c.preflightNote}</div>
        </>;
      })()}
    </section>}
  </>;
}
