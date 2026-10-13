"""Generate the one-paste RouterOS 7 Magic Hub enrollment script.

The script detects facts at runtime (never assumes ether1/wifi1/model), never
emits admin-password commands, and embeds only a short-lived enrollment token
(not Hub-admin secrets or router logins). Certificate check uses RouterOS
built-in anchors with yes-without-crl (CRL not checked — documented risk).

RouterOS scripting constraints honored here:
- Functions (`:local f do={...}`) cannot see the caller's locals; pass values
  as named parameters, use script globals for fail-context, or inline logic.
- `:find` returns nil when nothing matches; never compare with >= 0 / < 0.
- Version major is compared with `[:tonum ...] < 7`.
- HTTPS replies use `/tool fetch ... output=user as-value` and `($r->"data")`.
- Certificate signing is asynchronous; wait until signed before www-ssl assign.
- Every configuration write is wrapped in `:do {} on-error={}` so failures run
  the cleanup path.
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
        'router_address', 'hub_pool', 'keepalive', 'interface', 'listen_port',
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

:global mmGStatusUrl
:global mmGComment
:global mmGId8
:set mmGStatusUrl $mmStatusUrl
:set mmGComment $mmComment
:set mmGId8 $mmId8

:local mmFail do={{
  :local mmMsg [:tostr $1]
  :global mmGStatusUrl
  :global mmGComment
  :global mmGId8
  :put ("MM-FAIL: " . $mmMsg)
  :local mmEnc ""
  :do {{
    :set mmEnc [:convert to=url $mmMsg]
  }} on-error={{
    :local mmRaw $mmMsg
    :local mmOut ""
    :local mmI 0
    :while ($mmI < [:len $mmRaw]) do={{
      :local mmCh [:pick $mmRaw $mmI ($mmI + 1)]
      :if ($mmCh = " ") do={{ :set mmOut ($mmOut . "%20") }} else={{
        :if ($mmCh = "&") do={{ :set mmOut ($mmOut . "%26") }} else={{
          :if ($mmCh = "=") do={{ :set mmOut ($mmOut . "%3D") }} else={{
            :if ($mmCh = "+") do={{ :set mmOut ($mmOut . "%2B") }} else={{
              :if ($mmCh = "#") do={{ :set mmOut ($mmOut . "%23") }} else={{
                :if ($mmCh = "?") do={{ :set mmOut ($mmOut . "%3F") }} else={{
                  :if ($mmCh = "%") do={{ :set mmOut ($mmOut . "%25") }} else={{
                    :set mmOut ($mmOut . $mmCh)
                  }}
                }}
              }}
            }}
          }}
        }}
      }}
      :set mmI ($mmI + 1)
    }}
    :set mmEnc $mmOut
  }}
  :do {{ /tool fetch url=($mmGStatusUrl . "?phase=failed&message=" . $mmEnc) check-certificate={FETCH_CERT_MODE} keep-result=no }} on-error={{}}
  :do {{ /user remove [find where comment=$mmGComment] }} on-error={{}}
  :do {{ /ip firewall filter remove [find where comment=$mmGComment] }} on-error={{}}
  :do {{ /ip service set www-ssl disabled=yes certificate=none address="" }} on-error={{}}
  :do {{ /certificate remove [find where name=("mm-mgmt-" . $mmGId8)] }} on-error={{}}
  :do {{ /ip route remove [find where comment=$mmGComment] }} on-error={{}}
  :do {{ /ip address remove [find where comment=$mmGComment] }} on-error={{}}
  :do {{ /interface wireguard peers remove [find where comment=$mmGComment] }} on-error={{}}
  :do {{ /interface wireguard remove [find where comment=$mmGComment] }} on-error={{}}
  :do {{ /ip dhcp-client remove [find where comment=$mmGComment] }} on-error={{}}
  :do {{ /ip firewall nat remove [find where comment=$mmGComment] }} on-error={{}}
  :set mmGStatusUrl
  :set mmGComment
  :set mmGId8
  :error ("MM-FAIL: " . $mmMsg)
}}

:put "MM: Checking RouterOS version and WireGuard"
:local mmVer [/system resource get version]
:local mmDot [:find $mmVer "."]
:if ([:typeof $mmDot] = "nil") do={{ [$mmFail ("Upgrade RouterOS to v7 (have " . $mmVer . ")")] }}
:local mmMajor [:pick $mmVer 0 $mmDot]
:if ([:tonum $mmMajor] < 7) do={{ [$mmFail ("Upgrade RouterOS to v7 (have " . $mmVer . ")")] }}
:do {{ :local mmWgTest [/interface wireguard find] }} on-error={{ [$mmFail "Upgrade RouterOS to v7 with WireGuard"] }}

:put "MM: Pre-checks before any write"
:local mmWwwDisabled [/ip service get www-ssl disabled]
:if ($mmWwwDisabled = false || $mmWwwDisabled = "false" || $mmWwwDisabled = no) do={{
  [$mmFail "www-ssl is already enabled — disable owner www-ssl first or leave HTTPS management to MikroMagic"]
}}
:if ([:len [/user find where name~"^mm-"]] > 0) do={{
  [$mmFail "A user starting with mm- already exists — remove it before MikroMagic setup"]
}}
:if ([:len [/user group find where name~"^mm-"]] > 0) do={{
  [$mmFail "A group starting with mm- already exists — remove it before MikroMagic setup"]
}}

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
          :do {{
            /ip dhcp-client add interface=$mmIfName disabled=no add-default-route=yes use-peer-dns=yes comment=$mmComment
            :put ("MM: DHCP client added on " . $mmIfName)
          }} on-error={{ [$mmFail "Could not add DHCP client on unused Ethernet"] }}
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
:do {{
  /interface wireguard add name=$mmIface listen-port=$mmPort mtu={TUNNEL_MTU} comment=$mmComment
}} on-error={{ [$mmFail "Could not create WireGuard interface"] }}
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
:local mmReply ""
:do {{
  :local mmFetch [/tool fetch url=$mmEnrollUrl http-method=post http-data=$mmData check-certificate={FETCH_CERT_MODE} output=user as-value]
  :set mmReply ($mmFetch->"data")
}} on-error={{
  [$mmFail "Could not reach MikroMagic enroll URL (HTTPS fetch failed)"]
}}
:if ([:typeof $mmReply] = "nil" || [:len $mmReply] < 10) do={{ [$mmFail "Empty enroll reply from MikroMagic"] }}
:local mmErrPos [:find $mmReply "status=error"]
:if ([:typeof $mmErrPos] != "nil") do={{
  :local mmErr "enroll rejected"
  :local mmPos [:find $mmReply "error="]
  :if ([:typeof $mmPos] != "nil") do={{ :set mmErr [:pick $mmReply ($mmPos + 6) [:len $mmReply]] }}
  [$mmFail $mmErr]
}}
:local mmOkPos [:find $mmReply "status=ok"]
:if ([:typeof $mmOkPos] = "nil") do={{ [$mmFail "Unexpected enroll reply"] }}

:local mmGet do={{
  :local mmReplyText $"reply"
  :local mmKey ($"key" . "=")
  :local mmPos [:find $mmReplyText $mmKey]
  :if ([:typeof $mmPos] = "nil") do={{ :return "" }}
  :local mmStart ($mmPos + [:len $mmKey])
  :local mmRest [:pick $mmReplyText $mmStart [:len $mmReplyText]]
  :local mmEnd [:find $mmRest "\\n"]
  :if ([:typeof $mmEnd] = "nil") do={{ :set mmEnd [:find $mmRest "&"] }}
  :if ([:typeof $mmEnd] = "nil") do={{ :return $mmRest }}
  :return [:pick $mmRest 0 $mmEnd]
}}
:local mmHubKey [$mmGet reply=$mmReply key="hub_public_key"]
:local mmEndpoint [$mmGet reply=$mmReply key="endpoint"]
:local mmEpPort [$mmGet reply=$mmReply key="endpoint_port"]
:local mmHubAddr [$mmGet reply=$mmReply key="hub_address"]
:local mmRAddr [$mmGet reply=$mmReply key="router_address"]
:local mmHubPool [$mmGet reply=$mmReply key="hub_pool"]
:local mmKeep [$mmGet reply=$mmReply key="keepalive"]
:local mmEnrollUser [$mmGet reply=$mmReply key="enroll_user"]
:local mmEnrollPass [$mmGet reply=$mmReply key="enroll_password"]
:if ([:len $mmHubKey] < 40 || [:len $mmEnrollPass] < 8) do={{ [$mmFail "Incomplete enroll reply"] }}

:put "MM: Checking hub pool does not overlap existing addresses/routes"
:if ([:len $mmHubPool] > 0) do={{
  :if ([:len [/ip address find where address=$mmRAddr]] > 0) do={{
    [$mmFail ("Address already uses router tunnel address " . $mmRAddr)]
  }}
  :if ([:len [/ip address find where address~($mmHubAddr . "/")]] > 0) do={{
    [$mmFail ("Address already overlaps hub address " . $mmHubAddr)]
  }}
  :if ([:len [/ip route find where dst-address=($mmHubAddr . "/32")]] > 0) do={{
    [$mmFail ("Route already exists for hub address " . $mmHubAddr)]
  }}
  :if ([:len [/ip route find where dst-address=$mmHubPool]] > 0) do={{
    [$mmFail ("Route already covers hub pool " . $mmHubPool)]
  }}
  :local mmPoolSlash [:find $mmHubPool "/"]
  :if ([:typeof $mmPoolSlash] != "nil") do={{
    :local mmPoolNet [:pick $mmHubPool 0 $mmPoolSlash]
    :if ([:len $mmPoolNet] > 0) do={{
      :local mmLastDot 0
      :local mmScan 0
      :while ($mmScan < [:len $mmPoolNet]) do={{
        :if ([:pick $mmPoolNet $mmScan ($mmScan + 1)] = ".") do={{ :set mmLastDot $mmScan }}
        :set mmScan ($mmScan + 1)
      }}
      :local mmPrefix ([:pick $mmPoolNet 0 $mmLastDot] . ".")
      :foreach mmAid in=[/ip address find] do={{
        :local mmA [/ip address get $mmAid address]
        :local mmSlash [:find $mmA "/"]
        :local mmAip $mmA
        :if ([:typeof $mmSlash] != "nil") do={{ :set mmAip [:pick $mmA 0 $mmSlash] }}
        :local mmHit [:find $mmAip $mmPrefix]
        :if ([:typeof $mmHit] != "nil") do={{
          :if ($mmHit = 0) do={{
            [$mmFail ("Existing address " . $mmA . " overlaps hub pool " . $mmHubPool)]
          }}
        }}
      }}
    }}
  }}
}}

:put "MM: Connecting to Magic Hub"
:do {{
  /interface wireguard peers add interface=$mmIface public-key=$mmHubKey endpoint-address=$mmEndpoint endpoint-port=$mmEpPort allowed-address=($mmHubAddr . "/32") persistent-keepalive=($mmKeep . "s") comment=$mmComment
}} on-error={{ [$mmFail "Could not add WireGuard peer"] }}
:do {{
  /ip address add address=$mmRAddr interface=$mmIface comment=$mmComment
}} on-error={{ [$mmFail "Could not add tunnel address"] }}
:do {{
  /ip route add dst-address=($mmHubAddr . "/32") gateway=$mmIface comment=$mmComment
}} on-error={{ [$mmFail "Could not add hub route"] }}
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
:local mmIpSlash [:find $mmRAddr "/"]
:local mmIp $mmRAddr
:if ([:typeof $mmIpSlash] != "nil") do={{ :set mmIp [:pick $mmRAddr 0 $mmIpSlash] }}
:do {{
  /certificate add name=$mmCert common-name=$mmIp subject-alt-name=("IP:" . $mmIp) key-usage=key-cert-sign,digital-signature,key-encipherment,tls-server days-valid=3650
}} on-error={{ [$mmFail "Could not create management certificate"] }}
:do {{
  /certificate sign $mmCert
}} on-error={{ [$mmFail "Could not sign management certificate"] }}
:local mmSigned false
:local mmWait 0
:while (!$mmSigned && $mmWait < 30) do={{
  :delay 1s
  :do {{
    :local mmFp [/certificate get $mmCert fingerprint]
    :if ([:typeof $mmFp] != "nil" && [:len $mmFp] > 0) do={{ :set mmSigned true }}
  }} on-error={{}}
  :if (!$mmSigned) do={{
    :do {{
      :if ([/certificate get $mmCert private-key] = true || [/certificate get $mmCert private-key] = "true") do={{
        :local mmCa [/certificate get $mmCert ca]
        :if ([:typeof $mmCa] = "nil" || [:len [:tostr $mmCa]] = 0 || $mmCa = $mmCert) do={{ :set mmSigned true }}
      }}
    }} on-error={{}}
  }}
  :set mmWait ($mmWait + 1)
}}
:if (!$mmSigned) do={{ [$mmFail "Certificate was not signed in time"] }}
:do {{
  /ip service set www-ssl certificate=$mmCert address=($mmHubAddr . "/32") disabled=no
}} on-error={{ [$mmFail "Could not enable www-ssl for Hub management"] }}
:if ($mmInputLen > 0) do={{
  :do {{
    /ip firewall filter add chain=input in-interface=$mmIface src-address=$mmHubAddr protocol=tcp dst-port=443 action=accept comment=$mmComment place-before=0
  }} on-error={{ [$mmFail "Could not add Hub HTTPS accept rule"] }}
}} else={{
  :do {{
    /ip firewall filter add chain=input in-interface=$mmIface src-address=$mmHubAddr protocol=tcp dst-port=443 action=accept comment=$mmComment
  }} on-error={{ [$mmFail "Could not add Hub HTTPS accept rule"] }}
}}
:do {{
  /user add name=$mmEnrollUser group=full address=($mmHubAddr . "/32") password=$mmEnrollPass comment=$mmComment
}} on-error={{ [$mmFail "Could not create temporary enroll user"] }}
# enroll password comes only from the HTTPS enroll reply; never typed or shown in the app UI
:do {{ /tool fetch url=($mmStatusUrl . "?phase=management_applied") check-certificate={FETCH_CERT_MODE} keep-result=no }} on-error={{}}
:set mmGStatusUrl
:set mmGComment
:set mmGId8
:put "MM: Done. MikroMagic will finish Connected status in the app. Do not share this terminal output."
}}'''
    assert_script_safe(script, token=token)
    return script
