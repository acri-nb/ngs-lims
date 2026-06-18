from django.contrib import admin
from .models import Location, TempLog
from .models import Rack, Plate, PlateWell, PlateLayout



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

class TemperatureLogInline(admin.TabularInline):
    model = TempLog
    readonly_fields = ['date_logged']

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
            'fields': ('location', 'logged_by')
        }),
        ('Temperature (°C)', {
            'fields': ('current_temp_c', 'max_temp_c', 'min_temp_c')
        }),
        ('Humidity — Rooms only', {
            'fields': ('max_humidity', 'min_humidity'),
            'classes': ('collapse',),
        }),
    )


class PlateWellInline(admin.TabularInline):
    model = PlateWell
    extra = 0
    autocomplete_fields = ['sample', 'created_by']
    fields = (
        'well_position',
        'well_type',
        'sample',
        'volume_ul',
        'concentration_nm',
    )
    readonly_fields = ('well_position',)  # prevents accidental edits if generated



class PlateInline(admin.TabularInline):
    model = Plate
    extra = 0
    fields = (
        'plate_name',
        'rack_location',
        'plate_format',
        'created_by',
    )
    autocomplete_fields = ['created_by']


@admin.register(Rack)
class RackAdmin(admin.ModelAdmin):
    list_display = (
        'rack_name',
        'location',
        'rows',
        'cols',
        'capacity',
        'occupied_slots',
        'available_slots',
        'created_by',
    )
    list_filter = ('location',)
    search_fields = ('rack_name', 'location__location_name')
    autocomplete_fields = ('location', 'created_by')
    inlines = [PlateInline]

@admin.register(Plate)
class PlateAdmin(admin.ModelAdmin):
    list_display = (
        'plate_name',
        'rack',
        'rack_location',
        'plate_format',
        'rows',
        'cols',
        'well_count',
        'created_by',
    )
    list_filter = ('plate_format', 'rack')
    search_fields = ('plate_name', 'rack__rack_name', 'rack_location')
    autocomplete_fields = ('rack', 'location', 'created_by')

    inlines = [PlateWellInline]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'rack', 'location'
        )

@admin.register(PlateWell)
class PlateWellAdmin(admin.ModelAdmin):
    list_display = (
        'plate',
        'well_position',
        'well_type',
        'sample',
        'volume_ul',
        'concentration_nm',
    )
    list_filter = ('well_type', 'plate')
    search_fields = (
        'plate__plate_name',
        'well_position',
        'sample__sample_name',
    )
    autocomplete_fields = ('plate', 'sample', 'created_by')

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'plate', 'sample'
        )


@admin.register(PlateLayout)
class PlateLayoutAdmin(admin.ModelAdmin):
    list_display = (
        'plate',
        'layout_name',
        'is_committed',
        'created_by',
        'created_at',
    )
    list_filter = ('is_committed', 'created_at')
    search_fields = ('plate__plate_name', 'layout_name')
    autocomplete_fields = ('plate', 'created_by')
    readonly_fields = ('created_at', 'updated_at')

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'plate'
        )
