import React, { useEffect, useState } from 'react';
import { DAYS, DAY_NAMES, NETWORK_MODES, MAINTENANCE_PRESETS, defaultWeek, scheduleSummary, countdown, maintenanceMinutes, hoursBody, hoursProblem } from './site-hours.mjs';

function Field({ label, children }) {
  return <label className="field"><span>{label}</span>{children}</label>;
}

function shopTime(ts, timezone, withDate = false) {
  return new Date(ts * 1000).toLocaleString('en-GB', { timeZone: timezone, hour: '2-digit', minute: '2-digit', ...(withDate ? { day: 'numeric', month: 'short' } : {}) });
}

function WeekEditor({ label, week, onChange, disabled }) {
  const setDay = (day, value) => onChange({ ...week, [day]: value });
  return <fieldset className="week-hours" disabled={disabled}>
    <legend>{label}</legend>
    <table>
      <thead><tr><th>Day</th><th>Open</th><th>Opens</th><th>Closes</th></tr></thead>
      <tbody>{DAYS.map(day => {
        const hours = week[day];
        return <tr key={day}>
          <td>{DAY_NAMES[day]}</td>
          <td><input type="checkbox" aria-label={`${DAY_NAMES[day]} open`} checked={!!hours} onChange={event => setDay(day, event.target.checked ? { open: '08:00', close: '22:00' } : null)} /></td>
          <td>{hours ? <input aria-label={`${DAY_NAMES[day]} opens`} value={hours.open} maxLength={5} inputMode="numeric" placeholder="08:00" onChange={event => setDay(day, { ...hours, open: event.target.value })} /> : <small>Closed</small>}</td>
          <td>{hours && <input aria-label={`${DAY_NAMES[day]} closes`} value={hours.close} maxLength={5} inputMode="numeric" placeholder="22:00" onChange={event => setDay(day, { ...hours, close: event.target.value })} />}</td>
        </tr>;
      })}</tbody>
    </table>
    <button type="button" className="button secondary" onClick={() => onChange(Object.fromEntries(DAYS.map(day => [day, week.mon ? { ...week.mon } : null])))}>Copy Monday to every day</button>
  </fieldset>;
}

function formFrom(data) {
  return { businessSet: !!data.business_hours, business: data.business_hours || defaultWeek(), mode: data.network_hours_mode, network: data.network_hours || data.business_hours || defaultWeek() };
}

export default function SiteHours({ api, sites, refresh }) {
  const [site, setSite] = useState('');
  const [data, setData] = useState(null);
  const [form, setForm] = useState(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState('');
  const [choice, setChoice] = useState('30');
  const [custom, setCustom] = useState('');
  const [reason, setReason] = useState('');
  const [now, setNow] = useState(() => Date.now() / 1000);

  function show(result) { setData(result); setForm(formFrom(result)); }
  useEffect(() => {
    let live = true;
    setData(null); setForm(null); setNotice('');
    if (site) api.request(`sites/${site}/hours`).then(result => live && show(result)).catch(error => live && setNotice(error.message));
    return () => { live = false; };
  }, [site]);

  const active = data?.maintenance;
  useEffect(() => {
    if (!active) return undefined;
    const timer = setInterval(() => setNow(Date.now() / 1000), 1000);
    return () => clearInterval(timer);
  }, [active?.id]);
  useEffect(() => {
    if (active && now >= active.planned_end + 2) send(`sites/${site}/hours`, undefined, 'Maintenance time is up. The Magic Check result is below.');
  }, [active?.id, active?.planned_end, now >= (active?.planned_end ?? Infinity) + 2]);

  async function send(path, body, message) {
    setBusy(true);
    try { show(await api.request(path, body)); setNow(Date.now() / 1000); setNotice(message); refresh?.(); return true; }
    catch (error) { setNotice(error.message); return false; }
    finally { setBusy(false); }
  }

  const tz = data?.timezone;
  const problem = form ? hoursProblem(form) : '';
  const minutes = maintenanceMinutes(choice, custom);
  const lastCheck = data?.history.find(item => item.post_check);
  const status = data && { business: { open: 'Open now', closed: 'Closed now', not_set: 'Business hours not set' }[data.now.business], network: data.now.network === 'on' ? 'Network planned on' : 'Network planned off' };

  return <>
    <section className="panel site-hours">
      <h2>Opening hours</h2>
      <Field label="Shop"><select value={site} onChange={event => setSite(event.target.value)}>
        <option value="">Select a shop</option>{sites.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}
      </select></Field>
      {data && form && <>
        <p className="hours-now"><span className={'pill ' + (data.now.business === 'open' ? 'good' : 'warn')}>{status.business}</span> <span className={'pill ' + (data.now.network === 'on' ? 'good' : 'warn')}>{status.network}</span> <small>Shop time {shopTime(data.now.at, tz)} ({tz})</small></p>
        <form onSubmit={event => { event.preventDefault(); send(`sites/${site}/hours`, hoursBody(form), 'Hours saved. Nothing on your router or Wi-Fi was changed.'); }}>
          <label className="check"><input type="checkbox" checked={form.businessSet} onChange={event => setForm({ ...form, businessSet: event.target.checked })} /> This shop has business hours</label>
          {form.businessSet ? <WeekEditor label="Business hours" week={form.business} onChange={business => setForm({ ...form, business })} /> : <p className="muted">Business hours not set.</p>}
          <fieldset className="network-mode">
            <legend>Network operating hours</legend>
            {Object.entries(NETWORK_MODES).map(([mode, label]) => <label className="check" key={mode}><input type="radio" name="network-mode" value={mode} checked={form.mode === mode} onChange={() => setForm({ ...form, mode })} /> {label}</label>)}
          </fieldset>
          {form.mode === 'custom' && <WeekEditor label="Network operating hours" week={form.network} onChange={network => setForm({ ...form, network })} />}
          {problem && <p className="muted" role="status">{problem}</p>}
          <button className="button" disabled={busy || !!problem}>Save hours</button>
        </form>
        <p className="muted">Saved: business {scheduleSummary(data.business_hours)} · network {data.network_hours_mode === 'custom' ? scheduleSummary(data.network_hours) : NETWORK_MODES[data.network_hours_mode]}. Times use the shop timezone; a closing time earlier than the opening time runs past midnight. Outages that start while the network is planned off are recorded as expected. These hours do not switch your router or Wi-Fi on or off.</p>
      </>}
      {notice && <p className="notice" role="status">{notice}</p>}
    </section>
    {data && <section className="panel site-maintenance">
      <h2>Planned maintenance</h2>
      {active ? <div className="maintenance-active" role="status">
        <p><span className="pill warn">Maintenance running</span> <strong className="maintenance-countdown">{countdown(active.planned_end - now)}</strong> left · ends {shopTime(active.planned_end, tz)}{active.extensions ? ` · extended ${active.extensions}×` : ''}</p>
        {active.reason && <p>Reason: {active.reason}</p>}
        <div className="actions">
          <button className="button secondary" disabled={busy} onClick={() => send(`sites/${site}/maintenance/${active.id}/extend`, { minutes: 15 }, 'Maintenance extended by 15 minutes.')}>Extend 15 min</button>
          <button className="button secondary" disabled={busy} onClick={() => send(`sites/${site}/maintenance/${active.id}/extend`, { minutes: 30 }, 'Maintenance extended by 30 minutes.')}>Extend 30 min</button>
          <button className="button" disabled={busy} onClick={() => send(`sites/${site}/maintenance/${active.id}/end`, {}, 'Maintenance ended. The Magic Check result is below.')}>End maintenance now</button>
        </div>
      </div> : <form onSubmit={async event => { event.preventDefault(); if (await send(`sites/${site}/maintenance`, { minutes, reason }, 'Maintenance started.')) setReason(''); }}>
        <div className="formgrid">
          <Field label="How long"><select value={choice} onChange={event => setChoice(event.target.value)}>
            {MAINTENANCE_PRESETS.map(n => <option key={n} value={n}>{n < 60 ? `${n} minutes` : `${n / 60} hour`}</option>)}
            <option value="custom">Custom</option>
          </select></Field>
          {choice === 'custom' && <Field label="Minutes (5–1440)"><input inputMode="numeric" value={custom} onChange={event => setCustom(event.target.value)} placeholder="90" /></Field>}
          <Field label="Reason (optional)"><input maxLength={300} value={reason} onChange={event => setReason(event.target.value)} placeholder="e.g. Moving the access point" /></Field>
        </div>
        {choice === 'custom' && !minutes && <p className="muted" role="status">Enter whole minutes from 5 to 1440 (24 hours).</p>}
        <button className="button" disabled={busy || !minutes}>Start maintenance</button>
      </form>}
      <p className="muted">During maintenance, outages at this shop are recorded as expected instead of as problems, and monitoring continues. When it ends, MikroMagic runs a Magic Check. Starting maintenance does not change anything on your router.</p>
      {lastCheck && <div className="callout"><b>Magic Check after maintenance</b> ({shopTime(lastCheck.post_check.checked, tz, true)}): {lastCheck.post_check.summary}{lastCheck.post_check.open_incidents ? ` ${lastCheck.post_check.open_incidents} incident${lastCheck.post_check.open_incidents === 1 ? ' is' : 's are'} still open.` : ''}</div>}
      {data.history.length > 0 && <div className="tablewrap"><table>
        <thead><tr><th>Started</th><th>Ended</th><th>Reason</th><th>Extended</th><th>Magic Check</th></tr></thead>
        <tbody>{data.history.map(item => <tr key={item.id}>
          <td>{shopTime(item.started, tz, true)}</td>
          <td>{item.ended ? shopTime(item.ended, tz, true) : `Running until ${shopTime(item.planned_end, tz)}`}</td>
          <td>{item.reason || <small>None</small>}</td>
          <td>{item.extensions ? `${item.extensions}×` : '—'}</td>
          <td>{item.post_check ? (item.post_check.result === 'unable' ? 'Could not check' : item.post_check.result) : '—'}</td>
        </tr>)}</tbody>
      </table></div>}
    </section>}
  </>;
}
