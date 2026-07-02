"""
Wipes ALL application data from the database (keeps Django internals).

Usage:
    python manage.py delete_db
"""

from django.core.management.base import BaseCommand

MODELS_TO_WIPE = [
    # Library (children first)
    ("library", "LibraryPrepBatchAuditLog"),
    ("library", "LibraryPrepSample"),
    ("library", "LibraryQC"),
    ("library", "LibraryQCBatch"),
    ("library", "LibraryPrepBatch"),
    ("library", "LibraryIndex"),
    ("library", "IndexKit"),
    ("library", "WorkflowStepRowOrder"),
    ("library", "StepRow"),
    ("library", "WorkflowTypeStep"),
    ("library", "WorkflowType"),

    # QC
    ("qc", "BatchAuditLog"),
    ("qc", "SampleQC"),
    ("qc", "BatchSample"),
    ("qc", "SampleQCBatch"),

    # Inventory
    ("inventory", "Inventory"),
    ("inventory", "InventoryReceipt"),
    ("inventory", "ProductSupplier"),
    ("inventory", "Product"),
    ("inventory", "Supplier"),

    # Samples
    ("samples", "Sample"),
    ("samples", "Specimen"),
    ("samples", "SpecimenType"),
    ("samples", "Case"),
    ("samples", "Project"),
    ("samples", "Client"),

    # Locations
    ("locations", "PlateWell"),
    ("locations", "PlateLayout"),
    ("locations", "Plate"),
    ("locations", "Rack"),
    ("locations", "TempLog"),
    ("locations", "Location"),
]

class Command(BaseCommand):
    help = "Delete ALL application data from the database. Asks for confirmation."

    def handle(self, *args, **options):
        self.stdout.write(self.style.ERROR(
            "\n⚠  WARNING: This will permanently delete ALL lab data.\n"
            "   Users, admin logs, and Django internals are kept.\n"
        ))

        confirm = input("Type  DELETE  to confirm: ").strip()
        if confirm != "DELETE":
            self.stdout.write(self.style.WARNING("Cancelled — nothing was deleted.\n"))
            return

        self.stdout.write("")
        total = 0
        for app_label, model_name in MODELS_TO_WIPE:
            from django.apps import apps
            try:
                Model = apps.get_model(app_label, model_name)
                count, _ = Model.objects.all().delete()
                total += count
                self.stdout.write(f"  deleted  {model_name:<25} ({count} rows)")
            except LookupError:
                self.stdout.write(self.style.WARNING(
                    f"  skipped  {model_name:<25} (model not found)"
                ))

        self.stdout.write(self.style.SUCCESS(
            f"\nDone — {total} total rows deleted.\n"
        ))