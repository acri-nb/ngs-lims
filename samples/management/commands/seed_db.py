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
"""

from django.core.management.base import BaseCommand
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
    {"locationName": "Vanishing Cabinet",    "storageType": "Freezer(-80C)"},
    {"locationName": "Netflix N Chill",      "storageType": "Freezer(-20C)"},
    {"locationName": "James Bond",           "storageType": "Freezer(-80C)"},
    {"locationName": "Yeti",                 "storageType": "Fridge(4C)"},
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
    "Blood",
    "FFPE",
    "FrozenTissue",
    "Cells",
    "EV",   # Extracellular Vesicles   
    "smallEVs",        
    "LargeEVs",     
    "Plasma",
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
        self.stdout.write(self.style.SUCCESS("\nDone — database seeded successfully.\n"))

    # ── reset ──────────────────────────────────────────────────────────────────

    def _reset(self):
        from samples.models import Client, SpecimenType
        from locations.models import Location
        from inventory.models import Supplier, Product, ProductSupplier

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

    # ── helpers ───

    def _log(self, status: str, name: str):
        color = self.style.SUCCESS if status == "created" else self.style.HTTP_INFO
        self.stdout.write(f"  [{color(status)}]  {name}")
