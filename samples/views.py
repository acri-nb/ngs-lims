from django.shortcuts import render
from django.views.generic import ListView
from django.db.models import Q
from django.utils import timezone
from datetime import timedelta

from .models import Sample, Project

def home(request):
    """
    Dashboard view — passes counts and recent data to the template.
    Import the other models at the top of this function so Django doesn't
    choke if those apps aren't migrated yet.
    """
    
    from qc.models import SampleQCBatch, SampleQC
    from inventory.models import InventoryReceipt

    # Stat card counts
    total_samples  = Sample.objects.count()
    total_projects = Project.objects.count()
    total_batches  = SampleQCBatch.objects.count()

    # Inventory expiring in the next 30 days
    today     = timezone.now().date()
    in_30days = today + timedelta(days=30)
    expiring_soon = InventoryReceipt.objects.filter(
        expiration_date__isnull=False,
        expiration_date__gte=today,
        expiration_date__lte=in_30days,
    ).count()

    # Recent samples 
    recent_samples = (
        Sample.objects
        .select_related('project', 'specimen__case', 'specimen__specimen_type', 'location')
        .order_by('-date_received', '-sample_id')[:20]
    )

    # QC status breakdown
    from django.db.models import Count
    qc_status_stats = (
        SampleQC.objects
        .values('qc_status')
        .annotate(count=Count('id'))
        .order_by('qc_status')
    )

    # Recent QC batches (last 5)
    recent_batches = SampleQCBatch.objects.order_by('-date_batched')[:5]

    context = {
        'total_samples':   total_samples,
        'total_projects':  total_projects,
        'total_batches':   total_batches,
        'expiring_soon':   expiring_soon,
        'recent_samples':  recent_samples,
        'qc_status_stats': qc_status_stats,
        'recent_batches':  recent_batches,
    }
    return render(request, 'home.html', context)


class SampleListView(ListView):
    model = Sample
    template_name = 'samples/sample_list.html'
    context_object_name = 'samples'
    paginate_by = 100

    def get_queryset(self):
        qs = (
            Sample.objects
            .select_related(
                'project',
                'specimen__case',
                'specimen__specimen_type',
                'location',
            )
            .prefetch_related('qc_results')
            .order_by('-date_received', '-sample_id')
        )

        # Search by sample name / case name / project name
        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(
                Q(sample_name__icontains=q) |
                Q(project__project_name__icontains=q) |
                Q(specimen__case__case_name__icontains=q)
            )

        # Filter by sample type (DNA / RNA)
        sample_type = self.request.GET.get('type', '').strip()
        if sample_type in ('DNA', 'RNA'):
            qs = qs.filter(sample_type=sample_type)

        # Filter by project
        project_id = self.request.GET.get('project', '').strip()
        if project_id.isdigit():
            qs = qs.filter(project_id=int(project_id))

        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        # Pass projects for the filter dropdown
        ctx['projects'] = Project.objects.order_by('project_name')
        return ctx