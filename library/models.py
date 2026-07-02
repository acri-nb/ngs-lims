from django.db import models
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

User = get_user_model()


class WorkflowType(models.Model):
    workflowType = models.CharField(
        max_length=100, unique=True,
        verbose_name=_("Workflow Type"),
    )
    sample_type = models.CharField(
        max_length=10,
        choices=[('DNA', 'DNA'), ('RNA', 'RNA')],
        default='RNA',
        verbose_name=_("Sample Type"),
    )
    target_input_ng = models.FloatField(
        default=250.0,
        verbose_name=_("Target Input (ng)"),
    )
    target_volume_ul = models.FloatField(
        default=11.0,
        verbose_name=_("Target Volume (µL)"),
    )
    diluent_name = models.CharField(
        max_length=80,
        default='NF H₂O',
        verbose_name=_("Diluent Name"),
    )
    fragment_min_bp = models.IntegerField(null=True, blank=True, verbose_name=_("Min Fragment Size (bp)"))
    fragment_max_bp = models.IntegerField(null=True, blank=True, verbose_name=_("Max Fragment Size (bp)"))
    dimer_threshold_pct = models.FloatField( null=True, blank=True, default=None, verbose_name=_("Dimer Threshold (%)"), )

    class Meta:
        ordering = ['workflowType']
        verbose_name        = _("Workflow Type")
        verbose_name_plural = _("Workflow Types")

    def __str__(self):
        return self.workflowType


class StepRow(models.Model):
    stepRowName  = models.CharField(max_length=200, verbose_name=_("Reagent / Row Name"))
    volumePerRxn = models.FloatField(null=True, blank=True, verbose_name=_("Volume per Reaction (µL)"))
    constantOfMM = models.IntegerField(
        default=1,
        choices=[(0, 'Fixed / Header'), (1, 'Per Reaction (×n)')],
        verbose_name=_("Row Type"),
    )
    sort_order = models.PositiveSmallIntegerField(default=0, verbose_name=_("Sort Order"))

    class Meta:
        ordering = ['sort_order', 'stepRowName']
        verbose_name        = _("Step Row")
        verbose_name_plural = _("Step Rows")

    def __str__(self):
        return self.stepRowName


class WorkflowTypeStep(models.Model):
    workflowType     = models.ForeignKey(WorkflowType, on_delete=models.CASCADE, related_name='steps')
    stepName         = models.CharField(max_length=200, verbose_name=_("Step Name"))
    sort_order       = models.PositiveSmallIntegerField(default=0)
    numberOFReaction = models.IntegerField(default=1, verbose_name=_("Reaction Multiplier"))
    stepRows         = models.ManyToManyField(
        StepRow, blank=True, related_name='workflowSteps',
        through='WorkflowStepRowOrder',
    )

    class Meta:
        ordering = ['workflowType', 'sort_order', 'stepName']
        verbose_name        = _("Workflow Type Step")
        verbose_name_plural = _("Workflow Type Steps")

    def __str__(self):
        return f"{self.workflowType} – {self.stepName}"


class WorkflowStepRowOrder(models.Model):
    step       = models.ForeignKey(WorkflowTypeStep, on_delete=models.CASCADE)
    step_row   = models.ForeignKey(StepRow, on_delete=models.CASCADE)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering        = ['sort_order']
        unique_together = [('step', 'step_row')]


# 
#  Index Kits
#
#  An IndexKit represents one physical reagent kit / chemistry from the
#  manufacturer (e.g. "Illumina DNA/RNA UD Indexes v2", "KAPA UDI", a
#  small-RNA UDI kit, etc). 

class IndexKit(models.Model):
    name = models.CharField(
        max_length=100, unique=True,
        verbose_name=_("Index Kit Name"),
        help_text=_("e.g. 'ILLMN-DNA-RNA-V2', 'KAPA-UDI', 'sRNA-V4'."),
    )
    workflowType = models.ForeignKey(
        WorkflowType,
        on_delete=models.PROTECT,
        related_name='indexKits',
        verbose_name=_("Workflow Type"),
        help_text=_("The prep workflow this kit's indexes are used with."),
    )
    notes = models.TextField(blank=True, verbose_name=_("Notes"))

    class Meta:
        ordering            = ['name']
        verbose_name        = _("Index Kit")
        verbose_name_plural = _("Index Kits")

    def __str__(self):
        return self.name


class LibraryIndex(models.Model):
    """
    One physical well in an Index Kit's plate set.

    Identity is (indexKit, plateSet, well) a given kit + plate + well
    always points at exactly one i7/i5 sequence pair. udi_number is kept
    as a display label only (it can repeat across kits, e.g. 'UDP0001'
    in both V2 and V3 with different sequences, or carry a version
    suffix like 'UDP0252V2' when the manufacturer revised that well).
    """
    indexKit = models.ForeignKey(
        IndexKit,
        on_delete=models.CASCADE,
        related_name='indexes',
        verbose_name=_("Index Kit"),
    )
    plateSet = models.CharField(
        max_length=40, blank=True,
        verbose_name=_("Plate Set"),
        help_text=_("e.g. 'Set A V2', 'Plate 1'. Blank for single-plate kits."),
    )
    well = models.CharField(max_length=10, verbose_name=_("Well"))
    udi_number = models.CharField(max_length=50, blank=True, verbose_name=_("UDI Number"))
    i7Sequence = models.CharField(max_length=200, verbose_name=_("i7 Sequence"))
    i5Sequence = models.CharField(max_length=200, blank=True, verbose_name=_("i5 Sequence"))
    createdBy = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='libraryIndexes',
    )

    class Meta:
        ordering            = ['indexKit', 'plateSet', 'well']
        verbose_name        = _("Library Index")
        verbose_name_plural = _("Library Indexes")
        constraints = [
            models.UniqueConstraint(
                fields=['indexKit', 'plateSet', 'well'],
                name='unique_well_per_kit_plate',
            ),
        ]

    def __str__(self):
        ps = f" [{self.plateSet}]" if self.plateSet else ""
        return f"{self.indexKit.name}{ps} {self.well} – {self.udi_number}"


class LibraryPrepBatch(models.Model):
    """
    One library-prep run.  One batch = one physical plate.

    batch_name is generated at creation time:
        {project_name}-Library-{4-digit uppercase hex counter}
        e.g. ACME2024-Library-003F

    plate is created and linked during batch creation — it records the
    physical location (rack + slot) of the plate.
    """
    project = models.ForeignKey(
        'samples.Project',
        on_delete=models.PROTECT,
        related_name='libprep_batches',
        verbose_name=_("Project"),
        null=True, blank=True,
    )
    plate = models.OneToOneField(
        'locations.Plate',
        on_delete=models.PROTECT,
        null=True, blank=True,
        related_name='libprep_batch',
        verbose_name=_("Plate"),
    )
    workflowType = models.ForeignKey(
        WorkflowType,
        on_delete=models.PROTECT,
        related_name='libraryPrepBatches',
        verbose_name=_("Workflow Type"),
    )

    # Populated on creation via _save_new_batch; never auto-generated here
    # so it stays consistent with the Plate.plate_name.
    batch_name = models.CharField(
        max_length=200,
        blank=True,
        verbose_name=_("Batch Name"),
        help_text=_("Auto-generated: {project}-Library-{4HEX}. Do not edit manually."),
    )

    datePrepped = models.DateField(verbose_name=_("Date Prepped"))
    max_samples = models.PositiveSmallIntegerField(
        null=True, blank=True,
        verbose_name=_("Sample Count"),
        help_text=_("Number of samples (excluding controls) in this batch."),
    )
    notes     = models.TextField(blank=True, verbose_name=_("Notes"))
    createdBy = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='libraryPrepBatches',
        verbose_name=_("Created By"),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering            = ['-datePrepped']
        verbose_name        = _("Library Prep Batch")
        verbose_name_plural = _("Library Prep Batches")

    def __str__(self):
        return self.batch_name or (
            self.plate.plate_name if self.plate_id else f"Batch #{self.pk}"
        )

    @property
    def sample_count(self):
        return self.samples.filter(plateWell__well_type='sample').count()

    @property
    def control_count(self):
        return self.samples.filter(plateWell__well_type='control').count()


class LibraryPrepBatchAuditLog(models.Model):
    """
    Immutable record of every significant change to a LibraryPrepBatch.

    Intentionally kept simple: a timestamped action + free-text detail
    written by the view that makes the change.  This gives the lab a
    clear timeline without the overhead of a full field-level diff table.

    Nothing in this model is editable after creation (no update_fields
    that touch it; views only ever call .create()).
    """

    ACTION_CREATED  = 'created'
    ACTION_UPDATED  = 'updated'
    ACTION_SAMPLES  = 'samples_updated'
    ACTION_LOCATION = 'location_changed'
    ACTION_STATUS   = 'status_changed'
    ACTION_NOTES    = 'notes_updated'

    ACTION_CHOICES = [
        (ACTION_CREATED,  _('Batch Created')),
        (ACTION_UPDATED,  _('Batch Updated')),
        (ACTION_SAMPLES,  _('Samples Updated')),
        (ACTION_LOCATION, _('Location Changed')),
        (ACTION_STATUS,   _('Status Changed')),
        (ACTION_NOTES,    _('Notes Updated')),
    ]

    batch = models.ForeignKey(
        LibraryPrepBatch,
        on_delete=models.CASCADE,
        related_name='audit_logs',
        verbose_name=_("Batch"),
    )
    changed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='libprep_audit_logs',
        verbose_name=_("Changed By"),
    )
    changed_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Changed At"),
        db_index=True,
    )
    action = models.CharField(
        max_length=30,
        choices=ACTION_CHOICES,
        default=ACTION_UPDATED,
        verbose_name=_("Action"),
    )
    detail = models.TextField(
        blank=True,
        verbose_name=_("Detail"),
        help_text=_("Human-readable summary of what changed."),
    )

    class Meta:
        ordering            = ['-changed_at']
        verbose_name        = _("Library Prep Batch Audit Log")
        verbose_name_plural = _("Library Prep Batch Audit Logs")

    def __str__(self):
        who = self.changed_by.get_full_name() if self.changed_by else 'unknown'
        return f"{self.batch} — {self.get_action_display()} by {who} at {self.changed_at:%Y-%m-%d %H:%M}"



class PrepAction(models.TextChoices):
    PREP    = 'prep',    _('Prep')
    SKIP    = 'skip',    _('Skip')
    REQUEUE = 'requeue', _('Requeue')


class LibraryPrepSample(models.Model):
    """
    One sample (or control) within a LibraryPrepBatch.

    sampleQC is nullable for control wells (positive / negative).
    plateWell is intentionally null at batch creation time — it is
    assigned later when the physical plate layout is confirmed and
    PlateWell records are committed.
    Volume fields are pre-calculated at creation from the workflow
    target parameters and the sample's Qubit concentration.
    """
    libPrepBatch = models.ForeignKey(
        LibraryPrepBatch,
        on_delete=models.CASCADE,
        related_name='samples',
        verbose_name=_("Library Prep Batch"),
    )
    sampleQC = models.ForeignKey(
        'qc.SampleQC',
        on_delete=models.PROTECT,
        null=True, blank=True,
        related_name='libraryPrepSamples',
        verbose_name=_("Sample QC"),
        help_text=_("Null for control wells."),
    )
    plateWell = models.ForeignKey(
        'locations.PlateWell',
        on_delete=models.PROTECT,
        null=True, blank=True,
        related_name='libraryPrepSamples',
        verbose_name=_("Plate Well"),
        help_text=_("Populated when the physical plate layout is committed."),
    )
    libraryIndex = models.ForeignKey(
        LibraryIndex,
        on_delete=models.PROTECT,
        null=True, blank=True,
        related_name='libraryPrepSamples',
        verbose_name=_("Library Index"),
    )

    # Stored separately from plateWell so the intended layout is preserved
    # even before PlateWell records are committed.
    planned_well_position = models.CharField(
        max_length=4,
        blank=True,
        verbose_name=_("Planned Well Position"),
        help_text=_("Well position chosen during batch creation, e.g. 'A01'. "
                    "Committed to plateWell when plate layout is finalised."),
    )

    # Volume calculation fields 
    concentrationInput = models.FloatField(null=True, blank=True, verbose_name=_("Concentration Input (ng/µL)"))
    volumeSample_ul    = models.FloatField(null=True, blank=True, verbose_name=_("Volume Sample (µL)"))
    volumeDiluent_ul   = models.FloatField(null=True, blank=True, verbose_name=_("Volume Diluent (µL)"))
    actual_Input_ng    = models.FloatField(null=True, blank=True, verbose_name=_("Actual Input (ng)"))
    speedVacRequired   = models.BooleanField(default=False, verbose_name=_("SpeedVac Required"))
    PCRCycles          = models.IntegerField(null=True, blank=True, verbose_name=_("PCR Cycles"))

    prepAction = models.CharField(
        max_length=20,
        choices=PrepAction.choices,
        default=PrepAction.PREP,
        verbose_name=_("Prep Action"),
    )
    createdBy = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='libraryPrepSamples',
        verbose_name=_("Created By"),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering            = ['libPrepBatch', 'planned_well_position']
        verbose_name        = _("Library Prep Sample")
        verbose_name_plural = _("Library Prep Samples")

    def __str__(self):
        name = self.sampleQC.sample.sample_name if self.sampleQC_id else "Control"
        well = self.planned_well_position or (
            self.plateWell.well_position if self.plateWell_id else "?"
        )
        return f"{name} @ {well} (Batch {self.libPrepBatch_id})"


class QCStatus(models.TextChoices):
    PASS    = 'pass',    _('Pass')
    FAIL    = 'fail',    _('Fail')
    CAUTION = 'caution', _('Caution')
    PENDING = 'pending', _('Pending')


class LibraryQCBatch(models.Model):
    libPrepBatch = models.OneToOneField(
        LibraryPrepBatch,
        on_delete=models.CASCADE,
        related_name='qcBatch',
        verbose_name=_("Library Prep Batch"),
    )
    batchName = models.CharField(max_length=200, blank=True, verbose_name=_("Batch Name"))
    dateQCed  = models.DateField(null=True, blank=True, verbose_name=_("Date QC'd"))
    createdBy = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='libraryQCBatches',
    )

    class Meta:
        ordering            = ['-dateQCed']
        verbose_name        = _("Library QC Batch")
        verbose_name_plural = _("Library QC Batches")

    def __str__(self):
        return self.batchName or f"LibQCBatch #{self.pk}"


class LibraryQC(models.Model):
    libQCBatch    = models.ForeignKey(LibraryQCBatch, on_delete=models.CASCADE, related_name='qcResults')
    libPrepSample = models.OneToOneField(LibraryPrepSample, on_delete=models.CASCADE, related_name='qcResult')

    qubit_ng_ul        = models.FloatField(null=True, blank=True, verbose_name=_("Qubit (ng/µL)"))
    fragmentSizesAvgBP = models.FloatField(null=True, blank=True, verbose_name=_("Avg Fragment Size (bp)"))
    nmCalculated       = models.FloatField(null=True, blank=True, verbose_name=_("nM Calculated"))
    dimerPeak_pct      = models.FloatField(null=True, blank=True, verbose_name=_("Dimer Peak (%)"))
    QCstatus = models.CharField(
        max_length=20,
        choices=QCStatus.choices,
        default=QCStatus.PENDING,
        verbose_name=_("QC Status"),
    )
    createdBy = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='libraryQCs',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering            = ['libQCBatch', 'libPrepSample']
        verbose_name        = _("Library QC")
        verbose_name_plural = _("Library QCs")

    def __str__(self):
        return f"LibQC #{self.pk} – {self.QCstatus}"

    def calculate_nm(self):
        """nM = (qubit_ng_ul × 10⁶) / (fragment_bp × 650)"""
        if self.qubit_ng_ul and self.fragmentSizesAvgBP and self.fragmentSizesAvgBP > 0:
            return round((self.qubit_ng_ul * 1_000_000) / (self.fragmentSizesAvgBP * 650), 4)
        return None

    def calculate_qc_status(self, workflow_type=None):
        nm = self.nmCalculated or self.calculate_nm()
        if nm is None:
            return QCStatus.PENDING
        if nm < 2.0:
            return QCStatus.FAIL
        if workflow_type and self.fragmentSizesAvgBP:
            fmin = workflow_type.fragment_min_bp
            fmax = workflow_type.fragment_max_bp
            if fmin and fmax and not (fmin <= self.fragmentSizesAvgBP <= fmax):
                return QCStatus.FAIL
        return QCStatus.PASS

    def save(self, *args, **kwargs):
        if self.nmCalculated is None:
            self.nmCalculated = self.calculate_nm()
        super().save(*args, **kwargs)