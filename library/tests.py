
from unittest.mock import MagicMock, patch

from django.db import IntegrityError, transaction
from django.test import TestCase

from .models import (
    QCStatus,
    WorkflowType,
    StepRow,
    WorkflowTypeStep,
    WorkflowStepRowOrder,
    IndexKit,
    LibraryIndex,
    LibraryPrepBatch,
    LibraryPrepBatchAuditLog,
    LibraryPrepSample,
    LibraryQCBatch,
    LibraryQC,
)


class WorkflowTypeModelTests(TestCase):
    def test_str_and_defaults(self):
        wf = WorkflowType.objects.create(workflowType="RNA PolyA")
        self.assertEqual(str(wf), "RNA PolyA")
        self.assertEqual(wf.sample_type, "RNA")
        self.assertTrue(wf.requires_pcr)
        self.assertTrue(wf.uses_controls)
        self.assertEqual(wf.min_nm_threshold, 2.0)

    def test_workflow_type_name_unique(self):
        WorkflowType.objects.create(workflowType="RNA PolyA")
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                WorkflowType.objects.create(workflowType="RNA PolyA")


class StepRowModelTests(TestCase):
    def test_str_and_ordering(self):
        StepRow.objects.create(stepRowName="AMPure XP Beads", sort_order=2)
        StepRow.objects.create(stepRowName="NF H2O", sort_order=1)
        rows = list(StepRow.objects.all())
        self.assertEqual([r.stepRowName for r in rows], ["NF H2O", "AMPure XP Beads"])


class WorkflowTypeStepModelTests(TestCase):
    def setUp(self):
        self.wf = WorkflowType.objects.create(workflowType="RNA PolyA")

    def test_str(self):
        step = WorkflowTypeStep.objects.create(workflowType=self.wf, stepName="Fragmentation", sort_order=1)
        self.assertEqual(str(step), "RNA PolyA – Fragmentation")

    def test_steps_ordered_by_sort_order(self):
        WorkflowTypeStep.objects.create(workflowType=self.wf, stepName="Cleanup", sort_order=2)
        WorkflowTypeStep.objects.create(workflowType=self.wf, stepName="Fragmentation", sort_order=1)
        steps = list(self.wf.steps.all())
        self.assertEqual([s.stepName for s in steps], ["Fragmentation", "Cleanup"])


class WorkflowStepRowOrderModelTests(TestCase):
    def setUp(self):
        self.wf = WorkflowType.objects.create(workflowType="RNA PolyA")
        self.step = WorkflowTypeStep.objects.create(workflowType=self.wf, stepName="Fragmentation", sort_order=1)
        self.beads = StepRow.objects.create(stepRowName="AMPure XP Beads")

    def test_str_and_volume(self):
        row = WorkflowStepRowOrder.objects.create(
            step=self.step, step_row=self.beads, sort_order=1, volumePerRxn=90.0
        )
        self.assertEqual(str(row), f"{self.step} – {self.beads}")
        self.assertEqual(row.volumePerRxn, 90.0)

    def test_same_row_cannot_be_added_twice_to_same_step(self):
        WorkflowStepRowOrder.objects.create(step=self.step, step_row=self.beads, volumePerRxn=90.0)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                WorkflowStepRowOrder.objects.create(step=self.step, step_row=self.beads, volumePerRxn=34.0)

    def test_same_row_can_be_reused_at_different_volume_in_another_step(self):
        other_step = WorkflowTypeStep.objects.create(workflowType=self.wf, stepName="Final Cleanup", sort_order=2)
        WorkflowStepRowOrder.objects.create(step=self.step, step_row=self.beads, volumePerRxn=90.0)
        # Should not raise same reagent, different step, different volume.
        WorkflowStepRowOrder.objects.create(step=other_step, step_row=self.beads, volumePerRxn=34.0)


class IndexKitModelTests(TestCase):
    def test_str_and_workflow_link(self):
        wf = WorkflowType.objects.create(workflowType="RNA PolyA")
        kit = IndexKit.objects.create(name="ILLMN-DNA-RNA-V2", workflowType=wf)
        self.assertEqual(str(kit), "ILLMN-DNA-RNA-V2")

    def test_name_unique(self):
        wf = WorkflowType.objects.create(workflowType="RNA PolyA")
        IndexKit.objects.create(name="ILLMN-DNA-RNA-V2", workflowType=wf)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                IndexKit.objects.create(name="ILLMN-DNA-RNA-V2", workflowType=wf)


class LibraryIndexModelTests(TestCase):
    def setUp(self):
        wf = WorkflowType.objects.create(workflowType="RNA PolyA")
        self.kit = IndexKit.objects.create(name="ILLMN-DNA-RNA-V2", workflowType=wf)

    def test_str_with_and_without_plate_set(self):
        idx = LibraryIndex.objects.create(
            indexKit=self.kit, well="A01", udi_number="UDP0001", i7Sequence="ACGTACGT"
        )
        self.assertEqual(str(idx), "ILLMN-DNA-RNA-V2 A01 – UDP0001")

        idx2 = LibraryIndex.objects.create(
            indexKit=self.kit, plateSet="Set A V2", well="A02", udi_number="UDP0002", i7Sequence="TTTTAAAA"
        )
        self.assertEqual(str(idx2), "ILLMN-DNA-RNA-V2 [Set A V2] A02 – UDP0002")

    def test_unique_well_per_kit_and_plate_set(self):
        LibraryIndex.objects.create(indexKit=self.kit, plateSet="Set A", well="A01", i7Sequence="ACGT")
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                LibraryIndex.objects.create(indexKit=self.kit, plateSet="Set A", well="A01", i7Sequence="TTTT")

    def test_same_well_allowed_in_different_plate_sets(self):
        LibraryIndex.objects.create(indexKit=self.kit, plateSet="Set A", well="A01", i7Sequence="ACGT")
        LibraryIndex.objects.create(indexKit=self.kit, plateSet="Set B", well="A01", i7Sequence="TTTT")

    def test_udi_number_can_repeat_across_kits(self):
        wf2 = WorkflowType.objects.create(workflowType="DNA PCR-Free")
        other_kit = IndexKit.objects.create(name="KAPA-UDI", workflowType=wf2)
        LibraryIndex.objects.create(indexKit=self.kit, well="A01", udi_number="UDP0001", i7Sequence="ACGT")
        LibraryIndex.objects.create(indexKit=other_kit, well="A01", udi_number="UDP0001", i7Sequence="TTTT")


class LibraryPrepBatchModelTests(TestCase):
    def setUp(self):
        self.wf = WorkflowType.objects.create(workflowType="RNA PolyA")

    def test_str_uses_batch_name_when_set(self):
        batch = LibraryPrepBatch.objects.create(
            workflowType=self.wf, datePrepped="2026-01-01", batch_name="ACME2024-Library-0001"
        )
        self.assertEqual(str(batch), "ACME2024-Library-0001")

    def test_str_falls_back_to_batch_number_when_no_name_or_plate(self):
        batch = LibraryPrepBatch.objects.create(workflowType=self.wf, datePrepped="2026-01-01")
        self.assertEqual(str(batch), f"Batch #{batch.pk}")

    def test_sample_and_control_count_properties(self):
        batch = LibraryPrepBatch.objects.create(workflowType=self.wf, datePrepped="2026-01-01")

        # `samples` is a reverse-FK related manager (locations.PlateWell is
        # opaque to this app's tests), so it's swapped for a mock to verify
        # sample_count/control_count/total_reaction_count filter correctly
        # without depending on that model's real fields. Direct instance
        # assignment (`batch.samples = mock_manager`) is blocked by Django's
        # reverse-FK descriptor, so the class attribute is patched instead —
        # a plain MagicMock isn't a descriptor, so `self.samples` resolves
        # straight to it for the life of the `with` block.
        mock_manager = MagicMock()
        mock_manager.filter.return_value.count.side_effect = [3, 1]  # sample_count, then control_count
        with patch.object(LibraryPrepBatch, "samples", mock_manager):
            self.assertEqual(batch.sample_count, 3)
            self.assertEqual(batch.control_count, 1)
        mock_manager.filter.assert_any_call(plateWell__well_type="sample")
        mock_manager.filter.assert_any_call(plateWell__well_type="control")

    def test_total_reaction_count_sums_samples_and_controls(self):
        batch = LibraryPrepBatch.objects.create(workflowType=self.wf, datePrepped="2026-01-01")
        mock_manager = MagicMock()
        mock_manager.filter.return_value.count.side_effect = [8, 2]
        with patch.object(LibraryPrepBatch, "samples", mock_manager):
            self.assertEqual(batch.total_reaction_count, 10)


class LibraryPrepBatchAuditLogModelTests(TestCase):
    def test_str_with_unknown_user(self):
        wf = WorkflowType.objects.create(workflowType="RNA PolyA")
        batch = LibraryPrepBatch.objects.create(workflowType=wf, datePrepped="2026-01-01")
        log = LibraryPrepBatchAuditLog.objects.create(
            batch=batch, action=LibraryPrepBatchAuditLog.ACTION_CREATED, detail="Batch created"
        )
        self.assertIn("Batch Created", str(log))
        self.assertIn("unknown", str(log))


class LibraryPrepSampleModelTests(TestCase):
    def setUp(self):
        self.wf = WorkflowType.objects.create(workflowType="RNA PolyA")
        self.batch = LibraryPrepBatch.objects.create(workflowType=self.wf, datePrepped="2026-01-01")

    def test_str_for_control_well(self):
        sample = LibraryPrepSample.objects.create(
            libPrepBatch=self.batch, sampleQC=None, planned_well_position="H12"
        )
        self.assertEqual(str(sample), f"Control @ H12 (Batch {self.batch.pk})")

    def test_str_falls_back_to_question_mark_when_no_well(self):
        sample = LibraryPrepSample.objects.create(libPrepBatch=self.batch, sampleQC=None)
        self.assertEqual(str(sample), f"Control @ ? (Batch {self.batch.pk})")

    def test_default_prep_action_is_prep(self):
        sample = LibraryPrepSample.objects.create(libPrepBatch=self.batch)
        self.assertEqual(sample.prepAction, "prep")


class LibraryQCBatchModelTests(TestCase):
    def setUp(self):
        wf = WorkflowType.objects.create(workflowType="RNA PolyA")
        self.batch = LibraryPrepBatch.objects.create(workflowType=wf, datePrepped="2026-01-01")

    def test_str_uses_batch_name_when_set(self):
        qc_batch = LibraryQCBatch.objects.create(libPrepBatch=self.batch, batchName="QC-0001")
        self.assertEqual(str(qc_batch), "QC-0001")

    def test_str_falls_back_to_pk(self):
        qc_batch = LibraryQCBatch.objects.create(libPrepBatch=self.batch)
        self.assertEqual(str(qc_batch), f"LibQCBatch #{qc_batch.pk}")

    def test_one_qc_batch_per_prep_batch(self):
        LibraryQCBatch.objects.create(libPrepBatch=self.batch)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                LibraryQCBatch.objects.create(libPrepBatch=self.batch)


class LibraryQCCalculationTests(TestCase):
    def setUp(self):
        self.wf = WorkflowType.objects.create(
            workflowType="RNA PolyA",
            min_nm_threshold=2.0,
            fragment_min_bp=200,
            fragment_max_bp=400,
            dimer_threshold_pct=5.0,
        )
        self.prep_batch = LibraryPrepBatch.objects.create(workflowType=self.wf, datePrepped="2026-01-01")
        self.prep_sample = LibraryPrepSample.objects.create(libPrepBatch=self.prep_batch)
        self.qc_batch = LibraryQCBatch.objects.create(libPrepBatch=self.prep_batch)

    def test_calculate_nm_formula(self):
        qc = LibraryQC(
            libQCBatch=self.qc_batch, libPrepSample=self.prep_sample,
            qubit_ng_ul=10.0, fragmentSizesAvgBP=300.0,
        )
        expected = round((10.0 * 1_000_000) / (300.0 * 650), 4)
        self.assertEqual(qc.calculate_nm(), expected)

    def test_calculate_nm_returns_none_without_inputs(self):
        qc = LibraryQC(libQCBatch=self.qc_batch, libPrepSample=self.prep_sample)
        self.assertIsNone(qc.calculate_nm())

    def test_status_pending_without_nm_inputs(self):
        qc = LibraryQC(libQCBatch=self.qc_batch, libPrepSample=self.prep_sample)
        self.assertEqual(qc.calculate_qc_status(self.wf), QCStatus.PENDING)

    def test_status_fail_below_min_nm_threshold(self):
        # Deliberately low qubit -> nM well under the 2.0 threshold.
        qc = LibraryQC(
            libQCBatch=self.qc_batch, libPrepSample=self.prep_sample,
            qubit_ng_ul=0.05, fragmentSizesAvgBP=300.0,
        )
        self.assertEqual(qc.calculate_qc_status(self.wf), QCStatus.FAIL)

    def test_status_fail_fragment_size_out_of_range(self):
        qc = LibraryQC(
            libQCBatch=self.qc_batch, libPrepSample=self.prep_sample,
            qubit_ng_ul=10.0, fragmentSizesAvgBP=800.0,  # outside 200-400 bp window
        )
        self.assertEqual(qc.calculate_qc_status(self.wf), QCStatus.FAIL)

    def test_status_fail_dimer_peak_over_threshold(self):
        qc = LibraryQC(
            libQCBatch=self.qc_batch, libPrepSample=self.prep_sample,
            qubit_ng_ul=10.0, fragmentSizesAvgBP=300.0, dimerPeak_pct=8.0,  # over 5.0 threshold
        )
        self.assertEqual(qc.calculate_qc_status(self.wf), QCStatus.FAIL)

    def test_status_pass(self):
        qc = LibraryQC(
            libQCBatch=self.qc_batch, libPrepSample=self.prep_sample,
            qubit_ng_ul=10.0, fragmentSizesAvgBP=300.0, dimerPeak_pct=1.0,
        )
        self.assertEqual(qc.calculate_qc_status(self.wf), QCStatus.PASS)

    def test_status_uses_default_min_nm_without_workflow_type(self):
        qc = LibraryQC(
            libQCBatch=self.qc_batch, libPrepSample=self.prep_sample,
            qubit_ng_ul=10.0, fragmentSizesAvgBP=300.0,
        )
        # No workflow_type passed -> falls back to the hardcoded 2.0 gate only.
        self.assertEqual(qc.calculate_qc_status(), QCStatus.PASS)

    def test_save_auto_computes_nm_when_not_set(self):
        qc = LibraryQC.objects.create(
            libQCBatch=self.qc_batch, libPrepSample=self.prep_sample,
            qubit_ng_ul=10.0, fragmentSizesAvgBP=300.0,
        )
        expected = round((10.0 * 1_000_000) / (300.0 * 650), 4)
        self.assertEqual(qc.nmCalculated, expected)

    def test_save_does_not_overwrite_explicit_nm(self):
        qc = LibraryQC.objects.create(
            libQCBatch=self.qc_batch, libPrepSample=self.prep_sample,
            qubit_ng_ul=10.0, fragmentSizesAvgBP=300.0, nmCalculated=99.9,
        )
        self.assertEqual(qc.nmCalculated, 99.9)

    def test_one_qc_result_per_prep_sample(self):
        LibraryQC.objects.create(libQCBatch=self.qc_batch, libPrepSample=self.prep_sample)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                LibraryQC.objects.create(libQCBatch=self.qc_batch, libPrepSample=self.prep_sample)

    def test_str(self):
        qc = LibraryQC.objects.create(
            libQCBatch=self.qc_batch, libPrepSample=self.prep_sample, QCstatus=QCStatus.PASS
        )
        self.assertEqual(str(qc), f"LibQC #{qc.pk} – pass")