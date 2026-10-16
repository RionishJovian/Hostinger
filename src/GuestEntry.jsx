import React,{useState} from 'react';
import {getGuestMessage,normalizeGuestLanguage,persistGuestLanguage,readGuestLanguage} from './guest-localization.mjs';

export default function GuestEntry({portal,busy,onRegister,onLogin,language:languageProp,onLanguageChange}){
 const [language,setLanguage]=useState(()=>normalizeGuestLanguage(languageProp||readGuestLanguage()));
 const [signup,setSignup]=useState(true),[username,setUsername]=useState(''),[password,setPassword]=useState(''),[accepted,setAccepted]=useState(false);
 const t=(key)=>getGuestMessage(language,'entry',key);
 const shell=(key)=>getGuestMessage(language,'shell',key);
 function setLang(next){
  const selected=persistGuestLanguage(next);
  setLanguage(selected);
  onLanguageChange?.(selected);
 }
 return <section className="panel">
  <div className="langs" role="group" aria-label={shell('language')}>
   <button type="button" className="button secondary" aria-pressed={language==='my'} disabled={busy} onClick={()=>setLang('my')}>{shell('myanmar')}</button>
   <button type="button" className="button secondary" aria-pressed={language==='en'} disabled={busy} onClick={()=>setLang('en')}>{shell('english')}</button>
  </div>
  <div className="eyebrow">{t('eyebrow')(portal.site_name)}</div>
  <h2>{portal.settings.business_name}</h2>
  <p>{portal.settings.welcome}</p>
  <p>{portal.settings.contact}</p>
  <div className="metrics">{portal.packages.map(p=><div className="metric" key={p.id}><strong>{p.policy.name}</strong><small>{p.policy.price} MMK · {p.policy.service} · {p.policy.mode}</small></div>)}</div>
  <p>{portal.settings.terms||t('defaultTerms')}</p>
  <form onSubmit={async e=>{e.preventDefault();const ok=signup?await onRegister({username,password,accepted_terms:accepted,revision:portal.revision}):await onLogin({username,password});if(ok)setPassword('')}}>
   <label className="field"><span>{t('username')}</span><input required minLength={3} maxLength={160} autoComplete="username" value={username} onChange={e=>setUsername(e.target.value)}/></label>
   <label className="field"><span>{t('password')}</span><input required type="password" minLength={signup?6:1} maxLength={256} autoComplete={signup?'new-password':'current-password'} value={password} onChange={e=>setPassword(e.target.value)}/></label>
   {signup&&<label><input type="checkbox" required checked={accepted} onChange={e=>setAccepted(e.target.checked)}/> {t('acceptTerms')}</label>}
   <div className="buttons">
    <button className="button" disabled={busy}>{signup?t('createAccount'):t('signIn')}</button>
    <button className="button secondary" type="button" disabled={busy} onClick={()=>setSignup(!signup)}>{signup?t('haveAccount'):t('needAccount')}</button>
   </div>
  </form>
  <p className="muted">{t('footer')}</p>
 </section>;
}
