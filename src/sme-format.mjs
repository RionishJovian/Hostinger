/** Locale-aware MMK, date/time and Myanmar phone display for the SME workspace. */
import {normalizeSmeLanguage} from './sme-localization.mjs';

const MYANMAR_DIGITS='၀၁၂၃၄၅၆၇၈၉';
/** Map ASCII digits to Myanmar digits; leave other characters unchanged. */
export function toMyanmarDigits(text){
 return String(text).replace(/[0-9]/g,d=>MYANMAR_DIGITS[Number(d)]);
}

export function smeIntlLocale(language){
 return normalizeSmeLanguage(language)==='my'?'my-MM':'en';
}

/** MMK amounts: English uses Intl MMK; Burmese uses grouped Latin format then Myanmar digits + ကျပ်. */
export function formatMmk(amount,language='en'){
 const value=Number(amount)||0;
 if(normalizeSmeLanguage(language)!=='my'){
  return new Intl.NumberFormat('en',{style:'currency',currency:'MMK',maximumFractionDigits:0}).format(value);
 }
 // Chromium ICU often keeps Latin digits for MMK even with my-MM / numberingSystem=myanmar.
 const grouped=new Intl.NumberFormat('en-US',{maximumFractionDigits:0}).format(value);
 return `${toMyanmarDigits(grouped)} ကျပ်`;
}

/** Unix seconds → readable local date/time in the SME language. */
export function formatSmeDateTime(seconds,language='en',options={}){
 if(seconds==null||seconds==='')return '';
 const date=seconds instanceof Date?seconds:new Date(Number(seconds)*1000);
 if(Number.isNaN(date.getTime()))return '';
 const my=normalizeSmeLanguage(language)==='my';
 const locale=my?'my-MM':'en';
 const defaults={dateStyle:'medium',timeStyle:'short',...options};
 let text;
 try{text=new Intl.DateTimeFormat(locale,defaults).format(date)}catch{text=date.toLocaleString(locale)}
 return my?toMyanmarDigits(text):text;
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
