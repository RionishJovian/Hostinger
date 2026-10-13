# Cloud agent handoff — 2026-10-13 (one-paste Magic Hub connect)

Continuing MikroMagic Build 21 v8 corrective work on Cursor cloud. Do **not** run heavy checks, builds, or deploys on the owner's MacBook (owner decision 2026-10-13). Router is often solar-powered off — never contact or change the hAP ax² unless the owner says the hardware window is open.

## Source of truth

| Item | Value |
|---|---|
| Repo | private `RionishJovian/Hostinger` |
| Branch | `main` |
| Tip at previous handoff | `fe4eb7c` (owner decision recorded; one-paste implement on this cloud run) |
| Live public test | [megamagic.tech](https://megamagic.tech) |
| Tracker | Notion page `3f2489e3-dbb6-81cc-9d2d-e66befe42255` (append-only execution checkpoints) |
| REST notes | `docs/ROUTEROS-REST-API-NOTES.md` |
| Hardware evidence | `docs/MAGIC-CONNECT-HARDWARE-WINDOW.md` |
| Deploy log | `MIKROMAGIC-HOSTINGER-HANDOVER.md` |

Start every task: `git fetch origin && git merge --ff-only origin/main`. Finish on `origin/main` after `bash scripts/check.sh`, then `scripts/deploy-hostinger-public-test.sh` for verified increments (standing owner approval). Commit `.corrective-source-manifest.txt` if `check.sh` changes it, then rerun checks. Append handover + Notion checkpoint after deploy.

## What just landed (do not redo)

Prior Guest VLAN / REST / Safe Change / connection UI work through `fe4eb7c` remains live (see previous handoff sections in git history). Flag **`MIKROMAGIC_ROUTER_SETTINGS_CHANGES` stays off**.

**This session:** one-paste **Connect with Magic Hub** (owner decision 2026-10-13 router connection method). Routers page registers name/model/RouterOS version → popup with one RouterOS 7 script (short-lived token) → `/tool fetch` enroll → Hub peer + management → app finishes Connected. Migration **058**. QR technician flow remains available under advanced pairing; Routers leads with the popup. Discarded unfinished multi-step adaptive QR design (never merged).

## Priority next (software, no router)

1. Hardware-window verification of the one-paste script on the hAP ax² (owner-gated).
2. Do **not** enable `MIKROMAGIC_ROUTER_SETTINGS_CHANGES` until the owner opens a settings window.
3. Leave ChatGPT presentation (G01+) alone unless reviewing a PR they open.

## Next hardware window (owner-gated — prepare only)

Follow `docs/MAGIC-CONNECT-HARDWARE-WINDOW.md` **one-paste sequence**. Confirm `router_setup_available: true` (flag already on). Historical tunnel `mmh-8adfeb441215` only disable/delete inside an approved window.

## Hard rules

- Identity: corrective copy from frozen v8 zip only. Never touch `/opt/build21`, `/opt/mikromagic-v8`, Z.com, or `mikromagic.com`.
- Deploy only via `scripts/deploy-hostinger-public-test.sh` from commits already on `origin/main`.
- Never print `.env`, keys, passwords, or credential files.
- SSH: `mikromagic-hostinger` only; write only MikroMagic Build 21 public-test resources.
- One REST request stream per router; 60 s timeout; see `docs/ROUTEROS-REST-API-NOTES.md`.

## Report format (owner)

Changed / Deployed / Owner action (only if required) / Blockers — verified results only. Append Notion execution checkpoint after each verified step.
