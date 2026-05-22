# NGS-LIMS

A Laboratory Information Management System (LIMS) built for Next Generation Sequencing (NGS) workflows. Built with Django and PostgreSQL.

Built for the [Atlantic Cancer Research Institute (IARC)](https://canceratlantique.ca/en/).

---


## Development Status


> This LIMS is currently under active development. Features, database models, and workflows may change frequently and are not yet considered production-ready.




## Prerequisites

- Python 3.9
- Django 4.2
- PostgreSQL 16
- Conda (environment: `ngs-lims`)

---

## System Design / Conception

The application architecture and workflow conception diagrams are available in the `ngs-lims.drawio` file.

You can open and edit the diagram using [draw.io](https://app.diagrams.net/) (also known as diagrams.net).


### To open it:

1. Go to [https://app.diagrams.net/](https://app.diagrams.net/)
2. Click **File > Open from Device**
3. Select `ngs-lims.drawio`




## Project structure

```
ngs-lims/
  samples/       # Client, Case, Specimen, Sample, Project 
  qc/            # SampleQCBatch, BatchSample, SampleQC 
  inventory/     # Supplier, Product, Inventory, InventoryReceipt 
  locations/     # Location, TempLog 
  ngs_lims/      # Django settings and URLs
```

## Setup

### 1. Clone the repo

```bash
git clone https://github.com/your-org/ngs-lims.git
cd ngs-lims
```

### 2. Create the conda environment

```bash
conda create -n ngs-lims python=3.9
conda activate ngs-lims
pip install -r requirements.txt
```

### 3. Create the `.env` file

Copy the example and fill in your values:

```bash
cp .env.example .env
```

```bash
# .env
DB_ENGINE=django.db.backends.postgresql
DB_NAME=ngs_lims_db
DB_USER=lims_user
DB_PASSWORD=yourpassword
DB_HOST=localhost
DB_PORT=5432
SECRET_KEY=your-secret-key
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
```

### 4. Set up PostgreSQL (Arch)

```bash
sudo pacman -S postgresql
sudo -u postgres initdb -D /var/lib/postgres/data
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

```bash
sudo -u postgres psql
```

```sql
CREATE DATABASE ngs_lims_db;
CREATE USER lims_user WITH PASSWORD 'yourpassword';
GRANT ALL PRIVILEGES ON DATABASE ngs_lims_db TO lims_user;
ALTER DATABASE ngs_lims_db OWNER TO lims_user;
\q
```

```bash
sudo -u postgres psql -d ngs_lims_db
```

```sql
GRANT ALL ON SCHEMA public TO lims_user;
ALTER SCHEMA public OWNER TO lims_user;
\q
```

### 5. Run migrations

```bash
python manage.py makemigrations
python manage.py migrate
```

### 6. Create a superuser

```bash
python manage.py createsuperuser
```

### 7. Start the server

```bash
python manage.py runserver
```

Admin panel available at `http://127.0.0.1:8000/admin`

--- 

## License

MIT.