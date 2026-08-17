#!/bin/bash
# =============================================================================
#  NGS-LIMS — Development environment setup
#  (Recommended to do it by hand with PRODUCTION.md)
#  Takes a fresh clone from zero to a running dev server:
#    - creates a Python environment (conda if available, venv otherwise)
#    - installs dependencies
#    - creates .env from .env.example (prompts for DB values, generates a
#      real SECRET_KEY — never leaves the insecure example value in place)
#    - creates the PostgreSQL database + user (optional, asks first)
#    - runs migrations
#    - seeds reference data (workflows, index kits, locations, specimen
#      types) via the existing seed_db / seed_qc_presets management commands
#    - offers to create a superuser
#
#  Safe to re-run: every step checks whether it's already done before
#  acting, so running this again after a `git pull` just fills in gaps.
#
#  Usage:
#    ./scripts/setup_dev.sh
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
    # ask_yn "question" default(y/n)  → returns 0 for yes
    local prompt="$1" default="${2:-y}" reply
    if [ "$default" = "y" ]; then prompt="$prompt [Y/n] "; else prompt="$prompt [y/N] "; fi
    read -r -p "$prompt" reply
    reply="${reply:-$default}"
    [[ "$reply" =~ ^[Yy] ]]
}

echo -e "${CYAN}"
echo "  NGS-LIMS — Development Setup"
echo -e "${NC}============================================"

# ── 1. Python environment ────────────────────────────────────────────────────
step "Python environment"

PYTHON_BIN=""
if command -v conda >/dev/null 2>&1; then
    if conda env list | grep -qE '^\s*ngs-lims\s'; then
        ok "conda env 'ngs-lims' already exists"
    else
        echo "  Creating conda env 'ngs-lims' (python 3.9)..."
        conda create -y -n ngs-lims python=3.9
        ok "conda env created"
    fi
    echo "  Activating..."
    # shellcheck disable=SC1091
    source "$(conda info --base)/etc/profile.d/conda.sh"
    conda activate ngs-lims
    PYTHON_BIN="$(command -v python)"
else
    warn "conda not found, falling back to a plain venv at ./venv"
    if [ ! -d venv ]; then
        python3 -m venv venv
        ok "venv created"
    else
        ok "venv already exists"
    fi
    # shellcheck disable=SC1091
    source venv/bin/activate
    PYTHON_BIN="$(command -v python)"
fi
ok "using $PYTHON_BIN"

step "Installing dependencies"
pip install -q --upgrade pip
pip install -q -r requirements.txt
ok "requirements.txt installed"

# ── 2. .env file ──────────────────────────────────────────────────────────────
step ".env configuration"

if [ -f .env ]; then
    ok ".env already exists, leaving it as-is"
else
    cp .env.example .env
    ok "created .env from .env.example"

    echo ""
    echo "  A few values are worth setting now (press Enter to keep the default):"
    read -r -p "  Postgres database name [ngs_lims_db]: " DB_NAME_IN
    read -r -p "  Postgres user [lims_user]: " DB_USER_IN
    read -r -s -p "  Postgres password: " DB_PASS_IN; echo ""
    DB_NAME_IN="${DB_NAME_IN:-ngs_lims_db}"
    DB_USER_IN="${DB_USER_IN:-lims_user}"

    SECRET_KEY_GEN="$($PYTHON_BIN -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())" 2>/dev/null || true)"
    if [ -z "$SECRET_KEY_GEN" ]; then
        # django isn't importable yet on first-ever run before requirements
        # finish; fall back to /dev/urandom, still perfectly usable.
        SECRET_KEY_GEN="$(python3 -c "import secrets; print(secrets.token_urlsafe(50))")"
    fi

    # Portable in-place sed for both GNU and BSD/macOS sed
    sedi() { sed -i.bak "$1" .env && rm -f .env.bak; }
    sedi "s/^DB_NAME=.*/DB_NAME=${DB_NAME_IN}/"
    sedi "s/^DB_USER=.*/DB_USER=${DB_USER_IN}/"
    sedi "s/^DB_PASSWORD=.*/DB_PASSWORD=${DB_PASS_IN}/"
    sedi "s#^SECRET_KEY=.*#SECRET_KEY=${SECRET_KEY_GEN}#"

    ok ".env filled in with a freshly generated SECRET_KEY"
    warn "review .env and adjust DB_HOST / DB_PORT / ALLOWED_HOSTS if needed"
fi

# shellcheck disable=SC1091
set -a; source .env; set +a

# ── 3. PostgreSQL database ───────────────────────────────────────────────────
step "PostgreSQL database"

if ! command -v psql >/dev/null 2>&1; then
    warn "psql not found on PATH — skipping DB creation, set it up manually (see documentation/DEVELOPMENT.md)"
else
    DB_EXISTS=$(sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='${DB_NAME}'" 2>/dev/null || echo "")
    if [ "$DB_EXISTS" = "1" ]; then
        ok "database '${DB_NAME}' already exists"
    else
        if ask_yn "Create PostgreSQL database '${DB_NAME}' and user '${DB_USER}' now?"; then
            sudo -u postgres psql -v ON_ERROR_STOP=1 <<SQL
CREATE DATABASE ${DB_NAME};
DO \$\$
BEGIN
   IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = '${DB_USER}') THEN
      CREATE USER ${DB_USER} WITH PASSWORD '${DB_PASSWORD}';
   END IF;
END
\$\$;
GRANT ALL PRIVILEGES ON DATABASE ${DB_NAME} TO ${DB_USER};
ALTER DATABASE ${DB_NAME} OWNER TO ${DB_USER};
SQL
            sudo -u postgres psql -v ON_ERROR_STOP=1 -d "${DB_NAME}" <<SQL
GRANT ALL ON SCHEMA public TO ${DB_USER};
ALTER SCHEMA public OWNER TO ${DB_USER};
SQL
            ok "database and user created"
        else
            warn "skipped — create the database manually before continuing (see documentation/DEVELOPMENT.md)"
        fi
    fi
fi

# ── 4. Migrations ─────────────────────────────────────────────────────────────
step "Running migrations"
python manage.py migrate --noinput
ok "migrations applied"

# ── 5. Seed reference data ───────────────────────────────────────────────────
step "Seed data"
if ask_yn "Seed reference data (workflows, index kits, locations, specimen types)?"; then
    python manage.py seed_db
    python manage.py seed_qc_presets
    ok "seed data loaded"
else
    warn "skipped — run 'python manage.py seed_db' and 'seed_qc_presets' later if needed"
fi

# ── 6. Superuser ──────────────────────────────────────────────────────────────
step "Superuser account"
if ask_yn "Create a superuser now?"; then
    python manage.py createsuperuser
else
    warn "skipped — run 'python manage.py createsuperuser' later"
fi

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN} Setup complete.${NC}"
echo "============================================"
echo ""
echo "  Start the dev server with:"
if command -v conda >/dev/null 2>&1; then
    echo "    conda activate ngs-lims"
else
    echo "    source venv/bin/activate"
fi
echo "    python manage.py runserver"
echo ""
echo "  Then open http://127.0.0.1:8000/admin"
echo ""
