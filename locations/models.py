from django.db import models
from django.utils.translation import gettext_lazy as _

# Models for : Location and Temp_logs

class Loaction(models.Model):

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



# TODO Decimal places for the lab machines
class Temp_Logs(models.Model):

    location = models.ForeignKey(Loaction, on_delete=models.PROTECT)

    dateLogged = models.DateTimeField( auto_now_add=True)

    currentTempC = models.DecimalField( max_digits=2, decimal_places=1)

    maxTempC = models.DecimalField( max_digits=2, decimal_places=1)
    minTempC = models.DecimalField( max_digits=2, decimal_places=1)

    #TODO only for the Rooms
    maxHumidity = models.DecimalField( max_digits=2, decimal_places=1, blank=True, null=True)
    minHumidity = models.DecimalField( max_digits=2, decimal_places=1, blank=True, null=True)
