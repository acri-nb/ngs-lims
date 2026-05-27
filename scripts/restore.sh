#!/bin/bash
# =============================================================================
#  NGS-LIMS — PostgreSQL restore / rollback
#
#  Usage:
#    ./restore.sh                        ← lists available backups, picks latest
#    ./restore.sh ngs_lims_2026-01-15_02-00-00.sql.gz   ← restore specific file
# =============================================================================

# ── CONFIG (must match backup.sh) ────────────────────────────────────────────
DB_NAME="ngs_lims"
DB_USER="postgres"
DB_HOST="localhost"
DB_PORT="5432"
BACKUP_DIR="$./ngs-lims-backups"
# ─────────────────────────────────────────────────────────────────────────────

RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
NC='\033[0m' # no color

echo ""
echo -e "${CYAN}NGS-LIMS — Database Restore${NC}"
echo "============================================"

# ── Pick the backup file ──────────────────────────────────────────────────────
if [ -n "$1" ]; then
    # File passed as argument
    if [[ "$1" = /* ]]; then
        BACKUP_FILE="$1"           # absolute path
    else
        BACKUP_FILE="$BACKUP_DIR/$1"   # just filename
    fi

    if [ ! -f "$BACKUP_FILE" ]; then
        echo -e "${RED}Error: file not found — $BACKUP_FILE${NC}"
        exit 1
    fi
else
    # No argument — list available backups and let user choose
    mapfile -t FILES < <(find "$BACKUP_DIR" -name "ngs_lims_*.sql.gz" | sort -r)

    if [ ${#FILES[@]} -eq 0 ]; then
        echo -e "${RED}No backups found in $BACKUP_DIR${NC}"
        exit 1
    fi

    echo ""
    echo "Available backups (newest first):"
    echo ""
    for i in "${!FILES[@]}"; do
        SIZE=$(du -sh "${FILES[$i]}" | cut -f1)
        NAME=$(basename "${FILES[$i]}")
        printf "  %2d)  %s  (%s)\n" $((i+1)) "$NAME" "$SIZE"
    done

    echo ""
    read -p "Enter number to restore (or q to quit): " CHOICE

    if [[ "$CHOICE" == "q" || "$CHOICE" == "Q" ]]; then
        echo "Cancelled."
        exit 0
    fi

    if ! [[ "$CHOICE" =~ ^[0-9]+$ ]] || [ "$CHOICE" -lt 1 ] || [ "$CHOICE" -gt ${#FILES[@]} ]; then
        echo -e "${RED}Invalid choice.${NC}"
        exit 1
    fi

    BACKUP_FILE="${FILES[$((CHOICE-1))]}"
fi

BACKUP_NAME=$(basename "$BACKUP_FILE")
echo ""
echo -e "${YELLOW}⚠  WARNING: This will OVERWRITE the current database '${DB_NAME}'.${NC}"
echo -e "   Restoring from: ${CYAN}${BACKUP_NAME}${NC}"
echo ""
read -p "Type  RESTORE  to confirm: " CONFIRM

if [ "$CONFIRM" != "RESTORE" ]; then
    echo -e "${YELLOW}Cancelled — database was not changed.${NC}"
    exit 0
fi

echo ""
echo "Step 1/3 — Creating a safety backup of current state before overwriting..."

SAFETY_TIMESTAMP=$(date +"%Y-%m-%d_%H-%M-%S")
SAFETY_FILE="$BACKUP_DIR/ngs_lims_PRE-RESTORE_${SAFETY_TIMESTAMP}.sql.gz"

pg_dump \
    -h "$DB_HOST" \
    -p "$DB_PORT" \
    -U "$DB_USER" \
    -d "$DB_NAME" \
    --format=plain \
    --no-password \
    | gzip > "$SAFETY_FILE"

if [ $? -eq 0 ] && [ -s "$SAFETY_FILE" ]; then
    SIZE=$(du -sh "$SAFETY_FILE" | cut -f1)
    echo -e "  ${GREEN}Safety backup saved: $(basename $SAFETY_FILE) ($SIZE)${NC}"
else
    echo -e "${RED}Could not create safety backup — aborting restore.${NC}"
    rm -f "$SAFETY_FILE"
    exit 1
fi

echo ""
echo "Step 2/3 — Dropping and recreating database schema..."

# Drop all tables by dropping and recreating the public schema
psql \
    -h "$DB_HOST" \
    -p "$DB_PORT" \
    -U "$DB_USER" \
    -d "$DB_NAME" \
    --no-password \
    -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;" \
    > /dev/null 2>&1

if [ $? -ne 0 ]; then
    echo -e "${RED}Error clearing database. Check your PostgreSQL connection.${NC}"
    exit 1
fi
echo -e "  ${GREEN}Schema cleared.${NC}"

echo ""
echo "Step 3/3 — Restoring from backup..."

gunzip -c "$BACKUP_FILE" | psql \
    -h "$DB_HOST" \
    -p "$DB_PORT" \
    -U "$DB_USER" \
    -d "$DB_NAME" \
    --no-password \
    > /dev/null 2>&1

if [ $? -eq 0 ]; then
    echo -e "  ${GREEN}Restore successful.${NC}"
    echo ""
    echo -e "${GREEN}✓ Database restored from: ${BACKUP_NAME}${NC}"
    echo -e "  Safety backup kept at:    $(basename $SAFETY_FILE)"
    echo ""
else
    echo -e "${RED}Restore failed. Your safety backup is at:${NC}"
    echo -e "  $SAFETY_FILE"
    echo ""
    exit 1
fi
