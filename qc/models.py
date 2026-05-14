
from django.db import models
from django.utils.translation import gettext_lazy as _
from samples.models import Sample

# Model for: SampleQCBatch, BatchSample, SampleQC
 
class SampleQCBatch(models.Model):

    batch_name = models.CharField(max_length=255)
    date_batched = models.DateField()

    #TODO create lab users
    created_by = models.CharField(max_length=255)
 
    # ManyToMany to Sample through the explicit junction table BatchSample.
    # Django creates no extra table itself — BatchSample is the junction.

    samples = models.ManyToManyField(
        Sample,
        through='BatchSample',
        related_name='qc_batches'
    )
 
    class Meta:
        verbose_name = "Sample QC Batch"
        verbose_name_plural = "Sample QC Batches"
        ordering = ['-date_batched']
 
    def __str__(self):
        return f"{self.batch_name} ({self.date_batched})"
 
    @property
    def sample_count(self):
        return self.samples.count()
 
 
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

    qubit_nm = models.FloatField(
        null=True, blank=True,
    )
 
    rin = models.FloatField(
        null=True, blank=True,
    )

    dv200 = models.FloatField(
        null=True, blank=True,
    )
 
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

 
    def __str__(self):
        return f"QC {self.sample} — {self.qc_status}"
