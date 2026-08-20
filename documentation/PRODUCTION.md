# Production Deployment


## 1. Install PostgreSQL (Ubuntu)

```bash
sudo apt update
sudo apt install postgresql postgresql-contrib
```

**If this fails** (restricted network access on the lab machine, no reachable apt mirror, permissions, etc.) that's expected on some of the lab's machines. Install Postgres through conda instead:

```bash
conda install postgresql=15 -c conda-forge
```

Once installed via conda, it still needs a data directory initialized and the server started before anything can connect to it, conda doesn't set this up as a system service the way apt's package does:

```bash
initdb -D ~/pgdata
pg_ctl -D ~/pgdata -l ~/pgdata/logfile start
```

Then create the database and user:

```bash
psql -U postgres
```
```sql
CREATE DATABASE ngs_lims_db;
CREATE USER lims_user WITH PASSWORD 'yourpassword';
GRANT ALL PRIVILEGES ON DATABASE ngs_lims_db TO lims_user;
ALTER DATABASE ngs_lims_db OWNER TO lims_user;
\q
```
```bash
psql -U postgres -d ngs_lims_db
```
```sql
GRANT ALL ON SCHEMA public TO lims_user;
ALTER SCHEMA public OWNER TO lims_user;
\q
```

---

## 2. Configure `.env`

```bash
nano .env
```

Set every value, especially the host-specific ones:

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

`ALLOWED_HOSTS` must contain exactly what lab members type into their browser. the server's LAN IP (e.g. `10.1.1.7`). Get this wrong and every request 400s with `DisallowedHost`.

Generate a secret key with:
```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

`DEBUG` must be `False`. With `DEBUG=True`, Django serves detailed tracebacks to anyone and doesn't apply `ALLOWED_HOSTS` filtering correctly.

---

## 3. Collect static files

```bash
python manage.py collectstatic --noinput
```

There's no Nginx in this setup, so static files are served by **Whitenoise** instead, it's already wired into `settings.py` (`WhiteNoiseMiddleware` + `CompressedManifestStaticFilesStorage`), so this is the only step needed for CSS/JS to load correctly. Re-run this after any code update that changes static assets (see step 10, Deploying updates).

---

## 4. Set up the nightly backup cron job

```bash
crontab -e
```

Add:
```
0 2 * * * /path/to/ngs-lims/scripts/backup.sh
```

`scripts/backup.sh` reads DB credentials straight from `.env`, so nothing else to configure. It writes compressed `.sql.gz` files to `scripts/ngs-lims-backups/` and prunes anything older than 30 days automatically. See `scripts/README.md` for `restore.sh` and troubleshooting.

Worth testing it manually once before trusting the cron job with it:
```bash
./scripts/backup.sh
cat scripts/ngs-lims-backups/backup.log
```

---

## 5. Run migrations

```bash
python manage.py makemigrations
python manage.py migrate
```

---

## 6. Seed reference data

```bash
python manage.py seed_db
python manage.py seed_qc_presets
```

---

## 7. Create a superuser

```bash
python manage.py createsuperuser
```

---

## 8. Start the server

```bash
python manage.py runserver
```

**This will fail or be unreachable from other lab machines**: by default `runserver` binds to `127.0.0.1`, which only accepts connections from the server itself, not from anyone else on the network. Bind it to the server's actual LAN IP instead, and background it with `nohup` so it keeps running after you log out:

```bash
nohup python manage.py runserver 10.111.243.103:8000 &
```

Replace `10.111.243.103` with your server's actual LAN IP (the same one you put in `ALLOWED_HOSTS`). Lab members then reach the LIMS at `http://10.111.243.103:8000/`.

Output goes to `nohup.out` in the directory you ran it from unless redirected elsewhere, worth pointing that redirect somewhere predictable:
```bash
nohup python manage.py runserver 10.111.243.103:8000 > /var/log/ngs-lims/server.log 2>&1 &
```

### Stopping / restarting it

Find and stop the running process:
```bash
ps aux | grep runserver
kill <PID>
```
Then start it again with the same `nohup` command from above.

**This won't survive a reboot on its own**: if the machine restarts, someone needs to log back in and re-run the `nohup` command. If that's a real risk for this machine, either add an `@reboot` cron entry (`crontab -e`) with the same command, or move to the systemd + Gunicorn setup in the appendix below, which handles this automatically.

---

## 9. Known gap: media files aren't served

There's no Nginx `/media/` alias and no Gunicorn/Whitenoise handling for it either, `manage.py runserver` in this configuration doesn't serve `MEDIA_ROOT` uploads (e.g. `WorkflowType.protocol_file`). Links to those files from the Django admin will 404 for now. This is a known gap to revisit, not something silently working, worth flagging to whoever picks up hardening this deployment next.

---

>Extra Info, now you can add things that need to be manually added with admin for the ACRI lab (adding Racks, adding the pdf for the workflows, and accounts for the lab ) 

## 10. Deploying updates

```bash
cd /path/to/ngs-lims
git pull origin main

conda activate ngs-lims
pip install -r requirements.txt

python manage.py migrate --noinput
python manage.py collectstatic --noinput

# then stop and restart the server (step 8)
```

Always run `migrate` before restarting the server after a code change that includes model changes.

---

## 11. Logs

| Log | Location |
|---|---|
| Server output | wherever `nohup` redirected it (`nohup.out` by default, or your own path) |
| Backup log | `scripts/ngs-lims-backups/backup.log` |
| PostgreSQL log | `~/pgdata/logfile` (conda install) or `/var/log/postgresql/` (apt install) |

---

## 12. Health check

After deployment, verify:

1. The login page loads at `http://<server LAN IP>:8000/`
2. Static assets (CSS, JS) load correctly, missing styles mean `collectstatic` wasn't run
3. A superuser can log in and reach the admin panel at `/admin/`
4. The debug toolbar does not appear on any page (it's gated behind `DEBUG`, which should be `False`)
5. The backup cron job has produced at least one `.sql.gz` file
6. The server is confirmed unreachable from outside the company network (try it from a phone on cellular data, not company wifi)

---

## Staying internal-only

There's no TLS/HTTPS here on purpose, plain HTTP is fine *as long as this server is genuinely unreachable from outside the company network*. That's a network-level guarantee, not something Django can enforce on its own:

- If the machine has only one network interface and it's on the internal LAN, you're already fine.
- If it's dual-homed (also has a public-facing interface), block the port on the public interface at the firewall (`ufw`/`firewalld`/router ACL).
- Router/firewall port-forwarding rules are the other common way an "internal" server ends up reachable from the internet, worth a quick check that nothing forwards this port to this box.

If requirements ever change, remote access, a second site, exposure beyond the LAN, that's the point to add a domain, TLS, and the Django security settings in the appendix below, not before.

---

# Appendix: Optional upgrade path (Gunicorn + Nginx + systemd)

Everything above is what's actually running. The stack below is a more resilient alternative for later, Gunicorn instead of `runserver`, Nginx in front of it, and systemd to keep it running through crashes and reboots without anyone needing to `nohup` it by hand. Worth doing eventually; not required to have a working deployment today.

### Why upgrade later
- `runserver` is single-threaded and not built to hold up under real concurrent load, fine for a handful of lab members, a ceiling if usage grows.
- `nohup` doesn't restart the process if it crashes or the machine reboots, systemd does.
- Nginx adds request buffering, rate limiting, and a clean place to enforce `client_max_body_size` for large CSV/plate-import uploads.
- Nginx can also serve `/media/` properly, closing the gap noted in step 9 above.

### Gunicorn

Already in `requirements.txt`. Test it starts correctly:
```bash
gunicorn ngs_lims.wsgi:application --bind 127.0.0.1:8000
```

Example systemd unit (`deploy/generated/ngs-lims.service` if generated by `scripts/setup_production.sh`, or fill in a copy of `scripts/templates/ngs-lims.service.template` by hand):

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

```bash
sudo cp deploy/generated/ngs-lims.service /etc/systemd/system/ngs-lims.service
sudo systemctl daemon-reload
sudo systemctl enable --now ngs-lims
```

Adjust `--workers` to `2 * CPU_cores + 1` as a starting point.

### Nginx

Example config (LAN IP, no domain needed):

```nginx
server {
    listen 80;
    server_name 10.111.243.103;   # the server's LAN IP

    client_max_body_size 25M;     # allow CSV / plate-import uploads through

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

The `/media/` block matters even though nothing in the app links to it directly in normal use, `WorkflowType.protocol_file` uploads live there, and the Django admin's file-upload widget links straight to the file's URL, so without this block that admin link 404s (this is exactly the gap noted in step 9).

```bash
sudo cp deploy/generated/nginx-ngs-lims.conf /etc/nginx/sites-available/ngs-lims
sudo ln -s /etc/nginx/sites-available/ngs-lims /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### Django security settings (skip unless HTTPS is live)

`SECURE_HSTS_SECONDS`, `SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE`, and `CSRF_COOKIE_SECURE` all assume HTTPS. On plain HTTP:

- Don't add them. `SESSION_COOKIE_SECURE`/`CSRF_COOKIE_SECURE` tell the browser to only send the cookie over HTTPS, set them here and login breaks immediately. `SECURE_SSL_REDIRECT` would redirect every request to `https://`, which doesn't exist on this server.
- Django's defaults (all `False`) are already correct for this setup.
- The real security boundary is the network, `DEBUG=False`, `ALLOWED_HOSTS` set correctly, and genuine LAN-only reachability (see "Staying internal-only" above).

If this ever moves to a domain + HTTPS setup, add all four settings together, not partially, e.g. `SESSION_COOKIE_SECURE=True` without `SECURE_SSL_REDIRECT=True` produces the same "login silently fails" symptom. Certbot: `sudo certbot --nginx -d yourdomain.com`.