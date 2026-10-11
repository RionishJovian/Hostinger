# MikroMagic Build 21 — frozen-v1 checkpoint v8

This checkpoint continues v7 in place. It does not restart Build 21 or add a
new product feature.

## Included P0 implementation

- Migration 028 recovery/conflict fields with downgrade preservation guard.
- Durable Safe Change worker with a five-minute gateway deadline and
  revision-fenced, restart-idempotent claims.
- Applying → Waiting for Gateway → Reconnected/Failed lifecycle.
- Deterministic keepalive rollback only; failed/unverified rollback becomes
  Recovery Required.
- Later-reconnection reread and expected/actual reconciliation before recovery
  can be cleared.
- Whole-version Keep Router Version and Keep MikroMagic Version decisions; no
  per-setting merge.
- Verified backup gate for Keep MikroMagic; no unnecessary backup for Keep
  Router.
- Tenant-scoped sanitized recovery/conflict evidence, audit events and one-week
  view-only conflict history.

## Verification completed locally

- 308 Python tests pass.
- Four site-worker tests pass.
- Production Vite build passes.
- Network UI checks pass.
- Production npm audit reports zero vulnerabilities.
- OpenAPI regenerated.
- Clean SQLite migration upgrade → base → head passes.
- PostgreSQL offline migration SQL regenerated.

## Still external / not accepted

- Real MikroTik RouterOS apply, disconnect, reconnect, timeout and rollback.
- Magic Hub/WireGuard packet-flow and management reachability.
- Encrypted backup volume durability on the VPS.
- Docker Compose rendering, image build, worker restart, PostgreSQL concurrency,
  loopback binding and VPS acceptance. Docker was unavailable in this workspace.

These items remain 🟡 and must not be inferred from simulated tests.

## Corrective continuation — proposal-only HotSpot portal review (2026-10-10)

- Migration 034 stores a tenant/site/router/evidence/package-bound HotSpot
  portal proposal and preserves any recorded owner-review evidence on downgrade.
- Preparation requires a current Connected plan, fresh identity-bound compatible
  pre-flight, explicit observed HotSpot server/profile, HTTP-CHAP without
  HTTP-PAP, and the exact published deterministic local portal package.
- The review shows the create-only directory and selected-profile diff,
  shared-profile blast radius, mandatory conflict/storage rereads, encrypted
  backup gate, exclusions and bounded rollback.
- Owner review is revision-fenced and audited. It is not RouterOS write approval.
- No RouterOS commands, uploads, profile changes, users/vouchers, firewall,
  RADIUS, DHCP/DNS, Wi-Fi, VPN or live infrastructure operation is implemented.
- Router apply, test voucher, First Customer Test and Site Ready remain blocked.

Verification: 466 Python tests pass with 12 environment-gated skips; all 34
JavaScript tests, production build, Sites packaging and production dependency
audit pass. OpenAPI was regenerated and migration 034's model DDL compiles for
PostgreSQL. Full-chain offline SQL generation remains unavailable because
pre-existing migration 029 performs a data-dependent user lookup. The isolated
local browser completed proposal preparation and owner review with no console
errors; no existing application database or live infrastructure was changed.

## Corrective continuation — isolated public-test artifact (2026-10-10)

- Added a separate `mikromagic-build21-public-test` Compose project and
  deterministic source artifact. The accepted private RC and its database are
  not modified or promoted.
- PostgreSQL, API and backups use new project-scoped volumes. Database and API
  have no published host ports. Web joins only a required, explicitly named
  existing ingress network and a project-private frontend network.
- The web proxy has a fixed private address and the API trusts only that exact
  `/32` for forwarded client addresses. RouterOS test mode and HTTP remain off;
  no router credentials, worker or public listener are included.
- Artifact SHA-256 after the public-browser fix:
  `4e78bae98d394fe40bcff6ce332282d212047247a21063c026b68ff0d4d79e93`.
  It contains migration 034 and excludes the accepted RC Compose file,
  secrets, internal status documents and build-only source trees.
- Local image build passed. Image IDs: API
  `sha256:23a1630205faa76000f2ad92eb25a894590982255b85f1ee5b7fea767d7157af`,
  web `sha256:56699d97b2e64da67f33830927c4cbed6f9b82b6325f7680b8c03f80088525e5`,
  migrate `sha256:88758391f3cff9940240e210d2199773a46f9cfb957a258583530cbd9bd042ce`.
- Verification now covers 467 Python tests with 12 environment-gated skips,
  deterministic packaging, Compose rendering, image-content gates, production
  frontend build and four Sites packaging tests.

Hostinger VPS 2032937 now runs the separate public-test project from
`/opt/mikromagic-build21-public-test-20261010`. Migration 034, PostgreSQL, API
and web are healthy; the API/database publish no host ports. The existing Caddy
container routes `megamagic.tech` and `www.megamagic.tech` to the isolated web
alias on `megamagic-landing-net`. External TLS, `/v1/health`, `/v1/ready`, UI
rendering and sign-in readiness pass from the Mac and a real browser. The
development-only demo control was removed from production after public browser
acceptance found its intentionally unavailable `/api` dependency.
One isolated platform test account uses a 24-hour temporary password and forces
a password change on first sign-in; its credential is not stored in source or
deployment evidence.

The previous landing Caddyfile, Compose file, Caddy inspection, original web
source and release image evidence are preserved under
`/opt/mikromagic-public-test-rollback-20261010T0335Z`. Existing RC, voucher,
acceptance and authentication-candidate containers remained running. Hostinger
still reports no usable whole-VPS backup or snapshot, and the Lima VM
`mikromagic-wg-dev` remains stopped; both remain explicit infrastructure
limitations.

## Corrective continuation — dedicated Magic Hub candidate (2026-10-10)

- Added a dedicated WireGuard control agent, internal-only authenticated client,
  fixed-interface/pool validation, atomic peer persistence, rollback-safe peer
  operations and live identity/readiness reporting.
- Added a read-only, least-privilege Hub container to the isolated public-test
  Compose project. It has only `CAP_NET_ADMIN` plus `/dev/net/tun`; its control
  API is private and only the WireGuard UDP socket can be published.
- Production feature gates remain fail closed. The API never reports a router
  connection from Hub identity or peer presence alone.
- Verification: 33 focused Hub/package tests pass; all 475 Python tests pass
  with 12 environment-gated skips; both API and Hub images build; the real
  local container health/identity smoke test passes; production frontend build
  and four Sites packaging tests pass. The deterministic 147-file artifact is
  SHA-256 `628825938079ca19395a20fd32199b16bc7dce3daf90af6918eb1c90baffc4b1`.
- Deployed from `/opt/mikromagic-build21-public-test-hub-20261010T143844Z`.
  Database, Hub, API and web are healthy; the registered database public key
  matches authenticated live agent identity before and after a Hub restart.
- Live database linkage is one Hub, zero assignments, zero tenants, zero sites
  and zero router devices, with a `hub_registered` audit event. Backend state is
  `peer_control_ready`; `connection_verified` is false by design.
- External UDP 51820 delivery was observed before and after restart. No Hub
  management port is public. HTTPS health/readiness and browser rendering pass.
  Unrelated containers remain running.
- Rollback retains pre-Hub API/web image tags, the prior release directory,
  existing Caddy rollback bundle and a protected pre-registration table dump.
- Classification: deployed and operational for enrollment control-plane work.
  **HUB READY: READY.** No physical-router action or connection claim.

## Software-only continuation after Hub readiness

- Physical MikroTik testing remains deferred; no router connection is claimed.
- Guest My access now includes an owned-record diagnosis with safe actions and
  explicit unavailable/stale labels for missing RouterOS session evidence.
- The endpoint does not accept voucher codes or arbitrary guest/pass lookup
  identifiers and exposes no code hashes or full voucher codes.
- Full regression: 477 Python tests pass with 12 skips; 34 JavaScript tests,
  production build and four Sites packaging tests pass.
- OpenAPI regenerated. Local artifact only: SHA-256
  `65145710483f7e68c07b72effa8f463ceae26b0e9a95cd882d74d2f25f7c9b91`.
- No deployment, VPS database write or existing-service change occurred.

## Offline continuation — transport reconciliation and document corrections (2026-10-10)

- Documentation only; no code, migration, database, deployment, VM, router or
  WireGuard change. Details are in the matching `STATUS.md` section.
- Transport-only Stage 2 plan reconciled with fresh read-only checks; readiness
  **NO** (VM stopped after an error; UDP forward pinned to a stale Mac address;
  VPN now on the default route). Exact approvals A1–A4 are listed in
  `docs/MAGIC-CONNECT-TRANSPORT-LAB.md`.
- D1/S1 prerequisites reconciled with Stage 1 observations.
- Owner/Admin review: a legacy `manager` can perform the owner's bootstrap
  review in the current code (probe on the temporary fixture database).
  Correction proposed, not implemented.
- Stale gap rows corrected (password policy, login history, demo presentation).
- Verification: 477 Python tests pass with 12 skips; 34 JavaScript tests pass.

## Legacy staff frozen and Stage 2 offline rehearsal (2026-10-10)

- Owner decision: deny all legacy staff requests. Staff may only call `/v1/me`
  and sign out; staff creation returns 410; `owner()` excludes staff. Owner
  keeps list/disable/reset. No migration or data change.
- Approved A1–A3 done: forward re-pinned to `.248`, VM started with
  `mm-dev-hub` up, Mac-to-guest UDP verified. Readiness YES subject to the
  window gate; A4 (router writes) still needs a scoped approval. VM left running.
- Verification: 479 Python tests (12 skips), 34 JavaScript tests, build,
  Sites 4/4 and UI checks pass.

## Hostinger production verification and redeploy (2026-10-10)

- Owner chose Hostinger as production; Z.com and `mikromagic.com` are retired.
- Deployed `4092ce1da282388f59ef1ef23e9ecb57adae45cccf85a26eb80ccb11f7ffeb1b` to `/opt/mikromagic-build21-public-test-20261010T171319Z`:
  - rollback tags `*:rollback-20261010T171319Z`;
  - pre-deploy dump in `backups/`.
- Fixes deployed with it:
  - Hub UDP 51820 is now published (`hub_uplink`);
  - the database secret is split;
  - legacy staff access is closed.
- SSH key rotated and password login disabled.
- Nightly verified backup on the VPS, a Mac off-VPS pull, and Keychain escrow of the Hub and backup keys.
- Still external: the management path, D1/S1 and real router acceptance.

## Voucher code rules (2026-10-10)

- Migration 035 (additive) and `backend/voucher_codes.py`:
  - prefix plus 6-character unambiguous suffix;
  - case-insensitive matching;
  - VIP custom codes;
  - business-scoped hashes; legacy codes preserved.
- Tests: `test_voucher_codes`, `test_voucher_code_migration`; full suite green.
- Not deployed.

## Voucher lifecycle (2026-10-10)

- Migration 036 (additive) and `backend/voucher_lifecycle.py`: unused-only soft delete, Disable with reason, Re-enable, permanent Revoke; pending router action recorded.
- Tests: `test_voucher_lifecycle`, `test_voucher_code_migration` (036 downgrade guard); full suite green (493, 12 skipped).
- Not deployed.

## Voucher production jobs (2026-10-11)

- Migration 037 (additive) and `backend/voucher_production.py`: production jobs, My Templates, tenant serial numbers, sheet identity, calibration gate, print verification, failed-only reprint, lost-sheet disable, distribution.
- Frontend: `src/VoucherProduction.jsx`, `src/voucher-production.mjs` (layouts, sheets, calibration page, preferences).
- Tests: `test_voucher_production` (6), `voucher-production.test.mjs` (5); full suite green (499, 12 skipped).
- Not deployed.

## Dealers and physical stock (2026-10-11)

- Migration 038 (additive): `dealers`, append-only `dealer_movements` and `dealer_ledger` (per-dealer sequence, request-key idempotency); vouchers gain `dealer_id` and `dealer_price`. Downgrade refuses while any dealer history exists.
- `backend/dealers.py`; production Distribute hands remaining stock to a dealer; counter sale and delete refuse dealer-held vouchers.
- Frontend: `src/Dealers.jsx`, `src/dealers.mjs`; production Dealer step enabled; dealer short code on printed sheets.
- Tests: `test_dealers` (5), `dealers.test.mjs` (5); head assertions moved to 038.

## Voucher sale payment methods and Cancel Sale (2026-10-11)

- Migration 039: `voucher_sales` gains `cancelled_at`, `cancelled_by`, `cancel_reason`; the unique constraint on `voucher_id` becomes a partial unique index over active (not cancelled) sales. Downgrade refuses while cancelled sales exist.
- `POST /v1/vouchers/{id}/sale/cancel` (owner only, idempotent replay by reason); sold checks in dealers, lifecycle and production ignore cancelled sales; revenue counts cancellations as refund-kind events.
- Frontend: `src/voucher-sales.mjs`, `src/VoucherPayments.jsx` (Record sale / Cancel sale / Refund), Vouchers, Cashier and Revenue labels.
- Tests: `test_voucher_sales` (+3), `test_dealers` (+1), `voucher-sales.test.mjs` (3); head assertions moved to 039.

## Shop setting: default printed Wi-Fi name (2026-10-11)

- Migration 040 (additive): `sites.printed_ssid` (nullable, 32 bytes). Downgrade refuses while any shop has a name set.
- `POST /v1/sites/{id}/settings`; `GET /v1/sites` and site creation return and accept `printed_ssid`.
- Frontend: `src/site-settings.mjs` (byte limit, prefill rules), Shop settings on the Sites page, production prefill, batch sheet and Quick Voucher Wi-Fi line.
- Tests: `test_sites` (+1), `site-settings.test.mjs` (3); head assertions moved to 040.

## Platform console (2026-10-11)

- Migration 041 (additive): `users.platform_owner` boolean, default false, provisioned server-side only.
- `backend/platform_console.py`: `GET /v1/platform/console/sessions` and `/v1/platform/console/sign-ins` (platform owner only).
- Login history now also records platform accounts (Platform console only; the Owner/Admin endpoint is unchanged).
- Frontend: `src/PlatformConsole.jsx`; the tab appears only when `/v1/me` returns `platform_owner`.
- Tests: `test_platform_console` (4); head assertions moved to 041; `test_enrollment_migration` inserts its user with SQL.

## Daily voucher counts per shop and for all shops (2026-10-11)

- `backend/revenue.py`: voucher sold/cancelled/refunded counts overall and per day, shop and method; per-day net by method. No migration.
- Frontend: `src/revenue-days.mjs` (Today in the reporting timezone, method summary), new metrics, columns and Today button in `src/RevenueDashboard.jsx`.
- Tests: `test_voucher_sales` (+1), `revenue-days.test.mjs` (3), `scripts/verify-revenue-ui.mjs` extended.

## Batch QR (2026-10-11)

- `backend/voucher_production.py`: `ProductionSettings.batch_qr` (default true) in print settings. No migration.
- Frontend: `src/batch-link.mjs` (build/read/strip the `?batch=&sheet=` link, QR per sheet), QR in sheet/run headers in `src/voucher-production.mjs`, setting and deep-link open in `src/VoucherProduction.jsx`, pending batch through sign-in in `src/AccountWorkspace.jsx`.
- Tests: `test_voucher_production` (+1), `batch-link.test.mjs` (4), `voucher-production.test.mjs` (+1).

## Shop hours and planned maintenance (2026-10-11)

- Migration 042 (additive): hours columns on `sites`, `site_incidents.expected_reason`, table `site_maintenance`.
- `backend/site_hours.py` (hours, maintenance, expected-incident label, post-maintenance Magic Check); `backend/incidents.py` stores the label; `/v1/sites` adds hours and `maintenance_until`.
- Frontend: `src/SiteHours.jsx`, `src/site-hours.mjs`; Overview maintenance item in `src/OverviewHealth.jsx` and `src/sme-localization.mjs`.
- Tests: `test_site_hours` (5), `site-hours.test.mjs` (4); head assertions moved to 042.

## Magic Support Mode / Get help (2026-10-11)

- Migration 043 (additive): `support_reports`.
- `backend/support_report.py` (report builder, scrubbing, share, platform inbox).
- Frontend: `src/SupportReport.jsx` (owner page and platform `SupportInbox`), `src/support-report.mjs` (text, file name, short cause); Get help menu item and Overview button; translations in `src/sme-localization.mjs`.
- Tests: `test_support_report` (3), `support-report.test.mjs` (3); head assertions moved to 043.

## Public interactive Demo (2026-10-11)

- No migration, no backend change.
- `src/demo-api.mjs` (in-memory demo client and sample business), demo mode in `src/AccountWorkspace.jsx` and `src/App.jsx`, demo note in `src/SupportReport.jsx`, banner strings in `src/sme-localization.mjs`, `.demo-banner` in `src/styles.css`.
- Fix: Revenue cash reconciliation request body (`src/RevenueDashboard.jsx`), guarded in `scripts/verify-revenue-ui.mjs`.
- Tests: `tests/demo-api.test.mjs` (8).


## Subscription self-service and renewal rules (2026-10-11)

- Migration 044 `platform_settings`; model `PlatformSetting`.
- `backend/subscriptions.py` (term rules), new `backend/subscription_renewal.py`, approval path in `backend/subscription_billing.py`, restriction in `backend/app.py` `current()`.
- `src/SubscriptionRenewal.jsx`, `src/SubscriptionPaymentSettings.jsx`, banner and restricted mode in `src/AccountWorkspace.jsx`, `renewal` strings in `src/sme-localization.mjs`.
- Staff UI removed (`src/StaffRecovery.jsx`, `src/CashierVouchers.jsx` deleted); `scripts/verify-staff-subscriptions-ui.mjs` rewritten.
- Tests: `tests/test_subscription_renewal.py` (7); migration heads 044.

## Developer Dashboard, first increment (2026-10-11)

- Migration 045 `owner_access`; `User.access_state/access_reason/access_revision`, model `OwnerAccessEvent`.
- New `backend/developer.py`; suspended-owner message in `backend/app.py` login.
- `src/DeveloperDashboard.jsx`, `src/OwnerAccounts.jsx`; platform-owner menu in `src/AccountWorkspace.jsx`.
- Tests: `tests/test_developer.py` (5); migration heads 045; four stale UI check expectations updated.

## Developer Dashboard Application settings (2026-10-11)

- New `backend/branding.py` (stored in `platform_settings` keys `application` and `application_logo`; no migration); body limit 1 MiB for the logo upload in `backend/app.py`.
- `src/ApplicationSettings.jsx`; branding, language offer and announcement banner in `src/AccountWorkspace.jsx`; `src/SMELocalization.jsx` and `src/sme-localization.mjs` take the platform language settings.
- Tests: `tests/test_branding.py` (3); a language-selection test in `tests/sme-localization.test.mjs`.

## Referral Agents (2026-10-11)

- Migration 046 `agents`: role `agent` (no business), invoice status `refunded`, tables `agent_profiles`, `agent_referrals`, `agent_commissions`, `agent_wallets`, `agent_withdrawals`.
- New `backend/agents.py`; `provision_business` extracted in `backend/onboarding.py`; commission on approval and owner-only refund in `backend/subscription_billing.py`; Agent path guard in `backend/app.py`.
- `src/AgentWorkspace.jsx` (application form and four Agent pages), `src/AgentManagement.jsx` (Developer Dashboard → Agents), refund step in `src/SubscriptionBilling.jsx`.
- Tests: `tests/test_agents.py` (5); migration heads 046; roles test and the staff/subscriptions UI check updated for the Agents area.

## Smart Notification Center and Daily Owner Summary (2026-10-11)

- Migration 047 `notifications`: tables `notification_preferences` and `notification_reads`.
- New `backend/notifications.py` (derived feed with root-cause grouping, instability aggregation and in-place updates; preferences; read markers; daily summary), registered in `backend/app.py`.
- `src/NotificationCenter.jsx` (Notifications page, settings, Daily Owner Summary card); header bell, navigation entry and Overview card in `src/AccountWorkspace.jsx`; English and Burmese messages in `src/sme-localization.mjs`.
- Tests: `tests/test_notifications.py` (4), `tests/notification-messages.test.mjs` (2); migration heads 047.

## Media Pass rules (2026-10-11)

- Migration 048 `media_pass_rules`: column `media_titles.featured`, table `media_settings`.
- `backend/schemas.py` (no new combined packages, category mode), `backend/media.py` (category passes, `ensure_sold_separately`, activation windows and pass state, featured preview, settings endpoints), first-redemption activation in `backend/vouchers.py`, sale checks in `backend/app.py`, `backend/voucher_batch.py`, `backend/voucher_production.py`.
- `src/MediaCatalogue.jsx` (featured, preview setting, rules panel, pass status), package form in `src/AccountWorkspace.jsx`.
- Tests: `tests/test_media_pass_rules.py` (3); shared test package helper now an Internet package; migration heads 048.

## Agent application location (2026-10-11)

- Migration 049 `agent_location`: `agent_profiles.region`, `city`, `township`, `latitude`, `longitude` (nullable for earlier applicants).
- `backend/agents.py` (`REGIONS`, `MYANMAR` bounds, required location in `ApplicationIn`, `location` in profile output).
- `src/AgentLocation.jsx` (region list, on-demand Leaflet map pin with typed fallback, pin link), application form in `src/AgentWorkspace.jsx`, Developer list in `src/AgentManagement.jsx`. New dependency `leaflet` 1.9.4 (BSD-2-Clause), split into its own chunk.
- Tests: `tests/test_agents.py` (2 new); `scripts/verify-agent-location-ui.mjs`; migration heads 049.

## Interface review, increment 1 (2026-10-11)

- `docs/UX-REVIEW-2026-10-11.md` (findings and plan).
- `src/AccountWorkspace.jsx` (header icon buttons, removed developer texts), `src/styles.css` (phone header and table rules), `src/PortalSettings.jsx` (older drafts), `src/sme-localization.mjs` (unused `authenticatedRecords` removed).

## Interface increment 2, SME menu (2026-10-12)

- `src/AccountWorkspace.jsx` (`SME_GROUPS`, grouped navigation), `src/sme-localization.mjs` (`navGroups`, renamed menu labels), `src/styles.css` (group headings, scrolling menu).
- Checks updated for the new menu source and names: `scripts/verify-staff-subscriptions-ui.mjs`, `scripts/verify-release-candidate-browser.mjs`.

## Interface increment 3, Vouchers task-first (2026-10-12)

- `src/VoucherTabs.jsx` (new, accessible tabs whose hidden panels stay mounted), `src/Vouchers.jsx` (`VoucherInventory` `view` of `issue`, `list` or `all`), `src/AccountWorkspace.jsx` (Vouchers page as tabs), `src/sme-localization.mjs` (`voucherTabs`), `src/styles.css` (wrapping tabs).
- `scripts/verify-voucher-ui.mjs` covers the split views, tab markup, hidden panels and the fallback tab.

## Interface increment 4, Overview (2026-10-12)

- `src/OverviewHealth.jsx` (health card owns the router message and action; `OverviewNetwork` split out with a collections card), `src/AccountWorkspace.jsx` (Overview order, revenue panels removed, unused `Metric` removed), `src/NotificationCenter.jsx` and `src/styles.css` (four-figure daily summary row), `src/sme-localization.mjs` (new `noKnown`, `netCollections`, `revenueNote` in English and Burmese).
- New `scripts/verify-overview-ui.mjs`.
