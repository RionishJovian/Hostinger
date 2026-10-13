# Magic Connect hardware window — hAP ax² on the production Hub

Status: window run 2026-10-13 — hAP ax² **Connected** (see “Window result”). This document is not authorization to contact or change the router until the owner starts the window. The owner chooses the moment to power on and apply router commands.

## Goal

Enroll the owner's hAP ax² through the real Magic Connect flow on `mm-prod-hub` (`156.67.216.128:51820`), then prove:

1. a fresh WireGuard handshake (transport only)
2. MikroMagic-created monitoring and Safe Change logins (S1 evidence)
3. an authenticated, TLS-pinned, identity-checked management read: **Connected** (D1 evidence)

## Offline readiness — verified 2026-10-13 (engineer, read-only)

| Check | Result |
|---|---|
| Technician-guided setup code on `origin/main` | YES (steps 1–2b + voucher/portal/session software behind Connected) |
| Production Hub `mm-prod-hub` healthy, UDP `156.67.216.128:51820` | YES |
| Hub peer count | **0** (no live tunnels to interrupt) |
| Hub public key (fingerprint only) | `TG1jLN13+hA1Eg9/1h0DykQ768ZHZO54WFGAZWhjL0o=` |
| API → Hub tunnel relay (`MIKROMAGIC_HUB_RELAY_URL`) | YES (deployed earlier; 8791 not public) |
| RouterOS credential dirs present, empty, mode 0700 | YES (`monitoring` / `safe-change` / `enroll`) |
| Historical tunnel conflict plan | Disable `mmh-8adfeb441215` inside the window; delete only after Connected is proven |
| Exact router commands + rollback | Generated live on the technician page after Hub peer add; historical-tunnel commands below |
| Public capability before flag enable | `pairing_available: true`, `router_setup_available: false` |
| Flag enable for the window | `MIKROMAGIC_MAGIC_CONNECT_ROUTER_SETUP: "true"` in `compose.hostinger-public-test.yaml`, deploy with `ALLOW_INFRA_CHANGE=1`, then confirm `router_setup_available: true` |

**Offline readiness: YES.** Hardware uncertainties remain (see “Unverified until the window”). Do not claim Connected until step 9 succeeds.

## Owner checklist before power-on

1. Sign in at [megamagic.tech](https://megamagic.tech) as the business Owner/Admin.
2. **Shops:** the shop that will own the hAP ax² already exists.
3. **Routers:** register the hAP ax² on that shop if it is not already registered. Leave it with **no connection plan** yet. Have the **serial number from the router label** ready (typed later at approval).
4. Technician device ready (phone or laptop) with WinBox or RouterOS terminal to the router on the local LAN, using **Safe Mode** for writes.
5. Confirm local Wi-Fi / customer traffic that must stay up; stop if any step would touch WAN, LAN, Wi-Fi, HotSpot servers, other VPNs or unrelated firewall rules.
6. After the engineer confirms `router_setup_available: true`, power on the router and start the sequence table below.

## Before the window (engineer)

- `origin/main` deployed with step 2b; capability showed `router_setup_available: false` before the window flag.
- Enable setup for the window only: add `MIKROMAGIC_MAGIC_CONNECT_ROUTER_SETUP: "true"` to the API environment in `compose.hostinger-public-test.yaml`, commit, deploy with `ALLOW_INFRA_CHANGE=1`, confirm `router_setup_available: true`.
- The router is registered on the owner's Routers page for the right shop, with no plan yet.
- Hub has 0 peers; Hub key `TG1jLN13+hA1Eg9/1h0DykQ768ZHZO54WFGAZWhjL0o=`.

## Historical tunnel conflict

The router still has the dead tunnel `mmh-8adfeb441215` towards the same Hub address and port. Owner decision 2026-10-10: disable it inside the window, delete it only after the new connection is proven.

```
/interface wireguard print detail where name="mmh-8adfeb441215"
/interface wireguard disable [find where name="mmh-8adfeb441215"]
```

Rollback: `/interface wireguard enable [find where name="mmh-8adfeb441215"]`

## Sequence

| # | Who | Action | Expected |
|---|---|---|---|
| 1 | Owner | Routers → Magic Connect: create a pairing for the shop | QR and manual code, 10 minutes |
| 2 | Technician | Open the pairing link, claim | Same six-digit phrase on both screens |
| 3 | Owner | Compare the phrase, pick the router, approve | Technician page shows Step 1 and Step 2 |
| 4 | Technician | Step 1 read-only check, Step 2 create `mm-<id8>`, send the public key | Owner sees the key |
| 5 | Owner | Pick the Hub, create the plan, enter the serial number from the router label, tick review, approve | Hub peer added; technician session extended to 30 minutes |
| 6 | Technician | Disable `mmh-8adfeb441215` (above), Step 3: peer, `/32` address, Hub route, ping | Ping to `10.90.1.1` answers |
| 7 | Owner | Check handshake | "Handshake received", not Connected |
| 8 | Technician | Step 4 read-only check, then certificate, `www-ssl` for the Hub only, one input rule, temporary `mm-enroll-<id8>` login | — |
| 9 | Owner | Within three minutes of a handshake check: Finish management setup and verify | Logins created, temporary login removed, then **Connected** |
| 10 | Owner | Issue one test voucher for the shop (a 1-hour plan), then Routers → Sync vouchers | "Updated on router" 1; Need attention 0 |
| 11 | Owner | Disable that voucher, then Sync vouchers again | The router login is disabled and any active session for it is removed |

All router commands are generated per router on the technician page; the rollback block there removes everything MikroMagic added.

## Stop at once if

- Step 1 or Step 4 checks show a conflict listed on the technician page (existing `mm-` names, port 13239 in use, the tunnel pool already used, `www-ssl` already enabled).
- The ping in step 6 fails after the owner added the Hub peer, or the handshake does not appear within two minutes.
- Finish management setup returns `router_serial_mismatch`, `certificate_name_mismatch`, `group_conflict`, `user_conflict` or `monitoring_write_not_denied`. Do not retry with changes; record the code.
- Anything touches WAN, LAN, Wi-Fi, HotSpot servers, other VPNs or unrelated firewall rules. Voucher sync may only add or change HotSpot users with the comment `MikroMagic voucher`, user profiles named `mm-<hash>` (RouterOS profiles have no comment field), and the scheduler `mm-voucher-expiry`.
- Sync vouchers reports `hotspot_user_conflict` or `hotspot_profile_conflict`: a login or profile with that name already exists and was not created by MikroMagic. Leave it and record the name.

## Evidence to record

- Handshake time from the Hub (`wg show mm-prod-hub latest-handshakes`, key fingerprint only).
- Management setup response: model, architecture, certificate SHA-256, usernames, checks (`monitoring_write_denied`, `safe_change_login`, `enrollment_login_removed`). It contains no passwords.
- Preflight response: `connection.connection_verified: true`, RouterOS version, compatibility.
- On the router: `/user print where name~"^mm-"` shows only `mm-monitor-<id8>` and `mm-safechange-<id8>`, both with `address=10.90.1.1/32`.
- Voucher sync: the Sync vouchers result, `/ip hotspot user print detail where comment~"MikroMagic"` (redact the voucher code, which is the login name and password), `/ip hotspot user profile print where name~"^mm-"`, and `/system scheduler print where name="mm-voucher-expiry"`.

## Rollback

1. Technician pastes the rollback block from the technician page (users, groups, input rule, `www-ssl` off, certificate, route, address, peer, interface).
2. Owner: Emergency lock on the router plan revokes the Hub peer.
3. Re-enable `mmh-8adfeb441215` only if the owner wants the old state back.
4. Remove `MIKROMAGIC_MAGIC_CONNECT_ROUTER_SETUP` and redeploy if setup should close.

## Unverified until the window

These RouterOS behaviours are assumptions; each failure stops the window with a recorded code:

- REST over HTTPS for `mm-monitor` with group policy `read,api,rest-api` (no `write`) and for `mm-safechange` with `read,write,api,rest-api`. Official User docs list `api` and `rest-api` as separate login policies; REST is the JSON wrapper of the console API over `www-ssl`. Virtual RouterOS 7 returned "not allowed (9)" for `read,rest-api` alone — still unverified on the hAP ax².
- `/certificate add ... subject-alt-name=IP:<address>` and `/certificate sign` producing a certificate Python accepts when pinned.
- `/ip service set www-ssl address=<hub>/32` limiting HTTPS to the Hub.
- A user deleting itself through REST (`DELETE /rest/user/<id>`).
- `/rest/system/identity/set` being refused for the monitoring group.
- `place-before=0` on an input chain that already has rules.
- HotSpot user fields `limit-bytes-total` and `limit-uptime`, and profile fields `shared-users`, `rate-limit` (`<rx>k/<tx>k`) and `on-login`, accepted through REST and read back unchanged.
- The profile `on-login` script writing `|exp=<time>` into the user comment on first login, and the `mm-voucher-expiry` scheduler (every minute, using `[:timestamp]`, which needs a recent RouterOS 7 release) disabling the user and removing its session after expiry. Until a real login proves this, voucher sync is not enforcement evidence.

## Window result — 2026-10-13 (hAP ax², serial HEJ08NYV0M1, RouterOS 7.24.2)

**Connected** (sequence steps 1–9), then HotSpot and voucher test (steps 10–11) passed after two fixes, below.

- Uplink: no ISP cable on ether1, so `wifi1` (5 GHz) was set to station mode on the owner's home Wi-Fi with a DHCP client (comment `mm-station-wan`). The home ISP path dropped traffic to `156.67.216.128`, so the router reaches the Hub through the engineer's Mac: static route `156.67.216.128/32 via 192.168.88.10` (comment `mm-hub-via-mac-vpn`) and a pf NAT anchor `com.apple/mm.hubnat` on ExpressVPN. Temporary lab path only; undo with `~/mm-hub-vpn-rollback.sh` on the Mac.
- Historical tunnel `mmh-8adfeb441215` was not present on the router; nothing to disable.
- Pairing `ab42fa50-6691-4171-9026-2474ec8019bd`, comparison phrase matched; plan `89c9a9f0-ee43-464d-978b-5b6bc988eb17`, router address `10.90.1.2/32`, interface `mm-97546f1a`. Step 1 and Step 4 checks were clean.
- Handshake: Hub `wg show mm-prod-hub latest-handshakes` showed router key `mIhCUL9/tHAv9gw7lADwR81ozreYELUWUF/ju7K5RXU=`; plan `handshake_verified_at` 1791871217 (06:00:17 UTC). Ping to `10.90.1.1` answered.
- First management setup returned `unreachable`: TCP 443 connected but TLS stalled. Cause: the tunnel ran inside ExpressVPN (MTU 1350) with the WireGuard default MTU 1420. Setting `mtu=1280` on `mm-97546f1a` (MikroMagic's interface only) fixed it. The technician `create_interface` command now sets `mtu=1280`.
- Management setup: model `C52iG-5HaxD2HaxD`, arm64, certificate SHA-256 `48998fae420d4198df9c6b4db7780b5deec0e51cc637134e0e59600fb7bd3fca`, users `mm-monitor-97546f1a` / `mm-safechange-97546f1a` (both `address=10.90.1.1/32`), checks `monitoring_write_denied`, `safe_change_login`, `enrollment_login_removed` all true.
- Preflight: `routeros_rest_live_read`, TLS verified, serial matches the label, compatibility `compatible_for_safe_change`, `connection.state: connected`, `connection_verified: true`, management read 1791871289 (06:01:29 UTC).
- Verified on hardware: REST over HTTPS for `read,api,rest-api` (monitoring) and `read,write,api,rest-api` (Safe Change); self-signed certificate with `subject-alt-name=IP:` accepted when pinned; `www-ssl` limited to `10.90.1.1/32`; enrollment user self-deletion; `place-before=0` put the rule first.
- Lab HotSpot (technician step; MikroMagic does not create HotSpot servers): `wifi2` (2.4 GHz, channel 6) removed from the LAN bridge, open SSID `Magic Cafe`, `10.5.50.1/24`, pool and DHCP `mm-lab-guest`, HotSpot `mm-lab-hotspot` with profile `mm-lab-hsprof` (`http-chap,http-pap,cookie`), `wifi2` in LAN and `wifi1` in WAN (defconf masquerade). USB LAN management unaffected. Rollback: `~/mm-lab-hotspot-rollback.rsc` on the engineer's Mac.
- Voucher sync, first attempt: `router_write_failed`. RouterOS 7.24.2 HotSpot user profiles have **no `comment` field** (`bad parameter comment`). Fixed in `0d885d6`: profiles are owned by their content-hash `mm-` name, with `profile_conflict` when a same-named profile has other limits.
- Preflight after the HotSpot server existed: `invalid_response`. `/rest/file` inlines file contents and the default HotSpot PNGs are not UTF-8. Fixed in `6beb972`: all file reads use `.proplist=name,type,size,last-modified`.
- Test plan "Test 1 hour" (Internet, time, 1 h from first login, 1 device, 5 Mbps); voucher `6566eddd` (code hint `DE`). Sync: `applied 1`. Router: user with comment `MikroMagic voucher`, profile `mm-28cee99cbf` (`shared-users=1`, `rate-limit=5000k/5000k`, `on-login` script), scheduler `mm-voucher-expiry` (owner `mm-safechange-…`, policy `read,write`).
- Real Wi-Fi client (engineer's Mac on `Magic Cafe`): unauthenticated HTTP redirected to `http://10.5.50.1/login`; a wrong code created no session; the voucher logged in (`http-pap`), the on-login script stamped `|exp=` exactly 1 h ahead, a dynamic 5M/5M queue appeared, HTTPS worked.
- Disable in the app: background sync disabled the router user and removed the active session within 5 s; the guest was redirected to login again; re-login answered `invalid username or password`. App: `in_sync 1`, `failed 0`.
- Clock: the router started at 2026-09-02 and IP Cloud `update-time` corrected it once online; the NTP client is disabled. A clock jump after first login would shift voucher expiry; an NTP check belongs in pre-Connected checks.
- Still unverified: the scheduler actually expiring a user at `|exp=` (needs the hour to pass), data quotas (`limit-bytes-total`), `limit-uptime` (connected-clock plans), multi-device `shared-users`, and a real phone. HotSpot cookies (`/ip hotspot cookie`) remain after disable; the disabled user could not log in, but removing them on disable is a small follow-up.
- Display gap: `GET /v1/routers` still reports `connection_state: unverified` for every router (hardcoded); the router plan carries the real state.

### Later the same day — guest login page publish and extra checks

- Guest page (`3e7c0a4`): one voucher-code box; typed codes are uppercased and spaces/dashes dropped before CHAP login. Lab profile `mm-lab-hsprof` set to `login-by=cookie,http-chap`.
- Publish to MikroTik needed four adapter fixes, each found on the router and tested: configuration export fallback to `execute as-string` because `/rest/export` returns `[]` on 7.24.2 (`ba2e3a2`); files created with `PUT /rest/file {name,contents}`, which is create-only and creates the directory (`a519cc5`); `api.json` skipped because RouterOS REST refuses `.json` files, and `DELETE` sent without a body (`f0aabb3`); resource ids sent unencoded because RouterOS answers `%2A1` with `no such command prefix` (`5a2ac1b`).
- Two failed attempts left the 9 new files in `mm-b21-731723e8-r2` while the profile stayed on `hotspot`; the engineer removed them and a manual scheduler pass recorded `manual_or_delayed_recovery_verified` / `rolled_back`. The Hostinger public test does not run `backend.safe_change_worker`, so `recovery_required` changes are only re-checked manually until that reviewed infra change lands.
- Applied publish (13:5x local, before `5a2ac1b` was deployed, because the owner's Mac battery was failing): the normal Safe Change apply ran in a one-off process inside the public-test API container with only the corrected `set_hotspot_profile_html_directory`. Result `applied`, safety backup verified, profile `html-directory=mm-b21-731723e8-r2`, 9 files present. The same fix was deployed through the script at 20261013T073052Z.
- Voucher `6ZYRPM` (Test 1 hour) synced for the owner's phone test; the phone test of the new page (lowercase code) is still pending.
- Expiry verified: `YMFVLN` (`|exp=` 14:00:26 router time) was disabled by `mm-voucher-expiry` at the 14:01 run without the app.
- Quota/devices sync verified (router settings only): plan "Test 2 devices 1GB" (both, 2 h, 1 GB, 2 devices, 3 Mbps) gave user `P4DVBC` `limit-bytes-total=1000000000` and profile `mm-ab6de62fe9` `shared-users=2`, `rate-limit=1500k/1500k` (package speed split per device). Enforcement at 1 GB and a third device were not exercised.
- Accounting read: `POST /v1/routers/{id}/hotspot-sessions/collect` returned `verified`, `fresh`, 0 active guests.
- Reboot recovery verified: `/system reboot` at 14:01:26; by 14:03:01 the Hub saw a 34 s-old handshake, preflight `connected` with `management_read_verified`, accounting `fresh`. Engineer SSH could not be reopened afterwards (admin password was entered privately), so post-reboot router-side state beyond the app reads was not inspected.
- Still unverified: phone test of the new page, quota and device-limit enforcement, automatic Safe Change rollback, backup restore, the WireGuard keepalive Safe Change, gateway-loss timeout rollback, and Hub restart recovery.

## Known gaps after the window

- Router credential files are stored unencrypted on the API's `routeros_credentials` volume (directory mode 0700, files 0600). Encryption at rest (M1) is still required before launch.
- Password rotation, revocation and recovery for these logins are later Safe Change work (C1).
- Voucher sync does not yet enforce the "redeem before" date on the router, separate upload/download speeds or quotas, or activation reporting back to MikroMagic (session and accounting reads, development step 6). Vouchers issued before this release have no stored code and are not sent to routers.
