/** Guest cloud UI copy (Burmese first). Separate from SME localization dictionaries. */
export const GUEST_LANGUAGE_STORAGE_KEY = 'mikromagic-guest-language';
export const SUPPORTED_GUEST_LANGUAGES = ['my', 'en'];

export const GUEST_MESSAGES = {
  en: {
    shell: {
      guestAccess: 'Guest access',
      language: 'Language / ဘာသာစကား',
      myanmar: 'မြန်မာ',
      english: 'English',
    },
    nav: {
      'Guest portal': 'Guest portal',
      'My access': 'My access',
      Media: 'Media',
      Account: 'Account',
    },
    entry: {
      eyebrow: site => `GUEST ACCESS · ${site}`,
      username: 'Username',
      password: 'Password',
      acceptTerms: "I accept this business's published terms.",
      createAccount: 'Create guest account',
      signIn: 'Sign in',
      haveAccount: 'Already have an account?',
      needAccount: 'Create an account',
      defaultTerms: 'Contact the business for its access and payment terms.',
      footer: 'Payment and voucher records are available after sign-in. Live internet access and media playback are not connected.',
    },
    purchase: {
      unpublishedTitle: 'Guest portal',
      unpublished: 'The business has not published its portal yet. Contact the owner for assistance.',
      contact: value => `Contact: ${value}`,
      terms: 'Business terms',
      directOff: 'Direct purchases are currently disabled by the business owner.',
      package: 'Access package',
      selectPackage: 'Select a package',
      playbackNote: 'Playback is not connected.',
      payTo: dest => `Pay to ${dest}`,
      payHint: 'Use real payment evidence for the shop. Live internet and media access still need the shop router.',
      method: 'Payment method',
      reference: 'Transaction reference',
      evidence: 'Receipt evidence / payment details',
      submit: 'Submit for owner review',
      afterSubmit: 'After submitting, attach receipt images under My access. The owner reviews your submission. Approval creates a stored pass; live access awaits the router.',
    },
    redeem: {
      title: 'Already have a voucher?',
      code: 'Voucher code',
      placeholder: 'Enter the complete code',
      submit: 'Redeem voucher',
      note: "Redemption creates your stored pass. Internet and playback access await the shop's router.",
    },
    access: {
      title: 'Access check',
      checking: 'Checking…',
      checkAgain: 'Check again',
      evidenceUnavailable: 'Live network check unavailable',
      evidenceAvailable: 'Network evidence available',
      noDiagnosis: 'No diagnosis has been loaded.',
      freshness: value => `Freshness: ${value || 'unknown'} · The app will not guess whether a MikroTik session is online.`,
      businessWide: 'Business-wide',
      reference: id => `Reference ${id}`,
      voucherEnding: hint => `Voucher ending: ••••${hint}`,
      dataRecord: (remain, limit) => `Stored data record: ${remain} remaining of ${limit}.`,
      timeRecord: (remain, limit) => `Stored time record: ${remain} remaining of ${limit}.`,
      whatYouCanDo: 'What you can do:',
      usageSource: 'Usage source: MikroMagic record, not router verified. Last router observation: unavailable.',
      empty: 'No payment or pass records are attached to this guest account.',
      orders: 'Your orders',
      states: {
        awaiting_review: 'Awaiting payment review',
        evidence_needed: 'More evidence needed',
        payment_rejected: 'Payment rejected',
        provisioning_pending: 'Provisioning pending',
        access_stopped: 'Access stopped',
        quota_exhausted: 'Allowance exhausted',
        locally_active_unverified: 'Activation recorded · network unverified',
        unknown: 'Status unavailable',
      },
    },
  },
  my: {
    shell: {
      guestAccess: 'ဧည့်သည် ဝင်ရောက်မှု',
      language: 'Language / ဘာသာစကား',
      myanmar: 'မြန်မာ',
      english: 'English',
    },
    nav: {
      'Guest portal': 'ဧည့်သည် portal',
      'My access': 'ကျွန်ုပ်၏ ဝင်ရောက်ခွင့်',
      Media: 'မီဒီယာ',
      Account: 'အကောင့်',
    },
    entry: {
      eyebrow: site => `ဧည့်သည် ဝင်ရောက်မှု · ${site}`,
      username: 'အသုံးပြုသူအမည်',
      password: 'စကားဝှက်',
      acceptTerms: 'ဤလုပ်ငန်း၏ ထုတ်ပြန်ထားသော စည်းမျဉ်းများကို လက်ခံပါသည်။',
      createAccount: 'ဧည့်သည် အကောင့် ဖန်တီးရန်',
      signIn: 'ဝင်ရောက်ရန်',
      haveAccount: 'အကောင့် ရှိပြီးသားလား။',
      needAccount: 'အကောင့် ဖန်တီးရန်',
      defaultTerms: 'ဝင်ရောက်ခွင့်နှင့် ငွေပေးချေမှု စည်းမျဉ်းများအတွက် ဆိုင်ကို ဆက်သွယ်ပါ။',
      footer: 'ဝင်ရောက်ပြီးနောက် ငွေပေးချေမှုနှင့် voucher မှတ်တမ်းများကို ကြည့်နိုင်ပါသည်။ တိုက်ရိုက် အင်တာနက်နှင့် မီဒီယာ ဖွင့်ခြင်းကို မချိတ်ဆက်ရသေးပါ။',
    },
    purchase: {
      unpublishedTitle: 'ဧည့်သည် portal',
      unpublished: 'လုပ်ငန်းက portal ကို မထုတ်ပြန်ရသေးပါ။ ပိုင်ရှင်ကို ဆက်သွယ်ပါ။',
      contact: value => `ဆက်သွယ်ရန်: ${value}`,
      terms: 'လုပ်ငန်း စည်းမျဉ်းများ',
      directOff: 'လုပ်ငန်းပိုင်ရှင်က တိုက်ရိုက် ဝယ်ယူမှုကို ပိတ်ထားပါသည်။',
      package: 'Access package',
      selectPackage: 'Package ရွေးပါ',
      playbackNote: 'Playback ကို မချိတ်ဆက်ရသေးပါ။',
      payTo: dest => `${dest} သို့ ပေးချေရန်`,
      payHint: 'ဆိုင်အတွက် တကယ့် ငွေပေးချေမှု အထောက်အထား သုံးပါ။ တိုက်ရိုက် အင်တာနက်နှင့် မီဒီယာအတွက် ဆိုင် router လိုအပ်ပါသေးသည်။',
      method: 'ငွေပေးချေနည်း',
      reference: 'ငွေလွှဲ အမှတ်စဉ်',
      evidence: 'ပြေစာ / ငွေပေးချေမှု အသေးစိတ်',
      submit: 'ပိုင်ရှင် စစ်ဆေးရန် တင်သွင်းမည်',
      afterSubmit: 'တင်သွင်းပြီးနောက် My access တွင် ပြေစာပုံများ ပူးတွဲပါ။ ပိုင်ရှင်က စစ်ဆေးပြီး အတည်ပြုပါက pass သိမ်းပါမည်။ တိုက်ရိုက် ဝင်ရောက်ခွင့်အတွက် router လိုအပ်ပါသေးသည်။',
    },
    redeem: {
      title: 'Voucher ရှိပြီးသားလား။',
      code: 'Voucher ကုဒ်',
      placeholder: 'ကုဒ် အပြည့်အစုံ ရိုက်ထည့်ပါ',
      submit: 'Voucher အသုံးပြုရန်',
      note: 'အသုံးပြုခြင်းဖြင့် သိမ်းထားသော pass ဖြစ်ပါမည်။ အင်တာနက်နှင့် playback အတွက် ဆိုင် router လိုအပ်ပါသေးသည်။',
    },
    access: {
      title: 'ဝင်ရောက်ခွင့် စစ်ဆေးရန်',
      checking: 'စစ်ဆေးနေသည်…',
      checkAgain: 'ထပ်စစ်ရန်',
      evidenceUnavailable: 'ကွန်ရက် အခြေအနေ စစ်ဆေး၍ မရပါ',
      evidenceAvailable: 'ကွန်ရက် အထောက်အထား ရရှိပါသည်',
      noDiagnosis: 'ရလဒ် မတင်ထားရသေးပါ။',
      freshness: value => `လတ်တလောအခြေအနေ: ${value || 'မသိ'} · MikroTik session အွန်လိုင်း ဟုတ်/မဟုတ်ကို ခန့်မှန်းမပြပါ။`,
      businessWide: 'လုပ်ငန်းအနှံ့',
      reference: id => `အကိုးအကား ${id}`,
      voucherEnding: hint => `Voucher အဆုံး: ••••${hint}`,
      dataRecord: (remain, limit) => `သိမ်းထားသော ဒေတာ: ${remain} ကျန် / ${limit}။`,
      timeRecord: (remain, limit) => `သိမ်းထားသော အချိန်: ${remain} ကျန် / ${limit}။`,
      whatYouCanDo: 'သင်လုပ်နိုင်သည်:',
      usageSource: 'အသုံးပြုမှု အရင်းအမြစ်: MikroMagic မှတ်တမ်းသာ၊ router အတည်မပြုရသေးပါ။',
      empty: 'ဤဧည့်သည် အကောင့်တွင် ငွေပေးချေမှု သို့မဟုတ် pass မှတ်တမ်း မရှိပါ။',
      orders: 'သင့် မှာယူမှုများ',
      states: {
        awaiting_review: 'ငွေပေးချေမှု စစ်ဆေးရန် စောင့်နေသည်',
        evidence_needed: 'အထောက်အထား ထပ်လိုအပ်သည်',
        payment_rejected: 'ငွေပေးချေမှု ငြင်းပယ်ထားသည်',
        provisioning_pending: 'ပြင်ဆင်နေသည်',
        access_stopped: 'ဝင်ရောက်ခွင့် ရပ်ထားသည်',
        quota_exhausted: 'ခွင့်ပြုချက် ကုန်သွားသည်',
        locally_active_unverified: 'အသက်သွင်းပြီး · ကွန်ရက် မအတည်ပြုရသေး',
        unknown: 'အခြေအနေ မရရှိပါ',
      },
    },
  },
};

function availableStorage() {
  return typeof window !== 'undefined' ? window.localStorage : null;
}

export function normalizeGuestLanguage(value) {
  return SUPPORTED_GUEST_LANGUAGES.includes(value) ? value : 'my';
}

export function readGuestLanguage(storage = availableStorage()) {
  if (!storage) return 'my';
  try {
    return normalizeGuestLanguage(storage.getItem(GUEST_LANGUAGE_STORAGE_KEY));
  } catch {
    return 'my';
  }
}

export function persistGuestLanguage(language, storage = availableStorage()) {
  const selected = normalizeGuestLanguage(language);
  if (!storage) return selected;
  try {
    storage.setItem(GUEST_LANGUAGE_STORAGE_KEY, selected);
  } catch {}
  return selected;
}

export function getGuestMessage(language, section, key) {
  const lang = normalizeGuestLanguage(language);
  return GUEST_MESSAGES[lang]?.[section]?.[key] ?? GUEST_MESSAGES.en?.[section]?.[key] ?? key;
}
