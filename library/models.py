import math

from django.db import models
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

User = get_user_model()


class ReadLengthType(models.TextChoices):
    SHORT = 'short', _('Short Read')
    LONG  = 'long',  _('Long Read')


class QCMethod(models.TextChoices):
    QUBIT_ONLY        = 'qubit',            _('Qubit Only')
    QUBIT_TAPESTATION  = 'qubit_tapestation', _('Qubit + TapeStation')


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
    read_length_type = models.CharField(
        max_length=10,
        choices=ReadLengthType.choices,
        default=ReadLengthType.SHORT,
        verbose_name=_("Read Length Type"),
        help_text=_("Determines sequencing instrument: short read (iSeq/NovaSeq) vs long read (PromethION)."),
    )
    qc_method = models.CharField(
        max_length=20,
        choices=QCMethod.choices,
        default=QCMethod.QUBIT_TAPESTATION,
        verbose_name=_("Library QC Method"),
        help_text=_("Which QC is run at the Library QC step. Qubit-only workflows skip fragment size / dimer checks."),
    )
    uses_controls = models.BooleanField(
        default=True,
        verbose_name=_("Uses Positive/Negative Controls"),
        help_text=_("Whether a positive and negative control are added to each batch of this workflow."),
    )
    requires_pcr = models.BooleanField(
        default=True,
        verbose_name=_("Requires PCR Amplification"),
        help_text=_("Whether this workflow has a PCR amplification step (e.g. false for PCR-Free protocols)."),
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
    dimer_threshold_pct = models.FloatField(
        null=True, blank=True, default=None,
        verbose_name=_("Dimer Threshold (%)"),
    )
    min_nm_threshold = models.FloatField(
        default=2.0,
        verbose_name=_("Minimum nM Threshold"),
        help_text=_("Library QC pass gate. Was hardcoded at 2.0 in LibraryQC; now modifiable per workflow."),
    )

    class Meta:
        ordering = ['workflowType']
        verbose_name        = _("Workflow Type")
        verbose_name_plural = _("Workflow Types")

    def __str__(self):
        return self.workflowType


class StepRow(models.Model):
    
    stepRowName = models.CharField(max_length=200, verbose_name=_("Reagent / Row Name"))
    sort_order  = models.PositiveSmallIntegerField(
        default=0, verbose_name=_("Default Sort Order"),
        help_text=_("Fallback ordering when not overridden per-step by WorkflowStepRowOrder.sort_order."),
    )

    class Meta:
        ordering = ['sort_order', 'stepRowName']
        verbose_name        = _("Step Row")
        verbose_name_plural = _("Step Rows")

    def __str__(self):
        return self.stepRowName


class WorkflowTypeStep(models.Model):
    workflowType = models.ForeignKey(WorkflowType, on_delete=models.CASCADE, related_name='steps')
    stepName     = models.CharField(max_length=200, verbose_name=_("Step Name"))
    sort_order   = models.PositiveSmallIntegerField(default=0)
    is_stopping_point = models.BooleanField(
        default=False,
        verbose_name=_("Safe Stopping Point"),
        help_text=_("Marks this step as a safe point to pause the protocol (printed sheets highlight this)."),
    )
    stepRows = models.ManyToManyField(
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
    """
    Join table between a WorkflowTypeStep and a StepRow.

    Carries the step-specific volume/row-type.
    """
    step       = models.ForeignKey(WorkflowTypeStep, on_delete=models.CASCADE, related_name='row_links')
    step_row   = models.ForeignKey(StepRow, on_delete=models.CASCADE)
    sort_order = models.PositiveSmallIntegerField(default=0)

    volumePerRxn = models.FloatField(
        null=True, blank=True,
        verbose_name=_("Volume per Reaction (µL)"),
    )
    constantOfMM = models.IntegerField(
        default=1,
        choices=[
            (0, 'Fixed / Header'),
            (1, 'Per Reaction (×n)'),
            (2, 'Ethanol Dilution Pair (rounds to nearest 5 mL batch)'),
        ],
        verbose_name=_("Row Type"),
        help_text=_(
            "Per Reaction: volumePerRxn × (reactions + extra_reactions). "
            "Fixed / Header: volumePerRxn is used as-is, ignoring reaction "
            "count. Ethanol Dilution Pair: this single row represents a "
            "fresh 80% ethanol prep, call ethanol_dilution_volumes() to "
            "get the (ethanol, water) split instead of one plain volume; "
            "volumePerRxn here is the working-solution volume per "
            "reaction (e.g. the 350 or 400 µL of 80% EtOH used per wash), "
            "not a straight reagent volume."
        ),
    )

    # Several of the source protocol sheets don't just do volumePerRxn × n;
    # they pad a fixed number of extra reactions on top as dead-volume /
    # pipetting-loss buffer, e.g. "(n + 1)" or "(n + 2)"

    # Master mix volume for a "Per Reaction" row is therefore:
    #     volumePerRxn * (reaction_count + extra_reactions)

    extra_reactions = models.PositiveSmallIntegerField(
        default=0,
        verbose_name=_("Extra Reactions (Dead Volume)"),
        help_text=_(
            "Extra reactions' worth of volume added on top of the batch's "
            "reaction count for this specific reagent, to cover pipetting "
            "loss (e.g. this row's sheet used '(n + 2)'). Leave at 0 if "
            "the reagent scales with reaction count exactly."
        ),
    )
    
    # Every source sheet that preps fresh 80% ethanol uses the exact same
    # rounding convention, regardless of workflow.
    ETOH_ROUND_INCREMENT_UL = 5000   # round working-solution batches to the nearest 5 mL
    ETOH_BUFFER_THRESHOLD_UL = 1700  # if within 1.7 mL of the boundary, bump up one more batch
    ETOH_PERCENT = 0.8               # 80% ethanol : 20% nuclease-free water

    class Meta:
        ordering        = ['sort_order']
        unique_together = [('step', 'step_row')]
        verbose_name        = _("Workflow Step Row")
        verbose_name_plural = _("Workflow Step Rows")

    def __str__(self):
        return f"{self.step} – {self.step_row}"

    def mastermix_volume(self, reaction_count):
        """
        Compute this row's master mix volume for a given reaction count.
        Fixed/Header rows return volumePerRxn unchanged. 
        """
        if self.volumePerRxn is None:
            return None
        if self.constantOfMM == 0:
            return self.volumePerRxn
        if self.constantOfMM == 2:
            ethanol, water = self.ethanol_dilution_volumes(reaction_count)
            return None if ethanol is None else round(ethanol + water, 2)
        return self.volumePerRxn * (reaction_count + self.extra_reactions)

    def ethanol_dilution_volumes(self, reaction_count):
        """
        Only meaningful when constantOfMM == 2 (Ethanol Dilution Pair).

        The source sheets don't measure out an exact 80% ethanol volume —
        they prep it fresh in round 5 mL batches, with an extra batch
        added as a buffer if the raw volume needed is already close to
        the next boundary. Returns (ethanol_ul, water_ul), or (None, None)
        if this row isn't an Ethanol Dilution Pair or has no volume set.

            raw   = volumePerRxn * (reaction_count + extra_reactions)
            round = CEILING(raw, 5000)
            round = round + 5000  if raw >= round - 1700
            ethanol = round * 0.8
            water   = CEILING(ethanol, 5000) - ethanol
        """
        if self.constantOfMM != 2 or self.volumePerRxn is None:
            return None, None

        raw_total = self.volumePerRxn * (reaction_count + self.extra_reactions)
        rounded = math.ceil(raw_total / self.ETOH_ROUND_INCREMENT_UL) * self.ETOH_ROUND_INCREMENT_UL
        if raw_total >= rounded - self.ETOH_BUFFER_THRESHOLD_UL:
            rounded += self.ETOH_ROUND_INCREMENT_UL

        ethanol = round(rounded * self.ETOH_PERCENT, 2)
        water_batch = math.ceil(ethanol / self.ETOH_ROUND_INCREMENT_UL) * self.ETOH_ROUND_INCREMENT_UL
        water = round(water_batch - ethanol, 2)
        return ethanol, water


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

    # Persisted "number of reactions" used to calculate every master mix
    # volume on the (future) Master Mix tab / print sheet.

    mastermix_reaction_count = models.PositiveSmallIntegerField(
        null=True, blank=True,
        verbose_name=_("Master Mix Reaction Count"),
        help_text=_(
            "Number of reactions used to calculate master mix volumes on "
            "the Master Mix print sheet. Defaults to sample count + control "
            "count if not set. Persisted so it stays the same across visits "
            "until a lab member changes it."
        ),
    )

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

    @property
    def total_reaction_count(self):
        """
        Total number of reactions to print master mix sheets for. Defaults
        to sample_count + control_count.
        """
        return self.sample_count + self.control_count

    @property
    def effective_mastermix_reaction_count(self):
        """
        The reaction count to actually use when computing master mix
        volumes: the persisted override if one has been set, otherwise
        the computed total_reaction_count.
        """
        if self.mastermix_reaction_count is not None:
            return self.mastermix_reaction_count
        return self.total_reaction_count


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

        # nM threshold is now workflow-configurable instead of hardcoded.
        min_nm = workflow_type.min_nm_threshold if workflow_type else 2.0
        if nm < min_nm:
            return QCStatus.FAIL

        if workflow_type and self.fragmentSizesAvgBP:
            fmin = workflow_type.fragment_min_bp
            fmax = workflow_type.fragment_max_bp
            if fmin and fmax and not (fmin <= self.fragmentSizesAvgBP <= fmax):
                return QCStatus.FAIL

        # Dimer peak check was previously defined on WorkflowType but never
        # enforced here — the docs call it out as a real fail/pooling gate.
        if workflow_type and workflow_type.dimer_threshold_pct is not None and self.dimerPeak_pct is not None:
            if self.dimerPeak_pct > workflow_type.dimer_threshold_pct:
                return QCStatus.FAIL

        return QCStatus.PASS

    def save(self, *args, **kwargs):
        if self.nmCalculated is None:
            self.nmCalculated = self.calculate_nm()
        super().save(*args, **kwargs)