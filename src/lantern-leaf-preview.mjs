/** Owner preview of the Lantern Leaf HotSpot pages. Visual copy of the package the router serves; CSS is byte-identical to backend/local_portal_package.py.
 *  The code box does not run RouterOS CHAP and does not contact a router. */

const CSS_BASE = "*{box-sizing:border-box}html{color-scheme:dark}body{margin:0;min-height:100vh;font:16px/1.6 system-ui,-apple-s"
  + "ystem,\"Segoe UI\",Roboto,\"Noto Sans Myanmar\",\"Myanmar Text\",\"Padauk\",sans-serif;color:#E6E9ED;background:#0B101"
  + "4 linear-gradient(180deg,#0B1014 0%,#121A1F 100%)}.wrap{min-height:100vh;display:flex;flex-direction:column;ju"
  + "stify-content:center;padding:16px 16px 0;max-width:26rem;margin:0 auto}.top{display:flex;align-items:center;ju"
  + "stify-content:space-between;gap:16px;margin:0 0 16px}.seal{width:48px;height:48px;border-radius:50%;display:fl"
  + "ex;align-items:center;justify-content:center;font-weight:700;font-size:1.25rem;color:#E6E9ED;background:rgba(2"
  + "2,30,36,.78);border:1px solid rgba(200,205,212,.72);box-shadow:inset 0 0 0 3px #121A1F,0 0 0 1px rgba(200,205,"
  + "212,.18)}.brand{font-size:1.7rem;font-weight:700;line-height:1.3;margin:0 0 8px;letter-spacing:0}.lead{margin:"
  + "0 0 16px;color:#A8B0B8;font-size:.95rem;line-height:1.6}.page-title{margin:0 0 16px;color:#E6E9ED;font-size:1."
  + "15rem;line-height:1.6}.sheet{margin-top:16px;background:rgba(22,30,36,.78);border:1px solid rgba(200,205,212,."
  + "14);border-radius:20px;margin-bottom:calc(16px + env(safe-area-inset-bottom,0px));padding:20px 16px;box-shadow"
  + ":0 12px 40px rgba(0,0,0,.35)}label{display:block;font-weight:600;margin:0 0 8px;color:#E6E9ED;font-size:.9rem}"
  + "input,button.primary,button.secondary{display:block;width:100%;font:inherit;padding:12px 16px;margin:0 0 16px;"
  + "min-height:52px;border-radius:12px}input{background:rgba(230,233,237,.06);color:#E6E9ED;border:1.5px solid rgb"
  + "a(200,205,212,.22)}input::placeholder{color:#7A838C}button.primary{background:linear-gradient(180deg,#1F8F68,#"
  + "147A56);color:#E6E9ED;border:0;font-weight:700}button.primary:disabled{opacity:.65}#voucher{text-transform:upp"
  + "ercase;letter-spacing:.14em;text-align:center;font-size:1.25rem;font-weight:700}#voucher::placeholder{text-tra"
  + "nsform:none;letter-spacing:normal;font-weight:400;font-size:1rem}.hint{margin:-8px 0 16px;color:#7A838C;font-s"
  + "ize:.8rem;line-height:1.6}.divider{display:flex;align-items:center;gap:8px;margin:16px 0;color:#A8B0B8;font-si"
  + "ze:.85rem}.divider:before,.divider:after{content:\"\";flex:1;height:1px;background:rgba(200,205,212,.14)}.pay{ma"
  + "rgin:0 0 16px;padding:16px;border-radius:12px;background:rgba(230,233,237,.04);border:1px solid rgba(200,205,2"
  + "12,.14)}.pay h2{margin:0 0 8px;font-size:.95rem;color:#E6E9ED;font-weight:700}.pay .dest{margin:0 0 8px;font-s"
  + "ize:1.05rem;font-weight:700;color:#E6E9ED;white-space:pre-wrap}.pay .instr{margin:0 0 8px;color:#A8B0B8;font-s"
  + "ize:.88rem;line-height:1.6;white-space:pre-wrap}.pay .methods{margin:0;color:#7A838C;font-size:.78rem}.fair{ma"
  + "rgin:16px 0 0;color:#7A838C;font-size:.75rem;line-height:1.6}a{color:#5FD3A2}.secondary{display:flex;width:100"
  + "%;min-height:44px;align-items:center;justify-content:center;padding:8px 16px;border:1px solid rgba(200,205,212"
  + ",.22);border-radius:12px;color:#E6E9ED;background:rgba(230,233,237,.04);font-weight:700;text-align:center;text"
  + "-decoration:none}.err{color:#E9856B;margin:0 0 16px}.ok{color:#5FD3A2;margin:0 0 16px}.status-grid{display:gri"
  + "d;grid-template-columns:1fr 1fr;gap:16px}.stat{padding:16px;border-radius:12px;background:rgba(230,233,237,.04"
  + ");border:1px solid rgba(200,205,212,.14)}.stat-label{display:block;color:#7A838C;font-size:.8rem}.stat-value{d"
  + "isplay:block;margin-top:8px;color:#E6E9ED;font-weight:700}.status-logout{margin-top:24px}.status-logout .prima"
  + "ry{min-height:52px;margin-bottom:0}.mm{margin:16px 0 0;text-align:center;font-size:.72rem;color:#7A838C;letter"
  + "-spacing:.08em}.mm:before{content:\"\";display:inline-block;width:.35rem;height:.35rem;border-radius:50%;backgro"
  + "und:#176B50;margin-right:.4rem;vertical-align:middle}";

const CSS_BOTH = CSS_BASE
  + ".langs{display:flex;gap:0;margin:0;border:1px solid rgba(200,205,212,.18);border-radius:12px;overflow:hidden;b"
  + "ackground:rgba(22,30,36,.78)}.langs button{flex:1;min-width:4.2rem;padding:.45rem .65rem;font:inherit;border:0"
  + ";background:transparent;color:#7A838C;min-height:44px}.langs button[aria-pressed=\"true\"]{background:rgba(200,2"
  + "05,212,.14);color:#E6E9ED;font-weight:700}.my{display:none}html[lang=\"my\"] .my{display:inline}html[lang=\"my\"] "
  + ".en{display:none}html[lang=\"en\"] .en{display:inline}html[lang=\"en\"] .my{display:none}html[lang=\"my\"] .my-block"
  + "{display:block}html[lang=\"my\"] .en-block{display:none}html[lang=\"en\"] .en-block{display:block}html[lang=\"en\"] "
  + ".my-block{display:none}";

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

function page(titleMy, titleEn, content, settings, {login = false, showWelcome = true} = {}) {
  const mode = modeOf(settings?.language);
  const brand = localText(settings?.business_name || 'Shop');
  const welcome = welcomeText(settings?.welcome, mode);
  const seal = sealLetter(settings?.business_name);
  let lang, title, langBar, langJs, css, headings;
  if (mode === 'en') {
    lang = 'en'; title = titleEn; langBar = ''; langJs = ''; css = CSS_BASE;
    headings = `<h1 class="page-title">${localText(titleEn)}</h1>`;
  } else if (mode === 'my') {
    lang = 'my'; title = titleMy; langBar = ''; langJs = ''; css = CSS_BASE;
    headings = `<h1 class="page-title">${localText(titleMy)}</h1>`;
  } else {
    lang = 'my'; title = titleMy; langBar = LANG_BAR; langJs = LANG_JS; css = CSS_BOTH;
    headings = `<h1 class="my-block page-title">${localText(titleMy)}</h1>`
      + `<h1 class="en-block page-title">${localText(titleEn)}</h1>`;
  }
  const top = langBar
    ? `<div class="top"><div class="seal" aria-hidden="true">${seal}</div>${langBar}</div>`
    : `<div class="top"><div class="seal" aria-hidden="true">${seal}</div></div>`;
  return `<!doctype html><html lang="${lang}"><head><meta charset="utf-8">`
    + '<meta name="viewport" content="width=device-width,initial-scale=1">'
    + '<meta name="color-scheme" content="dark">'
    + `<title>${localText(title)} · ${brand}</title><style>${css}</style></head><body><div class="wrap">`
    + `${top}<p class="brand">${brand}</p>${login ? '' : headings}${showWelcome ? `<p class="lead">${welcome}</p>` : ''}`
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
    + `<a class="secondary" href="#">${phrase('ထပ်ကြိုးစားရန်', 'Try again', mode)}</a>`
    + errorScript(mode);
  return {
    login: page('Wi-Fi ဝင်ရန်', 'Wi-Fi login', login, settings, {login: true}),
    connected: page('ချိတ်ဆက်ပြီးပါပြီ', 'Connected',
      `<p class="ok">${phrase('အင်တာနက် သုံးနိုင်ပါပြီ။', 'You are connected.', mode)}</p><a class="secondary" href="#">${phrase('အခြေအနေ ကြည့်ရန်', 'Session status', mode)}</a>`,
      settings),
    failed: page('ချိတ်ဆက် မရပါ', 'Could not connect', failed, settings, {showWelcome: false}),
    status: page('Session အခြေအနေ', 'Session status',
      `<div class="status-grid"><div class="stat"><span class="stat-label">${phrase('ကျန်အချိန်', 'Time left', mode)}</span><span class="stat-value">1h12m</span></div>`
      + `<div class="stat"><span class="stat-label">${phrase('ကျန်ဒေတာ', 'Data left', mode)}</span><span class="stat-value">800.0MiB</span></div></div>`
      + `<form class="status-logout" action="#" method="post" onsubmit="return false"><button class="primary" type="submit">${phrase('ထွက်ရန်', 'Sign out', mode)}</button></form>`,
      settings, {showWelcome: false}),
    signedOut: page('ထွက်ပြီးပါပြီ', 'Signed out',
      `<p>${phrase('Session ပြီးဆုံးပါပြီ။', 'Your HotSpot session has ended.', mode)}</p><a class="secondary" href="#">${phrase('ပြန်ဝင်ရန်', 'Return to login', mode)}</a>`,
      settings, {showWelcome: false})
  };
}
