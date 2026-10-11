const NOW_BUSINESS={open:'Open now',closed:'Closed now',not_set:'Business hours not set'};
const CONNECTION={verified_handshake:'Magic Hub handshake verified (transport only, not full management)',not_verified:'No verified connection to MikroMagic'};

export function shopTime(ts,timezone){
 if(!ts)return '—';
 return new Date(ts*1000).toLocaleString('en-GB',{timeZone:timezone||'UTC',day:'numeric',month:'short',year:'numeric',hour:'2-digit',minute:'2-digit'});
}
const SCOPES={control_plane:'MikroMagic cloud',gateway:'Gateway',wan:'Internet (WAN)',switch:'Switch',access_point:'Access point',dns_portal:'DNS / portal',dependency:'Dependency'};
const words=value=>String(value||'').replace(/_/g,' ');
const sentence=value=>value?(/[.!?]$/.test(value)?value:value+'.'):'';

export function reportText(report){
 const tz=report.shop?.timezone,at=ts=>shopTime(ts,tz),lines=[];
 lines.push('MikroMagic help report',`Business: ${report.business||'—'}`,`Shop: ${report.shop?.name||'—'} (${tz})`,`Created: ${at(report.generated)}`,'');
 lines.push('What the owner says:',report.description||'(nothing written)','');
 lines.push('Likely causes (from MikroMagic records only):');
 for(const c of report.likely_causes||[])lines.push(`- ${c.text} [based on: ${c.evidence}]`);
 lines.push('','Right now:',`- ${NOW_BUSINESS[report.now?.business]||'—'}; network planned ${report.now?.network==='off'?'off':'on'}`);
 if(report.now?.maintenance_until)lines.push(`- Planned maintenance until ${at(report.now.maintenance_until)}${report.now.maintenance_reason?` (${report.now.maintenance_reason})`:''}`);
 lines.push('','Routers (owner-reported details):');
 if(!report.routers?.length)lines.push('- None registered');
 for(const r of report.routers||[])lines.push(`- ${r.name}: ${r.model}${r.reported_routeros?`, RouterOS ${r.reported_routeros}`:''}; ${CONNECTION[r.connection]||words(r.connection)}${r.magic_hub_assigned?'; Magic Hub assigned':''}${r.management_locked?'; remote management locked':''}`);
 lines.push('','Switches and access points (owner-reported):');
 if(!report.devices?.length)lines.push('- None recorded');
 for(const d of report.devices||[])lines.push(`- ${d.name} (${words(d.kind)}): ${[d.vendor,d.model].filter(Boolean).join(' ')}${d.location?`, ${d.location}`:''}; last seen ${d.last_seen?at(d.last_seen):'never reported'}`);
 lines.push('',`Outages (open, and closed in the last 7 days):`);
 if(!report.outages?.length)lines.push('- None recorded');
 for(const o of report.outages||[])lines.push(`- ${SCOPES[o.scope]||words(o.scope)}: ${o.ongoing?`ongoing for ${o.duration}`:`lasted ${o.duration}`}, started ${at(o.started)}${o.expected?` (expected: ${words(o.expected)})`:''}. ${sentence(o.symptoms)}${o.confirmed_cause?` Confirmed cause: ${o.confirmed_cause}.`:o.suspected_cause?` Suspected (not confirmed): ${o.suspected_cause}.`:''}`.trim());
 lines.push('','Recent recorded actions:');
 if(!report.recent_events?.length)lines.push('- None');
 for(const e of report.recent_events||[])lines.push(`- ${at(e.at)} ${words(e.action)}`);
 lines.push('',report.excluded||'');
 return lines.join('\n');
}

export function firstSentence(text){
 const value=String(text||''),cut=value.search(/[,.;](\s|$)/);
 return cut>0?value.slice(0,cut)+(value[cut]==='.'?'.':'…'):value;
}

export function reportFileName(report){
 const shop=String(report.shop?.name||'shop').toLowerCase().replace(/[^a-z0-9]+/g,'-').replace(/^-|-$/g,'')||'shop';
 return `mikromagic-help-${shop}-${new Date(report.generated*1000).toISOString().slice(0,16).replace(/[-:T]/g,'')}.txt`;
}
