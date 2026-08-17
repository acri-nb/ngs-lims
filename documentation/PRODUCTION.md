# Production Deployment

This document covers deploying NGS-LIMS in a production environment. The development setup described in the README is not suitable for production `DEBUG=True`, the built-in development server, and an unprotected secret key must all be replaced. (Could change in the future)


## Stack

The recommended production stack is:

- **Application server**: Gunicorn (WSGI)
- **Reverse proxy**: Nginx (plain HTTP : see "Staying internal-only" below)
- **Database**: PostgreSQL 16
- **Process manager**: systemd
- **OS**: Debian/Ubuntu or Arch Linux

**This deployment stays on the company's internal network, over HTTP, reached by IP address**, no domain name, no TLS certificate, no Certbot. That's a deliberate choice for a lab-internal tool, not a shortcut: it removes an entire category of setup (DNS, cert renewal) and failure mode (expired certs locking the lab out). The tradeoff is that this server must never be reachable from outside the company network, see the note at the end of section 5.


### Simpler alternative: Whitenoise instead of Nginx

The stack above is the recommended one, but it isn't the only option. `whitenoise` is already wired into `settings.py` (`WhiteNoiseMiddleware` + `CompressedManifestStaticFilesStorage`), which means Gunicorn can serve static files itself, compressed and cache-busted, with no Nginx in front of it at all.

For a small internal lab tool, that's a reasonable tradeoff:

- **Skip Nginx entirely.** No reverse proxy, no server block, no `sites-available`/`sites-enabled` symlinks. Gunicorn binds directly to the port lab members hit (e.g. `--bind 0.0.0.0:8000`) and Whitenoise handles `/static/` under the hood.
- **Gunicorn is still worth keeping.** It's what turns "one dev server, one request at a time, restarts on every code change" into something that can actually hold up to a few people using the LIMS at once, and `systemd` (section 4) is what keeps it running after a reboot without you needing to be logged in. If you want to drop that too and just run `manage.py runserver` behind nothing, that works for a one-person smoke test, but it's not something to leave running as the deployment.
- **What you lose without Nginx:** request buffering/queuing under load, easy rate limiting, and a clean place to enforce `client_max_body_size` for large uploads (CSV/plate imports) Gunicorn's own `--limit-request-line` and worker timeouts can mostly cover this for a small internal tool, but it's less battle-tested than letting Nginx handle it.
- **Media files** (`/media/`, e.g. `WorkflowType.protocol_file` uploads) aren't covered by Whitenoise — it's static-files-only. Django's `django.views.static.serve` can handle `/media/` directly in a pinch (see Django docs), but it's not optimized for production traffic, so if media uploads become heavy this is the first place to reconsider.

If this sounds like the right fit, skip section 5 (Nginx) below and section 6 still applies as written. Section 2 has the Whitenoise-specific `collectstatic` step either way — that part doesn't change.

**Fast path:** `./scripts/setup_production.sh` automates steps 1 (checks, including `ALLOWED_HOSTS`), 2, 4 (generates the config, doesn't install it without asking), 5 (same), 7 (backup + cron), and 8 below. It won't touch `/etc` or restart system services without asking first, and it doesn't attempt the one-time OS-level setup (installing Postgres/Nginx themselves), that stays manual, described below. Everything in this document is what that script does under the hood; read on if you want the manual version or you're troubleshooting something it didn't handle for you.

---

## 1. Environment configuration

This deployment is internal-network only: plain HTTP, reached by IP address, no public domain or TLS certificate. Copy `.env.example` to `.env` and set all values:

```bash
DB_ENGINE=django.db.backends.postgresql
DB_NAME=ngs_lims_db
DB_USER=lims_user
DB_PASSWORD=<strong password>
DB_HOST=localhost
DB_PORT=5432
SECRET_KEY=<generated key>
DEBUG=False
ALLOWED_HOSTS=<server's LAN IP>,localhost,127.0.0.1
```

`ALLOWED_HOSTS` must contain exactly what lab members type into their browser, usually the server's LAN IP (e.g. `192.168.1.50`). Get this wrong and every request 400s with `DisallowedHost`; `scripts/setup_production.sh` checks this for you and offers to fix `.env` on the spot.

Generate a secret key with:

```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

`DEBUG` must be `False`. With `DEBUG=True` Django will serve detailed tracebacks to any client and will not apply `ALLOWED_HOSTS` filtering correctly.

---

## 2. Static files

In production, Django does not serve static files. `STATIC_ROOT` is already set in `settings.py` (`BASE_DIR / 'staticfiles'`), so just collect them into it:

```bash
python manage.py collectstatic --noinput
```

`staticfiles/` is gitignored, it's a generated build artifact, not source. Run `collectstatic` again after any code update that changes static assets (see step 8, Deploying updates).

This step is identical whether Nginx or Whitenoise ends up serving the files, `collectstatic` always needs to run; the only thing that changes is *who* serves `staticfiles/` afterward (see the Whitenoise callout above).


---

## 3. Debug toolbar

`django-debug-toolbar` is gated behind `DEBUG` in both `settings.py` (`INSTALLED_APPS`/`MIDDLEWARE`) and `ngs_lims/urls.py` (the `/__debug__/` route), so it's automatically excluded whenever `.env` has `DEBUG=False`, nothing to do here as long as step 1's `.env` check passes. This is intentionally automatic rather than a manual "remove before deploying" step, since that's exactly the kind of thing that's easy to forget on a routine deploy. Still worth confirming in the health check (step 10) that the toolbar doesn't render on any page.

---

## 4. Gunicorn

Gunicorn is already in `requirements.txt`. Test it starts correctly:

```bash
gunicorn ngs_lims.wsgi:application --bind 127.0.0.1:8000
```

`scripts/setup_production.sh` fills in `scripts/templates/ngs-lims.service.template` with your actual deploy path, Python interpreter, service user, and worker count, and writes it to `deploy/generated/ngs-lims.service` for you to review. To do it by hand instead, copy the template and fill in the bracketed values yourself:

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

Install and start it:

```bash
sudo cp deploy/generated/ngs-lims.service /etc/systemd/system/ngs-lims.service
sudo systemctl daemon-reload
sudo systemctl enable --now ngs-lims
```

Adjust `--workers` to `2 * CPU_cores + 1` as a starting point.

---

## 5. Nginx

`scripts/setup_production.sh` fills in `scripts/templates/nginx-ngs-lims.conf.template` with the server's LAN IP and deploy path and writes it to `deploy/generated/nginx-ngs-lims.conf`. The shape:

```nginx
server {
    listen 80;
    server_name 192.168.1.50;   # the server's LAN IP, no domain needed

    client_max_body_size 25M;   # allow CSV / plate-import uploads through

    location /static/ {
        alias /srv/ngs-lims/staticfiles/;
    }

    location /media/ {
        alias /srv/ngs-lims/media/;
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

The `/media/` block matters even though nothing in the app links to it directly during normal uses `WorkflowType.protocol_file` uploads live there, and the Django admin's file-upload widget links straight to the file's URL, so without this block that admin link 404s.

Install and reload:

```bash
sudo cp deploy/generated/nginx-ngs-lims.conf /etc/nginx/sites-available/ngs-lims
sudo ln -s /etc/nginx/sites-available/ngs-lims /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### Staying internal-only

There's no TLS/HTTPS here on purpose, plain HTTP is fine *as long as this server is genuinely unreachable from outside the company network*. That's a network-level guarantee, not something Nginx or Django can enforce on their own, so make sure of it independently:

- If the machine has only one network interface and it's on the internal LAN, you're already fine.
- If it's dual-homed (also has a public-facing interface, e.g. a shared server), either bind Nginx to the internal IP explicitly (`listen 192.168.1.50:80;` instead of `listen 80;`) or block port 80 on the public interface at the firewall (`ufw`/`firewalld`/router ACL), don't rely on just one of the two.
- Router/firewall port-forwarding rules are the other common way an "internal" server ends up reachable from the internet — worth a quick check that nothing forwards port 80 to this box.

If requirements ever change, remote access, a second site, exposure beyond the LAN — that's the point to add a domain and TLS (Certbot: `sudo certbot --nginx -d yourdomain.com`), and to revisit section 6 below, not before.

---

## 6. Django security settings

**Skip this section for this deployment.** 
`SECURE_HSTS_SECONDS`, `SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE`, and `CSRF_COOKIE_SECURE` all assume HTTPS is live. Since this server intentionally stays on plain HTTP:

- Don't add them. `SESSION_COOKIE_SECURE`/`CSRF_COOKIE_SECURE` tell the browser "only ever send this cookie over HTTPS" — set them here and login breaks immediately, since the browser will silently withhold the session cookie over HTTP. `SECURE_SSL_REDIRECT` would 301-redirect every request to `https://`, which doesn't exist on this server, so the site becomes entirely unreachable.
- Django's defaults (`SESSION_COOKIE_SECURE = False`, `CSRF_COOKIE_SECURE = False`, `SECURE_SSL_REDIRECT = False`) are already correct for this setup — there's nothing to change.
- The real security boundary here is the network, not these settings: `DEBUG=False`, `ALLOWED_HOSTS` set correctly, and the server genuinely unreachable from outside the company LAN (see "Staying internal-only" above). That combination is what actually protects the app in this deployment mode.

If this ever moves to a domain + HTTPS setup, re-add all four settings from the block above at that point — not before, and not partially (e.g. `SESSION_COOKIE_SECURE=True` without `SECURE_SSL_REDIRECT=True` produces the exact same "login silently fails" symptom).

---

## 7. Database

### Connection pooling

For a small internal lab application, the default Django database connection behaviour is usually sufficient. If load increases, consider adding PgBouncer in front of PostgreSQL.

### Backups

See `scripts/backup.sh` and `scripts/README.md` for the built-in backup and restore tooling — both scripts read DB credentials from `.env` automatically. `scripts/setup_production.sh` offers to add the nightly cron job for you; to do it manually:

```bash
0 2 * * * /srv/ngs-lims/scripts/backup.sh
```

Backups are compressed `.sql.gz` files named with the timestamp. Files older than 30 days are pruned automatically (configurable via `KEEP_DAYS` in the script).

Verify that backups are actually being written:

```bash
cat scripts/ngs-lims-backups/backup.log
ls -lh scripts/ngs-lims-backups/
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
| Backup log | `scripts/ngs-lims-backups/backup.log` |
| PostgreSQL log | `/var/log/postgresql/` |

---

## 10. Health check

After deployment, verify:

1. The login page loads at `http://<server IP>/`
2. Static assets (CSS, JS) load correctly for missing styles indicate `collectstatic` was not run or the Nginx alias is wrong
3. A superuser can log in and reach the admin panel at `/admin/`
4. The debug toolbar does not appear on any page
5. The backup cron job has produced at least one `.sql.gz` file
6. The server is confirmed unreachable from outside the company network (try it from a phone on cellular data, not company wifi)