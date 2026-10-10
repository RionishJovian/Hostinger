## CRITICAL — MikroMagic Build 21 v8 identity and safety

- This directory is a corrective working copy derived only from `MikroMagic-Build21-FrozenV1-v8.zip` with SHA-256 `e4c4c2ea181c5e329a77903495f4862d2f4968b0e84803198ceb85693c289d01`.
- The frozen Notion tracker is the product authority. The original archive is immutable; never substitute or merge another MikroMagic project.
- Keep all edits in this clearly named corrective copy. Do not alter the original archive, `/opt/build21`, or the running `/opt/mikromagic-v8` deployment.
- No VPS, database, account, deployment, or infrastructure changes are authorized by this local task. A separate explicit approval is required for any deployment.
- Default to read-only outside this copy. Stop on identity mismatch, unexpected test data, unclear compatibility, or failed checkpoints; do not auto-repair.
- Preserve tenant isolation, audit history, existing sessions unless explicitly logged out/revoked, and stored legacy database structures.
- This section supersedes conflicting historical authorization or continuation instructions below for MikroMagic v8.

## Owner decisions — 2026-10-10 23:35 (Hostinger production)

- Production target is the existing Hostinger VPS `srv2032937.hstgr.cloud` (`156.67.216.128`), domain `megamagic.tech`. Z.com servers and `mikromagic.com` are discontinued: never deploy to or depend on them.
- Owner standing approval 2026-10-11 00:38: "You can deploy update works of yours to live app." The engineer may deploy verified increments to `megamagic.tech` without asking each time, still following the procedure (local tests green, new dated directory, pre-deploy dump, rollback image tags, migrate, verify, record evidence, Notion checkpoint) and stopping on anomalies.
- Owner decision 2026-10-11: Hostinger is the provider for the VPS and the domain, now and in future, and the app must live at `megamagic.tech`. Z.com and `mikromagic.com` are out of scope entirely — the owner has dropped them; do not follow up, back up, clean up or advise on them.
- The owner sets requirements; the lead engineer (agent) owns implementation and operations decisions. Approved: read-only live VPS verification, credential rotation run by the engineer, and redeploying the current corrective source to the public test.
- Notion is connected (2026-10-11). The authoritative tracker is the Notion page "MikroMagic — Requirements & Implementation Tracker" (id `3f2489e3-dbb6-81cc-9d2d-e66befe42255`); re-fetch it before requirement work and sync differences into `MIKROMAGIC-REQUIREMENTS.md`. Owner approved (2026-10-11) appending a short "Execution checkpoint — date" section at the end of that page after each verified step; append only, never rewrite owner content, and include only verified results.
- Notion owner direction 2026-10-10: work in small increments of build → deploy to the `megamagic.tech` public test → owner-visible test → fix; do not ask the owner to repeat requirements or manage agents. Report as Changed / Deployed / Owner action (only if required) / Blockers, verified results only.
- Each VPS change still follows its documented procedure: verify first, back up before writing, change only MikroMagic Build 21 resources, keep rollback, record evidence, and stop on anomalies. Co-hosted legacy stacks, `/opt/build21`, `/opt/mikromagic-v8` and router configuration stay untouched unless separately required.

## Mandatory physical-router window gate — owner decision 2026-10-09

- Do not request hAP ax² availability until offline readiness is YES: the Lima VM, Mac-to-guest UDP delivery, development Hub interface/port, rotated key, exact proposed router commands, known-conflict review, rollback, and available software-only checks must be complete.
- Prepare the bounded transport sequence before the window. Identify only-router uncertainties explicitly; stop promptly on a conflict or failed prerequisite. The owner alone chooses when hardware is available.
- During an approved window, prioritize a fresh real handshake. Preserve `mmh-8adfeb441215`, Wi-Fi, firewall, unrelated routes/VPNs, and customer services. A handshake is transport evidence, not Magic Connect Connected; D1/S1 remains separate.
- Owner decision 2026-10-10: the dead historical tunnel `mmh-8adfeb441215` may be **disabled** during an approved router window and **deleted** only after the new Hub connection is proven. This is the only exception to preserving it, and it applies only inside an approved window.
- Current temporary transport plan and rollback: `docs/MAGIC-CONNECT-TRANSPORT-LAB.md`. Its commands are not authorization to contact or modify the router.

# Prototype Instructions

Run the local server yourself and open the preview in the browser available to this environment. Do not give the user server-start instructions when you can run it.

Before making substantial visual changes, use the Product Design plugin's `get-context` skill when the visual source is unclear or no longer matches the current goal. When the user gives durable prototype-specific design feedback, preferences, or decisions, record them in `AGENTS.md`.

When implementing from a selected generated mock, treat that image as the source of truth for layout, component anatomy, density, spacing, color, typography, visible content, and hierarchy.

Build app UI in `src/`. Keep `.openai/hosting.json`, `worker/index.js`, `scripts/prepare-sites-build.mjs`, and `tests/sites-worker.test.mjs` intact so the same local prototype can be handed to Sites. Before a Sites handoff, run `npm run build` and `npm run test:sites`; the build must leave `dist/client/index.html`, `dist/server/index.js`, and `dist/.openai/hosting.json`.

# Current development sequence

The frozen v1 tracker dated 2026-10-08 makes real-device acceptance the top priority. Continue RouterOS enrollment, WireGuard, HotSpot/accounting/enforcement, backup/restore and vendor acceptance work without claiming success until real infrastructure evidence exists. `MIKROMAGIC-REQUIREMENTS.md` is authoritative and `REQUIREMENTS-GAP.md` is the current audit.

SME sidebar guidance is named 'Did you know?'. Platform publishers manage sourced cards. Keep compatibility marked unchecked until trusted router discovery exists. VPN, HotSpot/portal and RADIUS are separate roles. Local User Manager is a proposed authentication option; preserve it without claiming integration exists.

The user requested continuing through remaining non-live work without pausing for approval after each feature on 2026-10-06. Implement and verify consecutive work items, retaining the whole product scope. Pause only for real permission/access blockers or material business choices. Do not imply background execution continues after a final reply. Site WAN/budget and topology editors share one revision; preserve both settings when saving. Manual estimates/topology never count as discovered telemetry or verified enforcement.
