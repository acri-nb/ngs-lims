# NGS-LIMS Database Backup & Restore

## First-time setup

### 1. Put the scripts somewhere permanent

```bash
mkdir -p ~/ngs-lims-scripts
cp backup.sh restore.sh ~/ngs-lims-scripts/
chmod +x ~/ngs-lims-scripts/backup.sh
chmod +x ~/ngs-lims-scripts/restore.sh
```

### 2. Edit the CONFIG block in both scripts

Open each file and set these at the top:

```bash
DB_NAME="ngs_lims"      # your actual database name
DB_USER="postgres"      # your PostgreSQL user
DB_HOST="localhost"
DB_PORT="5432"
BACKUP_DIR="./ngs-lims-backups"   # where backups are saved
```

### 3. Allow passwordless pg_dump (so cron can run without a password prompt)

Create a `.pgpass` file:

```bash
echo "localhost:5432:ngs_lims:postgres:YOUR_PASSWORD" >> ~/.pgpass
chmod 600 ~/.pgpass
```

Format is: `host:port:database:user:password`

### 4. Schedule daily automatic backups with cron

```bash
crontab -e
```

Add this line (runs every day at 2 AM):

```
0 2 * * * /home/mathieu/ngs-lims-scripts/backup.sh
```

Other schedule options:
```
0 2 * * *     every day at 2 AM          ← recommended
0 2 * * 0     every Sunday at 2 AM
0 */6 * * *   every 6 hours
```

### 5. Test it manually first

```bash
~/ngs-lims-scripts/backup.sh
```

You should see a `.sql.gz` file appear in `~/ngs-lims-backups/`.

---

## Daily use

### Run a manual backup anytime

```bash
~/ngs-lims-scripts/backup.sh
```

### List backups and restore one

```bash
~/ngs-lims-scripts/restore.sh
```

This shows a numbered list of all backups. Pick a number, type `RESTORE` to confirm.
Before overwriting, it **automatically saves a safety backup** of the current state.

### Restore a specific file directly

```bash
~/ngs-lims-scripts/restore.sh ngs_lims_2026-01-15_02-00-00.sql.gz
```

---

## Backup file naming

```
ngs_lims_2026-01-15_02-00-00.sql.gz       ← regular daily backup
ngs_lims_PRE-RESTORE_2026-01-15_14-32-11.sql.gz  ← auto-saved before a restore
```

---

## Backup location

All files go to `~/ngs-lims-backups/` by default.
Old backups are automatically deleted after 30 days (set `KEEP_DAYS` in backup.sh).

---

## Check the backup log

```bash
cat ./ngs-lims-backups/backup.log
```
