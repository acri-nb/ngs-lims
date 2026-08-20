# Adding Things to NGS-LIMS

A guide for adding new reference data (workflow types, index kits, specimen types, etc.) and understanding how Samples and Batches get created day-to-day. Written for whoever picks this project up next.

---

## 1. Two kinds of "adding things"

It helps to keep these separate:

- **Reference / lookup data**: things like `SpecimenType`, `WorkflowType`, `IndexKit`, `Supplier`, `QCGatePreset`. These are configured once (or occasionally), and everything else in the app points at them. You add these through **Django Admin**, and ideally also add them to **`seed_db`** so a fresh database comes back with the same setup.
- **Day-to-day records**: `Sample`, `SampleQCBatch`, `LibraryPrepBatch`, etc. These get created constantly by lab members through the normal app pages, not the admin. Section 3 covers how that actually happens under the hood.

---

## 2. Adding reference data

### 2a. Through Django Admin

Every app registers its models in `admin.py` (`samples/admin.py`, `qc/admin.py`, `library/admin.py`, `inventory/admin.py`, `locations/admin.py`). Log in as a superuser at `/admin/` and the model will be listed under its app.

Quick reference of where each reference table lives:

| Thing | Model | App |
|---|---|---|
| Specimen type (FFPE, Cells, ...) | `SpecimenType` | `samples` |
| Client / researcher | `Client` | `samples` |
| Supplier | `Supplier` | `inventory` |
| Product (+ which suppliers carry it) | `Product`, `ProductSupplier` | `inventory` |
| Storage location (freezer, fridge, room) | `Location` | `locations` |
| Workflow type (TotalRNA, DNA PCR-Free, ...) | `WorkflowType` | `library` |
| Workflow's master mix steps/reagents | `WorkflowTypeStep`, `StepRow`, `WorkflowStepRowOrder` | `library` |
| Index kit + physical wells | `IndexKit`, `LibraryIndex` | `library` |
| QC gate preset (reusable threshold sets) | `QCGatePreset` | `qc` |

Most of these are plain `ModelAdmin` registrations, add a row, save, done. `WorkflowType` is the one with real structure behind it (see below).

### 2b. Adding a new Workflow Type

This is the most involved piece of reference data, so it's worth spelling out. A `WorkflowType` (e.g. "TotalRNA", "DNA PCR-Free") My best advice is to be in close proximity with the lab memebers when you initialize this new workflow with an excel:

1. **`WorkflowType` itself**, sample type (DNA/RNA), QC method, PCR/no-PCR, target input ng, fragment size gates, etc. All the per-workflow settings live as fields directly on this model (see `library/models.py`).
2. **`WorkflowTypeStep`**: the ordered steps of the protocol (e.g. "Fragmentation", "Adapter Ligation", "PCR Amplification"). Each step can be marked `is_stopping_point` if it's safe to pause the protocol there.
3. **`StepRow` + `WorkflowStepRowOrder`**: the reagents/master mix rows for each step, with a volume-per-reaction and a row type (`Fixed / Header`, `Per Reaction (×n)`, or `Ethanol Dilution Pair`). This is what generates the master mix sheet.
4. **`IndexKit`**: link the workflow to whichever index kit(s) it uses, via `IndexKit.workflowTypes`.

(Practically I would be in contact with the lab to make an excel sheet for the mastermix sheet and the workflow variables) then: create the `WorkflowType` first, then its `WorkflowTypeStep`s, then the `StepRow`/`WorkflowStepRowOrder` for each step. All of this can be done in Django Admin, `WorkflowTypeStep` and `WorkflowStepRowOrder` are ordinary models, not anything more exotic.

### 2c. Adding it to `seed_db`

`seed_db.py` (`samples/management/commands/seed_db.py`) exists so a freshly-migrated database can be brought back to a known state for the new lab machine, disaster recovery, or a new dev environment. It won't happen automatically just because you added something in Admin; **you need to add it to `seed_db.py` too** if you want it to survive a `python manage.py seed_db` run elsewhere.

The pattern is consistent everywhere in the file:

1. A plain Python list or dict near the top of the file holds the data (`SPECIMEN_TYPES`, `CLIENTS`, `SUPPLIERS`, `WORKFLOW_TYPES`, ...).
2. A `_seed_x()` method loops over it and calls `get_or_create()`, so re-running the command is always safe, existing rows are left alone and logged as `[exists]`, new ones are logged as `[created]`.

Simplest example (`SpecimenType` just a name):
```python
SPECIMEN_TYPES = [
    "Bl",
    "FFPE",
    "Cells",
    # add new specimen types here
]
```
```python
def _seed_specimen_types(self):
    from samples.models import SpecimenType
    for name in SPECIMEN_TYPES:
        obj, created = SpecimenType.objects.get_or_create(specimen_type=name)
```

Slightly richer example (`Client`: a dict of fields):
```python
CLIENTS = [
    {"client_name": "eric", "organisation_name": "ACRI"},
    # add new clients here
]
```
```python
def _seed_clients(self):
    from samples.models import Client
    for entry in CLIENTS:
        obj, created = Client.objects.get_or_create(
            client_name=entry["client_name"],
            defaults={"organisation_name": entry["organisation_name"]},
        )
```

To add a new kind of reference data:
1. Add your list/dict near the top of the file, in the same style as the existing ones (there are `# ══` banner comments marking each section, follow that formatting for ease of use).
2. Write a `_seed_yourthing()` method following the `get_or_create` pattern above.
3. Call it from `Command.handle()`, in the order that respects foreign keys (e.g. `Client` must exist before `Case`, `WorkflowType` before `IndexKit`).
4. If it should be wiped by `--reset`, add the delete call to `_reset()` too, in reverse dependency order.

`WORKFLOW_TYPES` (around line 252) is the most complex existing example, worth reading through if your new data has its own foreign-key relationships to set up, not just flat fields.

**Where to actually add lines:** several lists already have a marked spot, e.g. `CLIENTS` has a `# ── Add your clients below ──` block. Look for that pattern before adding at the end of a list.



### 2d. Adding a new Index Kit + its Library Indexes
 
Index kits are the one exception to "just add a Python list" a single kit can have hundreds of wells, so they're seeded from a **JSON fixture** (`samples/fixtures/library_index_seed.json`), not an inline list in `seed_db.py`. There are two things to update: the fixture (the actual well data) and `INDEX_KIT_WORKFLOW_MAP` (which workflow(s) the kit belongs to).
 
**1. Add the kit to the fixture.** Each entry is one kit, with one or more plate sets, each with a list of wells:
 
```json
{
  "kit_name": "ILLMN-DNA-RNA-V4",
  "sets": [
    {
      "set_label": "AV4",
      "wells": [
        {
          "well": "A01",
          "udi_number": "UDP0001",
          "i7Sequence": "GAACTGAGCG",
          "i5Sequence": "CGCTCCACGA"
        },
        {
          "well": "B01",
          "udi_number": "UDP0002",
          "i7Sequence": "AGGTCAGATA",
          "i5Sequence": "TATCTTGTAG"
        }
      ]
    }
  ]
}
```
Add this as a new object in the top-level JSON array in `library_index_seed.json`. `set_label` can be `""` for single-plate kits with no lettered sets. `i5Sequence` can be `""` for kits that don't use a dual index.
 
**2. Map it to its Workflow Type(s)** in `INDEX_KIT_WORKFLOW_MAP` (`seed_db.py`, near line 672) the kit name here must match `kit_name` in the fixture exactly:
 
```python
INDEX_KIT_WORKFLOW_MAP = {
    "ILLMN-DNA-RNA-V2": ["TotalRNA", "DNA PCR Free WGS"],
    "ILLMN-DNA-RNA-V4": ["TotalRNA", "DNA PCR Free WGS"],   # ← new kit added here
    "KAPA-UDI":         ["KAPA HyperPlus DNA"],
    "sRNA-V4":          ["Small RNA"],
}
```
A kit can list one workflow as a bare string (`"KAPA HyperPlus DNA"`) or several as a list, if the physical kit is shared across workflows. **The `WorkflowType`(s) listed must already exist** (via Admin or already seeded) before you run the seed, if not found, that kit is skipped with a warning, not silently dropped, so check the console output.
 
**3. Seed it:**
```bash
python manage.py seed_db
```
This is safe to re-run `IndexKit.objects.get_or_create(name=kit_name)` won't duplicate the kit, and each well is only inserted if its `(plateSet, well)` combination doesn't already exist for that kit, so adding new wells to an existing kit later (e.g. the manufacturer ships a new plate set) is just editing the fixture and re-running.
 
**If you'd rather skip the JSON fixture entirely** and add one kit/well by hand, Django Admin works fine too `IndexKit` first (name + link to its `WorkflowType`(s)), then `LibraryIndex` rows pointing at it (`indexKit`, `plateSet`, `well`, `udi_number`, `i7Sequence`, `i5Sequence`). The fixture approach is really just there because doing hundreds of wells by hand in Admin isn't practical, for a handful of one-off wells, Admin is simpler.


---

## 3. How Samples and Batches actually get created

This is the day-to-day flow lab members use, not the admin. Useful to know if you're changing or extending it.

### 3a. Samples

Chain: **Client → Case → Specimen → Sample**. A `Case` belongs to a `Client`; a `Specimen` belongs to a `Case` and has a `SpecimenType`; a `Sample` belongs to a `Specimen` and a `Project`.

(If you want to add samples with a Terryfox ID, add the SampleName has ACC-1234 and it will work for this lims.)

The "Add Sample" page (`samples/views.py::sample_add`) does all of this in one submit:
- Looks up the `Project` (already exists, chosen from a dropdown).
- `get_or_create`s the `Case` under that project's client, by name, so typing an existing case name reuses it, a new name creates it on the spot.
- `get_or_create`s the `Specimen` under that case + the chosen specimen type.
- Creates the `Sample` itself.

`Sample.sample_name` is auto-generated in `Sample.save()`, it needs the DB-assigned `sample_id` first, so the model saves once to get an ID, builds the name (`CaseName-SpecimenType-SampleType-5HexID`), then saves again with just that field updated. You don't set `sample_name` yourself.

### 3b. QC Batches (Sample QC)

`SampleQCBatch` groups samples for a QC run. These aren't created through a single "add batch" form, they come from the **QC batch board** (`qc/views.py::qc_batch_board` + `qc_save_board`), a drag-and-drop UI where lab members arrange samples into batches for a project.

`qc_save_board` reconciles the whole board state against the DB in one atomic transaction: new batches get created, membership (`BatchSample`) is added/removed to match what's on the board, and importantly a `SampleQC` **PENDING stub** (all metrics null) is created for every (sample, batch) pair so there's immediately a row to fill in results against. Existing `SampleQC` results are never touched or deleted by this, only membership changes.

`SampleQCBatch.batch_name` auto-generates the same way `Sample.sample_name` does, save once for the ID, build `{project_name}-SampleQC-{4-digit hex}`, save again.

### 3c. Library Prep Batches

`LibraryPrepBatch` is one physical plate of library prep. Created from `library/views.py::_save_new_batch` (called from `libprep_new_batch`), which atomically creates:
- A `Plate` (in `locations`) with a rack + slot assignment,
- The `LibraryPrepBatch` itself, linked to that plate,
- One `LibraryPrepSample` per well the lab member placed a sample into,
- An initial `LibraryPrepBatchAuditLog` entry.

Like the other two, `batch_name` auto-generates: `{project_name}-Library-{4-digit hex}`.

### 3d. The general pattern, if you're adding a new batch-like concept

All three follow the same shape, worth keeping if you add a fourth:
- A hex-suffixed, auto-generated name built in `save()` (save once for the ID, then save again with the name).
- Batch-level settings (QC gates, workflow config) live on the batch itself so they can be adjusted per-run without a code change.
- Membership/results go through a junction model (`BatchSample`, `LibraryPrepSample`) rather than a raw M2M, so you have somewhere to hang per-membership data (status, QC values, well position).
- Bulk create/update operations wrap in `transaction.atomic()` so a partial failure doesn't leave a half-created batch behind (see the open TODO about `seed_db` **not** doing this yet, the batch-creation views already do).