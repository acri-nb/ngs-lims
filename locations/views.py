import json
import re
from datetime import timedelta

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.utils import timezone
from django.db.models import Avg, Max, Min, Count, Q
from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.core.exceptions import ValidationError
from django.contrib.auth.decorators import login_required, permission_required
from django.views.decorators.http import require_POST

from .models import Location, Rack, Plate, PlateWell, TempLog

from samples.views_auth import lab_staff_required


# LOCATION LIST (/locations/) logs tab
@lab_staff_required
def location_list(request):
    """
    Shows all locations as cards.
    Each card shows today's log if it exists, or a pre-filled form if not.
    """
    locations = Location.objects.all().order_by('storageType', 'locationName')
    today = timezone.localdate()
    yesterday = today - timedelta(days=1)

    location_data = []
    for loc in locations:
        today_log     = loc.templogs.filter(date_logged=today).first()
        yesterday_log = loc.templogs.order_by('-date_logged').exclude(date_logged=today).first()
        location_data.append({
            'location':     loc,
            'today_log':    today_log,
            'yesterday_log': yesterday_log,
        })

    return render(request, 'locations/location_list.html', {
        'location_data': location_data,
        'today': today,
    })


# ADD TEMP LOG (POST only)
@lab_staff_required
def add_temp_log(request, location_pk):
    """
    Handles the quick-log form submission from either the list or history page.
    Redirects back to wherever the form was submitted from.
    """
    location = get_object_or_404(Location, pk=location_pk)

    if request.method != 'POST':
        return redirect('location-list')

    next_url = request.POST.get('next', 'location-list')

    try:
        today = timezone.localdate()

        existing = TempLog.objects.filter(location=location, date_logged=today).first()
        if existing:
            edit_url = f"/locations/log/{existing.temp_log_id}/edit/"
            messages.warning(
                request,
                f"{location.locationName} has already been logged today. "
                f"<a href='{edit_url}'>Edit today's log</a> if you need to correct it."
            )
        else:
            log = TempLog(
                location=location,
                current_temp_c=request.POST['current_temp_c'],
                max_temp_c=request.POST['max_temp_c'],
                min_temp_c=request.POST['min_temp_c'],
            )

            if location.storageType == Location.ROOMTEMPATURE:
                max_h = request.POST.get('max_humidity') or None
                min_h = request.POST.get('min_humidity') or None
                log.max_humidity = max_h
                log.min_humidity = min_h

            log.logged_by = request.user
            log.save()
            messages.success(request, f"Temperature logged for {location.locationName}.")

    except ValidationError as e:
        for field, errors in e.message_dict.items():
            for error in errors:
                messages.error(request, f"{field}: {error}")
    except IntegrityError:
        messages.warning(request, f"{location.locationName} has already been logged today.")
    except Exception as e:
        messages.error(request, f"Could not save log: {e}")

    if next_url.startswith('/'):
        return redirect(next_url)
    return redirect('location-list')


# LOCATION HISTORY (/locations/<pk>/history/)
@lab_staff_required
def location_log_history(request, location_pk):
    """
    Full temperature log history for a single location.
    Also shows a quick form to add today's log if not yet done.
    """
    location  = get_object_or_404(Location, pk=location_pk)
    today     = timezone.localdate()
    today_log = location.templogs.filter(date_logged=today).first()
    latest_log = location.templogs.order_by('-date_logged').first()

    all_logs  = location.templogs.order_by('-date_logged')
    paginator = Paginator(all_logs, 30)
    page      = request.GET.get('page', 1)
    logs      = paginator.get_page(page)

    thirty_days_ago = today - timedelta(days=30)
    recent = location.templogs.filter(date_logged__gte=thirty_days_ago)
    stats  = recent.aggregate(
        avg_temp=Avg('current_temp_c'),
        highest_max=Max('max_temp_c'),
        lowest_min=Min('min_temp_c'),
        days_logged=Count('temp_log_id'),
    )

    return render(request, 'locations/location_history.html', {
        'location':    location,
        'logs':        logs,
        'today':       today,
        'today_log':   today_log,
        'latest_log':  latest_log,
        'avg_temp':    stats['avg_temp'] or 0,
        'highest_max': stats['highest_max'] or 0,
        'lowest_min':  stats['lowest_min'] or 0,
        'days_logged': stats['days_logged'] or 0,
    })


# For /locations/history/
@lab_staff_required
def location_history_index(request):
    locations = Location.objects.all().order_by('storageType', 'locationName')
    today = timezone.localdate()

    for loc in locations:
        loc.last_log = loc.templogs.order_by('-date_logged').first()

    return render(request, 'locations/location_history_index.html', {
        'locations': locations,
        'today': today,
    })


# For (/locations/log/<pk>/edit/)
@login_required
@permission_required('locations.change_templog', raise_exception=True)
def edit_temp_log(request, log_pk):
    log = get_object_or_404(TempLog, pk=log_pk)

    if request.method == 'POST':
        try:
            log.current_temp_c = request.POST['current_temp_c']
            log.max_temp_c     = request.POST['max_temp_c']
            log.min_temp_c     = request.POST['min_temp_c']
            if log.location.storageType == Location.ROOMTEMPATURE:
                log.max_humidity = request.POST.get('max_humidity') or None
                log.min_humidity = request.POST.get('min_humidity') or None
            log.save()
            messages.success(request, "Log updated.")
        except (ValidationError, Exception) as e:
            messages.error(request, f"Could not update: {e}")
        return redirect('location-log-history', location_pk=log.location.pk)

    return render(request, 'locations/edit_log.html', {'log': log})


PLATE_ROWS = list('ABCDEFGH')       # 8 rows
PLATE_COLS = [f'{c:02d}' for c in range(1, 13)]   # 01-12

def _build_96_grid(plate):
    """
    Return a list of row dicts for a 96-well plate.
    Each cell: {'position': 'A01', 'well': <PlateWell|None>, 'occupied': bool}
    """
    wells_qs = plate.wells.select_related(
        'sample',
        'sample__specimen',
        'sample__specimen__case',
        'sample__specimen__case__client',
    ).prefetch_related(
        'libraryPrepSamples',
        'libraryPrepSamples__libPrepBatch',
        'libraryPrepSamples__libraryIndex',
        'libraryPrepSamples__qcResult',
        'sample__qc_results',
    )
    well_map = {w.well_position: w for w in wells_qs}

    grid = []
    for row in PLATE_ROWS:
        cells = []
        for col in PLATE_COLS:
            pos  = f'{row}{col}'
            well = well_map.get(pos)
            cells.append({
                'position': pos,
                'well':     well,
                'occupied': well is not None and well.well_type != 'empty',
            })
        grid.append({'row_letter': row, 'cells': cells})
    return grid

@lab_staff_required
def rack_detail(request, rack_pk):

    rack = get_object_or_404(
        Rack.objects.select_related('location').prefetch_related('plates__wells'),
        pk=rack_pk,
    )
    plate_map = {p.rack_location: p for p in rack.plates.all() if p.rack_location}
    rows = [chr(65 + r) for r in range(rack.rows)]
    cols = list(range(1, rack.cols + 1))

    grid = []
    for row in rows:
        row_cells = []
        for col in cols:
            slot  = f'{row}{col}'
            plate = plate_map.get(slot)
            count = plate.wells.filter(
                well_type__in=['sample', 'library', 'sequencing', 'control']
            ).count() if plate else 0
            row_cells.append({
                'slot':  slot,
                'plate': plate,
                'count': count,
                'empty': plate is None,
            })
        grid.append({'row': row, 'cells': row_cells})

    return render(request, 'locations/rack_detail.html', {
        'rack': rack,
        'grid': grid,
        'cols': cols,
    })

@lab_staff_required
def plate_detail(request, plate_pk):
    """96-well plate board click a well to see its contents."""
    plate = get_object_or_404(
        Plate.objects.select_related('location', 'rack'),
        pk=plate_pk,
    )
    grid = _build_96_grid(plate)

    total    = plate.wells.count()
    occupied = plate.wells.exclude(well_type='empty').count()

    return render(request, 'locations/plate_detail.html', {
        'plate':    plate,
        'grid':     grid,
        'cols':     PLATE_COLS,
        'total':    total,
        'occupied': occupied,
        'empty':    96 - occupied,
    })

@lab_staff_required
def well_detail(request, well_pk):
    """
    Single well: shows sample info + full pipeline summary.
    more detail will be added later.
    """
    well = get_object_or_404(
        PlateWell.objects.select_related(
            'plate',
            'plate__rack',
            'plate__location',
            'sample',
            'sample__specimen',
            'sample__specimen__case',
            'sample__specimen__case__client',
            'sample__project',
            'sample__project__client',
            'sample__location',
        ).prefetch_related(
            'sample__qc_results__batch',
            'libraryPrepSamples__libPrepBatch__workflowType',
            'libraryPrepSamples__libraryIndex',
            'libraryPrepSamples__qcResult',
        ),
        pk=well_pk,
    )

    sample      = well.sample
    qc_results  = sample.qc_results.all().order_by('-created_at') if sample else []
    lib_samples = well.libraryPrepSamples.all() if sample else []

    return render(request, 'locations/well_detail.html', {
        'well':        well,
        'sample':      sample,
        'qc_results':  qc_results,
        'lib_samples': lib_samples,
    })

@lab_staff_required
def inventory_search(request):
    """
    AJAX endpoint, returns JSON list of matches.
    Searches by sample name, plate name, UDI number.
    GET ?q=<query>
    """
    q = request.GET.get('q', '').strip()
    results = []

    if len(q) >= 2:
        wells = PlateWell.objects.select_related(
            'plate', 'plate__rack', 'plate__location', 'sample'
        ).filter(
            Q(sample__sample_name__icontains=q) |
            Q(plate__plate_name__icontains=q)   |
            Q(libraryPrepSamples__libraryIndex__udi_number__icontains=q)
        ).distinct()[:20]

        for w in wells:
            results.append({
                'well_pk':      w.pk,
                'well_pos':     w.well_position,
                'well_type':    w.well_type,
                'plate_name':   w.plate.plate_name,
                'plate_pk':     w.plate.pk,
                'rack_name':    w.plate.rack.rack_name if w.plate.rack else '—',
                'location':     w.plate.location.locationName if w.plate.location else '—',
                'sample_name':  w.sample.sample_name if w.sample else '—',
                'sample_type':  w.sample.sample_type if w.sample else '—',
            })

    return JsonResponse({'results': results, 'count': len(results)})


"""
rack_location on Plate uses:  "A1T" (top) or "A1B" (bottom)
"""
@lab_staff_required
def inventory_home(request):
    """
    Shows all racks as cards (one card per rack).
    Each card shows the 4×4 slot grid where every slot has
    a TOP and BOTTOM sub-cell (max 2 plates per slot = 32 total).
    Location name is shown inside each rack card, no location
    section headers, empty locations are hidden.
    """
    racks = Rack.objects.select_related('location').prefetch_related(
        'plates__wells'
    ).order_by('location__locationName', 'rack_name')

    rack_data = []
    for rack in racks:
        plate_map = {}
        for p in rack.plates.all():
            key = p.rack_location.upper() if p.rack_location else ''
            if key:
                plate_map[key] = p

        rows = [chr(65 + r) for r in range(rack.rows)]
        cols = list(range(1, rack.cols + 1))

        grid = []
        for row in rows:
            row_cells = []
            for col in cols:
                base = f'{row}{col}'
                top_plate  = plate_map.get(f'{base}T') or plate_map.get(base)
                bot_plate  = plate_map.get(f'{base}B')

                def _count(plate):
                    if not plate:
                        return 0
                    return plate.wells.filter(
                        well_type__in=['sample', 'library', 'sequencing', 'control']
                    ).count()

                row_cells.append({
                    'slot':       base,
                    'top':        top_plate,
                    'top_count':  _count(top_plate),
                    'bot':        bot_plate,
                    'bot_count':  _count(bot_plate),
                    'both_empty': top_plate is None and bot_plate is None,
                })
            grid.append({'row': row, 'cells': row_cells})

        total_plates   = rack.plates.count()
        total_capacity = rack.rows * rack.cols * 2

        rack_data.append({
            'rack':           rack,
            'grid':           grid,
            'cols':           cols,
            'total_plates':   total_plates,
            'total_capacity': total_capacity,
        })

    return render(request, 'locations/rack_home.html', {
        'rack_data': rack_data,
    })


# ---------------------------------------------------------------------------
# MOVE PLATE — rack/slot relocation endpoints
# ---------------------------------------------------------------------------

SLOT_RE = re.compile(r'^[A-D][1-4][TB]$')

@lab_staff_required
def rack_slots_json(request, rack_pk):
    """
    AJAX endpoint: returns occupancy for every slot in a rack so the
    'move plate' modal can grey out / block taken sub-slots.
    GET /locations/rack/<rack_pk>/slots/
    """
    rack = get_object_or_404(Rack, pk=rack_pk)
    plate_map = {}
    for p in rack.plates.all():
        if p.rack_location:
            plate_map[p.rack_location.upper()] = p

    rows = [chr(65 + r) for r in range(rack.rows)]
    cols = list(range(1, rack.cols + 1))

    slots = []
    for row in rows:
        for col in cols:
            base = f'{row}{col}'
            for suffix in ('T', 'B'):
                key = f'{base}{suffix}'
                plate = plate_map.get(key)
                slots.append({
                    'slot': key,
                    'occupied': plate is not None,
                    'plate_name': plate.plate_name if plate else None,
                    'plate_pk': plate.pk if plate else None,
                })

    return JsonResponse({
        'rack_pk': rack.pk,
        'rack_name': rack.rack_name,
        'rows': rows,
        'cols': cols,
        'slots': slots,
    })

@lab_staff_required
def rack_list_json(request):
    """AJAX endpoint: all racks for the 'move plate' rack dropdown."""
    racks = Rack.objects.select_related('location').order_by(
        'location__locationName', 'rack_name'
    )
    data = [{
        'pk': r.pk,
        'rack_name': r.rack_name,
        'location_name': r.location.locationName,
        'location_pk': r.location_id,
        'rows': r.rows,
        'cols': r.cols,
    } for r in racks]
    return JsonResponse({'racks': data})


@lab_staff_required
@require_POST
def move_plate(request, plate_pk):
    """
    AJAX endpoint to relocate a plate to a new rack/slot.
    POST body (JSON or form-encoded): { rack_pk: <int>, slot: 'A1T' }
    """
    plate = get_object_or_404(Plate, pk=plate_pk)

    if request.content_type == 'application/json':
        try:
            body = json.loads(request.body or '{}')
        except json.JSONDecodeError:
            return JsonResponse({'ok': False, 'error': 'Invalid JSON body.'}, status=400)
    else:
        body = request.POST

    rack_pk = body.get('rack_pk')
    slot    = (body.get('slot') or '').strip().upper()

    if not rack_pk or not slot:
        return JsonResponse({'ok': False, 'error': 'rack_pk and slot are required.'}, status=400)

    if not SLOT_RE.match(slot):
        return JsonResponse({'ok': False, 'error': "Slot must look like 'A1T' or 'A1B'."}, status=400)

    target_rack = get_object_or_404(Rack.objects.select_related('location'), pk=rack_pk)

    row_letter = slot[0]
    col_num = int(slot[1])
    row_index = ord(row_letter) - 65
    if row_index >= target_rack.rows or col_num > target_rack.cols:
        return JsonResponse({
            'ok': False,
            'error': f"Slot {slot} is outside {target_rack.rack_name}'s {target_rack.rows}×{target_rack.cols} grid."
        }, status=400)

    with transaction.atomic():
        clash = Plate.objects.filter(
            rack=target_rack, rack_location__iexact=slot
        ).exclude(pk=plate.pk).first()
        if clash:
            return JsonResponse({
                'ok': False,
                'error': f"Slot {slot} on {target_rack.rack_name} is already occupied by '{clash.plate_name}'."
            }, status=409)

        plate.rack = target_rack
        plate.location = target_rack.location
        plate.rack_location = slot

        try:
            plate.full_clean()
        except ValidationError as e:
            return JsonResponse({'ok': False, 'error': '; '.join(
                f'{k}: {", ".join(v)}' for k, v in e.message_dict.items()
            )}, status=400)

        plate.save()

    return JsonResponse({
        'ok': True,
        'plate_pk': plate.pk,
        'plate_name': plate.plate_name,
        'rack_pk': target_rack.pk,
        'rack_name': target_rack.rack_name,
        'location_name': target_rack.location.locationName,
        'slot': slot,
    })