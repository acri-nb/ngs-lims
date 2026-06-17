# Maintenance Guide

This document covers routine maintenance tasks, database management, dependency updates, and troubleshooting for NGS-LIMS. (Could change in the future)

---

## 1. Routine tasks

### 1.1 Verify backups

Check that the nightly backup cron job is running:

```bash
cat ~/ngs-lims-backups/backup.log
ls -lht ~/ngs-lims-backups/ | head -10
```

The log should show a successful entry for the previous night. If it is missing, check that the cron job is registered (`crontab -l`) and that the script is executable (`ls -l ~/ngs-lims-scripts/backup.sh`).

### 1.2 Check service status

```bash
sudo systemctl status ngs-lims
sudo systemctl status postgresql
sudo systemctl status nginx
```

All three should be `active (running)`. If any is failed, check the journal:

```bash
journalctl -u ngs-lims -n 50
```

### 1.3 Review error logs

```bash
tail -100 /var/log/ngs-lims/error.log
tail -100 /var/log/nginx/error.log
```

Look for recurring 500 errors, database connection failures, or import/export errors.

---

## 2. Database management

### 2.1 Manual backup

```bash
~/ngs-lims-scripts/backup.sh
```

This produces a `ngs_lims_YYYY-MM-DD_HH-MM-SS.sql.gz` file in the backup directory.

### 2.2 Restore from backup

```bash
~/ngs-lims-scripts/restore.sh
```

The script lists available backups and prompts for confirmation. Before overwriting, it saves an automatic pre-restore snapshot named `ngs_lims_PRE-RESTORE_<timestamp>.sql.gz`.

To restore a specific file directly:

```bash
~/ngs-lims-scripts/restore.sh ngs_lims_2026-01-15_02-00-00.sql.gz
```

### 2.3 Applying migrations

After pulling code that includes model changes:

```bash
conda activate ngs-lims
python manage.py showmigrations      # review pending migrations
python manage.py migrate --noinput
```

Never run `migrate` directly against a production database without first taking a manual backup. If a migration fails partway through, PostgreSQL will roll it back automatically (Django migrations run inside a transaction), but a backup ensures you can recover from any edge case.

### 2.4 Creating new migrations

After modifying a model:

```bash
python manage.py makemigrations
python manage.py migrate
```

Review the generated migration file before committing. Confirm that:

- `ALTER TABLE` statements are non-destructive (no unintended column drops)
- Fields with `null=False` have a default defined to avoid locking issues on large tables
- The migration is reversible if possible

### 2.5 Direct database access

```bash
sudo -u postgres psql -d ngs_lims_db
```

Useful queries:

```sql
-- Row counts per table
SELECT relname, n_live_tup FROM pg_stat_user_tables ORDER BY n_live_tup DESC;

-- Check for long-running queries
SELECT pid, now() - query_start AS duration, query
FROM pg_stat_activity
WHERE state = 'active'
ORDER BY duration DESC;
```

---

## 3. Django admin

The admin panel at `/admin/` provides direct CRUD access to all models. It is primarily used for:

- Creating and managing user accounts
- Adding `UserProfile` entries to link researchers to their `Client` records
- Adding new `Location` entries (storage units)
- Adding `SpecimenType` entries
- Correcting data entry errors that cannot be fixed through the UI

Access to the admin panel is restricted to superusers and staff-flagged accounts.

### 3.1 Creating a user account

```
Admin > Authentication and Authorization > Users > Add User
```

Set a username and password, then save. On the next page, set:

- **Staff status**: enable for lab staff (gives admin access)
- **Superuser status**: enable only for system administrators

For researcher accounts, do not set staff or superuser status. Instead, create a `UserProfile` under `Samples > User Profiles` and link it to the appropriate `Client`.

### 3.2 Resetting a password

```bash
python manage.py changepassword <username>
```

Or via the admin panel: open the user record and click **Change password**.

---

## 4. Dependency updates

### 4.1 Check for outdated packages

```bash
conda activate ngs-lims
pip list --outdated
```

### 4.2 Update a specific package

```bash
pip install --upgrade <package>
pip freeze > requirements.txt
```

Test locally before updating production. Django minor version updates (e.g. 4.2.x) are generally safe. Major version updates (e.g. 4.x to 5.x) require reviewing the deprecation notes in the Django release notes and running the full test suite.

### 4.3 After updating Django

Check for deprecation warnings by running the development server and exercising the main workflows. Django emits `RemovedInDjango<version>Warning` for code paths that will break in the next major version.

---

## 5. Troubleshooting

### 5.1 Static files not loading (CSS/JS missing)

Likely cause: `collectstatic` was not run after a deployment, or the `STATIC_ROOT` path does not match the Nginx `alias` directive.

```bash
python manage.py collectstatic --noinput
sudo systemctl reload nginx
```

### 5.2 500 errors on sample import

The import view decodes the uploaded CSV as UTF-8. Files exported from Excel in certain locales may use Latin-1 or UTF-16. Ask the submitter to re-save the file as UTF-8 CSV, or add encoding detection to `samples/views.py`:

```python
decoded = csv_file.read()
try:
    content = decoded.decode('utf-8')
except UnicodeDecodeError:
    content = decoded.decode('latin-1')
```

### 5.3 QC status stuck on Pending

Status is calculated from the stored metric values in `SampleQC.calculate_qc_status()`. If a sample is stuck on Pending, the most likely cause is that a required field was left null. Check the batch detail page and ensure all required fields for the sample type are filled in.

If metrics were entered correctly but the status did not update, trigger a recalculation by saving the record again (e.g. via the admin panel).

### 5.4 Database connection errors at startup

Check that PostgreSQL is running and that the credentials in `.env` match the database:

```bash
sudo systemctl status postgresql
sudo -u postgres psql -U lims_user -d ngs_lims_db -c "SELECT 1;"
```

If the connection is refused, PostgreSQL may not be listening on the expected host/port. Check `postgresql.conf` (`listen_addresses`) and `pg_hba.conf` (authentication rules).

### 5.5 Migrations out of sync

If `python manage.py showmigrations` shows unapplied migrations that should already be applied (e.g. after restoring from a backup taken before those migrations existed), you may need to fake the migration state:

```bash
# Only use --fake if the database schema already reflects the migration
python manage.py migrate --fake <app_name> <migration_name>
```

This is an advanced operation, take a backup first and confirm the actual schema state with `\d <table>` in psql.

---

## 6. Clearing development data

To reset the database during development without dropping and recreating it:

```bash
python manage.py flush --noinput
python manage.py createsuperuser
```

`flush` deletes all data but preserves the schema. Do not run this on production.

---

## 7. Conda environment

### Recreate from scratch

```bash
conda create -n ngs-lims python=3.9
conda activate ngs-lims
pip install -r requirements.txt
```

### Export the current environment

```bash
pip freeze > requirements.txt
```

Commit `requirements.txt` after any dependency change.