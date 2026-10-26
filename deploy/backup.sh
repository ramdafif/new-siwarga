#!/usr/bin/env bash
set -euo pipefail
umask 077
cd /srv/siwarga/current
: "${BACKUP_DIRECTORY:?}" "${BACKUP_METRICS:?}" "${BACKUP_LOCK:?}"
mkdir -p "$BACKUP_DIRECTORY" "$(dirname "$BACKUP_METRICS")"
write_failure() {
  printf 'siwarga_backup_last_attempt_success 0\n' > "$BACKUP_METRICS.attempt.tmp"
  chmod 0640 "$BACKUP_METRICS.attempt.tmp"
  mv "$BACKUP_METRICS.attempt.tmp" "$BACKUP_METRICS.attempt.prom"
}
trap write_failure ERR
result=$(/srv/siwarga/current/.venv/bin/python scripts/backup.py create --output "$BACKUP_DIRECTORY" --lock "$BACKUP_LOCK")
snapshot=$(printf '%s' "$result" | /srv/siwarga/current/.venv/bin/python -c 'import json,sys; print(json.load(sys.stdin)["snapshot"])')
restic backup --tag siwarga -- "$snapshot"
restic check --read-data-subset=5%
restic forget --tag siwarga --group-by tags --keep-daily 14 --keep-weekly 4 --prune
/srv/siwarga/current/.venv/bin/python scripts/backup.py prune-local --output "$BACKUP_DIRECTORY"
snapshot_timestamp=$(/srv/siwarga/current/.venv/bin/python -c 'from datetime import datetime; import json,sys; print(int(datetime.fromisoformat(json.load(open(sys.argv[1]))["snapshot_at"]).timestamp()))' "$snapshot/manifest.json")
printf 'siwarga_backup_last_success_timestamp_seconds %s\n' "$snapshot_timestamp" > "$BACKUP_METRICS.tmp"
chmod 0640 "$BACKUP_METRICS.tmp"
mv "$BACKUP_METRICS.tmp" "$BACKUP_METRICS"
printf 'siwarga_backup_last_attempt_success 1\n' > "$BACKUP_METRICS.attempt.tmp"
chmod 0640 "$BACKUP_METRICS.attempt.tmp"
mv "$BACKUP_METRICS.attempt.tmp" "$BACKUP_METRICS.attempt.prom"
