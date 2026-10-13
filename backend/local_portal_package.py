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

# Compact bilingual UI (Burmese first). No remote fonts/CDN; system stack only.
_CSS = (
    'body{font:16px/1.45 system-ui,sans-serif;margin:0;min-height:100vh;color:#14261f;'
    'background:linear-gradient(160deg,#e8f3ee 0%,#f7f4ec 55%,#efe8d8 100%)}'
    'main{max-width:22rem;margin:0 auto;padding:1.25rem 1rem 2rem}'
    '.brand{font-size:1.35rem;font-weight:700;letter-spacing:-.02em;margin:0 0 .35rem}'
    '.lead{margin:0 0 1rem;color:#3a5348;font-size:.95rem}'
    '.langs{display:flex;gap:.5rem;margin:0 0 1rem}'
    '.langs button{flex:0;min-width:4.5rem;padding:.45rem .7rem;font:inherit;border:1px solid #9bb5a8;'
    'background:#fff;border-radius:.45rem;color:#16382b;min-height:40px}'
    '.langs button[aria-pressed="true"]{background:#176b50;border-color:#176b50;color:#fff}'
    'label{display:block;font-weight:600;margin:.2rem 0}'
    'input,button.primary{display:block;width:100%;box-sizing:border-box;font:inherit;'
    'padding:.85rem;margin:.35rem 0 1rem;min-height:48px;border-radius:.55rem;border:1px solid #b7c9bf}'
    'button.primary{background:#176b50;color:#fff;border:0;font-weight:600}'
    '#voucher{text-transform:uppercase;letter-spacing:.14em;text-align:center;font-size:1.3rem;font-weight:600}'
    '#voucher::placeholder{text-transform:none;letter-spacing:normal;font-weight:400;font-size:1rem}'
    'a{color:#176b50}.err{color:#8b1e1e;margin:0 0 1rem}.ok{color:#176b50;margin:0 0 1rem}'
    '.mm{margin:2rem 0 0;text-align:center;font-size:.78rem;color:#5d7368;letter-spacing:.04em}'
    '.my{display:none}html[lang="my"] .my{display:inline}html[lang="my"] .en{display:none}'
    'html[lang="en"] .en{display:inline}html[lang="en"] .my{display:none}'
    'html[lang="my"] .my-block{display:block}html[lang="my"] .en-block{display:none}'
    'html[lang="en"] .en-block{display:block}html[lang="en"] .my-block{display:none}'
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
    'b.setAttribute("aria-pressed",b.getAttribute("data-lang")===h.lang?"true":"false")})}'
    'var s;try{s=sessionStorage.getItem(k)}catch(e){}'
    'set(s==="en"?"en":"my");'
    'document.querySelectorAll(".langs button").forEach(function(b){'
    'b.addEventListener("click",function(){set(b.getAttribute("data-lang"))})})})()</script>'
)

# Inline MD5 for RouterOS HTTP-CHAP (must stay local; no PAP fallback).
_MD5_JS = (
    'function md5(s){var b=unescape(encodeURIComponent(s)),n=b.length,x=[],i,j;'
    'for(i=0;i<n;i++)x[i]=b.charCodeAt(i);x[n]=128;while(x.length%64!==56)x.push(0);'
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


def _page(title_my: str, title_en: str, content: str, cfg: PortalConfig) -> str:
    # Owner-controlled text is escaped. Pages use only RouterOS-local template
    # variables and inline CSS/JS; no cloud origin, CDN, or PAP fallback.
    brand = html.escape(cfg.business_name)
    welcome = html.escape(cfg.welcome) if cfg.welcome else ''
    return (
        '<!doctype html><html lang="my"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<title>{html.escape(title_my)} · {brand}</title>'
        f'<style>{_CSS}</style></head><body><main>'
        f'{_LANG_BAR}<p class="brand">{brand}</p>'
        f'<h1 class="my-block" style="font-size:1.1rem;margin:0 0 .5rem">{html.escape(title_my)}</h1>'
        f'<h1 class="en-block" style="font-size:1.1rem;margin:0 0 .5rem">{html.escape(title_en)}</h1>'
        + (f'<p class="lead">{welcome}</p>' if welcome else '')
        + content
        + _LANG_JS
        + '<p class="mm">MikroMagic</p></main></body></html>'
    )


def _bilingual(my: str, en: str, *, block: bool = False) -> str:
    cls = 'my-block' if block else 'my'
    cls_en = 'en-block' if block else 'en'
    return f'<span class="{cls}">{my}</span><span class="{cls_en}">{en}</span>'


def build_local_hotspot_package(settings: PortalConfig | dict, *, tenant_id: str, site_id: str | None, revision: int) -> bytes:
    """Build a reviewable RouterOS servlet-content archive, not an installer."""
    cfg = settings if isinstance(settings, PortalConfig) else PortalConfig.model_validate(settings)
    if not tenant_id or len(tenant_id) > 80 or not re.fullmatch(r"[A-Za-z0-9_-]+", tenant_id):
        raise ValueError("A stable tenant identifier is required")
    if site_id is not None and (len(site_id) > 80 or not re.fullmatch(r"[A-Za-z0-9_-]+", site_id)):
        raise ValueError("A stable site identifier is required")
    if revision < 1:
        raise ValueError("A published portal revision is required")

    login = (
        '<form name="sendin" action="$(link-login-only)" method="post" style="display:none">'
        '<input name="username"><input name="password">'
        '<input name="dst" value="$(link-orig-esc)"><input name="popup" value="true"></form>'
        '<form name="login" action="$(link-login-only)" method="post" onsubmit="return doLogin()">'
        '<input type="hidden" name="dst" value="$(link-orig-esc)">'
        '<input type="hidden" name="popup" value="true">'
        f'<label>{_bilingual("Voucher ကုဒ်", "Voucher code")}'
        '<input name="username" id="voucher" autocomplete="username" required '
        'inputmode="text" autocapitalize="characters" spellcheck="false" '
        'placeholder="$(username)" value="$(username)"></label>'
        f'<button class="primary" type="submit">{_bilingual("ချိတ်ဆက်ရန်", "Connect")}</button></form>'
        f'<p class="lead">{_bilingual("ကုဒ်ကို ရိုက်ထည့်ပါ။ QR ဖြင့် ဖွင့်ထားလျှင် ကုဒ် ဖြည့်ပြီး ဖြစ်နိုင်သည်။", "Enter your code. A QR link may fill it for you.")}</p>'
        '<noscript><p class="err">JavaScript is required for the router challenge login.</p></noscript>'
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

    # Map common RouterOS HotSpot English $(error) strings to plain Burmese/English.
    flogin = (
        '<p class="err" id="msg" data-raw="$(error)"></p>'
        f'<a href="$(link-login-only)">{_bilingual("ထပ်ကြိုးစားရန်", "Try again")}</a>'
        '<script>(function(){var el=document.getElementById("msg"),r=(el.getAttribute("data-raw")||"").toLowerCase(),my,en;'
        'if(/traffic|bytes|limit.*data|quota/.test(r)){my="ဒေတာ ကုန်သွားပါပြီ။";en="Data allowance used up."}'
        'else if(/uptime|time limit|session time|expired|lifetime/.test(r)){my="အချိန် ကုန်သွားပါပြီ။";en="Time allowance used up or expired."}'
        'else if(/no more sessions|simultaneous|shared-users|session limit|too many/.test(r)){my="စက် အရေအတွက် ပြည့်နေပါပြီ။";en="Too many devices are already connected."}'
        'else if(/disabled|not allowed/.test(r)){my="ဤကုဒ်ကို အသုံးပြု၍ မရပါ။";en="This code cannot be used."}'
        'else if(/invalid|password|unknown|not found|wrong/.test(r)||!r.trim()){my="ကုဒ် မှားနေပါသည်။";en="Wrong code. Check and try again."}'
        'else{my="ချိတ်ဆက်၍ မရပါ။ ထပ်ကြိုးစားပါ။";en="Could not connect. Try again."}'
        'el.innerHTML=\'<span class="my">\'+my+\'</span><span class="en">\'+en+\'</span>\'})()</script>'
    )

    pages = {
        "login.html": _page("Wi-Fi ဝင်ရန်", "Wi-Fi login", login, cfg),
        "alogin.html": _page(
            "ချိတ်ဆက်ပြီးပါပြီ", "Connected",
            f'<p class="ok">{_bilingual("အင်တာနက် သုံးနိုင်ပါပြီ။", "You are connected.")}</p>'
            f'<a href="$(link-status)">{_bilingual("အခြေအနေ ကြည့်ရန်", "Session status")}</a>',
            cfg,
        ),
        "flogin.html": _page("ချိတ်ဆက် မရပါ", "Could not connect", flogin, cfg),
        "status.html": _page(
            "Session အခြေအနေ", "Session status",
            f'<p>{_bilingual("ကျန်အချိန်", "Time left")}: $(session-time-left)</p>'
            f'<p>{_bilingual("ကျန်ဒေတာ", "Data left")}: $(remain-bytes-total)</p>'
            f'<form action="$(link-logout)" method="post"><button class="primary" type="submit">'
            f'{_bilingual("ထွက်ရန်", "Sign out")}</button></form>',
            cfg,
        ),
        "logout.html": _page(
            "ထွက်ပြီးပါပြီ", "Signed out",
            f'<p>{_bilingual("Session ပြီးဆုံးပါပြီ။", "Your HotSpot session has ended.")}</p>'
            f'<a href="$(link-login-only)">{_bilingual("ပြန်ဝင်ရန်", "Return to login")}</a>',
            cfg,
        ),
        "fstatus.html": _page(
            "Session မရှိပါ", "No session",
            f'<p class="err">{_bilingual("လက်ရှိ HotSpot session မရှိပါ။", "No active HotSpot session.")}</p>'
            f'<a href="$(link-login-only)">{_bilingual("ပြန်ဝင်ရန်", "Return to login")}</a>',
            cfg,
        ),
        "flogout.html": _page(
            "ထွက်ပြီးသား", "Already signed out",
            f'<p>{_bilingual("Session မရှိတော့ပါ။", "There is no active HotSpot session.")}</p>'
            f'<a href="$(link-login-only)">{_bilingual("ပြန်ဝင်ရန်", "Return to login")}</a>',
            cfg,
        ),
        "error.html": _page(
            "ဆက်မလုပ်နိုင်ပါ", "Unable to continue",
            f'<p class="err">{_bilingual("Router က ဤတောင်းဆိုမှုကို ဆက်မလုပ်နိုင်ပါ။", "The router could not continue this request.")}</p>'
            f'<a href="$(link-login-only)">{_bilingual("ပြန်ဝင်ရန်", "Return to login")}</a>',
            cfg,
        ),
        "redirect.html": _page(
            "ဆက်သွားရန်", "Continue",
            f'<a href="$(link-orig-esc)">{_bilingual("တောင်းဆိုထားသော စာမျက်နှာသို့ ဆက်သွားရန်", "Continue to your requested page")}</a>',
            cfg,
        ),
        "api.json": '{"captive":$(if logged-in == \'yes\')false$(else)true$(endif),"user-portal-url":"$(link-login-only)","can-extend-session":false}',
    }
    manifest = {
        "format": FORMAT,
        "scope": {"tenant_id": tenant_id, "site_id": site_id, "published_revision": revision},
        "files": {name: hashlib.sha256(content.encode("utf-8")).hexdigest() for name, content in pages.items()},
        "router_configuration_included": False,
        "installation_performed": False,
        "router_compatibility_verified": False,
        "authentication": "RouterOS local HotSpot HTTP-CHAP template; no PAP fallback",
        "guest_ui": "burmese_first_single_voucher_field",
    }
    readme = (
        "MikroMagic local HotSpot content package\n\n"
        "Content-only review artifact. It has NOT been installed or verified on a router.\n"
        "No RouterOS commands, profile changes, credentials, remote assets, or cloud dependencies are included.\n"
        "Guest UI: Burmese first with English toggle; one voucher field (CHAP username=password); QR username= prefill.\n"
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
    if 'lang="my"' not in login and "lang='my'" not in login:
        raise ValueError("Guest login must default to Burmese")
    if "data-lang" not in login or "Voucher" not in login:
        raise ValueError("Guest login must offer language choice and a voucher field")
    if re.search(r"name=\"password\"[^>]*value=|http-pap|password.*type=.?text", login, re.I):
        raise ValueError("Unsafe password handling detected")
    # Visible password field must not appear; CHAP uses the hidden sendin form only.
    if re.search(r'<input[^>]*name="password"[^>]*type="password"', login, re.I):
        raise ValueError("Guest login must use a single voucher field, not a separate password prompt")
    flogin = data["flogin.html"].decode("utf-8")
    if "$(error)" not in flogin:
        raise ValueError("Failed-login page must surface the RouterOS error for guest messaging")
    return {"valid": True, "format": FORMAT, "file_count": len(FILES), "archive_bytes": len(payload), "installation_performed": False, "router_compatibility_verified": False}
