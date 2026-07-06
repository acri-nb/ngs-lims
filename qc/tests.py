
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.contrib.auth import get_user_model

from samples.models import Client, Case, SpecimenType, Specimen, Project, Sample
from .models import SampleQCBatch, BatchSample, BatchAuditLog, SampleQC

User = get_user_model()


class QCTestBase(TestCase):
    """Shared cross-app fixtures: a client, case, specimen, project, and one DNA + one RNA sample."""

    def setUp(self):
        self.user = User.objects.create_user(username="tech", password="x")
        self.client_obj = Client.objects.create(client_name="Acme Labs", organisation_name="Acme Corp")
        self.case = Case.objects.create(client=self.client_obj, case_name="MCF10A")
        self.specimen_type = SpecimenType.objects.create(specimen_type="Blood")
        self.specimen = Specimen.objects.create(case=self.case, specimen_type=self.specimen_type)
        self.project = Project.objects.create(
            client=self.client_obj, project_name="ACME2024", sequencing_type="WGS"
        )
        self.dna_sample = Sample.objects.create(
            specimen=self.specimen, project=self.project, sample_type=Sample.DNA
        )
        self.rna_sample = Sample.objects.create(
            specimen=self.specimen, project=self.project, sample_type=Sample.RNA
        )


class SampleQCBatchModelTests(QCTestBase):
    def test_batch_name_auto_generated_on_save(self):
        batch = SampleQCBatch.objects.create(
            date_batched="2026-01-01", project=self.project, created_by=self.user
        )
        expected_hex = format(batch.id, "04X")
        self.assertEqual(batch.batch_name, f"ACME2024-SampleQC-{expected_hex}")

    def test_batch_name_not_regenerated_if_already_set(self):
        batch = SampleQCBatch.objects.create(
            date_batched="2026-01-01",
            project=self.project,
            created_by=self.user,
            batch_name="CUSTOM-NAME",
        )
        self.assertEqual(batch.batch_name, "CUSTOM-NAME")

    def test_str_returns_batch_name(self):
        batch = SampleQCBatch.objects.create(
            date_batched="2026-01-01", project=self.project, created_by=self.user
        )
        self.assertEqual(str(batch), batch.batch_name)

    def test_sample_count_property(self):
        batch = SampleQCBatch.objects.create(
            date_batched="2026-01-01", project=self.project, created_by=self.user
        )
        self.assertEqual(batch.sample_count, 0)
        BatchSample.objects.create(batch=batch, sample=self.dna_sample)
        BatchSample.objects.create(batch=batch, sample=self.rna_sample)
        self.assertEqual(batch.sample_count, 2)


class BatchSampleModelTests(QCTestBase):
    def setUp(self):
        super().setUp()
        self.batch = SampleQCBatch.objects.create(
            date_batched="2026-01-01", project=self.project, created_by=self.user
        )

    def test_str(self):
        bs = BatchSample.objects.create(batch=self.batch, sample=self.dna_sample)
        self.assertEqual(str(bs), f"{self.dna_sample} in {self.batch}")

    def test_sample_cannot_appear_twice_in_same_batch(self):
        BatchSample.objects.create(batch=self.batch, sample=self.dna_sample)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                BatchSample.objects.create(batch=self.batch, sample=self.dna_sample)

    def test_same_sample_allowed_in_different_batches(self):
        other_batch = SampleQCBatch.objects.create(
            date_batched="2026-01-02", project=self.project, created_by=self.user
        )
        BatchSample.objects.create(batch=self.batch, sample=self.dna_sample)
        # Should not raise — uniqueness is scoped per batch.
        BatchSample.objects.create(batch=other_batch, sample=self.dna_sample)


class BatchAuditLogModelTests(QCTestBase):
    def test_str_and_defaults(self):
        log = BatchAuditLog.objects.create(
            project=self.project,
            action=BatchAuditLog.ACTION_CREATE,
            performed_by=self.user,
        )
        self.assertEqual(log.diff_json, {})
        self.assertIn("Batch created", str(log))
        self.assertIn(str(self.project), str(log))

    def test_batch_nullable_on_delete_set_null(self):
        batch = SampleQCBatch.objects.create(
            date_batched="2026-01-01", project=self.project, created_by=self.user
        )
        log = BatchAuditLog.objects.create(
            project=self.project, batch=batch, action=BatchAuditLog.ACTION_SAVE, performed_by=self.user
        )
        batch.delete()
        log.refresh_from_db()
        self.assertIsNone(log.batch)


class SampleQCValidationTests(QCTestBase):
    """clean() enforcement of which fields are allowed per sample_type."""

    def test_qubit_nm_required(self):
        qc = SampleQC(sample=self.dna_sample, batch=self._make_batch(), edited_by=self.user)
        with self.assertRaises(ValidationError):
            qc.clean()

    def test_qubit_nm_must_be_positive(self):
        qc = SampleQC(
            sample=self.dna_sample, batch=self._make_batch(), edited_by=self.user, qubit_nm=-1
        )
        with self.assertRaises(ValidationError):
            qc.clean()

    def test_dna_sample_rejects_rna_fields(self):
        qc = SampleQC(
            sample=self.dna_sample,
            batch=self._make_batch(),
            edited_by=self.user,
            qubit_nm=5.0,
            rin=7.0,
        )
        with self.assertRaises(ValidationError):
            qc.clean()

    def test_rna_sample_rejects_dna_fields(self):
        qc = SampleQC(
            sample=self.rna_sample,
            batch=self._make_batch(),
            edited_by=self.user,
            qubit_nm=5.0,
            nanodrop_260_280=1.8,
        )
        with self.assertRaises(ValidationError):
            qc.clean()

    def test_dna_sample_with_only_dna_fields_is_valid(self):
        qc = SampleQC(
            sample=self.dna_sample,
            batch=self._make_batch(),
            edited_by=self.user,
            qubit_nm=5.0,
            nanodrop_260_280=1.8,
            nanodrop_260_230=1.75,
        )
        qc.clean()  # should not raise

    def _make_batch(self):
        return SampleQCBatch.objects.create(
            date_batched="2026-01-01", project=self.project, created_by=self.user
        )


class SampleQCStatusCalculationTests(QCTestBase):
    def setUp(self):
        super().setUp()
        self.batch = SampleQCBatch.objects.create(
            date_batched="2026-01-01", project=self.project, created_by=self.user
        )

    # ---- DNA branch ----

    def test_dna_pending_when_values_missing(self):
        qc = SampleQC(sample=self.dna_sample, batch=self.batch, edited_by=self.user, qubit_nm=None)
        self.assertEqual(qc.calculate_qc_status(), SampleQC.PENDING)

    def test_dna_pass(self):
        # qubit_total = qubit_nm * 100 must exceed 100 -> qubit_nm > 1
        qc = SampleQC(
            sample=self.dna_sample,
            batch=self.batch,
            edited_by=self.user,
            qubit_nm=2.0,
            nanodrop_260_280=1.85,
            nanodrop_260_230=1.75,
        )
        self.assertEqual(qc.calculate_qc_status(), SampleQC.PASS)

    def test_dna_caution(self):
        qc = SampleQC(
            sample=self.dna_sample,
            batch=self.batch,
            edited_by=self.user,
            qubit_nm=2.0,
            nanodrop_260_280=1.5,   # fails the >1.79 pass gate
            nanodrop_260_230=1.5,   # but clears the >1.4 caution gate
        )
        self.assertEqual(qc.calculate_qc_status(), SampleQC.CAUTION)

    def test_dna_fail(self):
        qc = SampleQC(
            sample=self.dna_sample,
            batch=self.batch,
            edited_by=self.user,
            qubit_nm=0.1,
            nanodrop_260_280=1.0,
            nanodrop_260_230=1.0,
        )
        self.assertEqual(qc.calculate_qc_status(), SampleQC.FAIL)

    # ---- RNA branch ----

    def test_rna_pending_when_qubit_missing(self):
        qc = SampleQC(sample=self.rna_sample, batch=self.batch, edited_by=self.user, qubit_nm=None)
        self.assertEqual(qc.calculate_qc_status(), SampleQC.PENDING)

    def test_rna_pending_when_rin_and_dv200_missing(self):
        qc = SampleQC(sample=self.rna_sample, batch=self.batch, edited_by=self.user, qubit_nm=5.0)
        self.assertEqual(qc.calculate_qc_status(), SampleQC.PENDING)

    def test_rna_pass_via_rin(self):
        # qubit_total = qubit_nm * 40 must exceed 100 -> qubit_nm > 2.5
        qc = SampleQC(
            sample=self.rna_sample, batch=self.batch, edited_by=self.user, qubit_nm=5.0, rin=6.0
        )
        self.assertEqual(qc.calculate_qc_status(), SampleQC.PASS)

    def test_rna_pass_via_dv200(self):
        qc = SampleQC(
            sample=self.rna_sample, batch=self.batch, edited_by=self.user, qubit_nm=5.0, dv200=65.0
        )
        self.assertEqual(qc.calculate_qc_status(), SampleQC.PASS)

    def test_rna_caution(self):
        qc = SampleQC(
            sample=self.rna_sample,
            batch=self.batch,
            edited_by=self.user,
            qubit_nm=5.0,
            rin=3.0,
            dv200=45.0,
        )
        self.assertEqual(qc.calculate_qc_status(), SampleQC.CAUTION)

    def test_rna_fail(self):
        qc = SampleQC(
            sample=self.rna_sample,
            batch=self.batch,
            edited_by=self.user,
            qubit_nm=5.0,
            rin=1.0,
            dv200=10.0,
        )
        self.assertEqual(qc.calculate_qc_status(), SampleQC.FAIL)


class SampleQCSaveBehaviorTests(QCTestBase):
    def setUp(self):
        super().setUp()
        self.batch = SampleQCBatch.objects.create(
            date_batched="2026-01-01", project=self.project, created_by=self.user
        )

    def test_save_runs_full_clean_and_sets_status(self):
        qc = SampleQC(
            sample=self.dna_sample,
            batch=self.batch,
            edited_by=self.user,
            qubit_nm=2.0,
            nanodrop_260_280=1.85,
            nanodrop_260_230=1.75,
        )
        qc.save()
        self.assertEqual(qc.qc_status, SampleQC.PASS)

    def test_save_without_skip_validation_raises_on_missing_qubit(self):
        qc = SampleQC(sample=self.dna_sample, batch=self.batch, edited_by=self.user)
        with self.assertRaises(ValidationError):
            qc.save()

    def test_skip_validation_bypasses_full_clean(self):
        # Used by the batch board to create a blank PENDING stub.
        qc = SampleQC(sample=self.rna_sample, batch=self.batch, edited_by=self.user)
        qc.save(skip_validation=True)  # should not raise
        self.assertEqual(qc.qc_status, SampleQC.PENDING)

    def test_str(self):
        qc = SampleQC.objects.create(
            sample=self.rna_sample,
            batch=self.batch,
            edited_by=self.user,
            qubit_nm=5.0,
            rin=6.0,
        )
        self.assertEqual(str(qc), f"QC {self.rna_sample}(Pass)")