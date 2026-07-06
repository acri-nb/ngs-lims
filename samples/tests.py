
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.contrib.auth import get_user_model

from .models import Client, UserProfile, Case, Project, SpecimenType, Specimen, Sample

User = get_user_model()


class ClientModelTests(TestCase):
    def test_str_returns_client_name(self):
        client = Client.objects.create(client_name="Acme Labs", organisation_name="Acme Corp")
        self.assertEqual(str(client), "Acme Labs")


class UserProfileModelTests(TestCase):
    def setUp(self):
        self.client_obj = Client.objects.create(client_name="Acme Labs", organisation_name="Acme Corp")

    def test_lab_staff_has_no_client(self):
        user = User.objects.create_user(username="tech1", password="x")
        profile = UserProfile.objects.create(user=user)
        self.assertFalse(profile.is_researcher())
        self.assertEqual(str(profile), "tech1 (lab staff)")

    def test_researcher_has_client(self):
        user = User.objects.create_user(username="researcher1", password="x")
        profile = UserProfile.objects.create(user=user, client=self.client_obj)
        self.assertTrue(profile.is_researcher())
        self.assertEqual(str(profile), "researcher1 → Acme Labs")

    def test_one_profile_per_user(self):
        user = User.objects.create_user(username="tech2", password="x")
        UserProfile.objects.create(user=user)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                UserProfile.objects.create(user=user)


class CaseModelTests(TestCase):
    def setUp(self):
        self.client_obj = Client.objects.create(client_name="Acme Labs", organisation_name="Acme Corp")

    def test_str_returns_case_name(self):
        case = Case.objects.create(client=self.client_obj, case_name="MCF10A")
        self.assertEqual(str(case), "MCF10A")

    def test_case_name_unique_per_client(self):
        Case.objects.create(client=self.client_obj, case_name="MCF10A")
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Case.objects.create(client=self.client_obj, case_name="MCF10A")

    def test_same_case_name_allowed_across_different_clients(self):
        other_client = Client.objects.create(client_name="Other Labs", organisation_name="Other Corp")
        Case.objects.create(client=self.client_obj, case_name="MCF10A")
        # Should not raise — uniqueness is scoped per client.
        Case.objects.create(client=other_client, case_name="MCF10A")


class ProjectModelTests(TestCase):
    def setUp(self):
        self.client_obj = Client.objects.create(client_name="Acme Labs", organisation_name="Acme Corp")

    def test_str_and_uniqueness(self):
        project = Project.objects.create(
            client=self.client_obj, project_name="ACME2024", sequencing_type="WGS"
        )
        self.assertEqual(str(project), "ACME2024")
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Project.objects.create(
                    client=self.client_obj, project_name="ACME2024", sequencing_type="WGS"
                )

    def test_date_created_auto_populated(self):
        project = Project.objects.create(
            client=self.client_obj, project_name="ACME2025", sequencing_type="WGS"
        )
        self.assertIsNotNone(project.date_created)


class SpecimenModelTests(TestCase):
    def setUp(self):
        self.client_obj = Client.objects.create(client_name="Acme Labs", organisation_name="Acme Corp")
        self.case = Case.objects.create(client=self.client_obj, case_name="MCF10A")
        self.specimen_type = SpecimenType.objects.create(specimen_type="Blood")

    def test_str(self):
        specimen = Specimen.objects.create(case=self.case, specimen_type=self.specimen_type)
        self.assertEqual(str(specimen), "MCF10A—Blood")

    def test_unique_specimen_per_case_and_type(self):
        Specimen.objects.create(case=self.case, specimen_type=self.specimen_type)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Specimen.objects.create(case=self.case, specimen_type=self.specimen_type)

    def test_same_specimen_type_allowed_on_different_case(self):
        other_case = Case.objects.create(client=self.client_obj, case_name="HEK293")
        Specimen.objects.create(case=self.case, specimen_type=self.specimen_type)
        # Should not raise — uniqueness is scoped per case.
        Specimen.objects.create(case=other_case, specimen_type=self.specimen_type)


class SampleModelTests(TestCase):
    def setUp(self):
        self.client_obj = Client.objects.create(client_name="Acme Labs", organisation_name="Acme Corp")
        self.case = Case.objects.create(client=self.client_obj, case_name="MCF10A")
        self.specimen_type = SpecimenType.objects.create(specimen_type="Cells")
        self.specimen = Specimen.objects.create(case=self.case, specimen_type=self.specimen_type)
        self.project = Project.objects.create(
            client=self.client_obj, project_name="ACME2024", sequencing_type="WGS"
        )

    def test_sample_name_auto_generated_on_save(self):
        sample = Sample.objects.create(
            specimen=self.specimen, project=self.project, sample_type=Sample.RNA
        )
        expected_hex = format(sample.sample_id, "05X")
        expected_name = f"MCF10A-Cells-RNA-{expected_hex}"
        self.assertEqual(sample.sample_name, expected_name)

    def test_sample_name_zero_padded_to_five_hex_digits(self):
        sample = Sample.objects.create(
            specimen=self.specimen, project=self.project, sample_type=Sample.DNA
        )
        hex_part = sample.sample_name.rsplit("-", 1)[-1]
        self.assertEqual(len(hex_part), 5)
        self.assertEqual(hex_part, hex_part.upper())
        self.assertEqual(int(hex_part, 16), sample.sample_id)

    def test_sample_name_unique(self):
        sample1 = Sample.objects.create(
            specimen=self.specimen, project=self.project, sample_type=Sample.RNA
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                # Force a name collision directly, bypassing auto-generation,
                # to prove the DB-level unique constraint is in place.
                Sample.objects.create(
                    specimen=self.specimen,
                    project=self.project,
                    sample_type=Sample.RNA,
                    sample_name=sample1.sample_name,
                )

    def test_str_returns_sample_name(self):
        sample = Sample.objects.create(
            specimen=self.specimen, project=self.project, sample_type=Sample.RNA
        )
        self.assertEqual(str(sample), sample.sample_name)

    def test_location_and_optional_fields_are_optional(self):
        # location, volume_received, concentration, receiving_condition,
        # notes are all optional — creation shouldn't require them.
        sample = Sample.objects.create(
            specimen=self.specimen, project=self.project, sample_type=Sample.DNA
        )
        self.assertIsNone(sample.location)
        self.assertIsNone(sample.volume_received)
        self.assertIsNone(sample.concentration)
        self.assertTrue(sample.compliance)  # defaults to True