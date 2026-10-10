# Stage 2 (transport-only) physical WireGuard connection — prepared, not authorized to execute

Scope: hAP ax² / RouterOS 7.24.2 / ARM64 to the isolated `mikromagic-wg-dev` VM. This tests transport only. No D1/S1 credentials, RouterOS management service, firewall rule, Wi-Fi, WAN, default route, HotSpot, or historical VPN change is in scope. Do not touch `mmh-8adfeb441215` except for the owner-approved retirement step at the end of this document. Obtain the owner's explicit hardware-window and exact router-write approval before applying any command below.

Stage naming: in this document "Stage 2" means **transport-only connection to the development Hub**. It is not the Stage 1 report's proposed management-surface reduction (telnet/www/MAC Telnet), which remains a separate optional change, and it is not Stage 2 of `MAGIC-CONNECT-CONTROLLED-HARDWARE-ACCEPTANCE.md` (TLS/S1 lab). Its success state is **Transport Verified**, never Magic Connect Connected.

## Current offline-readiness check — 2026-10-10 23:20 (+06:30): YES, subject to the window gate

The owner approved A1–A3 on 2026-10-10. Results:

- **A1 PASS.** `en0` rechecked as `192.168.100.248`. Backup saved as `~/.lima/mikromagic-wg-dev/lima.yaml.pre-repin-20261010`. The only semantic change is `portForwards[0].hostIP` `192.168.100.213` → `192.168.100.248`; yq re-indented the list without changing it. The VM stayed Stopped during the edit.
- **A2 PASS — boot persistence proven.** `limactl start` succeeded. `mm-dev-hub.service` is active after boot; public key `JF4IiTP7LA9szC7qso85fPe+rAuxqPZIKrmKNgBgST4=`; listen port 51821; zero peers; `10.254.0.1 peer 10.254.0.2/32`; private key root:root 0600; staged adapter code present. The Mac listener is `limactl` on `192.168.100.248:51821` (IPv4) only. Lima also logged two "address already in use" warnings when the guest's IPv6 wildcard socket for the same port tried to claim the already-bound host address; the IPv4 listener is unaffected.
- **A3 PASS.** One 8-byte probe from the Mac to `192.168.100.248:51821` reached the guest. Lima delivers it on guest loopback (`127.0.0.1:<ephemeral> → 127.0.0.1:51821`), so inside the VM the router's endpoint will appear as `127.0.0.1`. The guarded adapter does not inspect peer endpoints. Zero peers remained afterwards.
- The VM is left **running** for the window. A later restart re-creates the same Hub automatically, but rerun the A2 checks after any restart.

Offline readiness is therefore YES. Before requesting hardware time, the owner still chooses the ExpressVPN handling, and the Mac address must still equal `192.168.100.248` (otherwise repeat A1–A3 with the new value). The window-only uncertainties below are unchanged.

## Earlier offline-readiness check — 2026-10-10 23:15 (+06:30): NO (superseded by the result above)

Fresh read-only Mac/VM checks; no router, VM, VPS or network setting was contacted or changed:

- `mikromagic-wg-dev` is **Stopped**. Its last host-agent log entry (2026-10-09 21:19) is `VirtualMachineStateError`, not a clean shutdown. The live Hub interface from that boot no longer exists and the installed boot unit has never run.
- The instance's only enabled port forward is UDP 51821 pinned to host IP **`192.168.100.213`**. The Mac's Wi-Fi (`en0`) address is now **`192.168.100.248`** (DHCP from `192.168.100.1`, 12-hour lease), so that forward cannot serve the current address. The instance configuration must be re-pinned before any start (approval A1).
- A full-tunnel VPN (ExpressVPN Lightway, `utun4`) is connected and owns the Mac default route. The route to `192.168.100.0/24` still uses `en0`, so the LAN path is not captured by the VPN routing table. Inbound LAN UDP behaviour under this VPN is unproven.
- macOS Application Firewall is enabled (stealth and block-all off); `limactl` is listed as allowed for incoming connections.
- No host UDP listener exists on 51820–51829. Mac has no `wg`/`wireguard-go`; no Mac-side WireGuard is used or required.
- ARP cache (passive read only) has no entry for the router's last observed address `192.168.100.210`, consistent with the router being powered off. The router's current DHCP address is unknown.
- The historical router peer targets `156.67.216.128:51820`, which is the Hostinger VPS that now runs the public-test Hub on UDP 51820. That path must not be used, tested or modified by this lab.

Do not request hAP ax² availability while this section remains NO.

## Selected development-only path

**Path A — shared Wi-Fi LAN to Lima user-mode UDP forward (recommended).**

`hAP wifi1 (station, DHCP on 192.168.100.0/24)` → UDP → `Mac en0 <MAC_WIFI_IP>:51821` → Lima host-agent UDP forward → guest `0.0.0.0:51821` → kernel interface `mm-dev-hub`.

- The router initiates (endpoint + 25 s persistent keepalive). Hub replies return as connection-tracked traffic, which the existing `temporary-wifi-return` established/related rule accepts on `wifi1`. No router firewall, route, Wi-Fi, DHCP or service change is needed. If tunnel traffic would need a firewall change, stop.
- Tunnel packets arrive on the new interface `mm-b21-t01`, which has no drop rule in the observed four-rule input table.
- The Hub binds only to the Mac's Wi-Fi address, not `0.0.0.0`, so the VPN interface and loopback-only services are not exposed. WireGuard does not respond to unauthenticated packets, and the Hub will hold exactly one allowlisted peer.
- Inside the guest, the peer's source appears as the Lima forwarder rather than the router; WireGuard endpoint roaming tolerates this. Hub-initiated traffic depends on the forwarder session that the router's keepalive maintains.

Rejected alternatives:

- **Hostinger public-test Hub (`156.67.216.128:51820`)**: production-adjacent endpoint and the historical peer's target. Prohibited.
- **Lima forward on `0.0.0.0`**: would also bind the VPN tunnel and every other interface. Broader than necessary.
- **Lima `shared`/bridged (`socket_vmnet`) networking**: needs a privileged host helper, which `dev/magic-hub/README.md` excludes.
- **Direct Ethernet Mac↔router**: requires a new router address on an Ethernet port plus a Mac adapter; outside transport-only scope.

## Uncertainties only the hardware window can resolve

- Whether the upstream Wi-Fi access point isolates clients (router→Mac UDP). Passive ARP entries for other clients are weak evidence that it does not.
- Whether ExpressVPN accepts inbound UDP from the LAN on `en0`. Owner choice before the window: pause the VPN for the window, or keep it and treat "no handshake within five minutes" as a stop.
- The router's current Wi-Fi address and whether the Mac keeps `.248` through the window.
- Whether the Lima UDP forwarder carries the return path for a remote LAN client (previously proven only for a Mac-local probe).

## Separately approved steps required before a hardware window

Each item is an exact operation; none is authorized by this document.

**A1 — re-pin the VM's UDP forward (instance config change, VM stays stopped).** Recheck `ipconfig getifaddr en0` first and substitute that value:

```sh
cp ~/.lima/mikromagic-wg-dev/lima.yaml ~/.lima/mikromagic-wg-dev/lima.yaml.pre-repin-20261010
limactl edit --tty=false --set '.portForwards[0].hostIP = "192.168.100.248"' mikromagic-wg-dev
limactl list mikromagic-wg-dev
```

Verify that only `portForwards[0].hostIP` changed (diff against the copy) and the instance is still Stopped. Rollback: restore the copy while stopped.

**A2 — start the VM (boot-persistence test).** `limactl start mikromagic-wg-dev`. Then read-only checks only:

```sh
limactl shell mikromagic-wg-dev -- systemctl is-active mm-dev-hub.service
limactl shell mikromagic-wg-dev -- sudo wg show mm-dev-hub public-key
limactl shell mikromagic-wg-dev -- sudo wg show mm-dev-hub listen-port
limactl shell mikromagic-wg-dev -- sudo wg show mm-dev-hub peers
limactl shell mikromagic-wg-dev -- ip -brief address show dev mm-dev-hub
limactl shell mikromagic-wg-dev -- test -d /var/tmp/mikromagic-pairing-continuation-code.t8LkUp && echo staged-code-present
```

Expected: `active`; public key `JF4IiTP7LA9szC7qso85fPe+rAuxqPZIKrmKNgBgST4=`; port `51821`; no peers; `10.254.0.1 peer 10.254.0.2/32`; staged code present. If the service failed, the key differs or a peer exists, stop. Do not retry blindly or use the old key.

**A3 — Mac-to-guest UDP rehearsal on the new address (no router).** In the guest, capture one packet, then send one from the Mac:

```sh
limactl shell mikromagic-wg-dev -- sudo timeout 20 tcpdump -ni any -c 1 udp port 51821
printf mm-probe | nc -u -w1 192.168.100.248 51821
```

If `tcpdump` is not installed, stop and request approval for that package rather than substituting another method.

**A4 — hardware window and the exact router/VM writes below.** Owner chooses the time and the VPN decision.

## Frozen offline inputs (recheck immediately before the window)

- Mac Wi-Fi endpoint: `<MAC_WIFI_IP>:51821/udp`. Current observation `192.168.100.248`. The A1 host IP and the router peer `endpoint-address` must equal the same freshly observed value.
- VM interface: `mm-dev-hub`, `10.254.0.1` with peer address `10.254.0.2/32`, UDP 51821, zero peers.
- Rotated Hub **public** key: `JF4IiTP7LA9szC7qso85fPe+rAuxqPZIKrmKNgBgST4=`. Its private key is root-only inside the VM and must never be displayed or moved.
- Proposed new router objects: interface `mm-b21-t01`, RouterOS UDP listen port `51822`, point-to-point address `10.254.0.2/32` with remote network `10.254.0.1`, and one Hub peer with Allowed Address `10.254.0.1/32`; comment `MM-B21-T01`. RouterOS should create the connected `/32` route from that address. No static route is proposed. These are proposals, not observed router facts.
- Separation from the historical path: new endpoint is a private LAN address (never `156.67.216.128`); new listen port `51822` differs from historical `50627`; new tunnel `10.254.0.0/24` does not overlap historical `10.77.0.0/*`; the historical interface, peer, address, route and SSH input rule are untouched.
- The full owner-bound Hub orchestrator has no live tenant/site/router enrollment for this physical device. For this temporary transport-only test, the existing guarded `WireGuardHubAdapter` can provision/read back/revoke the one peer in the isolated VM. It does not establish application Connected.

## VM restart persistence — installed and enabled, boot untested

Before installation, read-only inspection found no `mm-dev-hub.service`, no `mm-dev-hub.conf`, and a disabled `wg-quick@mm-dev-hub`. The existing rotated private-key file remains root-owned mode 0600. On 2026-10-09, the owner approved installing **only** `/etc/systemd/system/mm-dev-hub.service` in this VM and enabling it for future boots. The unit reads the private key from its existing file, creates the same interface/address/port with zero peers, and refuses to replace an already-existing interface. It does not change Lima port forwarding or a router. It was enabled but **not started**, so restart persistence remains untested (A2 above).

```ini
[Unit]
Description=Isolated MikroMagic development WireGuard Hub
After=network.target
ConditionPathExists=/etc/wireguard/mm-dev-hub.private

[Service]
Type=oneshot
RemainAfterExit=yes
UMask=0077
ExecStartPre=/usr/bin/test ! -e /sys/class/net/mm-dev-hub
ExecStart=/usr/sbin/ip link add mm-dev-hub type wireguard
ExecStart=/usr/bin/wg set mm-dev-hub private-key /etc/wireguard/mm-dev-hub.private listen-port 51821
ExecStart=/usr/sbin/ip address add 10.254.0.1 peer 10.254.0.2/32 dev mm-dev-hub
ExecStart=/usr/sbin/ip link set up dev mm-dev-hub
ExecStop=/usr/sbin/ip link delete dev mm-dev-hub

[Install]
WantedBy=multi-user.target
```

Installation checks passed: the key file was root:root 0600 and its public identity matched the active interface; staged and installed unit SHA-256 matched; `systemd-analyze verify` passed; the installed unit is root:root 0644, enabled and inactive. If the service fails or differs after boot, do not retry blindly or use the old key.

Rollback: disabling the unit prevents the next boot but does not stop a live interface. Stopping the service deletes the interface and any live peers, so it requires a separately approved maintenance action.

## Five-minute stop gate at the hardware window

Use the already authorized local WinBox path. Before any write, confirm the expected hAP ax² identity, version, existing historical interface, Wi-Fi uplink, current `wifi1` address and unchanged local access. Read only the relevant interface, WireGuard listen-port, address, route, peer and input policy views. Stop if `mm-b21-t01` or `MM-B21-T01` already exists: inspect that partial test state before any retry. Stop if UDP 51822, either tunnel address, a covering route, the Hub public key, or the selected names conflict. Stop if the Mac's Wi-Fi address differs from the A1 host IP, the Hub public identity differs, the VM has a peer, or scoped tunnel traffic would require a firewall change. Do not repeat the broad Stage 1 audit or print private keys/full exports.

These RouterOS Terminal readbacks return only counts or the new public key. They are not a substitute for the focused route/firewall views:

```routeros
:put [:len [/interface/wireguard/find where name="mmh-8adfeb441215"]]
:put [:len [/interface/wireguard/peers/find where endpoint-address="156.67.216.128"]]
:put [:len [/interface/wireguard/find where name="mm-b21-t01"]]
:put [:len [/interface/wireguard/find where listen-port=51822]]
:put [:len [/interface/wireguard/peers/find where comment="MM-B21-T01"]]
:put [:len [/ip/address/find where comment="MM-B21-T01"]]
:put [:len [/ip/address/find where address~"^10\\.254\\."]]
:put [:len [/ip/route/find where dst-address~"^10\\.254\\."]]
:put [:len [/ip/route/find where comment="MM-B21-T01"]]
```

Expected: historical interface count 1 and historical-endpoint peer count 1; every other count 0. If not, stop. Check the actual address and route prefixes in the existing WinBox views; an exact-match count alone misses overlap.

## Approved-write sequence for a later window only

Enter WinBox Safe Mode for the bounded router changes. RouterOS generates the private key when the interface is added without a `private-key` parameter. Execute one line, read back, then continue; never paste the whole section blindly. [MikroTik's WireGuard manual](https://manual.mikrotik.com/docs/virtual-private-networks/wireguard/) documents auto-generation, public-key readback, peer fields and interface-gateway routes.

```routeros
/interface/wireguard/add name="mm-b21-t01" listen-port=51822 comment="MM-B21-T01"
:put [/interface/wireguard/get [find where name="mm-b21-t01"] public-key]
```

Pass **only that router public key** to the isolated VM. After rechecking zero peers, live Hub public identity and the owner-approved test scope, provision the single `10.254.0.2/32` peer through the staged guarded adapter. Its code path is `/var/tmp/mikromagic-pairing-continuation-code.t8LkUp/backend/wireguard_hub.py`; supply the observed router public key as the argument in place of `<ROUTER_PUBLIC_KEY>`. Do not use the older staged bundle, which lacks the current identity guard. This is a transport-only peer operation, not a production or authenticated app enrollment.

```sh
limactl shell mikromagic-wg-dev sudo env PYTHONPATH=/var/tmp/mikromagic-pairing-continuation-code.t8LkUp python3 -c 'import sys; from backend.wireguard_hub import WireGuardHubAdapter; a=WireGuardHubAdapter(binary="/usr/bin/wg"); a.verify_hub_identity("mm-dev-hub","JF4IiTP7LA9szC7qso85fPe+rAuxqPZIKrmKNgBgST4="); print(a.provision_peer("mm-dev-hub",sys.argv[1],"10.254.0.2/32","10.254.0.0/24"))' '<ROUTER_PUBLIC_KEY>'
```

Read back exactly one peer and allowed address before touching the router again. Then add only the new point-to-point router address and Hub peer, substituting the freshly verified `<MAC_WIFI_IP>`. MikroTik documents `network=<remote IP>` for a `/32` point-to-point address; verify the resulting connected route before pinging. If RouterOS 7.24.2 does not create the expected narrow route, stop rather than improvising a route change. [MikroTik point-to-point addressing](https://manual.mikrotik.com/docs/getting-started/networking-fundamentals/).

```routeros
/ip/address/add address=10.254.0.2/32 network=10.254.0.1 interface="mm-b21-t01" comment="MM-B21-T01"
/interface/wireguard/peers/add interface="mm-b21-t01" public-key="JF4IiTP7LA9szC7qso85fPe+rAuxqPZIKrmKNgBgST4=" endpoint-address=<MAC_WIFI_IP> endpoint-port=51821 allowed-address=10.254.0.1/32 persistent-keepalive=25s comment="MM-B21-T01"
/ip/route/print detail where dst-address=10.254.0.1/32
/tool/ping address=10.254.0.1 src-address=10.254.0.2 count=3
```

Verify a fresh, non-future handshake for that exact peer on **both** RouterOS and the VM, then send three pings VM → `10.254.0.2`. Confirm ping replies and increasing encrypted RX/TX on both sides. Use the scoped readbacks below; the VM adapter's observation never claims management verification. Read back only the new objects and confirm historical interface count/configuration and existing local WinBox/Wi-Fi are preserved. Only then mark **Transport Verified**; never mark Magic Connect Connected. If handshake or tunnel traffic is absent, stop within five minutes. No firewall, service, default-route or Wi-Fi workaround is included in this approval.

```routeros
/interface/wireguard/peers/print detail where comment="MM-B21-T01"
```

```sh
limactl shell mikromagic-wg-dev sudo env PYTHONPATH=/var/tmp/mikromagic-pairing-continuation-code.t8LkUp python3 -c 'import sys; from backend.wireguard_hub import WireGuardHubAdapter; a=WireGuardHubAdapter(binary="/usr/bin/wg"); a.verify_hub_identity("mm-dev-hub","JF4IiTP7LA9szC7qso85fPe+rAuxqPZIKrmKNgBgST4="); print(a.observe_peer("mm-dev-hub",sys.argv[1],"10.254.0.2/32","10.254.0.0/24"))' '<ROUTER_PUBLIC_KEY>'
limactl shell mikromagic-wg-dev -- ping -c 3 -I mm-dev-hub 10.254.0.2
```

Evidence to record: router and VM handshake timestamps, RX/TX deltas, ping results, the three new object IDs, historical counts before/after, and the exact `<MAC_WIFI_IP>` used. Do not record private keys or full exports.

## Scoped rollback, to be approved with the write sequence

Record the three new object IDs after creation. If the session remains in WinBox Safe Mode, an abnormal disconnect can roll back its router edits, but do not assume that also revokes the VM peer. On a deliberate rollback, inspect each ID/comment and remove only the objects created in this lab, in this order. The preflight requires those comments to be absent beforehand, so each table should have at most one matching object:

```routeros
/interface/wireguard/peers/remove [find where comment="MM-B21-T01"]
/ip/address/remove [find where comment="MM-B21-T01"]
/interface/wireguard/remove [find where comment="MM-B21-T01"]
```

Separately revoke only that public key from the VM and verify zero peers:

```sh
limactl shell mikromagic-wg-dev sudo env PYTHONPATH=/var/tmp/mikromagic-pairing-continuation-code.t8LkUp python3 -c 'import sys; from backend.wireguard_hub import WireGuardHubAdapter; a=WireGuardHubAdapter(binary="/usr/bin/wg"); a.verify_hub_identity("mm-dev-hub","JF4IiTP7LA9szC7qso85fPe+rAuxqPZIKrmKNgBgST4="); print(a.revoke_peer("mm-dev-hub",sys.argv[1],"10.254.0.2/32","10.254.0.0/24"))' '<ROUTER_PUBLIC_KEY>'
```

Do not remove a pre-existing matching object, restore the exposed old Hub key, reset the router, or remove the historical interface as part of this rollback. If ownership/readback is ambiguous, stop and preserve state for a narrower recovery decision. The A1 host-IP re-pin can be reverted from its saved copy while the VM is stopped.

## Retiring the historical tunnel (owner decision 2026-10-10)

The owner approved retiring the dead `mmh-8adfeb441215` interface in two steps:

- **Disable** it in an approved router window.
- **Delete** it only after the router's connection to the new Hub is proven.

The interface points at `156.67.216.128:51820`. Since 2026-10-10 that address is the published production Hub `mm-prod-hub`, which has no peer for it, so it can never complete a handshake.

**When to disable.** Disable it only after Transport Verified is recorded, or at the end of the session if transport fails. Nothing else in the lab depends on it.

**Before disabling, record its non-secret identity** for the evidence. Never print its private key or a full export:

```routeros
/interface/wireguard/print detail where name="mmh-8adfeb441215"
/interface/wireguard/peers/print detail where interface="mmh-8adfeb441215"
/ip/address/print where interface="mmh-8adfeb441215"
/ip/route/print where gateway="mmh-8adfeb441215"
```

**Disable**, in WinBox Safe Mode, then read the state back:

```routeros
/interface/wireguard/disable [find where name="mmh-8adfeb441215"]
:put [/interface/wireguard/get [find where name="mmh-8adfeb441215"] disabled]
```

Confirm that local WinBox, Wi-Fi uplink, internet access and the `MM-B21-T01` lab objects are unaffected. Rollback is `/interface/wireguard/enable [find where name="mmh-8adfeb441215"]`.

**Delete** in a later window, after a proven connection to the production Hub:
1. Delete the routes and addresses on the interface first.
2. Then delete the peer.
3. Then delete the interface.

Delete only objects recorded above. Deletion destroys the interface's private key and cannot be undone. That is acceptable only because the tunnel has no working counterpart.

## What Transport Verified does not unlock

Transport Verified is not authenticated management. Moving beyond it needs the D1/S1 prerequisites listed in `MAGIC-CONNECT-D1-S1-READONLY-FEASIBILITY.md` ("Remaining prerequisites — 2026-10-10"), including HTTPS on the router, distinct Monitoring and Safe Change identities, and a reviewed credential-delivery design.
