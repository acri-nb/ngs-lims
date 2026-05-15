from django.contrib import admin
from .models import SampleQCBatch, BatchSample, SampleQC


class BatchSampleInline(admin.TabularInline):
    """
    Shows all samples assigned to a batch directly on the batch page.
    You can add/remove samples from a batch without leaving the batch form.
    """
    model = BatchSample
    extra = 1
    autocomplete_fields = ['sample']    # search box instead of a giant dropdown


class SampleQCInline(admin.TabularInline):
    """
    Shows all QC results for a batch on the batch page.
    Read-only here — edit individual results from their own page.
    """
    model = SampleQC
    extra = 0
    fields = ['sample', 'qc_status', 'qubit_nm', 'rin', 'dv200', 'nanodrop_260_230', 'notes']
    readonly_fields = ['created_at', 'updated_at']

    def get_readonly_fields(self, request, obj=None):
        # once a QC result exists, make sample field read-only to prevent re-assignment
        if obj:
            return self.readonly_fields + ['sample']
        return self.readonly_fields


@admin.register(SampleQCBatch)
class SampleQCBatchAdmin(admin.ModelAdmin):
    list_display = ['batch_name', 'date_batched', 'created_by', 'sample_count']
    search_fields = ['batch_name', 'created_by']
    ordering = ['-date_batched']
    inlines = [BatchSampleInline, SampleQCInline]

    # show sample_count property in the list
    @admin.display(description='# Samples')
    def sample_count(self, obj):
        return obj.sample_count


@admin.register(BatchSample)
class BatchSampleAdmin(admin.ModelAdmin):
    list_display = ['batch', 'sample']
    search_fields = ['batch__batch_name', 'sample__sample_name']
    list_filter = ['batch']
    autocomplete_fields = ['sample', 'batch']


@admin.register(SampleQC)
class SampleQCAdmin(admin.ModelAdmin):
    list_display = [
        'sample', 'batch', 'qc_status',
        'qubit_nm', 'rin', 'dv200', 'nanodrop_260_230',
        'created_at'
    ]
    search_fields = ['sample__sample_name', 'batch__batch_name']
    list_filter = ['qc_status', 'batch']
    readonly_fields = ['created_at', 'updated_at']

    # group fields into sections on the detail page
    fieldsets = (
        ('Sample & Batch', {
            'fields': ('sample', 'batch')
        }),
        ('QC Metrics — Shared', {
            'fields': ('qubit_nm',)
        }),
        ('QC Metrics — RNA only', {
            'fields': ('rin', 'dv200'),
            'classes': ('collapse',),   # collapsed by default, expand when needed
        }),
        ('QC Metrics — DNA only', {
            'fields': ('nanodrop_260_230',),
            'classes': ('collapse',),
        }),
        ('Result', {
            'fields': ('qc_status', 'notes')
        }),
        ('Audit', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )