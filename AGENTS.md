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

## Mandatory before every requirement build — Notion page 07 (synced 2026-10-13)

Source: Notion tracker index + page **07 — Mandatory before-build reconciliation and QA procedure** (consolidated 2026-10-13). Applies to Cursor and ChatGPT. Grants no new infrastructure or account permissions. Preserve every other repository safety/check rule; conflicts need explicit reconciliation.

**Before changing scope, before handoff/merge/deploy, and during QA:**

1. **Read current Notion.** Fetch the control-room index (`3f2489e3-dbb6-81cc-9d2d-e66befe42255`), the applicable domain page (01–06), page 07 (this procedure), and page 08 (evidence/gaps). On first onboarding read all six domain specs once; do not reload the full historical archive for every small task. Record page revision/time and requirement IDs. Never build from an old summary or conversation memory alone.
2. **Read actual GitHub/source.** Confirm repo `RionishJovian/Hostinger`, current `main`/target branch and exact full SHA. Inspect `AGENTS.md`, `MIKROMAGIC-REQUIREMENTS.md`, `REQUIREMENTS-GAP.md`, current handoff, relevant implementation/tests and active changes/PRs. Record owned/reserved files. Do not treat a CSS-only zip or old archive as the whole current app.
3. **Check the live app and deployed source identity.** Observe the real relevant route/role/state and served bundle; compare release directory/commit/image, migration and flags with authorized read access. GitHub main, a docs tip, API image, web bundle and router-installed portal can differ. No deploy/router/settings mutation during a read-only precheck. A public bundle proves neither backend source nor physical-router installation.
4. **Reconcile requirement versus code versus live.** For each acceptance clause mark Present / Partial / Missing / Conflict / Not verifiable. Newer explicit owner decision overrides older decision; later code or a test does not redefine policy. Preserve unresolved questions. If Notion and repo diverge, sync requirement/gap docs in the authorized ownership lane first.
5. **Declare the small build task.** Record owner, requirement IDs, scope, base SHA/Notion revision, intended files, dependencies, planned positive/negative tests and rollback/merge impact. Check active-file ownership. Cursor leads engine/backend/integrations/releases; ChatGPT supports handed-off presentation files only.
6. **Apply the readiness decision.** Missing current source, unresolved critical spec/ownership or unsafe authority blocks affected code edits. Missing live/backend access blocks live-verification claims, not independent documentation or a safely scoped offline task on verified source. Never imply background coding/testing is happening.

**Implementation and QA:** implement minimally; run baseline and focused checks; add meaningful tests including denial/failure/idempotency. Passing mocks or string checks are not end-to-end acceptance. Validate the real user flow (roles, EN/MY, desktop/mobile, themes, empty/loading/error/stale, reduced motion) without mutating production payments or router config for UI QA. Measure before/after performance deltas when the change can affect load/interaction. Use feature-specific acceptance (vouchers, payments, devices, media, hardware windows). Before merge/deploy refresh Notion and target main, detect drift, deploy only through `scripts/deploy-hostinger-public-test.sh` under current authorization, and prove served code matches release. Router portal publication remains a separate install/readback step.

**Status vocabulary:** Not Done · Ongoing/Partial · Implemented/Tested · Deployed · Verified · Blocked/Deferred — keep software, live-flow and hardware columns separate.

**Minimal task record:** requirement IDs; Notion revision; source full SHA/branch; owned files; deployed identity/flags; current gaps; planned checks; actual results; merge/deploy/hardware state; blocker/next action. No secrets, credentials or customer financial details in evidence.

## Cursor Cloud specific instructions — owner decision 2026-10-11

- The owner works from the Mac or, when it is unavailable, from a phone through Cursor cloud agents. Both use this GitHub repository (`RionishJovian/Hostinger`, private). It is the only source of truth for code and docs; the Mac copy must `git pull` before starting work.
- Environment: `.cursor/environment.json` runs `scripts/cloud-agent-install.sh` (`.venv` from `requirements.txt`, `npm ci`) and `scripts/cloud-agent-start.sh` (VPS SSH from the `MIKROMAGIC_VPS_SSH_KEY_B64` runtime secret).
- Start every task on the latest `origin/main` (`git fetch origin && git merge --ff-only origin/main` if the checkout is behind).
- Finish every task with the verified work merged into `origin/main` (rebase on the latest `main`, rerun the checks, then merge the branch or its pull request). Work left on a side branch is invisible to the other side and cannot be deployed. Do not run two agents on the same files at the same time.
- Checks: `bash scripts/check.sh` runs the Python tests in parallel (`scripts/run-tests.py`, one process per module; same tests as `.venv/bin/python -m unittest discover -s tests -p 'test_*.py'`), then `npm run build` before `node --test tests/*.test.mjs` (the Sites packaging test needs `dist/`; it includes `tests/sites-worker.test.mjs`). PostgreSQL tests skip without a database. While developing, run targeted modules with `.venv/bin/python scripts/run-tests.py test_hubs` (names or paths under `tests/`); run full `bash scripts/check.sh` once before merge. On success it records the passed source tree and commit in `.git/mikromagic-checks-passed`. If only `.corrective-source-manifest.txt` changed after the run, it records the tree that includes that manifest — commit the manifest file; deploy will not rerun checks. Deploy also skips rerunning checks when commits since the recorded pass change only documentation (`*.md`, `docs/**`) and/or `.corrective-source-manifest.txt` (`FORCE_CHECKS=1` reruns).
- Production is reachable only as `ssh mikromagic-hostinger` (root, dedicated cloud agent key, strict host key `deploy/known_hosts.hostinger`). The same rules apply as from the Mac: read-only verification freely; writes only to MikroMagic Build 21 public-test resources; never touch `/opt/build21`, `/opt/mikromagic-v8`, the `mikromagic-build21-rc` stack, other co-hosted stacks, sshd, the firewall or routers. Never print secret files, `.env` values or keys.
- Deploy only with `scripts/deploy-hostinger-public-test.sh`, only commits already on `origin/main`, under the owner's standing approval. It runs local checks, packages, uploads to a new dated directory, dumps the database, tags rollback images, rehearses new migrations on a throwaway PostgreSQL copy, migrates, starts, and verifies health, the Hub key/port, HTTPS and the served bundle. If it stops, do not work around it: report the message. `ALLOW_INFRA_CHANGE=1` is only for a reviewed Compose/Dockerfile/Caddy/Hub change.
- After a deploy, add a redeploy section to `MIKROMAGIC-HOSTINGER-HANDOVER.md` (copy the script's summary and rollback lines), commit and push it, then append the Notion execution checkpoint. Session notes that must survive go into the repository docs, not the agent's VM.
- Notion: use the Notion MCP server configured for cloud agents; the tracker rules above apply unchanged. If Notion tools are unavailable, say so in the report instead of skipping the checkpoint silently.

## Mandatory physical-router window gate — owner decision 2026-10-09

- Do not request hAP ax² availability until offline readiness is YES: the Lima VM, Mac-to-guest UDP delivery, development Hub interface/port, rotated key, exact proposed router commands, known-conflict review, rollback, and available software-only checks must be complete.
- Prepare the bounded transport sequence before the window. Identify only-router uncertainties explicitly; stop promptly on a conflict or failed prerequisite. The owner alone chooses when hardware is available.
- During an approved window, prioritize a fresh real handshake. Preserve `mmh-8adfeb441215`, Wi-Fi, firewall, unrelated routes/VPNs, and customer services. A handshake is transport evidence, not Magic Connect Connected; D1/S1 remains separate.
- Owner decision 2026-10-10: the dead historical tunnel `mmh-8adfeb441215` may be **disabled** during an approved router window and **deleted** only after the new Hub connection is proven. This is the only exception to preserving it, and it applies only inside an approved window.
- Current temporary transport plan and rollback: `docs/MAGIC-CONNECT-TRANSPORT-LAB.md`. Its commands are not authorization to contact or modify the router.
- Owner decision 2026-10-12: the Lima lab is not needed and `mikromagic-wg-dev` was deleted. The Lima items in the readiness list above no longer apply. The next window enrolls the hAP ax² through the real Magic Connect flow on the production Hub `mm-prod-hub`. Offline readiness now means: the technician-guided router setup is deployed behind its flag, the API can reach the tunnel pool through the Hub, the exact router commands and rollback are written, and the historical-tunnel conflict on `156.67.216.128:51820` is handled by disabling `mmh-8adfeb441215` inside the window.

## Mandatory local Mac housekeeping — owner decision 2026-10-12

- Local `npm run dev`, Vite, uvicorn, scratch SQLite DBs, deploy locks, and long unit-test runs on this MacBook hurt performance and memory when left running after testing.
- After every local test, browser walkthrough, or verification that started background processes: run `bash scripts/local-housekeeping.sh` before the final reply. Confirm ports `5173` / `8787` / `8788` are clear and report what was stopped/removed.
- Do not leave `npm run dev`, Vite, Python unittest runners, or scratch `/tmp/mm-*` databases running when the task is done. Prefer foreground bounded commands; if a background server is required, stop it in the same turn.
- Scope is this corrective checkout and known local scratch only. Never kill Cursor, unrelated apps, VPS processes, `/opt/build21`, `/opt/mikromagic-v8`, or co-hosted stacks.
- The Lima VM `mikromagic-wg-dev` was deleted on 2026-10-12 at the owner's request; do not recreate it for routine testing.
- Owner decision 2026-10-13: heavy work must not run on the MacBook (battery and performance). `scripts/check.sh`, unit-test suites, `npm run build`, local dev servers and `scripts/deploy-hostinger-public-test.sh` run only on a Cursor cloud agent instance. On the Mac, limit work to editing, git, and light SSH/API calls needed during a physical router window.

# Prototype Instructions

Run the local server yourself and open the preview in the browser available to this environment. Do not give the user server-start instructions when you can run it. After the preview/test is finished, run local housekeeping so the Mac is not left with leftover servers.

Before making substantial visual changes, use the Product Design plugin's `get-context` skill when the visual source is unclear or no longer matches the current goal. When the user gives durable prototype-specific design feedback, preferences, or decisions, record them in `AGENTS.md`.

Owner product-voice decision 2026-10-13: `megamagic.tech` is a B2B product for MikroMagic customers (shop owners / staff), not an engineering status board or agent chat. SME-facing copy must speak to the customer about their daily shop and MikroTik jobs (connect router, guest Wi-Fi page, vouchers, remote management). Do not show internal acceptance jargon, evidence-boundary wording, or feature-build narration on owner screens. Prefer plain steps (“Save guest Wi-Fi page in MikroMagic” vs “Publish portal content to MikroMagic”). Keep fail-closed honesty without sounding like a lab checklist.

Owner decision 2026-10-13 (sole builder): Cursor owns **all** implementation and progress for MikroMagic on this repository — including former ChatGPT support lanes G01–G06 (presentation tokens/components, responsive shell, copy/a11y, page polish, guidance presentation, frontend QA) as well as C01–C07. Do not wait on ChatGPT handoffs, CSS-only zips, or support patches. Notion may still mention historical G01–G06 labels for traceability; Cursor builds and deploys them.

Owner decision 2026-10-13 (priority): complete **G01→G06** presentation work first (Midnight Studio tokens/components, responsive shell, copy/a11y, stable-page polish, guidance presentation, frontend QA), then resume remaining P0b offline increments. Keep router/hardware safety rules; do not claim hardware acceptance from UI work.

When implementing from a selected generated mock, treat that image as the source of truth for layout, component anatomy, density, spacing, color, typography, visible content, and hierarchy.

Build app UI in `src/`. Keep `.openai/hosting.json`, `worker/index.js`, `scripts/prepare-sites-build.mjs`, and `tests/sites-worker.test.mjs` intact so the same local prototype can be handed to Sites. Before a Sites handoff, run `npm run build` and `npm run test:sites`; the build must leave `dist/client/index.html`, `dist/server/index.js`, and `dist/.openai/hosting.json`.

# Current development sequence

Owner decision 2026-10-12: prioritize MikroTik connection, router management workflows and the captive portal (Notion P0b) ahead of the remaining P0a interface work, media and switch/AP work. Order:

1. Technician-guided router setup on the real Hub: the router generates its own key, the technician submits the public key through the approved pairing session, the owner reviews the plan, the Hub peer is added, the app watches for the handshake. Behind a flag that stays off until a hardware window.
2. Management path: API → Hub → router tunnel route (reviewed infra change) and the router's least-privilege monitoring identity over HTTPS (D1/S1), ready for verification in the window.
3. Hardware window on the hAP ax²: first real handshake and authenticated management read (Connected).
4. Voucher → HotSpot user and profile sync (time, quotas, speeds, devices, disable/revoke), only for Connected routers.
5. Publish to MikroTik: install the local portal package and switch the selected HotSpot profile through Safe Change with backup, verify and rollback.
6. Session and accounting reads: first-login activation, usage, active guests; Unable to Verify when stale.
7. Local guest login page simplification, Burmese first.
8. First Customer Test on a real phone before Site Ready.

Small non-router fixes may still ship, but do not start new P1–P3 features until this list reaches step 5.

The frozen v1 tracker dated 2026-10-08 makes real-device acceptance the top priority. Continue RouterOS enrollment, WireGuard, HotSpot/accounting/enforcement, backup/restore and vendor acceptance work without claiming success until real infrastructure evidence exists. `MIKROMAGIC-REQUIREMENTS.md` is authoritative and `REQUIREMENTS-GAP.md` is the current audit.

Owner decision 2026-10-13 (router settings): build and test on the real router, through Safe Change, the guest SSID/Wi-Fi security change, the guest network IP/subnet/DHCP change, and a guest VLAN on a router port for an external AP feeding the HotSpot. Switch port VLAN management (Q70) stays later.

Owner decision 2026-10-13 (router connection method): connect routers through **Connect with Magic Hub** on the Routers page — one generated RouterOS script pasted once in WinBox (not hand-written scripts, not a multi-step technician QR command list). The script detects facts at runtime (free WireGuard name/port, internet/DHCP on unused Ethernet only when needed, firewall input chain); never assume interface names, wireless hardware or version; never include admin-password commands. Scratch routers with no default configuration must be supported as far as DHCP-on-link allows; otherwise stop with a clear internet message. QR technician pairing may remain as a secondary path; Routers leads with the one-paste popup.

Owner decision 2026-10-13 (router registration): the Routers page asks only for the device name. Model and RouterOS version are detected by the script and shown after connection, not typed. The app never asks for or stores the owner's WinBox username/password; the script creates MikroMagic's own limited monitoring and Safe Change logins. Popup progress: Router reported → Hub peer added → Handshake → Management ready → Connected.

Owner decision 2026-10-13 (guest phone login): the router login page is MikroMagic's own design with exactly one voucher-code box (no username/password pair); codes work in any letter case, ignoring spaces and dashes.

SME sidebar guidance is named 'Did you know?'. Platform publishers manage sourced cards. Keep compatibility marked unchecked until trusted router discovery exists. VPN, HotSpot/portal and RADIUS are separate roles. Local User Manager is a proposed authentication option; preserve it without claiming integration exists.

The user requested continuing through remaining non-live work without pausing for approval after each feature on 2026-10-06. Implement and verify consecutive work items, retaining the whole product scope. Pause only for real permission/access blockers or material business choices. Do not imply background execution continues after a final reply. Site WAN/budget and topology editors share one revision; preserve both settings when saving. Manual estimates/topology never count as discovered telemetry or verified enforcement.
