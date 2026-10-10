# Frozen v1 authentication correction — local only

This corrective copy is derived from the verified frozen Build 21 v8 checkpoint. It is not deployed. The frozen Notion tracker remains the product authority.

## Behavior

- Passwords accept 6–256 characters, with no composition rule or whitespace trimming.
- Five failed attempts for one normalized username cause a five-minute account lockout. The counter resets when the 15-minute failure window expires or after lock expiry; successful login resets only that account bucket.
- A separate source-IP spray guard permits up to 60 failed logins in a 15-minute window before a 60-second cooldown. It cannot impose the five-attempt account lock on every user behind a NAT. This higher aggregate threshold is only for sustained multi-username abuse; the account threshold remains five.
- Client IPs come from the socket peer unless that peer is an exact IP explicitly configured in `MIKROMAGIC_TRUSTED_PROXY_CIDRS`. Only then is `X-Forwarded-For` parsed right-to-left through explicitly trusted proxy hops. Invalid, oversized, or spoofed headers fall back to the peer address; no forwarded headers are trusted by default. Broad CIDRs are rejected, and the proxy must overwrite or safely append forwarding headers.
- Self-service password changes preserve all existing sessions and return the same current session token. Operator password resets preserve existing account sessions; only newly issued temporary-password sessions are gated until their password is changed. Users can still inspect and individually revoke sessions, explicitly sign out, or revoke all other sessions.
- Login accepts password only. MFA status/enrollment/confirmation/disable endpoints and UI are no longer mounted; legacy MFA tables, model and migration remain untouched.
- Public site registration remains guest-only. Extra role claims are rejected; public callers cannot create SME or platform accounts.

## Migration 029

Adds `sessions.must_change_password`, `login_attempts.scope`, and nullable `login_attempts.locked_until`. Existing sessions are retained and their per-session temporary-password gate is backfilled from the user's current flag. Existing hashed account buckets are identified from current usernames and only account buckets at five or more failures receive a five-minute lock. Legacy IP lockouts are cleared so an old shared-IP bucket cannot lock out unrelated users; IP failure counts remain available for the higher spray threshold. Known per-user password-change, voucher-attempt and MFA-operation buckets remain `other`; raw identifiers are never stored. No account, audit, tenant, voucher or MFA data is deleted or rewritten. Downgrade removes the added columns and loses per-session gate/throttle metadata; do not downgrade without a verified restore plan.

The local shared-IP regression verifies that five failures against one account do not prevent another account at the same peer IP from signing in. PostgreSQL row-lock concurrency still requires an isolated PostgreSQL test database; no live database is used by local tests.

## Verification and deployment boundary

Regression coverage is in the auth, onboarding, guest-entry, MFA-compatibility, session, and migration tests. The app and migration have only been exercised locally in this corrective copy. No VPS, active deployment, database, or frozen archive was modified.

Any future private deployment requires separate approval. Stage a versioned copy, verify its identity and effective Compose configuration, create and verify a protected database backup, apply migration 029 under a controlled stop-on-failure checkpoint, then run auth/session/tenant-isolation smoke tests privately. Do not replace the active deployment in place. For rollback, stop the candidate and restore the matching pre-migration backup only after confirming that any post-backup acceptance data can be discarded or separately preserved; otherwise retain the migrated database and stop for a reviewed forward-recovery decision. Never delete volumes or alter `/opt/build21`.

Public access, production launch, DNS/TLS/firewall changes, Magic Hub, and real RouterOS/HotSpot/WireGuard acceptance are out of scope.
