import json
from datetime import date

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages

from .models import (
    LibraryPrepBatch,
    LibraryPrepSample,
    WorkflowType,
    PrepAction,
)
from samples.models import Project
from qc.models import SampleQC


# plate grid constants 
ROWS = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']
COLS = [f'{c:02d}' for c in range(1, 7)]   # 01-06 → 48 wells



#  /libprep/
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

    return render(request, 'library/libprep_list.html', {
        'batch_data': batch_data,
    })


#  /libprep/batch/<id>/

def libprep_detail(request, batch_id):
    batch = get_object_or_404(
        LibraryPrepBatch.objects.select_related(
            'project', 'project__client', 'workflowType', 'plate'
        ),
        pk=batch_id,
    )

    samples_qs = batch.samples.select_related(
        'plateWell',
        'sampleQC',
        'sampleQC__sample',
        'libraryIndex',
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

    return render(request, 'library/libprep_detail.html', {
        'batch':   batch,
        'grid':    grid,
        'cols':    COLS,
        'total':   total,
        'prepped': prepped,
        'pending': pending,
    })



#  /libprep/projects/
def libprep_project_list(request):
    """
    Project selection page for new batch creation.
    Stats are based on SampleQC (not LibraryQC) — the sidebar on the
    next page shows which samples have passed SampleQC and are ready
    to be loaded onto a prep plate.
    """
    projects = Project.objects.select_related('client').order_by('project_name')

    project_data = []
    for project in projects:

        samples   = project.samples.all()
        dna_count = samples.filter(sample_type='DNA').count()
        rna_count = samples.filter(sample_type='RNA').count()

        # SampleQC records for samples in this project
        # SampleQC.qc_status uses title-case strings: 'Pass', 'Fail', 'Caution', 'Pending'
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



#  /libprep/newbatch/<project_id>/   GET + POST
def libprep_new_batch(request, project_id):
    """
    GET  — render the drag-and-drop plate builder.
           Left sidebar: SampleQC records for this project, split by status.
           Controls box: positive + negative control draggables (RNA only;
           DNA batches have no controls — enforced on save later).

    POST — validate, create LibraryPrepBatch + LibraryPrepSample rows,
           redirect to batch detail.

    Placement JSON sent by the form:
        {
          "A01": { "qcId": "42",  "sampleName": "…", "status": "pass",     "isControl": false },
          "B06": { "qcId": "pos", "sampleName": "Positive Control", "status": "control", "isControl": true },
          …
        }
    qcId is the SampleQC pk for real samples, or the special strings
    "pos" / "neg" for controls.
    """
    project = get_object_or_404(
        Project.objects.select_related('client'),
        pk=project_id,
    )

    if request.method == 'POST':
        return _save_new_batch(request, project)

    #  GET: build sidebar
    # Pull every SampleQC for samples in this project.
    # Use the most recent QC result per sample (latest created_at).
    from django.db.models import Max

    # Get the latest SampleQC pk per sample
    latest_ids = (
        SampleQC.objects
        .filter(sample__project=project)
        .values('sample')
        .annotate(latest=Max('created_at'))
        .values('sample', 'latest')
    )

    # Build a queryset of the latest QC per sample
    sample_qcs = SampleQC.objects.filter(
        sample__project=project,
        created_at__in=[row['latest'] for row in latest_ids],
    ).select_related('sample').order_by('sample__sample_name')

    qc_pass    = [q for q in sample_qcs if q.qc_status == SampleQC.PASS]
    qc_caution = [q for q in sample_qcs if q.qc_status == SampleQC.CAUTION]
    qc_fail    = [q for q in sample_qcs if q.qc_status == SampleQC.FAIL]
    qc_pending = [q for q in sample_qcs if q.qc_status == SampleQC.PENDING]

    workflow_types = WorkflowType.objects.order_by('workflowType')

    return render(request, 'library/libprep_newbatch.html', {
        'project':        project,
        'qc_pass':        qc_pass,
        'qc_caution':     qc_caution,
        'qc_fail':        qc_fail,
        'qc_pending':     qc_pending,
        'workflow_types': workflow_types,
        'rows':           ROWS,
        'cols':           COLS,
        'today':          date.today().isoformat(),
    })

def _save_new_batch(request, project):
    """
    POST handler for libprep_new_batch.

    Expected POST fields:
        workflow_type_id  – WorkflowType pk
        date_prepped      – YYYY-MM-DD
        placements        – JSON string
        notes             – optional
    """
    workflow_id     = request.POST.get('workflow_type_id', '').strip()
    date_str        = request.POST.get('date_prepped', '').strip()
    placements_raw  = request.POST.get('placements', '').strip()
    notes           = request.POST.get('notes', '').strip()

    # validate inputs 
    errors = []

    if not workflow_id:
        errors.append('Please select a Workflow Type.')
    if not date_str:
        errors.append('Please enter a Date Prepped.')

    try:
        placements = json.loads(placements_raw) if placements_raw else {}
    except (json.JSONDecodeError, ValueError):
        placements = {}

    # Filter out empty/null entries before checking count
    placements = {k: v for k, v in placements.items() if v and v.get('qcId')}

    if not placements:
        errors.append('No samples placed on the plate — drag at least one sample before saving.')

    if errors:
        for e in errors:
            messages.error(request, e)
        return redirect('libprep-new-batch', project_id=project.pk)

    workflow = get_object_or_404(WorkflowType, pk=workflow_id)

    try:
        prepped_date = date.fromisoformat(date_str)
    except ValueError:
        messages.error(request, 'Invalid date format.')
        return redirect('libprep-new-batch', project_id=project.pk)

    # create batch 
    # Count non-control wells
    sample_count = sum(
        1 for v in placements.values()
        if not v.get('isControl', False)
    )

    batch = LibraryPrepBatch.objects.create(
        project      = project,
        workflowType = workflow,
        datePrepped  = prepped_date,
        max_samples  = sample_count,
        notes        = notes,
        createdBy    = request.user,
    )

    # create LibraryPrepSample rows 
    created = 0
    for well_pos, info in placements.items():
        qc_id      = info.get('qcId')
        is_control = info.get('isControl', False)

        source_qc = None
        conc      = None

        if is_control:
            # Controls have no SampleQC record — created with null sampleQC
            pass
        else:
            try:
                source_qc = SampleQC.objects.select_related('sample').get(pk=int(qc_id))
                # Use Qubit reading as concentration input (ng/µL)
                conc = source_qc.qubit_nm
            except (SampleQC.DoesNotExist, ValueError, TypeError):
                source_qc = None
                conc = None

        vol_sample, vol_diluent, actual_input, speedvac = _calc_volumes(
            conc,
            workflow.target_input_ng,
            workflow.target_volume_ul,
        )

        LibraryPrepSample.objects.create(
            libPrepBatch       = batch,
            sampleQC           = source_qc,
            plateWell          = None,      # assigned when plate location is set later
            concentrationInput = conc,
            volumeSample_ul    = vol_sample,
            volumeDiluent_ul   = vol_diluent,
            actual_Input_ng    = actual_input,
            speedVacRequired   = speedvac,
            prepAction         = PrepAction.PREP,
            createdBy          = request.user,
        )
        created += 1

    messages.success(
        request,
        f'Batch created — {created} well{"s" if created != 1 else ""} assigned. '
        f'Plate location can be set from the batch detail page.'
    )
    return redirect('libprep-detail', batch_id=batch.pk)


#  volume calculation 

def _calc_volumes(conc, target_ng, start_vol):
    """
    Returns (vol_sample_ul, vol_diluent_ul, actual_input_ng, speedvac_required).
    All None if concentration is missing or zero.
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
        return (
            vol_needed,
            0.0,
            round(target_ng, 2),
            True,
        )