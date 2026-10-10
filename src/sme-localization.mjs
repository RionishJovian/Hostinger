export const SME_LANGUAGE_STORAGE_KEY='mikromagic-sme-language';
export const LEGACY_OVERVIEW_LANGUAGE_STORAGE_KEY='mikromagic-overview-language';
export const SUPPORTED_SME_LANGUAGES=['my','en'];

export const SME_MESSAGES={
 en:{
  navigation:{Overview:'Overview',Revenue:'Revenue',Sites:'Sites',Network:'Network',Routers:'Routers',Internet:'Internet','Captive portal':'Captive portal',Packages:'Packages',Vouchers:'Vouchers',Payments:'Payments',Staff:'Staff',Subscription:'Subscription',Integrations:'Integrations',Media:'Media','Did you know?':'Did you know?',Audit:'Audit',Account:'Account'},
  shell:{businessWorkspace:'Business workspace',authenticatedRecords:'Authenticated records',refresh:'Refresh',signOut:'Sign out',colorMode:'Toggle color mode',toggleNavigation:'Toggle navigation',dismissNotification:'Dismiss notification',language:'Language / ဘာသာစကား',saved:'Saved to your business records.'},
  overview:{networkTitle:'Your network.',businessTitle:'Your business.',health:'Wi-Fi health',question:'Is my business Wi-Fi working?',attention:'Needs Your Attention',summary:'Network summary',shops:'Shops',gateways:'Registered gateways',aps:'Registered APs',customers:'Connected customers',vouchers:'Generated vouchers',notConnected:'Not Connected',unable:'Unable to Verify',noRouter:'No MikroTik gateway is registered. Wi-Fi status and connected customers cannot be checked.',unverified:'The registered router connection is not verified. Wi-Fi status and connected customers cannot be checked.',siteNeeded:'Add a shop/site before connecting a gateway.',payments:n=>`${n} payment review${n===1?'':'s'} waiting`,paymentsHint:'Review the submitted payment evidence.',noKnown:'No additional issues are recorded. Wi-Fi health is still unverified.',routerAction:'Open Routers',siteAction:'Open Shops',paymentAction:'Review Payments',countNote:'Registration records; not live connection status.',apNote:'Owner-reported inventory; not live device status.',customerNote:'Live client telemetry is unavailable.',voucherNote:'Stored voucher inventory; not MikroTik activation.',unavailable:'Unavailable'}
 },
 my:{
  navigation:{Overview:'အနှစ်ချုပ်',Revenue:'ဝင်ငွေ',Sites:'ဆိုင်များ',Network:'ကွန်ရက်',Routers:'Router များ',Internet:'အင်တာနက်','Captive portal':'Captive portal',Packages:'Package များ',Vouchers:'Voucher များ',Payments:'ငွေပေးချေမှု',Staff:'ဝန်ထမ်းများ',Subscription:'စာရင်းသွင်းမှု',Integrations:'Integrations',Media:'မီဒီယာ','Did you know?':'သိကောင်းစရာ',Audit:'စာရင်းစစ်မှတ်တမ်း',Account:'အကောင့်'},
  shell:{businessWorkspace:'လုပ်ငန်း workspace',authenticatedRecords:'အကောင့်ဖြင့် ဝင်ထားသော မှတ်တမ်းများ',refresh:'ပြန်လည်စစ်ဆေးရန်',signOut:'ထွက်ရန်',colorMode:'အရောင်မုဒ် ပြောင်းရန်',toggleNavigation:'Navigation ကို ဖွင့်/ပိတ်ရန်',dismissNotification:'အသိပေးချက်ကို ပိတ်ရန်',language:'Language / ဘာသာစကား',saved:'လုပ်ငန်းမှတ်တမ်းများတွင် သိမ်းဆည်းပြီးပါပြီ။'},
  overview:{networkTitle:'သင့်ကွန်ရက်။',businessTitle:'သင့်လုပ်ငန်း။',health:'Wi-Fi အခြေအနေ',question:'လုပ်ငန်း၏ Wi-Fi အလုပ်လုပ်နေပါသလား။',attention:'သတိပြုရန်',summary:'ကွန်ရက်အကျဉ်းချုပ်',shops:'ဆိုင်များ',gateways:'စာရင်းသွင်းထားသော Gateway များ',aps:'စာရင်းသွင်းထားသော AP များ',customers:'ချိတ်ဆက်ထားသော သုံးစွဲသူများ',vouchers:'ထုတ်ပေးထားသော Voucher များ',notConnected:'မချိတ်ဆက်ရသေးပါ',unable:'အတည်ပြုမရပါ',noRouter:'MikroTik Gateway စာရင်းမရှိသေးပါ။ Wi-Fi အခြေအနေနှင့် ချိတ်ဆက်ထားသော သုံးစွဲသူများကို မစစ်ဆေးနိုင်ပါ။',unverified:'စာရင်းသွင်းထားသော Router ချိတ်ဆက်မှုကို အတည်မပြုရသေးပါ။ Wi-Fi အခြေအနေနှင့် သုံးစွဲသူများကို မစစ်ဆေးနိုင်ပါ။',siteNeeded:'Gateway မချိတ်ဆက်မီ ဆိုင်/နေရာတစ်ခု ထည့်ပါ။',payments:n=>`${n} ခုသော ငွေပေးချေမှုကို စစ်ဆေးရန် စောင့်နေသည်`,paymentsHint:'တင်ထားသော ငွေပေးချေမှုအထောက်အထားကို စစ်ဆေးပါ။',noKnown:'ထပ်မံသိရှိထားသော ပြဿနာမရှိပါ။ Wi-Fi အခြေအနေကို အတည်မပြုနိုင်သေးပါ။',routerAction:'Router များ',siteAction:'ဆိုင်များ',paymentAction:'ငွေပေးချေမှု စစ်ဆေးရန်',countNote:'စာရင်းမှတ်တမ်းသာဖြစ်ပြီး ချိတ်ဆက်မှုအခြေအနေ မဟုတ်ပါ။',apNote:'ပိုင်ရှင်ထည့်သွင်းထားသော စာရင်းသာဖြစ်ပြီး စက်အခြေအနေ မဟုတ်ပါ။',customerNote:'လက်ရှိ Client တိုင်းတာချက် မရရှိနိုင်ပါ။',voucherNote:'သိမ်းဆည်းထားသော Voucher စာရင်းဖြစ်ပြီး MikroTik တွင် အသက်သွင်းထားခြင်း မဟုတ်ပါ။',unavailable:'မရရှိနိုင်ပါ'}
 }
};

function availableStorage(){return typeof window!=='undefined'?window.localStorage:null}
export function normalizeSmeLanguage(value){return SUPPORTED_SME_LANGUAGES.includes(value)?value:'my'}
export function readSmeLanguage(storage=availableStorage()){
 if(!storage)return 'my';
 try{return normalizeSmeLanguage(storage.getItem(SME_LANGUAGE_STORAGE_KEY)||storage.getItem(LEGACY_OVERVIEW_LANGUAGE_STORAGE_KEY))}catch{return 'my'}
}
export function persistSmeLanguage(language,storage=availableStorage()){
 const selected=normalizeSmeLanguage(language);
 if(!storage)return selected;
 try{storage.setItem(SME_LANGUAGE_STORAGE_KEY,selected);storage.setItem(LEGACY_OVERVIEW_LANGUAGE_STORAGE_KEY,selected)}catch{}
 return selected;
}
export function getSmeMessage(language,section,key){return SME_MESSAGES[normalizeSmeLanguage(language)]?.[section]?.[key]??SME_MESSAGES.en?.[section]?.[key]??key}
