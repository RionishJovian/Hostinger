export const PRODUCTION_STEPS=['Profile','Quantity','Coverage','Dealer','Print layout','Preview','Generate','Print','Verify','Distribute'];
export const LAYOUTS={
 a4_ultra:{label:'A4 Ultra Economy · 60 per sheet',grid:[5,12]},
 a4_economy:{label:'A4 Economy · 40 per sheet',grid:[4,10]},
 a4_standard:{label:'A4 Standard · 24 per sheet',grid:[3,8]},
 a4_premium:{label:'A4 Premium · 10 per sheet',grid:[2,5]},
 a4_custom:{label:'A4 custom density'},
 thermal_58:{label:'Thermal 58 mm roll',thermal:58},
 thermal_80:{label:'Thermal 80 mm roll',thermal:80},
};
export const THERMAL_RUN=25;
export const MAGIC_TEMPLATES=[
 {id:'cafe',name:'Cafe / Restaurant',hint:'Short passes sold at the counter',settings:{quantity:40,layout:'a4_economy',expires_days:30}},
 {id:'hotel',name:'Hotel / Guesthouse',hint:'Passes handed out at check-in',settings:{quantity:10,layout:'a4_premium',expires_days:90}},
 {id:'neighborhood',name:'Neighborhood Wi-Fi',hint:'Large reseller runs, about 60 per A4',settings:{quantity:60,layout:'a4_ultra',expires_days:60}},
 {id:'gaming',name:'Gaming / Internet shop',hint:'Thermal tickets printed at the desk',settings:{quantity:25,layout:'thermal_80',expires_days:30}},
 {id:'custom',name:'Custom',hint:'Start from blank settings',settings:{}},
];
export function plan({layout,columns,rows},quantity){
 const spec=LAYOUTS[layout];if(!spec||!(quantity>0))return null;
 const [c,r]=layout==='a4_custom'?[Number(columns)||0,Number(rows)||0]:spec.grid||[0,0];
 const per=spec.thermal?THERMAL_RUN:c*r;if(!per)return null;
 const sheets=Math.ceil(quantity/per);
 return {unit:spec.thermal?'run':'sheet',per_sheet:per,sheets,last_sheet_count:quantity-(sheets-1)*per};
}
export function paperSummary(p){
 if(!p)return 'Choose a layout and quantity to preview paper use.';
 if(p.unit==='run')return `${p.sheets} thermal run${p.sheets===1?'':'s'} of up to ${p.per_sheet} tickets · last run ${p.last_sheet_count}/${p.per_sheet}`;
 return `${p.sheets} A4 sheet${p.sheets===1?'':'s'} · ${p.per_sheet} per sheet · last sheet ${p.last_sheet_count}/${p.per_sheet} used`;
}
export const serial=n=>n==null?'—':String(n).padStart(6,'0');
export function nextStep(job){
 if(!job)return 'Print layout';
 return ({draft:'Generate',generated:'Verify',verified:'Distribute',distributed:'Distribute',cancelled:'Profile'})[job.status]||'Profile';
}
const PREFS_KEY='mikromagic.voucherPrintPrefs';
const PREF_FIELDS=['layout','columns','rows','show_price','ssid'];
export function loadPrintPrefs(storage=globalThis.localStorage){
 try{const saved=JSON.parse(storage?.getItem(PREFS_KEY)||'{}');return Object.fromEntries(PREF_FIELDS.filter(k=>k in saved).map(k=>[k,saved[k]]))}catch{return {}}
}
export function savePrintPrefs(form,storage=globalThis.localStorage){
 try{storage?.setItem(PREFS_KEY,JSON.stringify(Object.fromEntries(PREF_FIELDS.map(k=>[k,form[k]]))))}catch{}
}
const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function density(p){return p.unit==='run'?'thermal':p.per_sheet>=50?'ultra':p.per_sheet>=30?'economy':p.per_sheet>=15?'standard':'premium'}
function card(v,{business,siteName,settings,level}){
 const deadline=new Date(v.expires*1000).toISOString().slice(0,10);
 const price=settings.show_price&&v.policy?.price?`<span>${esc(v.policy.price)} MMK</span>`:'';
 const ssid=settings.ssid?`<span>Wi-Fi: ${esc(settings.ssid)}</span>`:'';
 if(level==='ultra')return `<article class="card ultra"><strong>${esc(v.code)}</strong><small>${esc(v.policy?.name)} · SN ${serial(v.serial_no)}</small></article>`;
 const extra=level==='premium'||level==='thermal'?`<p class="how">Connect to ${settings.ssid?esc(settings.ssid):'the Wi-Fi'}, open your browser and enter this code.</p><small>${esc(siteName)}</small>`:'';
 return `<article class="card ${level}"><h2>${esc(business)}</h2><small>${esc(v.policy?.name)}</small><strong>${esc(v.code)}</strong><div class="meta">${ssid}${price}<span>Use by ${deadline}</span></div>${extra}<small class="sn">SN ${serial(v.serial_no)}</small></article>`;
}
const STYLE=`*{box-sizing:border-box}body{font:11px system-ui;color:#111;background:#fff;margin:0}
.screen{padding:12px;background:#f3f1ea;border-bottom:1px solid #ccc}.screen p{margin:4px 0}
.page{width:194mm;height:281mm;margin:8mm auto;display:grid;grid-template-rows:6mm 1fr;page-break-after:always;break-after:page}
.label{font-size:8px;display:flex;justify-content:space-between;align-items:center;border-bottom:.2mm solid #999}
.grid{display:grid;height:100%}
.card{border:.2mm dashed #777;padding:1.5mm;overflow:hidden;display:flex;flex-direction:column;justify-content:center;gap:.6mm}
.card h2{margin:0;font-size:11px}.card strong{font:700 13px ui-monospace,monospace;letter-spacing:.04em;overflow-wrap:anywhere}
.card small{font-size:8px}.card .meta{display:flex;flex-wrap:wrap;gap:0 2mm;font-size:8px}.card .how{margin:0;font-size:8px}
.card.ultra{padding:.8mm;gap:0}.card.ultra strong{font-size:10px}.card.ultra small{font-size:6.5px}
.card.premium strong{font-size:18px}.card.premium h2{font-size:14px}
.run{margin:0 auto;padding:2mm 0;page-break-after:always;break-after:page}
.ticket{border:0;border-bottom:.3mm dashed #000;padding:3mm 1mm}.ticket strong{font-size:16px}
.runlabel{font-size:9px;text-align:center;border-bottom:.3mm solid #000;padding-bottom:1mm}
@media print{.screen{display:none}.page{margin:0}@page{size:A4;margin:8mm}}`;
function htmlDocument(title,body,screenNote,thermal){
 const page=thermal?`@media print{@page{size:${thermal}mm auto;margin:0}}.run{width:${thermal-8}mm}`:'';
 return `<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>${esc(title)}</title><style>${STYLE}${page}</style><body><div class="screen">${screenNote}</div>${body}</body></html>`;
}
export function productionSheets({job,items,business,siteName='Business-wide',only=null,reprint=false,dealerCode=''}){
 const mark=dealerCode?` · Dealer ${esc(dealerCode)}`:'';
 const p=job.plan,level=density(p),settings=job.settings,thermal=LAYOUTS[settings.layout]?.thermal;
 const [c,r]=settings.layout==='a4_custom'?[settings.columns,settings.rows]:LAYOUTS[settings.layout]?.grid||[1,1];
 const bySheet=new Map();for(const v of items.filter(x=>x.code))bySheet.set(v.sheet_no,[...(bySheet.get(v.sheet_no)||[]),v]);
 const numbers=[...bySheet.keys()].sort((a,b)=>a-b).filter(n=>!only||only.includes(n));
 const pages=numbers.map(n=>{
  const list=bySheet.get(n).sort((a,b)=>a.serial_no-b.serial_no),range=`${serial(list[0].serial_no)}–${serial(list.at(-1).serial_no)}`;
  const copy=(reprint?` · REPRINT ${esc(job.sheets?.[n]?.reprints||'')}`:'')+mark;
  if(thermal)return `<section class="run"><div class="runlabel">Print run ${esc(job.ref)}-R${n} · ${n}/${p.sheets} · Seq ${range}${copy}</div>${list.map(v=>card(v,{business,siteName,settings,level}).replace('class="card thermal"','class="card thermal ticket"')).join('')}<div class="runlabel">End of run ${esc(job.ref)}-R${n}</div></section>`;
  return `<section class="page"><div class="label"><span>Batch ${esc(job.ref)} · Sheet ${n}/${p.sheets} · Serial ${range}${copy}</span><span>${esc(business)}</span></div><div class="grid" style="grid-template-columns:repeat(${c},1fr);grid-template-rows:repeat(${r},1fr)">${list.map(v=>card(v,{business,siteName,settings,level})).join('')}</div></section>`;
 }).join('');
 const note=`<p><strong>Private voucher ${thermal?'runs':'sheets'} · ${esc(job.ref)}</strong></p><p>Contains redeemable codes. Keep private. Print with your browser at 100% scale (no “fit to page”).</p><p>After printing, return to MikroMagic and mark each ${thermal?'run':'sheet'} as printed or failed. Opening the print dialog does not prove printing worked.</p>${reprint?'<p><strong>Reprint:</strong> destroy the failed copies first; this prints the same codes again.</p>':''}<p>QR codes are off: no verified guest portal address exists yet.</p>`;
 return htmlDocument(`${job.ref} voucher ${thermal?'runs':'sheets'}`,pages,note,thermal);
}
export function calibrationSheet({settings,business}){
 const p=plan(settings,1)||{per_sheet:1,unit:'sheet'},level=density(p),thermal=LAYOUTS[settings.layout]?.thermal;
 const [c,r]=settings.layout==='a4_custom'?[settings.columns,settings.rows]:LAYOUTS[settings.layout]?.grid||[1,1];
 const count=thermal?3:p.per_sheet;
 const sample=Array.from({length:count},(_,i)=>({code:'NOT·A·CODE',serial_no:i+1,expires:0,policy:{name:'SAMPLE · not a voucher',price:0}}));
 const cards=sample.map(v=>card(v,{business,siteName:'Calibration',settings:{...settings,show_price:false},level})).join('');
 const ruler=`<div style="width:${thermal?40:100}mm;border-top:.4mm solid #000;margin:2mm auto;text-align:center;font-size:8px">This line should measure ${thermal?40:100} mm</div>`;
 const body=thermal?`<section class="run"><div class="runlabel">PRINT TEST &amp; CALIBRATION · not vouchers</div>${ruler}${cards}</section>`:`<section class="page"><div class="label"><span>PRINT TEST &amp; CALIBRATION · not vouchers</span><span>${esc(business)}</span></div><div class="grid" style="grid-template-columns:repeat(${c},1fr);grid-template-rows:repeat(${r},1fr)">${cards}</div></section>${ruler}`;
 return htmlDocument('Print test & calibration',body,'<p><strong>Print test &amp; calibration</strong> — sample cards only; none of these codes work.</p><p>Print at 100% scale. Check that the ruler measures correctly, every card fits inside its cut guides, and text is readable. Then confirm in MikroMagic.</p>',thermal);
}
