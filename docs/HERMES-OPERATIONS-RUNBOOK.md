# Hermes operations runbook

This is the durable handoff for Hermes as MikroMagic's lead implementation and operations agent. It supplements `AGENTS.md`; when they differ, the newest explicit owner decision in `AGENTS.md` wins.

## 1. Start from identity, not memory

1. Work only in `/Users/aces/MikroMagic-Build21-FrozenV1-v8-corrective` and private GitHub repository `RionishJovian/Hostinger`.
2. Read `AGENTS.md`, `MIKROMAGIC-REQUIREMENTS.md`, `REQUIREMENTS-GAP.md`, and the relevant handover section.
3. Run `git status --short`, `git fetch origin main`, compare `HEAD` with `origin/main`, and fast-forward only when the working tree permits it. Never overwrite another agent's changes.
4. Record the exact full source SHA. A branch name, zip, screenshot, bundle, or remembered chat is not source identity.

## 2. Mandatory four-way reconciliation

Before changing a requirement, merging, or deploying:

1. Fetch the current Notion tracker index `3f2489e3-dbb6-81cc-9d2d-e66befe42255`, the applicable domain page 01–06, page 07, and page 08. Record revision times and requirement IDs.
2. Inspect current source, tests, active diff, and relevant open PRs on GitHub.
3. Read the live state without writing: Hostinger VPS identity, current dated release, container health, migration, flags, public readiness, served bundle, and the real relevant route/state.
4. Classify every acceptance clause as Present, Partial, Missing, Conflict, or Not verifiable. Current source, GitHub, live web, database migration, Hub state, and physical RouterOS are separate evidence layers.
5. Declare the bounded task: requirements, base SHA, owned files, intended checks, rollback impact, exclusions, and genuine blockers.

## 3. Implement safely

- Make the smallest complete change in the existing working tree. Preserve unrelated edits and data.
- Use fail-closed behavior. Do not simulate connectivity, payments, RouterOS reads, migrations, or delivery.
- Never request or store WinBox credentials, tokens, passwords, private keys, raw source IPs, or customer financial evidence in source, logs, screenshots, docs, or chat.
- Do not touch `/opt/build21`, `/opt/mikromagic-v8`, the RC stack, co-hosted stacks, firewall, SSH configuration, DNS, Caddy, Compose, Hub, or routers unless the current task specifically authorizes that resource.
- Router changes require the physical-router window gate. A WireGuard handshake alone is not `connection_verified`; require authenticated identity-bound RouterOS management evidence.

## 4. Test in layers

1. Run syntax/static checks and focused unit/component tests during implementation.
2. Run `git diff --check`.
3. Run the full repository gate before merge or deploy:

   ```sh
   bash scripts/check.sh
   ```

   Localhost-binding tests may require the approved unrestricted execution mode. Do not misreport sandbox `EPERM` as a product failure.
4. For responsive UI, run the actual browser acceptance at 375 × 812 and 430 × 932 in Burmese/English and light/dark. Require:
   - no page-level horizontal overflow;
   - interactive targets at least 44 × 44 px;
   - visible fields and body text at least 16 px;
   - secondary text at least 14 px;
   - readable Burmese wrapping and intact primary actions.
5. Inspect screenshots visually. Machine measurements do not replace visual inspection.
6. Run `bash scripts/local-housekeeping.sh` after local browser/server work and verify ports 5173, 8787, and 8788 are clear.

## 5. Commit and push

1. Refresh `origin/main` immediately before staging.
2. Stage explicit task files only. Review `git diff --cached --check` and `git diff --cached --stat`.
3. Commit with an outcome-focused message and push to `origin/main` only after all required checks pass.
4. Confirm local `HEAD` equals `origin/main` and the working tree is clean.
5. Bind the check record to the committed tree when appropriate:

   ```sh
   SKIP_CHECKS_TESTS=1 bash scripts/check.sh
   ```

   Use this only after the identical tree already passed the full gate; it is not a substitute for testing.

## 6. Deploy the isolated Hostinger stack

Deployment uses the standing owner authorization only for verified MikroMagic increments. Before writing, confirm the Hostinger VPS identity and read current container health, release, migration, and disk space.

Deploy only with:

```sh
scripts/deploy-hostinger-public-test.sh
```

The script must remain the authority. It requires a clean commit already on `origin/main`, builds and packages a deterministic artifact, creates a new dated directory, copies existing secrets without printing them, makes and validates a PostgreSQL dump, tags rollback images, rehearses new migrations, migrates, recreates only the isolated services, verifies health, preserves Hub identity/UDP publication, and checks public HTTPS plus the served bundle.

- If the script stops, stop. Do not work around its checkpoint.
- Never set `ALLOW_INFRA_CHANGE=1` unless the reported Compose/Dockerfile/Caddy/Hub change was separately reviewed and authorized.
- Do not restore a database dump unless the migration itself is proven faulty; restoration overwrites post-backup data.
- Do not prune images, volumes, networks, releases, or rollback artifacts during a deployment.

## 7. Verify production independently

After the script succeeds:

1. Re-read container health, running release directory, migration, worker state, and backup checksum.
2. Check the apex, `www`, and `/v1/ready` externally. Require HTTP 200 and `ready: true`.
3. Confirm public HTML serves the exact newly built bundle.
4. Re-run the relevant live browser flow and responsive matrix against `https://megamagic.tech`; inspect evidence screenshots.
5. If verification fails, preserve evidence and use the printed rollback procedure. Never call a successful upload or container start a verified deployment.

## 8. Record and hand off

1. Add a dated redeploy section to `MIKROMAGIC-HOSTINGER-HANDOVER.md` with source SHA, artifact digest, file count, release directory, prior release, dump entries, migration, rollback tags, recreated services, bundle, verification, boundaries, and exact rollback commands. Never include secrets.
2. Append—never rewrite—a concise verified execution checkpoint to Notion page 08.
3. Regenerate `.corrective-source-manifest.txt`, commit the evidence-only update, push it, and confirm clean local/remote SHA alignment.
4. Update any audit artifact so it distinguishes the original before-state from the deployed verified after-state.

## 9. Required reporting language

Report only observed facts under:

- **Changed** — source/docs changed.
- **Tested** — checks that actually passed, including counts.
- **Migrated** — database revision movement or explicitly unchanged revision.
- **Deployed** — exact source commit, artifact digest, release directory, and bundle.
- **Verified** — live containers, HTTPS/readiness, served bundle, and user-flow evidence.
- **Blocker** — only a real access, authority, hardware, or failed-check gate.
- **Owner action** — only what the owner must actually do.

Never collapse implemented, tested, migrated, deployed, live-verified, and RouterOS/hardware-verified into “done.”
