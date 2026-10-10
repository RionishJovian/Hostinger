# MikroMagic v1 Requirements Map

This map connects the authoritative master requirements to the current Build 21 implementation boundary.

| Requirement area | Build 21 position | Next implementation boundary |
|---|---|---|
| Roles, tenant isolation, authentication | Implemented and tested for core flows; frozen password/lockout/session policy (migration 029) and login history (migration 033) implemented; legacy staff roles frozen to the single Owner/Admin role (2026-10-10) | Technician Visit Mode; deployment hardening |
| SME portal, vouchers, packages and revenue | Implemented as account-backed web workflows | Connect local enforcement and complete authenticated/mobile QA |
| Router registry and Magic Hub plans | Implemented as planned, management-only records | Local controller, signed handshake, capability discovery and apply/verify |
| RouterOS HotSpot, AAA and quotas | Policy models and simulations only | Local gateway enforcement, counters, reconnect and bypass tests |
| Managed switch/AP inventory | Site-scoped owner-reported switch/AP inventory API, migration 021, and configurable default limit of 1 switch/5 APs | Vendor adapters, capability matrix, telemetry and safe actions |
| Offline voucher operation | Durable idempotent offline event ingestion and conflict records; migration 022; events never grant access automatically | Signed local controller queue, bounded inventory, counter reconciliation and operator resolution |
| Trusted/blocked clients | Requirement captured in master requirements; not implemented end-to-end | Identity states, enforcement point, MAC-randomization re-verification |
| Monitoring, uptime and outage history | Site incident model/API and migration 023 with evidence-labelled causes | Device telemetry, uptime aggregation, deduped notifications, escalation and exports |
| Backups/restores and rollback | Backup metadata API and migration 024; encrypted/checksum/restore-verified state is explicit | Encrypted storage, device exports, FIFO retention, restore preview/apply and recovery tests |
| Firmware management | Staged site firmware plans and migration 025 with maintenance window and safe-version metadata | Model safety matrix, capability approval, artifact storage, staged execution, health checks, rollback and manual recovery |
| Provider-neutral payment review | Pull review API and durable delivery implemented | Telegram/Discord identity verification, signatures and outbound notifications |
| Media/Jellyfin | Entitlement and catalogue policy groundwork | Site gateway, segment authorization, sync and playback acceptance |
| Magic Dude | Floating contextual UI and guarded demo responses | Evidence-backed diagnostics, model integration and approved tool actions |
| Commercial plan limits | Some subscription/account groundwork | Consistent UI/API/job/device enforcement and downgrade behavior |

## Non-negotiable boundaries

- Do not mark a router connected from generated configuration alone.
- Do not route guest internet or local media through the management Hub by default.
- Do not expose voucher secrets, private keys, passwords, or provider tokens in logs or exports.
- Do not claim live RouterOS, RADIUS/AAA, payment settlement, or Jellyfin playback until the corresponding integration acceptance test passes.
