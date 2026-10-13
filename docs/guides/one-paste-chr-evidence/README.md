# One-paste CHR evidence — skipped 2026-10-13

Part C (optional, ~20 minute time box) did **not** complete a full CHR enroll.

## Attempted
- Installed `qemu-system-x86` and `qemu-utils` on the cloud agent.
- Started download of official CHR 7.12.1 from `download.mikrotik.com` with `timeout 300` / `curl --max-time 120`.
- Download reached ~29 MB of ~39 MB then timed out; zip was incomplete and could not be unpacked.

## Decision
Skipped full QEMU boot + script paste against a local test hub rather than hang or extend the window. Software correctness for the generated script is covered by static unit tests in `tests/test_magic_hub_one_paste.py`. Hardware/CHR verification remains for an owner-gated window or a later dedicated lab run.
