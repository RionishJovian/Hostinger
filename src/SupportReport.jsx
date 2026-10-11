import React, { useEffect, useState } from 'react';
import { reportText, reportFileName, shopTime, firstSentence } from './support-report.mjs';

function download(report) {
  const url = URL.createObjectURL(new Blob([reportText(report)], { type: 'text/plain;charset=utf-8' }));
  const link = document.createElement('a');
  link.href = url; link.download = reportFileName(report); link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function ReportView({ item, onShare, busy }) {
  const report = item.report;
  return <div className="support-report">
    <ul className="support-causes">{report.likely_causes.map((cause, index) => <li key={index}><strong>{cause.text}</strong><small>Based on: {cause.evidence}</small></li>)}</ul>
    <pre className="support-text">{reportText(report)}</pre>
    <div className="actions">
      <button type="button" className="button secondary" onClick={() => navigator.clipboard?.writeText(reportText(report))}>Copy report</button>
      <button type="button" className="button secondary" onClick={() => download(report)}>Download .txt</button>
      {onShare && (item.shared_at
        ? <span className="pill good">Shared with MikroMagic support {shopTime(item.shared_at, report.shop.timezone)}</span>
        : <button type="button" className="button" disabled={busy} onClick={() => onShare(item)}>Share with MikroMagic support</button>)}
    </div>
  </div>;
}

export default function SupportReport({ api, sites }) {
  const [site, setSite] = useState('');
  const [description, setDescription] = useState('');
  const [items, setItems] = useState([]);
  const [open, setOpen] = useState(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState('');

  useEffect(() => {
    let live = true;
    setItems([]); setOpen(null); setNotice('');
    if (site) api.request(`sites/${site}/support-reports`).then(rows => { if (live) { setItems(rows); setOpen(rows[0]?.id || null); } }).catch(error => live && setNotice(error.message));
    return () => { live = false; };
  }, [site]);

  async function run(task, message) {
    setBusy(true);
    try { await task(); setNotice(message); } catch (error) { setNotice(error.message); } finally { setBusy(false); }
  }
  const create = () => run(async () => {
    const item = await api.request(`sites/${site}/support-reports`, { description });
    setItems([item, ...items]); setOpen(item.id); setDescription('');
  }, 'Help report created. Nothing on your network was changed.');
  const share = item => run(async () => {
    const updated = await api.request(`support-reports/${item.id}/share`, {});
    setItems(items.map(row => row.id === updated.id ? updated : row));
  }, 'Shared. MikroMagic support can read this report; they cannot change anything.');

  const current = items.find(item => item.id === open);
  return <section className="panel support-panel" id="get-help">
    <h2>Get help</h2>
    <p className="muted">Creates a help report for one shop from what MikroMagic already knows: hours and maintenance, routers and devices, outages and how long they lasted, recent actions, and the likely cause based on that evidence. Passwords, voucher codes, API credentials and WireGuard keys are never included. You choose whether to share it with MikroMagic support.</p>
    <form onSubmit={event => { event.preventDefault(); create(); }}>
      <div className="formgrid">
        <label className="field"><span>Shop</span><select value={site} onChange={event => setSite(event.target.value)}>
          <option value="">Select a shop</option>{sites.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}
        </select></label>
      </div>
      <label className="field"><span>What is wrong? (optional)</span><textarea maxLength={1000} rows={3} value={description} disabled={!site} onChange={event => setDescription(event.target.value)} placeholder="e.g. Customers in the back room cannot connect since 2 pm" /></label>
      <p className="muted">Don't type voucher codes or passwords here. If you do, they are removed from the report.</p>
      <button className="button" disabled={busy || !site}>Create help report</button>
    </form>
    {notice && <p className="notice" role="status">{notice}</p>}
    {current && <ReportView item={current} busy={busy} onShare={share} />}
    {items.length > 1 && <div className="tablewrap"><table>
      <thead><tr><th>Created</th><th>Likely cause</th><th>Support</th><th></th></tr></thead>
      <tbody>{items.map(item => <tr key={item.id} aria-current={item.id === open ? 'true' : undefined}>
        <td>{shopTime(item.created, item.report.shop.timezone)}</td>
        <td className="support-cause">{firstSentence(item.report.likely_causes[0]?.text)}</td>
        <td>{item.shared_at ? 'Shared' : 'Not shared'}</td>
        <td><button type="button" className="button secondary" onClick={() => setOpen(item.id)}>View</button></td>
      </tr>)}</tbody>
    </table></div>}
  </section>;
}

export function SupportInbox({ api }) {
  const [items, setItems] = useState(null);
  const [open, setOpen] = useState(null);
  const [error, setError] = useState('');
  useEffect(() => { api.request('support-reports').then(setItems).catch(e => setError(e.message)); }, []);
  const current = items?.find(item => item.id === open);
  return <section className="panel support-panel">
    <h2>Shared help reports</h2>
    <p className="muted">Reports business owners chose to share. They are read-only and redacted; they give no access to the business or its routers.</p>
    {error && <p className="notice" role="status">{error}</p>}
    {items && !items.length && <p className="muted">No shared reports yet.</p>}
    {items?.length > 0 && <div className="tablewrap"><table>
      <thead><tr><th>Shared</th><th>Business</th><th>Shop</th><th>Likely cause</th><th></th></tr></thead>
      <tbody>{items.map(item => <tr key={item.id} aria-current={item.id === open ? 'true' : undefined}>
        <td>{shopTime(item.shared_at, item.report.shop.timezone)}</td><td>{item.business}</td><td>{item.site_name}</td>
        <td className="support-cause">{firstSentence(item.report.likely_causes[0]?.text)}</td>
        <td><button type="button" className="button secondary" onClick={() => setOpen(item.id)}>View</button></td>
      </tr>)}</tbody>
    </table></div>}
    {current && <ReportView item={current} />}
  </section>;
}
