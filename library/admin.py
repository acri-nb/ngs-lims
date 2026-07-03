from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from .models import (
    WorkflowType,
    StepRow,
    WorkflowTypeStep,
    WorkflowStepRowOrder,
    IndexKit,
    LibraryIndex,
    LibraryPrepBatch,
    LibraryPrepBatchAuditLog,
    LibraryPrepSample,
    LibraryQCBatch,
    LibraryQC,
)



#  Workflow Templates (WorkflowType → WorkflowTypeStep → WorkflowStepRowOrder)

@admin.register(StepRow)
class StepRowAdmin(admin.ModelAdmin):
    """
    The reagent catalog. Add a reagent here once, then drop it into as many
    workflow steps as needed (via the step's page) 
    """
    list_display = ("stepRowName", "sort_order", "used_in_steps")
    search_fields = ("stepRowName",)
    ordering = ("sort_order", "stepRowName")

    @admin.display(description="Used in # steps")
    def used_in_steps(self, obj):
        return obj.workflowSteps.count()


class WorkflowStepRowOrderInline(admin.TabularInline):
    """
    The reagent rows for ONE step, in print order. This is what actually
    generates the master-mix sheet, so sort_order here = row order on the
    printed sheet.
    """
    model = WorkflowStepRowOrder
    extra = 1
    autocomplete_fields = ["step_row"]
    fields = ("sort_order", "step_row", "constantOfMM", "volumePerRxn")
    ordering = ("sort_order",)
    verbose_name = "Reagent Row"
    verbose_name_plural = "Reagent Rows — printed on the sheet in this order"


@admin.register(WorkflowTypeStep)
class WorkflowTypeStepAdmin(admin.ModelAdmin):
    """
    One step of one workflow. Reached
    by clicking a step's "Change" link from the WorkflowType page. Edit the
    step's reagent rows here.
    """
    list_display = ("stepName", "workflowType", "sort_order", "is_stopping_point", "row_count")
    list_filter = ("workflowType", "is_stopping_point")
    search_fields = ("stepName", "workflowType__workflowType")
    ordering = ("workflowType", "sort_order")
    fields = ("workflowType", "stepName", "sort_order", "is_stopping_point")
    inlines = [WorkflowStepRowOrderInline]

    @admin.display(description="# rows")
    def row_count(self, obj):
        return obj.stepRows.count()


class WorkflowTypeStepInline(admin.TabularInline):
    """
    Shows a workflow's steps in print order, right on the WorkflowType page.
    Add new steps here, reorder with sort_order, then click a step's
    "Change" link (bottom-right of its row, once saved) to edit its
    reagents.
    """
    model = WorkflowTypeStep
    extra = 1
    fields = ("sort_order", "stepName", "is_stopping_point", "row_count_display")
    readonly_fields = ("row_count_display",)
    ordering = ("sort_order",)
    show_change_link = True
    verbose_name = "Step"
    verbose_name_plural = (
        "Workflow Steps — in print order. Save first, then use each row's "
        "'Change' link to edit its reagents."
    )

    @admin.display(description="Reagent rows")
    def row_count_display(self, obj):
        if obj and obj.pk:
            return f"{obj.stepRows.count()} row(s)"
        return "— save step first —"


@admin.register(WorkflowType)
class WorkflowTypeAdmin(admin.ModelAdmin):
    list_display = (
        "workflowType",
        "sample_type",
        "read_length_type",
        "qc_method",
        "requires_pcr",
        "uses_controls",
        "step_count",
    )
    list_filter = ("sample_type", "read_length_type", "qc_method", "requires_pcr", "uses_controls")
    search_fields = ("workflowType",)
    ordering = ("workflowType",)
    inlines = [WorkflowTypeStepInline]

    fieldsets = (
        (None, {
            "fields": ("workflowType", "sample_type", "read_length_type"),
        }),
        ("Library QC gates", {
            "fields": ("qc_method", "min_nm_threshold", "fragment_min_bp", "fragment_max_bp", "dimer_threshold_pct"),
            "description": "These drive LibraryQC.calculate_qc_status() — the automatic pass/fail on the QC step.",
        }),
        ("Prep defaults", {
            "fields": ("requires_pcr", "uses_controls", "target_input_ng", "target_volume_ul", "diluent_name"),
        }),
    )

    @admin.display(description="# steps")
    def step_count(self, obj):
        return obj.steps.count()


#  Index Kits
@admin.register(IndexKit)
class IndexKitAdmin(admin.ModelAdmin):
    list_display = ("name", "workflowType", "index_count", "notes")
    list_filter = ("workflowType",)
    search_fields = ("name",)
    ordering = ("name",)

    @admin.display(description="# indexes")
    def index_count(self, obj):
        count = obj.indexes.count()
        app_label = LibraryIndex._meta.app_label
        url = reverse(f"admin:{app_label}_libraryindex_changelist") + f"?indexKit__id__exact={obj.id}"
        return format_html('<a href="{}">{} wells</a>', url, count)


@admin.register(LibraryIndex)
class LibraryIndexAdmin(admin.ModelAdmin):
    """
    Registered separately (rather than inlined on IndexKit) since a kit can
    have 96–384+ wells — better browsed/filtered here than loaded all at
    once on the kit page.
    """
    list_display = ("indexKit", "plateSet", "well", "udi_number", "i7Sequence", "i5Sequence")
    list_filter = ("indexKit", "plateSet")
    search_fields = ("udi_number", "well", "indexKit__name", "i7Sequence", "i5Sequence")
    ordering = ("indexKit", "plateSet", "well")
    autocomplete_fields = ["indexKit"]


#  Library Prep Batches
class LibraryPrepSampleInline(admin.TabularInline):
    model = LibraryPrepSample
    extra = 0
    fields = (
        "planned_well_position",
        "sampleQC",
        "libraryIndex",
        "prepAction",
        "concentrationInput",
        "volumeSample_ul",
        "volumeDiluent_ul",
        "actual_Input_ng",
        "PCRCycles",
        "speedVacRequired",
    )
    raw_id_fields = ["sampleQC"]  # cross-app FK (qc.SampleQC); avoids relying on its admin config
    autocomplete_fields = ["libraryIndex"]
    ordering = ("planned_well_position",)
    show_change_link = True


class LibraryPrepBatchAuditLogInline(admin.TabularInline):
    """Read-only timeline. Entries are only ever written by views, never edited here."""
    model = LibraryPrepBatchAuditLog
    extra = 0
    fields = ("changed_at", "action", "changed_by", "detail")
    readonly_fields = fields
    can_delete = False
    ordering = ("-changed_at",)

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(LibraryPrepBatch)
class LibraryPrepBatchAdmin(admin.ModelAdmin):
    list_display = (
        "batch_name",
        "project",
        "workflowType",
        "datePrepped",
        "sample_count",
        "control_count",
        "createdBy",
    )
    list_filter = ("workflowType", "datePrepped", "project")
    search_fields = ("batch_name", "notes")
    date_hierarchy = "datePrepped"
    ordering = ("-datePrepped",)
    raw_id_fields = ["project", "plate"]  # cross-app FKs (samples.Project, locations.Plate)
    autocomplete_fields = ["workflowType"]
    readonly_fields = ("batch_name", "created_at", "updated_at")
    inlines = [LibraryPrepSampleInline, LibraryPrepBatchAuditLogInline]

    fieldsets = (
        (None, {
            "fields": ("batch_name", "project", "plate", "workflowType", "datePrepped"),
        }),
        ("Details", {
            "fields": ("max_samples", "notes", "createdBy", "created_at", "updated_at"),
        }),
    )

    @admin.display(description="Samples")
    def sample_count(self, obj):
        return obj.sample_count

    @admin.display(description="Controls")
    def control_count(self, obj):
        return obj.control_count


@admin.register(LibraryPrepSample)
class LibraryPrepSampleAdmin(admin.ModelAdmin):
    """
    Registered standalone mainly so this model can be searched via
    autocomplete_fields elsewhere (e.g. LibraryQC below); day-to-day editing
    normally happens through the LibraryPrepBatch inline instead.
    """
    list_display = ("__str__", "libPrepBatch", "planned_well_position", "prepAction", "libraryIndex")
    list_filter = ("prepAction", "libPrepBatch__workflowType")
    search_fields = ("planned_well_position", "libPrepBatch__batch_name", "sampleQC__sample__sample_name")
    raw_id_fields = ["sampleQC", "plateWell"]
    autocomplete_fields = ["libraryIndex"]


@admin.register(LibraryPrepBatchAuditLog)
class LibraryPrepBatchAuditLogAdmin(admin.ModelAdmin):
    """Read-only ledger — nothing here should ever be created/edited/deleted by hand."""
    list_display = ("batch", "action", "changed_by", "changed_at")
    list_filter = ("action", "changed_at")
    search_fields = ("batch__batch_name", "detail")
    date_hierarchy = "changed_at"
    ordering = ("-changed_at",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


#  Library QC

class LibraryQCInline(admin.TabularInline):
    model = LibraryQC
    extra = 0
    fields = (
        "libPrepSample",
        "qubit_ng_ul",
        "fragmentSizesAvgBP",
        "nmCalculated",
        "dimerPeak_pct",
        "QCstatus",
    )
    readonly_fields = ("nmCalculated",)  # auto-computed in LibraryQC.save()
    autocomplete_fields = ["libPrepSample"]


@admin.register(LibraryQCBatch)
class LibraryQCBatchAdmin(admin.ModelAdmin):
    list_display = ("batchName", "libPrepBatch", "dateQCed", "createdBy", "pass_fail_summary")
    list_filter = ("dateQCed",)
    search_fields = ("batchName", "libPrepBatch__batch_name")
    date_hierarchy = "dateQCed"
    raw_id_fields = ["libPrepBatch"]
    inlines = [LibraryQCInline]

    @admin.display(description="Results")
    def pass_fail_summary(self, obj):
        results = obj.qcResults.all()
        total = results.count()
        if not total:
            return "—"
        passed = sum(1 for r in results if r.QCstatus == "pass")
        failed = sum(1 for r in results if r.QCstatus == "fail")
        return f"{passed}/{total} pass, {failed} fail"


@admin.register(LibraryQC)
class LibraryQCAdmin(admin.ModelAdmin):
    """
    Registered standalone too, for spot-checking/searching individual QC
    results outside the batch view (e.g. "find every failed sample this
    month").
    """
    list_display = (
        "libPrepSample",
        "libQCBatch",
        "qubit_ng_ul",
        "fragmentSizesAvgBP",
        "nmCalculated",
        "dimerPeak_pct",
        "status_badge",
    )
    list_filter = ("QCstatus", "libQCBatch")
    search_fields = ("libPrepSample__planned_well_position", "libQCBatch__batchName")
    readonly_fields = ("nmCalculated",)
    autocomplete_fields = ["libPrepSample", "libQCBatch"]

    _STATUS_COLORS = {"pass": "#1a7f37", "fail": "#cf222e", "caution": "#9a6700", "pending": "#57606a"}

    @admin.display(description="Status")
    def status_badge(self, obj):
        color = self._STATUS_COLORS.get(obj.QCstatus, "#000000")
        return format_html(
            '<strong style="color:{};">{}</strong>', color, obj.get_QCstatus_display()
        )