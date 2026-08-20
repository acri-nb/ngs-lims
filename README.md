# NGS LIMS

A Laboratory Information Management System (LIMS) built for Next Generation Sequencing (NGS) workflows. Built with Django and PostgreSQL.

Built for the [Atlantic Cancer Research Institute (IARC)](https://canceratlantique.ca/en/).


## Development Status
> This project was built and deployed for real lab use; active feature development has wrapped up and it's now in upkeep-only mode (bug fixes, dependency updates). See [`documentation/`](documentation/) for anyone picking this project back up.

---


## Tech stack

- **Backend:** Django 4.2, Django REST Framework
- **Database:** PostgreSQL
- **Deployment:** Gunicorn behind a reverse proxy
- **Frontend:** Django templates, crispy-forms, per-view CSS/JS (no SPA framework)

## Project layout

```
ngs-lims/
  ngs_lims/          # Django project package, settings, root URLs
  samples/           # Client, Case, Specimen, Sample, Project
  qc/                # SampleQCBatch, BatchSample, SampleQC, BatchAuditLog
  library/            # LibraryPrepBatch, WorkflowType, IndexKit, master mix/prep sheet, Library QC
  inventory/          # Supplier, Product, ProductSupplier, Inventory, InventoryReceipt
  locations/          # Location, TempLog, Plate, Rack, PlateWell
  documentation/       # Developer guide, production deploy guide, maintenance guide
  scripts/             # Backup / restore / dev-setup shell scripts
  mock_data/           # CSV fixtures for seeding a dev database
```
A typical project follows this path:
```
Create Project → Import Samples → QC Batch → Record QC Results
   → Library Prep Batch → Master Mix / Prep Sheet → Record Library QC
```

---

## System Design / Conception
The application architecture and workflow conception diagrams are available in the `ngs_lims.drawio` file.

You can open and edit the diagram using [draw.io](https://app.diagrams.net/) (also known as diagrams.net).

### To open it:
1. Go to [https://app.diagrams.net/](https://app.diagrams.net/)
2. Click **File > Open from Device**
3. Select `ngs_lims.drawio`


## Documentation

Anyone continuing work on this project should start here:

- [`documentation/WORKFLOW.md`](documentation/WORKFLOW.md): how the LIMS is used, module by module
- [`documentation/DEVELOPMENT.md`](documentation/DEVELOPMENT.md): local setup, project structure, conventions
- [`documentation/PRODUCTION.md`](documentation/PRODUCTION.md): deployment
- [`documentation/MAINTENANCE.md`](documentation/MAINTENANCE.md): backups, routine upkeep
- [`documentation/DRAW_IO.md`](documentation/DRAW_IO.md): how to read/update the schema diagram
- [`documentation/TODO.md`](documentation/TODO.md): known issues and ideas that were never picked up

## Quick start (development)

```bash
git clone <repo-url>
cd ngs-lims
./scripts/setup_dev.sh   # creates venv, installs deps, sets up a dev DB
python manage.py runserver
```

Full setup details, including seeding sample data, are in `documentation/DEVELOPMENT.md`.

## Project history

Built incrementally to replace spreadsheet-based tracking in the lab, starting with sample/client intake and QC, then extending into library prep (plate boards, master mix PDFs, prep sheets) and inventory/location tracking. The system has been running in production for lab use; development is now paused with the app considered feature-complete for its original scope.


## License
MIT.
