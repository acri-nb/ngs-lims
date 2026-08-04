import json
import csv
import io
from datetime import date

import os
from django.template.loader import render_to_string
from django.http import FileResponse
from weasyprint import HTML
from pypdf import PdfReader, PdfWriter

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.db import transaction
from django.db.models import Prefetch
from django.http import JsonResponse
from django.utils import timezone

from .models import (
    LibraryPrepBatch,
    LibraryPrepBatchAuditLog,
    LibraryPrepSample,
    WorkflowType,
    WorkflowTypeStep,
    WorkflowStepRowOrder,
    PrepAction,
    LibraryBatchStatus,
    SampleLibraryStatus,
    IndexKit,
    LibraryIndex,
    LibraryQCBatch,
    LibraryQC,
)
from locations.models import Rack, Plate, PlateWell, PlateFormat
from samples.models import Project
from qc.models import SampleQC

from collections import Counter

ROWS = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']
COLS = [f'{c:02d}' for c in range(1, 13)]   


def libprep_list(request):
    batches = LibraryPrepBatch.objects.select_related(
        'project', 'project__client', 'workflowType', 'plate'
    ).order_by('-datePrepped')

    batch_data = []
    for batch in batches:
        samples = list(batch.samples.select_related('qcResult').all())
        total   = len(samples)

        # workflow_status is only meaningful for real samples; controls
        # get their own separate count, not part of the progress bar.
        counts = Counter(s.workflow_status for s in samples if s.sampleQC_id)
        control_count = sum(1 for s in samples if s.sampleQC_id is None)

        pending_prep = counts.get(SampleLibraryStatus.PENDING_PREP, 0)
        pending_qc   = counts.get(SampleLibraryStatus.PENDING_QC, 0)
        qc_pass      = counts.get(SampleLibraryStatus.QC_PASS, 0)
        qc_caution   = counts.get(SampleLibraryStatus.QC_CAUTION, 0)
        qc_fail      = counts.get(SampleLibraryStatus.QC_FAIL, 0)
        skipped      = counts.get(SampleLibraryStatus.SKIPPED, 0)

        batch_data.append({
            'batch':         batch,
            'total':         total,
            'pending_prep':  pending_prep,
            'pending_qc':    pending_qc,
            'qc_pass':       qc_pass,
            'qc_caution':    qc_caution,
            'qc_fail':       qc_fail,
            'skipped':       skipped,
            'control_count': control_count,
            # used by the "Has Pending" filter button
            'still_pending': pending_prep + pending_qc,
        })

    return render(request, 'library/libprep_list.html', {'batch_data': batch_data})

def _get_mastermix_steps(batch, reaction_count):
    """
    Fetch this batch's workflow steps + reagent rows (ordered exactly like
    the source protocol sheets) and attach a computed `computed_volume` to
    each row for the given reaction_count, so templates never need to do
    the math themselves (handy for the print view, which has no JS).
    """
    steps = (
        WorkflowTypeStep.objects
        .filter(workflowType=batch.workflowType)
        .order_by('sort_order', 'stepName')
        .prefetch_related(
            Prefetch(
                'row_links',
                queryset=WorkflowStepRowOrder.objects
                    .select_related('step_row')
                    .order_by('sort_order'),
                to_attr='ordered_rows',
            )
        )
    )

    for step in steps:
        step_total = 0.0
        for row in step.ordered_rows:
            row.computed_volume = row.mastermix_volume(reaction_count)
            if row.constantOfMM == 2:
                row.computed_ethanol, row.computed_water = row.ethanol_dilution_volumes(reaction_count)
            else:
                row.computed_ethanol, row.computed_water = None, None
            if row.computed_volume is not None:
                step_total += row.computed_volume
        step.computed_total = round(step_total, 2) if step.ordered_rows else None

    return steps


def libprep_detail(request, batch_id):
    batch = get_object_or_404(
        LibraryPrepBatch.objects.select_related(
            'project', 'project__client', 'workflowType', 'plate',
            'plate__rack', 'plate__rack__location',
        ),
        pk=batch_id,
    )

    samples_qs = batch.samples.select_related(
        'plateWell', 'sampleQC', 'sampleQC__sample', 'libraryIndex', 'qcResult',
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

    #Master Mix tab data 
    reaction_count  = batch.effective_mastermix_reaction_count
    mastermix_steps = _get_mastermix_steps(batch, reaction_count)

    # Prep Sheet tab data ordered A01, B01 ... H01, A02 ... to match the
    # paper sheet's column-major fill order (8 rows = column A on the sheet)
    prep_rows = _get_prep_sheet_rows(batch)

    return render(request, 'library/libprep_detail.html', {
        'batch':           batch,
        'grid':            grid,
        'cols':            COLS,
        'total':           total,
        'prepped':         prepped,
        'pending':         pending,
        'audit_log':       audit_log,
        'mastermix_steps': mastermix_steps,
        'reaction_count':  reaction_count,
        'prep_rows':       prep_rows,
        'workflow':        batch.workflowType,
    })


def libprep_mastermix_save(request, batch_id):
    """
    AJAX endpoint persists the reaction count a lab member enters on the
    Master Mix tab, so it's remembered the next time anyone opens this
    batch
    """
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Invalid request method.'}, status=405)

    batch = get_object_or_404(LibraryPrepBatch, pk=batch_id)

    raw_count = request.POST.get('reaction_count', '').strip()
    try:
        reaction_count = int(raw_count)
        if reaction_count < 0:
            raise ValueError
    except (TypeError, ValueError):
        return JsonResponse({'ok': False, 'error': 'Reaction count must be a positive whole number.'}, status=400)

    previous = batch.mastermix_reaction_count
    batch.mastermix_reaction_count = reaction_count
    batch.save(update_fields=['mastermix_reaction_count'])

    LibraryPrepBatchAuditLog.objects.create(
        batch=batch,
        changed_by=request.user if request.user.is_authenticated else None,
        action=LibraryPrepBatchAuditLog.ACTION_UPDATED,
        detail=(
            f'Master Mix reaction count set to {reaction_count} '
            f'(previously {previous if previous is not None else "unset, used sample+control count"}).'
        ),
    )

    return JsonResponse({'ok': True, 'reaction_count': reaction_count})


def libprep_mastermix_print(request, batch_id):
    """
    Standalone, print-friendly Master Mix sheet no sidebar/topnav, The page has a Print button that
    calls window.print(); the lab member can "Save as PDF" from the
    browser's print dialog.
    """
    batch = get_object_or_404(
        LibraryPrepBatch.objects.select_related(
            'project', 'project__client', 'workflowType', 'plate',
        ),
        pk=batch_id,
    )

    reaction_count  = batch.effective_mastermix_reaction_count
    mastermix_steps = _get_mastermix_steps(batch, reaction_count)

    return render(request, 'library/libprep_mastermix_print.html', {
        'batch':           batch,
        'mastermix_steps': mastermix_steps,
        'reaction_count':  reaction_count,
        'printed_at':      timezone.now(),
    })

def libprep_mastermix_pdf(request, batch_id):
    """
    Server-rendered Master Mix PDF: same content as libprep_mastermix_print,
    but rendered to PDF with WeasyPrint and with the workflow's static
    protocol PDF (WorkflowType.protocol_file) appended at the end.
    """
    batch = get_object_or_404(
        LibraryPrepBatch.objects.select_related(
            'project', 'project__client', 'workflowType', 'plate',
        ),
        pk=batch_id,
    )

    reaction_count  = batch.effective_mastermix_reaction_count
    mastermix_steps = _get_mastermix_steps(batch, reaction_count)

    html_string = render_to_string('library/libprep_mastermix_print.html', {
        'batch':           batch,
        'mastermix_steps': mastermix_steps,
        'reaction_count':  reaction_count,
        'printed_at':      timezone.now(),
    })

    mastermix_pdf_bytes = HTML(
        string=html_string,
        base_url=request.build_absolute_uri('/'),
    ).write_pdf()

    writer = PdfWriter()
    for page in PdfReader(io.BytesIO(mastermix_pdf_bytes)).pages:
        writer.add_page(page)

    protocol = batch.workflowType.protocol_file
    if protocol and os.path.exists(protocol.path):
        for page in PdfReader(protocol.path).pages:
            writer.add_page(page)
    # If no protocol_file is set for this workflow, we just skip appending
    # silently — the mastermix sheet alone still gets returned.

    output = io.BytesIO()
    writer.write(output)
    output.seek(0)

    filename = f"MasterMix_{batch.batch_name or batch.plate.plate_name}.pdf"
    return FileResponse(output, filename=filename, content_type='application/pdf')

    
# PREP SHEET  (RNA/DNA + diluent volume calc, printable working sheet)

STANDARD_DILUTION_FACTORS = [2, 5, 10, 20, 50, 100]   # 1:2, 1:5, 1:10, 1:20, 1:50, 1:100
MIN_PIPETTE_UL = 1.5   # below this, pipetting raw stock isn't accurate and need to dilute it


def _suggest_dilution(conc, target_ng, target_vol_ul, min_pipette_ul=MIN_PIPETTE_UL):
    """
    When the raw pipette volume needed is under min_pipette_ul (too small
    to pipette accurately), pick the smallest standard dilution factor
    (1:2, 1:5, 1:10, ...) that brings the diluted-stock pipette volume
    back up to at least min_pipette_ul.
    """
    vol_needed = target_ng / conc
    if vol_needed >= min_pipette_ul:
        return None

    for factor in STANDARD_DILUTION_FACTORS:
        vol_from_diluted = vol_needed * factor
        if vol_from_diluted >= min_pipette_ul:
            return {
                'factor': factor,
                'diluted_conc': round(conc / factor, 4),
                'vol_from_diluted_ul': round(min(vol_from_diluted, target_vol_ul), 2),
            }

    # Even the largest standard factor doesn't clear the threshold,
    # use it anyway, better than nothing, and it's clearly labelled.
    factor = STANDARD_DILUTION_FACTORS[-1]
    return {
        'factor': factor,
        'diluted_conc': round(conc / factor, 4),
        'vol_from_diluted_ul': round(min(vol_needed * factor, target_vol_ul), 2),
    }


def _calc_prep_volumes(conc, volume_available, target_ng, target_vol_ul):
    """
    Core per-sample prep-volume calculation, matching the lab's paper
    protocol sheets (see NGS_workflows.md).
    
    - "Impossible" check: even pipetting the ENTIRE available volume, is there enough material to hit target_ng?
    - Simple case: vol_needed (target_ng / conc) fits within target_vol_ul and can get diluted or changed
    - SpeedVac case: vol_needed exceeds target_vol_ul (i.e. the diluent volume would go negative) 
    - Insufficient case: vol_needed exceeds volume_available itself (the whole tube isn't enough) 

    """
    base = {
        'status': 'no_conc',
        'vol_sample_ul': None,
        'vol_diluent_ul': None,
        'actual_input_ng': None,
        'speedvac_required': False,
        'insufficient': False,
        'dilution': None,
    }

    if not conc or conc <= 0:
        return base

    # Case 4: not even the whole available volume has enough material.
    if volume_available and (conc * volume_available) < target_ng:
        actual = round(conc * volume_available, 2)
        speedvac = volume_available > target_vol_ul
        base.update({
            'status': 'insufficient',
            'vol_sample_ul': round(volume_available, 2),
            'vol_diluent_ul': 0.0 if speedvac else round(target_vol_ul - volume_available, 2),
            'actual_input_ng': actual,
            'speedvac_required': speedvac,
            'insufficient': True,
        })
        return base

    vol_needed = round(target_ng / conc, 2)

    # Case 2 / 2b: fits directly, top up with diluent, unless the raw
    # volume is too small to pipette accurately, then suggest a dilution.
    if vol_needed <= target_vol_ul:
        dilution = _suggest_dilution(conc, target_ng, target_vol_ul)
        if dilution:
            pipette_vol = dilution['vol_from_diluted_ul']
            base.update({
                'status': 'dilute',
                'vol_sample_ul': pipette_vol,
                'vol_diluent_ul': round(target_vol_ul - pipette_vol, 2),
                'actual_input_ng': round(target_ng, 2),
                'speedvac_required': False,
                'dilution': dilution,
            })
            return base

        base.update({
            'status': 'ok',
            'vol_sample_ul': vol_needed,
            'vol_diluent_ul': round(target_vol_ul - vol_needed, 2),
            'actual_input_ng': round(target_ng, 2),
            'speedvac_required': False,
        })
        return base

    # Case 3: enough material overall, but need to SpeedVac down
    # (this is the "diluent volume would go negative" trigger).
    base.update({
        'status': 'speedvac',
        'vol_sample_ul': vol_needed,
        'vol_diluent_ul': 0.0,
        'actual_input_ng': round(target_ng, 2),
        'speedvac_required': True,
    })
    return base


def _get_prep_sheet_rows(batch):
    """
    Builds the row data for the Prep Sheet tab / print view, one row per
    LibraryPrepSample, ordered to match the paper sheet's fill order
    (column-major: A01..H01, A02..H02, ...) so the first 8 rows a lab
    member fills in correspond to column A on the physical plate
    """
    samples = (
        batch.samples
        .select_related('sampleQC__sample', 'plateWell', 'libraryIndex')
    )

    # Column-major sort key from planned_well_position / plateWell position
    def sort_key(s):
        pos = (s.plateWell.well_position if s.plateWell_id else s.planned_well_position) or 'Z99'
        row_letter, col_num = pos[0], pos[1:]
        try:
            col_num = int(col_num)
        except ValueError:
            col_num = 99
        return (col_num, row_letter)

    samples = sorted(samples, key=sort_key)

    rows = []
    for s in samples:
        is_control = s.sampleQC_id is None
        well_pos = s.plateWell.well_position if s.plateWell_id else s.planned_well_position

        if is_control:
            rows.append({
                'well_pos':      well_pos,
                'is_control':    True,
                'sample':        None,
                'sample_name':   'Control',
                'conc':          None,
                'calc':          None,
                'library_sample': s,
            })
            continue

        sample_obj = s.sampleQC.sample

        dilution = None
        if s.suggestedDilutionFactor:
            diluted_conc = (
                round(s.concentrationInput / s.suggestedDilutionFactor, 4)
                if s.concentrationInput else None
            )
            dilution = {
                'factor': s.suggestedDilutionFactor,
                'diluted_conc': diluted_conc,
            }

        if s.insufficientMaterial:
            status = 'insufficient'
        elif s.speedVacRequired:
            status = 'speedvac'
        elif dilution:
            status = 'dilute'
        elif s.volumeSample_ul is not None:
            status = 'ok'
        else:
            status = 'no_conc'

        calc = {
            'status':            status,
            'vol_sample_ul':     s.volumeSample_ul,
            'vol_diluent_ul':    s.volumeDiluent_ul,
            'actual_input_ng':   s.actual_Input_ng,
            'speedvac_required': s.speedVacRequired,
            'insufficient':      s.insufficientMaterial,
            'dilution':          dilution,
        }

        rows.append({
            'well_pos':       well_pos,
            'is_control':     False,
            'sample':         sample_obj,
            'sample_name':    sample_obj.sample_name,
            'conc':           s.concentrationInput,
            'calc':           calc,
            'library_sample': s,
        })

    return rows


def libprep_prep_sheet_print(request, batch_id):
    """
    Standalone, print-friendly Prep Sheet: the working sheet a lab member
    takes to the bench. """
    batch = get_object_or_404(
        LibraryPrepBatch.objects.select_related(
            'project', 'project__client', 'workflowType', 'plate',
        ),
        pk=batch_id,
    )
    prep_rows = _get_prep_sheet_rows(batch)

    return render(request, 'library/libprep_prepsheet_print.html', {
        'batch':      batch,
        'workflow':   batch.workflowType,
        'prep_rows':  prep_rows,
        'printed_at': timezone.now(),
    })


# WELL DATA IMPORT  (Plate Set/Well or UDI, PCR cycles, Qubit, TapeStation)

def _lookup_library_index(workflow, plate_set, index_well, udi):
    """
    Resolve a LibraryIndex row against this workflow's index kit(s).

    Two modes, matching workflow.logs_plate_and_well:
      - True  (TotalRNA, DNA PCR-Free): look up by (plateSet, well).
      - False (KAPA, Small RNA): look up by udi_number directly.
    """
    kits = IndexKit.objects.filter(workflowType=workflow)
    if not kits.exists():
        return None, f'No Index Kit configured for workflow "{workflow.workflowType}".'

    qs = LibraryIndex.objects.filter(indexKit__in=kits)

    if workflow.logs_plate_and_well:
        if not plate_set or not index_well:
            return None, None
        match_qs = qs.filter(plateSet__iexact=plate_set.strip(), well__iexact=index_well.strip())
        match = match_qs.first()
        if not match:
            return None, f'No index found for Plate Set "{plate_set}" / Well "{index_well}".'
        return match, None

    if not udi:
        return None, None
    match_qs = qs.filter(udi_number__iexact=udi.strip())
    if match_qs.count() > 1:
        return None, f'UDI "{udi}" matches more than one index for this workflow, resolve manually.'
    match = match_qs.first()
    if not match:
        return None, f'No index found for UDI "{udi}".'
    return match, None


def libprep_import_results(request, batch_id):
    """
    Accepts a CSV upload, the same shape as the Well Data export / printed
    Prep Sheet, and writes back the values a lab member filled in by hand:
    the index (Plate Set + Well, or UDI directly depending on the
    workflow), PCR cycles, and Library QC measurements (Qubit, and
    TapeStation fields where the workflow uses them).
    """
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Invalid request method.'}, status=405)

    batch = get_object_or_404(
        LibraryPrepBatch.objects.select_related('workflowType'), pk=batch_id
    )
    workflow = batch.workflowType

    if 'csv_file' not in request.FILES:
        return JsonResponse({'ok': False, 'error': 'No file uploaded.'}, status=400)

    csv_file = request.FILES['csv_file']
    if not csv_file.name.endswith('.csv'):
        return JsonResponse({'ok': False, 'error': 'File must be a .csv'}, status=400)

    try:
        text = csv_file.read().decode('utf-8-sig')
    except UnicodeDecodeError:
        return JsonResponse({'ok': False, 'error': 'Could not decode file, make sure it is UTF-8.'}, status=400)

    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        return JsonResponse({'ok': False, 'error': 'CSV appears to be empty.'}, status=400)

    def norm(s):
        return (
            s.strip().lower()
            .replace(' ', '_').replace('/', '_')
            .replace('(', '').replace(')', '')
        )

    raw_headers = reader.fieldnames
    norm_headers = [norm(h) for h in raw_headers]

    def get_col(row, *candidates):
        for candidate in candidates:
            for raw, normed in zip(raw_headers, norm_headers):
                if normed == candidate:
                    val = row.get(raw, '').strip()
                    return val if val != '' else None
        return None

    def to_float(val):
        if val is None:
            return None
        try:
            return float(val)
        except ValueError:
            return None

    def to_int(val):
        if val is None:
            return None
        try:
            return int(float(val))
        except ValueError:
            return None

    sample_map = {
        s.plateWell.well_position: s
        for s in batch.samples.select_related('sampleQC__sample', 'plateWell', 'libraryIndex')
        if s.plateWell_id
    }

    updated, skipped, errors = [], [], []

    with transaction.atomic():
        libqc_batch = None  # created lazily, only if a row actually has QC data

        for line_num, row in enumerate(reader, start=2):  # row 1 is the header
            well = get_col(row, 'well')
            if not well:
                errors.append(f'Row {line_num}: missing Well.')
                continue

            sample = sample_map.get(well.strip().upper())
            if sample is None:
                skipped.append(well)
                continue

            row_label = (
                sample.sampleQC.sample.sample_name
                if sample.sampleQC_id else f'{well} (control)'
            )
            row_changed = False

            # Index: Plate Set + Well, or UDI directly
            if workflow.logs_plate_and_well:
                plate_set  = get_col(row, 'plate_set', 'index_plate_set')
                index_well = get_col(row, 'index_well', 'well_x')
                index_obj, err = _lookup_library_index(workflow, plate_set, index_well, None)
            else:
                udi = get_col(row, 'udi', 'udi_number')
                index_obj, err = _lookup_library_index(workflow, None, None, udi)

            if err:
                errors.append(f'{row_label}: {err}')
            elif index_obj:
                sample.libraryIndex = index_obj
                row_changed = True

            # PCR cycles, only meaningful for workflows that PCR at all
            if workflow.requires_pcr:
                pcr = to_int(get_col(row, 'pcr_cycles', 'pcr'))
                if pcr is not None:
                    sample.PCRCycles = pcr
                    row_changed = True

            if row_changed:
                sample.save(update_fields=['libraryIndex', 'PCRCycles'])

            # Library QC values, only meaningful for real samples (not controls)
            qubit        = to_float(get_col(row, 'qubit_ng_ul', 'qubit'))
            avg_lib_size = None
            dimer_pct    = None
            region_pct   = None
            region_nm    = None

            if workflow.qc_method == 'qubit_tapestation':
                avg_lib_size = to_float(get_col(row, 'avg_lib_size'))
                dimer_pct    = to_float(get_col(row, 'dimer_peak_%', 'dimer_peak_pct'))
                region_pct   = to_float(get_col(row, 'region_%', 'region_pct'))
                region_nm    = to_float(get_col(row, 'region_nm'))

            has_qc_data = any(v is not None for v in (qubit, avg_lib_size, dimer_pct, region_pct, region_nm))

            if not has_qc_data or sample.sampleQC_id is None:
                # Controls don't carry a SampleQC/Sample and don't get
                # Library QC rows (for now); nothing more to do for them.
                if row_changed:
                    updated.append(row_label)
                continue

            if libqc_batch is None:
                libqc_batch, _ = LibraryQCBatch.objects.get_or_create(
                    libPrepBatch=batch,
                    defaults={'batchName': f'{batch.batch_name} Library QC', 'createdBy': request.user},
                )

            libqc, _ = LibraryQC.objects.get_or_create(
                libPrepSample=sample,
                defaults={'libQCBatch': libqc_batch},
            )
            if qubit is not None:
                libqc.qubit_ng_ul = qubit
            if avg_lib_size is not None:
                libqc.fragmentSizesAvgBP = avg_lib_size
            if dimer_pct is not None:
                libqc.dimerPeak_pct = dimer_pct
            if region_pct is not None:
                libqc.region_pct = region_pct
            if region_nm is not None:
                libqc.region_nm = region_nm

            # Recompute nM from the freshly-imported values. Passing the
            # workflow through matters for workflows without TapeStation
            libqc.nmCalculated = libqc.calculate_nm(workflow_type=workflow)
            libqc.createdBy = request.user
            libqc.QCstatus = libqc.calculate_qc_status(workflow_type=workflow)
            libqc.save()

            updated.append(row_label)

    return JsonResponse({'ok': True, 'updated': updated, 'skipped': skipped, 'errors': errors})


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
    GET: render the drag-and-drop plate builder.
           Left sidebar: SampleQC records for this project, sorted by status.
           Location modal: all racks, grouped by location.

    POST: validate inputs, then atomically:
             1. Generate batch name  (PROJECT-Library-4HEX)
             2. Create Plate         (locations.Plate)
             3. Assign to Rack slot
             4. Create LibraryPrepBatch
             5. Create LibraryPrepSample rows (no PlateWell yet filled later)
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

    # SampleQC pks that already appear in a LibraryPrepSample (any batch,
    # any project) these get pulled into their own "already prepped"
    # section instead of the normal status buckets.
    used_qc_ids = set(
        LibraryPrepSample.objects
        .filter(sampleQC__in=sample_qcs)
        .values_list('sampleQC_id', flat=True)
    )

    STATUS_ORDER  = {SampleQC.PASS: 0, SampleQC.CAUTION: 1, SampleQC.FAIL: 2, SampleQC.PENDING: 3}
    STATUS_LABELS = {SampleQC.PASS: 'Pass', SampleQC.CAUTION: 'Caution',
                      SampleQC.FAIL: 'Fail', SampleQC.PENDING: 'Pending'}

    qc_pass, qc_caution, qc_fail, qc_pending, qc_already_used = [], [], [], [], []

    for q in sample_qcs:
        if q.pk in used_qc_ids:
            qc_already_used.append(q)
        elif q.qc_status == SampleQC.PASS:
            qc_pass.append(q)
        elif q.qc_status == SampleQC.CAUTION:
            qc_caution.append(q)
        elif q.qc_status == SampleQC.FAIL:
            qc_fail.append(q)
        elif q.qc_status == SampleQC.PENDING:
            qc_pending.append(q)

    qc_already_used.sort(
        key=lambda q: (STATUS_ORDER.get(q.qc_status, 99), q.sample.sample_name.lower())
    )
    for q in qc_already_used:
        q.status_label = STATUS_LABELS.get(q.qc_status, q.qc_status)

    workflow_types = WorkflowType.objects.order_by('workflowType')

    racks = Rack.objects.select_related('location').order_by(
        'location__locationName', 'rack_name'
    )

    # Annotate each rack with occupancy so the location modal can grey out
    # racks that have no free slots, before the person opens the slot grid.
    
    for rack in racks:
        rack.total_slots = rack.rows * rack.cols * 2
        rack.occupied_count = Plate.objects.filter(
            rack=rack
        ).exclude(rack_location='').count()
        rack.free_slots = rack.total_slots - rack.occupied_count
        rack.is_full = rack.free_slots <= 0


    return render(request, 'library/libprep_newbatch.html', {
        'project':         project,
        'qc_pass':         qc_pass,
        'qc_caution':      qc_caution,
        'qc_fail':         qc_fail,
        'qc_pending':      qc_pending,
        'qc_already_used': qc_already_used,
        'workflow_types':  workflow_types,
        'racks':           racks,
        'rows':            ROWS,
        'cols':            COLS,
        'today':           date.today().isoformat(),
    })

def _validate_batch_composition(placements, workflow):
    """
    Returns a list of human-readable problems with this batch, or [] if it's fine.

    Checks:
      - not made up entirely of controls
      - every non-control sample's type matches workflow.sample_type
      - control usage matches workflow.uses_controls (both pos+neg required
        if the workflow uses controls, none allowed if it doesn't)
    """
    errors = []

    non_control_ids = [
        v['qcId'] for v in placements.values() if not v.get('isControl', False)
    ]
    control_ids = {
        v['qcId'] for v in placements.values() if v.get('isControl', False)
    }

    if not non_control_ids:
        errors.append('Batch contains only controls add at least one real sample.')
        return errors

    qcs = SampleQC.objects.filter(pk__in=non_control_ids).select_related('sample')
    qc_by_id = {str(q.pk): q for q in qcs}

    mismatched = []
    for qc_id in non_control_ids:
        qc = qc_by_id.get(str(qc_id))
        if qc is None:
            errors.append(f'Sample QC #{qc_id} could not be found.')
            continue
        if qc.sample.sample_type != workflow.sample_type:
            mismatched.append(f'{qc.sample.sample_name} ({qc.sample.sample_type})')

    if mismatched:
        errors.append(
            f'Workflow "{workflow.workflowType}" expects {workflow.sample_type} samples, '
            f'but these don\'t match: {", ".join(mismatched)}.'
        )

    if workflow.uses_controls:
        if 'pos' not in control_ids:
            errors.append(f'Workflow "{workflow.workflowType}" requires a positive control, none placed.')
        if 'neg' not in control_ids:
            errors.append(f'Workflow "{workflow.workflowType}" requires a negative control, none placed.')
    elif control_ids:
        errors.append(f'Workflow "{workflow.workflowType}" does not use controls, but one was placed.')

    return errors


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
        if not isinstance(placements, dict):
            placements = {}
    except (json.JSONDecodeError, ValueError, TypeError):
        placements = {}

    # Strip empty / null entries
    placements = {
        k: v for k, v in placements.items()
        if isinstance(v, dict) and v.get('qcId')
    }

    if not placements:
        errors.append('No samples placed on the plate, drag at least one sample before saving.')

    if errors:
        for e in errors:
            messages.error(request, e)
        return redirect('libprep-new-batch', project_id=project.pk)

    workflow = get_object_or_404(WorkflowType, pk=workflow_id)
    rack     = get_object_or_404(Rack.objects.select_related('location'), pk=rack_id)

    composition_errors = _validate_batch_composition(placements, workflow)
    if composition_errors:
        for e in composition_errors:
            messages.error(request, e)
        return redirect('libprep-new-batch', project_id=project.pk)

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
            rack_location = rack_slot,         
            plate_name    = batch_name,
            plate_format  = PlateFormat.F_96,   # physical plate is 96-well; batch uses 48
            notes         = f'Library prep plate: {workflow.workflowType}',
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
            project=project,
            plate=plate,
            workflowType=workflow,
            datePrepped=prepped_date,
            batch_name=batch_name,
            max_samples=sample_count,
            notes=notes,
            createdBy=request.user,
            status=LibraryBatchStatus.PENDING_PREP,
        )

        # 5c. Create LibraryPrepSample rows
        # PlateWell is intentionally left null filled when the batch is
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
                    # Prep math runs off the sample's own original intake
                    # values, not the QC measurement. SampleQC only gates
                    # which samples are eligible for a batch (Pass/
                    # Caution/Fail) — it isn't a re-measurement of the
                    # tube's concentration for prep purposes.
                    conc = source_qc.sample.concentration
                    placement_summary.append(
                        f'{well_pos}: {source_qc.sample.sample_name} [{status}]'
                    )
                except (SampleQC.DoesNotExist, ValueError, TypeError):
                    source_qc = None
                    placement_summary.append(f'{well_pos}: unknown sample [error]')

            volume_available = source_qc.sample.volume_received if source_qc else None
            calc = _calc_prep_volumes(
                conc,
                volume_available,
                workflow.target_input_ng,
                workflow.target_volume_ul,
            )
            vol_sample   = calc['vol_sample_ul']
            vol_diluent  = calc['vol_diluent_ul']
            actual_input = calc['actual_input_ng']
            speedvac     = calc['speedvac_required']
            insufficient = calc['insufficient']
            dilution_factor = calc['dilution']['factor'] if calc['dilution'] else None

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

            # If a sample can't reach target ng even using the whole tube,
            # pre-flag it as REQUEUE instead of PREP so the lab sees it
            # needs a decision (new material, or proceed with reduced
            # input) before this well gets worked on.
            prep_action = PrepAction.REQUEUE if insufficient else PrepAction.PREP

            LibraryPrepSample.objects.create(
                libPrepBatch=batch,
                sampleQC=source_qc,
                plateWell=plate_well,
                concentrationInput=conc,
                volumeSample_ul=vol_sample,
                volumeDiluent_ul=vol_diluent,
                actual_Input_ng=actual_input,
                speedVacRequired=speedvac,
                insufficientMaterial=insufficient,
                suggestedDilutionFactor=dilution_factor,
                prepAction=prep_action,
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
                f'Status: Pending LibraryPrep\n'
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
        f'Batch "{batch_name}" created {created} well{"s" if created != 1 else ""} '
        f'placed on plate {plate.plate_name} in {rack.rack_name} slot {rack_slot}.'
    )
    return redirect('libprep-detail', batch_id=batch.pk)

def libprep_check_batch(request, project_id):
    """AJAX pre-flight check, called before the confirm modal opens."""
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'errors': ['Invalid request method.']}, status=405)

    workflow_id    = request.POST.get('workflow_type_id', '').strip()
    placements_raw = request.POST.get('placements', '').strip()

    if not workflow_id:
        return JsonResponse({'ok': False, 'errors': ['Select a workflow type first.']})

    workflow = get_object_or_404(WorkflowType, pk=workflow_id)

    try:
        placements = json.loads(placements_raw) if placements_raw else {}
        if not isinstance(placements, dict):
            placements = {}
    except (json.JSONDecodeError, ValueError, TypeError):
        placements = {}
    placements = {
        k: v for k, v in placements.items()
        if isinstance(v, dict) and v.get('qcId')
    }

    errors = _validate_batch_composition(placements, workflow)
    return JsonResponse({'ok': not errors, 'errors': errors})