/** Owner preview of the Lantern Leaf HotSpot pages. Visual copy of the package the router serves.
 *  The code box does not run RouterOS CHAP and does not contact a router. */

const CSS_BASE = '*{box-sizing:border-box}html{color-scheme:dark}'
  + 'body{margin:0;min-height:100vh;font:16px/1.55 system-ui,-apple-system,"Segoe UI",Roboto,'
  + '"Noto Sans Myanmar","Myanmar Text","Padauk",sans-serif;color:#F3ECDD;'
  + 'background:#0A1210;background-image:'
  + 'radial-gradient(ellipse 90% 55% at 92% 0%,rgba(242,179,90,.42),transparent 58%),'
  + 'radial-gradient(ellipse 70% 45% at 8% 18%,rgba(140,74,28,.28),transparent 55%),'
  + 'radial-gradient(ellipse 85% 50% at 20% 100%,rgba(18,73,58,.55),transparent 60%),'
  + 'linear-gradient(180deg,#0A1210 0%,#0E1D18 100%)}'
  + '.wrap{min-height:100vh;display:flex;flex-direction:column;padding:1rem 1rem 0;max-width:26rem;margin:0 auto}'
  + '.top{display:flex;align-items:center;justify-content:space-between;gap:.75rem;margin:0 0 1rem}'
  + '.seal{width:3rem;height:3rem;border-radius:50%;display:flex;align-items:center;justify-content:center;'
  + 'font-weight:700;font-size:1.25rem;color:#FBF4E4;background:rgba(217,138,50,.18);'
  + 'border:2px solid #D98A32;box-shadow:inset 0 0 0 1px rgba(242,179,90,.45)}'
  + '.brand{font-size:1.7rem;font-weight:700;line-height:1.3;margin:0 0 .4rem;letter-spacing:0}'
  + '.lead{margin:0 0 1.25rem;color:#CFC6B3;font-size:.95rem;line-height:1.65}'
  + '.sheet{margin-top:auto;background:rgba(14,29,24,.92);border:1px solid rgba(243,236,221,.12);'
  + 'border-bottom:0;border-radius:1.35rem 1.35rem 0 0;padding:1.25rem 1.1rem calc(1.25rem + env(safe-area-inset-bottom,0px));'
  + 'box-shadow:0 -12px 40px rgba(0,0,0,.35)}'
  + 'label{display:block;font-weight:600;margin:0 0 .35rem;color:#F3ECDD;font-size:.9rem}'
  + 'input,button.primary,button.secondary{display:block;width:100%;font:inherit;padding:.9rem .85rem;margin:0 0 .75rem;min-height:52px;border-radius:.75rem}'
  + 'input{background:rgba(243,236,221,.06);color:#F3ECDD;border:1.5px solid rgba(243,236,221,.22)}'
  + 'input::placeholder{color:#9A9384}'
  + 'button.primary{background:linear-gradient(180deg,#1F7F5C,#145C45);color:#FBF4E4;border:0;font-weight:700}'
  + '#voucher{text-transform:uppercase;letter-spacing:.14em;text-align:center;font-size:1.25rem;font-weight:700}'
  + '#voucher::placeholder{text-transform:none;letter-spacing:normal;font-weight:400;font-size:1rem}'
  + '.hint{margin:-.35rem 0 .9rem;color:#9A9384;font-size:.8rem;line-height:1.55}'
  + '.divider{display:flex;align-items:center;gap:.6rem;margin:1rem 0 .85rem;color:#CFC6B3;font-size:.85rem}'
  + '.divider:before,.divider:after{content:"";flex:1;height:1px;background:rgba(243,236,221,.14)}'
  + '.pay{margin:0 0 .85rem;padding:.9rem;border-radius:.85rem;background:rgba(217,138,50,.1);border:1px solid rgba(242,179,90,.45)}'
  + '.pay h2{margin:0 0 .45rem;font-size:.95rem;color:#F2C27B;font-weight:700}'
  + '.pay .dest{margin:0 0 .4rem;font-size:1.05rem;font-weight:700;color:#F3ECDD;white-space:pre-wrap}'
  + '.pay .instr{margin:0 0 .45rem;color:#CFC6B3;font-size:.88rem;line-height:1.55;white-space:pre-wrap}'
  + '.pay .methods{margin:0;color:#9A9384;font-size:.78rem}'
  + '.fair{margin:.85rem 0 0;color:#9A9384;font-size:.75rem;line-height:1.5}'
  + 'a{color:#5FD3A2}.err{color:#E9856B;margin:0 0 .85rem}.ok{color:#5FD3A2;margin:0 0 .85rem}'
  + '.mm{margin:.9rem 0 0;text-align:center;font-size:.72rem;color:#9A9384;letter-spacing:.08em}'
  + '.mm:before{content:"";display:inline-block;width:.35rem;height:.35rem;border-radius:50%;background:#176B50;margin-right:.4rem;vertical-align:middle}';

const CSS_BOTH = CSS_BASE
  + '.langs{display:flex;gap:0;margin:0;border:1px solid rgba(243,236,221,.18);border-radius:.7rem;overflow:hidden;background:rgba(12,26,21,.72)}'
  + '.langs button{flex:1;min-width:4.2rem;padding:.45rem .65rem;font:inherit;border:0;background:transparent;color:#9A9384;min-height:40px}'
  + '.langs button[aria-pressed="true"]{background:rgba(243,236,221,.14);color:#F3ECDD;font-weight:700}'
  + '.my{display:none}html[lang="my"] .my{display:inline}html[lang="my"] .en{display:none}'
  + 'html[lang="en"] .en{display:inline}html[lang="en"] .my{display:none}'
  + 'html[lang="my"] .my-block{display:block}html[lang="my"] .en-block{display:none}'
  + 'html[lang="en"] .en-block{display:block}html[lang="en"] .my-block{display:none}';

const LANG_BAR = '<div class="langs" role="group" aria-label="Language"><button type="button" data-lang="my" aria-pressed="true">မြန်မာ</button><button type="button" data-lang="en" aria-pressed="false">English</button></div>';

const LANG_JS = '<script>(function(){var h=document.documentElement;'
  + 'function set(l){h.lang=l==="en"?"en":"my";'
  + 'document.querySelectorAll(".langs button").forEach(function(b){b.setAttribute("aria-pressed",b.getAttribute("data-lang")===h.lang?"true":"false")});'
  + 'var v=document.getElementById("voucher");if(v){v.placeholder=h.lang==="en"?"Type your code":"ကုဒ် ရိုက်ထည့်ပါ"}}'
  + 'set("my");'
  + 'document.querySelectorAll(".langs button").forEach(function(b){b.addEventListener("click",function(){set(b.getAttribute("data-lang"))})})})()</script>';

export const GUEST_PREVIEW_PAGE_IDS = ['login', 'connected', 'failed', 'status', 'signedOut'];

function modeOf(language) {
  return language === 'en' || language === 'my' || language === 'both' ? language : 'both';
}

function localText(value) {
  return String(value || '').replace(/https?:\/\//gi, '').replace(/[&<>"']/g, character => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[character]));
}

function bilingual(my, en, block) {
  const mine = block ? 'my-block' : 'my';
  const theirs = block ? 'en-block' : 'en';
  return `<span class="${mine}">${my}</span><span class="${theirs}">${en}</span>`;
}

function phrase(my, en, mode, block) {
  if (mode === 'my') return my;
  if (mode === 'en') return en;
  return bilingual(my, en, block);
}

function sealLetter(name) {
  const trimmed = String(name || '').trim();
  return localText(trimmed ? trimmed[0] : '?');
}

function welcomeText(raw, mode) {
  const value = String(raw || '').trim();
  if (!value || value === 'Welcome. Choose internet or media access.') {
    return phrase('ကုဒ်ထည့်ရုံနဲ့ Wi-Fi သုံးနိုင်ပါပြီ။', 'Just enter your code to use the Wi-Fi.', mode, true);
  }
  return localText(value);
}

function paymentCard(settings, mode) {
  if (!settings?.direct_purchase) return '';
  const destination = String(settings.payment_destination || '').trim();
  const instructions = String(settings.payment_instructions || '').trim();
  const methods = (settings.payment_methods || []).map(item => String(item || '').trim()).filter(Boolean);
  if (!destination || !instructions) return '';
  const methodsLine = methods.map(localText).join(' · ');
  return `<div class="divider">${phrase('ကုဒ် မရှိသေးဘူးလား။', 'No code yet?', mode)}</div>`
    + '<aside class="pay" aria-label="Payment">'
    + `<h2>${phrase('ဘဏ် / ဝေါလက် အချက်အလက်', 'Bank / wallet details', mode, true)}</h2>`
    + `<p class="dest">${localText(destination)}</p>`
    + `<p class="instr">${localText(instructions)}</p>`
    + (methodsLine ? `<p class="methods">${methodsLine}</p>` : '')
    + '</aside>';
}

function fairUse(settings, mode) {
  const terms = String(settings?.terms || '').trim();
  if (terms) return `<p class="fair">${localText(terms)}</p>`;
  return `<p class="fair">${phrase('လူတိုင်း အဆင်ပြေအောင် သင့်တင့်စွာ သုံးပေးပါ။', 'Please share the Wi-Fi fairly with everyone here.', mode)}</p>`;
}

function errorScript(mode) {
  if (mode === 'both') {
    return '<script>(function(){var el=document.getElementById("msg"),r=(el.getAttribute("data-raw")||"").toLowerCase(),my,en;'
      + 'if(/traffic|bytes|limit.*data|quota/.test(r)){my="ဒေတာ ကုန်သွားပါပြီ။";en="Data allowance used up."}'
      + 'else if(/uptime|time limit|session time|expired|lifetime/.test(r)){my="အချိန် ကုန်သွားပါပြီ။";en="Time allowance used up or expired."}'
      + 'else if(/no more sessions|simultaneous|shared-users|session limit|too many/.test(r)){my="စက် အရေအတွက် ပြည့်နေပါပြီ။";en="Too many devices are already connected."}'
      + 'else if(/disabled|not allowed/.test(r)){my="ဤကုဒ်ကို အသုံးပြု၍ မရပါ။";en="This code cannot be used."}'
      + 'else if(/invalid|password|unknown|not found|wrong/.test(r)||!r.trim()){my="ကုဒ် မှားနေပါသည်။";en="Wrong code. Check and try again."}'
      + 'else{my="ချိတ်ဆက်၍ မရပါ။ ထပ်ကြိုးစားပါ။";en="Could not connect. Try again."}'
      + 'el.innerHTML=\'<span class="my">\'+my+\'</span><span class="en">\'+en+\'</span>\'})()</script>';
  }
  if (mode === 'my') {
    return '<script>(function(){var el=document.getElementById("msg"),r=(el.getAttribute("data-raw")||"").toLowerCase(),msg;'
      + 'if(/traffic|bytes|limit.*data|quota/.test(r)){msg="ဒေတာ ကုန်သွားပါပြီ။"}'
      + 'else if(/uptime|time limit|session time|expired|lifetime/.test(r)){msg="အချိန် ကုန်သွားပါပြီ။"}'
      + 'else if(/no more sessions|simultaneous|shared-users|session limit|too many/.test(r)){msg="စက် အရေအတွက် ပြည့်နေပါပြီ။"}'
      + 'else if(/disabled|not allowed/.test(r)){msg="ဤကုဒ်ကို အသုံးပြု၍ မရပါ။"}'
      + 'else if(/invalid|password|unknown|not found|wrong/.test(r)||!r.trim()){msg="ကုဒ် မှားနေပါသည်။"}'
      + 'else{msg="ချိတ်ဆက်၍ မရပါ။ ထပ်ကြိုးစားပါ။"}'
      + 'el.textContent=msg})()</script>';
  }
  return '<script>(function(){var el=document.getElementById("msg"),r=(el.getAttribute("data-raw")||"").toLowerCase(),msg;'
    + 'if(/traffic|bytes|limit.*data|quota/.test(r)){msg="Data allowance used up."}'
    + 'else if(/uptime|time limit|session time|expired|lifetime/.test(r)){msg="Time allowance used up or expired."}'
    + 'else if(/no more sessions|simultaneous|shared-users|session limit|too many/.test(r)){msg="Too many devices are already connected."}'
    + 'else if(/disabled|not allowed/.test(r)){msg="This code cannot be used."}'
    + 'else if(/invalid|password|unknown|not found|wrong/.test(r)||!r.trim()){msg="Wrong code. Check and try again."}'
    + 'else{msg="Could not connect. Try again."}'
    + 'el.textContent=msg})()</script>';
}

function page(titleMy, titleEn, content, settings) {
  const mode = modeOf(settings?.language);
  const brand = localText(settings?.business_name || 'Shop');
  const welcome = welcomeText(settings?.welcome, mode);
  const seal = sealLetter(settings?.business_name);
  let lang, title, langBar, langJs, css, headings;
  if (mode === 'en') {
    lang = 'en'; title = titleEn; langBar = ''; langJs = ''; css = CSS_BASE;
    headings = `<h1 class="lead" style="font-weight:700;color:#F3ECDD;margin:0 0 .35rem">${localText(titleEn)}</h1>`;
  } else if (mode === 'my') {
    lang = 'my'; title = titleMy; langBar = ''; langJs = ''; css = CSS_BASE;
    headings = `<h1 class="lead" style="font-weight:700;color:#F3ECDD;margin:0 0 .35rem">${localText(titleMy)}</h1>`;
  } else {
    lang = 'my'; title = titleMy; langBar = LANG_BAR; langJs = LANG_JS; css = CSS_BOTH;
    headings = `<h1 class="my-block lead" style="font-weight:700;color:#F3ECDD;margin:0 0 .35rem">${localText(titleMy)}</h1>`
      + `<h1 class="en-block lead" style="font-weight:700;color:#F3ECDD;margin:0 0 .35rem">${localText(titleEn)}</h1>`;
  }
  const top = langBar
    ? `<div class="top"><div class="seal" aria-hidden="true">${seal}</div>${langBar}</div>`
    : `<div class="top"><div class="seal" aria-hidden="true">${seal}</div></div>`;
  return `<!doctype html><html lang="${lang}"><head><meta charset="utf-8">`
    + '<meta name="viewport" content="width=device-width,initial-scale=1">'
    + '<meta name="color-scheme" content="dark">'
    + `<title>${localText(title)} · ${brand}</title><style>${css}</style></head><body><div class="wrap">`
    + `${top}<p class="brand">${brand}</p>${headings}<p class="lead">${welcome}</p>`
    + `<div class="sheet">${content}${fairUse(settings, mode)}${langJs}<p class="mm">MikroMagic</p></div></div></body></html>`;
}

export function previewHotspotPages(settings = {}) {
  const mode = modeOf(settings.language);
  const pay = paymentCard(settings, mode);
  const login = '<form action="#" method="post" onsubmit="return false">'
    + `<label>${phrase('Wi-Fi ကုဒ်', 'Wi-Fi code', mode)}`
    + '<input id="voucher" autocomplete="username" inputmode="text" autocapitalize="characters" spellcheck="false" '
    + `placeholder="${mode === 'en' ? 'Type your code' : 'ကုဒ် ရိုက်ထည့်ပါ'}" value=""></label>`
    + `<p class="hint">${phrase('စာလုံးအကြီး/အသေး၊ (-) ပါ/မပါ ရိုက်နိုင်ပါတယ်။', 'Capital or small letters, with or without the dash.', mode)}</p>`
    + `<button class="primary" type="submit">${phrase('ချိတ်ဆက်ရန်', 'Connect', mode)}</button></form>`
    + pay;
  const failed = '<p class="err" id="msg" data-raw="invalid password"></p>'
    + `<a href="#">${phrase('ထပ်ကြိုးစားရန်', 'Try again', mode)}</a>`
    + errorScript(mode);
  return {
    login: page('Wi-Fi ဝင်ရန်', 'Wi-Fi login', login, settings),
    connected: page('ချိတ်ဆက်ပြီးပါပြီ', 'Connected',
      `<p class="ok">${phrase('အင်တာနက် သုံးနိုင်ပါပြီ။', 'You are connected.', mode)}</p><a href="#">${phrase('အခြေအနေ ကြည့်ရန်', 'Session status', mode)}</a>`,
      settings),
    failed: page('ချိတ်ဆက် မရပါ', 'Could not connect', failed, settings),
    status: page('Session အခြေအနေ', 'Session status',
      `<p>${phrase('ကျန်အချိန်', 'Time left', mode)}: 1h12m</p><p>${phrase('ကျန်ဒေတာ', 'Data left', mode)}: 800.0MiB</p><button class="primary" type="button">${phrase('ထွက်ရန်', 'Sign out', mode)}</button>`,
      settings),
    signedOut: page('ထွက်ပြီးပါပြီ', 'Signed out',
      `<p>${phrase('Session ပြီးဆုံးပါပြီ။', 'Your HotSpot session has ended.', mode)}</p><a href="#">${phrase('ပြန်ဝင်ရန်', 'Return to login', mode)}</a>`,
      settings)
  };
}
