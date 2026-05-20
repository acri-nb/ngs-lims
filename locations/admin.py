from django.contrib import admin
from .models import Location, TempLog


class TempLogInline(admin.TabularInline):
    """
    Shows recent temperature logs directly on the location page.
    """
    model = TempLog
    extra = 1
    fields = ['date_logged', 'currentTempC', 'maxTempC', 'minTempC', 'maxHumidity', 'minHumidity']
    readonly_fields = ['date_logged']    # auto_now_add — can't be edited
    ordering = ['-date_logged']

    def get_extra(self, request, obj=None, **kwargs):
        # don't show empty rows when viewing an existing location
        return 0 if obj else 1


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ['locationName', 'storageType', 'temp_log_count']
    list_filter = ['storageType']
    search_fields = ['locationName']
    inlines = [TempLogInline]

    @admin.display(description='# Temp Logs')
    def temp_log_count(self, obj):
        return obj.temp_logs_set.count()


@admin.register(TempLog)
class TempLogAdmin(admin.ModelAdmin):
    list_display = [
        'location', 'date_logged',
        'current_temp_c', 'max_temp_c', 'min_temp_c',
        'max_humidity', 'min_humidity'
    ]
    search_fields = ['location__locationName']
    list_filter = ['location']
    ordering = ['-date_logged']
    autocomplete_fields = ['location']

    fieldsets = (
        ('Location & Date', {
            'fields': ('location', 'date_logged')
        }),
        ('Temperature (°C)', {
            'fields': ('current_temp_c', 'max_temp_c', 'min_temp_c')
        }),
        ('Humidity — Rooms only', {
            'fields': ('max_humidity', 'min_humidity'),
            'classes': ('collapse',),
        }),
    )