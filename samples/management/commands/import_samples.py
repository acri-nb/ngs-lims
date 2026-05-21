"""
Management command: import_samples

Imports samples from a CSV file into the LIMS.

Expected CSV format:
    CaseID, SpecimenType, NucleidType, Concentration(ng), Volume(uL)
    Y1V9RH, smallEVs, RNA, 250.7564, 788

Usage:
    python manage.py import_samples --project 1 --file path/to/samples.csv
    python manage.py import_samples --project 1 --file path/to/samples.csv --dry-run
"""

import csv
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from samples.models import Project, Case, Specimen, SpecimenType, Sample
from qc.models import SampleQCBatch, BatchSample, SampleQC


# CSV column names
COL_CASE_ID       = 'CaseID'
COL_SPECIMEN_TYPE = 'SpecimenType'
COL_NUCLEID_TYPE  = 'NucleidType'
COL_CONCENTRATION = 'Concentration(ng)'
COL_VOLUME        = 'Volume(uL)'


def parse_float(value: str, field_name: str, row_num: int):
    """Safely parse a float, returning None for empty/missing values."""
    value = value.strip()
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        raise ValueError(f"Row {row_num}: '{field_name}' value '{value}' is not a valid number.")


class Command(BaseCommand):
    help = 'Import samples from a client CSV file into the LIMS'

    def add_arguments(self, parser):
        parser.add_argument(
            '--project',
            type=int,
            required=True,
            help='ID of the project to import samples into'
        )
        parser.add_argument(
            '--file',
            type=str,
            required=True,
            help='Path to the CSV file'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            default=False,
            help='Validate and preview without saving anything to the database'
        )
        parser.add_argument(
            '--batch-name',
            type=str,
            default=None,
            help='Name for the intake QC batch (default: auto-generated from project + date)'
        )

    def handle(self, *args, **options):
        project_id = options['project']
        file_path  = options['file']
        dry_run    = options['dry_run']
        batch_name = options['batch_name']

        # Load the project
        try:
            project = Project.objects.get(pk=project_id)
        except Project.DoesNotExist:
            raise CommandError(f"Project with ID {project_id} does not exist.")

        self.stdout.write(f"\nProject   : {project.project_name}")
        self.stdout.write(f"File      : {file_path}")
        self.stdout.write(f"Mode      : {'DRY RUN — nothing will be saved' if dry_run else 'LIVE'}\n")


        # Read and parse the CSV
        rows = []
        errors = []

        try:
            with open(file_path, newline='', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)

                # Validate headers exist
                required_cols = [COL_CASE_ID, COL_SPECIMEN_TYPE, COL_NUCLEID_TYPE, COL_CONCENTRATION, COL_VOLUME]
                missing = [c for c in required_cols if c not in reader.fieldnames]
                if missing:
                    raise CommandError(
                        f"CSV is missing required columns: {missing}\n"
                        f"Found columns: {reader.fieldnames}"
                    )

                for row_num, row in enumerate(reader, start=2):  # start=2 because row 1 is header
                    case_id = row.get(COL_CASE_ID, '').strip()
                    if not case_id:
                        errors.append(f"Row {row_num}: Empty CaseID — skipped.")
                        continue

                    try:
                        specimen_type  = row.get(COL_SPECIMEN_TYPE, '').strip()
                        nucleid_type   = row.get(COL_NUCLEID_TYPE, '').strip()
                        concentration  = parse_float(row.get(COL_CONCENTRATION, ''), COL_CONCENTRATION, row_num)
                        volume         = parse_float(row.get(COL_VOLUME, ''), COL_VOLUME, row_num)

                        if not specimen_type:
                            errors.append(f"Row {row_num}: Empty SpecimenType — skipped.")
                            continue

                        if nucleid_type not in ('DNA', 'RNA'):
                            errors.append(
                                f"Row {row_num}: NucleidType '{nucleid_type}' is not valid. "
                                f"Expected 'DNA' or 'RNA'."
                            )
                            continue

                        rows.append({
                            'row_num'      : row_num,
                            'case_id'      : case_id,
                            'specimen_type': specimen_type,
                            'nucleid_type' : nucleid_type,
                            'concentration': concentration,
                            'volume'       : volume,
                        })

                    except ValueError as e:
                        errors.append(str(e))

        except FileNotFoundError:
            raise CommandError(f"File not found: {file_path}")


        # Validate specimen types against the database
        found_types = set(r['specimen_type'] for r in rows)
        existing_types = set(
            SpecimenType.objects.filter(specimen_type__in=found_types).values_list('specimen_type', flat=True)
        )
        unknown_types = found_types - existing_types
        if unknown_types:
            errors.append(
                f"Unknown SpecimenType values: {unknown_types}. "
                f"Add them to specimen_type before importing."
            )

        # Check for duplicate (CaseID, SpecimenType) combos already in this project
        # A sample is uniquely identified by its generated name, which we can't know until
        # after save(). Instead we check for existing specimens under each case.
        existing_case_specimen_pairs = set(
            Sample.objects.filter(project=project)
            .values_list('specimen__case__case_name', 'specimen__specimen_type__specimen_type')
        )
        duplicates_in_db = [
            r for r in rows
            if (r['case_id'], r['specimen_type']) in existing_case_specimen_pairs
        ]
        if duplicates_in_db:
            for r in duplicates_in_db:
                errors.append(
                    f"Row {r['row_num']}: A sample for case '{r['case_id']}' / "
                    f"specimen '{r['specimen_type']}' already exists in this project."
                )

        # Check for duplicate rows within the file itself
        seen_pairs = set()
        for r in rows:
            key = (r['case_id'], r['specimen_type'])
            if key in seen_pairs:
                errors.append(
                    f"Row {r['row_num']}: Duplicate (CaseID, SpecimenType) "
                    f"'{r['case_id']} / {r['specimen_type']}' in this file."
                )
            seen_pairs.add(key)

        # Print validation summary
        self.stdout.write(f"Rows parsed       : {len(rows)}")
        self.stdout.write(f"Unique cases      : {len(set(r['case_id'] for r in rows))}")
        self.stdout.write(f"Unique specimens  : {len(set((r['case_id'], r['specimen_type']) for r in rows))}")
        self.stdout.write(f"Samples to create : {len(rows) - len(duplicates_in_db)}")
        self.stdout.write(f"Errors found      : {len(errors)}\n")

        if errors:
            self.stdout.write(self.style.ERROR("── Errors ───"))
            for e in errors:
                self.stdout.write(self.style.ERROR(f"  {e}"))
            self.stdout.write("")
            if not dry_run:
                raise CommandError("Import aborted due to errors. Fix them and try again.")

        # Preview table
        self.stdout.write(self.style.WARNING("── Preview (first 10 rows) ───"))
        self.stdout.write(
            f"  {'CaseID':<12} {'SpecimenType':<18} {'Type':<6} "
            f"{'Conc.(ng)':<12} {'Volume(uL)'}"
        )
        self.stdout.write("  " + "-" * 65)
        for r in rows[:10]:
            self.stdout.write(
                f"  {r['case_id']:<12} {r['specimen_type']:<18} {r['nucleid_type']:<6} "
                f"{str(r['concentration']):<12} {str(r['volume'])}"
            )
        if len(rows) > 10:
            self.stdout.write(f"  ... and {len(rows) - 10} more rows")
        self.stdout.write("")

        if dry_run:
            self.stdout.write(self.style.SUCCESS("Dry run complete — nothing was saved."))
            return


        # Save everything in one transaction
        # If anything fails mid-import the whole thing rolls back cleanly.
        with transaction.atomic():

            #TODO make an automatic batch system (divide this batch in 4 equally and add control sample for the batches?)
            #TODO max batch of 96 for a plate. Make it so the user can say i want all these samples to be divided in n batches
            from django.utils import timezone
            if not batch_name:
                batch_hex  = format(SampleQCBatch.objects.count() + 1, '04X')
                batch_name = f"{project.project_name}-Batch-{batch_hex}"

            intake_batch = SampleQCBatch.objects.create(
                batch_name=batch_name,
                date_batched=timezone.now().date(),
                created_by='Client Intake Import',
            )

            cases_created     = 0
            specimens_created = 0
            samples_created   = 0

            # Cache to avoid hitting the DB on every row
            case_cache     = {}   # case_id → Case instance
            specimen_cache = {}   # (case_id, specimen_type) → Specimen instance
            type_cache     = {}   # specimen_type string → SpecimenType instance

            for r in rows:
                if (r['case_id'], r['specimen_type']) in existing_case_specimen_pairs:
                    continue    # skip already-existing samples

                # ── Case ───
                if r['case_id'] not in case_cache:
                    case, created = Case.objects.get_or_create(
                        client=project.client,
                        case_name=r['case_id'],
                    )
                    case_cache[r['case_id']] = case
                    if created:
                        cases_created += 1
                else:
                    case = case_cache[r['case_id']]

                # ── SpecimenType lookup ───
                if r['specimen_type'] not in type_cache:
                    type_cache[r['specimen_type']] = SpecimenType.objects.get(
                        specimen_type=r['specimen_type']
                    )
                specimen_type_obj = type_cache[r['specimen_type']]

                # ── Specimen ───
                specimen_key = (r['case_id'], r['specimen_type'])
                if specimen_key not in specimen_cache:
                    specimen, created = Specimen.objects.get_or_create(
                        case=case,
                        specimen_type=specimen_type_obj,
                    )
                    specimen_cache[specimen_key] = specimen
                    if created:
                        specimens_created += 1
                else:
                    specimen = specimen_cache[specimen_key]

                # ── Sample ────
                sample = Sample.objects.create(
                    specimen=specimen,
                    project=project,
                    sample_type=r['nucleid_type'],
                    volume_received=r['volume'],
                    date_received=timezone.now().date(),
                )
                samples_created += 1

                # ── BatchSample + SampleQC (client intake measurements) ──
                BatchSample.objects.create(batch=intake_batch, sample=sample)
                SampleQC.objects.create(
                    sample=sample,
                    batch=intake_batch,
                    qubit_nm=r['concentration'],    # Concentration (ng) = Qubit
                    qc_status=SampleQC.PENDING,     # lab will review and update status
                    notes='Client intake values.',
                )


        # Final summary
        self.stdout.write(self.style.SUCCESS("── Import complete ───"))
        self.stdout.write(self.style.SUCCESS(f"  Cases created     : {cases_created}"))
        self.stdout.write(self.style.SUCCESS(f"  Specimens created : {specimens_created}"))
        self.stdout.write(self.style.SUCCESS(f"  Samples created   : {samples_created}"))
        self.stdout.write(self.style.SUCCESS(f"  QC batch created  : {intake_batch.batch_name}"))
        self.stdout.write(self.style.SUCCESS(f"  QC results created: {samples_created}"))
        self.stdout.write(self.style.SUCCESS(f"  Skipped (existing): {len(duplicates_in_db)}"))