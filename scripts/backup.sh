#!/bin/bash
# =============================================================================
#  NGS-LIMS — PostgreSQL daily backup
#  Saves a compressed .sql.gz file, keeps the last N days, logs everything.
#
#  DB_NAME / DB_USER / DB_HOST / DB_PORT are read automatically from the
#  project's .env file, so this script always matches whatever the app is
#  actually configured to use — no manual editing, no risk of drifting out
#  of sync with restore.sh or the running app.
#
#  Setup:
#    1. chmod +x backup.sh
#    2. Add to cron: crontab -e
#       0 2 * * * /path/to/backup.sh   ← runs every day at 2 AM
#    (see scripts/README.md for passwordless-auth / .pgpass setup)
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_FILE="$PROJECT_ROOT/.env"

if [ ! -f "$ENV_FILE" ]; then
    echo "ERROR: .env not found at $ENV_FILE — cannot read DB credentials." >&2
    exit 1
fi

# Load DB_* values from .env without executing arbitrary lines in it.
set -a
# shellcheck disable=SC1090
source <(grep -E '^(DB_NAME|DB_USER|DB_HOST|DB_PORT)=' "$ENV_FILE")
set +a

# ── CONFIG ───────────────────────────────────────────────────────────────────
# DB_NAME / DB_USER / DB_HOST / DB_PORT come from .env above.
# Only backup-specific settings live here:
BACKUP_DIR="$SCRIPT_DIR/ngs-lims-backups"   # where backups are stored
KEEP_DAYS=30                                 # how many days of backups to keep
LOG_FILE="$BACKUP_DIR/backup.log"            # log file location
# ─────────────────────────────────────────────────────────────────────────────

: "${DB_NAME:?DB_NAME missing from .env}"
: "${DB_USER:?DB_USER missing from .env}"
: "${DB_HOST:?DB_HOST missing from .env}"
: "${DB_PORT:?DB_PORT missing from .env}"

TIMESTAMP=$(date +"%Y-%m-%d_%H-%M-%S")
FILENAME="ngs_lims_${TIMESTAMP}.sql.gz"
BACKUP_PATH="$BACKUP_DIR/$FILENAME"

mkdir -p "$BACKUP_DIR"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')]  $1" | tee -a "$LOG_FILE"
}

log "------------------------------------------------------------"
log "Starting backup of '$DB_NAME'@'$DB_HOST' → $FILENAME"

pg_dump \
    -h "$DB_HOST" \
    -p "$DB_PORT" \
    -U "$DB_USER" \
    -d "$DB_NAME" \
    --format=plain \
    --no-password \
    | gzip > "$BACKUP_PATH"

if [ -s "$BACKUP_PATH" ]; then
    SIZE=$(du -sh "$BACKUP_PATH" | cut -f1)
    log "Backup successful — $SIZE written to $BACKUP_PATH"
else
    log "ERROR — backup failed or file is empty. Check PostgreSQL connection."
    rm -f "$BACKUP_PATH"
    exit 1
fi

DELETED=$(find "$BACKUP_DIR" -name "ngs_lims_*.sql.gz" -mtime +$KEEP_DAYS -print -delete)
if [ -n "$DELETED" ]; then
    log "Pruned old backups:"
    echo "$DELETED" | while read -r f; do log "  removed: $(basename "$f")"; done
fi

COUNT=$(find "$BACKUP_DIR" -name "ngs_lims_*.sql.gz" | wc -l)
log "Backup complete. $COUNT backup(s) on disk."
