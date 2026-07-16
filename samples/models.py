from django.db import models


from django.db import models
from django.utils.translation import gettext_lazy as _

from locations.models import Location

from django.contrib.auth import get_user_model
User = get_user_model()

# Model for : Client, Case, Specimen, Samples and Projects

#TODO Look at all the on_delete behaviors for good implementation in the lab

class Client(models.Model):
    client_id = models.AutoField(primary_key=True)
    client_name = models.CharField(max_length=255)
    organisation_name = models.CharField(max_length=255)

    def __str__(self):
        return f"{self.client_name}"

class UserProfile(models.Model):
    """
    Links a Django User to a Client (researcher account).
    Lab staff have NO UserProfile that's how we tell them apart.
    Researchers have a UserProfile pointing to their Client.
    """
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='profile'
    )
    client = models.ForeignKey(
        Client,
        on_delete=models.PROTECT,
        related_name='users',
        null=True, blank=True,
        help_text="Leave blank for lab staff. Set for researcher/client accounts."
    )

    def is_researcher(self):
        """Returns True if this user is a client/researcher (not lab staff)."""
        return self.client is not None

    def __str__(self):
        if self.client:
            return f"{self.user.username} → {self.client.client_name}"
        return f"{self.user.username} (lab staff)"

    class Meta:
        verbose_name = "User Profile"
        verbose_name_plural = "User Profiles"

class Case(models.Model):
    case_id = models.AutoField(primary_key=True)
    client = models.ForeignKey(
        Client,
        on_delete=models.PROTECT,
        related_name="cases"
    )
    case_name = models.CharField(max_length=255)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['client', 'case_name'],
                name='unique_case_per_client'
            )
        ]

    def __str__(self):
        return self.case_name


class Project(models.Model):
    project_id = models.AutoField(primary_key=True)
    client = models.ForeignKey(
        Client,
        on_delete=models.PROTECT,
        related_name="projects"
    )

    project_name = models.CharField(max_length=255, unique=True)
    sequencing_type = models.CharField(max_length=255)
    date_created = models.DateField(auto_now_add=True)

    def __str__(self):
        return f"{self.project_name}"

class SpecimenType(models.Model):

    specimen_type = models.CharField(max_length=255, primary_key=True)

    def __str__(self):
        return self.specimen_type


class Specimen(models.Model):

    specimen_id = models.AutoField(primary_key=True)

    case = models.ForeignKey(
        Case,
        on_delete=models.PROTECT,
        related_name="specimens"
    )

    specimen_type = models.ForeignKey(SpecimenType, on_delete=models.PROTECT)

    # Speciment origin 
    #BLOOD = 'Blood'
    #FFPE = 'FFPE'
    #FROZENTISSUE = 	'Frozen Tissue'
    #EV = 'EV'
    #SPECIMEN_ORIGIN_CHOICES = [
    #    (BLOOD, _('Blood')),
    #    (FFPE, _('FFPE')),
    #    (FROZENTISSUE, _('Frozen Tissue')),
    #    (EV, _('EV')),
    #]
    #specimen_origin = models.CharField(max_length=255, choices=SPECIMEN_ORIGIN_CHOICES)
    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['case', 'specimen_type'],
                name='unique_specimen_per_case'
            )
        ]
    def __str__(self):
        return f"{self.case.case_name}—{self.specimen_type.specimen_type}"


class Sample(models.Model):
    # AutoField so Django assigns the integer, we then convert it to hex for the name
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
    location = models.ForeignKey(
        Location,
        on_delete=models.PROTECT,
        null=True,
        blank=True
    )
 
    # blank=True so Django doesn't require it on the form, we generate it in save()
    sample_name = models.CharField(max_length=255, unique=True, blank=True)
 
    DNA = 'DNA'
    RNA = 'RNA'
    SAMPLE_TYPE_CHOICES = [
        (DNA, _('DNA')),
        (RNA, _('RNA')),
    ]
    sample_type = models.CharField(max_length=10, choices=SAMPLE_TYPE_CHOICES)
 
    date_received = models.DateField(auto_now_add=True)
    volume_received = models.FloatField(null=True, blank=True)
    
    
    concentration = models.FloatField(
        null=True, blank=True
    )

    TUBES = 'Tubes'
    PLATES = 'Plates'
    TUBES_STRIPS = 'Tube Strips'
    RECEIVING_CONDITION_CHOICES = [
        (TUBES,       _('Tubes')),
        (PLATES,      _('Plates')),
        (TUBES_STRIPS,_('Tube Strips')),
    ]
    receiving_condition = models.CharField(
        max_length=255,
        choices=RECEIVING_CONDITION_CHOICES,
        blank=True
    )
    compliance = models.BooleanField(default=True)
    notes =  models.CharField(max_length=255, blank=True)

    def _generate_sample_name(self):
        """
        Format: CaseName-SpecimenType-SampleType-5HexID
        Example: MCF10A-Cells-RNA-000C8
 
        The hex ID is the sample_id zero-padded to 5 uppercase hex digits.
        Sample 200  → 000C8
        Sample 1    → 00001
        Sample 65535 → 0FFFF
        """
        case_name     = self.specimen.case.case_name
        specimen_type = self.specimen.specimen_type.specimen_type
        sample_type   = self.sample_type
        hex_id        = format(self.sample_id, '05X')   # 5 digits, uppercase, zero-padded
        return f"{case_name}-{specimen_type}-{sample_type}-{hex_id}"
 
    def save(self, *args, **kwargs):
        # First save to get the auto-incremented sample_id from the DB
        super().save(*args, **kwargs)
        # Now generate the name using the real ID
        self.sample_name = self._generate_sample_name()
        # Save again to store the generated name
        super().save(update_fields=['sample_name'])
        
 
    def __str__(self):
        return self.sample_name
