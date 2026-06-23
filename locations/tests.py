from decimal import Decimal

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from .models import Location, TempLog, Rack, Plate

User = get_user_model()


class LocationModelTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username="tester",
            password="test123"
        )

        self.room_location = Location.objects.create(
            locationName=Location.PRE_PCR_ROOM,
            storageType=Location.ROOMTEMPATURE
        )

        self.freezer_location = Location.objects.create(
            locationName=Location.YETI,
            storageType=Location.FREEZER80C
        )


    def test_valid_room_temperature_log(self):
        """
        Room temperature locations require humidity.
        """
        log = TempLog(
            location=self.room_location,
            current_temp_c=Decimal("22.0"),
            min_temp_c=Decimal("20.0"),
            max_temp_c=Decimal("24.0"),
            min_humidity=Decimal("40.0"),
            max_humidity=Decimal("50.0"),
            logged_by=self.user
        )

        log.full_clean()
        log.save()

        self.assertEqual(TempLog.objects.count(), 1)

    def test_room_temperature_requires_max_humidity(self):
        log = TempLog(
            location=self.room_location,
            current_temp_c=22,
            min_temp_c=20,
            max_temp_c=24,
            min_humidity=40,
            logged_by=self.user
        )

        with self.assertRaises(ValidationError):
            log.full_clean()

    def test_room_temperature_requires_min_humidity(self):
        log = TempLog(
            location=self.room_location,
            current_temp_c=22,
            min_temp_c=20,
            max_temp_c=24,
            max_humidity=50,
            logged_by=self.user
        )

        with self.assertRaises(ValidationError):
            log.full_clean()

    def test_freezer_cannot_have_humidity(self):
        log = TempLog(
            location=self.freezer_location,
            current_temp_c=-80,
            min_temp_c=-82,
            max_temp_c=-78,
            min_humidity=20,
            max_humidity=30,
            logged_by=self.user
        )

        with self.assertRaises(ValidationError):
            log.full_clean()

    def test_min_temp_cannot_exceed_current(self):
        log = TempLog(
            location=self.freezer_location,
            current_temp_c=-80,
            min_temp_c=-75,
            max_temp_c=-70,
            logged_by=self.user
        )

        with self.assertRaises(ValidationError):
            log.full_clean()

    def test_current_temp_cannot_exceed_max(self):
        log = TempLog(
            location=self.freezer_location,
            current_temp_c=-70,
            min_temp_c=-80,
            max_temp_c=-75,
            logged_by=self.user
        )

        with self.assertRaises(ValidationError):
            log.full_clean()

    def test_min_temp_cannot_exceed_max(self):
        log = TempLog(
            location=self.freezer_location,
            current_temp_c=-75,
            min_temp_c=-70,
            max_temp_c=-80,
            logged_by=self.user
        )

        with self.assertRaises(ValidationError):
            log.full_clean()

    def test_one_log_per_location_per_day(self):
        """
        unique_together(location, date_logged)
        """

        TempLog.objects.create(
            location=self.freezer_location,
            current_temp_c=-80,
            min_temp_c=-82,
            max_temp_c=-78,
            logged_by=self.user
        )

        with self.assertRaises(IntegrityError):
            TempLog.objects.create(
                location=self.freezer_location,
                current_temp_c=-81,
                min_temp_c=-83,
                max_temp_c=-79,
                logged_by=self.user
            )


    def test_location_string_representation(self):
        self.assertEqual(
            str(self.freezer_location),
            "Yeti (Freezer(-80C))"
        )


class RackTests(TestCase):

    def setUp(self):
        self.location = Location.objects.create(
            locationName=Location.YETI,
            storageType=Location.FREEZER80C
        )

    def test_rack_capacity(self):
        rack = Rack.objects.create(
            location=self.location,
            rack_name="Rack 1",
            rows=4,
            cols=4
        )

        self.assertEqual(rack.capacity, 16)

    def test_available_slots_when_empty(self):
        rack = Rack.objects.create(
            location=self.location,
            rack_name="Rack 1"
        )

        self.assertEqual(rack.occupied_slots, 0)
        self.assertEqual(rack.available_slots, 16)

    def test_unique_rack_name_per_location(self):
        Rack.objects.create(
            location=self.location,
            rack_name="Rack 1"
        )

        with self.assertRaises(IntegrityError):
            Rack.objects.create(
                location=self.location,
                rack_name="Rack 1"
            )


class PlateTests(TestCase):

    def setUp(self):
        self.location = Location.objects.create(
            locationName=Location.YETI,
            storageType=Location.FREEZER80C
        )

    def test_96_well_plate_count(self):
        plate = Plate.objects.create(
            location=self.location,
            plate_name="Plate001"
        )

        self.assertEqual(plate.rows, 8)
        self.assertEqual(plate.cols, 12)
        self.assertEqual(plate.well_count, 96)

    def test_custom_plate_count(self):
        plate = Plate.objects.create(
            location=self.location,
            plate_name="CustomPlate",
            plate_format="CUSTOM",
            custom_rows=5,
            custom_cols=10
        )

        self.assertEqual(plate.well_count, 50)