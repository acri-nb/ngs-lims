
from django.db import models
from django.utils.translation import gettext_lazy as _
from samples.models import Sample, Project 

from django.core.exceptions import ValidationError

from django.contrib.auth import get_user_model

User = get_user_model()
# Model for: SampleQCBatch, BatchSample, SampleQC
 
class SampleQCBatch(models.Model):
    """
    Represents a QC run 
 
    Batch name format: ProjectName-BATCH-4HexID
    Example: CancerTEST-BATCH-1A4C
 
    The hex ID is the batch's auto-incremented primary key
    zero-padded to 4 uppercase hex digits.
    Batch 1   → 0001
    Batch 16  → 0010
    Batch 255 → 00FF
    """

    batch_name = models.CharField(max_length=255, unique=True, blank=True)
    date_batched = models.DateField()
    
    project = models.ForeignKey(
        Project,
        on_delete=models.PROTECT,
        related_name="qc_batches",
        null=True,
        blank=True,
    )

    batch_type = models.CharField(
        max_length=10,
        choices=[
            ("DNA", "DNA"),
            ("RNA", "RNA"),
        ],
        default="RNA"
    )

    created_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='qc_batches_created'
    )

   
    samples = models.ManyToManyField(
        Sample,
        through='BatchSample',
        related_name='qc_batches'
    )

    def _generate_batch_name(self, project_name: str) -> str:
        hex_id = format(self.id, '04X')   # ← self.id not self.batch_id
        return f"{project_name}-BATCH-{hex_id}"

    def save(self, *args, **kwargs):
        if not self.batch_name:
            super().save(*args, **kwargs)
            self.batch_name = self._generate_batch_name(self.project.project_name)
            super().save(update_fields=['batch_name'])
        else:
            super().save(*args, **kwargs)

    class Meta:
        verbose_name = "Sample QC Batch"
        verbose_name_plural = "Sample QC Batches"
        ordering = ['-date_batched']

    @property
    def sample_count(self):
        return self.samples.count()
      
    def __str__(self):
        return f"{self.batch_name}"
 
 
 
class BatchSample(models.Model):
    """
    Junction table between SampleQCBatch and Sample.
    Prevents the same sample appearing twice in the same batch.
    """
    batch = models.ForeignKey(
        SampleQCBatch,
        on_delete=models.CASCADE,       # if a batch is deleted, remove its membership rows
        related_name='batch_samples'
    )
    sample = models.ForeignKey(
        Sample,
        on_delete=models.PROTECT,       # cannot delete a sample that is in a batch
        related_name='batch_memberships'
    )
 
    class Meta:
        verbose_name = "Batch Sample"
        verbose_name_plural = "Batch Samples"
        unique_together = ('batch', 'sample')   # one sample can only appear once per batch
 
    def __str__(self):
        return f"{self.sample} in {self.batch}"
 
 

class BatchAuditLog(models.Model):
    """
    Immutable record of every save action performed on the batch board.
    Written once per save; never updated.
    """
    ACTION_SAVE    = 'save'
    ACTION_CREATE  = 'create'
    ACTION_DELETE  = 'delete'
    ACTION_CHOICES = [
        (ACTION_SAVE,   'Board saved'),
        (ACTION_CREATE, 'Batch created'),
        (ACTION_DELETE, 'Batch deleted'),
    ]

    project    = models.ForeignKey(Project,        on_delete=models.PROTECT, related_name='batch_audit_logs')
    batch      = models.ForeignKey(SampleQCBatch,  on_delete=models.SET_NULL, null=True, blank=True, related_name='audit_logs')
    action     = models.CharField(max_length=20,   choices=ACTION_CHOICES)
    performed_by = models.ForeignKey(User,         on_delete=models.PROTECT, related_name='batch_audit_logs')
    timestamp  = models.DateTimeField(auto_now_add=True)

    # JSON snapshot of the diff: { "added": [...], "removed": [...], "moved": [...] }
    diff_json  = models.JSONField(default=dict, blank=True)
    notes      = models.TextField(blank=True, default='')

    class Meta:
        verbose_name = "Batch Audit Log"
        verbose_name_plural = "Batch Audit Logs"
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.get_action_display()} — {self.project} — {self.performed_by} @ {self.timestamp:%Y-%m-%d %H:%M}"


 
class SampleQC(models.Model):
    """
    QC measurement results for a sample
    Metrics depend on sample type:
      DNA : QubitNM, Nanodrop260280, Nanodrop260230
      RNA : RIN, dv200, QubitNM

    (Unused metrics are left null)
    """
 
    PASS = 'Pass'
    FAIL = 'Fail'
    CAUTION = 'Caution'
    PENDING = 'Pending'
    QC_STATUS_CHOICES = [
        (PASS,    _('Pass')),
        (FAIL,    _('Fail')),
        (CAUTION, _('Caution')),
        (PENDING, _('Pending')),
    ]
 
    
    sample = models.ForeignKey(
        Sample,
        on_delete=models.PROTECT,           # never silently lose QC data
        related_name='qc_results'
    )
    batch = models.ForeignKey(
        SampleQCBatch,
        on_delete=models.PROTECT,           # batch must be cleared before deletion
        related_name='qc_results'
    )
 

    #TODO Decimal places of the parameters

    # Shared
    qubit_nm = models.FloatField(
        null=True, blank=True,
    )
    
    # RNA only
    rin = models.FloatField(
        null=True, blank=True,
    )

    dv200 = models.FloatField(
        null=True, blank=True,
    )
    
    # DNA Only
    nanodrop_260_280 = models.FloatField(
        null=True, 
        blank=True
    )

    nanodrop_260_230 = models.FloatField(
        null=True,
        blank=True
    )
    

    qc_status = models.CharField(
        max_length=20,
        choices=QC_STATUS_CHOICES,
        default=PENDING
    )

    notes = models.TextField(blank=True, default='')
 
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    edited_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='sample_qc_edited'
    )

    def calculate_qc_status(self) -> str:
        """
        Automatically determine QC status based on sample type and measured values.
        Returns 'Pass', 'Fail', 'Caution', or 'Pending' if data is missing.
        """
        sample_type = self.sample.sample_type  # 'DNA' or 'RNA'

        if sample_type == 'DNA':
            # Need all three values to evaluate
            if any(v is None for v in [self.qubit_nm, self.nanodrop_260_280, self.nanodrop_260_230]):
                return self.PENDING

            qubit_total = self.qubit_nm * 100  # assumes 100 µL elution volume

            if qubit_total > 100 and self.nanodrop_260_280 > 1.79 and self.nanodrop_260_230 > 1.7:
                return self.PASS
            elif self.nanodrop_260_230 > 1.4:
                return self.CAUTION
            else:
                return self.FAIL

        elif sample_type == 'RNA':
            # Need qubit at minimum
            if self.qubit_nm is None:
                return self.PENDING
            if self.rin is None and self.dv200 is None:
                return self.PENDING

            qubit_total = self.qubit_nm * 40  # assumes 40 µL elution volume

            rin   = self.rin   if self.rin   is not None else 0
            dv200 = self.dv200 if self.dv200 is not None else 0

            passes_quantity = qubit_total > 100
            passes_quality  = (
                rin > 5
                or (rin > 2 and dv200 > 55)
                or dv200 > 62          # dv200 > L3+7 where L3=55
            )

            if passes_quantity and passes_quality:
                return self.PASS
            elif (1.99 <= rin < 5) and (40 <= dv200 < 55):
                return self.CAUTION
            else:
                return self.FAIL

        return self.PENDING



    # DNA and RNA Validation 
    def clean(self):

        super().clean()

        if not self.sample:
            return

        sample_type = self.sample.sample_type

        if self.qubit_nm is None: 
            raise ValidationError({
                    'qubit_nm': 'Qubit nm should be set'
                })

        #Positives validation
        if self.qubit_nm is not None and self.qubit_nm <= 0:
            raise ValidationError({'qubit_nm': 'Qubit nm must be a positive number.'})

        if self.rin is not None and self.rin <= 0:
            raise ValidationError({'rin': 'RIN must be a positive number.'})

        if self.dv200 is not None and self.dv200 <= 0:
            raise ValidationError({'dv200': 'DV200 must be a positive number.'})

        if self.nanodrop_260_230 is not None and self.nanodrop_260_230 <= 0:
            raise ValidationError({'nanodrop_260_230': 'Nanodrop 260/230 must be a positive number.'})

        if self.nanodrop_260_280 is not None and self.nanodrop_260_280 <= 0:
            raise ValidationError({'nanodrop_260_280': 'Nanodrop 260/280 must be a positive number.'})


        if sample_type == "RNA":

            #TODO PENDING is possible? 
            # Required RNA fields
            #if self.rin is None:
            #    raise ValidationError({
            #        'rin': 'RIN is required for RNA samples.'
            #    })

            #if self.dv200 is None:
            #    raise ValidationError({
            #        'dv200': 'DV200 is required for RNA samples.'
            #    })

            # DNA fields should not be used
            if self.nanodrop_260_230 is not None:
                raise ValidationError({
                    'nanodrop_260_230': 'Nanodrop 260/230 should not be set for RNA samples.'
                })
            if self.nanodrop_260_280 is not None:
                raise ValidationError({
                    'nanodrop_260_280': 'Nanodrop_260_280 should not be set for RNA samples.'
                })


        elif sample_type == "DNA":

            # Required DNA field
            #if self.nanodrop_260_230 is None:
            #    raise ValidationError({
            #        'nanodrop_260_230': 'Nanodrop 260/230 is required for DNA samples.'
            #    })
            #if self.nanodrop_260_280 is not None:
            #    raise ValidationError({
            #        'nanodrop_260_280': 'Nanodrop_260_280 is required for DNA samples.'
            #    })

            # RNA fields should not be used
            if self.rin is not None:
                raise ValidationError({
                    'rin': 'RIN should not be set for DNA samples.'
                })

            if self.dv200 is not None:
                raise ValidationError({
                    'dv200': 'DV200 should not be set for DNA samples.'
                })

    def save(self, *args, skip_validation=False, **kwargs):
        # skip_validation=True is used when creating a blank PENDING stub
        # (all metrics null) from the batch board — there is nothing to validate yet.
        if not skip_validation:
            self.full_clean()
        self.qc_status = self.calculate_qc_status()
        super().save(*args, **kwargs)


    def __str__(self):
        return f"QC {self.sample}({self.qc_status})"

    """
    QC measurement results for a sample.
    Metrics depend on sample type:
      DNA : qubit_nm, nanodrop_260_280, nanodrop_260_230
      RNA : qubit_nm, rin, dv200

    (Unused metrics are left null.)
    """

    PASS    = 'Pass'
    FAIL    = 'Fail'
    CAUTION = 'Caution'
    PENDING = 'Pending'
    QC_STATUS_CHOICES = [
        (PASS,    _('Pass')),
        (FAIL,    _('Fail')),
        (CAUTION, _('Caution')),
        (PENDING, _('Pending')),
    ]

    sample = models.ForeignKey(
        Sample,
        on_delete=models.PROTECT,
        related_name='qc_results'
    )
    batch = models.ForeignKey(
        SampleQCBatch,
        on_delete=models.PROTECT,
        related_name='qc_results'
    )
