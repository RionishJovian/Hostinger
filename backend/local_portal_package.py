"""Deterministic local HotSpot content package; it never contacts or writes a router."""
from __future__ import annotations

import hashlib
import html
import io
import json
import re
import zipfile

from .schemas import PortalConfig

FORMAT = "mikromagic.local-hotspot-content.v1"
FILES = ("login.html", "alogin.html", "flogin.html", "status.html", "logout.html", "fstatus.html", "flogout.html", "error.html", "redirect.html", "api.json")
MAX_ARCHIVE_BYTES = 128_000
MAX_FILE_BYTES = 32_000

# Lantern Leaf guest UI — Midnight Studio graphite/emerald/silver, system fonts only, no CDN/remote assets.
# Compatible with RouterOS HotSpot servlet HTML size and offline CHAP login.
_CSS_BASE = (
    '*{box-sizing:border-box}html{color-scheme:dark}'
    'body{margin:0;min-height:100vh;font:16px/1.6 system-ui,-apple-system,"Segoe UI",Roboto,'
    '"Noto Sans Myanmar","Myanmar Text","Padauk",sans-serif;color:#E6E9ED;'
    'background:#0B1014 linear-gradient(180deg,#0B1014 0%,#121A1F 100%)}'
    '.wrap{min-height:100vh;display:flex;flex-direction:column;justify-content:center;padding:16px 16px 0;'
    'max-width:26rem;margin:0 auto}'
    '.top{display:flex;align-items:center;justify-content:space-between;gap:16px;margin:0 0 16px}'
    '.seal{width:48px;height:48px;border-radius:50%;display:flex;align-items:center;justify-content:center;'
    'font-weight:700;font-size:1.25rem;color:#E6E9ED;background:rgba(22,30,36,.78);'
    'border:1px solid rgba(200,205,212,.72);box-shadow:inset 0 0 0 3px #121A1F,0 0 0 1px rgba(200,205,212,.18)}'
    '.brand{font-size:1.7rem;font-weight:700;line-height:1.3;margin:0 0 8px;letter-spacing:0}'
    '.lead{margin:0 0 16px;color:#A8B0B8;font-size:.95rem;line-height:1.6}'
    '.page-title{margin:0 0 16px;color:#E6E9ED;font-size:1.15rem;line-height:1.6}'
    '.sheet{margin-top:16px;background:rgba(22,30,36,.78);border:1px solid rgba(200,205,212,.14);'
    'border-radius:20px;margin-bottom:calc(16px + env(safe-area-inset-bottom,0px));padding:20px 16px;'
    'box-shadow:0 12px 40px rgba(0,0,0,.35)}'
    'label{display:block;font-weight:600;margin:0 0 8px;color:#E6E9ED;font-size:.9rem}'
    'input,button.primary,button.secondary{display:block;width:100%;font:inherit;'
    'padding:12px 16px;margin:0 0 16px;min-height:52px;border-radius:12px}'
    'input{background:rgba(230,233,237,.06);color:#E6E9ED;border:1.5px solid rgba(200,205,212,.22)}'
    'input::placeholder{color:#7A838C}'
    'button.primary{background:linear-gradient(180deg,#1F8F68,#147A56);color:#E6E9ED;border:0;font-weight:700}'
    'button.primary:disabled{opacity:.65}'
    '#voucher{text-transform:uppercase;letter-spacing:.14em;text-align:center;font-size:1.25rem;font-weight:700}'
    '#voucher::placeholder{text-transform:none;letter-spacing:normal;font-weight:400;font-size:1rem}'
    '.hint{margin:-8px 0 16px;color:#7A838C;font-size:.8rem;line-height:1.6}'
    '.divider{display:flex;align-items:center;gap:8px;margin:16px 0;color:#A8B0B8;font-size:.85rem}'
    '.divider:before,.divider:after{content:"";flex:1;height:1px;background:rgba(200,205,212,.14)}'
    '.pay{margin:0 0 16px;padding:16px;border-radius:12px;background:rgba(230,233,237,.04);'
    'border:1px solid rgba(200,205,212,.14)}'
    '.pay h2{margin:0 0 8px;font-size:.95rem;color:#E6E9ED;font-weight:700}'
    '.pay .dest{margin:0 0 8px;font-size:1.05rem;font-weight:700;color:#E6E9ED;white-space:pre-wrap}'
    '.pay .instr{margin:0 0 8px;color:#A8B0B8;font-size:.88rem;line-height:1.6;white-space:pre-wrap}'
    '.pay .methods{margin:0;color:#7A838C;font-size:.78rem}'
    '.fair{margin:16px 0 0;color:#7A838C;font-size:.75rem;line-height:1.6}'
    'a{color:#5FD3A2}.secondary{display:flex;width:100%;min-height:44px;align-items:center;justify-content:center;'
    'padding:8px 16px;border:1px solid rgba(200,205,212,.22);border-radius:12px;color:#E6E9ED;'
    'background:rgba(230,233,237,.04);font-weight:700;text-align:center;text-decoration:none}'
    '.err{color:#E9856B;margin:0 0 16px}.ok{color:#5FD3A2;margin:0 0 16px}'
    '.status-grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}.stat{padding:16px;border-radius:12px;'
    'background:rgba(230,233,237,.04);border:1px solid rgba(200,205,212,.14)}'
    '.stat-label{display:block;color:#7A838C;font-size:.8rem}.stat-value{display:block;margin-top:8px;color:#E6E9ED;font-weight:700}'
    '.status-logout{margin-top:24px}.status-logout .primary{min-height:52px;margin-bottom:0}'
    '.mm{margin:16px 0 0;text-align:center;font-size:.72rem;color:#7A838C;letter-spacing:.08em}'
    '.mm:before{content:"";display:inline-block;width:.35rem;height:.35rem;border-radius:50%;'
    'background:#176B50;margin-right:.4rem;vertical-align:middle}'
)
_CSS_BOTH = (
    _CSS_BASE
    + '.langs{display:flex;gap:0;margin:0;border:1px solid rgba(200,205,212,.18);border-radius:12px;'
    + 'overflow:hidden;background:rgba(22,30,36,.78)}'
    + '.langs button{flex:1;min-width:4.2rem;padding:.45rem .65rem;font:inherit;border:0;'
    + 'background:transparent;color:#7A838C;min-height:44px}'
    + '.langs button[aria-pressed="true"]{background:rgba(200,205,212,.14);color:#E6E9ED;font-weight:700}'
    + '.my{display:none}html[lang="my"] .my{display:inline}html[lang="my"] .en{display:none}'
    + 'html[lang="en"] .en{display:inline}html[lang="en"] .my{display:none}'
    + 'html[lang="my"] .my-block{display:block}html[lang="my"] .en-block{display:none}'
    + 'html[lang="en"] .en-block{display:block}html[lang="en"] .my-block{display:none}'
)

_LANG_BAR = (
    '<div class="langs" role="group" aria-label="Language">'
    '<button type="button" data-lang="my" aria-pressed="true">မြန်မာ</button>'
    '<button type="button" data-lang="en" aria-pressed="false">English</button></div>'
)

_LANG_JS = (
    '<script>(function(){var h=document.documentElement,k="mm-hs-lang";'
    'function set(l){h.lang=l==="en"?"en":"my";try{sessionStorage.setItem(k,h.lang)}catch(e){}'
    'document.querySelectorAll(".langs button").forEach(function(b){'
    'b.setAttribute("aria-pressed",b.getAttribute("data-lang")===h.lang?"true":"false")});'
    'var v=document.getElementById("voucher");'
    'if(v){v.placeholder=h.lang==="en"?"Type your code":"ကုဒ် ရိုက်ထည့်ပါ"}}'
    'var s;try{s=sessionStorage.getItem(k)}catch(e){}'
    'set(s==="en"?"en":"my");'
    'document.querySelectorAll(".langs button").forEach(function(b){'
    'b.addEventListener("click",function(){set(b.getAttribute("data-lang"))})})})()</script>'
)


def _language_mode(cfg: PortalConfig) -> str:
    return cfg.language if cfg.language in ('en', 'my', 'both') else 'both'


def _guest_ui_label(mode: str) -> str:
    if mode == 'en':
        return 'lantern_leaf_english_only_single_voucher_field'
    if mode == 'my':
        return 'lantern_leaf_myanmar_only_single_voucher_field'
    return 'lantern_leaf_burmese_first_single_voucher_field'


def _local_text(value: str) -> str:
    """Escape owner text and strip URL schemes so the offline package stays link-free."""
    cleaned = re.sub(r'https?://', '', value or '', flags=re.I)
    return html.escape(cleaned)


def _seal_letter(business_name: str) -> str:
    name = (business_name or '?').strip() or '?'
    return html.escape(name[0])


def _default_welcome(mode: str) -> str:
    return _phrase(
        'ကုဒ်ထည့်ရုံနဲ့ Wi-Fi သုံးနိုင်ပါပြီ။',
        'Just enter your code to use the Wi-Fi.',
        mode,
        block=True,
    )


def _payment_card(cfg: PortalConfig, mode: str) -> str:
    if not cfg.direct_purchase:
        return ''
    destination = (cfg.payment_destination or '').strip()
    instructions = (cfg.payment_instructions or '').strip()
    methods = [m.strip() for m in (cfg.payment_methods or []) if m and m.strip()]
    if not destination or not instructions:
        return ''
    title = _phrase('ဘဏ် / ဝေါလက် အချက်အလက်', 'Bank / wallet details', mode, block=True)
    methods_line = ' · '.join(_local_text(m) for m in methods) if methods else ''
    return (
        f'<div class="divider">{_phrase("ကုဒ် မရှိသေးဘူးလား။", "No code yet?", mode)}</div>'
        f'<aside class="pay" aria-label="Payment">'
        f'<h2>{title}</h2>'
        f'<p class="dest">{_local_text(destination)}</p>'
        f'<p class="instr">{_local_text(instructions)}</p>'
        + (f'<p class="methods">{methods_line}</p>' if methods_line else '')
        + '</aside>'
    )


def _fair_use(cfg: PortalConfig, mode: str) -> str:
    if (cfg.terms or '').strip():
        text = _local_text(cfg.terms.strip())
        return f'<p class="fair">{text}</p>'
    return (
        f'<p class="fair">{_phrase("လူတိုင်း အဆင်ပြေအောင် သင့်တင့်စွာ သုံးပေးပါ။", "Please share the Wi-Fi fairly with everyone here.", mode)}</p>'
    )


# Inline MD5 for RouterOS HTTP-CHAP (must stay local; no PAP fallback).
_MD5_JS = (
    # RouterOS CHAP ids/challenges are raw bytes (octal escapes up to \377); hash each char as one byte, not UTF-8.
    'function md5(s){var b=s,n=b.length,x=[],i,j;'
    'for(i=0;i<n;i++)x[i]=b.charCodeAt(i)&255;x[n]=128;while(x.length%64!==56)x.push(0);'
    'var bits=n*8;for(i=0;i<8;i++)x.push(i<4?(bits>>> (8*i))&255:0);'
    'var a0=1732584193,b0=-271733879,c0=-1732584194,d0=271733878;'
    'var sh=[7,12,17,22,5,9,14,20,4,11,16,23,6,10,15,21];'
    'for(i=0;i<x.length;i+=64){var m=[];for(j=0;j<16;j++)m[j]=x[i+4*j]|x[i+4*j+1]<<8|x[i+4*j+2]<<16|x[i+4*j+3]<<24;'
    'var a=a0,bv=b0,c=c0,d=d0;for(j=0;j<64;j++){var f,g,k=Math.floor(Math.abs(Math.sin(j+1))*4294967296);'
    'if(j<16){f=(bv&c)|(~bv&d);g=j}else if(j<32){f=(d&bv)|(~d&c);g=(5*j+1)%16}'
    'else if(j<48){f=bv^c^d;g=(3*j+5)%16}else{f=c^(bv|~d);g=(7*j)%16}'
    'var q=(a+f+k+m[g])|0,r=sh[(j<16?0:j<32?1:j<48?2:3)*4+(j%4)];'
    'a=d;d=c;c=bv;bv=(bv+((q<<r)|(q>>>(32-r))))|0}a0=(a0+a)|0;b0=(b0+bv)|0;c0=(c0+c)|0;d0=(d0+d)|0}'
    'return [a0,b0,c0,d0].map(function(v){return [0,8,16,24].map(function(s){return ("0"+(v>>>s&255).toString(16)).slice(-2)}).join("")}).join("")}'
)


def _page(title_my: str, title_en: str, content: str, cfg: PortalConfig, *, login: bool = False, show_welcome: bool = True) -> str:
    # Owner-controlled text is escaped. Pages use only RouterOS-local template
    # variables and inline CSS/JS; no cloud origin, CDN, or PAP fallback.
    mode = _language_mode(cfg)
    brand = _local_text(cfg.business_name)
    welcome_raw = (cfg.welcome or '').strip()
    # Schema default is English; use Lantern Leaf bilingual job line until the owner customizes it.
    if not welcome_raw or welcome_raw == 'Welcome. Choose internet or media access.':
        welcome_html = _default_welcome(mode)
    else:
        welcome_html = _local_text(welcome_raw)
    seal = _seal_letter(cfg.business_name)
    if mode == 'en':
        lang, title = 'en', title_en
        lang_bar, lang_js, css = '', '', _CSS_BASE
        headings = f'<h1 class="page-title">{html.escape(title_en)}</h1>'
    elif mode == 'my':
        lang, title = 'my', title_my
        lang_bar, lang_js, css = '', '', _CSS_BASE
        headings = f'<h1 class="page-title">{html.escape(title_my)}</h1>'
    else:
        lang, title = 'my', title_my
        lang_bar, lang_js, css = _LANG_BAR, _LANG_JS, _CSS_BOTH
        headings = (
            f'<h1 class="my-block page-title">{html.escape(title_my)}</h1>'
            f'<h1 class="en-block page-title">{html.escape(title_en)}</h1>'
        )
    top = f'<div class="top"><div class="seal" aria-hidden="true">{seal}</div>{lang_bar}</div>' if lang_bar else f'<div class="top"><div class="seal" aria-hidden="true">{seal}</div></div>'
    return (
        f'<!doctype html><html lang="{lang}"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<meta name="color-scheme" content="dark">'
        f'<title>{html.escape(title)} · {brand}</title>'
        f'<style>{css}</style></head><body><div class="wrap">'
        f'{top}<p class="brand">{brand}</p>'
        + ('' if login else headings)
        + (f'<p class="lead">{welcome_html}</p>' if show_welcome else '')
        + f'<div class="sheet">{content}{_fair_use(cfg, mode)}'
        + lang_js
        + '<p class="mm">MikroMagic</p></div></div></body></html>'
    )


def _bilingual(my: str, en: str, *, block: bool = False) -> str:
    cls = 'my-block' if block else 'my'
    cls_en = 'en-block' if block else 'en'
    return f'<span class="{cls}">{my}</span><span class="{cls_en}">{en}</span>'


def _phrase(my: str, en: str, mode: str, *, block: bool = False) -> str:
    if mode == 'my':
        return my
    if mode == 'en':
        return en
    return _bilingual(my, en, block=block)


def _flogin_error_script(mode: str) -> str:
    """Emit RouterOS $(error) mapping for bilingual or single-language guest pages."""
    if mode == 'both':
        return (
            '<script>(function(){var el=document.getElementById("msg"),r=(el.getAttribute("data-raw")||"").toLowerCase(),my,en;'
            'if(/traffic|bytes|limit.*data|quota/.test(r)){my="ဒေတာ ကုန်သွားပါပြီ။";en="Data allowance used up."}'
            'else if(/uptime|time limit|session time|expired|lifetime/.test(r)){my="အချိန် ကုန်သွားပါပြီ။";en="Time allowance used up or expired."}'
            'else if(/no more sessions|simultaneous|shared-users|session limit|too many/.test(r)){my="စက် အရေအတွက် ပြည့်နေပါပြီ။";en="Too many devices are already connected."}'
            'else if(/disabled|not allowed/.test(r)){my="ဤကုဒ်ကို အသုံးပြု၍ မရပါ။";en="This code cannot be used."}'
            'else if(/invalid|password|unknown|not found|wrong/.test(r)||!r.trim()){my="ကုဒ် မှားနေပါသည်။";en="Wrong code. Check and try again."}'
            'else{my="ချိတ်ဆက်၍ မရပါ။ ထပ်ကြိုးစားပါ။";en="Could not connect. Try again."}'
            "el.innerHTML='<span class=\"my\">'+my+'</span><span class=\"en\">'+en+'</span>'})()</script>"
        )
    if mode == 'my':
        return (
            '<script>(function(){var el=document.getElementById("msg"),r=(el.getAttribute("data-raw")||"").toLowerCase(),msg;'
            'if(/traffic|bytes|limit.*data|quota/.test(r)){msg="ဒေတာ ကုန်သွားပါပြီ။"}'
            'else if(/uptime|time limit|session time|expired|lifetime/.test(r)){msg="အချိန် ကုန်သွားပါပြီ။"}'
            'else if(/no more sessions|simultaneous|shared-users|session limit|too many/.test(r)){msg="စက် အရေအတွက် ပြည့်နေပါပြီ။"}'
            'else if(/disabled|not allowed/.test(r)){msg="ဤကုဒ်ကို အသုံးပြု၍ မရပါ။"}'
            'else if(/invalid|password|unknown|not found|wrong/.test(r)||!r.trim()){msg="ကုဒ် မှားနေပါသည်။"}'
            'else{msg="ချိတ်ဆက်၍ မရပါ။ ထပ်ကြိုးစားပါ။"}'
            'el.textContent=msg})()</script>'
        )
    return (
        '<script>(function(){var el=document.getElementById("msg"),r=(el.getAttribute("data-raw")||"").toLowerCase(),msg;'
        'if(/traffic|bytes|limit.*data|quota/.test(r)){msg="Data allowance used up."}'
        'else if(/uptime|time limit|session time|expired|lifetime/.test(r)){msg="Time allowance used up or expired."}'
        'else if(/no more sessions|simultaneous|shared-users|session limit|too many/.test(r)){msg="Too many devices are already connected."}'
        'else if(/disabled|not allowed/.test(r)){msg="This code cannot be used."}'
        'else if(/invalid|password|unknown|not found|wrong/.test(r)||!r.trim()){msg="Wrong code. Check and try again."}'
        'else{msg="Could not connect. Try again."}'
        'el.textContent=msg})()</script>'
    )


def build_local_hotspot_package(settings: PortalConfig | dict, *, tenant_id: str, site_id: str | None, revision: int) -> bytes:
    """Build a reviewable RouterOS servlet-content archive, not an installer."""
    cfg = settings if isinstance(settings, PortalConfig) else PortalConfig.model_validate(settings)
    mode = _language_mode(cfg)
    if not tenant_id or len(tenant_id) > 80 or not re.fullmatch(r"[A-Za-z0-9_-]+", tenant_id):
        raise ValueError("A stable tenant identifier is required")
    if site_id is not None and (len(site_id) > 80 or not re.fullmatch(r"[A-Za-z0-9_-]+", site_id)):
        raise ValueError("A stable site identifier is required")
    if revision < 1:
        raise ValueError("A published portal revision is required")

    pay = _payment_card(cfg, mode)
    login = (
        '<form name="sendin" action="$(link-login-only)" method="post" style="display:none">'
        '<input name="username"><input name="password">'
        '<input name="dst" value="$(link-orig-esc)"><input name="popup" value="true"></form>'
        '<form name="login" action="$(link-login-only)" method="post" onsubmit="return doLogin()">'
        '<input type="hidden" name="dst" value="$(link-orig-esc)">'
        '<input type="hidden" name="popup" value="true">'
        f'<label>{_phrase("Wi-Fi ကုဒ်", "Wi-Fi code", mode)}'
        '<input name="username" id="voucher" autocomplete="username" required '
        'inputmode="text" autocapitalize="characters" spellcheck="false" '
        f'placeholder="{html.escape("Type your code" if mode == "en" else "ကုဒ် ရိုက်ထည့်ပါ")}" value="$(username)"></label>'
        f'<p class="hint">{_phrase("စာလုံးအကြီး/အသေး၊ (-) ပါ/မပါ ရိုက်နိုင်ပါတယ်။", "Capital or small letters, with or without the dash.", mode)}</p>'
        f'<button class="primary" type="submit">{_phrase("ချိတ်ဆက်ရန်", "Connect", mode)}</button></form>'
        + pay
        + '<noscript><p class="err">JavaScript is required for the router challenge login.</p></noscript>'
        '<script>' + _MD5_JS +
        # Codes are stored upper-case without spaces/hyphens; RouterOS user names are case-sensitive.
        'function norm(v){return (v||"").replace(/[\\s-]+/g,"").toUpperCase()}'
        'function doLogin(){var c=norm(document.getElementById("voucher").value);'
        'if(!c)return false;document.sendin.username.value=c;'
        'document.sendin.password.value=md5("$(chap-id)"+c+"$(chap-challenge)");'
        'document.sendin.submit();return false}'
        '(function(){var u=new URLSearchParams(location.search).get("username");'
        'var el=document.getElementById("voucher");'
        'if(u&&el&&(!el.value||el.value==="$(username)"))el.value=norm(u)})()'
        '</script>'
    )

    # Map common RouterOS HotSpot English $(error) strings to the configured guest language(s).
    flogin = (
        '<p class="err" id="msg" data-raw="$(error)"></p>'
        f'<a class="secondary" href="$(link-login-only)">{_phrase("ထပ်ကြိုးစားရန်", "Try again", mode)}</a>'
        + _flogin_error_script(mode)
    )

    pages = {
        "login.html": _page("Wi-Fi ဝင်ရန်", "Wi-Fi login", login, cfg, login=True),
        "alogin.html": _page(
            "ချိတ်ဆက်ပြီးပါပြီ", "Connected",
            f'<p class="ok">{_phrase("အင်တာနက် သုံးနိုင်ပါပြီ။", "You are connected.", mode)}</p>'
            f'<a class="secondary" href="$(link-status)">{_phrase("အခြေအနေ ကြည့်ရန်", "Session status", mode)}</a>',
            cfg,
        ),
        "flogin.html": _page("ချိတ်ဆက် မရပါ", "Could not connect", flogin, cfg, show_welcome=False),
        "status.html": _page(
            "Session အခြေအနေ", "Session status",
            f'<div class="status-grid"><div class="stat"><span class="stat-label">{_phrase("ကျန်အချိန်", "Time left", mode)}</span>'
            f'<span class="stat-value">$(session-time-left)</span></div>'
            f'<div class="stat"><span class="stat-label">{_phrase("ကျန်ဒေတာ", "Data left", mode)}</span>'
            f'<span class="stat-value">$(remain-bytes-total)</span></div></div>'
            f'<form class="status-logout" action="$(link-logout)" method="post"><button class="primary" type="submit">'
            f'{_phrase("ထွက်ရန်", "Sign out", mode)}</button></form>',
            cfg, show_welcome=False,
        ),
        "logout.html": _page(
            "ထွက်ပြီးပါပြီ", "Signed out",
            f'<p>{_phrase("Session ပြီးဆုံးပါပြီ။", "Your HotSpot session has ended.", mode)}</p>'
            f'<a class="secondary" href="$(link-login-only)">{_phrase("ပြန်ဝင်ရန်", "Return to login", mode)}</a>',
            cfg, show_welcome=False,
        ),
        "fstatus.html": _page(
            "Session မရှိပါ", "No session",
            f'<p class="err">{_phrase("လက်ရှိ HotSpot session မရှိပါ။", "No active HotSpot session.", mode)}</p>'
            f'<a class="secondary" href="$(link-login-only)">{_phrase("ပြန်ဝင်ရန်", "Return to login", mode)}</a>',
            cfg, show_welcome=False,
        ),
        "flogout.html": _page(
            "ထွက်ပြီးသား", "Already signed out",
            f'<p>{_phrase("Session မရှိတော့ပါ။", "There is no active HotSpot session.", mode)}</p>'
            f'<a class="secondary" href="$(link-login-only)">{_phrase("ပြန်ဝင်ရန်", "Return to login", mode)}</a>',
            cfg, show_welcome=False,
        ),
        "error.html": _page(
            "ဆက်မလုပ်နိုင်ပါ", "Unable to continue",
            f'<p class="err">{_phrase("Router က ဤတောင်းဆိုမှုကို ဆက်မလုပ်နိုင်ပါ။", "The router could not continue this request.", mode)}</p>'
            f'<a class="secondary" href="$(link-login-only)">{_phrase("ပြန်ဝင်ရန်", "Return to login", mode)}</a>',
            cfg, show_welcome=False,
        ),
        "redirect.html": _page(
            "ဆက်သွားရန်", "Continue",
            f'<a href="$(link-orig-esc)">{_phrase("တောင်းဆိုထားသော စာမျက်နှာသို့ ဆက်သွားရန်", "Continue to your requested page", mode)}</a>',
            cfg,
        ),
        "api.json": '{"captive":$(if logged-in == \'yes\')false$(else)true$(endif),"user-portal-url":"$(link-login-only)","can-extend-session":false}',
    }
    ui_note = {
        'both': 'Lantern Leaf · Burmese first with English toggle',
        'my': 'Lantern Leaf · Myanmar only (no language toggle)',
        'en': 'Lantern Leaf · English only (no language toggle)',
    }[mode]
    manifest = {
        "format": FORMAT,
        "scope": {"tenant_id": tenant_id, "site_id": site_id, "published_revision": revision},
        "files": {name: hashlib.sha256(content.encode("utf-8")).hexdigest() for name, content in pages.items()},
        "router_configuration_included": False,
        "installation_performed": False,
        "router_compatibility_verified": False,
        "authentication": "RouterOS local HotSpot HTTP-CHAP template; no PAP fallback",
        "guest_language": mode,
        "guest_ui": _guest_ui_label(mode),
        "theme": "lantern_leaf",
        "payment_card": bool(pay),
    }
    readme = (
        "MikroMagic local HotSpot content package\n\n"
        "Content-only review artifact. It has NOT been installed or verified on a router.\n"
        "No RouterOS commands, profile changes, credentials, remote assets, or cloud dependencies are included.\n"
        f"Guest UI: {ui_note}; Lantern Leaf theme; one voucher field (CHAP username=password); "
        "optional bank/wallet card from published portal payment fields; QR username= prefill.\n"
        "The login template requires RouterOS HTTP-CHAP variables and a compatible HotSpot profile.\n"
        "Before any future deployment: inspect target/version/profile sharing/storage/file collisions, explain the exact diff, obtain owner confirmation, back up if required, install only into a new unique persistent directory, update only the selected profile directory if justified, then verify.\n"
        "Never overwrite existing portal files or change auth methods, firewall, DHCP, DNS, users, sessions, or unrelated HotSpot settings.\n"
        "Offline voucher authentication/enforcement, page compatibility, persistence and rollback require real-router acceptance.\n"
        "First Customer Test on a real phone is a separate step.\n"
    )
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        def write(name, content):
            info = zipfile.ZipInfo(name, date_time=(2020, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, content)
        for name in FILES:
            write(name, pages[name])
        write("portal-manifest.json", json.dumps(manifest, sort_keys=True, separators=(",", ":")))
        write("README.txt", readme)
    payload = out.getvalue()
    validate_local_hotspot_package(payload)
    return payload


def package_install_files(payload: bytes) -> dict[str, str]:
    """Return UTF-8 servlet files to install after validating the archive."""
    validate_local_hotspot_package(payload)
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        return {name: archive.read(name).decode("utf-8") for name in FILES}


def validate_local_hotspot_package(payload: bytes) -> dict:
    """Fail-closed structural/content validation for generated or supplied archives."""
    if not isinstance(payload, bytes) or len(payload) > MAX_ARCHIVE_BYTES:
        raise ValueError("Portal package is missing or exceeds the archive size limit")
    try:
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            names = archive.namelist()
            expected = set(FILES) | {"portal-manifest.json", "README.txt"}
            if len(names) != len(set(names)) or set(names) != expected:
                raise ValueError("Unexpected, duplicate, or missing package files")
            if any(name.startswith(("/", "\\")) or ".." in name.split("/") for name in names):
                raise ValueError("Unsafe package path")
            data = {name: archive.read(name) for name in names}
    except (zipfile.BadZipFile, OSError, KeyError) as exc:
        raise ValueError("Invalid portal package archive") from exc
    if any(len(content) > MAX_FILE_BYTES for content in data.values()):
        raise ValueError("Portal package file exceeds the size limit")
    try:
        manifest = json.loads(data["portal-manifest.json"])
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Invalid portal package manifest") from exc
    if manifest.get("format") != FORMAT or manifest.get("router_configuration_included") is not False:
        raise ValueError("Unsupported or unsafe package manifest")
    scope = manifest.get("scope", {})
    if not isinstance(scope.get("tenant_id"), str) or scope.get("site_id") is not None and not isinstance(scope.get("site_id"), str) or not isinstance(scope.get("published_revision"), int) or scope['published_revision'] < 1:
        raise ValueError("Package scope is incomplete or invalid")
    if set(manifest.get("files", {})) != set(FILES):
        raise ValueError("Manifest file list does not match the package")
    for name in FILES:
        body = data[name]
        text = body.decode("utf-8")
        if hashlib.sha256(body).hexdigest() != manifest["files"][name]:
            raise ValueError("Package file checksum mismatch")
        if re.search(r"https?://|<script[^>]+src=|\b(fetch|XMLHttpRequest|eval)\s*\(", text, re.I):
            raise ValueError("Remote or dynamic code is not permitted in local portal files")
        if "$(link-" not in text:
            raise ValueError("RouterOS-local servlet variables are required")
    login = data["login.html"].decode("utf-8")
    if "$(chap-id)" not in login or "$(chap-challenge)" not in login or "md5(" not in login or "method=\"post\"" not in login:
        raise ValueError("Login page must use the local RouterOS CHAP challenge flow")
    if 'id="voucher"' not in login and "id='voucher'" not in login:
        raise ValueError("Guest login must offer a voucher field")
    guest_language = manifest.get("guest_language")
    if guest_language not in ('en', 'my', 'both'):
        # Older packages defaulted to Burmese-first bilingual UI.
        guest_language = 'both' if "data-lang" in login else None
    if guest_language == 'both':
        if 'lang="my"' not in login and "lang='my'" not in login:
            raise ValueError("Bilingual guest login must default to Burmese")
        if "data-lang" not in login:
            raise ValueError("Bilingual guest login must offer a language choice")
    elif guest_language == 'my':
        if 'lang="my"' not in login and "lang='my'" not in login:
            raise ValueError("Myanmar-only guest login must use Burmese")
        if "data-lang" in login:
            raise ValueError("Myanmar-only guest login must not include a language toggle")
    elif guest_language == 'en':
        if 'lang="en"' not in login and "lang='en'" not in login:
            raise ValueError("English-only guest login must use English")
        if "data-lang" in login:
            raise ValueError("English-only guest login must not include a language toggle")
    else:
        raise ValueError("Guest login language mode is missing or invalid")
    if re.search(r"name=\"password\"[^>]*value=|http-pap|password.*type=.?text", login, re.I):
        raise ValueError("Unsafe password handling detected")
    # Visible password field must not appear; CHAP uses the hidden sendin form only.
    if re.search(r'<input[^>]*name="password"[^>]*type="password"', login, re.I):
        raise ValueError("Guest login must use a single voucher field, not a separate password prompt")
    flogin = data["flogin.html"].decode("utf-8")
    if "$(error)" not in flogin:
        raise ValueError("Failed-login page must surface the RouterOS error for guest messaging")
    return {"valid": True, "format": FORMAT, "file_count": len(FILES), "archive_bytes": len(payload), "installation_performed": False, "router_compatibility_verified": False, "guest_language": guest_language}
