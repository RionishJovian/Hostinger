#!/bin/zsh
# Pull verified nightly MikroMagic Build 21 backups from the Hostinger VPS to this Mac (off-VPS copy).
# Copies are checked against the VPS SHA256SUMS files; local copies older than 30 days are removed.
set -euo pipefail
DEST="$HOME/MikroMagic-offhost-backups"
umask 077
mkdir -p "$DEST"
rsync -a -e "ssh -o BatchMode=yes -o ConnectTimeout=20" "mikromagic-hostinger:/var/backups/mikromagic-build21/" "$DEST/"
cd "$DEST"
for sums in SHA256SUMS_*(N); do shasum -a 256 -c "$sums" >/dev/null || { echo "$(date -u +%FT%TZ) CHECKSUM FAILED: $sums"; exit 1; }; done
find "$DEST" -type f -mtime +30 -delete
echo "$(date -u +%FT%TZ) pulled and verified $(ls -1 db_*.dump 2>/dev/null | wc -l | tr -d ' ') database backups"
