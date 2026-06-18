
from django.db import models
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

User = get_user_model()


# WORKFLOW TEMPLATE SYSTEM 

class WorkflowType(models.Model):
    """
    A named library-prep workflow, e.g. 'Total RNA', 'Small RNA',
    'KAPA HyperPlus DNA', 'DNA PCR-Free WGS'.
    """
    workflowType = models.CharField(
        max_length=100, unique=True,
        verbose_name=_("Workflow Type"),
    )
    sample_type = models.CharField(
        max_length=10,
        choices=[('DNA', 'DNA'), ('RNA', 'RNA')],
        default='RNA',
        verbose_name=_("Sample Type"),
        help_text=_("Whether this workflow processes DNA or RNA samples."),
    )
    # Volume calculation parameters (used by the plate-board volume helper)
    target_input_ng = models.FloatField(
        default=250.0,
        verbose_name=_("Target Input (ng)"),
        help_text=_("Target mass in ng to load per sample."),
    )
    target_volume_ul = models.FloatField(
        default=11.0,
        verbose_name=_("Target Volume (µL)"),
        help_text=_("Starting reaction volume in µL."),
    )
    diluent_name = models.CharField(
        max_length=80,
        default='NF H₂O',
        verbose_name=_("Diluent Name"),
        help_text=_("e.g. 'NF H₂O', 'Tris-HCl pH 8.5 10 mM', 'RSB'."),
    )
    # Fragment size QC gates (used by LibraryQC auto-status)
    fragment_min_bp = models.IntegerField(
        null=True, blank=True,
        verbose_name=_("Min Fragment Size (bp)"),
    )
    fragment_max_bp = models.IntegerField(
        null=True, blank=True,
        verbose_name=_("Max Fragment Size (bp)"),
    )
    # Dimer threshold (stored but not actively tracked per lab request)
    dimer_threshold_pct = models.FloatField(
        default=10.0,
        verbose_name=_("Dimer Threshold (%)"),
    )

    class Meta:
        ordering = ['workflowType']
        verbose_name        = _("Workflow Type")
        verbose_name_plural = _("Workflow Types")

    def __str__(self):
        return self.workflowType


class StepRow(models.Model):
    """
    A single reagent / action row within a master-mix step.
    Stores the per-reaction volume; the printable MM template
    multiplies this by the sample count.

    constantOfMM:
      0 = this row is a fixed volume (not multiplied by sample count),
          e.g. a header or a note row.
      1 = volume is per reaction (multiplied by n+2 for controls).
    """
    stepRowName   = models.CharField(max_length=200, verbose_name=_("Reagent / Row Name"))
    volumePerRxn  = models.FloatField(
        null=True, blank=True,
        verbose_name=_("Volume per Reaction (µL)"),
        help_text=_("µL per reaction; leave blank for header/note rows."),
    )
    constantOfMM  = models.IntegerField(
        default=1,
        choices=[(0, 'Fixed / Header'), (1, 'Per Reaction (×n)')],
        verbose_name=_("Row Type"),
    )
    sort_order = models.PositiveSmallIntegerField(
        default=0,
        verbose_name=_("Sort Order"),
        help_text=_("Controls print order within a step."),
    )

    class Meta:
        ordering = ['sort_order', 'stepRowName']
        verbose_name        = _("Step Row")
        verbose_name_plural = _("Step Rows")

    def __str__(self):
        return self.stepRowName


class WorkflowTypeStep(models.Model):
    """
    One named step in a workflow master-mix template
    (e.g. 'Step A: 3′ Adaptor Ligation').

    numberOFReaction is the multiplier printed in the 'No. of Reactions'
    column — usually n_samples + 2 controls, but some steps use a
    different multiplier (e.g. ×1.2 overage); store as a formula string
    or override per-step.
    """
    workflowType   = models.ForeignKey(
        WorkflowType,
        on_delete=models.CASCADE,
        related_name='steps',
        verbose_name=_("Workflow Type"),
    )
    stepName       = models.CharField(max_length=200, verbose_name=_("Step Name"))
    sort_order     = models.PositiveSmallIntegerField(default=0, verbose_name=_("Sort Order"))
    numberOFReaction = models.IntegerField(
        default=1,
        verbose_name=_("Reaction Multiplier"),
        help_text=_("Usually n_samples + 2.  The view overrides this at print time."),
    )
    stepRows = models.ManyToManyField(
        StepRow,
        blank=True,
        related_name='workflowSteps',
        verbose_name=_("Reagent Rows"),
        through='WorkflowStepRowOrder',
    )

    class Meta:
        ordering = ['workflowType', 'sort_order', 'stepName']
        verbose_name        = _("Workflow Type Step")
        verbose_name_plural = _("Workflow Type Steps")

    def __str__(self):
        return f"{self.workflowType} – {self.stepName}"


class WorkflowStepRowOrder(models.Model):
    """
    Explicit through-table so each StepRow can appear in multiple steps
    while preserving a per-step sort order.
    """
    step     = models.ForeignKey(WorkflowTypeStep, on_delete=models.CASCADE)
    step_row = models.ForeignKey(StepRow,          on_delete=models.CASCADE)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering        = ['sort_order']
        unique_together = [('step', 'step_row')]


class LibraryIndex(models.Model):
    """
    Sequencing index lookup table.

    For dual-index workflows that use plate sets (TotalRNA, DNA PCR-Free):
      plateSet  = 'A' | 'B' | 'C' | 'D'
      well      = 'A01' … 'H12'
    For single-set workflows (SmallRNA, KAPA): leave plateSet blank.

    indexVersion differentiates Illumina V2 vs V3 index sequences,
    which is important for the iSeq / NovaSeq sample sheets.
    """
    udi_number   = models.CharField(max_length=50,  verbose_name=_("UDI Number"), null=True,blank=True,)
    plateSet     = models.CharField(max_length=10,  blank=True, verbose_name=_("Plate Set"))
    well         = models.CharField(max_length=10,  verbose_name=_("Well"))
    i7Sequence   = models.CharField(max_length=200, verbose_name=_("i7 Sequence"))
    i5Sequence   = models.CharField(max_length=200, blank=True, verbose_name=_("i5 Sequence"))
    indexVersion = models.CharField(max_length=50,  blank=True, verbose_name=_("Index Version"),
                                    help_text=_("e.g. 'V2', 'V3'"))
    workflow_types = models.ManyToManyField(
        WorkflowType,
        blank=True,
        related_name='indexes',
        verbose_name=_("Compatible Workflow Types"),
    )
    createdBy = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='libraryIndexes',
        verbose_name=_("Created By"),
    )

    class Meta:
        ordering            = ['plateSet', 'well']
        verbose_name        = _("Library Index")
        verbose_name_plural = _("Library Indexes")

    def __str__(self):
        ps = f" [{self.plateSet}]" if self.plateSet else ""
        return f"UDI-{self.udi_number}{ps} {self.well}"


class LibraryPrepBatch(models.Model):
    """
    One library-prep run.  One batch = one physical plate.

    Linked to:
      - Project  (for filtering the plate board)
      - Plate    (the physical 48-well plate created at save time)
      - WorkflowType (KAPA / TotalRNA / SmallRNA / …)
    """
    project = models.ForeignKey(
        'samples.Project',
        on_delete=models.PROTECT,
        related_name='libprep_batches',
        verbose_name=_("Project"),
        null=True,
        blank=True,
    )
    plate = models.OneToOneField(
        'locations.Plate',
        on_delete=models.PROTECT,
        null=True, blank=True,
        related_name='libprep_batch',
        verbose_name=_("Plate"),
        help_text=_("The physical plate this batch is loaded onto."),
    )
    workflowType = models.ForeignKey(
        WorkflowType,
        on_delete=models.PROTECT,
        related_name='libraryPrepBatches',
        verbose_name=_("Workflow Type"),
    )
    datePrepped = models.DateField(
        verbose_name=_("Date Prepped"),
    )
    max_samples = models.PositiveSmallIntegerField(
        null=True, blank=True,
        verbose_name=_("Sample Count"),
        help_text=_("Number of samples (excluding controls) in this batch."),
    )
    notes = models.TextField(blank=True, verbose_name=_("Notes"))
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
        plate_name = self.plate.plate_name if self.plate_id else f"#{self.pk}"
        return f"{plate_name} — {self.workflowType} ({self.datePrepped})"

    @property
    def sample_count(self):
        return self.samples.filter(plateWell__well_type='sample').count()

    @property
    def control_count(self):
        return self.samples.filter(plateWell__well_type='control').count()


# PREP ACTION 

class PrepAction(models.TextChoices):
    PREP    = 'prep',    _('Prep')
    SKIP    = 'skip',    _('Skip')
    REQUEUE = 'requeue', _('Requeue')


# LIBRARY PREP SAMPLE 
class LibraryPrepSample(models.Model):
    """
    One sample (or control) within a LibraryPrepBatch.

    sampleQC is nullable so control wells (positive/negative) can be
    represented without a QC record.

    Volume fields are calculated by the plate-board save view and stored
    so the printable working sheet doesn't need to recalculate.
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
    )
    libraryIndex = models.ForeignKey(
        LibraryIndex,
        on_delete=models.PROTECT,
        null=True, blank=True,
        related_name='libraryPrepSamples',
        verbose_name=_("Library Index"),
        help_text=_("Assigned after library prep is complete."),
    )

    # Volume calculation fields (auto-filled by save view) 
    concentrationInput = models.FloatField(
        null=True, blank=True,
        verbose_name=_("Concentration Input (ng/µL)"),
    )
    volumeSample_ul = models.FloatField(
        null=True, blank=True,
        verbose_name=_("Volume Sample (µL)"),
        help_text=_("Calculated volume of sample to pipette."),
    )
    volumeDiluent_ul = models.FloatField(
        null=True, blank=True,
        verbose_name=_("Volume Diluent (µL)"),
        help_text=_("NF H₂O / Tris / RSB to add to reach target volume."),
    )
    actual_Input_ng = models.FloatField(
        null=True, blank=True,
        verbose_name=_("Actual Input (ng)"),
        help_text=_("May differ from target when SpeedVac'd from limited material."),
    )
    speedVacRequired = models.BooleanField(
        default=False,
        verbose_name=_("SpeedVac Required"),
    )
    PCRCycles = models.IntegerField(
        null=True, blank=True,
        verbose_name=_("PCR Cycles"),
        help_text=_("Logged after library prep for applicable workflows."),
    )

    # Admin / tracking 
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
        ordering            = ['libPrepBatch', 'plateWell__well_position']
        verbose_name        = _("Library Prep Sample")
        verbose_name_plural = _("Library Prep Samples")

    def __str__(self):
        name = self.sampleQC.sample.sample_name if self.sampleQC_id else "Control"
        well = self.plateWell.well_position if self.plateWell_id else "?"
        return f"{name} @ {well} (Batch {self.libPrepBatch_id})"






# LIBRARY QC 

class QCStatus(models.TextChoices):
    PASS    = 'pass',    _('Pass')
    FAIL    = 'fail',    _('Fail')
    CAUTION = 'caution', _('Caution')
    PENDING = 'pending', _('Pending')


class LibraryQCBatch(models.Model):
    """Groups QC results for a library prep batch (1-to-1 with LibraryPrepBatch)."""
    libPrepBatch = models.OneToOneField(
        LibraryPrepBatch,
        on_delete=models.CASCADE,
        related_name='qcBatch',
        verbose_name=_("Library Prep Batch"),
    )
    batchName  = models.CharField(max_length=200, blank=True, verbose_name=_("Batch Name"))
    dateQCed   = models.DateField(null=True, blank=True, verbose_name=_("Date QC'd"))
    createdBy  = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='libraryQCBatches',
        verbose_name=_("Created By"),
    )

    class Meta:
        ordering            = ['-dateQCed']
        verbose_name        = _("Library QC Batch")
        verbose_name_plural = _("Library QC Batches")

    def __str__(self):
        return self.batchName or f"LibQCBatch #{self.pk}"


class LibraryQC(models.Model):

    libQCBatch     = models.ForeignKey(
        LibraryQCBatch,
        on_delete=models.CASCADE,
        related_name='qcResults',
        verbose_name=_("Library QC Batch"),
    )
    libPrepSample  = models.OneToOneField(
        LibraryPrepSample,
        on_delete=models.CASCADE,
        related_name='qcResult',
        verbose_name=_("Library Prep Sample"),
    )
    qubit_ng_ul        = models.FloatField(null=True, blank=True, verbose_name=_("Qubit (ng/µL)"))
    fragmentSizesAvgBP = models.FloatField(null=True, blank=True, verbose_name=_("Avg Fragment Size (bp)"))
    nmCalculated       = models.FloatField(null=True, blank=True, verbose_name=_("nM Calculated"))
    # Dimer stored but not actively tracked (lab request)
    dimerPeak_pct      = models.FloatField(
        null=True, blank=True,
        verbose_name=_("Dimer Peak (%)"),
        help_text=_("Recorded but not used to gate progression per lab preference."),
    )
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
        verbose_name=_("Created By"),
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
        """Auto-determine pass/fail from nM and fragment size gates."""
        nm = self.nmCalculated or self.calculate_nm()
        if nm is None:
            return QCStatus.PENDING

        if nm < 2.0:
            return QCStatus.FAIL

        if workflow_type and self.fragmentSizesAvgBP:
            fmin = workflow_type.fragment_min_bp
            fmax = workflow_type.fragment_max_bp
            if fmin and fmax:
                if not (fmin <= self.fragmentSizesAvgBP <= fmax):
                    return QCStatus.FAIL

        return QCStatus.PASS

    def save(self, *args, **kwargs):
        # Auto-calculate nM if not set
        if self.nmCalculated is None:
            self.nmCalculated = self.calculate_nm()
        super().save(*args, **kwargs)