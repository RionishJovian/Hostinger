import React,{createContext,useContext,useMemo,useState} from 'react';
import {chooseSmeLanguage,getSmeMessage,normalizeSmeLanguage,persistSmeLanguage,readStoredSmeLanguage,SME_MESSAGES} from './sme-localization.mjs';
import './sme-localization.css';

const SMELocalizationContext=createContext(null);

export function SMELocalizationProvider({children,languages=['my','en'],defaultLanguage='my'}){
 const [stored,setStored]=useState(readStoredSmeLanguage);
 const language=chooseSmeLanguage(stored,languages,defaultLanguage);
 const setLanguage=value=>{
  if(!languages.includes(value))return;
  setStored(persistSmeLanguage(value));
 };
 const offered=languages.join(',');
 const value=useMemo(()=>({language,languages,setLanguage,t:(section,key)=>getSmeMessage(language,section,key)}),[language,offered]);
 return <SMELocalizationContext.Provider value={value}>{children}</SMELocalizationContext.Provider>;
}

export function useSMELocalization(){
 const context=useContext(SMELocalizationContext);
 if(!context)throw new Error('useSMELocalization must be used inside SMELocalizationProvider');
 return context;
}
/** Page copy for the signed-in language. Without a provider, or when disabled, English is used so shared platform screens stay English. */
export function useSmeCopy(section,enabled=true){
 const context=useContext(SMELocalizationContext);
 const language=enabled&&context?normalizeSmeLanguage(context.language):'en';
 return SME_MESSAGES[language]?.[section]??SME_MESSAGES.en?.[section]??{};
}

const LANGUAGE_LABELS={my:'မြန်မာ',en:'English'};
export function LanguageToggle({className='language-toggle'}){
 const {language,languages,setLanguage,t}=useSMELocalization();
 if(languages.length<2)return null;
 return <div className={className} role="group" aria-label={t('shell','language')}>
  {languages.map(l=><button key={l} type="button" aria-pressed={language===l} onClick={()=>setLanguage(l)}>{LANGUAGE_LABELS[l]}</button>)}
 </div>;
}
