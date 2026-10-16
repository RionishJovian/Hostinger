# Notion live-release fixes

Source archive: `mikromagic-build21-public-test-20261015T202701Z.zip`

Source archive SHA-256: `c41f9101c5a37b23ed89a64d647978f9c38b8ebecf4514e4b2ce578431837621`

This is an isolated Mac working directory created from the deployed release.
The VPS release remains unchanged.

## Local progress

- Q1/R1: terminal input is a closed allowlist of exact read-only commands; chaining, writes, selectors, and the former blocklist bypasses are rejected.
- Q2/R2: scripts accept only the named `remove-legacy-lovable-api-user-and-wg-peer` Safe Change operation.
- Q3/D2: browser-supplied backup lifecycle and verification flags are ignored; new records start as server-created and unverified.
- Q5: bearer token persists in `sessionStorage`; unauthenticated deep links retain an internal `/app` return path.
- Q9: Profile no longer calls the unregistered MFA status endpoint.
- Q10: Reseller Operation falls into an error state after a bounded loading timeout.
- Q11: readiness hub/management flags use the shared freshness result instead of an inline time-window calculation.
- Q12: overview revenue counts only collections and refunds, matching the revenue module's sign convention.
- Q13: TOTP replay steps can be consumed through a conditional database update on the account MFA row; repeated or out-of-order steps are rejected.
- P1: owner-visible labels for Topology, Scripts and Backups no longer claim platform-admin-only access; existing route gates remain enforced.
- P7/Q18: Home and Easy mode now use the shared `Not connected yet` state instead of silent dashes or an object rendered as `Available MMK`.

## Verification

- Focused Python tests: 10 passed.
- Python compileall: passed.
- Owner-web build: passed after installing the declared local dependencies.
- CI/CD: added `scripts/ci-check.sh`, a GitHub Actions check workflow, a manual production gate, and a macOS-dispatch workflow. The deploy job intentionally requires the reviewed Hostinger deployment script; this reconstructed archive does not contain that script or a pushed Git history.
- Deployment/live verification: not done.
