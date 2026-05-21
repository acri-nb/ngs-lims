from django.contrib import admin
from .models import Location, TempLog


class TempLogInline(admin.TabularInline):
    model = TempLog
    extra = 0
    fields = [
        'date_logged',
        'current_temp_c',
        'max_temp_c',
        'min_temp_c',
        'max_humidity',
        'min_humidity'
    ]
    readonly_fields = ['date_logged']

@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ['locationName', 'storageType', 'temp_log_count']
    list_filter = ['storageType']
    search_fields = ['locationName']
    inlines = [TempLogInline]

    #@admin.display(description='# Temp Logs')
    def temp_log_count(self, obj):
        return obj.templogs.count() 


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