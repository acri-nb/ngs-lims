# TODO / Loose Ends

Flat checklist, grouped loosely by category. To add: drop a new `-` line wherever it fits. To remove: delete the line. Move a line to `## Done` instead of deleting if you want a record of it.

## Bugs

- If you dont have a RIN and DV200 it crashes the calculation

## SetUp

- Make the acri seed_db personalized. (Rack, New index or workflows, accounts )
- PDF workflow sheets in admin

## Not Implemented (bigger features, missing entirely, Talk with the lab members to implement these feature and what they would want)

- Sequencing: make it so you can put multiple LibraryQC into a Sequencing (LibraryQC -> ISeq-> Novaseq) *Future Promethion?
- Pooling 
- Rebalancing
- Controls: no model/storage for controls at all
- Client portal: outdated, needs refresh if clients are actually using it

## Admin / Ease of Editing

- Expose admin-style editing outside of `/admin` (currently only Django admin), sidebar entry, but gate it behind `login_required`/admin check
- `admin.py` (or `seed_db`) helper for adding new library indexes more easily
- Easier account creation/staging flow (Eric OK'd doing this in-office for now)
- Easier way to link clients and accounts together

## Data Quality / Validation

- General warning/validation overhaul across all inputs
- Confirmation warning before changing a batch or sample, to avoid mistakes
- Mark required fields clearly on all input forms
- Add a usual duration for a product for the expiration date to be automatique

## UX / Usability

- Make sampleQC failure reasons clearer on hover (why it failed(Jessica's recommendation))
- Merge overlapping app functionality into one place (sample detail page) instead of scattered across apps
- Kanban board to track batches and see where they are in the pipeline?
- Make the dashboard actually useful, not just decorative
- Audit trail easier to find (who changed what, when)
- Sortable table headers + better spreadsheet-like behavior generally
- More breadcrumbs to make navigation between steps easier
- Make navigation more clickable/discoverable overall
- Sidebar collapse *hadrien (tried once, was buggy, revisit)

## Docs

- Keep documentation updated as things change
- Write a doc/addon explaining how to add stuff to Django admin (including tables) and to the apps in general

## Other / Ideas

- Update Platewell for when sequencing is done
- Seed DB with ACRI products and suppliers
- Seed DB + QC presets together
- Make controls more robust/useful (once implemented)

## Done

<!-- move completed items here -->