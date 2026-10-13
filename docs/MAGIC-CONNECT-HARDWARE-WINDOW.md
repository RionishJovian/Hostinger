# Magic Connect hardware window — hAP ax² on the production Hub

Status: software readiness verified 2026-10-13; window not yet run. This document is not authorization to contact or change the router until the owner starts the window. The owner chooses the moment to power on and apply router commands.

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
- Anything touches WAN, LAN, Wi-Fi, HotSpot servers, other VPNs or unrelated firewall rules. Voucher sync may only add or change HotSpot users with the comment `MikroMagic voucher`, user profiles named `mm-<hash>` with the comment `MikroMagic plan`, and the scheduler `mm-voucher-expiry`.
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

## Known gaps after the window

- Router credential files are stored unencrypted on the API's `routeros_credentials` volume (directory mode 0700, files 0600). Encryption at rest (M1) is still required before launch.
- Password rotation, revocation and recovery for these logins are later Safe Change work (C1).
- Voucher sync does not yet enforce the "redeem before" date on the router, separate upload/download speeds or quotas, or activation reporting back to MikroMagic (session and accounting reads, development step 6). Vouchers issued before this release have no stored code and are not sent to routers.
