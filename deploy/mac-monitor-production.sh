#!/bin/zsh
# Production health check for megamagic.tech, run from the owner's Mac by launchd.
# Notifies (macOS notification) when the set of failures changes, including recovery.
set -u
STATE_DIR="$HOME/Library/Application Support/MikroMagic"
STATE="$STATE_DIR/production-monitor.state"
BACKUPS="$HOME/MikroMagic-offhost-backups"
CERT_MIN_DAYS=21
BACKUP_MAX_HOURS=50
PROJECT=mikromagic-build21-public-test
failures=()

[ "$(curl -s -o /dev/null -m 20 -w '%{http_code}' https://megamagic.tech/v1/ready)" = 200 ] || failures+=("API not ready")

for host in megamagic.tech www.megamagic.tech; do
  end=$(echo | openssl s_client -servername $host -connect $host:443 2>/dev/null | openssl x509 -noout -enddate 2>/dev/null | cut -d= -f2)
  if [ -z "$end" ]; then failures+=("$host certificate unreadable"); continue; fi
  days=$(( ($(date -j -f '%b %e %T %Y %Z' "$end" +%s) - $(date +%s)) / 86400 ))
  [ $days -ge $CERT_MIN_DAYS ] || failures+=("$host certificate expires in $days days")
done

dumps=( "$BACKUPS"/db_*.dump(N.om) )
newest=${dumps[1]:-}
if [ -z "$newest" ]; then failures+=("no off-VPS backup copy")
else
  age=$(( ($(date +%s) - $(stat -f %m "$newest")) / 3600 ))
  [ $age -le $BACKUP_MAX_HOURS ] || failures+=("off-VPS backup is $age hours old")
fi

remote=$(ssh -o BatchMode=yes -o ConnectTimeout=20 mikromagic-hostinger "
  for s in db api web magic-hub; do printf '%s=%s\n' \$s \"\$(docker inspect -f '{{.State.Health.Status}}' $PROJECT-\$s-1 2>/dev/null || echo missing)\"; done
  printf 'hubport=%s\n' \"\$(docker port $PROJECT-magic-hub-1 51820/udp 2>/dev/null | head -1)\"
  printf 'backup=%s\n' \"\$(systemctl show -p Result --value mikromagic-build21-backup.service)\"
  printf 'disk=%s\n' \"\$(df --output=pcent / | tail -1 | tr -dc 0-9)\"" 2>/dev/null)
if [ -z "$remote" ]; then failures+=("VPS unreachable over SSH")
else
  for s in db api web magic-hub; do
    st=$(print -r -- "$remote" | sed -n "s/^$s=//p"); [ "$st" = healthy ] || failures+=("$s container $st")
  done
  print -r -- "$remote" | grep -q '^hubport=156.67.216.128:51820$' || failures+=("Hub UDP 51820 not published")
  [ "$(print -r -- "$remote" | sed -n 's/^backup=//p')" = success ] || failures+=("VPS nightly backup failed")
  disk=$(print -r -- "$remote" | sed -n 's/^disk=//p'); [ "${disk:-100}" -lt 85 ] || failures+=("VPS disk ${disk}% full")
fi

summary=${(j:; :)failures}
previous=$(cat "$STATE" 2>/dev/null || true)
print -r -- "$summary" > "$STATE"
stamp=$(date -u +%FT%TZ)
if [ -n "$summary" ]; then
  echo "$stamp FAIL: $summary"
  [ "$summary" = "$previous" ] || osascript -e "display notification \"${summary//\"/}\" with title \"MegaMagic production problem\" sound name \"Basso\""
  exit 1
fi
echo "$stamp OK"
[ -z "$previous" ] || osascript -e 'display notification "All checks pass again." with title "MegaMagic production recovered"'
