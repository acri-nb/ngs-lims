import json
from datetime import date

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.db import transaction
from django.utils import timezone

from .models import (
    LibraryPrepBatch,
    LibraryPrepBatchAuditLog,
    LibraryPrepSample,
    WorkflowType,
    PrepAction,
)
from locations.models import Rack, Plate, PlateWell, PlateFormat
from samples.models import Project
from qc.models import SampleQC


ROWS = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']
COLS = [f'{c:02d}' for c in range(1, 7)]   # 01–06  →  48 wells


def libprep_list(request):
    batches = LibraryPrepBatch.objects.select_related(
        'project', 'project__client', 'workflowType', 'plate'
    ).order_by('-datePrepped')

    batch_data = []
    for batch in batches:
        samples  = batch.samples.all()
        total    = samples.count()
        prepped  = samples.filter(prepAction=PrepAction.PREP).count()
        skipped  = samples.filter(prepAction=PrepAction.SKIP).count()
        requeued = samples.filter(prepAction=PrepAction.REQUEUE).count()
        pending  = total - prepped - skipped - requeued

        batch_data.append({
            'batch':    batch,
            'total':    total,
            'prepped':  prepped,
            'skipped':  skipped,
            'requeued': requeued,
            'pending':  pending,
        })

    return render(request, 'library/libprep_list.html', {'batch_data': batch_data})


def libprep_detail(request, batch_id):
    batch = get_object_or_404(
        LibraryPrepBatch.objects.select_related(
            'project', 'project__client', 'workflowType', 'plate',
            'plate__rack', 'plate__rack__location',
        ),
        pk=batch_id,
    )

    samples_qs = batch.samples.select_related(
        'plateWell', 'sampleQC', 'sampleQC__sample', 'libraryIndex',
    )
    sample_map = {}
    for s in samples_qs:
        if s.plateWell:
            sample_map[s.plateWell.well_position] = s

    grid = []
    for row in ROWS:
        row_cells = []
        for col in COLS:
            pos    = f'{row}{col}'
            sample = sample_map.get(pos)
            row_cells.append({
                'position':   pos,
                'sample':     sample,
                'occupied':   sample is not None,
                'is_control': (
                    sample.plateWell.well_type == 'control'
                    if sample and sample.plateWell else False
                ),
            })
        grid.append({'row_letter': row, 'cells': row_cells})

    total   = len(sample_map)
    prepped = sum(1 for s in sample_map.values() if s.prepAction == PrepAction.PREP)
    pending = sum(
        1 for s in sample_map.values()
        if s.prepAction not in (PrepAction.PREP, PrepAction.SKIP, PrepAction.REQUEUE)
    )

    # Recent audit log for this batch
    audit_log = batch.audit_logs.select_related('changed_by').order_by('-changed_at')[:20]

    return render(request, 'library/libprep_detail.html', {
        'batch':     batch,
        'grid':      grid,
        'cols':      COLS,
        'total':     total,
        'prepped':   prepped,
        'pending':   pending,
        'audit_log': audit_log,
    })


def libprep_project_list(request):
    """
    Project selection page for new batch creation.
    Shows SampleQC status breakdown per project.
    """
    projects = Project.objects.select_related('client').order_by('project_name')

    project_data = []
    for project in projects:

        samples   = project.samples.all()
        dna_count = samples.filter(sample_type='DNA').count()
        rna_count = samples.filter(sample_type='RNA').count()

        sample_qcs = SampleQC.objects.filter(sample__project=project)
        qc_total   = sample_qcs.count()
        qc_pass    = sample_qcs.filter(qc_status=SampleQC.PASS).count()
        qc_caution = sample_qcs.filter(qc_status=SampleQC.CAUTION).count()
        qc_fail    = sample_qcs.filter(qc_status=SampleQC.FAIL).count()
        qc_pending = sample_qcs.filter(qc_status=SampleQC.PENDING).count()

        def pct(n):
            return round(n / qc_total * 100) if qc_total else 0

        existing_batches = LibraryPrepBatch.objects.filter(project=project).count()

        project_data.append({
            'project':          project,
            'dna_count':        dna_count,
            'rna_count':        rna_count,
            'qc_total':         qc_total,
            'qc_pass':          qc_pass,
            'qc_caution':       qc_caution,
            'qc_fail':          qc_fail,
            'qc_pending':       qc_pending,
            'pct_pass':         pct(qc_pass),
            'pct_caution':      pct(qc_caution),
            'pct_fail':         pct(qc_fail),
            'pct_pending':      pct(qc_pending),
            'existing_batches': existing_batches,
        })

    return render(request, 'library/libprep_projects.html', {
        'project_data': project_data,
    })


def libprep_new_batch(request, project_id):
    """
    GET  — render the drag-and-drop plate builder.
           Left sidebar: SampleQC records for this project, sorted by status.
           Location modal: all racks, grouped by location.

    POST — validate inputs, then atomically:
             1. Generate batch name  (PROJECT-Library-4HEX)
             2. Create Plate         (locations.Plate)
             3. Assign to Rack slot
             4. Create LibraryPrepBatch
             5. Create LibraryPrepSample rows (no PlateWell yet — filled later)
             6. Write initial audit log entry
    """
    project = get_object_or_404(
        Project.objects.select_related('client'),
        pk=project_id,
    )

    if request.method == 'POST':
        return _save_new_batch(request, project)

    from django.db.models import Max

    latest_ids = (
        SampleQC.objects
        .filter(sample__project=project)
        .values('sample')
        .annotate(latest=Max('created_at'))
        .values_list('latest', flat=True)
    )

    sample_qcs = (
        SampleQC.objects
        .filter(sample__project=project, created_at__in=latest_ids)
        .select_related('sample')
        .order_by('sample__sample_name')
    )

    qc_pass    = [q for q in sample_qcs if q.qc_status == SampleQC.PASS]
    qc_caution = [q for q in sample_qcs if q.qc_status == SampleQC.CAUTION]
    qc_fail    = [q for q in sample_qcs if q.qc_status == SampleQC.FAIL]
    qc_pending = [q for q in sample_qcs if q.qc_status == SampleQC.PENDING]

    workflow_types = WorkflowType.objects.order_by('workflowType')

    # All racks with their location — template uses {% regroup racks by location %}
    racks = Rack.objects.select_related('location').order_by(
        'location__locationName', 'rack_name'
    )

    return render(request, 'library/libprep_newbatch.html', {
        'project':        project,
        'qc_pass':        qc_pass,
        'qc_caution':     qc_caution,
        'qc_fail':        qc_fail,
        'qc_pending':     qc_pending,
        'workflow_types': workflow_types,
        'racks':          racks,
        'rows':           ROWS,
        'cols':           COLS,
        'today':          date.today().isoformat(),
    })


def _save_new_batch(request, project):
    """
    Atomically creates:
      - Plate (locations.Plate) with rack assignment
      - LibraryPrepBatch linked to that Plate
      - LibraryPrepSample rows (one per placed well)
      - Initial LibraryPrepBatchAuditLog entry

    POST fields expected:
        workflow_type_id  – WorkflowType pk
        date_prepped      – YYYY-MM-DD
        placements        – JSON: { wellPos: {qcId, sampleName, status, isControl}, … }
        notes             – optional free text
        rack_id           – Rack pk (from location modal)
        rack_slot         – slot string e.g. "A1T" or "B2B"

    Batch naming convention:
        {project_name}-Library-{4-digit uppercase hex counter}
        Example: ACME2024-Library-003F
        The counter is global across all LibraryPrepBatch rows.
    """
    workflow_id    = request.POST.get('workflow_type_id', '').strip()
    date_str       = request.POST.get('date_prepped', '').strip()
    placements_raw = request.POST.get('placements', '').strip()
    notes          = request.POST.get('notes', '').strip()
    rack_id        = request.POST.get('rack_id', '').strip()
    rack_slot      = request.POST.get('rack_slot', '').strip()

    errors = []

    if not workflow_id:
        errors.append('Please select a Workflow Type.')
    if not date_str:
        errors.append('Please enter a Date Prepped.')
    if not rack_id:
        errors.append('Please select a rack location.')
    if not rack_slot:
        errors.append('Please select a rack slot.')

    try:
        placements = json.loads(placements_raw) if placements_raw else {}
    except (json.JSONDecodeError, ValueError):
        placements = {}

    # Strip empty / null entries
    placements = {k: v for k, v in placements.items() if v and v.get('qcId')}

    if not placements:
        errors.append('No samples placed on the plate — drag at least one sample before saving.')

    if errors:
        for e in errors:
            messages.error(request, e)
        return redirect('libprep-new-batch', project_id=project.pk)

    workflow = get_object_or_404(WorkflowType, pk=workflow_id)
    rack     = get_object_or_404(Rack.objects.select_related('location'), pk=rack_id)

    try:
        prepped_date = date.fromisoformat(date_str)
    except ValueError:
        messages.error(request, 'Invalid date format.')
        return redirect('libprep-new-batch', project_id=project.pk)

    # rack_slot from the template is e.g. "A1T" or "B2B"
    # We store just the base slot (e.g. "A1") in Plate.rack_location and
    # append T/B to the plate name to differentiate top/bottom stacking.
    # Extract the base (all chars except last) and the side (last char).
    slot_base = rack_slot[:-1] if len(rack_slot) > 2 else rack_slot
    slot_side = rack_slot[-1].upper() if len(rack_slot) > 2 else ''

    existing_plate = Plate.objects.filter(rack=rack, rack_location=rack_slot).first()
    if existing_plate:
        messages.error(
            request,
            f'Rack slot {rack_slot} in {rack.rack_name} is already occupied '
            f'by plate "{existing_plate.plate_name}". Please choose a different slot.'
        )
        return redirect('libprep-new-batch', project_id=project.pk)

    # Convention: {ProjectName}-Library-{4-digit hex, global counter}
    # The counter is simply the next LibraryPrepBatch pk expressed in hex.
    # Since we don't know the pk yet, we use the current total count + 1
    # and pad to 4 hex digits.
    total_batches = LibraryPrepBatch.objects.count()
    hex_suffix    = format(total_batches + 1, '04X')        # e.g. "003F"
    batch_name    = f"{project.project_name}-Library-{hex_suffix}"

    with transaction.atomic():

        # 5a. Create the Plate in the chosen rack slot
        plate = Plate.objects.create(
            location      = rack.location,
            rack          = rack,
            rack_location = rack_slot,          # e.g. "A1T" — full slot string
            plate_name    = batch_name,
            plate_format  = PlateFormat.F_96,   # physical plate is 96-well; batch uses 48
            notes         = f'Library prep plate — {workflow.workflowType}',
            created_by    = request.user,
        )

        # Create all PlateWell objects for this plate
        plate_wells = []

        for row in ROWS:
            for col in COLS:
                plate_wells.append(
                    PlateWell(
                        plate=plate,
                        well_position=f"{row}{col}",
                        well_type="empty",  
                        created_by=request.user,
                    )
                )

        PlateWell.objects.bulk_create(plate_wells)

        # 5b. Create the LibraryPrepBatch
        sample_count = sum(
            1 for v in placements.values() if not v.get('isControl', False)
        )
        control_count = sum(
            1 for v in placements.values() if v.get('isControl', False)
        )

        batch = LibraryPrepBatch.objects.create(
            project      = project,
            plate        = plate,
            workflowType = workflow,
            datePrepped  = prepped_date,
            batch_name   = batch_name,
            max_samples  = sample_count,
            notes        = notes,
            createdBy    = request.user,
        )

        # 5c. Create LibraryPrepSample rows
        # PlateWell is intentionally left null — filled when the batch is
        # fully prepared and the physical well positions are confirmed.
        created = 0
        placement_summary = []   # for the audit log

        for well_pos, info in placements.items():
            qc_id      = info.get('qcId')
            is_control = info.get('isControl', False)
            status     = info.get('status', '')

            source_qc = None
            conc      = None

            if is_control:
                # Positive / negative controls: no SampleQC record
                control_label = info.get('sampleName', 'Control')
                placement_summary.append(
                    f'{well_pos}: {control_label} [control]'
                )
            else:
                try:
                    source_qc = SampleQC.objects.select_related('sample').get(pk=int(qc_id))
                    conc = source_qc.qubit_nm    # ng/µL from Qubit reading
                    placement_summary.append(
                        f'{well_pos}: {source_qc.sample.sample_name} [{status}]'
                    )
                except (SampleQC.DoesNotExist, ValueError, TypeError):
                    source_qc = None
                    placement_summary.append(f'{well_pos}: unknown sample [error]')

            vol_sample, vol_diluent, actual_input, speedvac = _calc_volumes(
                conc,
                workflow.target_input_ng,
                workflow.target_volume_ul,
            )

            plate_well = PlateWell.objects.get(
                plate=plate,
                well_position=well_pos,
            )

            if is_control:
                plate_well.well_type = "control"
                plate_well.sample = None
            else:
                plate_well.well_type = "library"
                plate_well.sample = source_qc.sample if source_qc else None

            plate_well.volume_ul = vol_sample
            plate_well.concentration_nm = conc
            plate_well.created_by = request.user
            plate_well.save()

            LibraryPrepSample.objects.create(
                libPrepBatch=batch,
                sampleQC=source_qc,
                plateWell=plate_well,
                concentrationInput=conc,
                volumeSample_ul=vol_sample,
                volumeDiluent_ul=vol_diluent,
                actual_Input_ng=actual_input,
                speedVacRequired=speedvac,
                prepAction=PrepAction.PREP,
                createdBy=request.user,
            )
            created += 1

        # 5d. Write initial audit log entry
        LibraryPrepBatchAuditLog.objects.create(
            batch      = batch,
            changed_by = request.user,
            action     = LibraryPrepBatchAuditLog.ACTION_CREATED,
            detail     = (
                f'Batch "{batch_name}" created.\n'
                f'Workflow: {workflow.workflowType}\n'
                f'Date prepped: {prepped_date}\n'
                f'Plate: {plate.plate_name} → {rack.rack_name} slot {rack_slot} '
                f'({rack.location.locationName})\n'
                f'Wells placed ({created}):\n'
                + '\n'.join(f'  {line}' for line in placement_summary)
            ),
        )

    messages.success(
        request,
        f'Batch "{batch_name}" created — {created} well{"s" if created != 1 else ""} '
        f'placed on plate {plate.plate_name} in {rack.rack_name} slot {rack_slot}.'
    )
    return redirect('libprep-detail', batch_id=batch.pk)


def _calc_volumes(conc, target_ng, start_vol):
    """
    Returns (vol_sample_ul, vol_diluent_ul, actual_input_ng, speedvac_required).
    All None / False if concentration is missing or zero.

    Cases:
      - conc is sufficient: dilute into start_vol with diluent
      - conc too low (vol_needed > start_vol): flag SpeedVac, use full start_vol
    """
    if not conc or conc <= 0:
        return None, None, None, False

    vol_needed = round(target_ng / conc, 2)

    if vol_needed <= start_vol:
        return (
            vol_needed,
            round(start_vol - vol_needed, 2),
            round(target_ng, 2),
            False,
        )
    else:
        # Can't reach target mass in start_vol — take all the sample, flag SpeedVac
        actual = round(conc * start_vol, 2)
        return (
            round(start_vol, 2),
            0.0,
            actual,
            True,
        )