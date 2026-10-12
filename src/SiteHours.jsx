import React, { useEffect, useState } from 'react';
import { DAYS, MAINTENANCE_PRESETS, defaultWeek, scheduleSummary, countdown, maintenanceMinutes, hoursBody, hoursProblem } from './site-hours.mjs';
import { toMyanmarDigits } from './sme-format.mjs';
import { useSmeCopy, useSMELocalization } from './SMELocalization.jsx';

function Field({ label, children }) {
  return <label className="field"><span>{label}</span>{children}</label>;
}

function shopTime(ts, timezone, language, withDate = false) {
  const my = language === 'my';
  const text = new Date(ts * 1000).toLocaleString(my ? 'my-MM' : 'en-GB', {
    timeZone: timezone, hour: '2-digit', minute: '2-digit',
    ...(withDate ? { day: 'numeric', month: 'short' } : {})
  });
  return my ? toMyanmarDigits(text) : text;
}

function WeekEditor({ label, week, onChange, disabled, c }) {
  const setDay = (day, value) => onChange({ ...week, [day]: value });
  return <fieldset className="week-hours" disabled={disabled}>
    <legend>{label}</legend>
    <table>
      <thead><tr><th>{c.dayCol}</th><th>{c.dayOpen}</th><th>{c.dayOpens}</th><th>{c.dayCloses}</th></tr></thead>
      <tbody>{DAYS.map(day => {
        const hours = week[day];
        const name = c.days[day];
        return <tr key={day}>
          <td>{name}</td>
          <td><input type="checkbox" aria-label={`${name} ${c.dayOpen}`} checked={!!hours} onChange={event => setDay(day, event.target.checked ? { open: '08:00', close: '22:00' } : null)} /></td>
          <td>{hours ? <input aria-label={`${name} ${c.dayOpens}`} value={hours.open} maxLength={5} inputMode="numeric" placeholder="08:00" onChange={event => setDay(day, { ...hours, open: event.target.value })} /> : <small>{c.dayClosed}</small>}</td>
          <td>{hours && <input aria-label={`${name} ${c.dayCloses}`} value={hours.close} maxLength={5} inputMode="numeric" placeholder="22:00" onChange={event => setDay(day, { ...hours, close: event.target.value })} />}</td>
        </tr>;
      })}</tbody>
    </table>
    <button type="button" className="button secondary" onClick={() => onChange(Object.fromEntries(DAYS.map(day => [day, week.mon ? { ...week.mon } : null])))}>{c.copyMonday}</button>
  </fieldset>;
}

function formFrom(data) {
  return { businessSet: !!data.business_hours, business: data.business_hours || defaultWeek(), mode: data.network_hours_mode, network: data.network_hours || data.business_hours || defaultWeek() };
}

function hourLabels(c) {
  return {
    week: { dayNames: c.days, setSchedule: c.setSchedule, badTimes: c.badTimes, mustDiffer: c.mustDiffer },
    businessPrefix: c.businessPrefix, networkPrefix: c.networkPrefix, needBusinessFirst: c.needBusinessFirst
  };
}

function summaryLabels(c) {
  return { dayNames: c.days, closed: c.closed, notSet: c.notSet, nextDay: c.nextDay };
}

export default function SiteHours({ api, sites, refresh }) {
  const c = useSmeCopy('siteHours');
  const { language } = useSMELocalization();
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
    if (active && now >= active.planned_end + 2) send(`sites/${site}/hours`, undefined, c.timeUp);
  }, [active?.id, active?.planned_end, now >= (active?.planned_end ?? Infinity) + 2, c.timeUp]);

  async function send(path, body, message) {
    setBusy(true);
    try { show(await api.request(path, body)); setNow(Date.now() / 1000); setNotice(message); refresh?.(); return true; }
    catch (error) { setNotice(error.message); return false; }
    finally { setBusy(false); }
  }

  const tz = data?.timezone;
  const problem = form ? hoursProblem(form, hourLabels(c)) : '';
  const minutes = maintenanceMinutes(choice, custom);
  const lastCheck = data?.history.find(item => item.post_check);
  const status = data && {
    business: { open: c.openNow, closed: c.closedNow, not_set: c.businessNotSet }[data.now.business],
    network: data.now.network === 'on' ? c.networkOn : c.networkOff
  };
  const networkLabel = mode => c.modes[mode] || mode;

  return <>
    <section className="panel site-hours">
      <h2>{c.title}</h2>
      <Field label={c.shop}><select value={site} onChange={event => setSite(event.target.value)}>
        <option value="">{c.selectShop}</option>{sites.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}
      </select></Field>
      {data && form && <>
        <p className="hours-now"><span className={'pill ' + (data.now.business === 'open' ? 'good' : 'warn')}>{status.business}</span> <span className={'pill ' + (data.now.network === 'on' ? 'good' : 'warn')}>{status.network}</span> <small>{c.shopTime(shopTime(data.now.at, tz, language), tz)}</small></p>
        <form onSubmit={event => { event.preventDefault(); send(`sites/${site}/hours`, hoursBody(form), c.hoursSaved); }}>
          <label className="check"><input type="checkbox" checked={form.businessSet} onChange={event => setForm({ ...form, businessSet: event.target.checked })} /> {c.hasBusiness}</label>
          {form.businessSet ? <WeekEditor label={c.businessHours} week={form.business} onChange={business => setForm({ ...form, business })} c={c} /> : <p className="muted">{c.businessNotSet}</p>}
          <fieldset className="network-mode">
            <legend>{c.networkHours}</legend>
            {Object.keys(c.modes).map(mode => <label className="check" key={mode}><input type="radio" name="network-mode" value={mode} checked={form.mode === mode} onChange={() => setForm({ ...form, mode })} /> {c.modes[mode]}</label>)}
          </fieldset>
          {form.mode === 'custom' && <WeekEditor label={c.networkHours} week={form.network} onChange={network => setForm({ ...form, network })} c={c} />}
          {problem && <p className="muted" role="status">{problem}</p>}
          <button className="button" disabled={busy || !!problem}>{c.save}</button>
        </form>
        <p className="muted">{c.saved(scheduleSummary(data.business_hours, summaryLabels(c)), data.network_hours_mode === 'custom' ? scheduleSummary(data.network_hours, summaryLabels(c)) : networkLabel(data.network_hours_mode))}</p>
      </>}
      {notice && <p className="notice" role="status">{notice}</p>}
    </section>
    {data && <section className="panel site-maintenance">
      <h2>{c.maintenanceTitle}</h2>
      {active ? <div className="maintenance-active" role="status">
        <p><span className="pill warn">{c.running}</span> <strong className="maintenance-countdown">{language === 'my' ? toMyanmarDigits(countdown(active.planned_end - now)) : countdown(active.planned_end - now)}</strong> {c.left} {shopTime(active.planned_end, tz, language)}{active.extensions ? c.extended(active.extensions) : ''}</p>
        {active.reason && <p>{c.reasonLabel} {active.reason}</p>}
        <div className="actions">
          <button className="button secondary" disabled={busy} onClick={() => send(`sites/${site}/maintenance/${active.id}/extend`, { minutes: 15 }, c.extended15)}>{c.extend15}</button>
          <button className="button secondary" disabled={busy} onClick={() => send(`sites/${site}/maintenance/${active.id}/extend`, { minutes: 30 }, c.extended30)}>{c.extend30}</button>
          <button className="button" disabled={busy} onClick={() => send(`sites/${site}/maintenance/${active.id}/end`, {}, c.ended)}>{c.endNow}</button>
        </div>
      </div> : <form onSubmit={async event => { event.preventDefault(); if (await send(`sites/${site}/maintenance`, { minutes, reason }, c.started)) setReason(''); }}>
        <div className="formgrid">
          <Field label={c.howLong}><select value={choice} onChange={event => setChoice(event.target.value)}>
            {MAINTENANCE_PRESETS.map(n => <option key={n} value={n}>{c.minutesLabel(n)}</option>)}
            <option value="custom">{c.custom}</option>
          </select></Field>
          {choice === 'custom' && <Field label={c.minutes}><input inputMode="numeric" value={custom} onChange={event => setCustom(event.target.value)} placeholder="90" /></Field>}
          <Field label={c.reasonOptional}><input maxLength={300} value={reason} onChange={event => setReason(event.target.value)} placeholder={c.reasonHint} /></Field>
        </div>
        {choice === 'custom' && !minutes && <p className="muted" role="status">{c.customHint}</p>}
        <button className="button" disabled={busy || !minutes}>{c.start}</button>
      </form>}
      <p className="muted">{c.maintenanceNote}</p>
      {lastCheck && <div className="callout"><b>{c.magicCheck}</b> ({shopTime(lastCheck.post_check.checked, tz, language, true)}): {lastCheck.post_check.summary}{lastCheck.post_check.open_incidents ? c.stillOpen(lastCheck.post_check.open_incidents) : ''}</div>}
      {data.history.length > 0 && <div className="tablewrap"><table>
        <thead><tr>{c.historyHeads.map(h => <th key={h}>{h}</th>)}</tr></thead>
        <tbody>{data.history.map(item => <tr key={item.id}>
          <td>{shopTime(item.started, tz, language, true)}</td>
          <td>{item.ended ? shopTime(item.ended, tz, language, true) : c.runningUntil(shopTime(item.planned_end, tz, language))}</td>
          <td>{item.reason || <small>{c.none}</small>}</td>
          <td>{item.extensions ? `${item.extensions}×` : c.dash}</td>
          <td>{item.post_check ? (item.post_check.result === 'unable' ? c.couldNotCheck : item.post_check.result) : c.dash}</td>
        </tr>)}</tbody>
      </table></div>}
    </section>}
  </>;
}
