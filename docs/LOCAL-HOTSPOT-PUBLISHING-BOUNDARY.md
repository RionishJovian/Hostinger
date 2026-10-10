# Local HotSpot package and future publishing boundary

This document records the frozen-v1 Local-first architecture clarification. Each owner publication atomically stores a content-only package artifact with its tenant/site/published-revision identity and SHA-256. The package stays internal to MikroMagic. There is no router upload/apply path enabled in this build.

## Package contract

- Build a deterministic ZIP from the already-published site portal revision and a stable site ID. It contains a small local servlet set (`login.html`, success/failure/status/logout/error/redirect pages, and `api.json`), a content hash manifest, and a human-readable boundary notice.
- Owner-entered text is HTML escaped. No cloud origin, remote script/style/image, payment endpoint, router command, router credential, user/voucher record, or network configuration is packaged.
- Login uses the RouterOS local HTTP-CHAP challenge variables (`chap-id`, `chap-challenge`) and POSTs only to `link-login-only`. The bundle carries an inline MD5 challenge routine; it has no HTTP-PAP/plain-password fallback. If the profile does not provide the expected CHAP flow, it must fail closed. This implementation is fixture-tested but still needs RouterOS/browser validation.
- The package manifest explicitly says installation and RouterOS compatibility are unverified. A passing fixture test proves archive structure and escaping only.

## Future narrow deployment sequence (not implemented/enabled)

1. Re-authenticate to the selected router over verified HTTPS and perform read-only inventory only. Verify model/RouterOS version, HotSpot capability, selected server/profile association, all servers sharing that profile, auth method compatibility, configured portal directory, relevant file metadata, available persistent storage and whether `flash/` is required. If current inventory cannot establish a fact, stop rather than infer it.
2. Choose a new, site/revision-scoped directory under persistent storage only after checking for exact path/file collisions. Existing router files remain unchanged. If a safe unique location cannot be proven, stop.
3. Render a diff listing exact new files, hashes, target directory and the one profile property that may need a change (`html-directory` or the device-supported override property). Explain shared-profile impact and offline/login behavior. Obtain explicit Owner confirmation.
4. Capture and verify a protected RouterOS configuration backup before changing the profile reference. Backup failure or unverified recovery means no change.
5. The future adapter may allow only: create the new directory; create new files at previously absent paths; and, only if required and confirmed, update the selected profile's portal-directory property. Every target path and property must be allowlisted and rechecked immediately before writing. No generic RouterOS command endpoint, overwrite, delete, auth-method change, user/session change, firewall, DHCP, DNS or unrelated HotSpot write is allowed. If target RouterOS cannot support bounded file creation and one-property update over a tested interface, do not fall back to arbitrary POST commands, scripts or manual uploads.
6. Read back every new file and verify exact hashes, inspect the selected profile's effective path and confirm the router serves its local login page. Any mismatch reports failed/pending, never success. Preserve the prior profile value and backup as recovery evidence. Rollback may restore only the prior profile-directory value; created files may be removed only if they still match the package hashes and no profile references them.
7. Real-device acceptance must separately test first login, failed login, local synchronized voucher login during cloud loss, session status/logout, persistence across reboot, another profile sharing behavior, backup recovery and rollback. Until those pass, show Router deployment as unverified.

## Evidence and current limits

Official RouterOS docs describe HotSpot-local servlet variables and the MD5 challenge routine needed for HTTP-CHAP (their example loads `md5.js`); they also note that files outside `flash/` may be RAM-backed on devices that expose that directory. Current MikroMagic discovery is GET-only and the Safe Change writer remains limited to its existing WireGuard operation. No page here enables new router writes or claims the bundle is installed, persistent, offline-capable, or operational.
