from django.shortcuts import render, get_object_or_404
from .models import LibraryPrepBatch, LibraryPrepSample, QCStatus


def libprep_list(request):
    """
    List all LibraryPrepBatches, grouped with a quick summary count
    so the cards can show progress (similar to qc_batch_list).
    """
    batches = LibraryPrepBatch.objects.select_related(
        'project', 'project__client', 'workflowType', 'plate'
    ).order_by('-datePrepped')

    batch_data = []
    for batch in batches:
        samples = batch.samples.select_related('plateWell')

        total    = samples.count()
        prepped  = samples.filter(prepAction='prep').count()
        skipped  = samples.filter(prepAction='skip').count()
        requeued = samples.filter(prepAction='requeue').count()
        pending  = total - prepped - skipped - requeued

        batch_data.append({
            'batch':   batch,
            'total':   total,
            'prepped': prepped,
            'skipped': skipped,
            'requeued':requeued,
            'pending': pending,
        })

    return render(request, 'library/libprep_list.html', {
        'batch_data': batch_data,
    })


def libprep_detail(request, batch_id):
    """
    Show the 48-well plate board for a single LibraryPrepBatch.
    Builds a grid: rows A-D, cols 1-6 (48 wells max).
    Each cell is either occupied (sample data) or empty.
    """
    batch = get_object_or_404(
        LibraryPrepBatch.objects.select_related(
            'project', 'project__client', 'workflowType', 'plate'
        ),
        pk=batch_id,
    )

    # All samples for this batch, keyed by well_position for O(1) lookup
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

    # Build the 48-well grid 
    # The physical plate is 96-well but the batch uses max 48 wells (~30 samples + 2 controls + spare)
    ROWS = ['A', 'B', 'C', 'D', 'E', 'F', 'G' , 'H']   
    COLS = [f'{c:02d}' for c in range(1, 7)]  # 01 – 06

    grid = []
    for row in ROWS:
        row_cells = []
        for col in COLS:
            pos    = f'{row}{col}'
            sample = sample_map.get(pos)
            row_cells.append({
                'position': pos,
                'sample':   sample,
                'occupied': sample is not None,
                'is_control': (
                    sample.plateWell.well_type == 'control'
                    if sample and sample.plateWell else False
                ),
            })
        grid.append({'row_letter': row, 'cells': row_cells})

    # Stats for the header banner
    total    = len(sample_map)
    prepped  = sum(1 for s in sample_map.values() if s.prepAction == 'prep')
    pending  = sum(1 for s in sample_map.values() if s.prepAction not in ('prep', 'skip', 'requeue'))

    return render(request, 'library/libprep_detail.html', {
        'batch':   batch,
        'grid':    grid,
        'cols':    COLS,
        'total':   total,
        'prepped': prepped,
        'pending': pending,
    })