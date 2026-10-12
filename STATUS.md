# MikroMagic delivery status — development build 21

Authoritative frozen v1 requirements: [MIKROMAGIC-REQUIREMENTS.md](MIKROMAGIC-REQUIREMENTS.md). The current audit is [REQUIREMENTS-GAP.md](REQUIREMENTS-GAP.md). This document is historical delivery detail; the frozen tracker and gap audit take precedence where older increments conflict.

## Frozen-v1 P0 pass 4 — recovery scheduler and whole-version conflicts

Implementation complete: migration 028 adds durable recovery deadlines/evidence and conflict history. The dedicated Safe Change worker claims due records with revision fencing and repeatedly rereads actual RouterOS state. A successful write moves through Applying → Waiting for Gateway; reconnection is called Reconnected only after a matching reread. At five minutes, MikroMagic attempts rollback only for the existing deterministic keepalive operation. Failed or unverified rollback becomes Recovery Required. Later reconnection clears that state only after the actual router matches the recorded expected MikroMagic or rollback state.

Configuration conflict resolution is whole-version only. Keep Router Version rereads and verifies the unchanged conflict state, adopts it as expected and creates no backup. Keep MikroMagic Version requires Owner confirmation, captures/verifies the encrypted safety backup, applies the expected version and verifies or rolls back. Per-setting merge is not implemented. Conflict detection, choice, backup, verification, rollback and recovery evidence are audited; resolved conflict history remains view-only for one week. Tenant checks and API projections exclude credentials, private keys, backup storage references and encryption secrets.

Simulated/test verification covers scheduler timing, reconnect-before-timeout, timeout rollback success/failure, delayed recovery, mismatching actual state, both conflict choices, backup failure, verification mismatch, stale revisions, restart/idempotency, migration preservation and tenant isolation. The complete **308-test Python regression**, four site-worker tests, production frontend build, server-rendered network UI checks and production dependency audit pass with zero vulnerabilities. OpenAPI, a clean SQLite upgrade→base→head and PostgreSQL offline schema generation pass. Real MikroTik, Magic Hub, Docker/VPS networking and reconnect behavior remain 🟡 and unaccepted. The prepared VPS/Compose acceptance pass is still pending because Docker is unavailable in this workspace.

## Frozen-v1 P0 pass 3 — controlled RouterOS Safe Change

Implementation complete for one explicit operation: the reviewed Magic Hub WireGuard peer's persistent keepalive. The Owner/Admin flow reads actual RouterOS state, shows before/after and High risk impact, requires confirmation, fences stale previews and concurrent/replayed apply attempts, and refuses arbitrary paths or fields. Apply rereads the peer, captures a `show-sensitive=no` export, encrypts it with a separately mounted Fernet key, writes ciphertext mode `0600`, decrypt/checksum-verifies it and stops without writing if backup fails. The API then changes only the keepalive, rereads actual state and preserves before/desired/actual values.

If verification differs, rollback writes the exact captured keepalive to the exact peer and rereads it. Confirmed restoration becomes `rolled_back`; an ambiguous or failed rollback becomes `recovery_required`. Backup metadata never returns its internal storage reference. RouterOS credentials, backup key and private keys are absent from request models, database state, UI and exports. Per-router backup retention is seven days and at most three active artifacts; the fourth expires/removes the oldest.

Simulated/test verified: all requested success/failure paths pass, including backup failure, apply failure with unchanged state, verification mismatch, rollback success, rollback failure, stale live state, reused revision, tenant isolation, encryption/no-plaintext checks, `0600` permissions, FIFO retention and migration preservation. Full regression: **299 Python tests**. Production frontend build, Safe Change network UI checks and `npm audit --omit=dev` pass with zero vulnerabilities. OpenAPI, PostgreSQL offline schema and SQLite migration round-trip are regenerated/verified.

Real-device/external acceptance required: no MikroTik or Magic Hub was available, so RouterOS export, PATCH, reconnect and rollback are not accepted. Full-device restore, firmware-triggered backup and push delivery remain outstanding. Five-minute recovery scheduling and whole-version conflict resolution are implemented in pass 4 but remain real-device unaccepted. Docker is unavailable in this workspace, so Compose rendering must be repeated on the prepared VPS; YAML parsing is not counted as equivalent acceptance.

## Frozen-v1 P0 pass 2 — durable enrollment and router-side WireGuard evidence

Implementation complete: migration 026 adds protected, tenant-scoped RouterOS evidence history. Read-only pre-flight results are persisted. After an SME owner reviews the immutable Magic Hub plan, `POST /v1/routers/{id}/wireguard-evidence` reads RouterOS WireGuard peers, matches the planned hub public key and interface, evaluates the reported handshake age, stores sanitized evidence and records an audit event. `GET /v1/routers/{id}/evidence` returns up to 100 records within the caller's tenant scope. Router credentials remain operator-mounted secrets; full public keys and passwords are not returned in evidence.

Simulated/test verified: RouterOS duration parsing, matching and mismatch behavior, no false acceptance claims, API plan gating, tenant isolation, durable history and migration preservation tests pass. The complete Python regression passes **288 tests**. The production Vite build, network UI checks and production dependency audit pass; the audit reports zero vulnerabilities. The OpenAPI contract is regenerated.

Real-device/external acceptance required: no real MikroTik or Magic Hub was available in this pass. A recent router-side peer report does not prove the hub-side handshake, management reachability, firewall isolation, bidirectional packet flow, reconnect behavior, HotSpot enforcement or site readiness. Those values remain explicitly false/unaccepted. RouterOS configuration apply, verification and rollback were not performed.

Latest addition: frozen-v1 P0 RouterOS work now includes controlled Safe Change and encrypted pre-change backup handling for one explicit WireGuard peer field. Earlier increment sections are historical; the frozen requirements and gap tracker take precedence. Production integrations remain outstanding.

Code, simulated verification and real-environment acceptance are separate. Nothing here proves real router enforcement, a hub-side WireGuard handshake, tunnel reachability, paid streaming, backup restore or firmware behavior.

| Requirement | Current implementation | Verification / remaining work |
|---|---|---|
| Three roles | Platform, SME and guest workspaces; scoped API demo sessions | Browser role switching tested; API blocks foreign-tenant payment decisions. Account sign-in and tenant/role authorization implemented for core flows; scoped support delegation and deployment hardening pending. |
| SME revenue | Account-backed cash event ledger; site/date/timezone filters; gross/refunds/net, receipt count/average, pending workload, service/site/method/day totals and CSV export | Isolated tests cover period refunds, midnight boundaries, historical backfill, tenant/site isolation and source snapshots. Costs/profit remain demo-only; reconciliation and full KPI suite remain pending. Authenticated browser QA pending. |
| Manual payment review | Persistent orders and price snapshots; reference/evidence, duplicate warnings; approve/reject/request evidence; refund record and revocation | API tests passed for permission, duplicate decision, reasons, resubmission and revoke. Guest-order JPEG/PNG receipts now upload privately, with authenticated viewing and stale-review checks. Counter-sale image attachments and independent money verification remain pending. |
| External review API | Account-backed owner-delegated service credentials, complete review context/private receipts, context/version checks and idempotent audited decisions; separate demo HMAC implementation | Read-only, tenant/role isolation, token expiry/revoke/owner disable, stale context and approval/request-evidence/reject workflows tested. Durable per-service pull delivery with leases/acknowledgement/retries is now implemented. Real Telegram/Discord identity adapters, signature verification, provider notifications and reconciliation remain pending. |
| Voucher lifecycle | Account-backed issuance, hashed codes, masked inventory, single redemption, configurable 1–365 day redeem deadline, revocation, print UI and redemption metrics | Isolated tests verify retries, concurrent redemption, tenant isolation, expiry and revoke. Counter-sale receipt/refund records are connected in increment 6; browser print QA remains. |
| Internet entitlement | Data/time/both records, elapsed or connected counters, activation, usage simulation | API tests deny exhausted data and preserve counter on reactivation. Actual RouterOS/AAA accounting, sessions and device enforcement unbuilt. |
| Media entitlements | Account-backed timed-library, one-title and hybrid package policies; separate hybrid library/title windows and combined internet/media windows | Policy snapshots propagate through orders/vouchers/passes. Demo tests check expiry/title restrictions; live activation, playback, segment checks and replay-count policy remain pending. |
| Portal configuration | Saved SME drafts for branding, hostname/interface/subnet, payment instructions, allowlist and isolation; preview | Browser preview tested. Router selection, TLS, address-pool validation, diff/apply/backup/rollback unbuilt. |
| Magic Hub onboarding | Platform hub registry and business assignments; SME router plan allocation, immutable snapshots, JSON export and review | Atomic allocation/retry/isolation/overlap/exhaustion tests pass. Hub provisioning, router diff/apply/backup/rollback, capability discovery and trusted handshake/reachability evidence still need adapters and actual VPS/router. |
| WAN controls | Budget/reset/threshold/action/failover/load balancing drafts | Save API exists. Real Starlink estimate collection, cycle rollover, alerts and local policy apply/fault tests unbuilt. |
| Topology | Explicit manual architecture preview; separates management from local traffic | Real discovered graph/link evidence and editing unbuilt. |
| Appearance | Account-backed platform light/dark palette drafts, publication, role scope enforcement and previous-publication restore | Platform-only writes, revision conflicts, publication/restore and 20 contrast pairs tested. Authenticated browser and full accessibility QA remain pending; per-tenant overrides are not implemented. |
| SME guidance | Account-backed Did you know? sidebar page; search/topic filters, source/date, related settings and saved explanations in Magic Dude; platform drafts/edit/publish/withdraw/retire/restore | Role and revision checks, source/date validation and migration preservation tests pass. Three initial documentation cards. Compatibility stays unchecked; no AI-generated explanation or router discovery. |
| Floating Magic Dude | Contextual overlay, input and guided demo answers | Browser open/send/response checked. No model, diagnostic tools or config execution integration. |
| Platform operations | Business/first-SME-owner creation, 24-hour temporary-password handoff and mandatory change; owner reset/session/service-key revocation and reset history; account/fleet/hub readiness and audit | Permission, replay/duplicate, gate, expiry, password/session and reset isolation checks pass. SaaS billing, complete owner/staff lifecycle, recovery/MFA, fleet monitoring and live operational actions remain pending. |
| Media management | SME catalogue drafts/edit/publication/archive/restore; package pricing through Packages; guest browsing and stored media passes | Tenant/role/revision, publication and history tests pass. File upload, artwork, transcoding, storage, per-site source mapping, Jellyfin sync and playback remain unbuilt. |
| UI | User-reference forest/sage and ivory/evergreen; navigation and forms | Desktop browser checked at 1363x936. Responsive CSS exists; mobile browser/device testing remains. |
| Managed switches/APs | Site-scoped switch/AP inventory API and migration 021; owner-reported model, location, firmware and image metadata are stored with explicit unverified state; configurable default limit is one switch and five APs per site | Vendor discovery/control, health, client monitoring, capability checks and safe actions are not implemented. |
| Offline voucher operation | v1 requirement captured in blueprint | Bounded offline inventory, signed local redemption, reconciliation and conflict review are not implemented. |
| Monitoring and outage history | Site-scoped incident API with evidence-labelled suspected/confirmed causes, resolution history and tenant isolation; migration 023 | Live telemetry, uptime aggregation, deduplicated notifications, escalation and automatic root-cause correlation are not implemented. |
| Backups and restore history | Tenant/site-scoped backup metadata API and migration 024; encryption, checksum, retention and verified-restore state are recorded; healthy status requires restore verification | Actual encrypted storage, RouterOS/device export capture, FIFO deletion, restore preview/apply and automated integrity tests are not implemented. |
| Firmware management | Site-scoped staged firmware plan API and migration 025; maintenance window, safe version, rollout status and adapter-pending state are recorded | Model capability approval, artifact storage, staged execution, health checks, rollback and manual recovery are not implemented. |

## Validation performed
- Seven API workflow tests passed, isolated temporary database.
- Frontend production build passed.
- Browser test: guest evidence → pending order → SME review/approval → guest activation/check → revenue update.
- Portal preview, palette publish/restore, dark mode and assistant interactions tested.
- No application-origin console errors in checked browser logs. Browser extension metadata errors excluded.

## Production dependencies
Webapp VPS and hub VPS connection details; test MikroTik and site LAN; local media hardware/Jellyfin; operational domains/TLS; tenant/operator identities; adapter secrets and reviewer accounts; model integration. Never expose the demo role-login API publicly.

## Next implementation sequence
1. Production authentication/tenant RBAC and typed policy validation; authoritative order ledger and evidence storage.
2. Magic Hub peer onboarding and router capability discovery, backup/diff/apply/verification.
3. Router-local hotspot/AAA accounting and quota/device enforcement; bypass/IPv6 tests.
4. Telegram/Discord adapters and durable event delivery, audited reviewer identity.
5. Local media gateway/Jellyfin with per-segment entitlement checks and offline policy.
6. Operational telemetry, WAN fault tests, complete KPIs and deployment acceptance.

No requirement has been removed; unfinished items stay explicit here and in BLUEPRINT.md.

## Increment 21 — SME cash reconciliation

Revenue now lets an SME owner record a cash close for the selected site/date/timezone scope. The record stores counted collections, counted refunds, the actual immutable financial-event totals, the signed variance and operator notes. Positive variance means counted net cash is higher than recorded net cash. Request keys make retries safe and changed reuse conflicts; history is tenant-isolated and append-only. This is an operator attestation for cash control, not bank verification, a transfer, tax accounting or profit calculation. The web dashboard places reconciliation beside the KPI and ledger views.

Migration 020 adds reconciliation records with downgrade preservation requirements. Verification: reconciliation API tests cover variance, exact retry, changed-key conflict, validation and tenant isolation; the revenue component check now covers the cash-close form and history; OpenAPI and PostgreSQL offline migration SQL regenerate successfully. The 128-case Python regression, 17 JavaScript tests, production build, Sites packaging tests and preview restart pass. PostgreSQL runtime/concurrency and authenticated/mobile browser QA remain pending. Live router enforcement and media playback remain deferred.

## Increment 2 — account/payment backend (6 October 2026)

Added `backend/` FastAPI service with normalized SQLAlchemy records, PostgreSQL driver, frozen Alembic migration, private provisioning CLI and strict request schemas. Passwords use Argon2; opaque sessions are stored as digests, expire after one hour and support logout/account disable. Login failure buckets are persisted. Account role/tenant come from the database. No demo role creation endpoint exists in this service.

Packages/orders/manual decisions/refund records/entitlements/audit/outbox use relational transactions. Order request keys prevent retry duplication; approval uses a conditional pending-state update and unique entitlement constraint. Approved fulfillment stays pending_adapter, never falsely active. Platform accounts cannot automatically review SME guest payments.

Verified: eight new backend tests plus seven prior demo tests; schema compilation/offline migration SQL for PostgreSQL; migration upgrade → downgrade → upgrade on isolated SQLite. PostgreSQL runtime, concurrency under PostgreSQL and deployment still unverified.

At increment 2, the frontend remained on the development API. Increment 3 below connects the core account workflows. Production authentication is partially implemented, not a completed deployment. Frontend TypeScript conversion, guest onboarding, scoped support, evidence image storage, full API parity, accounting enforcement and adapters remain. Existing preview data is preserved; no implicit migration into the new database occurs.

## Increment 3 — authenticated browser workflows

The default entry is account sign-in, with a separate demo exploration button. Account role/tenant are database-derived; no account role switcher is present. Session tokens remain in memory; sign-out revokes them and expiry returns to sign-in. There are no default accounts.

Connected to `/v1`: SME packages, payment queue/full review, approval/rejection/evidence request/refund recording, revenue summaries, guest purchases with stable retry keys, evidence resubmission, stored passes, platform tenant registry and scoped audit. Fulfillment remains pending_adapter.

At increment 3, account portal settings, vouchers, WAN, routers, topology, media, integrations and palette publication showed pending work. Portal settings are connected in increment 4 below. Their demonstration forms remain separate; demo records are never used as authenticated business data. Core revenue has collections, refunds, order counts and service breakdown; cost tracking and date filters remain demo-only.

Verified: 16 isolated Python workflow tests, two client session/error tests, four frontend worker checks and production build. Browser checked sign-in layout and demo entry/return. Sign-in service proxy health was not independently confirmed in the browser. Authenticated browser journeys, mobile tests and PostgreSQL runtime validation remain pending.

## Increment 4 — SME portal drafts and publication

SME owners can save account-backed portal branding, welcome text, language preference, terms/contact, direct purchase and desired voucher options, payment destination/instructions/methods, hostname, guest interface/subnet, TLS/isolation preferences and explicit pre-login allowed hosts. Draft preview and publication are separate. Revision checks reject stale updates/publications. Changes are audited and isolated by account tenant.

Guests see only published guest-facing fields. Network configuration is excluded from that API. New purchases require a published portal, enabled direct purchases, an offered method and the published revision seen by the guest. Each order snapshots the payment destination/instructions; later portal edits never rewrite that history. Older orders retain null payment context rather than invented historical details. Existing request-key retries still return their original order after purchases close.

Publishing updates web content and purchase availability only. Router selection, DHCP/address pools, DNS/TLS provisioning, apply/diff/backup/verification/rollback, IPv6 behavior and media gateway enforcement remain pending. This initial portal is per business; per-site configuration awaits the site model. Language preference is stored; translated interface strings and recorded terms acceptance are pending. Desired voucher login does not activate account-backed redemption. Guest onboarding/pre-login account resolution remains pending.

Verified: 22 Python tests (including five portal workflow checks and migration preservation/round-trip), six existing JavaScript client/worker checks, component rendering checks for visible editor fields, closed purchasing, escaped untrusted text and no guest network fields, plus production build. PostgreSQL migration SQL compiles, but PostgreSQL runtime remains unverified. The preview service starts; browser inspection of the new editor was blocked by the current browser's unsupported error-page state. A static preview rendered from the actual React component is provided with sample data and disabled controls; it is not an authenticated browser journey.

## Increment 5 — account-backed vouchers

SME owners issue a single-use code against an immutable package snapshot, set a 1–365 day redemption deadline, view masked inventory and issued/redeemed/rate metrics, and revoke unused codes or redeemed passes with an audit reason. The database stores only a SHA-256 digest of a random 128-bit code. Full codes are returned once for copying/printing. Issuance request keys prevent duplicate codes on retry; a lost issuance response requires revoking the masked inventory entry and reissuing.

Guests redeem through the published portal's voucher option. Disabled/unpublished portals reject new redemptions. An atomic voucher claim plus unique entitlement origin grants one stored pass. Same-guest retries return that pass, including its revoked state; another guest cannot claim it. Expired/revoked/foreign-tenant codes are denied. Invalid well-formed codes have a persisted attempt limit per guest account. Stored passes identify their source as order or voucher, with an exactly-one-source database constraint. Redemption does not activate router or media access.

Issuance/redemption do not create payment orders or collections. Voucher counter-sale recording, refunds and ledger/revenue linkage remain pending; redemption metrics are operational counts, not sales. Entitlement activation, usage accounting, live revocation enforcement and voucher notifications still need the adapters. No requirement for external review, WAN, media, hubs, topology, themes or AI was removed.

Migration 003 preserves prior order entitlements and supports empty-voucher rollback; it refuses rollback when voucher records exist to prevent losing them. Verified: 29 isolated Python tests, six JavaScript client/worker tests, portal and voucher component rendering checks and production build. PostgreSQL migration SQL compiles; PostgreSQL runtime and authenticated browser journeys remain pending. Browser QA retains the previous blocked-browser limitation.

## Increment 6 — confirmed voucher counter sales and refunds

SME owners record a confirmed full-price counter payment against a voucher, with received amount, method, receipt/reference, evidence, staff identity and time. Issuance/redemption remain nonfinancial. A unique sale per voucher prevents duplicate collections; identical retries return the original record and different payment details conflict. Expired unused or revoked vouchers cannot receive a new sale record. Discounts/partial payments remain pending.

Full refund recording requires confirmation of funds returned outside the app, plus refund reference and reason. The recorded sale remains in history; voucher and stored pass are revoked in the same transaction. Repeated identical refunds do not subtract twice. Revoking a code alone never implies returning money. No transfer, independent receipt verification or live adapter action is claimed.

Revenue now combines approved guest orders and confirmed voucher sales, with gross, refunds, net, confirmed payment count, service breakdown and separate guest-order/voucher-sale totals. Platform subscription revenue remains separate. Date/site filters, historical period ledger, cash reconciliation/export, payment notifications, taxes and discounts remain pending.

Migration 004 preserves earlier records and refuses rollback when sale records exist. Verified: 35 Python tests, six JavaScript client/worker tests, component checks and production build, including concurrent sale submissions, retry/refund behavior, amount/confirmation validation, isolation and migration accounting preservation. PostgreSQL SQL generation passes; live PostgreSQL and authenticated browser QA remain pending.

## Increment 7 — sites, MikroTik registry and branch portals

SME owners create named sites with validated reporting timezones, register MikroTik model/name/reported RouterOS version at a site, and see their own registry. Platform accounts read the permitted site/router fleet; guests cannot read router metadata. Reported models/versions are explicitly unverified, with no assigned hub or handshake. No credentials, network connection or generated router script is claimed. Hub onboarding/capability discovery are still pending infrastructure work.

Each site has independent portal drafts and publication with the existing validation/revision checks. Guests can select published sites belonging to their business; their public portal data excludes private network settings. New guest orders and vouchers retain site identity, and resulting passes inherit it. Site vouchers cannot redeem at another site's portal. Packages remain shared within the business. Legacy business-wide portal and existing records are preserved without inventing historical site assignments.

Migration 005 adds site/router/site-portal records and nullable site references, preserving earlier payments/passes and check/foreign-key constraints. Downgrade refuses to discard existing site records. Site archival/editing, router-to-hotspot configuration assignment, automatic portal resolution from a real guest network, site-specific financial filters, infrastructure adapters, discovered topology and telemetry remain pending.

Verified: 40 Python tests, six JavaScript client/worker checks, portal/voucher/network component checks and production build. Tests cover tenant/role registry isolation, rejection of fake online-state claims, independent branch publication, site propagation, wrong-branch voucher denial, valid timezones, preservation of legacy grants and database constraints. PostgreSQL migration SQL generation passes; PostgreSQL runtime and authenticated/mobile browser QA remain pending.

## Increment 8 — Magic Hub registry and router connection plans

Platform owners register immutable hub names, public IPv4/DNS endpoints, UDP ports, public WireGuard keys and dedicated private /24 tunnel pools, then assign hubs to businesses. SMEs only see assigned hubs; guests cannot read hub or router-plan APIs. Registered hubs remain operationally unverified. No private keys or router credentials are accepted. DNS endpoint validation checks syntax only; no connectivity or DNS resolution is claimed. Hub key validity is format-checked; possession is not verified.

SME owners create one immutable connection plan per registered router using its public key and an assigned hub. The hub uses .1, routers receive .2–.254. A conditional database counter update allocates addresses atomically; uniqueness constraints protect router keys, plans and hub addresses. Exact retries reuse the existing plan. Pools are aligned /24 networks, so duplicate-pool rejection prevents overlap between registered hub pools. Known site/business portal draft and published subnet conflicts block initial planning. Complete live LAN/WAN/VPN conflict detection and revalidation before apply remain pending.

Plans snapshot management-only /32 peer addresses and routes, a generated interface name, endpoint/key and 25-second keepalive. They include required capability, address-conflict, backup/diff, peer-isolation, firewall/TLS, handshake and authorization checks. Guest internet/media traffic is not routed through the hub by this plan. JSON download is a review document, not an executable router script. SME review is recorded and audited exactly once, with an awaiting-adapter state; it does not apply configuration or establish connectivity.

Migration 006 preserves existing account/site/payment records and refuses downgrade if hub records exist. Verification: 47 Python tests, six JavaScript client/worker tests, four component-render checks and production build pass. PostgreSQL migration SQL generates through 006, but PostgreSQL runtime remains unverified. Local preview service restarts with the new migration. Authenticated/mobile browser journeys remain pending due to the previously observed blocked browser state; the Magic Hub static preview renders actual React components using sample records and disabled forms.

Still pending: live hub provisioning/agent authentication, signed connectivity evidence, router commands and capability discovery, backup/diff/apply/rollback, tunnel revocation/key rotation/hub migration, hub assignment removal, remote service authorization, discovered topology, WAN/Starlink enforcement, network accounting, protected Jellyfin playback, external payment dispatch, scoped theme publication and connected AI. These remain part of the original goal.

## Increment 9 — SME revenue reporting and cash ledger

Live router configuration and verification are deferred by the user. The original MikroTik, Magic Hub, WAN, captive-portal enforcement and telemetry requirements remain on the roadmap. This increment adds web-app financial reporting without requiring router/VPS access.

Guest-order approval/refund and voucher-counter receipt/refund now append unique financial events in the same transaction as their existing workflow changes. Each event captures tenant/site/source, positive amount, collection/refund kind, currency, service/package name, method/reference, reviewer and recording time. Replays never add duplicate collections. The ledger has no editing endpoint. Refunds subtract in their recording period rather than rewriting the original receipt period. A period can therefore have negative net collections. These are manually confirmed cash records, not independent bank verification, transfers, profit or tax accounting.

SME Revenue supports all-time or inclusive 1–366 day ranges, valid reporting timezones and all sites, one owned site, or business-wide/unassigned records. The selected site supplies the default timezone. KPIs include gross receipts, refunds, net collections, receipt count, average receipt, pending amount and reviews waiting over 24 hours. Service/source, business-site, payment-method and daily cash totals use event time; pending workload uses submission time and current pending status. Daily UI shows the most recent 31 active dates. Legacy compatibility count fields remain, but the new UI uses receipt/refund event counts.

The scoped ledger endpoint returns stable event/source identifiers, signed amounts, local timestamps, staff IDs and timestamp basis. UI shows the latest 100 events; CSV export reads up to 10,000 in one request and requires narrower dates if additional rows exist. User-controlled text is quoted and formula-neutralized; numeric negative refunds remain numeric. Large-scale SQL aggregation, reconciliation, expenses/profit, advanced KPI comparisons and export jobs are pending.

Migration 007 backfills approved/refunded guest orders from available audit times and actors. Missing historical event dates use explicitly labelled submission estimates; missing refund actors remain unknown. Existing voucher receipts/refunds use their stored event times. A warning appears for estimated historical dates. Backfill preserves payments/passes and refuses a downgrade that would discard ledger rows. Migration SQL also compiles for PostgreSQL; PostgreSQL runtime remains unverified.

Verified: 53 Python tests and eight JavaScript tests pass (61 total), five component checks pass and production build passes. Tests include cross-period refunds, Myanmar midnight boundaries, inclusive dates, invalid ranges/timezones, foreign site/role denial, pagination, site propagation for orders and voucher sales, immutable financial snapshots, legacy backfill/rollback protection and CSV formula handling. A static preview is rendered from the actual React components using labelled sample data with disabled controls. Local preview restarts with migration 007. Authenticated/mobile browser journeys remain pending because of the previously blocked browser state.

## Increment 10 — platform palette publication

Platform Appearance now edits the light ivory/evergreen and dark forest/sage palettes using five validated color tokens. Unsaved changes affect only the preview. Saving a draft does not change effective colors; publication applies the saved light/dark palettes to selected roles. Platform scope includes the shared account sign-in screen. Excluded roles receive the default palettes. Authenticated platform, SME and guest workspaces fetch only their effective palettes; draft/previous data stays platform-only. Public sign-in receives only the effective sign-in palettes, with no-store responses. Refresh or next sign-in picks up a publication; real-time push remains pending.

Revision checks protect draft saves, publication and restoration. Restore atomically replaces both draft and publication with the prior published configuration, including its role choices; the replaced publication becomes the next restore point. Initial publication can restore the original default configuration. Duplicate publication is rejected so it cannot erase that restore point. Saves/publishes/restores are audited. Business-specific branding overrides, version-history browsing, custom fonts/logos and scheduled publication remain pending.

Publication validates both palettes against 20 foreground/background pairs at 4.5:1: page, surface, mixed panels, primary links/buttons, secondary text, selected navigation and badges. Low-contrast drafts can be saved but cannot be published. The default secondary-text mix was adjusted from 66% to 70% text for the light palette. The UI and backend contrast checks match. This is validation of the listed pairs, not a complete accessibility audit; borders, focus, hover/disabled states, charts and every mixed element still require browser QA. Only six-digit hex colors are accepted, with no arbitrary CSS.

Migration 008 stores draft/current/previous appearance data and refuses downgrade if records exist. Verified: 61 Python tests and eight JavaScript tests pass (69 total), six component checks pass and production build passes. Tests cover role denial, private draft/public projection, role scope enforcement, bad CSS/color rejection, low contrast, concurrent initial saves, stale revisions, restores, duplicate-publication protection and migration preservation. PostgreSQL migration SQL generates through 008; PostgreSQL runtime remains unverified. Local preview restarts with 008. The static Appearance preview uses actual React components with labelled sample data and disabled controls; authenticated/mobile browser journeys remain pending due to the previously blocked browser state. Live router configuration and verification remain deferred.

## Increment 11 — media catalogue and hybrid sales policies

SME Media now maintains tenant-scoped title metadata: name, description, genre, runtime and optional release year. New titles start as drafts; guests only see published, non-archived titles from their business. Edits return a title to draft, while archive removes it from the published catalogue; restore returns it as a draft. Revision checks reject stale edits/state changes. Platform accounts have no implicit catalogue editing scope. There are no media files, stream URLs, server keys or actual playback connections in these records.

Packages supports timed library, one-title and hybrid library-plus-title policies. Hybrid has independent library hours and title hours, both intended to begin at verified activation. Combined internet/media retains a separate library window from internet limits. Title selection uses an owned active catalogue ID, with an immutable title name/runtime/year snapshot in package/order/voucher/pass history. Pricing remains in Packages, and confirmed receipts/refunds flow to the existing media revenue ledger. Single-title passes allow the chosen title for the configured window; playback-count/replay limits remain unimplemented.

New guest title purchases, approvals and voucher issuance require a currently published title. Media-only library sales require at least one published title. Title-row claims serialize relevant media sales with catalogue withdrawal. Internet+media combined packages remain available for their internet service even when the media catalogue is empty. Exact order/voucher retries preserve their historical record after withdrawal. Previously issued valid vouchers can still redeem their stored policy after catalogue withdrawal; this preserves the promise in the record rather than fabricating playback availability. Existing passes are not silently erased by catalogue editing/archive.

Guest Media browses published metadata, searches title/genre/description, shows offered media package windows and lists its own stored media passes with site identity. Playback is explicitly unavailable, and no activation or viewing clock is started by these screens. Withdrawn purchased titles are flagged as no longer listed. The catalogue is shared within a business; per-site media-source/availability mapping remains pending. Catalogue metadata/publication is separate from Jellyfin synchronization, protected file/segment access, artwork, upload/transcoding and media-server health.

Migration 009 preserves earlier financial/theme/site records, adds catalogue constraints and refuses downgrade with media records. Legacy unresolved title policies retain history but cannot make new title sales without an owned published catalogue record. Verified: 69 Python tests and eight JavaScript tests pass (77 total), seven component checks pass and production build passes. Tests cover catalogue role/tenant visibility, stale changes, archive/restore, invalid policies, foreign title IDs, independent hybrid/combined windows, immutable purchase history, media ledger revenue, withdrawn offer denial, empty-library sale denial, historical voucher redemption and migration preservation. PostgreSQL migration SQL generates through 009; PostgreSQL runtime remains unverified. The static media preview renders actual React components with labelled sample data and disabled controls. Authenticated/mobile browser QA and playback remain pending; live router configuration/verification are still deferred.

## Increment 12 — SME guidance and platform publishing

SME owners have a Did you know? sidebar page with searchable cards grouped by MikroTik, Internet access, Media and Business. Initial cards explain portal/HotSpot/RADIUS responsibilities, User Manager session licensing and WireGuard's role in Magic Hub. Each card carries a fact, business implication, requirements, related workspace page, source URL and source-check date. Router compatibility is explicitly not checked; no capability is inferred from registration or documentation.

Platform accounts alone create/edit/publish/withdraw/retire/restore cards through the Guidance page. Editing withdraws publication until another review and publish. Revision checks reject stale writes; all mutations are audited. Only published, non-retired cards reach authenticated SME accounts across businesses. Guests cannot access this global business guidance. Source links require HTTPS without embedded credentials; future verification dates and invalid action targets are rejected. Publishing records the operator's attestation, not an automated fact-check. Restoring retired content returns it to draft.

Explain with Magic Dude opens the existing floating assistant and displays the saved guidance; no model is connected. Contextual inline setting tips, multilingual cards, full editorial history and trusted router compatibility discovery remain pending. Local User Manager is an architecture option, not an implemented adapter; cloud and local quota state must have one authority per site before any failover is introduced.

Migration 010 adds global guidance and three reviewed initial cards. Downgrade permits removing pristine bundled cards but refuses to discard operator-created or modified content. PostgreSQL migration SQL generated successfully; PostgreSQL runtime remains untested. Verified: full 71-test Python suite passed, plus the newly added migration test in a passing seven-test migration suite (72 distinct Python tests); eight JavaScript tests and the guidance component render check passed; production build passed. Authenticated/mobile browser QA remains pending because the prior browser security block has not been bypassed. Static preview uses the actual components with disabled controls. Live router configuration and verification stay deferred.


## Increment 13 — protected guest-order receipt evidence

Guests attach JPEG/PNG payment receipts under My access after submitting an order; SME owners view the images in payment review. Reads require the exact purchaser or same-business SME owner; platform accounts, other guests and other businesses cannot view them. Receipts use authenticated byte requests rather than public URLs. Read/attachment events are audited. Temporary browser image URLs are revoked when closed, replaced or unmounted.

Up to three images per order, 5 MiB input and 8 million pixels per image. The server creates a lossless, orientation-corrected PNG without input metadata; original files are not retained. An original input hash supports upload-key retry safety. Animated images, SVG, HEIC and PDF are not supported. Private database blobs are a bounded initial implementation; deployment storage/retention/backup/abuse controls and object-store migration remain pending.

Uploads are allowed only while pending or awaiting additional evidence. Identical retries return the existing receipt after a decision; conflicting reuse is rejected. Each image increments an order receipt revision. Payment decisions atomically require the reviewed version so newly attached evidence cannot silently slip past a stale review. Attaching does not resubmit an evidence request, create revenue or grant access. Existing text-only orders remain compatible; the UI always sends its review version. Upload/delete-original behavior is stated beside the file input. No automatic receipt settlement verification exists.

Migration 011 protects receipt history from destructive downgrade and retains order constraints. PostgreSQL SQL generation succeeds; runtime/concurrency verification remains pending. Verified: 77 Python tests and nine JavaScript tests pass (86 total), receipt component render checks pass and production build passes. Tests cover tenant/guest/platform isolation, normalization and metadata removal, retry/conflict/count limits, invalid/oversized/over-pixel images, stale approval, attachment without resubmission or revenue, migration preservation and authenticated binary client behavior. Authenticated/mobile browser verification remains pending; no blocked browser route has been bypassed. Live router work stays deferred.


## Increment 14 — delegated external payment-review API

SME Integrations creates named Telegram/Discord/custom service credentials with a configured reviewer identity, 1–90 day expiration and read-only or read+decision permission. Creation requires explicit delegation. Secrets are returned/shown once; only hashes are stored. Owners can revoke their credentials with a reason. The API refuses revoked/expired tokens and tokens bound to an unavailable owner. Platform/guest accounts cannot create or inspect owner credentials. Provider labels do not prove a connection; no bots or messages are connected or sent.

Separate review-api routes expose same-business queues, full payment context, private receipt images and decisions. Context includes guest/site, immutable package/payment snapshots, destination/instructions, reference/text/images, duplicate warnings and current status. Metadata queries avoid loading image blobs. Decision callbacks require configured identity, permission, stable callback key, displayed context hash and receipt version. Changed evidence, new receipts or another decision require a refreshed review. The trusted adapter must verify the actual external platform user; the server records its configured identity claim and credential, not a claim of independent platform authentication.

Dashboard and service decisions share the same transaction. Approval records one entitlement and financial collection plus outbox/audit; the external action records credential/provider/label/identity, reason and result. Exact retries preserve that action/result, changed key reuse conflicts. Service tokens cannot access ordinary account APIs, ordinary account tokens cannot access service routes. Read-only permissions include private receipt viewing but no decisions. Delegated refunds, actual bot callback verification, notifications/dispatch/retries, PostgreSQL concurrency, support controls and real bot/browser acceptance remain pending.

Migration 012 preserves integration records on downgrade. The API contract is in backend/REVIEW_API.md. Verified: 84 Python tests and nine JavaScript tests pass (93 total); integration component render checks and production build pass. Tests cover full review context, tenant/role/token separation, hashed storage, expiry/revoke/owner disable, read-only decisions, identity mismatch, retry conflicts, stale text/image context, private receipts, request-more-evidence/reject/approve history, single entitlement/ledger/outbox effects and migration preservation. PostgreSQL SQL generation passes; runtime/concurrency and authenticated/mobile browser verification remain pending. Live router work stays deferred.


## Increment 15 — durable per-service payment events

SME owners can subscribe or pause future payment events per service credential. Payment submission, evidence requests/resubmissions, approval/rejection and refund commit immutable event snapshots and per-service deliveries in the same transaction. Repeated evidence rounds now have distinct event revisions; the old one-event-name-per-order constraint no longer blocks them. Exact submission/decision retries do not create more events. Previously stored events retain unknown snapshot/revision/time and are not auto-sent.

Services claim up to 50 events with 30–300 second leases, acknowledge success or report failure. Only lease-token hashes are stored. Completion retries preserve results; replaced/expired tokens cannot acknowledge another worker's claim. Backoff and a five-attempt retry cycle lead to failed status; SME manual retry resets the cycle, fences previous tokens and retains total attempt counts. Each subscribed service gets its own record. Paused or unavailable credentials cannot collect; existing queues remain for resuming. Queues attached to expired/revoked credentials need a future reassignment workflow.

SME Integrations displays the latest 100 delivery records, subscriptions, status, attempts, credential availability and last error, with failed-delivery retry and pause/resume controls. Claiming/acknowledgement record a service's handling report, not confirmed provider delivery. Delivery is at least once: downstream consumers must deduplicate stable event IDs after crashes. No provider messages are sent, no Telegram/Discord handler is connected, and full attempt/error history, lease renewal, queue reassignment and push dispatch remain pending.

Migration 013 preserves existing event records and protects new delivery/history from destructive downgrade. Verified: 89 Python tests and nine JavaScript tests pass (98 total); integration render checks and production build pass. Tests cover subscriber separation, acknowledgement retries, lease fencing/expiry, failure backoff and manual retry, cumulative attempts, repeated evidence event order/snapshots, paused/foreign/revoked credentials, no retroactive fanout and legacy/new event migration preservation. PostgreSQL SQL compilation passes; PostgreSQL concurrency/runtime and authenticated/mobile browser testing remain pending. Live router work stays deferred.


## Increment 16 — platform business onboarding and password lifecycle

Platform Businesses creates a business and its first SME owner with a one-time random temporary password, expiring after 24 hours. Owner usernames are normalized and unique. Request keys prevent duplicate creation; exact repeats return metadata without exposing the secret again. The tenant, owner, portal draft and audit/provisioning record commit together. Purchases and voucher login start disabled, and the portal is unpublished. No billing subscription or live router is created.

First-login owners must change the temporary password before accessing business APIs. The account UI shows only that required step and sign-out. Password changes verify the current password, require a different nonblank 12–256 character password, throttle wrong attempts and invalidate all browser sessions while returning a new token for the current browser. Existing users retain password hashes, roles and normal access through migration 014. All roles can rotate their password from Account. Ordinary password changes preserve existing independently delegated service tokens.

Platform operators can reset an SME owner with a reason and authority confirmation. Recovery preserves payment/voucher/revenue data and account active state, ends browser sessions, revokes review credentials and issues another one-time password. Only SME owners in the selected business can be targeted. Reset history records actor, owner, reason and time without plaintext passwords. Expired/lost handoff passwords require a new reset. No messages are sent, and the bootstrap platform account remains CLI-provisioned.

Subscription billing, owner/staff lifecycle, MFA/self-service recovery, pre-login guest onboarding and authenticated/mobile browser verification remain pending. PostgreSQL SQL compilation and migration preservation are checked; runtime/concurrency remain pending. Verified: the 94-case Python regression run and the updated five-case onboarding suite pass (95 distinct Python cases), along with nine JavaScript tests (104 total), onboarding component render checks and the production build. Coverage includes creation/replay/duplicate isolation, first-password API gate, temporary expiry, wrong-password throttling and recovery, hashed storage, all-session rotation, reset/service-key revocation and private reset history. Authenticated/mobile browser and PostgreSQL runtime/concurrency verification remain pending. Live router work stays deferred.

## Increment 17 — published guest site entry

SME site portal settings now expose a public guest link (`?guest_site=<site id>`). The entry API serves only published guest fields and active business packages, excluding private network settings. Guests can register with published revision/terms acceptance; the server fixes their tenant and guest role. Existing sign-in then selects that site and opens the established payment/voucher workflow. Usernames remain globally unique. Registrations are limited by direct client IP; forwarded addresses are not trusted. Registration creates a cloud account, not a HotSpot/RADIUS session. Guest identity verification, recovery, configurable signup policy, edge abuse protection and live captive browser testing remain pending. Business-wide anonymous registration is not yet offered.

New three-case API tests cover public projection, tenant/role assignment, terms and publication checks, duplicate names and registration limits. JavaScript tests, guest component render checks and production build pass. Full regression: 98 Python tests and nine JavaScript tests passed (107 total). PostgreSQL runtime/concurrency and authenticated/mobile browser QA remain pending. No live router changes were made.

## Increment 18 — continued non-live implementation

Implemented in sequence, without intermediate approval requests:

- Private, SME-scoped portal review ZIP export. Includes escaped published guest HTML, public guest content, current saved network draft, supplied HTTPS webapp origin and deployment checklist. Saved-revision conflicts, unpublished portals and unsafe origins are rejected. This is NOT a HotSpot install bundle and contains no executable RouterOS commands or NAS credentials. Origin reachability is not verified; business-wide export has no anonymous guest link.
- Atomic batches of 1–100 vouchers with retry keys, no partial issuance, immutable package snapshots and full codes returned once. Retry responses never recover full codes. Owner UI downloads a private printable sheet, warns about code secrecy and requires clearing the current sheet before issuing another batch. Stock filters support site, payment state, status, ID/package/code-ending search and seven-day expiry warnings. Filtered stock CSV excludes full codes and guest identity and neutralizes spreadsheet formulas. Cashier assignment, batch revoke and physical print/device QA remain pending.
- Own-account active-session listing and revocation, for all three roles. Other sessions can be ended individually or together with confirmation; current session is preserved. References do not expose bearer tokens/stored hashes. This is session management, not verified device/location history. Independently delegated service credentials are not revoked by this operation.
- Server-side, permission-scoped audit search with literal substring/exact action/actor/time filters and stable pagination. Owner UI exports the current result page with safe CSV cells. This is not a full audit backup or proof of external settlement/application.
- Site-scoped saved WAN plans: up to eight provider-labelled uplinks, enabled state, failover priority and balancing weights. Owners can define a data allowance, cycle, warning threshold and proposed notify/throttle/block action. Manual cumulative usage requires a dated reading in the cycle. Estimates use end-of-day readings and constant average usage; no Starlink allowance or restriction is inferred. No automatic telemetry, notifications or exhaustion action runs.
- Owner-authored manual topology: up to 30 devices and 100 labelled links, SVG layout, position editing and device/link removal. Router/AP/switch/media/upstream labels are plans, not discovery. Link endpoints, duplicate pairs and unique node IDs are validated. WAN/budget and topology share a compare-and-save revision to prevent lost updates.

Migration 015 adds saved site plans and refuses a destructive downgrade when plans exist. Verification: 109 Python tests and 15 JavaScript tests pass (124 total), seven new component render checks pass, PostgreSQL offline migration SQL compiles, and the production build passes. All live router changes and playback remain deferred. PostgreSQL runtime/concurrency, authenticated/mobile browser QA, external workers, subscriptions, staff lifecycle, MFA/recovery and operational deployment remain outstanding.

## Increment 19 — platform subscription records and staff authority

Platform operators can create immutable plans with their own price/currency/site/router allowances and assign a business's recorded state, period and reason. Assignment stores a plan snapshot and uses revision checks. SMEs can view only their own subscription. States include trial, active, past_due, suspended and cancelled; these are records, not verified settlement or enforced service cutoffs. Invoices, subscription payment review, proration, automatic renewal and plan-limit enforcement remain pending. No pricing was chosen for the user and no money was collected.

SME owners can create manager/cashier/technician staff with one-time 24-hour temporary passwords, mandatory password replacement and retry-safe creation. Server-side authorization checks every staff account request; frontend navigation and initial reads follow the same profiles. Managers handle business operations but cannot manage staff, delegate review credentials or access platform operations. Cashiers can view business revenue/orders, manually review guest payments, issue vouchers and record counter receipts; refunds/revocation are unavailable. Technicians can manage site/router/planning records and view guidance, without guest payment/order data. Technician audit reads are limited to their own actions. Existing SME owners retain their permissions.

Owner profile/active-state updates require a revision and reason, immediately invalidate staff sessions and delegated credentials, and retain business history. Owners can recover staff sign-in with an authority confirmation, issuing a new mandatory-change temporary password while preserving disabled state/profile. The latest reason is saved on the staff grant and action/actor/target/time in audit; full staff-reason history, invitation delivery, guest/self-service recovery, MFA and per-site staff scopes remain pending. Staff are excluded from the platform's owner list and owner-reset endpoint.

Migrations 016/017 preserve subscription/staff records; staff downgrade specifically refuses to remove grants and accidentally elevate SME staff to owners. Tests cover profile isolation, prohibited endpoints, payment approval/counter receipts, creation retry/conflict, disable/session invalidation, recovery/confirmation/disabled preservation, owner-list separation and downgrade protection. Subscription tests cover role/tenant isolation, snapshots, revision conflicts and date validation. Verification: the 115-case Python regression and updated four-case staff suite pass (116 distinct Python tests), along with 16 JavaScript tests (132 total), four component render checks, PostgreSQL offline migration SQL generation and the production build. PostgreSQL runtime/concurrency and authenticated/mobile browser verification remain pending. No integration workers, messages, live routers or playback were connected.

## Increment 20 — subscription payment review and authenticator security

Platform operators issue private payment requests with a fixed plan/price/currency snapshot, subscription revision, period, destination and instructions. SME owners submit payment method/reference/evidence. Staff and guests cannot access platform billing. Operators can approve after independently confirming receipt, request evidence, reject or void unpaid invoices with a reason. Approval atomically activates the specified subscription period and records invoice provenance; changed subscriptions or overlapping active periods block approval. Creation, submission and decision retries preserve one effect, including replaying older evidence submissions. Billing history and escaped printable payment requests are available. This records operator confirmation, not provider verification or money transfer. Image attachments, refunds, taxes/proration, reminders, automatic renewal, external notifications and enforced plan limits remain pending.

All account roles can optionally enroll a six-digit authenticator with their password and a ten-minute setup confirmation. Setup secrets use server-key encryption; ten recovery codes are hashed, shown once and consumed once. Used or older authenticator steps cannot be reused. Confirmation/disabling ends existing account sessions and returns a replacement token. Password resets preserve MFA. Guest and normal sign-in accept authenticator/recovery codes. Enrollment requires a separately configured MIKROMAGIC_MFA_KEY; no key is bundled in source. Key rotation, operator break-glass recovery, mandatory MFA policy, verified guest recovery and production security review remain outstanding. See backend/MFA.md for deployment requirements. Delegated service credentials remain independently managed.

Migrations 018/019 add billing/MFA records with downgrade preservation guards. Tests cover atomic billing/retry/isolation/stale review, RFC authenticator vectors, code replay, one-use recovery, session rotation, guest disable, encrypted storage, password throttling, enrollment expiry and missing key behavior. Empty migration round-trip and MFA record preservation pass. The 123-case Python regression passes, followed by the updated five-case MFA suite and one new migration test (125 distinct Python cases). Two component render checks, 17 JavaScript tests, PostgreSQL offline SQL generation and the production build pass. Local preview is restarted; authenticated/mobile browser QA and PostgreSQL runtime/concurrency remain pending. Live router enforcement and media playback remain deferred.

## 2026-10-10 continuation — fail-closed first-site acceptance coordination

The Owner/Admin Sites workspace now contains one ordered acceptance journey from
site details through Site Ready. Its read-only API derives progress only from
tenant-scoped durable records: registered router, Connected plan with ordered
handshake/management evidence, compatible authenticated pre-flight, and the
exact published local portal package. Owner-reported model/version never counts
as discovery. Staff, guest and cross-tenant access are rejected.

Migration 034 adds a durable proposal-only HotSpot portal plan. A plan can be
prepared only from a current Connected management path, a newer authenticated
identity-bound compatible pre-flight no older than 15 minutes, an explicitly
selected observed HotSpot server/profile already using HTTP-CHAP without
HTTP-PAP, and the exact published local package. It records the create-only
target directory, profile-directory diff, shared-profile impact, conflict and
storage rechecks, encrypted-backup prerequisite, exclusions and bounded
rollback. Owner review is revision-fenced and audited separately.

This still provides no RouterOS commands or write path and never contacts the
router. Owner review is not authorization for router access, a hardware window,
upload or apply. Verified backup/apply/rollback, local voucher enforcement,
temporary revenue-excluded test voucher, real-phone customer test and Site
Ready remain blocked.

Verification: 466 Python tests pass with 12 environment-gated skips; all 34
JavaScript tests, production build and Sites packaging pass. The API contract
is regenerated, and migration 034's model DDL compiles for PostgreSQL. Full
offline SQL generation remains unavailable because pre-existing migration 029
performs a data-dependent user lookup. The complete proposal/review journey was
verified against a fresh isolated SQLite database in the local browser with no
console errors. No existing application database, VPS, deployment, account or
router was changed.

## 2026-10-10 public-test packaging continuation

A new isolated public-test Compose project and deterministic artifact now carry
the current source through migration 034 without modifying the accepted private
RC. The database/API publish no host ports; only web may join a separately
verified existing ingress network. RouterOS remains disabled and no credentials
or worker are included. The deployed artifact SHA-256 is
`4e78bae98d394fe40bcff6ce332282d212047247a21063c026b68ff0d4d79e93`.

Local verification passes: 467 Python tests (12 environment-gated skips),
deterministic packaging, Compose rendering, API/web image content checks,
production frontend build and four Sites packaging tests. All three public-test
images build locally.

The public-test project is deployed on Hostinger VPS 2032937 at
`/opt/mikromagic-build21-public-test-20261010`. Migration 034 and all three
containers are healthy. Existing Caddy routes the apex and `www` hostnames to
the new web alias without publishing the database or API. Mac-side HTTPS,
readiness, security headers and real-browser sign-in rendering pass with no
console warnings or errors. Browser acceptance found and removed the
development-only demo entry point from the production build.
One isolated platform test account was created with a 24-hour temporary
password and mandatory first-sign-in password change; no credential is stored
in source, status documents or deployment evidence.

Rollback evidence is stored in
`/opt/mikromagic-public-test-rollback-20261010T0335Z`; unrelated VPS services
were not stopped or replaced. The local Lima development VM remains stopped,
and Hostinger still exposes no usable whole-VPS backup or snapshot.

## 2026-10-10 dedicated Magic Hub deployment

A dedicated fail-closed WireGuard Hub agent is implemented in this corrective
copy. It owns one fixed interface and private `/24`, exposes its authenticated
peer-control API only on the Compose-internal network, persists only peer
public keys and `/32` assignments, and supports idempotent provision, observe,
revoke and live identity readback. The application accepts this adapter only at
the exact internal service address and enables production pairing only when all
dedicated-agent feature gates are explicit. Hub-list responses report
`identity_verified` or `peer_control_ready` from live identity readback, while
`connection_verified` remains false until real handshake and authenticated
router-management evidence exist.

The Hub container is read-only, unprivileged, limited to `CAP_NET_ADMIN`, uses
`/dev/net/tun`, has no public management port, and publishes only its configured
WireGuard UDP socket. Local image build and a real Linux container smoke test
passed: the interface initialized, generic health and authenticated identity
readback succeeded, and no host port was published during the smoke test.
Focused Hub tests pass, the production frontend and four Sites packaging tests
pass, and the full Python regression is 475 tests passing with 12
environment-gated skips. The deterministic 147-file deployment artifact is
`release/mikromagic-build21-public-test.zip`, SHA-256
`628825938079ca19395a20fd32199b16bc7dce3daf90af6918eb1c90baffc4b1`.

The verified artifact is deployed from
`/opt/mikromagic-build21-public-test-hub-20261010T143844Z`. PostgreSQL, the
dedicated Hub, API and web are healthy. The Hub is registered once in the live
database with a matching live agent identity and an audit event; there are no
tenant assignments because no tenant, site or router records exist yet. Backend
readiness is `peer_control_ready`, while `connection_verified` correctly remains
false until a real router supplies a fresh handshake plus authenticated,
identity-bound RouterOS management evidence.

The Hub survived a controlled restart with the same registered identity. UDP
51820 packets were observed arriving from outside the VPS both before and after
the restart. Host UFW permits the WireGuard UDP port, Docker binds only that UDP
port for the Hub, and the internal management port is not publicly reachable.
External `/v1/health` and `/v1/ready` return HTTPS 200 with valid TLS; live
browser sign-in renders with no console warnings or errors. All unrelated
containers remained running. Pre-Hub image tags, the prior release directory,
the existing Caddy rollback bundle and a protected pre-registration Hub-table
dump are retained. The physical MikroTik was not contacted or changed.

**HUB READY: READY for tenant/site/router enrollment.** This is not a router
connection claim and is not physical MikroTik acceptance.

## 2026-10-10 software-only continuation — guest access diagnosis

Physical MikroTik testing is deferred because the device cannot currently be
powered on. The Hub remains ready for enrollment, while Connected and hardware
acceptance remain unclaimed.

Guests now receive an authenticated, account-owned access diagnosis rather
than only raw order/pass rows. The result distinguishes payment review,
additional-evidence requests, rejection, revocation, stored quota exhaustion,
provisioning pending and locally recorded activation. It never searches by a
voucher code or exposes voucher hashes; a redeemed voucher is identified only
by its final four characters. Stored usage is labelled as not router verified,
and the UI explicitly reports that live RouterOS session/accounting evidence
and freshness are unavailable. Each state provides a bounded safe next action
without telling the guest to pay or redeem again.

Verification: the full Python regression passes 477 tests with 12
environment-gated skips; all 34 JavaScript tests, the production frontend build
and four Sites packaging tests pass. The OpenAPI contract was regenerated. The
deterministic 149-file deployment artifact is
`release/mikromagic-build21-public-test.zip`, SHA-256
`65145710483f7e68c07b72effa8f463ceae26b0e9a95cd882d74d2f25f7c9b91`.
This artifact has not been deployed; the running public test and VPS data were
not changed in this continuation.

## 2026-10-10 offline continuation — Stage 2 transport reconciliation and stale-document corrections

Documentation and read-only analysis only. No application code, migration, test,
database, deployment, VPS, Lima VM, router or historical WireGuard state changed.

Fresh read-only Mac/VM checks reconciled the transport-only Stage 2 plan in
`docs/MAGIC-CONNECT-TRANSPORT-LAB.md`. Readiness remains **NO**:

- `mikromagic-wg-dev` is Stopped after a `VirtualMachineStateError` on
  2026-10-09 21:19; the boot unit has never run.
- The VM's UDP 51821 forward is pinned to `192.168.100.213`, but the Mac Wi-Fi
  address is now `192.168.100.248`. The forward must be re-pinned (one exact
  `limactl edit --set` command) before any start.
- A full-tunnel VPN now owns the Mac default route; the router subnet still
  routes over Wi-Fi. Inbound LAN UDP behaviour under the VPN is unproven.

The selected development-only path is the shared Wi-Fi LAN to the Mac's Wi-Fi
address and the Lima user-mode forward, with the router initiating so its
existing established/related rule carries replies. The Hostinger public-test Hub
(the historical peer's target), a `0.0.0.0` forward, privileged Lima networking
and direct Ethernet were rejected with reasons. The document now lists the exact
approvals A1–A4, adds historical-path and `10.254.0.0/24` overlap checks to the
stop gate, and states that the result is Transport Verified, never Connected.

`docs/MAGIC-CONNECT-D1-S1-READONLY-FEASIBILITY.md` now maps the 2026-10-09
Stage 1 observations to the D1/S1 prerequisites: HTTPS REST is absent
(`www-ssl` disabled, no certificate), plain HTTP is enabled, and no distinct
Monitoring/Safe Change identity exists. It lists the remaining software, owner
decision, read-only and router-write prerequisites separately.

Owner/Admin authorization review: a throwaway probe against the temporary test
fixture database showed that a legacy `manager` staff account can create a
router plan (201) and perform the owner's initial bootstrap review (200), and
passes authorization for post-connection pre-flight, WireGuard evidence and
Safe Change preview (409, stopped only by lifecycle state). Hub peer
provisioning stays owner-only (403). The findings and a proposed correction
are recorded in `REQUIREMENTS-GAP.md`; the correction is **not implemented**
and needs implementation authorization plus an owner decision on existing
staff sessions.

Stale documentation corrected: the password/recovery policy row (⚠️ → ✅,
already implemented by migration 029), signed-in devices/login history
(🟡 → ✅, migration 033), Safe Demo presentation (⚠️ → ✅, development-only
entry), the account-policy summary row, and two stale rows in
`V1-REQUIREMENTS-MAP.md` (MFA as a next step; duplicate firmware row).

Verification: the full Python regression passes 477 tests with 12
environment-gated skips, and all 34 JavaScript tests pass (the four Sites
worker tests ran against the existing `dist/`; `npm run build` was not rerun).
The source manifest was regenerated by the documented procedure after these
documentation edits.

Unresolved and not selected here: the recorded Hostinger public-test deployment
versus the frozen-production instruction, and the `megamagic.tech` versus
`mikromagic.com` domain disagreement. Plaintext credentials found in local files
outside this project were flagged to the owner for relocation and rotation;
none was read into this project or used.

## 2026-10-10 — legacy staff frozen; Stage 2 offline rehearsal (A1–A3)

Supersedes the readiness and Owner/Admin statements in the previous section.

Owner/Admin fix implemented with the owner's choice to deny all legacy staff
requests. Legacy staff can only call `/v1/me` and sign out, and they see one
"Staff access closed" page. `POST /v1/staff` returns 410. The owner can still
list, disable and reset legacy staff. `owner()` and router evidence access now
exclude staff as defense in depth, and platform access is unchanged. There was
no migration and no data change, staff records and audit history are kept,
and the OpenAPI contract is unchanged. Details and test coverage are in
`REQUIREMENTS-GAP.md`. The probe findings above (manager 201/200/409) no
longer hold: every listed action now returns 403 for every staff profile.

Approved Lima steps A1–A3 ran (no router, VPS or historical WireGuard change):
A1 re-pinned the UDP 51821 forward to `192.168.100.248` (backup of the previous
`lima.yaml` kept beside it); A2 started `mikromagic-wg-dev` and the boot unit
brought `mm-dev-hub` up; A3 delivered Mac-to-guest UDP through the forward.
Offline transport readiness is now **YES, subject to the window gate** in
`docs/MAGIC-CONNECT-TRANSPORT-LAB.md`. Before A4 the owner still decides how
the full-tunnel VPN is handled, and the Mac must still hold `.248`. The VM was
left running.

Verification: 479 Python tests pass with 12 environment-gated skips; all 34
JavaScript tests pass; `npm run build` then `npm run test:sites` (4/4) and
`npm run test:ui` pass. The source manifest was regenerated after these edits.

## 2026-10-10 — Hostinger VPS handover (read-only)

`MIKROMAGIC-HOSTINGER-HANDOVER.md` inventories the Hostinger VPS
(`srv2032937.hstgr.cloud`, `156.67.216.128`) from project documents, repository
configuration and anonymous public checks only. No SSH, Hostinger panel/API,
port scan, WireGuard probe or VPS change occurred. Publicly verified:
`megamagic.tech` and `www` resolve to the VPS, have valid Let's Encrypt
certificates (expiring 2027-01-06) with HSTS and security headers, and
`/v1/health` and `/v1/ready` return 200. Key findings are listed below.

- The deployed public test predates the staff freeze and the guest access
  diagnosis.
- Pairing and Hub peer writes are enabled by configuration, but no API → Hub →
  router management path or RouterOS credential mount exists.
- There is no off-host backup or snapshot, and Hub key escrow is undocumented.
- The local public-test ZIP hash matches no documented digest.
- `mikromagic.com` is still live behind Cloudflare.

The exact read-only access and commands needed for a live verification are
listed in the handover.

## 2026-10-10 — Hostinger is production; live verification, fixes and redeploy

Owner decisions:
- Production is this Hostinger VPS (`megamagic.tech`).
- Z.com and `mikromagic.com` are discontinued.
- Live verification, credential rotation and redeployment are approved.

Live verification fixed three problems:
- The Magic Hub port was never published, because the Hub sat only on an internal Docker network. Fixed with a `hub_uplink` network; the Hub key is unchanged and it has 0 peers.
- The database password file was world-readable inside containers. It is now split into separate database and API copies with restrictive ownership.
- An undocumented deploy of `6514…` at 15:07 UTC was found.

Current source `4092ce1da282388f…` is deployed in
`/opt/mikromagic-build21-public-test-20261010T171319Z`:
- Rollback image tags and a pre-deploy dump exist.
- All containers are healthy and HTTPS returns 200.

Access, backups and escrow:
- SSH now uses a single new dedicated key, and password login is disabled.
- Old keys and plaintext credential files were retired.
- A nightly restore-verified backup runs on the VPS, and a daily checksum-verified pull copies it to the Mac.
- The Hub private key and the backup key are escrowed in the Mac Keychain.

Connected is still impossible here until the management path and D1/S1 exist.
Full details are in `MIKROMAGIC-HOSTINGER-HANDOVER.md`.

Production monitoring (2026-10-10):
- A Mac launch agent, `tech.megamagic.production-monitor`, checks site readiness, certificate expiry, container health, Hub port publication, VPS backup result, disk and off-VPS backup age every 30 minutes.
- It notifies on change and on recovery.
- The failure path was tested with notifications stubbed.
- The router-window plan now includes the owner-approved disable-then-delete retirement of `mmh-8adfeb441215`.

## 2026-10-10 — Voucher code rules (frozen v1)

Implemented the frozen voucher-code rules without hardware.

New codes:
- An optional SME prefix plus a secure 6-character suffix, avoiding O/0 and I/1.
- Case-insensitive matching that ignores spaces and hyphens.
- VIP packages allow one custom code at a time.
- Hashes are scoped per business, so uniqueness is enforced within the SME without colliding across businesses.

Compatibility:
- Migration 035 adds `code_format` and `code_prefix` to vouchers.
- Existing codes are marked `legacy` and keep working; their hashes are unchanged.

Screens:
- Package editor has a VIP option.
- Single and batch issue have a prefix field; single issue also has a VIP custom-code field.
- Inventory, stock and cashier lists show the prefix.
- The redeem field accepts short codes.

Verification:
- 487 Python tests (12 skipped), 34 JavaScript tests, the build, Sites 4/4 and UI checks pass.
- A local browser check on a scratch database covered a VIP package, a prefixed batch and a custom VIP code.

Not deployed to production yet.

## 2026-10-10 — Voucher lifecycle (frozen v1)

Implemented Delete, Disable, Re-enable and Revoke as the frozen states, without hardware. Migration 036 adds `disabled_at`, `disabled_reason`, `deleted_at` and `router_sync` to vouchers (all nullable; downgrade refuses while any voucher is disabled or deleted).

Behaviour:
- Delete: only unused, unsold vouchers. Soft delete, hidden from inventory; audit history stays.
- Disable: requires a reason; works on unused or activated vouchers. Blocks redeem, counter sale and offline events. Guest diagnosis shows access paused.
- Re-enable: restores the voucher with its existing entitlement and history.
- Revoke: permanent; cannot be re-enabled or deleted.
- No Reset action. Every action is audited.
- Each action records the pending router action; staff see "Router update pending · no router connected yet". Nothing is sent to a router.

Screens: the voucher inventory has an Actions column with a reason field, Disable, Re-enable, Delete unused and Revoke permanently. The stock explorer has a Disabled status filter.

Verification:
- 493 Python tests (12 skipped), 34 JavaScript tests, the build, Sites 4/4 and UI checks pass.
- Local browser check on a scratch database: Disable with a reason and Re-enable both persisted.

Still open: pushing these actions to RouterOS (with active-session kick on disable) and the Block Client cascade. Not deployed to production yet.

## 2026-10-11 — Voucher production jobs, printing and templates (frozen v1)

Implemented the frozen Voucher Production Job flow without hardware: Profile → Quantity → Coverage → Dealer → Print layout → Preview → Generate → Print → Verify → Distribute.

Data (migration 037, additive):
- `voucher_production_jobs` and `voucher_templates` tables.
- Vouchers gain `serial_no` (unique per business), `production_job_id` and `sheet_no`.
- Downgrade refuses while any job, template or serial exists.

Behaviour:
- A draft stores settings only. Codes are generated only after the owner ticks the confirmation and presses Generate; they are shown once and stored as hashes.
- Serial numbers continue across jobs within a business. They identify stock and never log anyone in.
- The first multi-sheet run of each layout requires the fake-code calibration page to be confirmed.
- The owner marks each sheet or thermal run printed or failed. Only failed sheets can be reprinted, with a reason and a REPRINT label and duplicate-copy warning, and only while the codes are still on screen.
- Marking a sheet lost disables just its unused vouchers (pending router disable) and recommends a replacement job.
- Distribute records a note; dealer assignment arrives with dealer management.
- Magic Voucher Templates prefill quantity, layout and redeem window only. Owners can save and archive My Templates.

Printing: A4 Ultra Economy (60), Economy (40), Standard (24), Premium (10), custom up to 8×16, and 58/80 mm thermal runs of 25. Sheets carry Batch ID, Sheet x/y and serial range. QR stays off until a verified guest portal address exists.

Verification:
- 499 Python tests (12 skipped), 39 JavaScript tests, the build, Sites 4/4 and UI checks pass.
- Local browser walk-through on a scratch database: template, draft, calibration, Generate 130 codes (serials 000001–000130), print verification with a failed-sheet reprint, distribution, My Template, and serial search. The downloaded reprint sheet showed 60 cards per A4 page with the correct batch, sheet and serial label.

Not deployed to production yet. Real paper output is unverified.

## 2026-10-11 — Dealers and physical voucher stock (frozen v1)

Owner-managed dealers with no dealer login, app or portal (migration 038, additive; `backend/dealers.py`, `src/Dealers.jsx`, `src/dealers.mjs`).

- Dealers: name, location, phone, optional short code printed on sheets, Prepaid or Credit settlement, optional credit limit, archive.
- Stock: hand over unused vouchers by serial range or everything left in a production job at a dealer price; return to stock with credit, or move to another dealer; stock check with Lost / Damaged / Counting difference / Other and optional disabling of missing vouchers.
- Money: an append-only dealer ledger (stock charges, return credits, payments by Cash/KBZPay/WavePay/Other, corrections, reversals). It is separate from counter-sale revenue; dealer-held vouchers cannot be sold at the counter or deleted.
- Ranking by activated vouchers (not sales) with a low-stock hint the owner acts on.
- Production jobs: the Dealer step is live; Distribute can hand the job's remaining unused vouchers to a dealer.

Verification: dealer tests (5) and helper tests (5) added; full Python suite, 44 JavaScript tests, build and Sites 4/4 pass. Local browser walk-through on a scratch database: two dealers, prepaid refusal then payment and handover, job handover of the 25 available cards, stock check with 2 lost and disabled, return with credit, ledger and ranking.

## 2026-10-11 — Voucher sale payment methods and Cancel Sale (frozen v1)

Counter sales record how the customer paid, and a mistaken sale can be cancelled without losing its history (migration 039).

- Paid with: Cash, KBZPay, WavePay or Other. KBZPay and WavePay need the wallet transaction ID; Other needs a short description; Cash needs nothing extra. Older free-text methods still display.
- Cancel Sale (owner only): for a sale whose voucher is unused and not refunded. It needs a reason and the confirmation "No money was kept for this sale". The sale stays in history, revenue is reversed, an audit record is written, and the voucher returns to unsold stock and can be sold again. Used vouchers still need a refund, which revokes the pass.
- Revenue: "Refunds & cancelled sales" metric, cancellations included by site, payment method and day, and "sale cancelled" in the ledger.
- Vouchers: the Payment column shows the method and a cancelled count; the sale panel lists cancelled sales.

Verification: new backend tests for payment-method rules and Cancel Sale (history, revenue reversal, resale, refusals), dealer handover after a cancelled sale, migration downgrade guard; 3 new JavaScript helper tests. Local browser walk-through on a scratch database: Cash sale, Cancel Sale, KBZPay resale blocked until a transaction ID was entered, then recorded; Revenue showed net MMK 1,500 from MMK 3,000 gross with the Cash sale cancelled.

## 2026-10-11 — Shop setting: default printed Wi-Fi name (frozen v1)

Each shop (site) can store an optional default Wi-Fi name to print on voucher cards (migration 040, additive; `POST /v1/sites/{id}/settings`, owner only, audited as `site_printed_ssid_updated`).

- Sites page: a "Printed Wi-Fi name" column, a Shop settings panel, and an optional field when adding a site. Names are limited to 32 bytes like a real SSID; the form explains that Burmese letters use about 3 bytes each.
- Production jobs: choosing a shop fills in its Wi-Fi name ("From this shop's settings"); switching shops replaces it only if the owner has not typed their own. Business-wide jobs keep the typed value.
- Batch sheets and Quick Voucher cards show "Wi-Fi: <name>" for vouchers of a shop that has one.
- The name is a printed label only; it does not change any router or access point.

Verification: backend test for the setting (owner only, tenant isolation, byte limit with Burmese text, control characters, clearing, audit), migration 040 up/down with a downgrade guard while names are set, 3 JavaScript tests. Local browser walk-through on a scratch database: over-long Burmese name refused with the byte count, name saved, production form prefill and switching, Quick Voucher card showing the Wi-Fi name.

## 2026-10-11 — Platform console for the platform owner (owner request)

The owner asked for a "Platform console" tab, visible only on their own platform account, that lists sign-in sessions. Migration 041 (additive) adds `users.platform_owner` (default false). It is set only by trusted server-side provisioning and honored only for the platform role; no API can set it.

- `GET /v1/platform/console/sessions`: every unexpired session on the platform with account, role (staff shown as staff), business, device/browser labels, login and last-active times, masked approximate source and expiry. Tokens and session references are not returned.
- `GET /v1/platform/console/sign-ins`: past 7 days of sign-ins, sign-outs and ended sessions (from the audit log) plus failed sign-ins (from login history). Device details are joined from login history where one was recorded.
- Platform-account sign-ins now also write login history rows (device/browser, approximate source, success/failure); they are shown only in the Platform console. Staff, guests and unknown usernames still get no row.
- `/v1/me` returns `platform_owner`; the workspace adds the Platform console tab only when it is true. Both endpoints return 403 for every other account, including other platform accounts.

Verification: `test_platform_console` (4 cases: access limited to the flagged platform account, cross-account session listing without tokens, platform sign-ins/failures/sign-outs with device details and no secrets, 7-day retention), migration 041 up/down on SQLite. Local browser walk-through on a scratch database: a second platform account has no tab; the owner account sees the tab, all active sessions and its own failed and successful sign-ins.

## 2026-10-11 — Daily voucher counts per shop and for all shops (frozen v1)

Frozen v1: "Daily revenue, voucher count and payment-method breakdown support per-shop/all-shops views." Revenue already had daily money, a payment-method table and a shop filter; voucher counts and a per-day method split were missing.

- `GET /v1/revenue` adds `vouchers_sold`, `vouchers_cancelled` and `vouchers_refunded` overall and in every `by_day`, `by_site` and `by_method` row, plus `methods` (net per payment method) in each `by_day` row. Counts come from counter-sale financial events only: generated, unsold or redeemed vouchers are never counted as sold. A Cancel Sale and a refund are counted separately on the day they were recorded.
- Revenue page: "Vouchers sold" and "Vouchers cancelled / refunded" metrics; both columns in the shop, payment-method and daily tables; a "Net by payment method" column per day; a **Today** button using the reporting timezone; a hint that the all-shops view combines shops.

Verification: backend test with two shops, four payment methods, a cancelled sale, a refund and an unsold voucher (all-shops totals, per-shop, per-method, per-day methods, single-shop filter); 3 JavaScript tests (timezone-correct Today, method summary, combined returns); the revenue UI check covers the new columns and button. Local browser walk-through on a scratch database: Today for all shops (7 sold, 1 cancelled, per-shop split 4/3, methods Cash/KBZPay/WavePay) and for one shop (3 sold).

## 2026-10-11 — Batch QR on voucher sheets and thermal runs (frozen v1)

Frozen v1: "Batch QR opens the exact batch using only a safe reference and requires signed-in Owner for sensitive actions."

- New print setting **Print a batch QR on each sheet**, on by default, saved with production jobs and My Templates (`print_settings.batch_qr`). No migration: print settings are stored as JSON.
- Each A4 sheet header carries a 12 mm QR beside the business name; each 58/80 mm thermal run carries one before its run label. Caption: "Owner: scan to open this batch (sign-in required). No voucher codes inside."
- The QR link is `https://<app>/?batch=<job id>&sheet=<n>`. It holds no codes, serials or tenant data, and is generated only on HTTPS (or local development).
- Opening the link: signed out shows "Sign in as the business owner to open the voucher batch you scanned."; the Owner/Admin lands on Vouchers with that exact job open, the sheet row highlighted and the message "Nothing was changed". Another business sees "This batch QR does not belong to this business, or the batch no longer exists." and no data. Platform, guest and staff accounts are told batch QR codes open only for the business Owner/Admin. The link is removed from the address bar after use.
- Guest QR on vouchers stays off until a verified guest portal destination exists on a router; the print preview says so.
- The calibration page shows a dashed batch-QR slot so the test print matches the real header. With the QR on, the A4 header is 13 mm instead of 6 mm, so cards are slightly shorter.

Verification: backend test (default on, off kept on job and detail, template keeps it, invalid value rejected, other business 404); 4 batch-link and 1 sheet JavaScript tests; full suites green (514 backend, 58 JavaScript, voucher and revenue UI checks). Local browser walk-through on a scratch database: signed-out hint, wrong business refused, owner opened the exact older job with sheet 1 highlighted, rendered 40-voucher Economy sheet shows the QR in the header. Scanning a printed sheet with a phone is unverified.

## 2026-10-11 — Shop business hours, network operating hours and planned maintenance (frozen v1)

Frozen v1: "Site has separate Business Hours and Network Operating Hours (same as business hours / 24×7 / custom)", expected shutdowns during closed/network-off hours do not alert, and "Planned Maintenance Mode supports timed 15m/30m/1h/custom maintenance, optional reason, continued monitoring, suppression of expected outage/uptime penalties, visible countdown, extension, and automatic post-maintenance Magic Check."

- Migration 042 (additive): `sites.business_hours`, `sites.network_hours_mode` (default `always`), `sites.network_hours`, `site_incidents.expected_reason`, new table `site_maintenance`.
- `backend/site_hours.py`: `GET/POST /v1/sites/{id}/hours`, `POST /v1/sites/{id}/maintenance`, `/maintenance/{mid}/extend`, `/maintenance/{mid}/end`; Owner/Admin only, tenant-scoped, audited. One running window per shop, 24 h cap including extensions. A window whose time ran out is closed on the next read with its Magic Check.
- Incidents: an outage that starts inside a maintenance window (including a past one recorded later) is stored as `maintenance`; one that starts while network hours say off is `network_off_hours`. MikroMagic cloud (`control_plane`) outages are never expected.
- Magic Check after maintenance reports only held evidence: with no verified router connection it says the network could not be checked and lists still-open incidents.
- Sites page: weekly hours editor (closed days, past-midnight closing, copy Monday), network mode, now open/closed and network on/off in shop time; maintenance start, live countdown, extend, end, history and last Magic Check. Overview "Needs Your Attention" lists running maintenance (English and Burmese).
- Not done (needs live monitoring/notifications): automatic Opening Check, push-alert suppression, uptime penalties. Hours do not switch the router or Wi-Fi.

Verification: 5 backend tests (overnight/all-day/closed schedule maths, validation and tenant isolation, maintenance start/extend/end/audit, self-closing window, expected incidents) and 4 JavaScript tests; full suites green (563 backend incl. inherited, 62 JavaScript, voucher and revenue UI checks). Migration upgrade, downgrade and re-upgrade on SQLite. Local browser walk-through on a scratch database: saved hours (Sunday closed → "Closed now", network planned off), started, extended and ended maintenance, Overview listed it, an outage during maintenance was labelled expected and one at another shop was not, and a window that ran out closed itself and showed the Magic Check.

## 2026-10-11 — Magic Support Mode / Get help (frozen v1)

Frozen v1: "Magic Support Mode / Get Help creates a safe diagnostic report with site/device status, outage duration, recent event and evidence-based likely cause. Never include passwords, voucher secrets, API credentials or WireGuard private keys. Full remote support control is later."

- Migration 043 (additive): table `support_reports` (immutable report JSON, optional `shared_at`).
- `backend/support_report.py`: `POST/GET /v1/sites/{id}/support-reports` (Owner/Admin), `POST /v1/support-reports/{id}/share` (Owner/Admin), `GET /v1/support-reports` (platform accounts, shared reports only). Audited `support_report_created` / `support_report_shared`.
- Report content, allow-listed: business and shop, the owner's description, open/closed and network on/off now, running maintenance, owner-reported routers with the recorded Magic Hub evidence (handshake, management read, lock), switches/APs, open outages and those closed in the last 7 days with durations and confirmed/suspected causes, the last 15 audited actions on that shop's records (name and time only), and likely causes each labelled with the evidence used.
- Never included: passwords, voucher codes, API credentials, WireGuard keys, router addresses, router public keys, payment details. Free text is scrubbed of password/token/key patterns and of this business's real voucher codes (checked against stored hashes, also when typed with spaces or hyphens).
- UI: new owner page **Get help** (English/Burmese menu label), reachable from the Overview health card; report with likely causes, full text, Copy, Download .txt, Share with MikroMagic support, and history. Platform Operations page lists shared reports read-only.

Verification: 3 backend tests (redaction of spaced/hyphenated codes, passwords, keys and tokens; evidence-based causes with durations, maintenance and router evidence; sharing, tenant isolation and platform read-only inbox) and 3 JavaScript tests; full suites green (610 backend incl. inherited, 65 JavaScript, voucher and revenue UI checks). Migration upgrade/downgrade/upgrade on SQLite. Local browser walk-through: Overview Get help → report removed a real voucher code typed as "7gmm 98" and a Wi-Fi password; shared it; the platform account saw only the shared report.

## 2026-10-11 — Public interactive Demo (owner decisions Q16–Q19)

Owner decisions: Demo view before payment (Q16); interactive with sample data, isolated from real SMEs, production data, payments/subscriptions and routers, no live voucher credentials (Q17); open to everyone without account, sign-in or payment (Q18); changes discarded on exit, every visit starts fresh (Q19).

- `src/demo-api.mjs`: in-memory client with the same interface as `accountClient`; it never calls `fetch`. Seeds "Golden Cafe (demo)" with two shops (Downtown with hours, Riverside), a registered unverified router, four packages, eight vouchers with counter sales, two approved and two pending guest orders. Implements the owner flows used by the demo pages with the real response shapes (issue/batch/sale/cancel/refund/disable/enable/revoke/delete vouchers, packages, sites and Wi-Fi name, hours and maintenance with Magic Check, routers, payment decisions and refunds, revenue/ledger/cash close computed like `backend/revenue.py`, help reports with code/password scrubbing). Everything else answers "Not available in the demo — nothing was changed."
- Demo mode in `src/AccountWorkspace.jsx` and `src/App.jsx`: **Try the demo** panel on the sign-in page (production builds too) and `?demo=1`; signs in a sample owner automatically; menu limited to Overview, Revenue, Sites, Routers, Packages, Vouchers, Payments, Get help; banner (English/Burmese) and Exit demo; voucher production, dealers, first-site acceptance, router onboarding/Magic Connect/router changes are hidden; help reports cannot be shared. Each entry remounts with a fresh client.
- Voucher codes are `DEMO-XXXXXX` (`DEMO-PREFIX-XXXXXX` with a prefix) and exist only in the browser tab.
- Fixed: the Revenue **Cash reconciliation** save sent `{method,body}` as the JSON body and the API rejected it (422); it now sends the fields directly. `scripts/verify-revenue-ui.mjs` guards against the wrapper.

Verification: 8 JavaScript tests (`tests/demo-api.test.mjs`: no network calls across the full owner load and actions, DEMO codes, fresh data per visit, revenue/approval/refund/cash-close maths, refused actions leave state unchanged, scrubbing, overnight hours, menu limits); full suites green (610 backend incl. inherited, 73 JavaScript, voucher and revenue UI checks). Local browser walk-through: Try the demo and `?demo=1` opened the workspace with zero `/v1/` requests; quick voucher, cash close (variance shown), payment approval, maintenance start/extend/end, help report (typed demo code removed, no share button), batch issue; Exit demo returned to sign-in and re-entry showed the original sample data.

## 2026-10-11 — Subscription self-service and renewal rules (owner decisions Q9–Q15)

Owner decisions: no SME staff accounts (Q9); SME Owners request subscriptions and renewals with payment evidence, the platform owner approves manually (Q10); in-platform warning 7 days before expiry and renewal-only sign-in from the expiry date, no grace period, guest internet untouched (Q11/Q12); approval reactivates immediately (Q13); early renewal adds to the current expiry (Q14); renewal after expiry starts on the approval date (Q15). Terms are monthly or annual to match the Agent commission rates in Q20–Q22.

- Migration 044 adds `platform_settings` (key/value with revision). The `subscription_payment` key holds the platform's receiving account, instructions and accepted methods; only the platform owner reads or saves it (`/v1/platform/subscription-payment`, revisioned, audited).
- `backend/subscriptions.py`: calendar rules in Asia/Yangon. The expiry date is the local date of `period_end`; the warning shows when 1–7 days are left; restriction starts at local midnight of the expiry date. Terms end at local midnight N months after the start, clamped to the month's last day. `/v1/subscription` now returns `expires_on`, `days_left`, `warning`, `restricted`.
- `backend/subscription_renewal.py`: `GET /v1/subscription/plans` (paid plans, terms, payment details, current subscription) and `POST /v1/subscription/requests` (plan, 1 or 12 months, listed method, reference, evidence, idempotent request key). The request becomes a pending subscription invoice marked `self_service` with amount = monthly price × months; one open request per business.
- `backend/subscription_billing.py`: approving a self-service request requires the platform owner, computes the term at approval, writes it to the invoice and the subscription, and skips the issued-invoice revision/overlap checks. Replays return the recorded result; a second approval is refused by status. Platform-issued invoices behave as before.
- `backend/app.py`: an SME Owner whose subscription is past expiry may call only `/v1/me`, sign-out, password change, `/v1/account/*` and `/v1/subscription*`; everything else returns 403 with a renewal message. `/v1/me` returns `subscription_restricted`. A business with no subscription record is not restricted.
- Frontend: `src/SubscriptionRenewal.jsx` (status, plans, monthly/annual term, total, platform payment details, request form, approval check; English/Burmese), expiry warning banner with **Renew now**, renewal-only menu (Subscription, Account) and no business data loaded while expired. `src/SubscriptionPaymentSettings.jsx` on the platform owner's Subscriptions page. The invoice list marks business requests and says their dates are set on approval.
- Staff (Q9): the SME Staff page, `StaffRecovery.jsx` and `CashierVouchers.jsx` are removed; any legacy staff appear only on the Account page for disabling. `scripts/verify-staff-subscriptions-ui.mjs` rewritten and passing.

Verification: `tests/test_subscription_renewal.py` (7: month clamping, warning and restriction days, early/late term rules, owner-only payment details, request validation/idempotency/one-open/owner-only approval/isolation, late renewal restores access from the approval date and cannot extend twice, early renewal keeps remaining days); migration head assertions moved to 044; SQLite upgrade/downgrade/upgrade round trip; full suites green (617 backend, 73 JavaScript; staff/subscriptions, billing, voucher and revenue UI checks). Local browser run with an expired test business: renewal-only menu, 3-month request (before terms were limited to monthly/annual), platform-owner approval set 11 Oct 2026 – 11 Jan 2027, owner regained the full menu; the 7-day banner rendered in Burmese.

## 2026-10-11 — Developer Dashboard, first increment (owner decisions on the Developer role)

Owner decisions: Developer capabilities belong to the owner's existing `nish@magic` account, in a separate Developer Dashboard (not a second login, not mixed into the Platform console), limited to application settings, SME owner accounts, the platform payment system, and platform roles and permissions.

- Migration 045: `users.access_state` (`active`/`suspended`/`disabled`, existing inactive accounts become `disabled`), `access_reason`, `access_revision`, and `owner_access_events` (one row per change with the reason, sessions ended and revision).
- `backend/developer.py` (platform owner only): `GET /v1/developer/owners`, `POST /v1/developer/owners/{id}/access` (revisioned; suspending or disabling ends every session and revokes delegated review credentials), `POST /v1/developer/businesses/{id}/name` (checked against the current name), `GET /v1/developer/owners/{id}/history`, `GET /v1/developer/roles`.
- Sign-in: a suspended SME owner with the right password gets 403 with the suspension reason; a wrong password and disabled accounts keep the generic 401.
- Frontend: `src/DeveloperDashboard.jsx` (four areas), `src/OwnerAccounts.jsx`. The platform owner's menu shows Developer Dashboard and no longer lists Businesses, Subscriptions and Appearance separately; other platform operators are unchanged. The subscription payment-details form is only in the dashboard.
- UI checks: `verify-businesses-responsive-ui`, `verify-onboarding-ui`, `verify-portal-ui` and `verify-progress-ui` had stale text expectations from earlier deliberate changes (demo sign-out label, 6-character password minimum, local HotSpot package wording, "Signed-in devices"); updated so all 16 offline UI checks pass.

Verification: `tests/test_developer.py` (5: owner-only access, suspension with reason and restore, disable with generic failure and isolation, rename conflict, roles); migration heads 045; SQLite 044 → 045 → 044 → 045 with an inactive account; full suites green (622 backend, 73 JavaScript, all offline UI checks). Local browser: suspended and restored an owner from the dashboard, suspended sign-in showed the reason, all four areas rendered.

## 2026-10-11 — Developer Dashboard Application settings (owner decision C: branding and application configuration)

- `backend/branding.py`, owner only except the two public reads: `GET /v1/branding` (app name, offered languages, default language, logo URL) and `GET /v1/branding/logo` (PNG). `GET/POST /v1/developer/application` saves the app name (1–40 characters), offered languages (`my`, `en`, at least one), default language (must be offered) and an optional announcement (up to 500 characters, information or warning) with a revision check and an audit entry. `POST /v1/developer/application/logo` accepts PNG, JPEG or WebP up to 1 MiB and 4 million pixels, single frame; Pillow redraws it into a new PNG of at most 256×256, so metadata, appended data and SVG never reach browsers. `POST /v1/developer/application/logo/remove` restores the MikroMagic logo. `GET /v1/announcement` returns the announcement to SME owners only.
- Stored as `platform_settings` rows `application` and `application_logo`; no migration.
- Frontend: the Application settings area has an Application configuration form above the existing appearance editor. The sign-in page, forced password page, sidebar and browser tab use the app name and logo. SME workspaces start in the platform default language until the owner picks one on the device, show only offered languages, and hide the switch when one language is offered. The announcement shows as a banner in SME owner workspaces until dismissed; a newly saved announcement shows again.
- Not included: email, SMS or push notifications; translating platform or guest screens; body text still names MikroMagic.

Verification: `tests/test_branding.py` (3: public defaults and owner-only access, revisioned save with validation and SME-only announcement, logo re-encoding, size and frame limits, SVG refusal and removal); language-selection unit test; full suites green (625 backend with 12 PostgreSQL skips, 74 JavaScript, all 16 offline UI checks). Local browser test with a throwaway SQLite database: saved name, English default and warning announcement, uploaded a logo (256×256), sign-in page and tab show the new name and logo, the owner workspace opened in English with the banner, dismissal survived a refresh, English-only hid the switch and overrode a stored Burmese choice, an edited announcement reappeared, an SVG upload got 422.

## 2026-10-11 — Referral Agents (owner decisions Q20–Q30)

- Migration 046: `users.role` allows `agent` (an Agent has no business); `subscription_invoices.status` allows `refunded`; new tables `agent_profiles` (application and status), `agent_referrals` (business → Agent, set at creation), `agent_commissions` (one per invoice), `agent_wallets` (KBZPay/WavePay) and `agent_withdrawals`.
- Applications: public `POST /v1/agent-applications`, 5 per network per hour. The platform owner approves, rejects (reason), suspends (reason) or restores in Developer Dashboard → Agents. Pending, rejected and suspended Agents can sign in and see their status but cannot register businesses or withdraw.
- Registration: `POST /v1/agent/businesses` reuses the platform's business creation (`provision_business`): the Agent receives the owner's one-time temporary password, valid 24 hours, which must be changed at first sign-in. The Agent sees the business name, owner username, whether the owner has signed in, subscription state and its own commission, nothing else. `current()` refuses every path for Agents except `/v1/agent/*`, `/v1/account/*`, `/v1/me`, password change and sign-out.
- Commission: on approval of a subscription invoice for an attributed business, 20% (monthly) or 30% (annual) of the list price (`monthly_price × months` from the invoice's plan snapshot), available immediately. Platform-issued single-period invoices count as monthly. One commission per invoice.
- Refund: the platform owner can record a refund for a paid invoice (`POST /v1/platform/subscription-invoices/{id}/refund`, reason and confirmation that the money was returned). It reverses the commission; if that commission was already withdrawn the balance goes negative and is recovered from future earnings. The subscription term is not changed automatically.
- Withdrawals: from 10,000 MMK, to a saved KBZPay or WavePay wallet of the Agent, at most the available balance. A request reserves the amount (requests are serialized per Agent); the Agent can cancel before review; the owner approves or rejects, then records the payout reference to mark it paid. Wallet details are copied into each request.
- Frontend: "Become a MikroMagic Agent" on the sign-in page; Agent workspace with Agent overview, Registered businesses, Commissions, Withdrawals and Account; Developer Dashboard → Agents (accounts, withdrawal review, commission ledger, attributed businesses); "Record refund" on paid invoices in Developer Dashboard → Payment system.

Verification: `tests/test_agents.py` (5: approval gate and path confinement, application rate limit, registration with one-time password and no business access, commission rates and refund reversal, withdrawal reservation, review, payout and negative balance after refund); SQLite 045 → 046 → 045 → 046 with data, downgrade refused while Agent data exists; full suites green (630 backend with 12 PostgreSQL skips, 74 JavaScript, all 16 offline UI checks). Local browser run: application, approval, business registration with handoff, monthly and annual approvals (6,000 and 108,000 MMK), wallet, 50,000 MMK withdrawal approved and paid, refund reversing 6,000 MMK, no failed requests from the Agent session.

## 2026-10-11 — Smart Notification Center and Daily Owner Summary (frozen v1, in-app)

- Migration 047: `notification_preferences` (per Owner/Admin: show Critical only, Critical + Attention, or All; Daily Owner Summary Daily, Important days only, or Off; revision-checked) and `notification_reads` (read markers per notification key and version). Nothing else is stored: notifications are derived from current business records on each request, so one issue is one entry that updates in place and disappears once resolved.
- Sources (SME Owner/Admin only, tenant-scoped): router changes needing recovery (Critical) or in conflict (Attention); open incidents, with downstream faults at a site (switch, access point, DNS/login page) grouped under the most upstream open incident (internet/WAN, then gateway) and its suspected or confirmed root cause; three or more incidents of the same scope at a site within 24 hours become one "unstable" entry; incidents recorded during planned maintenance or closed hours are Information; recoveries within 24 hours are Information; pending guest payments (one grouped entry); failed payment-review event deliveries; subscription expiry warning; active (Information) or overdue (Attention) planned maintenance. A changed entry becomes unread again.
- Daily Owner Summary (Overview, previous day in Asia/Yangon): recorded revenue net of refunds, recorded payments, vouchers sold (counter sales) and vouchers redeemed in the app shown separately ("Redeemed is not the same as sold, and not router activation"), incidents started, open incidents, outstanding Critical/Attention. Peak customers, internet availability, access point health and router voucher activation are shown as not measured until a router is connected. "Important days only" shows it when incidents started, Critical issues are outstanding or refunds were recorded.
- Endpoints: `GET /v1/notifications`, `POST /v1/notifications/read`, `POST /v1/notifications/preferences`, `GET /v1/notifications/daily-summary`. Frontend: Notifications page and header bell with unread count (English and Burmese), summary card on Overview. Phone push, SMS and email are not connected; the page says so.

Verification: `tests/test_notifications.py` (4: owner-only and tenant isolation, root-cause grouping and instability aggregation, read markers that reset when an entry changes, preferences with revision conflict and audit, daily summary keeping sold separate from redeemed); `tests/notification-messages.test.mjs` (every backend kind, scope and reason has English and Burmese text); SQLite 046 → 047 → 046 → 047; full suites green (634 backend with 12 PostgreSQL skips, 76 JavaScript, all 16 offline UI checks). Local browser run in English and Burmese: two Critical entries (gateway with one grouped access point issue, unstable WAN) and maintenance, summary 4,500 MMK from two sales, mark as read and "Critical only" setting, no failed requests.

## 2026-10-11 — Media Pass rules (owner decisions Q36–Q49, software part)

- Migration 048: `media_titles.featured` and `media_settings` (per business: catalogue preview `full` or `featured`, revision-checked).
- Q38: Internet and Media passes are sold separately. New `combined` packages are refused (422). Existing combined packages stay readable but are hidden from guests and cannot get new orders or vouchers (409); orders already submitted can still be approved, and their passes keep the legacy library window.
- Q37: new Media Pass type "Selected categories" (1–10 catalogue genres, each must match a title in the business's own catalogue; offered to guests only while a published title in those categories exists), alongside whole library, one title, and library + one title.
- Q40–Q42: a Media Pass voucher starts its time when the guest first redeems the code in the guest portal (stored as the pass activation; redeeming again does not restart it). Each pass reports `valid_until`, per-scope windows, state active/expired/not activated/revoked, one device and no transfer until expiry. Device binding and playback are reported as not connected.
- Q49: the owner chooses Full catalogue preview or Featured titles only, and marks titles as featured. With Featured only, guests without a valid Media Pass see only featured published titles; guests holding one see the whole published catalogue.
- Frontend: package form drops "combined" and adds category selection from catalogue genres; Media page adds Feature / Remove from featured, the preview setting and a Media Pass rules panel; guest passes show Active until / Expired and the one-device rule.

Verification: `tests/test_media_pass_rules.py` (3: category validation and guest availability, activation at first redemption with expiry and no activation for Internet vouchers, featured-only preview with pass holders and tenant isolation); `tests/test_media.py` legacy combined case; SQLite 047 → 048 → 047 → 048 with a title row (constraints and index preserved); media UI check extended; full suites green. Local browser run: category pass created from the form, title featured, preview switched to Featured only, no failed requests.

## 2026-10-11 — Media Pass bought online starts at first use (owner decision)

- Owner decision: a Media Pass bought online starts at the guest's first use. Online-purchased passes now report `activation: starts_at_first_use` and state `not_started`, and the guest sees "Starts at your first use"; the owner's Media Pass rules panel and the guest package text say the same. No clock runs until playback (not yet connected) records the first use. No migration.

Verification: `tests/test_media.py` asserts the online pass state; media UI check covers the new label; full suites green.

## 2026-10-11 — Agent application location (owner decisions Q31–Q32)

- New Agent applications must give a state or region (Myanmar's 14 states and regions plus Naypyidaw Union Territory), a city, a township and a map pin. The pin is placed by clicking a map (Leaflet with OpenStreetMap tiles, loaded only when the applicant opens it) or by typing coordinates; it must fall inside Myanmar's bounding box (an approximate check). The browser's location feature stays disabled and nothing is tracked.
- The Developer Dashboard → Agents list shows the township, city and region with a link to the pin on OpenStreetMap. Applicants from before this change show "No location — applied before location was required".
- Migration 049 `agent_location`: five nullable columns on `agent_profiles`; the SQLite downgrade restores the exact 048 schema.

Verification: `tests/test_agents.py` (required fields, bounds, stored and returned location, legacy rows, region list parity with the form); `scripts/verify-agent-location-ui.mjs`; local browser run (apply with a map pin, Developer view and pin link); full suites green.

## 2026-10-11 — Interface review and page-frame cleanup (P0a, increment 1)

- Product-wide interface review recorded in `docs/UX-REVIEW-2026-10-11.md` (72 captures: SME owner, Developer, Agent, sign-in, demo; desktop and phone), with findings F1–F13 and the increment plan.
- Increment 1: on phones the header fits (Refresh and Sign out become labelled icons), tables scroll inside their box instead of squeezing columns, and no page scrolls sideways at 390 px (was every SME page). Developer-facing texts removed for signed-in users: "Development build" footer, "account database · Your authorized workspace" subtitle, sidebar "Authenticated records" and adapters note, the page eyebrow. The Captive portal page no longer goes blank on an older draft. No migration.

## 2026-10-12 — SME menu grouped, owner terms in the menu (P0a, increment 2)

- Owner terminology decisions: Shop (not Site), Internet Pass / Media Pass with a "Passes" catalogue page (not Package), Router (Gateway only in technical details).
- The SME owner menu is grouped: Overview and Notifications, then Sell, Shops & network, Business and Help, in English and Burmese. Labels: Shops, Passes, Guest Wi-Fi page (was Captive portal), Connected services (was Integrations), Activity history (was Audit). The menu scrolls inside the sidebar on short windows. No page removed; internal page names unchanged. No migration.

## 2026-10-12 — Vouchers page task-first (P0a, increment 3)

- The Vouchers page opens on Issue a voucher. All vouchers (metrics, inventory, sale review), Find stock, Batches & printing (batch sheets, production jobs) and Dealers are tabs, in English and Burmese. Dealers and production jobs remain owner/admin only and hidden in the demo, as before.
- Inactive tabs stay mounted but hidden, so a code shown only once survives switching tabs; a batch QR link opens Batches & printing. No behaviour or API change; no migration.

## 2026-10-12 — Overview simplified (P0a, increment 4)

- The router state is shown once, in the Wi-Fi health card, with its action next to Get help; Needs your attention no longer repeats it. Order: health, attention, Quick Voucher, daily summary, network summary.
- Revenue detail stays on Revenue: the Overview's revenue figures, Revenue by service (which still listed the retired "combined" service) and Business actions are removed; a Net confirmed collections card opens Revenue. No API change; no migration.

## 2026-10-12 — Routers page guided, technician detail under Advanced (P0a, increment 5)

- SME owners see **Connect your router** first: four steps with Done / Next / Later and one action on the next step. An unverified router is never shown as connected.
- Magic Hub, connection plans and Safe RouterOS changes moved into a closed **Advanced (technician)** section that opens by itself when a router change needs attention. No API change; no migration.

## 2026-10-12 — SME terminology and Burmese (P0a, increment 6)

- SME page contents use Shop, Pass (Internet Pass / Media Pass), Router, and Guest Wi-Fi page. Internal API names and page keys are unchanged. Generated, Sold, and Activated stay distinct.
- Burmese covers Overview, the Vouchers page, and the Routers sections under the guide, including Magic Hub, connection plans, and Safe RouterOS. Platform screens stay English. Guest portal and Developer Dashboard are next. No API change; no migration.
