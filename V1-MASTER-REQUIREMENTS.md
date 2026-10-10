# MikroMagic v1 — Master Requirements

**Status:** Authoritative implementation handoff for Build 21  
**Target:** Existing Build 21 `mikromagic/` source tree

## 1. Authority, scope, and implementation rules

This document consolidates the confirmed MikroMagic v1 direction available from the originating conversation and the current handoff. The Build 21 source is the implementation baseline.

- **Never replace Build 21 with Build 20 or any older ZIP/source snapshot.** Older material may be consulted only as reference.
- Begin implementation now. Do not wait for every future question to be answered.
- When a detail is not specified below, choose a conservative, reversible default; isolate it behind configuration or a migration-safe interface.
- Treat future confirmed requirements as incremental updates. Preserve backward compatibility and record schema/API changes.
- Keep the system operable during WAN/cloud loss wherever the local gateway and RouterOS can enforce the rule.
- Separate local implementation, tests, migration, deployment, and production verification in status reporting.

## 2. Product and architecture

MikroMagic is a multi-site management and captive-portal platform for small and medium businesses. It manages a local MikroTik gateway, a managed switch, and wireless APs while providing a cloud/control-plane view for provisioning, policy, monitoring, audit, and commercial limits.

### Control plane

- Tenant, site, user, role, device, policy, voucher, subscription, audit, notification, backup, firmware, and outage domains are separate modules with stable IDs.
- Desired state is stored centrally; each site has a local agent/controller that applies desired state to RouterOS and managed devices.
- Every push is idempotent, versioned, diffable, and attributable to an actor or automation.
- Device adapters must be capability-aware: unsupported features are reported clearly and never silently emulated.
- Secrets are encrypted at rest, redacted from logs, and scoped to tenant/site/device.

### Local site plane

- The gateway remains authoritative for immediate traffic enforcement and HotSpot behavior.
- The local controller maintains a durable queue of pending commands, observations, and reconciliation results.
- WAN/cloud loss must not remove existing valid access policy or require a cloud round trip for an already enrolled client.
- Reconnect uses ordered, idempotent replay with conflict detection and a final observed-state report.

## 3. RouterOS, local HotSpot, and offline resilience

- Support RouterOS local HotSpot configuration, address lists, user profiles, walled-garden rules, DNS/HTTP redirect behavior, and rate limits through generated, validated configuration.
- Script generation is not enrollment. Enrollment requires execution on the real MikroTik (normally through WinBox or the approved local mechanism), followed by app-side **Finish/Check** verification.
- Never report a site as connected solely because a script was generated or downloaded.
- Preserve safe rollback points before risky changes; use transactions where RouterOS permits and compensating rollback otherwise.
- Offline mode preserves current vouchers, profiles, expiry/quota counters, bandwidth limits, client allow/deny state, and local audit buffering.
- On reconnect, upload buffered events and reconcile counters and policy versions without double-consuming quota.
- Clock skew is detected; expiry and quota decisions use a trusted local time source with an explicit degraded-mode policy.

## 4. Vouchers, profiles, lifecycle, quotas, bandwidth, concurrency, codes, and printing

### Profiles and policy

- Profiles define duration/expiry, data quota, speed limits, concurrent-session limit, idle/session timeout, allowed sites/SSIDs, and disable/revoke behavior.
- Policies must be composable but have deterministic precedence: explicit client block/allow, voucher state, profile, site defaults, then device defaults.
- Quota accounting is monotonic and auditable. Define whether upload/download are separate or combined at the profile level; default to combined total unless a tenant explicitly chooses otherwise.

### Voucher lifecycle

States: `draft` → `generated` → `printed/exported` → `active` → `used`/`expired`/`exhausted`/`disabled`/`revoked` → `archived`.

- Codes are generated with cryptographically secure randomness, configurable length/alphabet, collision checks, and no predictable sequence.
- A voucher is single-use by default; reuse requires an explicit profile setting.
- Disable pauses admission immediately and preserves history. Revoke permanently invalidates admission. Delete is a soft-delete/archive operation for records referenced by sessions, invoices, or audit; physical purge is retention-controlled.
- Existing sessions after disable/revoke follow the configured enforcement grace period; conservative default is immediate new-login denial and termination at the next policy check.
- Bulk generation supports preview, deduplication, export, and print layouts. Printing must not expose more data than the operator selected and must remain reproducible from the stored batch.
- Never log full voucher secrets in ordinary logs.

### Quotas, bandwidth, concurrency

- Enforce quota and rate policy locally at the gateway where possible.
- Counters are associated with voucher/client/session and include timestamps, source device, and confidence (live vs reconciled).
- Concurrent sessions are counted per voucher/profile using gateway observations; stale sessions expire via heartbeat/timeout.
- Rate limits must distinguish per-client and aggregate/site limits. Default to per-client profile rate.
- Reconciliation must resolve duplicate or out-of-order usage events deterministically and preserve an audit trail.

## 5. Clients, trusted devices, and blocked behavior

- Client identity may include MAC, DHCP lease/IP, username/voucher, and observed device fingerprint; do not assume MAC alone is permanent.
- Support explicit states: unknown, pending, trusted/allowed, blocked, quarantined, and expired.
- Trusted clients may bypass selected portal steps only under an explicit tenant/site policy and still remain subject to block and network safety rules.
- Blocked clients are denied according to the selected enforcement point (gateway, SSID, or device) and receive a visible reason to authorized operators.
- MAC randomization and identity changes must not silently transfer trust or quota; require a configurable re-verification path.

## 6. AP, SSID, vendor, and device management

- Manage SSIDs, security mode, VLAN/network mapping, channel/power defaults, guest isolation, and portal association through vendor adapters.
- Maintain a vendor/model capability matrix and surface unsupported settings before apply.
- Preserve existing SSIDs and credentials unless a confirmed change is requested; secret rotation is staged and reversible.
- Default site topology is **1 gateway → 1 managed switch → 5 APs**.
- Paid expansions may add APs, switches, gateways, sites, clients, vouchers, or throughput according to the tenant’s commercial plan. Enforce limits in the control plane and show the reason when blocked.
- Provisioning must be safe for partial completion: one failed AP must not silently roll back healthy devices without an explicit operator choice.

## 7. Monitoring, metadata, imagery, firmware, and notifications

### Switch/device monitoring

Collect reachability, uptime, CPU/memory/temperature when available, port link state/speed/errors, PoE state, client counts, SSID/radio state, gateway health, and last-seen timestamps. Clearly label unavailable metrics.

### Device metadata and model imagery

- Store vendor, model, serial/MAC, role, site, rack/room/location, purchase/warranty metadata, firmware, and notes.
- Model imagery is informational and must not be treated as proof of the physically installed unit. Allow replacement of image assets without changing device identity.

### Firmware

- Track current, target, minimum-safe, and rollback firmware versions per model.
- Scheduling supports maintenance windows, staged rollout, health checks, retry limits, and rollback/recovery guidance.
- Notify operators before scheduling, at start, on success, partial failure, rollback, and required manual recovery. Never auto-upgrade an unknown or unsupported model.

## 8. Backups, restores, retention, and FIFO

- Back up control-plane configuration, tenant/site policy, device inventory, voucher/profile definitions, audit metadata, and restore-critical secrets using encrypted storage.
- Where supported, capture RouterOS/device exports with version and checksum metadata; redact secrets from human-readable copies.
- Retention is configurable by tenant/plan with safe minimums; expired backups are removed by FIFO while retaining the required latest successful restore point.
- Restore is explicit, permissioned, previewable, and produces a change plan. Never overwrite a live site without confirmation and a new rollback backup.
- Test restore integrity and report failures; a backup that cannot be restored is not considered healthy.

## 9. Outages, root cause, uptime, and history

- Monitor control plane, site gateway, WAN, switch, AP, DNS/portal, and key service dependencies separately.
- Record incident start/end, affected scope, detection source, symptoms, suspected and confirmed root cause, remediation, and operator notes.
- Notify only authorized recipients through configured channels, with deduplication and escalation rules. Do not claim root cause until evidence supports it; label hypotheses as hypotheses.
- Uptime history must distinguish device unreachable, WAN unavailable, service failure, maintenance, and unknown data gaps.
- Preserve incident and uptime history under retention policy and make it exportable with timestamps and timezone.

## 10. Risky changes, reconnect, rollback, and recovery

- Classify changes by risk. High-risk changes require an explicit diff, expected impact, pre-change backup/checkpoint, and recovery path.
- During apply, show progress per device and stop safely on loss of contact. Do not report success until post-change verification passes.
- Reconnect uses exponential backoff, bounded retries, and a visible pending state. Repeated failure creates an actionable notification.
- Rollback must be versioned and targeted; avoid reverting unrelated successful changes.
- Provide recovery instructions for gateway lockout, bad SSID/VLAN, failed firmware, partial topology apply, and expired credentials.

## 11. Reconciliation and conflict handling

- Every desired and observed state has a version, timestamp, source, and checksum where applicable.
- Detect drift rather than overwriting it silently.
- Conflicts identify the competing values and source (operator, local controller, external change, automation), then require or apply a documented policy: operator-wins, desired-state-wins, observed-state-wins for safety, or merge.
- Safety-critical observed conditions (loss of connectivity, overheating, unsupported firmware) must block destructive reconciliation and notify operators.
- Preserve conflict history and resolution actor.

## 12. Logs, retention, and export

- Audit all authentication, authorization, configuration, voucher lifecycle, policy, device, firmware, backup, restore, outage, and reconciliation actions.
- Use structured logs with correlation ID, tenant/site/device, actor, action, result, timestamps, and redaction.
- Retention is plan/configuration driven, subject to a safe minimum for security and support. Export supports filtered JSON/CSV and human-readable reports with timezone and provenance.
- Never include passwords, API tokens, voucher secrets, or private keys in ordinary logs or exports.

## 13. SME accounts and security

- Support tenant owner, administrator, operator, support/read-only, and site-scoped roles with least privilege.
- Enforce strong authentication, secure password storage, session expiry/revocation, rate limiting, and optional MFA where available.
- Owner and billing/security actions require re-authentication and are fully audited.
- Do not expose one SME tenant’s clients, vouchers, devices, logs, backups, or commercial usage to another tenant.
- Provide safe account recovery and notify on security-sensitive changes.

## 14. Commercial limits and plan enforcement

Commercial limits are configuration, not hidden assumptions. Enforce and display limits for sites, gateways, switches, APs, clients, vouchers, concurrent sessions, bandwidth, retention, firmware management, notifications, backups, and support features as the plan defines them.

- Limit checks are consistent in UI, API, background jobs, and local provisioning.
- Existing service behavior during downgrade is explicit and conservative: do not delete data or disconnect active infrastructure silently; prevent new usage beyond the limit and present an upgrade/remediation path.
- Billing/entitlement state is separate from operational device state and must be auditable.

## 15. Pending or undecided items

The following require later confirmation or product-specific configuration. They must not block initial implementation; use reversible defaults and feature flags.

- Exact pricing tiers, currencies, taxes, payment provider, grace periods, and entitlement source.
- Final RouterOS major-version matrix and exact supported MikroTik models.
- Exact AP/switch vendor list, controller APIs, and model-specific capabilities.
- Voucher code length/alphabet, printable paper dimensions, branding, locale, and barcode/QR format.
- Whether quotas are combined or split upload/download per plan (default: combined total).
- Default trusted-client bypass scope and enforcement grace period (default: deny new login immediately; terminate at next policy check).
- Exact notification channels, recipient groups, escalation timings, and quiet hours.
- Exact retention durations and regional/data-residency requirements.
- MFA provider, SSO support, and password/session policy values.
- Firmware approval authority, maintenance-window defaults, and rollback artifact storage.
- Final uptime SLA definitions and incident severity taxonomy.
- Whether any destructive physical deletion is ever allowed; default is soft-delete plus retention-controlled purge.

## 16. Build 21 execution checklist

1. Inspect and preserve the existing Build 21 `mikromagic/` structure and migrations.
2. Map each requirement in this document to an issue/module/configuration point.
3. Implement the local site/controller and idempotent desired/observed reconciliation path first.
4. Implement voucher/profile lifecycle and local offline enforcement with durable counters.
5. Add device adapters, default 1→1→5 topology, capability reporting, and paid-limit gates.
6. Add monitoring, audit, backups/restores, firmware scheduling, outage history, and notifications incrementally.
7. Add migrations and compatibility handling without replacing Build 21 artifacts.
8. Test failure paths: WAN loss, RouterOS reconnect, partial device apply, duplicate events, quota exhaustion, revoke/disable, restore, rollback, and entitlement limits.
9. Report status using the boundaries: implemented → tested → migrated → deployed → verified.
10. Accept future confirmed requirements as incremental changes to this baseline.

