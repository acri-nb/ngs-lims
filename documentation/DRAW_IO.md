# ERD Reference — NGS-LIMS

The Entity Relationship Diagram is maintained in `ngs_lims.drawio` and serves as the primary design reference for the database schema. It documents all models, their fields, and the relationships between them.

The diagram must be kept in sync with the codebase. Any change to a model, adding a field, removing one, changing a FK target, requires a corresponding update to the diagram before the change is merged.

---

## Reading the diagram

Each table in the diagram represents a Django model. The table name maps directly to the model class. Each row inside a table is a field.

```
SAMPLE
------
SampleID       PK
SampleName     str
CaseID         FK -> Case
SpecimenTypeID FK -> SpecimenType
NucleicType    str
Concentration  float
Volume         float
DateReceived   date
```

### Field notation

| Label | Meaning |
|---|---|
| PK | Primary key |
| FK | Foreign key (followed by the referenced table) |
| str | CharField or TextField |
| int | IntegerField |
| float | FloatField or DecimalField |
| bool | BooleanField |
| date | DateField or DateTimeField |

---

## Schema overview

The diagram is divided into phases reflecting the planned evolution of the system.

### Phase 1: Samples and Logistics (current)

The active, fully implemented section. Covers the complete sample lifecycle from intake to QC and the supporting logistics models.

**Samples app**: client, project, case, specimen type, sample

**QC app**: QC batch, batch-sample assignment, per-sample QC measurements

**Inventory app**: product catalogue, supplier, receipt, stock (inventory)

**Locations app**: storage units, temperature logs

### Phase 2: Library Preparation (planned)

Reserved for library prep workflows. Structure is not yet finalised.

### Phase 3: Sequencing (planned)

Reserved for sequencing run tracking. Structure is not yet finalised.

---

## Relationships

### Core sample hierarchy

```
CLIENT
  └── PROJECT (one client, many projects)
        └── CASE (one project, many cases)
              └── SAMPLE (one case, many samples)
```

### QC batching (many-to-many via junction table)

```
SAMPLE_QC_BATCH ──── BATCH_SAMPLE ──── SAMPLE
```

`BATCH_SAMPLE` is the junction table. It allows a batch to contain multiple samples and makes it possible to track per-sample QC results independently.

### Inventory chain

```
SUPPLIER ──── PRODUCT_SUPPLIER ──── PRODUCT
                                       │
                               INVENTORY_RECEIPT
                                       │
                                   INVENTORY
                                       │
                                   LOCATION
```

`PRODUCT_SUPPLIER` is a junction table allowing many suppliers per product and many products per supplier. `INVENTORY_RECEIPT` captures the lot-level receipt event. `INVENTORY` is the current stock entry derived from a receipt.

---

## Color coding

Each Django app has an assigned color in the diagram. This grouping must be maintained when adding new models. When introducing a new Django app, assign it a distinct color.

---

## Naming conventions

**Models**: singular noun: `Client`, `Project`, `Sample`, `Product`

**Primary keys**: `<ModelName>ID`: `ClientID`, `SampleID`, `ProductID`

**Foreign keys**: name of the referenced model's PK: `ProjectID`, `SupplierID`

**Relationship labels**: short verb: `has`, `contains`, `yields`, `stores`, `groups`

---

## Relationship Notation
 
Connectors use crow's foot notation to indicate cardinality on each end of a relationship.
 
| Symbol | Meaning |
|---|---|
| `\|\|` (two lines) | Exactly one |
| `o<` (circle + crow's foot) | Zero or many |
| `\|<` (line + crow's foot) | One or many |
| `o\|` (circle + line) | Zero or one |
 
 
For an example look at the relation of client to case:
The double line on the CLIENT side means "exactly one client". The circle and crow's foot on the CASE side means "zero or many cases". Read together: one client has zero or many cases.
 
The label on the connector (`has`, `contains`, `yields`, etc.) describes the relationship from the left or parent side.


## Adding a new model

**Design first.** Sketch the model in the ERD before writing any code. Review the field types, FK targets, and cardinality of relationships. This catches normalization issues before they are baked into a migration.

1. Add the table to the ERD in the correct app color section.
2. Define all fields with their type notation.
3. Draw and label connectors to related tables.
4. Implement the Django model.
5. Generate and review the migration (`makemigrations`, then inspect the file).
6. Commit the code change and the updated `.drawio` file in the same PR.

---

## Adding a field to an existing model

1. Add the field row to the table in the diagram.
2. If the field is a FK, add the connector.
3. Update the Django model.
4. Generate and review the migration.
5. Update this document if the field affects a documented workflow.

--- 

## Consistency checklist

Before merging any database-related change:

- Django model and diagram are in agreement
- Migration is generated and reviewed for unintended side effects
- FKs use the correct `on_delete` behaviour (`PROTECT` for audit-critical refs, `CASCADE` for junction rows)
- New models are placed in the correct color section
- Relationship labels are present and accurate