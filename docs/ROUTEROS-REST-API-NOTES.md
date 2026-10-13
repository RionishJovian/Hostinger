# RouterOS REST API — notes for MikroMagic

Sources: MikroTik documentation ([REST API](https://help.mikrotik.com/docs/spaces/ROS/pages/47579162/REST+API), [Services](https://help.mikrotik.com/docs/spaces/ROS/pages/103841820/Services), [WiFi](https://help.mikrotik.com/docs/display/ros/wifi), [file reference](https://manual.mikrotik.com/docs/cli-reference/file/)), the MikroTik forum threads linked below, and what the real hAP ax² (RouterOS 7.24.2) did on 2026-10-13. "Router-verified" means seen on that router.

## Basics

- REST (RouterOS 7.1+) is a JSON wrapper over the console API at `https://<router>/rest`, served by `www-ssl`. HTTP Basic auth. MikroMagic uses HTTPS only, restricted to the Hub tunnel address.
- Verbs: `GET` = print, `PATCH` = set (one record), `PUT` = add (one record per request), `DELETE` = remove, `POST /rest/<menu>/<command>` = any console command.
- All values come back as strings (`"true"`, `"25"`).
- Records are addressed by id in the path, written literally: `/rest/ip/address/*3`. Router-verified: `%2A3` fails with `400 no such command prefix`. Named menus also accept the name (`/rest/interface/ether1`).
- `DELETE` must carry no body (router-verified); success is an empty reply, a second delete is `404`.
- Filtering: `?name=value&other=value`; projection: `?.proplist=a,b`. `POST .../print` accepts `.proplist` and `.query` (API query stack).
- Errors: status ≥ 400 with `{"error":…, "message":…, "detail":…}`. Missing group policy shows as `500 not enough permissions (9)` ([forum](https://forum.mikrotik.com/t/dedicated-user-cant-access-api/166242)). A REST user needs `api,rest-api` plus `read` (and `write` for changes).

## Limits that shape the app

- **60-second timeout per request**; long-running commands (ping without `count`, monitors) end with `Session closed`. Use `once`/`count`/`duration`.
- **Requests are processed one at a time per router.** Parallel requests queue; a slow command delays everything behind it and aborting the client socket does not free the router ([forum #266665](https://forum.mikrotik.com/t/routeros-rest-api-requests-running-in-series/266665), [terraform-routeros #976](https://github.com/terraform-routeros/terraform-provider-routeros/issues/976)). MikroMagic holds a **per-router REST lock** for the whole `RouterOSClient` session (PostgreSQL `pg_advisory_lock` across API workers / Safe Change worker; in-process lock for SQLite tests) so monitoring, HotSpot collect/sync and Safe Change never interleave. Prefer one bulk `GET` with `.proplist` over many per-id reads, and keep monitoring/collect intervals modest. Contended callers receive `409 router_busy`.
- `www-ssl max-sessions` defaults to 20 (1–1000).
- No continuous/streaming commands over REST.

## Files

- Create with `PUT /rest/file {"name":"dir/file.html","contents":"…"}`; the parent directory is created automatically and an existing file is refused (`failure: file already exists`) — router-verified, usable as create-only.
- `contents` is limited to 61439 bytes when creating. Reading `contents` back is unreliable: router-verified, a 5631-byte `login.html` returned empty `contents`; verify by name and `size` instead.
- Listing without `.proplist` inlines file contents and breaks on binary files (router-verified); always list with `?.proplist=name,type,size,last-modified`.
- `.json` files are refused (`failure: permission denied`, router-verified). `.html`/`.txt` work.
- Delete a file with `DELETE /rest/file/<url-encoded name>`; remove a directory with `POST /rest/file/remove {".id":"*…"}` (router-verified).
- Larger files: `/file/read` with offset and chunk-size (≤32768) exists in recent v7 ([forum](https://forum.mikrotik.com/t/max-variable-size-and-reading-from-or-writing-to-files/183209)).

## Configuration export (Safe Change backup)

- `POST /rest/export` writes to a file and returns `[]` by design ([forum #263182](https://forum.mikrotik.com/t/restapi-export-backup/263182)) — router-verified.
- Workaround in use: `POST /rest/execute {"script":"/export terse","as-string":""}` returns `{"ret":"# … by RouterOS …"}`; RouterOS 7 hides secrets unless `show-sensitive` is given. Router-verified: 10.9 KB export.
- Completeness (software): Safe Change always writes `/export file=` first, reads listed size via `/file?.proplist=…`, prefers chunked `/file/read`, and only falls back to `execute as-string` when that length is not substantially shorter than the file size (`backup_incomplete` otherwise). Temp `.rsc` files are deleted after the read.
- REST exports can differ cosmetically from CLI exports (for example missing `KiB` units, [forum #262819](https://forum.mikrotik.com/t/inconsistence-between-config-export-from-rest-api-vs-webui/262819)); both import, but restore must be tested on hardware.

## Wi-Fi (RouterOS 7.13+ `/interface/wifi`)

- SSID and security can be set inline on the interface: `PATCH /rest/interface/wifi/<id> {"configuration.ssid":"…","security.authentication-types":"wpa2-psk,wpa3-psk","security.passphrase":"…"}`, or through named profiles in `/interface/wifi/configuration` and `/interface/wifi/security` that several interfaces may share.
- Open network = empty `authentication-types`. WPA/WPA2-PSK needs a passphrase of 8–63 characters.
- `passphrase` is a sensitive property: users without the `sensitive` policy (MikroMagic's Safe Change group) cannot read it, so verification must use authentication types and other non-secret fields, never the passphrase.
- Changing SSID/security disconnects associated clients.

## HotSpot

- Login page files live under the profile's `html-directory`; any directory name works (`/ip hotspot profile set html-directory=…`).
- RouterOS HotSpot user names are case-sensitive (router-verified); MikroMagic codes are stored upper-case and the guest page normalizes input.
- `$(chap-id)`/`$(chap-challenge)` are raw bytes (octal escapes); the page's MD5 must hash them as single bytes, not UTF-8 (router-verified bug, fixed).
- HotSpot user profiles have no `comment` field on 7.24.2 (router-verified).
