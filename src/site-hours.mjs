export const DAYS=['mon','tue','wed','thu','fri','sat','sun'];
export const DAY_NAMES={mon:'Mon',tue:'Tue',wed:'Wed',thu:'Thu',fri:'Fri',sat:'Sat',sun:'Sun'};
export const NETWORK_MODES={always:'24×7 (always on)',business:'Same as business hours',custom:'Custom'};
export const MAINTENANCE_PRESETS=[15,30,60];
const OPEN=/^([01]\d|2[0-3]):[0-5]\d$/,CLOSE=/^(([01]\d|2[0-3]):[0-5]\d|24:00)$/;

export function defaultWeek(open='08:00',close='22:00'){return Object.fromEntries(DAYS.map(d=>[d,{open,close}]))}

export function weekProblem(week){
 if(!week)return 'Set a weekly schedule.';
 for(const d of DAYS){
  const day=week[d];if(day===null)continue;
  if(!day||!OPEN.test(day.open||'')||!CLOSE.test(day.close||''))return `${DAY_NAMES[d]}: use 24-hour times such as 08:00 and 22:00 (closing may be 24:00).`;
  if(day.open===day.close)return `${DAY_NAMES[d]}: opening and closing times must differ. For all day use 00:00 to 24:00.`;
 }
 return '';
}

export function scheduleSummary(week){
 if(!week)return 'Not set';
 const label=d=>week[d]?`${week[d].open}–${week[d].close}${week[d].close<week[d].open?' (next day)':''}`:'Closed';
 const groups=[];
 for(const d of DAYS){const text=label(d),last=groups.at(-1);if(last&&last.text===text)last.to=d;else groups.push({from:d,to:d,text})}
 return groups.map(g=>`${DAY_NAMES[g.from]}${g.to!==g.from?'–'+DAY_NAMES[g.to]:''} ${g.text}`).join(' · ');
}

export function countdown(seconds){
 const s=Math.max(0,Math.floor(seconds)),h=Math.floor(s/3600),m=Math.floor(s%3600/60),r=s%60,pad=n=>String(n).padStart(2,'0');
 return h?`${h}h ${pad(m)}m ${pad(r)}s`:`${m}m ${pad(r)}s`;
}

export function maintenanceMinutes(choice,custom){
 const n=choice==='custom'?Number(custom):Number(choice);
 return Number.isInteger(n)&&n>=5&&n<=1440?n:null;
}

export function hoursBody(form){
 return {business_hours:form.businessSet?form.business:null,network_hours_mode:form.mode,network_hours:form.mode==='custom'?form.network:null};
}

export function hoursProblem(form){
 if(form.businessSet){const p=weekProblem(form.business);if(p)return 'Business hours · '+p}
 if(form.mode==='business'&&!form.businessSet)return 'Set business hours first, or choose 24×7 or Custom network hours.';
 if(form.mode==='custom'){const p=weekProblem(form.network);if(p)return 'Network hours · '+p}
 return '';
}
