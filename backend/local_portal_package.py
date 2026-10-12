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


def _page(title: str, content: str, cfg: PortalConfig) -> str:
    # All owner-controlled text is escaped. Pages use only RouterOS-local
    # template variables and inline CSS; no cloud origin, CDN, script, or form
    # fallback to an unencrypted PAP submission is introduced.
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<title>{html.escape(title)} · {html.escape(cfg.business_name)}</title>'
        '<style>body{font:16px system-ui,sans-serif;max-width:34rem;margin:2rem auto;'
        'padding:1rem;color:#16382b;background:#f5f2e9}main{background:white;padding:1.25rem;'
        'border-radius:1rem}label,input,button{display:block;width:100%;box-sizing:border-box}input,button{'
        'font:inherit;padding:.8rem;margin:.4rem 0 1rem;min-height:44px}button{background:#176b50;'
        'color:white;border:0;border-radius:.5rem}p{white-space:pre-wrap}.error{color:#8b1e1e}</style>'
        f'</head><body><main><h1>{html.escape(cfg.business_name)}</h1>'
        f'<h2>{html.escape(title)}</h2><p>{html.escape(cfg.welcome)}</p>{content}'
        f'{"<p>" + html.escape(cfg.contact) + "</p>" if cfg.contact else ""}'
        f'{"<details><summary>Terms</summary><p>" + html.escape(cfg.terms) + "</p></details>" if cfg.terms else ""}'
        '</main></body></html>'
    )


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
        '<p class="error">If login fails, check the voucher and try again.</p>'
        '<form name="sendin" action="$(link-login-only)" method="post" style="display:none">'
        '<input name="username"><input name="password"><input name="dst" value="$(link-orig-esc)">'
        '<input name="popup" value="true"></form>'
        '<form name="login" action="$(link-login-only)" method="post" '
        'onsubmit="return doLogin()"><input type="hidden" name="dst" value="$(link-orig-esc)">'
        '<input type="hidden" name="popup" value="true">'
        '<label>Voucher / username<input name="username" autocomplete="username" required></label>'
        '<label>Password<input name="password" type="password" autocomplete="current-password" required></label>'
        '<button type="submit">Connect</button></form>'
        '<noscript>JavaScript is required for the router challenge login. No password was sent.</noscript>'
        '<script>function md5(s){var b=unescape(encodeURIComponent(s)),n=b.length,x=[],i,j;'
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
        'function doLogin(){if(!document.login.username.value||!document.login.password.value)return false;'
        'document.sendin.username.value=document.login.username.value;'
        'document.sendin.password.value=md5("$(chap-id)"+document.login.password.value+"$(chap-challenge)");'
        'document.sendin.submit();return false}</script>'
    )
    pages = {
        "login.html": _page("Wi-Fi access", login, cfg),
        "alogin.html": _page("Connected", '<p>Router reports that this session is connected.</p><a href="$(link-status)">Session status</a>', cfg),
        "flogin.html": _page("Login failed", '<p class="error">Check the voucher and try again.</p><a href="$(link-login-only)">Try again</a>', cfg),
        "status.html": _page("Session status", '<p>Time remaining: $(session-time-left)</p><p>Data remaining: $(remain-bytes-total)</p><form action="$(link-logout)" method="post"><button type="submit">Sign out</button></form>', cfg),
        "logout.html": _page("Signed out", '<p>The router has ended this HotSpot session.</p><a href="$(link-login-only)">Return to login</a>', cfg),
        "fstatus.html": _page("Session unavailable", '<p>No active local HotSpot session was reported.</p><a href="$(link-login-only)">Return to login</a>', cfg),
        "flogout.html": _page("Already signed out", '<p>The router reports no active HotSpot session.</p><a href="$(link-login-only)">Return to login</a>', cfg),
        "error.html": _page("Unable to continue", '<p class="error">The router could not continue this request.</p><a href="$(link-login-only)">Return to login</a>', cfg),
        "redirect.html": _page("Continue", '<a href="$(link-orig-esc)">Continue to your requested page</a>', cfg),
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
    }
    readme = (
        "MikroMagic local HotSpot content package\n\n"
        "Content-only review artifact. It has NOT been installed or verified on a router.\n"
        "No RouterOS commands, profile changes, credentials, remote assets, or cloud dependencies are included.\n"
        "The login template requires RouterOS HTTP-CHAP variables and a compatible HotSpot profile.\n"
        "Before any future deployment: inspect target/version/profile sharing/storage/file collisions, explain the exact diff, obtain owner confirmation, back up if required, install only into a new unique persistent directory, update only the selected profile directory if justified, then verify.\n"
        "Never overwrite existing portal files or change auth methods, firewall, DHCP, DNS, users, sessions, or unrelated HotSpot settings.\n"
        "Offline voucher authentication/enforcement, page compatibility, persistence and rollback require real-router acceptance.\n"
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
    if re.search(r"name=\"password\"[^>]*value=|http-pap|password.*type=.?text", login, re.I):
        raise ValueError("Unsafe password handling detected")
    return {"valid": True, "format": FORMAT, "file_count": len(FILES), "archive_bytes": len(payload), "installation_performed": False, "router_compatibility_verified": False}
