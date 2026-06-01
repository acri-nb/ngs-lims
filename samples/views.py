# Django imports
from django.shortcuts import render, get_object_or_404
from django.views.generic import ListView
from django.db.models import Q, Count, Prefetch
from django.utils import timezone
from datetime import timedelta

# Local app models
from .models import Client, Project, Sample, Case
from qc.models import SampleQC

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
    paginate_by = 50

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


# pipeline stage for a sample 

def _pipeline_stage(sample):
    """
    Returns a (stage_label, icon_class) tuple based on where the sample
    currently is in the pipeline. Expand this as more phases are built.
    """
    latest_qc = sample.qc_results.order_by('-created_at').first()

    if latest_qc:
        if latest_qc.qc_status == 'Pass':
            return ('QC Pass',    'fa-check-circle')
        elif latest_qc.qc_status == 'Fail':
            return ('QC Fail',    'fa-times-circle')
        elif latest_qc.qc_status == 'Caution':
            return ('QC Caution', 'fa-exclamation-circle')
        else:
            return ('Awaiting QC','fa-hourglass-half')

    return ('Received', 'fa-inbox')


# CLIENT

def client_list(request):
    clients = Client.objects.all().order_by('client_name')

    client_data = []
    for client in clients:
        project_count = client.projects.count()
        sample_count  = Sample.objects.filter(project__client=client).count()
        case_count    = client.cases.count()
        client_data.append({
            'client':        client,
            'project_count': project_count,
            'sample_count':  sample_count,
            'case_count':    case_count,
        })

    return render(request, 'samples/client_list.html', {
        'clients': client_data,
    })


def client_detail(request, client_pk):

    client = get_object_or_404(
        Client,
        pk=client_pk
    )

    # Summary stats
    total_projects = client.projects.count()

    total_samples = Sample.objects.filter(
        project__client=client
    ).count()

    total_cases = Case.objects.filter(
        client=client
    ).count()

    project_data = []

    for project in client.projects.all().order_by('project_name'):

        samples = project.samples.all()

        sample_count = samples.count()

        dna_count = samples.filter(
            sample_type=Sample.DNA
        ).count()

        rna_count = samples.filter(
            sample_type=Sample.RNA
        ).count()

        # QC counts
        qc_pass = SampleQC.objects.filter(
            sample__project=project,
            qc_status=SampleQC.PASS
        ).count()

        qc_fail = SampleQC.objects.filter(
            sample__project=project,
            qc_status=SampleQC.FAIL
        ).count()

        qc_caution = SampleQC.objects.filter(
            sample__project=project,
            qc_status=SampleQC.CAUTION
        ).count()

        qc_pending = SampleQC.objects.filter(
            sample__project=project,
            qc_status=SampleQC.PENDING
        ).count()

        qc_total = qc_pass + qc_fail + qc_caution + qc_pending

        if qc_total:
            qc_pass_pct = (qc_pass / qc_total) * 100
            qc_fail_pct = (qc_fail / qc_total) * 100
            qc_caution_pct = (qc_caution / qc_total) * 100
            qc_pending_pct = (qc_pending / qc_total) * 100
        else:
            qc_pass_pct = 0
            qc_fail_pct = 0
            qc_caution_pct = 0
            qc_pending_pct = 0

        project_data.append({
            'project': project,

            'sample_count': sample_count,

            'dna_count': dna_count,
            'rna_count': rna_count,

            'qc_pass': qc_pass,
            'qc_fail': qc_fail,
            'qc_caution': qc_caution,
            'qc_pending': qc_pending,

            'qc_pass_pct': qc_pass_pct,
            'qc_fail_pct': qc_fail_pct,
            'qc_caution_pct': qc_caution_pct,
            'qc_pending_pct': qc_pending_pct,
        })

    context = {
        'client': client,

        'total_projects': total_projects,
        'total_samples': total_samples,
        'total_cases': total_cases,

        'projects': project_data,
    }

    return render(
        request,
        'samples/client_detail.html',
        context
    )





# Project 
def project_list(request):
    query = request.GET.get("q", "").strip()

    projects = (
        Project.objects
        .select_related("client")
        .annotate(sample_count=Count("samples"))
        .order_by("-date_created")
    )

    if query:
        projects = projects.filter(
            project_name__icontains=query
        )

    return render(
        request,
        "samples/project_list.html",
        {
            "projects": projects,
        }
    )

def project_detail(request, project_id):
    project = get_object_or_404(
        Project.objects.select_related("client"),
        pk=project_id
    )

    project_samples = (
        Sample.objects
        .filter(project=project)
        .select_related(
            "specimen",
            "specimen__case",
            "specimen__specimen_type",
            "location"
        )
        .prefetch_related(
            Prefetch(
                "qc_results",
                queryset=SampleQC.objects.order_by("-created_at")
            )
        )
    )

    sample_rows = []

    qc_pass_count = 0
    qc_fail_count = 0
    qc_caution_count = 0
    qc_pending_count = 0

    for sample in project_samples:

        latest_qc = sample.qc_results.all()[0] if sample.qc_results.all() else None

        qc_status = None

        if latest_qc:
            qc_status = latest_qc.qc_status

            if qc_status == SampleQC.PASS:
                qc_pass_count += 1

                pipeline_stage = "QC Pass"
                pipeline_icon = "fa-check-circle"

            elif qc_status == SampleQC.FAIL:
                qc_fail_count += 1

                pipeline_stage = "QC Fail"
                pipeline_icon = "fa-times-circle"

            elif qc_status == SampleQC.CAUTION:
                qc_caution_count += 1

                pipeline_stage = "QC Caution"
                pipeline_icon = "fa-exclamation-triangle"

            else:
                qc_pending_count += 1

                pipeline_stage = "Awaiting QC"
                pipeline_icon = "fa-clock"

        else:
            qc_pending_count += 1

            pipeline_stage = "Awaiting QC"
            pipeline_icon = "fa-clock"

        sample_rows.append({
            "sample": sample,
            "qc_status": qc_status,
            "pipeline_stage": pipeline_stage,
            "pipeline_icon": pipeline_icon,
        })

    context = {
        "project": project,

        "samples": sample_rows,

        "total_samples": project_samples.count(),

        "qc_pass_count": qc_pass_count,
        "qc_fail_count": qc_fail_count,
        "qc_caution_count": qc_caution_count,
        "qc_pending_count": qc_pending_count,
    }

    return render(
        request,
        "samples/project_detail.html",
        context
    )