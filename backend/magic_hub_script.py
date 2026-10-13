"""Generate the one-paste RouterOS 7 Magic Hub enrollment script.

The script detects facts at runtime (never assumes ether1/wifi1/model), never
emits admin-password commands, and embeds only a short-lived enrollment token
(not Hub-admin secrets or router logins). Certificate check uses RouterOS
built-in anchors with yes-without-crl (CRL not checked — documented risk).
"""
from __future__ import annotations
import re

PREFERRED_LISTEN_PORT = 13239
TUNNEL_MTU = 1280
# RouterOS 7 trusts public CAs for fetch; CRL retrieval often fails on captive/edge WANs.
# yes-without-crl still verifies the chain against built-in anchors (safer than no).
FETCH_CERT_MODE = 'yes-without-crl'

FORBIDDEN_IN_VISIBLE_SCRIPT = re.compile(
    r'(/user\s+set\s+admin|/password|/user\s+add\s+name=admin|hub_private|agent.token|MIKROMAGIC_HUB_AGENT)',
    re.I,
)


def assert_script_safe(script: str, *, token: str | None = None) -> None:
    if FORBIDDEN_IN_VISIBLE_SCRIPT.search(script):
        raise ValueError('Generated script contained forbidden admin/secret material')
    # Hardcoded classic defconf names must not appear as assumed uplinks.
    if re.search(r'\bether1\b', script) or re.search(r'\bwifi1\b', script):
        raise ValueError('Generated script hardcodes ether1/wifi1')
    if token and token not in script:
        raise ValueError('Enrollment token missing from script')


def format_enroll_response(fields: dict[str, str]) -> str:
    """Plain key=value lines for RouterOS 7 `:parse` / line splitting (widely available)."""
    lines = []
    for key in (
        'status', 'hub_public_key', 'endpoint', 'endpoint_port', 'hub_address',
        'router_address', 'keepalive', 'interface', 'listen_port',
        'enroll_user', 'enroll_password', 'certificate', 'error',
    ):
        if key in fields and fields[key] is not None:
            lines.append(f'{key}={fields[key]}')
    return '\n'.join(lines) + '\n'


def parse_enroll_request(body: str) -> dict[str, str]:
    """Parse router POST body (form-urlencoded or key=value lines / &-joined)."""
    text = (body or '').strip()
    out: dict[str, str] = {}
    if not text:
        return out
    # Support both newline and & separators; values may be URL-encoded.
    from urllib.parse import unquote_plus
    chunks = re.split(r'[&\n]', text.replace('\r\n', '\n').replace('\r', '\n'))
    for chunk in chunks:
        chunk = chunk.strip()
        if not chunk or '=' not in chunk:
            continue
        key, _, value = chunk.partition('=')
        key = unquote_plus(key.strip()).lower()
        value = unquote_plus(value.strip())
        if key:
            out[key] = value
    return out


def rollback_script(iface_hint: str = 'mm-*') -> str:
    """Owner-visible rollback: removes only MikroMagic enroll objects by comment/name prefix."""
    return f'''{{
:put "MikroMagic rollback: removing only objects tagged MikroMagic enroll / management"
:do {{ /user remove [find where comment~"MikroMagic" and name~"^mm-"] }} on-error={{}}
:do {{ /user group remove [find where name="mm-monitor" or name="mm-safechange"] }} on-error={{}}
:do {{ /ip firewall filter remove [find where comment~"MikroMagic"] }} on-error={{}}
:do {{ /ip service set www-ssl disabled=yes certificate=none address="" }} on-error={{}}
:do {{ /certificate remove [find where name~"^mm-mgmt-"] }} on-error={{}}
:do {{ /ip route remove [find where comment~"MikroMagic"] }} on-error={{}}
:do {{ /ip address remove [find where comment~"MikroMagic"] }} on-error={{}}
:do {{ /interface wireguard peers remove [find where comment~"MikroMagic"] }} on-error={{}}
:do {{ /interface wireguard remove [find where comment~"MikroMagic" or name~"^mm-"] }} on-error={{}}
:do {{ /ip dhcp-client remove [find where comment~"MikroMagic"] }} on-error={{}}
:do {{ /ip firewall nat remove [find where comment~"MikroMagic"] }} on-error={{}}
:put "Rollback finished. Review the router if customer WAN was changed outside MikroMagic."
}}'''


def generate_enroll_script(*, token: str, base_url: str, router_id: str, hub_endpoint: str) -> str:
    """Build the one-paste script. `token` is the only secret embedded (short-lived)."""
    base = base_url.rstrip('/')
    id8 = router_id[:8]
    enroll_url = f'{base}/v1/magic-connect/hub-enroll/{token}'
    status_url = f'{base}/v1/magic-connect/hub-enroll/{token}/progress'
    # Escape for RouterOS double-quoted strings
    def q(s: str) -> str:
        return s.replace('\\', '\\\\').replace('"', '\\"')

    script = f'''{{
:local mmToken "{q(token)}"
:local mmBase "{q(base)}"
:local mmEnrollUrl "{q(enroll_url)}"
:local mmStatusUrl "{q(status_url)}"
:local mmId8 "{q(id8)}"
:local mmHubHost "{q(hub_endpoint)}"
:local mmComment "MikroMagic enroll"
:local mmIface ""
:local mmPort {PREFERRED_LISTEN_PORT}
:local mmAdded [/system script environment find where name="mm-unused"]
:set mmAdded [:toarray ""]

:local mmFail do={{
  :put ("MM-FAIL: " . $1)
  :do {{ /tool fetch url=($mmStatusUrl . "?phase=failed&message=" . $1) check-certificate={FETCH_CERT_MODE} keep-result=no }} on-error={{}}
  :do {{ /user remove [find where comment=$mmComment] }} on-error={{}}
  :do {{ /ip firewall filter remove [find where comment=$mmComment] }} on-error={{}}
  :do {{ /ip service set www-ssl disabled=yes certificate=none address="" }} on-error={{}}
  :do {{ /certificate remove [find where name=("mm-mgmt-" . $mmId8)] }} on-error={{}}
  :do {{ /ip route remove [find where comment=$mmComment] }} on-error={{}}
  :do {{ /ip address remove [find where comment=$mmComment] }} on-error={{}}
  :do {{ /interface wireguard peers remove [find where comment=$mmComment] }} on-error={{}}
  :do {{ /interface wireguard remove [find where comment=$mmComment] }} on-error={{}}
  :do {{ /ip dhcp-client remove [find where comment=$mmComment] }} on-error={{}}
  :do {{ /ip firewall nat remove [find where comment=$mmComment] }} on-error={{}}
  :error message=$1
}}

:put "MM: Checking RouterOS version and WireGuard"
:local mmVer [/system resource get version]
:local mmMajor [:pick $mmVer 0 [:find $mmVer "."]]
:if ([:typeof $mmMajor] = "nil" || $mmMajor < "7") do={{ [$mmFail ("Upgrade RouterOS to v7 (have " . $mmVer . ")")] }}
:do {{ :local mmWgTest [/interface wireguard find] }} on-error={{ [$mmFail "Upgrade RouterOS to v7 with WireGuard"] }}

:put "MM: Checking internet"
:local mmOnline false
:do {{
  :local mmResolve [:resolve $mmHubHost]
  :if ([:len $mmResolve] > 0) do={{ :set mmOnline true }}
}} on-error={{ :set mmOnline false }}
:if (!$mmOnline) do={{
  :put "MM: No DNS yet — trying DHCP on unused Ethernet links (not bridge ports, no IP)"
  :foreach mmIfId in=[/interface find where type="ether" and running=yes and disabled=no] do={{
    :local mmIfName [/interface get $mmIfId name]
    :local mmIsBridge false
    :do {{
      :if ([:len [/interface bridge port find where interface=$mmIfName]] > 0) do={{ :set mmIsBridge true }}
    }} on-error={{}}
    :local mmHasIp false
    :do {{
      :if ([:len [/ip address find where interface=$mmIfName]] > 0) do={{ :set mmHasIp true }}
    }} on-error={{}}
    :if (!$mmIsBridge && !$mmHasIp) do={{
      :do {{
        :if ([:len [/ip dhcp-client find where interface=$mmIfName]] = 0) do={{
          /ip dhcp-client add interface=$mmIfName disabled=no add-default-route=yes use-peer-dns=yes comment=$mmComment
          :put ("MM: DHCP client added on " . $mmIfName)
        }}
      }} on-error={{}}
    }}
  }}
  :delay 8s
  :do {{
    :local mmResolve2 [:resolve $mmHubHost]
    :if ([:len $mmResolve2] > 0) do={{ :set mmOnline true }}
  }} on-error={{ :set mmOnline false }}
}}
:if (!$mmOnline) do={{
  [$mmFail "Connect the router to the internet first, e.g. PPPoE/static"]
}}

:put "MM: Creating WireGuard interface"
:local mmBaseName ("mm-" . $mmId8)
:set mmIface $mmBaseName
:local mmN 2
:while ([:len [/interface find where name=$mmIface]] > 0) do={{
  :set mmIface ($mmBaseName . "-" . $mmN)
  :set mmN ($mmN + 1)
  :if ($mmN > 50) do={{ [$mmFail "No free WireGuard interface name"] }}
}}
:local mmUsedPort false
:do {{
  :foreach mmW in=[/interface wireguard find] do={{
    :if ([/interface wireguard get $mmW listen-port] = $mmPort) do={{ :set mmUsedPort true }}
  }}
}} on-error={{}}
:if ($mmUsedPort) do={{
  :set mmPort ($mmPort + 1)
  :local mmTries 0
  :local mmStill true
  :while ($mmStill && $mmTries < 200) do={{
    :set mmStill false
    :do {{
      :foreach mmW2 in=[/interface wireguard find] do={{
        :if ([/interface wireguard get $mmW2 listen-port] = $mmPort) do={{
          :set mmStill true
          :set mmPort ($mmPort + 1)
        }}
      }}
    }} on-error={{}}
    :set mmTries ($mmTries + 1)
  }}
}}
/interface wireguard add name=$mmIface listen-port=$mmPort mtu={TUNNEL_MTU} comment=$mmComment
:local mmPub [/interface wireguard get [find where name=$mmIface] public-key]
:put ("MM: Interface " . $mmIface . " public-key ready")

:put "MM: Collecting router facts"
:local mmBoard [/system resource get board-name]
:local mmArch [/system resource get architecture-name]
:local mmSerial ""
:do {{ :set mmSerial [/system routerboard get serial-number] }} on-error={{ :set mmSerial "" }}
:local mmIfCount [:len [/interface find]]
:local mmInputLen 0
:do {{ :set mmInputLen [:len [/ip firewall filter find where chain=input]] }} on-error={{ :set mmInputLen 0 }}

:put "MM: Reporting to MikroMagic"
:local mmData ("public_key=" . $mmPub . "&board=" . $mmBoard . "&version=" . $mmVer . "&architecture=" . $mmArch . "&serial=" . $mmSerial . "&interface=" . $mmIface . "&listen_port=" . $mmPort . "&input_rules=" . $mmInputLen . "&interface_count=" . $mmIfCount)
:do {{
  /tool fetch url=$mmEnrollUrl http-method=post http-data=$mmData check-certificate={FETCH_CERT_MODE} dst-path=("mm-enroll-" . $mmId8 . ".txt")
}} on-error={{
  [$mmFail "Could not reach MikroMagic enroll URL (HTTPS fetch failed)"]
}}
:local mmReply [/file get [find where name=("mm-enroll-" . $mmId8 . ".txt")] contents]
:do {{ /file remove [find where name=("mm-enroll-" . $mmId8 . ".txt")] }} on-error={{}}
:if ([:typeof $mmReply] = "nil" || [:len $mmReply] < 10) do={{ [$mmFail "Empty enroll reply from MikroMagic"] }}
:if ([:find $mmReply "status=error"] >= 0) do={{
  :local mmErr "enroll rejected"
  :local mmPos [:find $mmReply "error="]
  :if ([:typeof $mmPos] != "nil") do={{ :set mmErr [:pick $mmReply ($mmPos + 6) [:len $mmReply]] }}
  [$mmFail $mmErr]
}}
:if ([:find $mmReply "status=ok"] < 0) do={{ [$mmFail "Unexpected enroll reply"] }}

:local mmGet do={{
  :local mmKey ($1 . "=")
  :local mmPos [:find $mmReply $mmKey]
  :if ([:typeof $mmPos] = "nil") do={{ :return "" }}
  :local mmStart ($mmPos + [:len $mmKey])
  :local mmRest [:pick $mmReply $mmStart [:len $mmReply]]
  :local mmEnd [:find $mmRest "\\n"]
  :if ([:typeof $mmEnd] = "nil") do={{ :set mmEnd [:find $mmRest "&"] }}
  :if ([:typeof $mmEnd] = "nil") do={{ :return $mmRest }}
  :return [:pick $mmRest 0 $mmEnd]
}}
:local mmHubKey [$mmGet "hub_public_key"]
:local mmEndpoint [$mmGet "endpoint"]
:local mmEpPort [$mmGet "endpoint_port"]
:local mmHubAddr [$mmGet "hub_address"]
:local mmRAddr [$mmGet "router_address"]
:local mmKeep [$mmGet "keepalive"]
:local mmEnrollUser [$mmGet "enroll_user"]
:local mmEnrollPass [$mmGet "enroll_password"]
:if ([:len $mmHubKey] < 40 || [:len $mmEnrollPass] < 8) do={{ [$mmFail "Incomplete enroll reply"] }}

:put "MM: Connecting to Magic Hub"
/interface wireguard peers add interface=$mmIface public-key=$mmHubKey endpoint-address=$mmEndpoint endpoint-port=$mmEpPort allowed-address=($mmHubAddr . "/32") persistent-keepalive=($mmKeep . "s") comment=$mmComment
/ip address add address=$mmRAddr interface=$mmIface comment=$mmComment
/ip route add dst-address=($mmHubAddr . "/32") gateway=$mmIface comment=$mmComment
:local mmPingOk false
:local mmTry 0
:while (!$mmPingOk && $mmTry < 12) do={{
  :delay 3s
  :do {{
    :local mmP [/ping $mmHubAddr count=2]
    :if ($mmP > 0) do={{ :set mmPingOk true }}
  }} on-error={{}}
  :set mmTry ($mmTry + 1)
}}
:if (!$mmPingOk) do={{ [$mmFail "No handshake/ping to Magic Hub within timeout"] }}
:do {{ /tool fetch url=($mmStatusUrl . "?phase=handshake") check-certificate={FETCH_CERT_MODE} keep-result=no }} on-error={{}}

:put "MM: Enabling management access for Hub only"
:local mmCert ("mm-mgmt-" . $mmId8)
:local mmIp [:pick $mmRAddr 0 [:find $mmRAddr "/"]]
/certificate add name=$mmCert common-name=$mmIp subject-alt-name=("IP:" . $mmIp) key-usage=key-cert-sign,digital-signature,key-encipherment,tls-server days-valid=3650
/certificate sign $mmCert
/ip service set www-ssl certificate=$mmCert address=($mmHubAddr . "/32") disabled=no
:local mmPlace ""
:if ($mmInputLen > 0) do={{
  /ip firewall filter add chain=input in-interface=$mmIface src-address=$mmHubAddr protocol=tcp dst-port=443 action=accept comment=$mmComment place-before=0
}} else={{
  /ip firewall filter add chain=input in-interface=$mmIface src-address=$mmHubAddr protocol=tcp dst-port=443 action=accept comment=$mmComment
}}
/user add name=$mmEnrollUser group=full address=($mmHubAddr . "/32") password=$mmEnrollPass comment=$mmComment
# enroll password comes only from the HTTPS enroll reply; never typed or shown in the app UI
:do {{ /tool fetch url=($mmStatusUrl . "?phase=management_applied") check-certificate={FETCH_CERT_MODE} keep-result=no }} on-error={{}}
:put "MM: Done. MikroMagic will finish Connected status in the app. Do not share this terminal output."
}}'''
    assert_script_safe(script, token=token)
    return script
