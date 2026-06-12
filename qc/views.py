import json
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.utils import timezone
from django.db import transaction
from datetime import date

from samples.models import Project, Sample
from .models import SampleQCBatch, BatchSample, BatchAuditLog, SampleQC


# BATCH CARD LIST (main QC landing page)

@login_required
def qc_batch_list(request):
    """
    Landing page: all batches as cards, grouped by project.
    'Assign Batches' button leads to the project picker.
    """
    batches = (
        SampleQCBatch.objects
        .select_related('project__client', 'created_by')
        .prefetch_related('batch_samples__sample')
        .order_by('-date_batched')
    )

    batch_data = []
    for batch in batches:
        total   = batch.batch_samples.count()
        pending = batch.qc_results.filter(qc_status=SampleQC.PENDING).count()
        passed  = batch.qc_results.filter(qc_status=SampleQC.PASS).count()
        failed  = batch.qc_results.filter(qc_status=SampleQC.FAIL).count()
        caution = batch.qc_results.filter(qc_status=SampleQC.CAUTION).count()
        batch_data.append({
            'batch':   batch,
            'total':   total,
            'pending': pending,
            'passed':  passed,
            'failed':  failed,
            'caution': caution,
        })

    return render(request, 'qc/qc_batch_list.html', {'batch_data': batch_data})


# BATCH DETAIL 

@login_required
def qc_batch_detail(request, batch_id):
    """
    Detail page for a single batch.
    Shows a type-specific QC results table (DNA or RNA columns).
    """
    batch = get_object_or_404(
        SampleQCBatch.objects.select_related('project__client', 'created_by'),
        pk=batch_id
    )
    qc_results = (
        batch.qc_results
        .select_related('sample__specimen__case', 'sample__specimen__specimen_type', 'edited_by')
        .order_by('sample__sample_name')
    )
    return render(request, 'qc/qc_batch_detail.html', {
        'batch':      batch,
        'qc_results': qc_results,
    })


# PROJECT PICKER (assign flow entry)

@login_required
def qc_project_list(request):
    projects = Project.objects.select_related('client').order_by('project_name')
    project_data = []
    for project in projects:
        sample_qs   = project.samples.all()
        total       = sample_qs.count()
        batched     = sample_qs.filter(batch_memberships__isnull=False).distinct().count()
        unbatched   = total - batched
        batch_count = SampleQCBatch.objects.filter(project=project).count()
        dna_count   = sample_qs.filter(sample_type='DNA').count()
        rna_count   = sample_qs.filter(sample_type='RNA').count()
        project_data.append({
            'project':     project,
            'total':       total,
            'batched':     batched,
            'unbatched':   unbatched,
            'batch_count': batch_count,
            'dna_count':   dna_count,
            'rna_count':   rna_count,
        })
    return render(request, 'qc/qc_project_list.html', {'project_data': project_data})


# BATCH ASSIGNMENT BOARD

@login_required
def qc_batch_board(request, project_id):
    project = get_object_or_404(Project, pk=project_id)

    all_samples = (
        project.samples
        .select_related('specimen__case', 'specimen__specimen_type')
        .prefetch_related('qc_results', 'batch_memberships__batch')
        .order_by('sample_type', 'sample_name')
    )

    # Only batches that belong to this project
    batches = (
        SampleQCBatch.objects
        .filter(project=project)
        .prefetch_related('batch_samples__sample')
        .order_by('date_batched', 'batch_name')
    )

    batch_list = []
    batched_sample_ids = set()
    for batch in batches:
        s_ids = list(batch.batch_samples.values_list('sample__sample_id', flat=True))
        batch_list.append({
            'batch':      batch,
            'sample_ids': s_ids,
            'dna_count':  batch.batch_samples.filter(sample__sample_type='DNA').count(),
            'rna_count':  batch.batch_samples.filter(sample__sample_type='RNA').count(),
            'has_qc':     batch.qc_results.exists(),
        })
        batched_sample_ids.update(s_ids)

    unassigned = [s for s in all_samples if s.sample_id not in batched_sample_ids]

    # Recent audit log for this project (last 20 entries)
    audit_log = (
        BatchAuditLog.objects
        .filter(project=project)
        .select_related('performed_by', 'batch')
        .order_by('-timestamp')[:20]
    )

    samples_json = json.dumps({
        str(s.sample_id): {
            'id':       s.sample_id,
            'name':     s.sample_name,
            'type':     s.sample_type,
            'case':     s.specimen.case.case_name,
            'specimen': s.specimen.specimen_type.specimen_type,
        }
        for s in all_samples
    })

    batches_json = json.dumps({
        str(b['batch'].pk): {
            'id':        b['batch'].pk,
            'name':      b['batch'].batch_name,
            'date':      b['batch'].date_batched.isoformat(),
            'sampleIds': b['sample_ids'],
            'hasQC':     b['has_qc'],
        }
        for b in batch_list
    })

    recommended = _recommend_batches(list(all_samples))

    return render(request, 'qc/qc_batch_board.html', {
        'project':      project,
        'all_samples':  all_samples,
        'unassigned':   unassigned,
        'batch_list':   batch_list,
        'samples_json': samples_json,
        'batches_json': batches_json,
        'recommended':  json.dumps(recommended),
        'audit_log':    audit_log,
    })


def _recommend_batches(samples):
    PLATE_MAX = 60
    dna = [s for s in samples if s.sample_type == 'DNA']
    rna = [s for s in samples if s.sample_type == 'RNA']
    result = []
    for type_label, group in [('DNA', dna), ('RNA', rna)]:
        for i, chunk_start in enumerate(range(0, len(group), PLATE_MAX)):
            chunk = group[chunk_start:chunk_start + PLATE_MAX]
            result.append({
                'label':      f'{type_label} Batch {i + 1}',
                'type':       type_label,
                'sample_ids': [s.sample_id for s in chunk],
                'count':      len(chunk),
            })
    return result


# AJAX: DIFF PREVIEW 

@require_POST
@login_required
def qc_diff_preview(request, project_id):
    """
    Compares the submitted board state against what's currently in the DB.
    Returns a human-readable diff so the confirmation modal can show it.

    Expected body: same as qc_save_board
    {
      "batches": [
        { "id": 3,    "name": "...", "date": "2025-06-01", "sampleIds": [1,4] },
        { "id": null, "name": "NEW-BATCH-1", "date": "2025-06-01", "sampleIds": [2,5] }
      ]
    }
    """
    project = get_object_or_404(Project, pk=project_id)
    try:
        payload = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'ok': False, 'error': 'Invalid JSON'}, status=400)

    valid_ids   = set(project.samples.values_list('sample_id', flat=True))
    sample_names = dict(project.samples.values_list('sample_id', 'sample_name'))

    # Current DB state: batch_id → set of sample_ids
    db_batches = {}
    for batch in SampleQCBatch.objects.filter(project=project).prefetch_related('batch_samples'):
        db_batches[batch.pk] = {
            'name':       batch.batch_name,
            'sample_ids': set(batch.batch_samples.values_list('sample__sample_id', flat=True)),
            'has_qc':     batch.qc_results.exists(),
        }

    changes = []

    for b in payload.get('batches', []):
        new_ids = set(sid for sid in b.get('sampleIds', []) if sid in valid_ids)

        if b.get('id'):
            bid = int(b['id'])
            if bid not in db_batches:
                continue
            old_ids  = db_batches[bid]['sample_ids']
            name     = db_batches[bid]['name']
            has_qc   = db_batches[bid]['has_qc']
            added    = new_ids - old_ids
            removed  = old_ids - new_ids

            if added or removed:
                entry = {
                    'type':    'modify',
                    'batch':   name,
                    'has_qc':  has_qc,
                    'added':   [sample_names.get(sid, str(sid)) for sid in sorted(added)],
                    'removed': [sample_names.get(sid, str(sid)) for sid in sorted(removed)],
                }
                changes.append(entry)
        else:
            # New virtual batch
            if new_ids:
                changes.append({
                    'type':    'create',
                    'batch':   b.get('name', 'New Batch'),
                    'has_qc':  False,
                    'added':   [sample_names.get(sid, str(sid)) for sid in sorted(new_ids)],
                    'removed': [],
                })

    # Batches in DB that are completely absent from payload → deleted
    submitted_ids = {int(b['id']) for b in payload.get('batches', []) if b.get('id')}
    for bid, info in db_batches.items():
        if bid not in submitted_ids:
            changes.append({
                'type':    'delete',
                'batch':   info['name'],
                'has_qc':  info['has_qc'],
                'added':   [],
                'removed': [sample_names.get(sid, str(sid)) for sid in sorted(info['sample_ids'])],
            })

    return JsonResponse({'ok': True, 'changes': changes})


# AJAX: SAVE BOARD STATE

@require_POST
@login_required
def qc_save_board(request, project_id):
    """
    Reconciles the full board state with the DB, writes an audit log entry,
    and ensures every (sample, batch) pair has a SampleQC PENDING stub so
    the lab can immediately start entering measurements.

    SampleQC stubs are created with all metric fields null (status=PENDING).
    Existing SampleQC records are NEVER deleted or overwritten — only new
    ones are created for pairs that don't have one yet.
    """
    project = get_object_or_404(Project, pk=project_id)
    try:
        payload = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'ok': False, 'error': 'Invalid JSON'}, status=400)

    batches_data = payload.get('batches', [])
    valid_ids    = set(project.samples.values_list('sample_id', flat=True))
    sample_names = dict(project.samples.values_list('sample_id', 'sample_name'))

    # Snapshot current DB state for diff + deletion guard
    db_batches_before = {}
    for batch in SampleQCBatch.objects.filter(project=project).prefetch_related('batch_samples'):
        db_batches_before[batch.pk] = set(
            batch.batch_samples.values_list('sample__sample_id', flat=True)
        )

    diff_summary = []

    with transaction.atomic():
        processed_batch_ids = []

        for b in batches_data:
            sample_ids = [sid for sid in b.get('sampleIds', []) if sid in valid_ids]
            try:
                batch_date = date.fromisoformat(b.get('date', timezone.now().date().isoformat()))
            except ValueError:
                batch_date = timezone.now().date()

            if b.get('id'):
                # Existing batch — reconcile membership
                batch   = get_object_or_404(SampleQCBatch, pk=b['id'])
                old_ids = db_batches_before.get(batch.pk, set())
                new_ids = set(sample_ids)

                # Only touch memberships — never touch SampleQC rows
                added   = new_ids - old_ids
                removed = old_ids - new_ids

                # Remove BatchSample rows for samples no longer in this batch
                # (only if they have no QC result in this batch)
                for sid in removed:
                    qc_exists = SampleQC.objects.filter(
                        batch=batch, sample_id=sid
                    ).exists()
                    if not qc_exists:
                        BatchSample.objects.filter(batch=batch, sample_id=sid).delete()
                    # If QC exists, leave the BatchSample row — data safety

                # Add new BatchSample rows
                for sid in added:
                    BatchSample.objects.get_or_create(batch=batch, sample_id=sid)

                if added or removed:
                    diff_summary.append({
                        'batch':   batch.batch_name,
                        'added':   [sample_names.get(sid, str(sid)) for sid in sorted(added)],
                        'removed': [sample_names.get(sid, str(sid)) for sid in sorted(removed)],
                    })

            else:
                #  New virtual batch — create in DB now
                if not sample_ids:
                    continue
                batch = SampleQCBatch.objects.create(
                    date_batched=batch_date,
                    created_by=request.user,
                    project=project,
                )
                for sid in sample_ids:
                    BatchSample.objects.create(batch=batch, sample_id=sid)
                diff_summary.append({
                    'batch':   batch.batch_name,
                    'added':   [sample_names.get(sid, str(sid)) for sid in sorted(sample_ids)],
                    'removed': [],
                })

            # Set / verify batch_type 
            # Derive from the samples currently in the batch
            current_types = set(
                batch.batch_samples
                .values_list('sample__sample_type', flat=True)
                .distinct()
            )
            if len(current_types) == 1:
                batch.batch_type = current_types.pop()
            elif len(current_types) == 0:
                batch.batch_type = None
            # (mixed is prevented client-side; if it somehow arrives we leave
            #  batch_type as-is rather than crash — the board will show a warning)
            batch.save(update_fields=['batch_type', 'date_batched']
                       if batch.date_batched != batch_date
                       else ['batch_type'])

            processed_batch_ids.append(batch.pk)

            # Create PENDING SampleQC stubs for new (sample, batch) pairs 
            # We only create stubs that don't already exist.
            existing_qc_sample_ids = set(
                SampleQC.objects.filter(batch=batch)
                .values_list('sample_id', flat=True)
            )
            current_batch_sample_ids = set(
                batch.batch_samples.values_list('sample__sample_id', flat=True)
            )
            stubs_needed = current_batch_sample_ids - existing_qc_sample_ids

            for sid in stubs_needed:
                qc = SampleQC(
                    sample_id=sid,
                    batch=batch,
                    qc_status=SampleQC.PENDING,
                    edited_by=request.user,
                )
                # skip_validation=True because all metric fields are null at creation;
                # the lab will fill them in later through the QC entry form.
                qc.save(skip_validation=True)

        # Handle deletions: batches in DB absent from payload 
        submitted_ids = {int(b['id']) for b in batches_data if b.get('id')}
        for bid, old_ids in db_batches_before.items():
            if bid not in submitted_ids:
                batch = SampleQCBatch.objects.filter(pk=bid).first()
                if not batch:
                    continue
                if batch.qc_results.filter(
                    qc_status__in=[SampleQC.PASS, SampleQC.FAIL, SampleQC.CAUTION]
                ).exists():
                    # Has real QC data — refuse silent deletion, surface in diff
                    diff_summary.append({
                        'batch':   batch.batch_name,
                        'added':   [],
                        'removed': [],
                        'error':   'Cannot delete — has completed QC results. Remove from the board only.',
                    })
                else:
                    # Only PENDING stubs (or none) — safe to delete
                    diff_summary.append({
                        'batch':   batch.batch_name,
                        'added':   [],
                        'removed': [sample_names.get(sid, str(sid)) for sid in sorted(old_ids)],
                        'deleted': True,
                    })
                    # Delete PENDING stubs first (they cascade anyway but be explicit)
                    SampleQC.objects.filter(batch=batch, qc_status=SampleQC.PENDING).delete()
                    batch.delete()

        # Write audit log
        if diff_summary:
            BatchAuditLog.objects.create(
                project=project,
                action=BatchAuditLog.ACTION_SAVE,
                performed_by=request.user,
                diff_json={'changes': diff_summary},
                notes=payload.get('notes', ''),
            )

    return JsonResponse({'ok': True, 'batchIds': processed_batch_ids})


# AJAX: AUDIT LOG 

@login_required
def qc_audit_log(request, project_id):
    """Returns the last 50 audit entries for a project as JSON (for the log panel)."""
    project = get_object_or_404(Project, pk=project_id)
    entries = (
        BatchAuditLog.objects
        .filter(project=project)
        .select_related('performed_by', 'batch')
        .order_by('-timestamp')[:50]
    )
    data = []
    for e in entries:
        data.append({
            'id':          e.pk,
            'action':      e.get_action_display(),
            'performed_by': e.performed_by.get_full_name() or e.performed_by.username,
            'timestamp':   e.timestamp.strftime('%Y-%m-%d %H:%M'),
            'diff':        e.diff_json,
            'notes':       e.notes,
        })
    return JsonResponse({'ok': True, 'log': data})


@require_POST
@login_required
def qc_import_results(request, batch_id):
    """
    Accepts a CSV file upload and bulk-updates SampleQC records for this batch.

    DNA columns : sample_id, qubit_ng_ul, nanodrop_260_280, nanodrop_260_230
    RNA columns : sample_id, qubit_ng_ul, rin, dv200

    """
    import csv, io

    batch = get_object_or_404(SampleQCBatch, pk=batch_id)

    if 'csv_file' not in request.FILES:
        return JsonResponse({'ok': False, 'error': 'No file uploaded.'}, status=400)

    csv_file = request.FILES['csv_file']
    if not csv_file.name.endswith('.csv'):
        return JsonResponse({'ok': False, 'error': 'File must be a .csv'}, status=400)

    try:
        text = csv_file.read().decode('utf-8-sig')  # strip BOM if present
    except UnicodeDecodeError:
        return JsonResponse({'ok': False, 'error': 'Could not decode file — make sure it is UTF-8.'}, status=400)

    batch_type = batch.batch_type  # 'DNA' or 'RNA'

    # Build a map of sample_name → SampleQC for this batch
    qc_map = {
        qc.sample.sample_name: qc
        for qc in (
            SampleQC.objects
            .filter(batch=batch)
            .select_related('sample')
        )
    }
    valid_names = set(qc_map.keys())

    reader   = csv.DictReader(io.StringIO(text))

    # Normalise header names: lowercase + strip whitespace
    if reader.fieldnames is None:
        return JsonResponse({'ok': False, 'error': 'CSV appears to be empty.'}, status=400)

    def norm(s):
        return s.strip().lower().replace(' ', '_').replace('/', '_')

    raw_headers = reader.fieldnames
    norm_headers = [norm(h) for h in raw_headers]

    def get_col(row, *candidates):
        """Return the first matching normalised column value, or None."""
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

    updated  = []
    skipped  = []
    errors   = []

    with transaction.atomic():
        for line_num, row in enumerate(reader, start=2):  # start=2 because row 1 is header
            sample_id_val = get_col(row, 'sample_id', 'sampleid', 'sample_name', 'sample')
            if not sample_id_val:
                errors.append(f'Row {line_num}: missing sample_id — skipped.')
                continue

            if sample_id_val not in valid_names:
                skipped.append(sample_id_val)
                continue

            qc = qc_map[sample_id_val]
            raw_qubit = to_float(get_col(row, 'qubit_ng_ul', 'qubit(ng_ul)', 'qubit'))

            if batch_type == 'DNA':
                qc.qubit_nm         = raw_qubit if raw_qubit is not None else qc.qubit_nm
                qc.nanodrop_260_280 = to_float(get_col(row, 'nanodrop_260_280', 'nanodrop(260_280)', '260_280')) or qc.nanodrop_260_280
                qc.nanodrop_260_230 = to_float(get_col(row, 'nanodrop_260_230', 'nanodrop(260_230)', '260_230')) or qc.nanodrop_260_230

            elif batch_type == 'RNA':
                qc.qubit_nm = raw_qubit if raw_qubit is not None else qc.qubit_nm
                qc.rin      = to_float(get_col(row, 'rin'))  or qc.rin
                qc.dv200    = to_float(get_col(row, 'dv200')) or qc.dv200

            qc.edited_by = request.user
            qc.save(skip_validation=False)  # run full validation now — real data
            updated.append(sample_id_val)

    return JsonResponse({
        'ok':      True,
        'updated': updated,
        'skipped': skipped,
        'errors':  errors,
    })