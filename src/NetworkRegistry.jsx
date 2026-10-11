import React, { useState } from 'react';
import { ssidProblem } from './site-settings.mjs';

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
      <div className="panelhead"><h2>Business sites</h2></div>
      <div className="tablewrap">
        <table>
          <thead><tr><th>Site</th><th>Timezone</th><th>Printed Wi-Fi name</th><th>Identifier</th></tr></thead>
          <tbody>{sites.map(site => <tr key={site.id}>
            <td>{site.name}</td><td>{site.timezone}</td><td>{site.printed_ssid || <small>Not set</small>}</td><td>{site.id}</td>
          </tr>)}</tbody>
        </table>
      </div>
    </section>
    {sites.length > 0 && <ShopSettings sites={sites} act={act} busy={busy} />}
    <section className="panel">
      <h2>Add a site</h2>
      <form onSubmit={async event => {
        event.preventDefault();
        if (await act('sites', { name, timezone, printed_ssid: ssid.trim() || null })) { setName(''); setSsid(''); }
      }}>
        <div className="formgrid">
          <Field label="Site name"><input required maxLength={120} value={name} onChange={event => setName(event.target.value)} /></Field>
          <Field label="Reporting timezone"><input required maxLength={80} value={timezone} onChange={event => setTimezone(event.target.value)} /></Field>
          <Field label="Printed Wi-Fi name (optional)"><input value={ssid} onChange={event => setSsid(event.target.value)} placeholder="e.g. Golden Cafe WiFi" /></Field>
        </div>
        {problem && <p className="muted" role="status">{problem}</p>}
        <button className="button" disabled={busy || !!problem}>Create site</button>
      </form>
    </section>
  </>;
}

export function RouterRegistry({ sites, routers, act, busy, platform = false }) {
  const [site, setSite] = useState('');
  const [name, setName] = useState('');
  const [model, setModel] = useState('');
  const [version, setVersion] = useState('');
  const [preflight, setPreflight] = useState(null);

  return <>
    {!platform && <section className="panel" id="register-router">
      <div className="panelhead"><h2>Register a MikroTik</h2></div>
      <form onSubmit={async event => {
        event.preventDefault();
        if (await act('routers', { site_id: site, name, model, reported_routeros: version })) setName('');
      }}>
        <div className="formgrid">
          <Field label="Business site"><select required value={site} onChange={event => setSite(event.target.value)}>
            <option value="">Select a site</option>{sites.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}
          </select></Field>
          <Field label="Router name"><input required maxLength={120} value={name} onChange={event => setName(event.target.value)} /></Field>
          <Field label="MikroTik model"><input required maxLength={120} value={model} onChange={event => setModel(event.target.value)} placeholder="Enter the model shown on the device" /></Field>
          <Field label="Reported RouterOS version"><input maxLength={40} value={version} onChange={event => setVersion(event.target.value)} placeholder="Optional · verified during post-connection preflight" /></Field>
        </div>
        <button className="button" disabled={busy || !site}>Register router</button>
      </form>
      <p className="muted">Registration stores owner-reported details only. Initial bootstrap review is separate and does not claim remote device verification. Compatibility is based on authenticated device discovery, not this form or a single reference model. Router credentials are installed separately by the platform operator as protected secrets; passwords and keys are never entered here.</p>
    </section>}
    <section className="panel">
      <div className="panelhead"><h2>{platform ? 'Platform router fleet' : 'Site routers'}</h2></div>
      <div className="tablewrap">
        <table>
          <thead><tr>{['Router', 'Site', 'Model / RouterOS', 'Connection', 'Magic Hub', ...(!platform ? ['Post-connection check'] : [])].map(label => <th key={label}>{label}</th>)}</tr></thead>
          <tbody>{routers.map(router => <tr key={router.id}>
            <td>{router.name}</td>
            <td>{sites.find(item => item.id === router.site_id)?.name || router.site_id}</td>
            <td>{router.model}<small>{router.reported_routeros || 'Version not reported'} · owner reported</small></td>
            <td><span className="pill warn">Unverified</span></td>
            <td>{router.hub_id ? <>Assigned<small>{router.hub_id}</small></> : 'Not assigned'}</td>
            {!platform && <td><button className="button secondary" disabled={busy} onClick={async () => {
              const result = await act(`routers/${router.id}/preflight`, {});
              if (result) setPreflight(result);
            }}>Run post-connection preflight</button></td>}
          </tr>)}
          {!routers.length && <tr><td colSpan={platform ? 5 : 6}>No routers registered yet.</td></tr>}</tbody>
        </table>
      </div>
    </section>
    {preflight && <section className="panel">
      <div className="panelhead"><h2>Post-connection MikroTik preflight</h2><button className="button secondary" onClick={() => setPreflight(null)}>Close</button></div>
      {(() => {
        const evidence = preflight.evidence || {};
        const compatibility = evidence.compatibility || { status: 'needs_review', reasons: ['Compatibility details are unavailable.'] };
        const compatible = compatibility.status === 'compatible_for_safe_change';
        return <>
          <div className="details">
            <p><b>Compatibility</b><span className={'pill ' + (compatible ? 'good' : compatibility.status === 'unsupported' ? 'danger' : 'warn')}>{compatible ? 'Compatible for Safe Change review' : compatibility.status === 'unsupported' ? 'Unsupported' : 'Needs compatibility review'}</span></p>
            <p><b>Detected model</b>{evidence.identity?.model || evidence.identity?.['board-name'] || 'Not reported'}</p>
            <p><b>RouterOS</b>{evidence.identity?.version || 'Not reported'}</p>
            <p><b>CPU architecture</b>{compatibility.architecture || 'Not reported'}{compatibility.architecture && !compatibility.architecture_recognized_for_routeros7 ? ' · review required' : ''}</p>
            <p><b>WireGuard</b>{compatibility.wireguard_detected ? 'Detected by authenticated read' : 'Not detected'}</p>
            <p><b>Management permissions</b>Monitoring read {compatibility.management_permissions?.monitoring_read || 'unverified'}; Safe Change write not tested</p>
            <p><b>HotSpot capability</b>{evidence.capabilities?.hotspot ? 'Detected' : 'Not detected'}</p>
            <p><b>Configuration change</b>None · read-only</p>
            <p><b>Connection verification</b>{preflight.connection?.connection_verified ? 'Authenticated management read verified after handshake' : 'Not verified'}</p>
          </div>
          {compatibility.reasons?.length > 0 && <div className="callout">Compatibility guidance: {compatibility.reasons.join(' ')}</div>}
          <div className="callout">This post-connection check uses authenticated, certificate-verified reads. It is not model certification and does not prove HotSpot enforcement, rollback, or site readiness. A fresh handshake alone is insufficient for Connected; Safe Change remains separately gated.</div>
        </>;
      })()}
    </section>}
  </>;
}
