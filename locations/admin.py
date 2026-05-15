from django.contrib import admin
from .models import Location, Temp_Logs


class TempLogInline(admin.TabularInline):
    """
    Shows recent temperature logs directly on the location page.
    """
    model = Temp_Logs
    extra = 1
    fields = ['dateLogged', 'currentTempC', 'maxTempC', 'minTempC', 'maxHumidity', 'minHumidity']
    readonly_fields = ['dateLogged']    # auto_now_add — can't be edited
    ordering = ['-dateLogged']

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


@admin.register(Temp_Logs)
class TempLogsAdmin(admin.ModelAdmin):
    list_display = [
        'location', 'dateLogged',
        'currentTempC', 'maxTempC', 'minTempC',
        'maxHumidity', 'minHumidity'
    ]
    list_filter = ['location', 'location__storageType']
    search_fields = ['location__locationName']
    readonly_fields = ['dateLogged']
    ordering = ['-dateLogged']

    fieldsets = (
        ('Location & Date', {
            'fields': ('location', 'dateLogged')
        }),
        ('Temperature (°C)', {
            'fields': ('currentTempC', 'maxTempC', 'minTempC')
        }),
        ('Humidity — Rooms only', {
            'fields': ('maxHumidity', 'minHumidity'),
            'classes': ('collapse',),
        }),
    )