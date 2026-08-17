#!/bin/bash
# =============================================================================
#  NGS-LIMS — Production deployment helper
#
#  Automates the parts of a deploy that are safe to run unattended
#  (dependency install, .env sanity checks, migrate, collectstatic) and
#  GENERATES the systemd + Nginx config files from templates rather than
#  writing directly into /etc — you review and install those yourself,
#  since they touch the rest of the server, not just this project.
#
#  This script is idempotent: re-running it after a `git pull` on future
#  deploys just re-checks/re-applies each step, it won't duplicate work.
#
#  See documentation/PRODUCTION.md for the full manual walkthrough this
#  script is based on, and for the one-time OS-level steps it doesn't
#  attempt the one-time OS-level setup (installing Postgres/Nginx themselves).
#
#  Usage:
#    ./scripts/setup_production.sh
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m'

step()  { echo -e "\n${CYAN}==>${NC} $1"; }
ok()    { echo -e "  ${GREEN}✓${NC} $1"; }
warn()  { echo -e "  ${YELLOW}⚠${NC}  $1"; }
fail()  { echo -e "  ${RED}✗ $1${NC}"; exit 1; }
ask_yn() {
    local prompt="$1" default="${2:-y}" reply
    if [ "$default" = "y" ]; then prompt="$prompt [Y/n] "; else prompt="$prompt [y/N] "; fi
    read -r -p "$prompt" reply
    reply="${reply:-$default}"
    [[ "$reply" =~ ^[Yy] ]]
}

echo -e "${CYAN}"
echo "  NGS-LIMS — Production Deployment Helper"
echo -e "${NC}============================================"
echo "  Working directory: $PROJECT_ROOT"

# This script calls `sudo` itself, internally, only for the specific steps
# that need root (creating the service user, installing systemd/nginx
# configs, restarting services). Running the WHOLE script under sudo makes
# venv/pip installs, generated files, and the systemd service itself all
# end up owned by / running as root — including defaulting the "service
# user" prompt to root, since $(whoami) would return root too.
if [ "$EUID" -eq 0 ]; then
    fail "Don't run this with sudo — run it as your normal user:
    ./scripts/setup_production.sh
  It will prompt for your password itself, only for the commands that
  actually need root. If you already ran it with sudo once, fix ownership
  of anything it touched before re-running:
    sudo chown -R \$USER:\$USER $PROJECT_ROOT"
fi

# ── 1. .env sanity checks ────────────────────────────────────────────────────
step ".env checks"

if [ ! -f .env ]; then
    fail ".env not found. Copy .env.example to .env, fill in real production values, then re-run this script."
fi

# shellcheck disable=SC1091
set -a; source .env; set +a

: "${SECRET_KEY:?SECRET_KEY missing from .env}"
: "${ALLOWED_HOSTS:?ALLOWED_HOSTS missing from .env}"

if [ "${DEBUG:-False}" = "True" ]; then
    warn "DEBUG=True in .env — this MUST be False in production."
    ask_yn "Continue anyway?" n || exit 1
else
    ok "DEBUG=False"
fi

if [[ "$SECRET_KEY" == *"django-insecure"* ]] || [ -z "$SECRET_KEY" ]; then
    fail "SECRET_KEY looks like a placeholder/insecure value. Generate a real one:
    python -c \"from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())\""
else
    ok "SECRET_KEY is set"
fi

if [[ "$ALLOWED_HOSTS" == *"localhost"* ]] && ! ask_yn "ALLOWED_HOSTS still includes 'localhost' — is that intentional for this deploy?" n; then
    warn "update ALLOWED_HOSTS in .env to the server's LAN IP before going further"
fi
ok "ALLOWED_HOSTS = ${ALLOWED_HOSTS}"

# ── 2. Python environment + dependencies ─────────────────────────────────────
step "Python environment"

PYTHON_BIN=""
if command -v conda >/dev/null 2>&1 && conda env list | grep -qE '^\s*ngs-lims\s'; then
    # shellcheck disable=SC1091
    source "$(conda info --base)/etc/profile.d/conda.sh"
    conda activate ngs-lims
    PYTHON_BIN="$(command -v python)"
    ok "using conda env 'ngs-lims'"
else
    if [ ! -d venv ]; then
        python3 -m venv venv
        ok "created venv"
    fi
    # shellcheck disable=SC1091
    source venv/bin/activate
    PYTHON_BIN="$(command -v python)"
    ok "using venv at $PROJECT_ROOT/venv"
fi

pip install -q --upgrade pip
pip install -q -r requirements.txt
ok "requirements.txt installed (includes gunicorn, psycopg2)"

# ── 3. Database ───────────────────────────────────────────────────────────────
step "Database migrations"
python manage.py migrate --noinput
ok "migrations applied"

if [ -f scripts/backup.sh ]; then
    if ask_yn "Take a backup before continuing?"; then
        chmod +x scripts/backup.sh
        ./scripts/backup.sh
    fi
fi

# ── 4. Static files ───────────────────────────────────────────────────────────
step "Static files"
python manage.py collectstatic --noinput
ok "collected into $(python -c "from django.conf import settings; print(settings.STATIC_ROOT)" 2>/dev/null || echo staticfiles/)"

# ── 5. Config file generation (systemd + Nginx) ──────────────────────────────
step "Generating systemd + Nginx config"

OUT_DIR="$PROJECT_ROOT/deploy/generated"
mkdir -p "$OUT_DIR"

echo "  This deploy stays on the internal network over plain HTTP — no domain"
echo "  or TLS certificate needed, just the server's LAN IP (or internal hostname"
echo "  if you have local DNS)."
read -r -p "  Server address (e.g. 192.168.1.50): " SERVER_ADDR
if [ -z "$SERVER_ADDR" ]; then
    fail "A server address is required — it's what lab members will type in their browser, and what Nginx and ALLOWED_HOSTS need to match."
fi

# Django rejects requests whose Host header isn't in ALLOWED_HOSTS with a
# 400 Bad Request — the single most common first-run surprise when moving
# from a domain to a bare IP. Check now and offer to fix .env directly.
if [[ ",${ALLOWED_HOSTS}," != *",${SERVER_ADDR},"* ]]; then
    warn "'${SERVER_ADDR}' is not in ALLOWED_HOSTS in .env (currently: ${ALLOWED_HOSTS})"
    if ask_yn "Add it to .env now?"; then
        NEW_ALLOWED_HOSTS="${ALLOWED_HOSTS},${SERVER_ADDR}"
        sed -i.bak "s#^ALLOWED_HOSTS=.*#ALLOWED_HOSTS=${NEW_ALLOWED_HOSTS}#" .env && rm -f .env.bak
        ALLOWED_HOSTS="$NEW_ALLOWED_HOSTS"
        ok "ALLOWED_HOSTS is now: ${ALLOWED_HOSTS}"
    else
        warn "http://${SERVER_ADDR}/ will 400 until ALLOWED_HOSTS in .env includes it"
    fi
else
    ok "'${SERVER_ADDR}' already in ALLOWED_HOSTS"
fi

read -r -p "  System user to run the app as [$(whoami)]: " SERVICE_USER
SERVICE_USER="${SERVICE_USER:-$(whoami)}"

if [ "$SERVICE_USER" = "root" ]; then
    fail "Running Gunicorn as root is not something this script will set up.
  Pick a real non-root account — your own login user is fine for a small
  internal deploy, or a dedicated system account (this script can create
  one for you)."
fi

# Catch a bad/typo'd username now, before configs are generated and sudo is
# invoked for install — not deep in the middle of the install where a
# non-existent user shows up as a cryptic `chown: invalid user` failure.
if ! id "$SERVICE_USER" >/dev/null 2>&1; then
    warn "no system user named '${SERVICE_USER}' exists yet."
    if ask_yn "Create it now as a system account (no login, no home dir)?"; then
        sudo useradd --system --no-create-home --shell /usr/sbin/nologin "$SERVICE_USER" \
            || fail "Could not create user '${SERVICE_USER}'. Create it manually, e.g.:
    sudo useradd --system --no-create-home --shell /usr/sbin/nologin ${SERVICE_USER}
  then re-run this script."
        ok "created system user '${SERVICE_USER}'"
    else
        fail "Pick an existing user, or create one first:
    sudo useradd --system --no-create-home --shell /usr/sbin/nologin ${SERVICE_USER}"
    fi
else
    ok "system user '${SERVICE_USER}' exists"
fi

read -r -p "  Gunicorn worker count [3]: " WORKERS
WORKERS="${WORKERS:-3}"
read -r -p "  Log directory [/var/log/ngs-lims]: " LOG_DIR
LOG_DIR="${LOG_DIR:-/var/log/ngs-lims}"

GUNICORN_BIN="$(dirname "$PYTHON_BIN")/gunicorn"

sed \
    -e "s#__DEPLOY_PATH__#${PROJECT_ROOT}#g" \
    -e "s#__SERVICE_USER__#${SERVICE_USER}#g" \
    -e "s#__SERVICE_GROUP__#${SERVICE_USER}#g" \
    -e "s#__PYTHON_BIN__#${PYTHON_BIN}#g" \
    -e "s#__GUNICORN_WORKERS__#${WORKERS}#g" \
    -e "s#__LOG_DIR__#${LOG_DIR}#g" \
    scripts/templates/ngs-lims.service.template > "$OUT_DIR/ngs-lims.service"
ok "wrote $OUT_DIR/ngs-lims.service"

sed \
    -e "s#__SERVER_ADDR__#${SERVER_ADDR}#g" \
    -e "s#__DEPLOY_PATH__#${PROJECT_ROOT}#g" \
    scripts/templates/nginx-ngs-lims.conf.template > "$OUT_DIR/nginx-ngs-lims.conf"
ok "wrote $OUT_DIR/nginx-ngs-lims.conf"

echo ""
echo "  Review both files in deploy/generated/ before installing them."
echo "  (gunicorn resolved to: $GUNICORN_BIN — sanity-check it exists)"

if ask_yn "Install and enable them now? (requires sudo, will reload nginx + restart the service)" n; then
    sudo mkdir -p "$LOG_DIR"
    sudo chown "$SERVICE_USER":"$SERVICE_USER" "$LOG_DIR"

    sudo cp "$OUT_DIR/ngs-lims.service" /etc/systemd/system/ngs-lims.service
    sudo systemctl daemon-reload
    sudo systemctl enable ngs-lims
    sudo systemctl restart ngs-lims
    ok "ngs-lims.service installed and (re)started"

    # /etc/nginx/conf.d/ is included by default on both Arch and Debian/
    # Ubuntu nginx packages — unlike sites-available/sites-enabled, which is
    # a Debian-only convention Arch's nginx package doesn't create.
    sudo mkdir -p /etc/nginx/conf.d
    sudo cp "$OUT_DIR/nginx-ngs-lims.conf" /etc/nginx/conf.d/ngs-lims.conf
    if ! grep -q "conf\.d/\*\.conf" /etc/nginx/nginx.conf 2>/dev/null; then
        warn "/etc/nginx/nginx.conf doesn't seem to include conf.d/*.conf — add this line inside the http {} block, then re-run:"
        warn "    include /etc/nginx/conf.d/*.conf;"
    fi
    if sudo nginx -t; then
        sudo systemctl reload nginx
        ok "nginx config installed and reloaded"
    else
        fail "nginx config test failed — check /etc/nginx/conf.d/ngs-lims.conf and re-run 'sudo nginx -t'"
    fi

    echo ""
    ok "No TLS/certbot step needed — this deploy is internal-network HTTP only."
    warn "Make sure this server isn't reachable from outside your company network"
    warn "(firewall rule or the box simply has no public interface) — see"
    warn "documentation/PRODUCTION.md for details."
    echo ""
    echo "  Lab members can now reach it at: http://${SERVER_ADDR}/"
else
    echo ""
    echo "  Not installed. To do it manually:"
    echo "    sudo cp $OUT_DIR/ngs-lims.service /etc/systemd/system/ngs-lims.service"
    echo "    sudo systemctl daemon-reload && sudo systemctl enable --now ngs-lims"
    echo "    sudo mkdir -p /etc/nginx/conf.d"
    echo "    sudo cp $OUT_DIR/nginx-ngs-lims.conf /etc/nginx/conf.d/ngs-lims.conf"
    echo "    sudo nginx -t && sudo systemctl reload nginx"
fi

# ── 6. Superuser ──────────────────────────────────────────────────────────────
step "Superuser account"
if ask_yn "Create a superuser now?" n; then
    python manage.py createsuperuser
fi

# ── 7. Cron backup ────────────────────────────────────────────────────────────
step "Scheduled backups"
CRON_LINE="0 2 * * * $PROJECT_ROOT/scripts/backup.sh"

if ! command -v crontab >/dev/null 2>&1; then
    warn "'crontab' isn't installed on this system (common on a fresh Arch install — cron isn't included by default)."
    if command -v pacman >/dev/null 2>&1; then
        if ask_yn "Install cronie (cron for Arch) now?"; then
            if sudo pacman -S --noconfirm cronie && sudo systemctl enable --now cronie; then
                ok "cronie installed and running"
            else
                warn "install failed — do it manually: sudo pacman -S cronie && sudo systemctl enable --now cronie"
            fi
        fi
    elif command -v apt-get >/dev/null 2>&1; then
        if ask_yn "Install cron now?"; then
            if sudo apt-get install -y cron && sudo systemctl enable --now cron; then
                ok "cron installed and running"
            else
                warn "install failed — do it manually: sudo apt-get install -y cron"
            fi
        fi
    else
        warn "couldn't detect pacman or apt — install a cron daemon manually for your distro."
    fi
fi

if ! command -v crontab >/dev/null 2>&1; then
    warn "cron still not available — skipping automatic scheduling."
    echo "  Run backups manually, or set up a systemd timer instead:"
    echo "    ./scripts/backup.sh                       ← manual, any time"
    echo "    crontab -e   → add: $CRON_LINE            ← once cron is installed"
elif crontab -l 2>/dev/null | grep -qF "$PROJECT_ROOT/scripts/backup.sh"; then
    ok "nightly backup already scheduled in crontab"
elif ask_yn "Add nightly backup to crontab (2 AM daily)?"; then
    { crontab -l 2>/dev/null; echo "$CRON_LINE"; } | crontab -
    ok "added to crontab: $CRON_LINE"
else
    warn "not scheduled — add manually later: $CRON_LINE"
fi

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN} Deployment steps complete.${NC}"
echo "============================================"
echo ""
echo "  Before calling this done, walk through the health check in"
echo "  documentation/PRODUCTION.md section 10:"
echo "    1. Login page loads at http://${SERVER_ADDR}/"
echo "    2. Static assets (CSS/JS) load correctly"
echo "    3. A superuser can log in and reach /admin/"
echo "    4. The debug toolbar does NOT appear on any page"
echo "    5. scripts/backup.sh has produced at least one .sql.gz file"
echo "    6. The server is unreachable from outside the company network"
echo ""
