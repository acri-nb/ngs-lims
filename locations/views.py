from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.utils import timezone
from django.db.models import Avg, Max, Min, Count
from django.db import IntegrityError
from datetime import timedelta

from .models import Location, TempLog
from django.core.paginator import Paginator
from django.core.exceptions import ValidationError
from django.contrib.auth.decorators import login_required

# LOCATION LIST (/locations/)
@login_required
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
@login_required
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

        # Check for an existing log before attempting to save
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

            # Only set humidity for room-temp locations
            if location.storageType == Location.ROOMTEMPATURE:
                max_h = request.POST.get('max_humidity') or None
                min_h = request.POST.get('min_humidity') or None
                log.max_humidity = max_h
                log.min_humidity = min_h

            log.logged_by = request.user
            log.save()   # calls full_clean() via model's save()
            messages.success(request, f"Temperature logged for {location.locationName}.")

    except ValidationError as e:
        # Flatten the error dict into readable messages
        for field, errors in e.message_dict.items():
            for error in errors:
                messages.error(request, f"{field}: {error}")
    except IntegrityError:
        messages.warning(request, f"{location.locationName} has already been logged today.")
    except Exception as e:
        messages.error(request, f"Could not save log: {e}")

    # If next_url looks like a full URL path, redirect there; otherwise go to list
    if next_url.startswith('/'):
        return redirect(next_url)
    return redirect('location-list')


# LOCATION HISTORY (/locations/<pk>/history/)
@login_required
def location_log_history(request, location_pk):
    """
    Full temperature log history for a single location.
    Also shows a quick form to add today's log if not yet done.
    """
    location  = get_object_or_404(Location, pk=location_pk)
    today     = timezone.localdate()
    today_log = location.templogs.filter(date_logged=today).first()
    latest_log = location.templogs.order_by('-date_logged').first()

    # Paginated log list
    all_logs  = location.templogs.order_by('-date_logged')
    paginator = Paginator(all_logs, 30)
    page      = request.GET.get('page', 1)
    logs      = paginator.get_page(page)

    # Stats for the last 30 days
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
@login_required
def location_history_index(request):
    locations = Location.objects.all().order_by('storageType', 'locationName')
    today = timezone.localdate()
    
    # Add last-logged date to each location for context
    for loc in locations:
        loc.last_log = loc.templogs.order_by('-date_logged').first()
    
    return render(request, 'locations/location_history_index.html', {
        'locations': locations,
        'today': today,
    })

from django.contrib.auth.decorators import permission_required

# For (/locations/log/<pk>/edit/)
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