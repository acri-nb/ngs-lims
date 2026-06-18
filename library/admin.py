from django.contrib import admin
from .models import (
    WorkflowType,
    StepRow,
    WorkflowTypeStep,
    WorkflowStepRowOrder,
    LibraryIndex,
    LibraryPrepBatch,
    LibraryPrepSample,
    LibraryQCBatch,
    LibraryQC,
    PrepAction,
    QCStatus,
)

class WorkflowStepRowOrderInline(admin.TabularInline):
    model = WorkflowStepRowOrder
    extra = 1
    autocomplete_fields = ['step_row']


class WorkflowTypeStepInline(admin.StackedInline):
    model = WorkflowTypeStep
    extra = 1
    show_change_link = True

    fields = (
        'stepName',
        'sort_order',
        'numberOFReaction',
    )


class LibraryPrepSampleInline(admin.TabularInline):
    model = LibraryPrepSample
    extra = 0
    autocomplete_fields = ['sampleQC', 'plateWell', 'libraryIndex']
    fields = (
        'sampleQC',
        'plateWell',
        'libraryIndex',
        'volumeSample_ul',
        'volumeDiluent_ul',
        'prepAction',
    )
    readonly_fields = ('volumeSample_ul', 'volumeDiluent_ul')


class LibraryQCInline(admin.TabularInline):
    model = LibraryQC
    extra = 0
    readonly_fields = ('nmCalculated',)
    fields = (
        'libPrepSample',
        'qubit_ng_ul',
        'fragmentSizesAvgBP',
        'nmCalculated',
        'QCstatus',
    )


@admin.register(WorkflowType)
class WorkflowTypeAdmin(admin.ModelAdmin):
    list_display = (
        'workflowType',
        'sample_type',
        'target_input_ng',
        'target_volume_ul',
        'diluent_name',
    )
    search_fields = ('workflowType',)
    list_filter = ('sample_type',)
    inlines = [WorkflowTypeStepInline]


@admin.register(StepRow)
class StepRowAdmin(admin.ModelAdmin):
    list_display = ('stepRowName', 'volumePerRxn', 'constantOfMM', 'sort_order')
    list_filter = ('constantOfMM',)
    search_fields = ('stepRowName',)
    ordering = ('sort_order',)


@admin.register(WorkflowTypeStep)
class WorkflowTypeStepAdmin(admin.ModelAdmin):
    list_display = ('stepName', 'workflowType', 'sort_order', 'numberOFReaction')
    list_filter = ('workflowType',)
    search_fields = ('stepName',)
    inlines = [WorkflowStepRowOrderInline]


@admin.register(WorkflowStepRowOrder)
class WorkflowStepRowOrderAdmin(admin.ModelAdmin):
    list_display = ('step', 'step_row', 'sort_order')
    list_filter = ('step',)
    autocomplete_fields = ('step', 'step_row')


@admin.register(LibraryIndex)
class LibraryIndexAdmin(admin.ModelAdmin):
    list_display = (
        'udi_number',
        'plateSet',
        'well',
        'i7Sequence',
        'i5Sequence',
        'indexVersion',
        'createdBy',
    )
    list_filter = ('plateSet', 'indexVersion', 'workflow_types')
    search_fields = ('udi_number', 'well', 'i7Sequence', 'i5Sequence')
    autocomplete_fields = ('workflow_types', 'createdBy')


@admin.register(LibraryPrepBatch)
class LibraryPrepBatchAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'workflowType',
        'project',
        'plate',
        'datePrepped',
        'max_samples',
        'createdBy',
    )
    list_filter = ('workflowType', 'datePrepped')
    search_fields = ('project__name', 'plate__plate_name')
    autocomplete_fields = ('project', 'plate', 'workflowType', 'createdBy')
    inlines = [LibraryPrepSampleInline]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'workflowType', 'project', 'plate'
        )


@admin.register(LibraryPrepSample)
class LibraryPrepSampleAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'libPrepBatch',
        'sampleQC',
        'plateWell',
        'libraryIndex',
        'prepAction',
        'volumeSample_ul',
        'volumeDiluent_ul',
    )
    list_filter = ('prepAction', 'libPrepBatch')
    search_fields = ('sampleQC__sample__sample_name',)
    autocomplete_fields = (
        'libPrepBatch',
        'sampleQC',
        'plateWell',
        'libraryIndex',
        'createdBy',
    )

@admin.register(LibraryQCBatch)
class LibraryQCBatchAdmin(admin.ModelAdmin):
    list_display = ('id', 'batchName', 'libPrepBatch', 'dateQCed', 'createdBy')
    list_filter = ('dateQCed',)
    search_fields = ('batchName',)
    autocomplete_fields = ('libPrepBatch', 'createdBy')
    inlines = [LibraryQCInline]


@admin.register(LibraryQC)
class LibraryQCAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'libQCBatch',
        'libPrepSample',
        'qubit_ng_ul',
        'fragmentSizesAvgBP',
        'nmCalculated',
        'QCstatus',
    )
    list_filter = ('QCstatus',)
    search_fields = ('libPrepSample__id',)
    autocomplete_fields = ('libQCBatch', 'libPrepSample', 'createdBy')
    readonly_fields = ('nmCalculated',)