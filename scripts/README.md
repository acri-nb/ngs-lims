# NGS-LIMS Scripts

## `setup_dev.sh` / `setup_production.sh`

One-shot environment bootstrap for development and production respectively. See the root `README.md` for what each one does. Both are safe to re-run.

---

## Database Backup & Restore

`backup.sh` and `restore.sh` read `DB_NAME` / `DB_USER` / `DB_HOST` / `DB_PORT` **directly from the project's `.env` file** there's nothing to configure inside the scripts themselves, and the two scripts can never drift out of sync with each other or with what the app is actually connected to.

### First-time setup

#### 1. Make the scripts executable

```bash
chmod +x scripts/backup.sh scripts/restore.sh
```

They can be run from anywhere — they locate the project root (and `.env`) relative to their own location, not your current directory.

#### 2. Allow passwordless `pg_dump`/`psql` (so cron can run without a password prompt)

Create a `.pgpass` file for the user that will run the scripts (e.g. the account cron runs as):

```bash
echo "localhost:5432:ngs_lims_db:lims_user:YOUR_PASSWORD" >> ~/.pgpass
chmod 600 ~/.pgpass
```

Format is `host:port:database:user:password` match whatever's actually in your `.env`.

#### 3. Schedule daily automatic backups with cron

`scripts/setup_production.sh` offers to add this for you. To do it manually:

```bash
crontab -e
```

```
0 2 * * * /path/to/ngs-lims/scripts/backup.sh   ← runs every day at 2 AM
```

Other schedule options:
```
0 2 * * *     every day at 2 AM          ← recommended
0 2 * * 0     every Sunday at 2 AM
0 */6 * * *   every 6 hours
```

#### 4. Test it manually first

```bash
./scripts/backup.sh
```

You should see a `.sql.gz` file appear in `scripts/ngs-lims-backups/`.

---

## Daily use

### Run a manual backup anytime

```bash
./scripts/backup.sh
```

### List backups and restore one

```bash
./scripts/restore.sh
```

Shows a numbered list of all backups. Pick a number, type `RESTORE` to confirm. Before overwriting, it **automatically saves a safety backup** of the current state first.

### Restore a specific file directly

```bash
./scripts/restore.sh ngs_lims_2026-01-15_02-00-00.sql.gz
```

---

## Backup file naming

```
ngs_lims_2026-01-15_02-00-00.sql.gz               ← regular scheduled backup
ngs_lims_PRE-RESTORE_2026-01-15_14-32-11.sql.gz   ← auto-saved before a restore
```

---

## Backup location

All files go to `scripts/ngs-lims-backups/` by default (gitignored). Old backups are automatically deleted after 30 days, change `KEEP_DAYS` near the top of `backup.sh` if you want a different retention window.

---

## Check the backup log

```bash
cat scripts/ngs-lims-backups/backup.log
```
