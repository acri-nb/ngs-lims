
from django.db import models
from django.utils.translation import gettext_lazy as _
from samples.models import Sample

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
            self.batch_name = self._generate_batch_name('LAB')
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
    nanodrop_260_230 = models.FloatField(
        null=True, blank=True,
    )
    
    # TODO automate the calculation of the QC status
    qc_status = models.CharField(
        max_length=20,
        choices=QC_STATUS_CHOICES,
        default=PENDING
    )

    notes = models.TextField(blank=True, default='')
 
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
#
#    # DNA and RNA Validation 
#    def clean(self):
#
#        super().clean()
#
#        if not self.sample:
#            return
#
#        sample_type = self.sample.sample_type
#
#        if sample_type == "RNA":
#
#            # Required RNA fields
#            if self.rin is None:
#                raise ValidationError({
#                    'rin': 'RIN is required for RNA samples.'
#                })
#
#            if self.dv200 is None:
#                raise ValidationError({
#                    'dv200': 'DV200 is required for RNA samples.'
#                })
#
#            # DNA fields should not be used
#            if self.nanodrop_260_230 is not None:
#                raise ValidationError({
#                    'nanodrop_260_230': 'Nanodrop 260/230 should not be set for RNA samples.'
#                })
#
#        elif sample_type == "DNA":
#
#            # Required DNA field
#            if self.nanodrop_260_230 is None:
#                raise ValidationError({
#                    'nanodrop_260_230': 'Nanodrop 260/230 is required for DNA samples.'
#                })
#
#            # RNA fields should not be used
#            if self.rin is not None:
#                raise ValidationError({
#                    'rin': 'RIN should not be set for DNA samples.'
#                })
#
#            if self.dv200 is not None:
#                raise ValidationError({
#                    'dv200': 'DV200 should not be set for DNA samples.'
#                })


    def save(self, *args, **kwargs):
        if self.sample_id:
            self.full_clean()
            super().save(*args, **kwargs)

    def __str__(self):
        return f"QC {self.sample}({self.qc_status})"
