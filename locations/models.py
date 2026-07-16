from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import RegexValidator, MinValueValidator, MaxValueValidator
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model

User = get_user_model()


class WellType(models.TextChoices):
    SAMPLE      = "sample",      _("Sample")
    LIBRARY     = "library",     _("Library Prep")
    SEQUENCING  = "sequencing",  _("Sequencing Batch")
    CONTROL     = "control",     _("Control")
    EMPTY       = "empty",       _("Empty")

class PlateFormat(models.TextChoices):
    F_96   = "96",   _("96-well  (8 × 12)")
    F_24   = "24",   _("24-well  (4 × 6)")
    CUSTOM = "CUSTOM", _("Custom")


# Regex for well positions: A01, H12
WELL_POSITION_RE = RegexValidator(
    regex=r"^[A-P](?:0[1-9]|1[0-9]|2[0-4]|[1-9])$",
    message="Well position must be in the form 'A01' … 'H12'",
)

# Regex for rack slot positions: A1 … D4, optionally suffixed T (top) or B (bottom)
RACK_SLOT_RE = RegexValidator(
    regex=r"^[A-D][1-4][TB]?$",
    message="Rack slot must be in the form 'A1', 'A1T', or 'A1B'.",
)


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

    logged_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='temp_logs'
    )

    def clean(self):
        super().clean()

        # min ≤ current ≤ max 
        if self.min_temp_c is not None and self.current_temp_c is not None:
            if self.min_temp_c > self.current_temp_c:
                raise ValidationError({
                    'min_temp_c': f'Min ({self.min_temp_c}°C) cannot be greater than current ({self.current_temp_c}°C).'
                })

        if self.current_temp_c is not None and self.max_temp_c is not None:
            if self.current_temp_c > self.max_temp_c:
                raise ValidationError({
                    'current_temp_c': f'Current ({self.current_temp_c}°C) cannot be greater than max ({self.max_temp_c}°C).'
                })

        if self.min_temp_c is not None and self.max_temp_c is not None:
            if self.min_temp_c > self.max_temp_c:
                raise ValidationError({
                    'min_temp_c': f'Min ({self.min_temp_c}°C) cannot be greater than max ({self.max_temp_c}°C).'
                })


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



class Rack(models.Model):
    """
    A physical rack that lives inside a Location.
    A rack has a fixed grid of slots (default 4 rows × 4 cols = 16 slots,
    """
    location = models.ForeignKey(
        Location,
        on_delete=models.PROTECT,
        related_name="racks",
    )
    rack_name = models.CharField(
        max_length=80,
        help_text="e.g. 'Rack 1', 'Rack 2' …",
    )
    # Grid dimensions (overrideable for non-standard racks)
    rows = models.PositiveSmallIntegerField(
        default=4,
        validators=[MinValueValidator(1), MaxValueValidator(16)],
        help_text="Number of rows (A … D by default).",
    )
    cols = models.PositiveSmallIntegerField(
        default=4,
        validators=[MinValueValidator(1), MaxValueValidator(24)],
        help_text="Number of columns (1 … 4 by default).",
    )
    notes = models.TextField(blank=True)

    # Audit
    created_by = models.ForeignKey(
        User,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="racks_created",
    )
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("location", "rack_name")]
        ordering = ["location", "rack_name"]
        verbose_name = "Rack"
        verbose_name_plural = "Racks"

    def __str__(self):
        return f"{self.rack_name} @ {self.location.locationName}"

    @property
    def capacity(self):
        return self.rows * self.cols

    @property
    def occupied_slots(self):
        return self.plates.count()

    @property
    def available_slots(self):
        return self.capacity - self.occupied_slots


class Plate(models.Model):
    """
    A physical plate (96-well) that occupies.

    rack_location stores the slot string, e.g. 'A1', 'B3'.
    The frontend drag-and-drop will write this field when the user places a
    plate on the rack grid.
    """
    # Where it lives
    location = models.ForeignKey(
        Location,
        on_delete=models.PROTECT,
        related_name="plates",
        help_text="Denormalised for fast location queries (mirrors Rack→Location).",
    )
    rack = models.ForeignKey(
        Rack,
        on_delete=models.PROTECT,
        related_name="plates",
        null=True, blank=True,
        help_text="Null if the plate is not yet placed on a rack.",
    )
    rack_location = models.CharField(
        max_length=4,
        blank=True,
        validators=[RACK_SLOT_RE],
        help_text="Slot on the rack grid, e.g. 'A1', 'C3'.",
    )

    # Plate identity
    plate_name = models.CharField(
        max_length=160,
        help_text="Plate barcode or human label, e.g. 'ACC-Mat-Batch-16-WGS-Lib-Prep-2-Kappa'.",
    )
    plate_format = models.CharField(
        max_length=10,
        choices=PlateFormat.choices,
        default=PlateFormat.F_96,
    )
    # For CUSTOM format, record actual dimensions
    custom_rows = models.PositiveSmallIntegerField(null=True, blank=True)
    custom_cols = models.PositiveSmallIntegerField(null=True, blank=True)

    notes = models.TextField(blank=True)

    # Audit
    created_by = models.ForeignKey(
        User,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="plates_created",
    )
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        
        ordering = ["rack", "rack_location", "plate_name"]
        verbose_name = "Plate"
        verbose_name_plural = "Plates"

    def __str__(self):
        slot = f" [{self.rack_location}]" if self.rack_location else ""
        rack = f" in {self.rack}" if self.rack else ""
        return f"{self.plate_name}{slot}{rack}"

    @property
    def rows(self):
        """Return actual row count based on format."""
        mapping = {"96": 8, "48": 6, "24": 4}
        return self.custom_rows if self.plate_format == "CUSTOM" else mapping.get(self.plate_format, 8)

    @property
    def cols(self):
        mapping = {"96": 12, "48": 8, "24": 6}
        return self.custom_cols if self.plate_format == "CUSTOM" else mapping.get(self.plate_format, 12)

    @property
    def well_count(self):
        return self.rows * self.cols



class PlateWell(models.Model):
    """
    A single well on a Plate. 

    The well can reference a Sample, a LibPrepLibrary, or a SequencingBatch
    (all nullable).  Only one should be set at a time, enforced by the
    clean() method and a DB check constraint.

    well_type drives the frontend colour coding and filtering:
        'sample'     → raw sample aliquot
        'library'    → completed library prep
        'sequencing' → sequencing batch / pool
        'control'    → positive / negative control
        'empty'      → placeholder (drag-and-drop target)

    """

    plate = models.ForeignKey(
        Plate,
        on_delete=models.CASCADE,
        related_name="wells",
    )
    well_position = models.CharField(
        max_length=4,
        validators=[WELL_POSITION_RE],
        help_text="Well address, e.g. 'A01', 'H12'.",
    )
    well_type = models.CharField(
        max_length=20,
        choices=WellType.choices,
        default=WellType.EMPTY,
    )

    # --- Content FKs (only one should be non-null at a time) ---------------

    # Link to the core Sample model (adjust app_label to match your project)
    sample = models.ForeignKey(
        "samples.Sample",           # <-- update app_label if needed
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="plate_wells",
        help_text="Set when this well holds a raw sample aliquot.",
    )

    # Placeholder FK for LibPrepLibrary uncomment once that model exists
    # lib_prep_library = models.ForeignKey(
    #     "libprep.LibPrepLibrary",
    #     null=True, blank=True,
    #     on_delete=models.SET_NULL,
    #     related_name="plate_wells",
    #     help_text="Set when this well holds a library prep.",
    # )

    # Placeholder FK for SequencingBatch uncomment once that model exists
    # sequencing_batch = models.ForeignKey(
    #     "sequencing.SequencingBatch",
    #     null=True, blank=True,
    #     on_delete=models.SET_NULL,
    #     related_name="plate_wells",
    #     help_text="Set when this well holds a sequencing pool.",
    # )

    # Optional metadata
    volume_ul = models.FloatField(
        null=True, blank=True,
        validators=[MinValueValidator(0)],
        help_text="Volume in µL loaded into the well.",
    )
    concentration_nm = models.FloatField(
        null=True, blank=True,
        validators=[MinValueValidator(0)],
        help_text="Concentration in nM (relevant for library prep wells).",
    )
    notes = models.TextField(blank=True)

    # Audit
    created_by = models.ForeignKey(
        User,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="wells_created",
    )
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("plate", "well_position")]
        ordering = ["plate", "well_position"]
        verbose_name = "Plate Well"
        verbose_name_plural = "Plate Wells"

    def __str__(self):
        return f"{self.plate.plate_name} – {self.well_position} ({self.get_well_type_display()})"

    def clean(self):
        """
        Enforce that at most one content FK is set.
        Extend this list when lib_prep_library / sequencing_batch FKs are added.
        """
        from django.core.exceptions import ValidationError
        content_fields = [
            self.sample_id,
            # self.lib_prep_library_id,
            # self.sequencing_batch_id,
        ]
        filled = [f for f in content_fields if f is not None]
        if len(filled) > 1:
            raise ValidationError(
                "A well can only reference one content type "
                "(sample, library, or sequencing batch) at a time."
            )

    @property
    def is_empty(self):
        return self.well_type == WellType.EMPTY

    @property
    def content_object(self):
        """Return whichever content object is set, or None."""
        return (
            self.sample
            # or self.lib_prep_library
            # or self.sequencing_batch
            or None
        )


class PlateLayout(models.Model):
    """
    Stores a named layout / template for a plate so the frontend can
    save/restore drag-and-drop arrangements before committing them to
    individual PlateWell records.

    Workflow:
        1. User opens the drag-and-drop plate editor.
        2. Frontend saves interim state here as JSON.
        3. On 'Commit', the backend iterates layout_data and creates/updates
           PlateWell rows accordingly.
    """
    plate = models.ForeignKey(
        Plate,
        on_delete=models.CASCADE,
        related_name="layouts",
    )
    layout_name = models.CharField(
        max_length=120,
        default="Draft",
        help_text="e.g. 'Draft', 'Submitted', 'Committed'.",
    )
    is_committed = models.BooleanField(
        default=False,
        help_text="True once the layout has been written to PlateWell records.",
    )
    # JSON blob: { "A01": {"type": "library", "content_id": 42}, "A02": … }
    layout_data = models.JSONField(
        default=dict,
        help_text="Serialised well assignments from the drag-and-drop editor.",
    )

    # Audit
    created_by = models.ForeignKey(
        User,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="plate_layouts_created",
    )
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Plate Layout"
        verbose_name_plural = "Plate Layouts"

    def __str__(self):
        committed = "✓" if self.is_committed else "draft"
        return f"{self.plate.plate_name} – {self.layout_name} [{committed}]"