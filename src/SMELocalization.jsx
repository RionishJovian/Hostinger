import React,{createContext,useContext,useMemo,useState} from 'react';
import {getSmeMessage,persistSmeLanguage,readSmeLanguage} from './sme-localization.mjs';
import './sme-localization.css';

const SMELocalizationContext=createContext(null);

export function SMELocalizationProvider({children}){
 const [language,setLanguageState]=useState(readSmeLanguage);
 const setLanguage=value=>{
  const selected=persistSmeLanguage(value);
  setLanguageState(selected);
 };
 const value=useMemo(()=>({language,setLanguage,t:(section,key)=>getSmeMessage(language,section,key)}),[language]);
 return <SMELocalizationContext.Provider value={value}>{children}</SMELocalizationContext.Provider>;
}

export function useSMELocalization(){
 const context=useContext(SMELocalizationContext);
 if(!context)throw new Error('useSMELocalization must be used inside SMELocalizationProvider');
 return context;
}

export function LanguageToggle({className='language-toggle'}){
 const {language,setLanguage,t}=useSMELocalization();
 return <div className={className} role="group" aria-label={t('shell','language')}>
  <button type="button" aria-pressed={language==='my'} onClick={()=>setLanguage('my')}>မြန်မာ</button>
  <button type="button" aria-pressed={language==='en'} onClick={()=>setLanguage('en')}>English</button>
 </div>;
}
