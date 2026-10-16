import React,{useState} from 'react';
import {getGuestMessage,normalizeGuestLanguage,persistGuestLanguage,readGuestLanguage} from './guest-localization.mjs';

const formatBytes=value=>value>=1_000_000_000?(value/1_000_000_000).toFixed(2)+' GB':Math.max(0,value/1_000_000).toFixed(0)+' MB';
const formatTime=value=>value>=3600?(value/3600).toFixed(1)+' h':Math.ceil(value/60)+' min';

export default function GuestAccessStatus({api,diagnosis,sites=[],language:languageProp,onLanguageChange}){
 const [language,setLanguage]=useState(()=>normalizeGuestLanguage(languageProp||readGuestLanguage()));
 const [current,setCurrent]=useState(diagnosis),[busy,setBusy]=useState(false),[error,setError]=useState('');
 const t=(key)=>getGuestMessage(language,'access',key);
 const shell=(key)=>getGuestMessage(language,'shell',key);
 const states=getGuestMessage(language,'access','states')||{};
 function setLang(next){
  const selected=persistGuestLanguage(next);
  setLanguage(selected);
  onLanguageChange?.(selected);
 }
 async function refresh(){setBusy(true);setError('');try{setCurrent(await api.request('my-access/diagnosis'))}catch(e){setError(e.message)}finally{setBusy(false)}}
 const evidence=current?.network_evidence;
 return <section className="panel">
  <div className="langs" role="group" aria-label={shell('language')}>
   <button type="button" className="button secondary" aria-pressed={language==='my'} disabled={busy} onClick={()=>setLang('my')}>{shell('myanmar')}</button>
   <button type="button" className="button secondary" aria-pressed={language==='en'} disabled={busy} onClick={()=>setLang('en')}>{shell('english')}</button>
  </div>
  <div className="panelhead"><h2>{t('title')}</h2><button className="button secondary" type="button" disabled={busy} onClick={refresh}>{busy?t('checking'):t('checkAgain')}</button></div>
  <div className="callout"><b>{evidence?.status==='unavailable'?t('evidenceUnavailable'):t('evidenceAvailable')}</b><p>{evidence?.detail||t('noDiagnosis')}</p><small>{t('freshness')(evidence?.freshness)}</small></div>
  {error&&<p role="alert">{error}</p>}
  {current?.items?.map(item=><article className="pass" key={item.kind+item.id}><h3>{item.name}</h3><p><span className="pill warn">{states[item.state]||item.state}</span></p><small>{sites.find(site=>site.id===item.site_id)?.name||item.site_id||t('businessWide')} · {t('reference')(item.id)}</small><p>{item.detail}</p>{item.voucher_code_hint&&<p>{t('voucherEnding')(item.voucher_code_hint)}</p>}{item.quota?.data&&<p>{t('dataRecord')(formatBytes(item.quota.data.remaining_bytes),formatBytes(item.quota.data.limit_bytes))}</p>}{item.quota?.time&&<p>{t('timeRecord')(formatTime(item.quota.time.remaining_seconds),formatTime(item.quota.time.limit_seconds))}</p>}<p><b>{t('whatYouCanDo')}</b> {item.safe_action}</p>{item.quota&&<small>{t('usageSource')}</small>}</article>)}
  {!current?.items?.length&&<p>{t('empty')}</p>}
 </section>;
}
