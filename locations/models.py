from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError

# Models for : Location and Temp_logs

class Location(models.Model):

    # Location ID automatique with djangos

    # Locations options
    VANISHING_CABINET = 'Vanishing Cabinet'
    NETLIX_N_CHILL = 'Netflix N Chill'
    JAMES_BOND = 'James Bond'
    YETI = 'Yeti'
    PRE_PCR_ROOM = 'Pre-PCR Room'
    POST_PCR_ROOM = 'Post-PCR Room'
    FLOOR4FREEZER80C = '4th floor -80C Freezer'
    FLOOR4FREEZER20C = '4th floor -20C Freezer'

    LOCATION_CHOICES = [
        (VANISHING_CABINET, _('Vanishing Cabinet')),
        (NETLIX_N_CHILL, _('Netflix N Chill')),
        (JAMES_BOND, _('James Bond')),
        (YETI, _('Yeti')),
        (PRE_PCR_ROOM, _('Pre-PCR Room')),
        (POST_PCR_ROOM, _('Post-PCR Room')),
        (FLOOR4FREEZER80C, _('4th floor -80C Freezer')),
        (FLOOR4FREEZER20C, _('4th floor -20C Freezer')),
    ]

    # Storage Type options
    ROOMTEMPATURE = 'Room-Temperature'
    FRIDGE4C = 'Fridge(4C)'
    FREEZER20C = 'Freezer(-20C)'
    FREEZER80C = 'Freezer(-80C)'

    STORAGE_TYPE_CHOICES = [
        (ROOMTEMPATURE, _('Room-Temperature')),
        (FRIDGE4C, _('Fridge(4C)')),
        (FREEZER20C, _('Freezer(-20C)')),
        (FREEZER80C, _('Freezer(-80C)')),
    ]

    storageType = models.CharField(
        max_length=255,
        choices=STORAGE_TYPE_CHOICES
    )

    locationName = models.CharField(
        max_length=255,
        choices=LOCATION_CHOICES
    )

    def __str__(self):
        return f"{self.locationName} ({self.storageType})"


class TempLog(models.Model):
    """
    Daily temperature and humidity log for a storage location.
    Linked to Location so you can pull all logs for a given freezer.

    """
    temp_log_id = models.AutoField(primary_key=True)

    location = models.ForeignKey(
        Location,
        on_delete=models.PROTECT,       # keep historical logs even if location is renamed
        related_name='templogs'
    )

    date_logged = models.DateField(auto_now_add=True)
    current_temp_c = models.DecimalField(max_digits=5, decimal_places=2)
    max_temp_c = models.DecimalField(max_digits=5, decimal_places=2)
    min_temp_c = models.DecimalField(max_digits=5, decimal_places=2)

    # Humidity only applies to room-temperature locations
    max_humidity = models.DecimalField(
        max_digits=5, decimal_places=2,
        null=True, blank=True,
        help_text="Room locations only."
    )
    min_humidity = models.DecimalField(
        max_digits=5, decimal_places=2,
        null=True, blank=True,
        help_text="Room locations only."
    )

    def clean(self):
        super().clean()

        # Humidity required for room-temperature locations
        if self.location.storageType == Location.ROOMTEMPATURE:

            if self.max_humidity is None:
                raise ValidationError({
                    'max_humidity': 'Max humidity is required for room-temperature locations.'
                })

            if self.min_humidity is None:
                raise ValidationError({
                    'min_humidity': 'Min humidity is required for room-temperature locations.'
                })

        else:
            # Optional: prevent humidity for freezer/fridge locations
            if self.max_humidity is not None or self.min_humidity is not None:
                raise ValidationError(
                    'Humidity values should only be set for room-temperature locations.'
                )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
        
    class Meta:
        ordering = ['-date_logged']
        verbose_name = "Temperature Log"
        verbose_name_plural = "Temperature Logs"
        unique_together = ('location', 'date_logged')   # one log entry per location per day

    def __str__(self):
        return f"{self.location}—{self.date_logged}"