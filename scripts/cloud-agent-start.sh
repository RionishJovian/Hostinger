#!/usr/bin/env bash
# Cursor cloud agent start step: sets up `ssh mikromagic-hostinger` from the
# MIKROMAGIC_VPS_SSH_KEY_B64 runtime secret (base64 of the dedicated cloud agent key).
set -euo pipefail
cd "$(dirname "$0")/.."
if [ -z "${MIKROMAGIC_VPS_SSH_KEY_B64:-}" ]; then
  echo "MIKROMAGIC_VPS_SSH_KEY_B64 is not set; VPS access is unavailable in this agent."
  exit 0
fi
umask 077
install -d -m 700 ~/.ssh
printf '%s' "$MIKROMAGIC_VPS_SSH_KEY_B64" | base64 -d > ~/.ssh/mikromagic-hostinger
cp deploy/known_hosts.hostinger ~/.ssh/known_hosts.mikromagic
if ! grep -qx 'Host mikromagic-hostinger' ~/.ssh/config 2>/dev/null; then
  cat >> ~/.ssh/config <<EOF
Host mikromagic-hostinger
    HostName 156.67.216.128
    User root
    IdentityFile $HOME/.ssh/mikromagic-hostinger
    IdentitiesOnly yes
    UserKnownHostsFile $HOME/.ssh/known_hosts.mikromagic
    StrictHostKeyChecking yes
EOF
fi
echo "VPS access configured: ssh mikromagic-hostinger"
