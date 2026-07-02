"""
Management command to seed the database with static / reference data.

Usage:
    python manage.py seed_db            # seed everything
    python manage.py seed_db --reset    # wipe the seeded tables first, then reseed

Sections — edit the DATA blocks below to add / change values:
    1.  Django permission groups
    2.  Locations
    3.  Specimen types
    4.  Clients
    5.  Suppliers
    6.  Products  (+ links to suppliers)
    7.  Index Kits + Library Indexes (loaded from library/fixtures/library_index_seed.json)
"""

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import Group, Permission


# ══════════════════════════════════════════════════════════════════════════════
#  1. PERMISSION GROUPS
#     Each entry is a group name + a list of Django permission codenames.
#     Format: "app_label.codename"  e.g. "samples.add_sample"
#     Leave the permissions list empty [] if you want to assign them later.
# ══════════════════════════════════════════════════════════════════════════════
GROUPS = [
    {
        "name": "Lab Technician",
        "permissions": [
            "samples.view_sample",
            "samples.add_sample",
            "samples.change_sample",
            "qc.view_sampleqc",
            "qc.add_sampleqc",
            "qc.change_sampleqc",
            "qc.view_sampleqcbatch",
            "qc.add_sampleqcbatch",
            "inventory.view_inventory",
            "inventory.view_inventoryreceipt",
            "inventory.add_inventoryreceipt",
            "locations.view_location",
            "locations.view_templog",
            "locations.add_templog",
        ],
    },
    {
        "name": "Client Investagator",
        "permissions": [
            "samples.view_sample",
            "samples.view_client",
            "samples.view_case",
            "samples.view_project",
            "qc.view_sampleqc",
            "qc.view_sampleqcbatch",
            "inventory.view_inventory",
        ],
    },
    {
        "name": "Lab Manager",
        "permissions": [
            "samples.view_sample",
            "samples.add_sample",
            "samples.change_sample",
            "qc.view_sampleqc",
            "qc.add_sampleqc",
            "qc.change_sampleqc",
            "qc.view_sampleqcbatch",
            "qc.add_sampleqcbatch",
            "inventory.view_inventory",
            "inventory.view_inventoryreceipt",
            "inventory.add_inventoryreceipt",
            "locations.view_location",
            "locations.view_templog",
            "locations.add_templog",


        ],  # assign all permissions manually in admin, or list them here
    },
]


# ══════════════════════════════════════════════════════════════════════════════
#  2. LOCATIONS
#     locationName must be one of the choices defined in Location.LOCATION_CHOICES
#     storageType  must be one of the choices defined in Location.STORAGE_TYPE_CHOICES
#
#     Valid locationName values:
#       'Vanishing Cabinet', 'Netflix N Chill', 'James Bond', 'Yeti',
#       'Pre-PCR Room', 'Post-PCR Room',
#       '4th floor -80C Freezer', '4th floor -20C Freezer'
#
#     Valid storageType values:
#       'Room-Temperature', 'Fridge(4C)', 'Freezer(-20C)', 'Freezer(-80C)'
# ══════════════════════════════════════════════════════════════════════════════
LOCATIONS = [
    {"locationName": "Vanishing Cabinet",    "storageType": "Freezer(-20C)"},
    {"locationName": "Netflix N Chill",      "storageType": "Freezer(-20C)"},
    {"locationName": "James Bond",           "storageType": "Fridge(4C)"},
    {"locationName": "Yeti",                 "storageType": "Freezer(-20C)"},
    {"locationName": "Pre-PCR Room",         "storageType": "Room-Temperature"},
    {"locationName": "Post-PCR Room",        "storageType": "Room-Temperature"},
    {"locationName": "4th floor -80C Freezer", "storageType": "Freezer(-80C)"},
    {"locationName": "4th floor -20C Freezer", "storageType": "Freezer(-20C)"},
]


# ══════════════════════════════════════════════════════════════════════════════
#  3. SPECIMEN TYPES
#     specimen_type is the primary key — must be unique.
#     Add / remove types as you need
# ══════════════════════════════════════════════════════════════════════════════
SPECIMEN_TYPES = [
    "Bl",
    "FFPE",
    "FrzT", # "FrozenTissue",
    "Cells",
    "EV",   # Extracellular Vesicles   
    "smallEVs",        
    "LargeEVs",     
    #"Plasma",
    #"Serum",
    #"Urine",
    #"Saliva",
    #"CSF",                  # Cerebrospinal Fluid
    #"BoneMarrow",
    #"PBMC",
    
]


# ══════════════════════════════════════════════════════════════════════════════
#  4. CLIENTS
#     client_name      → person's name
#     organisation_name → their institution / lab
# ══════════════════════════════════════════════════════════════════════════════
CLIENTS = [
    # ── Add your clients below ────────────────────────────────────────────────
    # {"client_name": "Jane Smith",    "organisation_name": "Dalhousie University"},
    # {"client_name": "Paul Dubois",   "organisation_name": "Université de Moncton"},
    # ─────────────────────────────────────────────────────────────────────────

    {"client_name": "eric",    "organisation_name": "ACRI"},
    {"client_name": "mathieu",   "organisation_name": "Université de Moncton"},

]


# ══════════════════════════════════════════════════════════════════════════════
#  5. SUPPLIERS
#     supplier_name  → company name
#     contact_name   → your rep / main contact
#     contact_email  → their email
# ══════════════════════════════════════════════════════════════════════════════
SUPPLIERS = [
    # ── Add your suppliers below ──────────────────────────────────────────────
    # {
    #     "supplier_name":  "Thermo Fisher Scientific",
    #     "contact_name":   "John Doe",
    #     "contact_email":  "jdoe@thermofisher.com",
    # },
    # {
    #     "supplier_name":  "Qiagen",
    #     "contact_name":   "Alice Martin",
    #     "contact_email":  "amartin@qiagen.com",
    # },
    # ─────────────────────────────────────────────────────────────────────────
    {"supplier_name": "Amneal-Agila, LLC",                   "contact_name": "Fletcher",  "contact_email": "fmcilhargar@networksolutions.com"},
    {"supplier_name": "Apotex Corp",                         "contact_name": "Nessa",     "contact_email": "nboog7@163.com"},
    {"supplier_name": "Duramed Pharmaceuticals, Inc.",       "contact_name": "Nolana",    "contact_email": "npalfremanp@archive.org"},
    {"supplier_name": "General Injectables & Vaccines, Inc", "contact_name": "Archibald", "contact_email": "aboswellf@state.tx.us"},
    {"supplier_name": "Par Pharmaceutical, Inc.",            "contact_name": "Carin",     "contact_email": "cpendockx@uol.com.br"},
    {"supplier_name": "Reese Pharmaceutical Co",             "contact_name": "Reese",     "contact_email": "rdaymont3@msu.edu"},
    {"supplier_name": "REMEDYREPACK INC.",                   "contact_name": "Sinclair",  "contact_email": "sbirdseyef@oakley.com"},
]


# ══════════════════════════════════════════════════════════════════════════════
#  6. PRODUCTS
#     product_name       → display name
#     product_ref_number → catalog / reference number
#     product_notes      → optional note (or None)
#     suppliers          → list of supplier_name strings from SUPPLIERS above
#                          (must match exactly — case sensitive)
# ══════════════════════════════════════════════════════════════════════════════
PRODUCTS = [
    # ── Add your products below ───────────────────────────────────────────────
    # {
    #     "product_name":       "RNeasy Mini Kit",
    #     "product_ref_number": "74104",
    #     "product_notes":      "50 preps",
    #     "suppliers":          ["Qiagen"],
    # },
    # {
    #     "product_name":       "Qubit RNA HS Assay Kit",
    #     "product_ref_number": "Q32852",
    #     "product_notes":      None,
    #     "suppliers":          ["Thermo Fisher Scientific"],
    # },
    # ─────────────────────────────────────────────────────────────────────────


    {
        "product_name":       "CEFPROZIL",
        "product_ref_number": "QXZ5-Y8BB",
        "product_notes":      None,
        "suppliers":          ["Duramed Pharmaceuticals, Inc.", "REMEDYREPACK INC."],
    },
    {
        "product_name":       "Cephalexin",
        "product_ref_number": "S1KJ-7YI4",
        "product_notes":      None,
        "suppliers":          ["Apotex Corp", "General Injectables & Vaccines, Inc", "REMEDYREPACK INC."],
    },
    {
        "product_name":       "Nafcillin",
        "product_ref_number": "329E-WKFB",
        "product_notes":      None,
        "suppliers":          ["Reese Pharmaceutical Co"],
    },
    {
        "product_name":       "Rifampin",
        "product_ref_number": "5E7Y-WZ9V",
        "product_notes":      None,
        "suppliers":          ["Apotex Corp", "Duramed Pharmaceuticals, Inc.", "Par Pharmaceutical, Inc."],
    },
    {
        "product_name":       "Topiramate",
        "product_ref_number": "W7AE-189V",
        "product_notes":      None,
        "suppliers":          ["Amneal-Agila, LLC", "Apotex Corp", "Par Pharmaceutical, Inc."],
    },
]


# ══════════════════════════════════════════════════════════════════════════════
#  7. INDEX KITS  (Library Indexes)
#     The actual ~1,250 well/sequence rows live in:
#         library/fixtures/library_index_seed.json
#     (generated from the lab's index plate spec sheets — not meant to be
#     hand-edited; regenerate it instead if the source spreadsheet changes).
#
#     This map just tells the seeder which WorkflowType each kit in that
#     fixture belongs to. The key MUST match a "kit_name" in the JSON file;
#     the value MUST match a WorkflowType.workflowType already defined
#     (either seeded elsewhere, or created manually in admin first).
#
#     If a kit's WorkflowType doesn't exist yet, that kit is skipped with
#     a warning it will NOT silently attach to the wrong workflow.
# ══════════════════════════════════════════════════════════════════════════════

# ══════════════════════════════════════════════════════════════════════════════
#  7. WORKFLOW TYPES
#     workflowType MUST exactly match the values used in INDEX_KIT_WORKFLOW_MAP
#     below, since IndexKit looks these up by name.
# ══════════════════════════════════════════════════════════════════════════════
# ══════════════════════════════════════════════════════════════════════════════
#  X. WORKFLOW TYPES
#     workflowType MUST exactly match the values used in INDEX_KIT_WORKFLOW_MAP.
# ══════════════════════════════════════════════════════════════════════════════
WORKFLOW_TYPES = [
    {
        "workflowType":      "TotalRNA",
        "sample_type":       "RNA",
        "target_input_ng":   250.0,
        "target_volume_ul":  11.0,
        "diluent_name":      "NF H₂O",
        "fragment_min_bp":   200,
        "fragment_max_bp":   475,
        "dimer_threshold_pct": 10.0,
    },
    {
        "workflowType":      "Small RNA",
        "sample_type":       "RNA",
        "target_input_ng":   10.0,
        # 5 µl total prep volume = 4.5 µl sample/diluent + 0.5 µl Qia Spike control.
        "target_volume_ul":  4.5,
        "diluent_name":      "NF H₂O",
        "fragment_min_bp":   140,
        "fragment_max_bp":   250,
        "dimer_threshold_pct": 10.0,
    },
    {
        "workflowType":      "KAPA HyperPlus DNA",
        "sample_type":       "DNA",
        "target_input_ng":   250.0,
        "target_volume_ul":  35.0,
        "diluent_name":      "Tris-HCl pH 8.5 10mM",
        "fragment_min_bp":   200,
        "fragment_max_bp":   600,
        "dimer_threshold_pct": 10.0,
    },
    {
        "workflowType":      "DNA PCR Free WGS",
        "sample_type":       "DNA",
        "target_input_ng":   500.0,
        "target_volume_ul":  25.0,
        "diluent_name":      "Resuspension Buffer (RSB)",
        # No TapeStation / no dimer cleanup step for this workflow -
        # only a Qubit nM gate, so leave these unset.
        "fragment_min_bp":   None,
        "fragment_max_bp":   None,
        "dimer_threshold_pct": None,
    },
]


INDEX_KIT_WORKFLOW_MAP = {
    "ILLMN-DNA-RNA-V2": "Illumina DNA/RNA UD Indexes v2",
    "ILLMN-DNA-RNA-V3": "Illumina DNA/RNA UD Indexes v3",
    "KAPA-UDI":         "KAPA HyperPlus DNA",
    "sRNA-V4":          "Small RNA",
}

LIBRARY_INDEX_FIXTURE = Path(__file__).resolve().parent.parent.parent / "fixtures" / "library_index_seed.json"


# ══════════════════════════════════════════════════════════════════════════════
#  Command — do not edit below this line unless you know what you're doing
# ══════════════════════════════════════════════════════════════════════════════

class Command(BaseCommand):
    help = "Seed the database with static reference data."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete existing seed data before re-seeding.",
        )
        parser.add_argument(
            "--skip-indexes",
            action="store_true",
            help="Skip seeding Index Kits / Library Indexes (the slow, ~1,250-row step).",
        )

    def handle(self, *args, **options):
        if options["reset"]:
            self.stdout.write(self.style.WARNING("-- Resetting seed tables --"))
            self._reset()

        self.stdout.write("\nSeeding...")
        self._seed_groups()
        self._seed_locations()
        self._seed_specimen_types()
        self._seed_clients()
        self._seed_suppliers()
        self._seed_products()
        self._seed_workflow_types()
        if not options["skip_indexes"]:
            self._seed_index_kits()
        self.stdout.write(self.style.SUCCESS("\nDone — database seeded successfully.\n"))

    # ── reset ──────────────────────────────────────────────────────────────────

    def _reset(self):
        from samples.models import Client, SpecimenType
        from locations.models import Location
        from inventory.models import Supplier, Product, ProductSupplier
        from library.models import LibraryIndex, IndexKit

        LibraryIndex.objects.all().delete()
        self._log("cleared", "Library Indexes")
        IndexKit.objects.all().delete()
        self._log("cleared", "Index Kits")
        ProductSupplier.objects.all().delete()
        self._log("cleared", "ProductSupplier links")
        Product.objects.all().delete()
        self._log("cleared", "Products")
        Supplier.objects.all().delete()
        self._log("cleared", "Suppliers")
        Client.objects.all().delete()
        self._log("cleared", "Clients")
        SpecimenType.objects.all().delete()
        self._log("cleared", "Specimen types")
        Location.objects.all().delete()
        self._log("cleared", "Locations")
        Group.objects.all().delete()
        self._log("cleared", "Groups")
        WorkflowType.objects.all().delete()
        self._log("cleared", "Workflow Types")

    # ── seeders ────────────────────────────────────────────────────────────────

    def _seed_groups(self):
        self.stdout.write("\n[Groups]")
        for entry in GROUPS:
            group, created = Group.objects.get_or_create(name=entry["name"])
            if created:
                self._log("created", entry["name"])
            else:
                self._log("exists ", entry["name"])

            for perm_str in entry["permissions"]:
                try:
                    app_label, codename = perm_str.split(".")
                    perm = Permission.objects.get(
                        codename=codename,
                        content_type__app_label=app_label,
                    )
                    group.permissions.add(perm)
                except Permission.DoesNotExist:
                    self.stdout.write(
                        self.style.WARNING(
                            f"  ⚠  Permission not found: {perm_str} — skipping"
                        )
                    )
                except ValueError:
                    self.stdout.write(
                        self.style.WARNING(
                            f"  ⚠  Bad permission format '{perm_str}' — use 'app_label.codename'"
                        )
                    )

    def _seed_locations(self):
        from locations.models import Location

        self.stdout.write("\n[Locations]")
        for entry in LOCATIONS:
            obj, created = Location.objects.get_or_create(
                locationName=entry["locationName"],
                storageType=entry["storageType"],
            )
            status = "created" if created else "exists "
            self._log(status, str(obj))

    def _seed_specimen_types(self):
        from samples.models import SpecimenType

        self.stdout.write("\n[Specimen Types]")
        for name in SPECIMEN_TYPES:
            obj, created = SpecimenType.objects.get_or_create(specimen_type=name)
            status = "created" if created else "exists "
            self._log(status, name)

    def _seed_clients(self):
        from samples.models import Client

        self.stdout.write("\n[Clients]")
        if not CLIENTS:
            self.stdout.write("  (no clients defined — add them to the CLIENTS list)")
            return
        for entry in CLIENTS:
            obj, created = Client.objects.get_or_create(
                client_name=entry["client_name"],
                defaults={"organisation_name": entry["organisation_name"]},
            )
            status = "created" if created else "exists "
            self._log(status, f"{entry['client_name']} ({entry['organisation_name']})")

    def _seed_suppliers(self):
        from inventory.models import Supplier

        self.stdout.write("\n[Suppliers]")
        if not SUPPLIERS:
            self.stdout.write("  (no suppliers defined — add them to the SUPPLIERS list)")
            return
        for entry in SUPPLIERS:
            obj, created = Supplier.objects.get_or_create(
                supplier_name=entry["supplier_name"],
                defaults={
                    "contact_name":  entry["contact_name"],
                    "contact_email": entry["contact_email"],
                },
            )
            status = "created" if created else "exists "
            self._log(status, entry["supplier_name"])

    def _seed_products(self):
        from inventory.models import Product, Supplier, ProductSupplier

        self.stdout.write("\n[Products]")
        if not PRODUCTS:
            self.stdout.write("  (no products defined — add them to the PRODUCTS list)")
            return
        for entry in PRODUCTS:
            product, created = Product.objects.get_or_create(
                product_ref_number=entry["product_ref_number"],
                defaults={
                    "product_name":  entry["product_name"],
                    "product_notes": entry.get("product_notes"),
                },
            )
            status = "created" if created else "exists "
            self._log(status, entry["product_name"])

            for supplier_name in entry.get("suppliers", []):
                try:
                    supplier = Supplier.objects.get(supplier_name=supplier_name)
                    ProductSupplier.objects.get_or_create(
                        product=product,
                        supplier=supplier,
                    )
                    self._log("linked ", f"{entry['product_name']} → {supplier_name}")
                except Supplier.DoesNotExist:
                    self.stdout.write(
                        self.style.WARNING(
                            f"  ⚠  Supplier '{supplier_name}' not found — "
                            f"add it to SUPPLIERS first"
                        )
                    )

    def _seed_workflow_types(self):
        from library.models import WorkflowType

        self.stdout.write("\n[Workflow Types]")
        for entry in WORKFLOW_TYPES:
            obj, created = WorkflowType.objects.get_or_create(
                workflowType=entry["workflowType"],
                defaults={k: v for k, v in entry.items() if k != "workflowType"},
            )
            status = "created" if created else "exists "
            self._log(status, entry["workflowType"])

    def _seed_index_kits(self):
        from library.models import IndexKit, LibraryIndex
        from library.models import WorkflowType

        self.stdout.write("\n[Index Kits / Library Indexes]")

        if not LIBRARY_INDEX_FIXTURE.exists():
            self.stdout.write(
                self.style.WARNING(
                    f"  ⚠  Fixture not found at {LIBRARY_INDEX_FIXTURE} — skipping. "
                    f"Re-run the parser script to regenerate it if needed."
                )
            )
            return

        with open(LIBRARY_INDEX_FIXTURE) as f:
            kits_data = json.load(f)

        for kit_entry in kits_data:
            kit_name = kit_entry["kit_name"]
            workflow_name = INDEX_KIT_WORKFLOW_MAP.get(kit_name)

            if not workflow_name:
                self.stdout.write(
                    self.style.WARNING(
                        f"  ⚠  '{kit_name}' has no entry in INDEX_KIT_WORKFLOW_MAP — skipping"
                    )
                )
                continue

            try:
                workflow_type = WorkflowType.objects.get(workflowType=workflow_name)
            except WorkflowType.DoesNotExist:
                self.stdout.write(
                    self.style.WARNING(
                        f"  ⚠  WorkflowType '{workflow_name}' not found for kit "
                        f"'{kit_name}' — create it first (admin or seed script), then re-run. Skipping kit."
                    )
                )
                continue

            kit, created = IndexKit.objects.get_or_create(
                name=kit_name,
                defaults={"workflowType": workflow_type},
            )
            if not created and kit.workflowType_id != workflow_type.id:
                kit.workflowType = workflow_type
                kit.save(update_fields=["workflowType"])
            status = "created" if created else "exists "
            self._log(status, f"IndexKit: {kit_name}  (→ {workflow_name})")

            new_wells = []
            existing_keys = set(
                LibraryIndex.objects.filter(indexKit=kit).values_list("plateSet", "well")
            )

            total_wells = 0
            for plate_set in kit_entry["sets"]:
                set_label = plate_set["set_label"] or ""
                for well in plate_set["wells"]:
                    total_wells += 1
                    key = (set_label, well["well"])
                    if key in existing_keys:
                        continue
                    new_wells.append(
                        LibraryIndex(
                            indexKit=kit,
                            plateSet=set_label,
                            well=well["well"],
                            udi_number=well["udi_number"],
                            i7Sequence=well["i7Sequence"],
                            i5Sequence=well["i5Sequence"],
                        )
                    )

            if new_wells:
                LibraryIndex.objects.bulk_create(new_wells, batch_size=500)
                self._log("created", f"{len(new_wells)} new well(s) for {kit_name}")
            else:
                self._log("exists ", f"all {total_wells} well(s) already present for {kit_name}")

    # ── helpers ───

    def _log(self, status: str, name: str):
        color = self.style.SUCCESS if status == "created" else self.style.HTTP_INFO
        self.stdout.write(f"  [{color(status)}]  {name}")