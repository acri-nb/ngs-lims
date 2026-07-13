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
    7.  Workflow Types
    8.  Master Mix step/row data (per WorkflowType)
    9.  Index Kits + Library Indexes (loaded from library/fixtures/library_index_seed.json)
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
#  7. WORKFLOW TYPES
#     workflowType MUST exactly match the values used in INDEX_KIT_WORKFLOW_MAP
#     and in MASTERMIX_DATA below, since those look these up by name.
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


# ══════════════════════════════════════════════════════════════════════════════
#  8. MASTER MIX STEP / ROW DATA
#
#     Reference data for the (future) Master Mix tab. This mirrors the lab's
#     protocol sheets: for each WorkflowType, an ordered list of steps, and
#     for each step, an ordered list of reagent rows with a per-reaction
#     volume.
#
#     Each row dict:
#         name             → StepRow.stepRowName (shared/reused across
#                             workflows and steps — e.g. "NF H2O" only
#                             gets created once, then linked per-step
#                             with its own volume via WorkflowStepRowOrder)
#         volume_per_rxn   → µL per single reaction (WorkflowStepRowOrder.volumePerRxn)
#         constant         → 0 = "Fixed / Header" (volume used as-is,
#                             ignores reaction count), 1 = "Per Reaction"
#                             (volume × reaction count), 2 = "Ethanol
#                             Dilution Pair" (this row's volume_per_rxn is
#                             the 80% ethanol working-solution volume per
#                             reaction; the model computes the actual
#                             ethanol + water split, rounded to 5 mL
#                             batches — see WorkflowStepRowOrder in
#                             models.py). Matches
#                             WorkflowStepRowOrder.constantOfMM. Default 1.
#         extra            → extra "dead volume" reactions added on top of
#                             the batch's reaction count for THIS reagent
#                             only, e.g. the sheet's "(n + 2)" pattern.
#                             Matches WorkflowStepRowOrder.extra_reactions.
#                             Default 0.
#
#     NOT included below (deliberately — see chat writeup):
#       - "Total Volume" rows: these are just sums of the rows above them
#         and are meant to be computed at display time, not stored.
#       - Adapter/probe dilution sub-tables (stock + diluent): these are a
#         one-time dilution prep independent of reaction count and also
#         depend on a separate "dilution factor" input the lab member picks
#         per batch — that's a different kind of input than anything else
#         here, so it stays out of scope for now.
#       - The KAPA "Stop Solution (ST2)" / "Resuspension Buffer (RSB)"
#         "aliquot into 8-strip" sub-division (divide the total by 8 for
#         pipetting) — a display nicety on top of the already-correct
#         total volume, not a new number worth modelling yet.
# ══════════════════════════════════════════════════════════════════════════════
MASTERMIX_DATA = {

    # ── 1.ods — MM NextFlex RiboZeroPlus ───────────────────────────────────
    "TotalRNA": [
        {
            "stepName": "Hybridize Probe MM", "sort_order": 10,
            "rows": [
                {"name": "DB1", "volume_per_rxn": 3.6},
                {"name": "DP1", "volume_per_rxn": 1.2},
            ],
        },
        {
            "stepName": "rRNA Depletion MM", "sort_order": 20,
            "rows": [
                {"name": "RDB", "volume_per_rxn": 4.8},
                {"name": "RDE (flick to mix)", "volume_per_rxn": 1.2},
            ],
        },
        {
            "stepName": "Probe Removal MM", "sort_order": 30,
            "rows": [
                {"name": "PRB", "volume_per_rxn": 7.7},
                {"name": "PRE (flick to mix)", "volume_per_rxn": 3.3},
            ],
        },
        {
            "stepName": "Clean Up RNA", "sort_order": 35,
            "rows": [
                {"name": "80% Ethanol (RNA Clean-up)", "volume_per_rxn": 350, "extra": 2, "constant": 2},
                {"name": "RNAClean XP Beads", "volume_per_rxn": 60},
            ],
        },
        {
            "stepName": "Fragment and Denature RNA", "sort_order": 40,
            "rows": [
                {"name": "EPH3", "volume_per_rxn": 8.5, "extra": 1},
            ],
        },
        {
            "stepName": "First Strand Synthesis MM", "sort_order": 50,
            "rows": [
                {"name": "FSA", "volume_per_rxn": 9},
                {"name": "RVT (flick to mix)", "volume_per_rxn": 1},
            ],
        },
        {
            "stepName": "Second Strand Synthesis MM", "sort_order": 60,
            "rows": [
                {"name": "SMM (invert to mix)", "volume_per_rxn": 25, "extra": 1},
            ],
        },
        {
        
            "stepName": "Clean Up cDNA", "sort_order": 65,
            "is_stopping_point": True,
            "rows": [
                {"name": "80% Ethanol (cDNA Clean-up)", "volume_per_rxn": 350, "extra": 2, "constant": 2},
                {"name": "AMPure XP Beads", "volume_per_rxn": 90},
            ],
        },
        {
            "stepName": "Adenylate 3' Ends", "sort_order": 70,
            "rows": [
                {"name": "ATL4 (flick to mix)", "volume_per_rxn": 12.5, "extra": 1},
            ],
        },
        {
            # Sheet note: "Use directly from tube" — no dead-volume buffer.
            "stepName": "Ligate Anchors", "sort_order": 80,
            "rows": [
                {"name": "LIGX (flick to mix)", "volume_per_rxn": 2.5},
            ],
        },
        {
            "stepName": "Stop Ligation", "sort_order": 90,
            "rows": [
                {"name": "STL", "volume_per_rxn": 5, "extra": 2},
            ],
        },
        {
            # Sheet marks "Safe Stopping Point" right after this clean-up,
            # not after Stop Ligation itself.
            "stepName": "Clean Up Fragments", "sort_order": 95,
            "is_stopping_point": True,
            "rows": [
                {"name": "80% Ethanol (Fragment Clean-up)", "volume_per_rxn": 350, "extra": 2, "constant": 2},
                {"name": "AMPure XP Beads", "volume_per_rxn": 34},
            ],
        },
        {
            "stepName": "PCR Amplification", "sort_order": 100,
            "is_stopping_point": True,
            "rows": [
                {"name": "EPM (invert to mix)", "volume_per_rxn": 20, "extra": 1},
            ],
        },
        {
            "stepName": "Clean Up Library", "sort_order": 110,
            "rows": [
                {"name": "80% Ethanol (Library Clean-up)", "volume_per_rxn": 350, "extra": 2, "constant": 2},
                {"name": "AMPure XP Beads", "volume_per_rxn": 50},
            ],
        },
    ],

    # ── 2.ods — MM Illumina DNA-PCR Free ───────────────────────────────────
    "DNA PCR Free WGS": [
        {
            "stepName": "BLT-PF", "sort_order": 10,
            "rows": [
                {"name": "BLT-PF", "volume_per_rxn": 15, "extra": 2},
            ],
        },
        {
            "stepName": "Tagmentation Buffer (TB1)", "sort_order": 20,
            "rows": [
                {"name": "TB1", "volume_per_rxn": 10, "extra": 2},
            ],
        },
        {
            "stepName": "Tagmentation Wash Buffer (TWB) - Post-Tagmentation", "sort_order": 30,
            "rows": [
                {"name": "TWB", "volume_per_rxn": 150, "extra": 2},
            ],
        },
        {
            "stepName": "Enzyme Ligation Mix (ELM)", "sort_order": 40,
            "rows": [
                {"name": "ELM", "volume_per_rxn": 50, "extra": 2},
            ],
        },
        {
            "stepName": "Tagmentation Wash Buffer (TWB) - Post-Ligation", "sort_order": 50,
            "rows": [
                {"name": "TWB", "volume_per_rxn": 75, "extra": 2},
            ],
        },
        {
            "stepName": "HP3", "sort_order": 60,
            "rows": [
                {"name": "HP3", "volume_per_rxn": 6},
                {"name": "NF H2O", "volume_per_rxn": 54},
            ],
        },
        {
            "stepName": "Illumina Purification Beads (Plate 1)", "sort_order": 70,
            "rows": [
                {"name": "IPB", "volume_per_rxn": 36},
            ],
        },
        {
            "stepName": "Illumina Purification Beads (Plate LP2)", "sort_order": 80,
            "rows": [
                {"name": "IPB", "volume_per_rxn": 42},
            ],
        },
        {
            "stepName": "Ethanol 80%", "sort_order": 90,
            "rows": [
                {"name": "Ethanol 99%", "volume_per_rxn": 400},
                {"name": "NF H2O", "volume_per_rxn": 100},
            ],
        },
        {
            "stepName": "Resuspension Buffer (RSB)", "sort_order": 100,
            "rows": [
                {"name": "RSB", "volume_per_rxn": 22, "extra": 4},
            ],
        },
    ],

    # ── 3.ods — MM KAPA HyperPlus ───────────────────────────────────────────
    "KAPA HyperPlus DNA": [
        {
            "stepName": "Step A: Enzymatic Fragmentation of Genomic DNA", "sort_order": 10,
            "rows": [
                {"name": "KAPA Fragmentation Buffer (10X)", "volume_per_rxn": 5},
                {"name": "KAPA Fragmentation Enzyme", "volume_per_rxn": 10},
            ],
        },
        {
            "stepName": "Step B: End Repair & A-Tailing", "sort_order": 20,
            "rows": [
                {"name": "End Repair & A-Tailing Buffer", "volume_per_rxn": 7},
                {"name": "End Repair & A-Tailing Enzyme Mix", "volume_per_rxn": 3},
            ],
        },
        {
            "stepName": "Step C: Adapter Ligation", "sort_order": 30,
            "rows": [
                {"name": "NF H2O", "volume_per_rxn": 5},
                {"name": "Ligation Buffer", "volume_per_rxn": 30},
                {"name": "DNA Ligase", "volume_per_rxn": 10},
            ],
        },
        {
            # Unlike TotalRNA's clean-ups, KAPA's ethanol formula here uses
            # the reaction count directly with no "+2" dead-volume buffer,
            # and the sheet doesn't track a separate bead-volume line item.
            "stepName": "Step D: Post-Ligation Cleanup", "sort_order": 35,
            "rows": [
                {"name": "80% Ethanol (Post-Ligation Clean-up)", "volume_per_rxn": 400, "constant": 2},
            ],
        },
        {
            # Sheet note: "Add Following Samples in Order. DO NOT CREATE
            # MASTERMIX" — these two reagents are added to each reaction
            # individually rather than pre-mixed. Kept as regular rows for
            # reference volumes; the print-sheet UI should call this out.
            "stepName": "Step E: PCR Library Amplification (add individually, do not premix)",
            "sort_order": 40,
            "rows": [
                {"name": "Library Amplification Primer Mix (10X)", "volume_per_rxn": 5},
                {"name": "KAPA HiFi HotStart ReadyMix (2X)", "volume_per_rxn": 25},
            ],
        },
        {
            "stepName": "Step F: Post-Amplification Cleanup", "sort_order": 45,
            "rows": [
                {"name": "80% Ethanol (Post-Amplification Clean-up)", "volume_per_rxn": 400, "constant": 2},
            ],
        },
    ],

    # ── 4.ods — MM NextFlex Small RNA ───────────────────────────────────────
    "Small RNA": [
        {
            "stepName": "Step A: 3' 4N Adenylated Adaptor Ligation to RNA Template",
            "sort_order": 10,
            "rows": [
                {"name": "NextFlex 3' Adapter (refer to dilution)", "volume_per_rxn": 1},
                {"name": "NEXTFLEX 3' Ligation Buffer", "volume_per_rxn": 12.5},
                {"name": "NEXTFLEX 3' Ligation Enzyme Mix", "volume_per_rxn": 1.5},
            ],
        },
        {
            "stepName": "Step B: Excess 3' Adapter Removal", "sort_order": 20,
            "rows": [
                {"name": "NEXTFLEX Adapter Inactivation Mix", "volume_per_rxn": 4},
            ],
        },
        {
            "stepName": "Step C: NEXTFLEX 5' 4N Adapter Ligation", "sort_order": 30,
            "rows": [
                {"name": "NEXTFLEX 5' 4N Adapter (diluted)", "volume_per_rxn": 1},
                {"name": "NEXTFLEX 5' Ligation Buffer", "volume_per_rxn": 3},
                {"name": "NEXTFLEX 5' Ligation Enzyme Mix", "volume_per_rxn": 2},
            ],
        },
        {
            "stepName": "Step D: Reverse Transcription - First Strand Synthesis",
            "sort_order": 40,
            "is_stopping_point": True,
            "rows": [
                {"name": "NEXTFLEX RT Primer", "volume_per_rxn": 1},
                {"name": "NEXTFLEX RT Buffer", "volume_per_rxn": 7},
                {"name": "M-MuLV Reverse Transcriptase", "volume_per_rxn": 2},
            ],
        },
        {
            # Ethanol formula here uses reaction count directly (no "+2");
            # the isopropanol precipitation step does use "+2", matching
            # the sheet's two different formulas side by side.
            "stepName": "Step E: Bead Clean Up (without size selection)", "sort_order": 45,
            "is_stopping_point": True,
            "rows": [
                {"name": "80% Ethanol (Bead Clean-up)", "volume_per_rxn": 400, "constant": 2},
                {"name": "100% Isopropanol", "volume_per_rxn": 90, "extra": 2},
            ],
        },
        {
            "stepName": "Step 7: PCR Amplification of the RT Product", "sort_order": 50,
            "is_stopping_point": True,
            "rows": [
                {"name": "NEXTFLEX Small RNA PCR Master Mix", "volume_per_rxn": 6},
            ],
        },
        {
            "stepName": "Step 8: Size Selection and Clean Up (without size selection for exosome samples)",
            "sort_order": 55,
            "rows": [
                {"name": "80% Ethanol (Size Selection Clean-up)", "volume_per_rxn": 400, "constant": 2},
            ],
        },
    ],
}


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
        self._seed_mastermix_steps()
        if not options["skip_indexes"]:
            self._seed_index_kits()
        self.stdout.write(self.style.SUCCESS("\nDone — database seeded successfully.\n"))

    # ── reset ──────────────────────────────────────────────────────────────────

    def _reset(self):
        from samples.models import Client, SpecimenType
        from locations.models import Location
        from inventory.models import Supplier, Product, ProductSupplier
        from library.models import (
            LibraryIndex, IndexKit, WorkflowType, WorkflowTypeStep,
            StepRow, WorkflowStepRowOrder,
        )

        WorkflowStepRowOrder.objects.all().delete()
        self._log("cleared", "Workflow Step Rows (master mix links)")
        WorkflowTypeStep.objects.all().delete()
        self._log("cleared", "Workflow Type Steps")
        StepRow.objects.all().delete()
        self._log("cleared", "Step Rows (reagents)")
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

    def _seed_mastermix_steps(self):
        """
        Seed WorkflowTypeStep / StepRow / WorkflowStepRowOrder reference
        data for the Master Mix tab, from MASTERMIX_DATA above.

        StepRow (reagent) rows are shared/reused by name across workflows
        and steps — e.g. "NF H2O" is only created once, then linked to
        each step that uses it (with that step's own volume) through a
        separate WorkflowStepRowOrder row.
        """
        from library.models import WorkflowType, WorkflowTypeStep, StepRow, WorkflowStepRowOrder

        self.stdout.write("\n[Master Mix Steps]")

        for workflow_name, steps in MASTERMIX_DATA.items():
            try:
                workflow_type = WorkflowType.objects.get(workflowType=workflow_name)
            except WorkflowType.DoesNotExist:
                self.stdout.write(
                    self.style.WARNING(
                        f"  ⚠  WorkflowType '{workflow_name}' not found — "
                        f"add it to WORKFLOW_TYPES first. Skipping its master mix data."
                    )
                )
                continue

            for step_entry in steps:
                step, created = WorkflowTypeStep.objects.get_or_create(
                    workflowType=workflow_type,
                    stepName=step_entry["stepName"],
                    defaults={
                        "sort_order": step_entry.get("sort_order", 0),
                        "is_stopping_point": step_entry.get("is_stopping_point", False),
                    },
                )
                if not created:
                    # keep sort_order / stopping-point flag in sync on re-runs
                    step.sort_order = step_entry.get("sort_order", step.sort_order)
                    step.is_stopping_point = step_entry.get("is_stopping_point", step.is_stopping_point)
                    step.save(update_fields=["sort_order", "is_stopping_point"])

                status = "created" if created else "exists "
                self._log(status, f"{workflow_name} → {step_entry['stepName']}")

                for row_sort, row_entry in enumerate(step_entry["rows"], start=10):
                    step_row, _ = StepRow.objects.get_or_create(
                        stepRowName=row_entry["name"],
                    )

                    link, link_created = WorkflowStepRowOrder.objects.get_or_create(
                        step=step,
                        step_row=step_row,
                        defaults={
                            "sort_order": row_sort,
                            "volumePerRxn": row_entry["volume_per_rxn"],
                            "constantOfMM": row_entry.get("constant", 1),
                            "extra_reactions": row_entry.get("extra", 0),
                        },
                    )
                    if not link_created:
                        link.sort_order = row_sort
                        link.volumePerRxn = row_entry["volume_per_rxn"]
                        link.constantOfMM = row_entry.get("constant", 1)
                        link.extra_reactions = row_entry.get("extra", 0)
                        link.save(update_fields=[
                            "sort_order", "volumePerRxn", "constantOfMM", "extra_reactions",
                        ])

                    link_status = "created" if link_created else "exists "
                    self._log(link_status, f"    · {row_entry['name']}")

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