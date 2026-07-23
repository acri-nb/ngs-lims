from django.core.management.base import BaseCommand
from qc.models import QCGatePreset


PRESETS = [
    {
        'name': 'TotalRNA', 'sample_type': 'RNA', 'order': 1,
        'description': 'RIN > 5, or RIN > 2 with dv200 > 55.',
        'gate_rna_min_ng': 100, 'gate_rna_elution_ul': 40,
        'gate_rna_rin_pass': 5, 'gate_rna_rin_or_min': 2,
        'gate_rna_dv200_or_min': 55, 'gate_rna_dv200_pass': 62,
        'gate_rna_caution_rin_min': 1.99,
        'gate_rna_caution_dv200_min': 40, 'gate_rna_caution_dv200_max': 54,
    },
    {
        'name': 'SmallRNA', 'sample_type': 'RNA', 'order': 2,
        'description': 'Same quality gates as TotalRNA (RIN > 5, or RIN > 2 with dv200 > 55).',
        'gate_rna_min_ng': 100, 'gate_rna_elution_ul': 40,
        'gate_rna_rin_pass': 2, 'gate_rna_rin_or_min': 2,
        'gate_rna_dv200_or_min': 35, 'gate_rna_dv200_pass': 55,
        'gate_rna_caution_rin_min': 1.99,
        'gate_rna_caution_dv200_min': 40, 'gate_rna_caution_dv200_max': 54,
    },
    {
        'name': 'KAPA HyperPlus DNA', 'sample_type': 'DNA', 'order': 1,
        'description': '260/280 > 1.79, 260/230 > 1.7, no upper bound on 260/280.',
        'gate_dna_min_ng': 100, 'gate_dna_elution_ul': 100,
        'gate_dna_260_280_min': 1.79, 'gate_dna_260_280_max': None,
        'gate_dna_260_230_pass_min': 1.7, 'gate_dna_260_230_caution_min': 1.4,
    },
    {
        'name': 'DNA PCR-Free WGS', 'sample_type': 'DNA', 'order': 2,
        'description': '260/280 between 1.79–2.0, 260/230 > 1.99 (stricter than KAPA).',
        'gate_dna_min_ng': 100, 'gate_dna_elution_ul': 100,
        'gate_dna_260_280_min': 1.79, 'gate_dna_260_280_max': 2.0,
        'gate_dna_260_230_pass_min': 1.99, 'gate_dna_260_230_caution_min': 1.4,
    },
]


class Command(BaseCommand):
    help = 'Seeds/updates the standard NGS workflow QC gate presets.'

    def handle(self, *args, **options):
        for data in PRESETS:
            name = data.pop('name')
            preset, created = QCGatePreset.objects.update_or_create(
                name=name, defaults=data,
            )
            self.stdout.write(self.style.SUCCESS(
                f"{'Created' if created else 'Updated'} preset: {preset}"
            ))