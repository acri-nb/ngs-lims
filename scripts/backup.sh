#!/bin/bash
# =============================================================================
#  NGS-LIMS — PostgreSQL daily backup
#  Saves a compressed .sql.gz file, keeps the last N days, logs everything.
#
#  Setup:
#    1. Edit the CONFIG block below
#    2. chmod +x backup.sh
#    3. Add to cron: crontab -e
#       0 2 * * * /path/to/backup.sh   ← runs every day at 2 AM
# =============================================================================

# ── CONFIG ────────────────────────────────────────────────────────────────────
DB_NAME="ngs_lims"             # your PostgreSQL database name
DB_USER="postgres"             # your PostgreSQL user
DB_HOST="localhost"            # usually localhost
DB_PORT="5432"                 # usually 5432

BACKUP_DIR="./ngs-lims-backups"   # where backups are stored
KEEP_DAYS=30                          # how many days of backups to keep
LOG_FILE="$BACKUP_DIR/backup.log"     # log file location
# ─────────────────────────────────────────────────────────────────────────────

TIMESTAMP=$(date +"%Y-%m-%d_%H-%M-%S")
FILENAME="ngs_lims_${TIMESTAMP}.sql.gz"
BACKUP_PATH="$BACKUP_DIR/$FILENAME"

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')]  $1" | tee -a "$LOG_FILE"
}

log "------------------------------------------------------------"
log "Starting backup → $FILENAME"

# Run pg_dump and compress on the fly
pg_dump \
    -h "$DB_HOST" \
    -p "$DB_PORT" \
    -U "$DB_USER" \
    -d "$DB_NAME" \
    --format=plain \
    --no-password \
    | gzip > "$BACKUP_PATH"

# Check if backup succeeded
if [ $? -eq 0 ] && [ -s "$BACKUP_PATH" ]; then
    SIZE=$(du -sh "$BACKUP_PATH" | cut -f1)
    log "Backup successful — $SIZE written to $BACKUP_PATH"
else
    log "ERROR — backup failed or file is empty. Check PostgreSQL connection."
    rm -f "$BACKUP_PATH"   # remove empty file
    exit 1
fi

# Delete backups older than KEEP_DAYS
DELETED=$(find "$BACKUP_DIR" -name "ngs_lims_*.sql.gz" -mtime +$KEEP_DAYS -print -delete)
if [ -n "$DELETED" ]; then
    log "Pruned old backups:"
    echo "$DELETED" | while read f; do log "  removed: $(basename $f)"; done
fi

# Show how many backups exist now
COUNT=$(find "$BACKUP_DIR" -name "ngs_lims_*.sql.gz" | wc -l)
log "Backup complete. $COUNT backup(s) on disk."
