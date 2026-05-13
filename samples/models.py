from django.db import models

# Create your models here.


from django.db import models
from django.utils.translation import gettext_lazy as _

# Model for : Client, Case, Specimen, Samples and Projects



#TODO Look at all the on_delete behaviors for good implementation in the lab



class Client(models.Model):
    client_id = models.AutoField(primary_key=True)
    client_name = models.CharField(max_length=255)
    organisation_name = models.CharField(max_length=255)

    def __str__(self):
        return self.client_name


class Case(models.Model):
    case_id = models.AutoField(primary_key=True)
    client = models.ForeignKey(
        Client,
        on_delete=models.PROTECT,
        related_name="cases"
    )
    case_name = models.CharField(max_length=255)

    def __str__(self):
        return self.case_name


class Project(models.Model):
    project_id = models.AutoField(primary_key=True)
    client = models.ForeignKey(
        Client,
        on_delete=models.PROTECT,
        related_name="projects"
    )

    project_name = models.CharField(max_length=255)
    sequencing_type = models.CharField(max_length=255)
    date_created = models.DateField(auto_now_add=True)

    def __str__(self):
        return self.project_name


class Specimen(models.Model):

    specimen_id = models.AutoField(primary_key=True)

    case = models.ForeignKey(
        Case,
        on_delete=models.PROTECT,
        related_name="specimens"
    )

    specimen_name = models.CharField(max_length=255)

    # Speciment origin 
    BLOOD = 'Blood'
    FFPE = 'FFPE'
    FROZENTISSUE = 	'Frozen Tissue'
    EV = 'EV'

    SPECIMEN_ORIGIN_CHOICES = [
        (BLOOD, _('Blood')),
        (FFPE, _('FFPE')),
        (FROZENTISSUE, _('Frozen Tissue')),
        (EV, _('EV')),
    ]
    specimen_origin = models.CharField(max_length=255, choices=SPECIMEN_ORIGIN_CHOICES)

    def __str__(self):
        return self.specimen_name


class Sample(models.Model):
    
    sample_id = models.AutoField(primary_key=True)

    specimen = models.ForeignKey(
        Specimen,
        on_delete=models.PROTECT,
        related_name="samples"
    )

    project = models.ForeignKey(
        Project,
        on_delete=models.PROTECT,
        related_name="samples"
    )

    parent_sample = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='re_extraction',
        
    )

    location = models.ForeignKey(
        'locations.Location',
        on_delete=models.PROTECT,
        null=True,
        blank=True
    )
   
    
    date_received = models.DateField()

    volume_received = models.FloatField()

    # Sample Type 
    DNA = 'DNA'
    RNA = 'RNA'

    SAMPLE_TYPE_CHOICES = [
        (DNA, _('DNA')),
        (RNA, _('RNA'))
    ]
    sample_type = models.CharField(max_length=10, choices=SAMPLE_TYPE_CHOICES)

    # Receiving condition 
    TUBES = 'Tubes'
    PLATES = 'Plates'
    TUBES_STRIPS = 'Tube Strips'

    RECEIVING_CONDITION_CHOICES = [
        (TUBES, _('Tubes')),
        (PLATES, _('Plates')),
        (TUBES_STRIPS, _('Tube Strips'))
    ]
    receiving_condition = models.CharField(max_length=255, choices=RECEIVING_CONDITION_CHOICES)


    # TODO automatique to lab format name? : Study-Cohort-TissueType-CaseNo-SpecimenType-SpecimenNo-SampleType-SampleExtractionNo : ACC-PanCancer-FFPE-380-N-1-DNA-1

    sample_name = models.CharField(max_length=255, unique=True)

    def __str__(self):
        return self.sample_name