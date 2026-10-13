# Cloud agent handoff — 2026-10-13 (afternoon)

Mac session ending. Continue from this tip on `origin/main`. Do **not** run heavy checks, builds, or deploys on the owner's MacBook (owner decision 2026-10-13). Router is often solar-powered off — never contact or change the hAP ax² unless the owner says the hardware window is open.

## Source of truth

| Item | Value |
|---|---|
| Repo | private `RionishJovian/Hostinger` |
| Branch | `main` |
| Tip at handoff | `8610d61` (redeploy note for guest Wi-Fi Safe Change `7a24911`) |
| Live public test | [megamagic.tech](https://megamagic.tech) |
| Tracker | Notion page `3f2489e3-dbb6-81cc-9d2d-e66befe42255` (append-only execution checkpoints) |
| REST notes | `docs/ROUTEROS-REST-API-NOTES.md` |
| Hardware evidence | `docs/MAGIC-CONNECT-HARDWARE-WINDOW.md` |
| Deploy log | `MIKROMAGIC-HOSTINGER-HANDOVER.md` |

Start every task: `git fetch origin && git merge --ff-only origin/main`. Finish on `origin/main` after `bash scripts/check.sh`, then `scripts/deploy-hostinger-public-test.sh` for verified increments (standing owner approval). Commit `.corrective-source-manifest.txt` if `check.sh` changes it, then rerun checks. Append handover + Notion checkpoint after deploy.

## What just landed (do not redo)

| Work | Commit / deploy | State |
|---|---|---|
| Guest portal publish adapter fixes | through `5a2ac1b` | Verified on router (r2 files); lab profile later switched back to `hotspot` |
| Router-only voucher activation + usage on collect; 422 strips `input` | `85de0a9` @ 20261013T080203Z, migration **055** | Live; **not** re-verified with a live guest after deploy |
| Guest CHAP md5 byte fix (`charCodeAt(i)&255`) | `79c93c6` @ 20261013T081929Z | In API package; **router still serves old page** until new revision Safe Change |
| Guest Wi-Fi + guest addressing Safe Change | `7a24911` @ 20261013T083305Z, migration **056** | Live; flag **`MIKROMAGIC_ROUTER_SETTINGS_CHANGES` off** |
| RouterOS REST study | `a362868` → `docs/ROUTEROS-REST-API-NOTES.md` | Written |

Cloud agents that finished this work: accounting `bc-8a3052ad-9de4-43e0-bb3c-ce3991b7bbf6`, CHAP `bc-305a20bf-1dcc-4597-b5fa-5e546ed6e32b`, guest Wi-Fi/addressing `bc-8ecb1587-86e7-4ae8-ad82-7b1ead44696a`.

## Priority next (software, no router)

Owner order: MikroTik / captive portal ahead of remaining P0a. ChatGPT owns G01–G06 presentation (Midnight Studio); Cursor/cloud owns C02 engine.

1. **Guest VLAN for external AP (owner 2026-10-13)** — Safe Change behind the **same** `MIKROMAGIC_ROUTER_SETTINGS_CHANGES` flag. Scope: a guest VLAN on a **router Ethernet port** so an external AP feeds the HotSpot. Do **not** build switch-port VLAN management (Q70). Follow patterns in `backend/guest_wifi_settings.py`, `backend/guest_network_addressing.py`, `backend/safe_changes.py`, UI in `src/SafeRouterChanges.jsx`. Preserve WAN/`wifi1`, Hub tunnel, and lab bridge. Use literal RouterOS resource ids; never put secrets in diffs. Document expected REST + rollback in `docs/MAGIC-CONNECT-HARDWARE-WINDOW.md`. Migration if needed = next head after **056**.
2. Optional small docs: note in the hardware window that CHAP fix is deployed at `79c93c6` and still needs portal revision publish when the router is on.
3. Do **not** enable `MIKROMAGIC_ROUTER_SETTINGS_CHANGES` on production until the owner opens a hardware window.
4. Do **not** add `safe_change_worker` to Hostinger compose without an explicit reviewed `ALLOW_INFRA_CHANGE=1` task.
5. Leave ChatGPT presentation (G01+) alone unless reviewing a PR they open; handoff zip on Notion is tip `f52348d` (later `main` is fine if they rebase).

## Next hardware window (owner-gated — prepare only)

When the owner powers the hAP ax² and says go:

1. Observe Hub peer, then preflight → Connected.
2. Publish **new** portal revision (CHAP fix) → Safe Change install → phone-test code lower and upper case on the single box.
3. With a guest on a router-only voucher: `collect` → confirm voucher `activated` / used bytes.
4. Enable flag → Guest Wi-Fi SSID/security + guest addressing Safe Changes → disable flag.
5. Guest VLAN (once built) on a chosen ether port for external AP.
6. Still unverified from earlier: data-limit cut-off, third-device block, automatic rollback, backup restore, keepalive, gateway-loss, Hub restart.

Lab facts (do not change casually): guest `wifi2` SSID `Magic Cafe` open, `10.5.50.1/24`, HotSpot `mm-lab-hotspot` / `mm-lab-hsprof`, tunnel `mm-97546f1a`, Hub `156.67.216.128`. Historical dead peer `mmh-8adfeb441215` only disable/delete inside an approved window after new Hub proven.

## Hard rules

- Identity: corrective copy from frozen v8 zip only. Never touch `/opt/build21`, `/opt/mikromagic-v8`, Z.com, or `mikromagic.com`.
- Deploy only via `scripts/deploy-hostinger-public-test.sh` from commits already on `origin/main`.
- Never print `.env`, keys, passwords, or credential files.
- SSH: `mikromagic-hostinger` only; write only MikroMagic Build 21 public-test resources.
- One REST request stream per router; 60 s timeout; see `docs/ROUTEROS-REST-API-NOTES.md`.

## Report format (owner)

Changed / Deployed / Owner action (only if required) / Blockers — verified results only. Append Notion execution checkpoint after each verified step.
