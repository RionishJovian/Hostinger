/** Locale-aware MMK, date/time and Myanmar phone display for the SME workspace. */
import {normalizeSmeLanguage} from './sme-localization.mjs';

export function smeIntlLocale(language){
 return normalizeSmeLanguage(language)==='my'?'my-MM':'en';
}

/** MMK amounts: Burmese digits + ကျပ် symbol via ICU when my; plain MMK when English. */
export function formatMmk(amount,language='en'){
 const value=Number(amount)||0;
 return new Intl.NumberFormat(smeIntlLocale(language),{style:'currency',currency:'MMK',maximumFractionDigits:0}).format(value);
}

/** Unix seconds → readable local date/time in the SME language. */
export function formatSmeDateTime(seconds,language='en',options={}){
 if(seconds==null||seconds==='')return '';
 const date=seconds instanceof Date?seconds:new Date(Number(seconds)*1000);
 if(Number.isNaN(date.getTime()))return '';
 const locale=smeIntlLocale(language);
 const defaults={dateStyle:'medium',timeStyle:'short',...options};
 try{return new Intl.DateTimeFormat(locale,defaults).format(date)}catch{return date.toLocaleString(locale)}
}

/**
 * Soft-format Myanmar mobile numbers for display (does not validate).
 * Accepts 09…, +959…, 959… and spaces/hyphens; returns a spaced local form when recognized.
 */
export function formatSmePhone(value,language='en'){
 const raw=String(value??'').trim();
 if(!raw)return '';
 const digits=raw.replace(/[^\d+]/g,'');
 let national='';
 if(digits.startsWith('+959'))national='09'+digits.slice(4);
 else if(digits.startsWith('959')&&digits.length>=11)national='09'+digits.slice(3);
 else if(digits.startsWith('09'))national=digits;
 else return raw;
 const body=national.slice(2);
 if(body.length<7||body.length>9)return raw;
 const grouped=body.length===9?`${body.slice(0,3)} ${body.slice(3,6)} ${body.slice(6)}`
  :body.length===8?`${body.slice(0,3)} ${body.slice(3,6)} ${body.slice(6)}`
  :`${body.slice(0,3)} ${body.slice(3)}`;
 const local=`09 ${grouped}`;
 return normalizeSmeLanguage(language)==='my'?local:local;
}
