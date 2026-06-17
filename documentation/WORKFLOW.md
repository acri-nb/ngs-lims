# NGS-LIMS Workflow Guide

This document describes the standard day-to-day workflows in the LIMS from the perspective of a lab operator. It covers the full lifecycle of a sequencing project: from project creation, through sample intake and QC, to inventory and storage management.

---

## Overview

The LIMS is organized around four functional areas:

- **Samples**: clients, projects, cases, specimens, and sample intake
- **QC**: batching samples and recording QC measurements
- **Inventory**: reagent receipts, stock levels, and adjustments
- **Locations**: physical storage units and temperature logging

A typical project follows this path:

```
Create Project -> Import Samples -> Assign to QC Batches -> Record QC Results
```

---

## 1. Creating a Project

Before any samples can be entered, a project must exist and be linked to a client.

### 1.1 Create or confirm the client

Navigate to **Clients** and look whether the submitting researcher. If not, click **New Client** and fill in:

- Client name (the researcher)
- Organisation name

### 1.2 Create the project

Navigate to **Projects > New Project** and fill in:

- **Project name**: must be unique across the system; this name appears in all generated identifiers (batch names, etc.)
- **Client**: select the client created above
- **Sequencing type**: e.g. WGS, DNA, RNA...

Once saved, the project is ready to receive samples.

---

## 2. Sample Import

Samples are entered in bulk via a CSV import. Individual samples can also be added one at a time through the manual add form, but the import is the standard path for most intakes.

### 2.1 Download the import template

Navigate to **Samples > Import** and click **Download Template**. This produces a CSV file with the following columns:

| Column | Description |
|---|---|
| `CaseID` | Identifier for the patient or experimental case |
| `SpecimenType` | Tissue or material type (FFPE, Cells, smallEVs...) |
| `NucleidType` | `DNA` or `RNA` |
| `Concentration(ng/ul)` | Measured concentration at reception |
| `Volume(uL)` | Volume received in microlitres |

### 2.2 Fill the template

Each row represents one sample. The `CaseID` does not need to pre-exist, the system will create a Case record automatically if the name is new under the selected project. The `SpecimenType` likewise creates a new `SpecimenType` record on first use, but their are initialized SpecimenTypes in the Lab.

A single case can span multiple rows if multiple specimen types or nucleic acid types were received.

### 2.3 Run the import

On the **Sample Import** page:

1. Select the target project from the dropdown
2. Upload the filled CSV file
3. Click **Preview** for the system validates headers and each row, listing any errors before committing
4. If the preview is clean, click **Import** to commit all rows

Each imported sample receives an auto-generated name in the format:

```
CaseName-SpecimenType-SampleType-XXXXX
```

Where `XXXXX` is the sample's primary key zero-padded to five uppercase hex digits (`MCF10A-Cells-RNA-000C8`).

### 2.4 Manual single-sample entry

For one-off additions, use **Samples > Add Sample**. The form requires selecting a project, entering a case name, specimen type, sample type, and optionally concentration, volume, receiving condition, and location. Cases and specimen types are created automatically if they do not exist.

---

## 3. QC Batching

Once samples are imported, they are grouped into QC batches for processing. This is managed through the **batch board**, a drag-and-drop interface per project.

### 3.1 Navigate to the batch board

Go to **QC > Assign** and select the target project. This opens the batch board, which shows:

- All unassigned samples for the project on the left
- Existing batches and their assigned samples on the right

### 3.2 Create a batch

On the batch board, click **New Batch** and provide:

- **Date**: the date the batch will be processed
- **Batch type**: `DNA` or `RNA` (determines which QC metrics are expected)

The batch name is auto-generated as:

```
ProjectName-BATCH-XXXX
```

Where `XXXX` is the batch primary key in four-digit uppercase hex.

### 3.3 Assign samples to batches

Drag samples from the unassigned pool into a batch. A sample can only appear in one batch at a time. When the board reflects the intended groupings, click **Save** to commit. Every save is recorded in the audit log with a diff of what was added, removed, or moved.

### 3.4 View the audit log

The audit log for a project is accessible via the batch board. It lists every save action with the performing user, timestamp, and a JSON diff of the changes.

---

## 4. Recording QC Results

Each batch has a detail page where QC measurements are entered per sample.

### 4.1 Open the batch

Navigate to **QC** and select the batch from the list. The batch detail page shows all samples in the batch with their current QC status (initially `Pending`).

### 4.2 Enter measurements

For each sample, enter the relevant metrics:

**DNA samples:**

- `Qubit (ng/ul)` required
- `Nanodrop 260/280` required
- `Nanodrop 260/230` required

**RNA samples:**

- `Qubit (ng/ul)` required
- `RIN` optional if DV200 is provided
- `DV200` optional if RIN is provided

### 4.3 QC status calculation

Status is calculated automatically on save and cannot be set manually

### 4.4 Bulk import via CSV

If results are exported from an instrument (Qubit reader), they can be imported directly. From the batch detail page, click **Import Results** and upload a CSV matching the expected columns. This populates the fields for each sample and recalculates statuses.

---

## 5. Inventory Management

The inventory module tracks reagents and consumables from receipt to consumption.

### 5.1 Log a new receipt

When a shipment arrives, navigate to **Inventory > Log Receipt** and fill in:

- **Product**: select from the existing product catalogue
- **Supplier**: select the supplier for this specific delivery
- **Lot number**: from the product packaging
- **Receiving condition**: Frozen, On Ice, or Room-Temperature
- **Location**: the storage unit where the stock will be placed
- **Quantity received** and **unit** (12 tubes, 500 mL, etc... )
- **Date received** and **expiration date** (if applicable)
- **Notes**:optional free-text remarks

Saving the receipt automatically creates an `Inventory` record linking the stock to the receipt (lot), product, and location. This provides full lot traceability.

### 5.2 Adjust stock

To update the quantity on hand after consumption or waste, navigate to the inventory dashboard and click **Adjust** next to the relevant stock entry. Enter the new quantity on hand and save.

### 5.3 Inventory dashboard

The dashboard shows current stock levels for all products, grouped by location. Expired lots are flagged. From here you can drill into a product's receipt history and current stock across all locations.

---

## 6. Location and Temperature Logging

### 6.1 Storage locations

Physical storage units (freezers, fridges, cabinets) are managed under **Locations**. Each location has a name and a storage type (Room-Temperature, Fridge 4C, Freezer -20C, Freezer -80C). Locations are referenced by both the sample and inventory modules.

### 6.2 Temperature logs

To record a daily temperature check, navigate to **Locations**, select the unit, and add a temperature log entry with:

- Temperature reading
- Humidity reading (if applicable)
- Date and time
- Logged by (auto-set to the current user)

The location history page shows a chart of temperature readings over time for a given storage unit.

---

## 7. Researcher Portal

Researchers with a portal account (i.e. users with a `UserProfile` linked to a `Client`) log in and land on a restricted view that shows only their own projects and the samples and QC results within those projects. They cannot access other clients' data, inventory, or location management.

Lab staff accounts have no `UserProfile` and are routed to the full LIMS dashboard on login.