# Production Deployment

This document covers deploying NGS-LIMS in a production environment. The development setup described in the README is not suitable for production `DEBUG=True`, the built-in development server, and an unprotected secret key must all be replaced. (Could change in the future)

---

## Stack

The recommended production stack is:

- **Application server**: Gunicorn (WSGI)
- **Reverse proxy**: Nginx
- **Database**: PostgreSQL 16
- **Process manager**: systemd
- **OS**: Debian/Ubuntu or Arch Linux

---

## 1. Environment configuration

Copy `.env.example` to `.env` and set all values:

```bash
DB_ENGINE=django.db.backends.postgresql
DB_NAME=ngs_lims_db
DB_USER=lims_user
DB_PASSWORD=<strong password>
DB_HOST=localhost
DB_PORT=5432
SECRET_KEY=<generated key>
DEBUG=False
ALLOWED_HOSTS=yourdomain.com,<server IP>
```

Generate a secret key with:

```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

`DEBUG` must be `False`. With `DEBUG=True` Django will serve detailed tracebacks to any client and will not apply `ALLOWED_HOSTS` filtering correctly.

---

## 2. Static files

In production, Django does not serve static files. Collect them to a directory served by Nginx:

```bash
python manage.py collectstatic --noinput
```

Add `STATIC_ROOT` to `settings.py` if not already present:

```python
STATIC_ROOT = BASE_DIR / 'staticfiles'
```

Run `collectstatic` again after any code update that changes static assets.

---

## 3. Remove debug toolbar

`django-debug-toolbar` is installed and active in the current codebase. It adds overhead and should be disabled in production. In `settings.py`:

```python
INSTALLED_APPS = [
    # ... existing apps ...
    # 'debug_toolbar',   # remove or comment out in production
]

MIDDLEWARE = [
    # ... existing middleware ...
    # 'debug_toolbar.middleware.DebugToolbarMiddleware',   # remove in production
]
```

And in `ngs_lims/urls.py`, remove or guard the debug toolbar URL pattern:

```python
from django.conf import settings

if settings.DEBUG:
    import debug_toolbar
    urlpatterns += [path('__debug__/', include(debug_toolbar.urls))]
```

---

## 4. Gunicorn

Install Gunicorn into the project environment:

```bash
pip install gunicorn
```

Test that it starts correctly:

```bash
gunicorn ngs_lims.wsgi:application --bind 127.0.0.1:8000
```

Create a systemd service unit at `/etc/systemd/system/ngs-lims.service`:

```ini
[Unit]
Description=NGS-LIMS Gunicorn daemon
After=network.target postgresql.service

[Service]
User=lims
Group=lims
WorkingDirectory=/srv/ngs-lims
EnvironmentFile=/srv/ngs-lims/.env
ExecStart=/srv/ngs-lims/venv/bin/gunicorn \
    ngs_lims.wsgi:application \
    --workers 3 \
    --bind 127.0.0.1:8000 \
    --access-logfile /var/log/ngs-lims/access.log \
    --error-logfile /var/log/ngs-lims/error.log
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

Enable and start the service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable ngs-lims
sudo systemctl start ngs-lims
```

Adjust the number of `--workers` to `2 * CPU_cores + 1` as a starting point.

---

## 5. Nginx

Create a site configuration at `/etc/nginx/sites-available/ngs-lims`:

```nginx
server {
    listen 80;
    server_name yourdomain.com;

    location /static/ {
        alias /srv/ngs-lims/staticfiles/;
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Enable the site and reload Nginx:

```bash
sudo ln -s /etc/nginx/sites-available/ngs-lims /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### HTTPS

Use Certbot (Let's Encrypt) to add a TLS certificate:

```bash
sudo certbot --nginx -d yourdomain.com
```

If the server is on an internal network without public DNS, provision a certificate through your institution's CA or use a self-signed certificate and distribute it to clients.

---

## 6. Django security settings

Add the following to `settings.py` for production:

```python
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
```

These require HTTPS to be configured first. Do not enable `SECURE_SSL_REDIRECT` if the server is not yet serving HTTPS, it will lock you out of the HTTP interface.

---

## 7. Database

### Connection pooling

For a small internal lab application, the default Django database connection behaviour is usually sufficient. If load increases, consider adding PgBouncer in front of PostgreSQL.

### Backups

See `scripts/backup.sh` and the `scripts/README.md` for the built-in backup and restore tooling. Configure cron to run the backup script nightly:

```bash
0 2 * * * /srv/ngs-lims/scripts/backup.sh
```

Backups are compressed `.sql.gz` files named with the timestamp. Files older than 30 days are pruned automatically (configurable via `KEEP_DAYS` in the script).

Verify that backups are actually being written:

```bash
cat ~/ngs-lims-backups/backup.log
ls -lh ~/ngs-lims-backups/
```

---

## 8. Deploying updates

```bash
cd /srv/ngs-lims
git pull origin main

# Activate the environment
conda activate ngs-lims
# or: source venv/bin/activate

pip install -r requirements.txt
python manage.py migrate --noinput
python manage.py collectstatic --noinput

sudo systemctl restart ngs-lims
```

Always run `migrate` before restarting Gunicorn after a code change that includes model changes.

---

## 9. Logs

| Log | Location |
|---|---|
| Gunicorn access log | `/var/log/ngs-lims/access.log` |
| Gunicorn error log | `/var/log/ngs-lims/error.log` |
| Nginx access log | `/var/log/nginx/access.log` |
| Nginx error log | `/var/log/nginx/error.log` |
| Backup log | `~/ngs-lims-backups/backup.log` |
| PostgreSQL log | `/var/log/postgresql/` |

---

## 10. Health check

After deployment, verify:

1. The login page loads over HTTPS
2. Static assets (CSS, JS) load correctly for missing styles indicate `collectstatic` was not run or the Nginx alias is wrong
3. A superuser can log in and reach the admin panel at `/admin/`
4. The debug toolbar does not appear on any page
5. The backup cron job has produced at least one `.sql.gz` file