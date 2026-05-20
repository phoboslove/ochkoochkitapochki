#!/usr/bin/env bash
# Hourly Postgres + MinIO snapshot. Run via cron on the host:
#   0 * * * * /opt/buchuchet/infra/backup.sh >> /var/log/buchuchet-backup.log 2>&1
set -euo pipefail
ROOT="${BACKUP_DIR:-/var/backups/buchuchet}"
STAMP="$(date -u +%Y%m%d-%H%M%S)"
mkdir -p "$ROOT/db" "$ROOT/storage"

# Database
docker compose -f docker-compose.prod.yml exec -T postgres \
  pg_dump -U "${POSTGRES_USER:-buchuchet}" "${POSTGRES_DB:-buchuchet}" \
  | gzip > "$ROOT/db/$STAMP.sql.gz"

# Object storage (mirrors bucket using mc); skip if mc isn't present.
if command -v mc >/dev/null; then
  mc alias set local http://localhost:9000 "$S3_ACCESS_KEY" "$S3_SECRET_KEY" >/dev/null
  mc mirror --remove --overwrite "local/${S3_BUCKET:-buchuchet}" "$ROOT/storage/$STAMP/"
fi

# Retain last 14 days
find "$ROOT/db"      -type f -mtime +14 -delete
find "$ROOT/storage" -mindepth 1 -maxdepth 1 -type d -mtime +14 -exec rm -rf {} +
echo "[$STAMP] backup complete"
