# Django imports
from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import ListView
from django.db.models import Q, Count, Prefetch
from django.utils import timezone
from datetime import timedelta

import csv
import io

from django.contrib import messages
from django.contrib.auth.decorators import login_required

from .models import Client, Sample, Project, Specimen, Case, SpecimenType, Case
from locations.models import Location
from qc.models import SampleQC

from django.http import JsonResponse,HttpResponse
from .forms import SampleAddForm

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
        )

        #  Search 
        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(
                Q(sample_name__icontains=q)               |
                Q(specimen__case__case_name__icontains=q) |
                Q(project__project_name__icontains=q)     |
                Q(notes__icontains=q)
            )

        #  Type filter 
        sample_type = self.request.GET.get('type', '').strip()
        if sample_type in ('DNA', 'RNA'):
            qs = qs.filter(sample_type=sample_type)

        # Project filter 
        project_id = self.request.GET.get('project', '').strip()
        if project_id.isdigit():
            qs = qs.filter(project_id=int(project_id))

        # QC filter 
        qc = self.request.GET.get('qc', '').strip()
        if qc == 'none':
            qs = qs.filter(qc_results__isnull=True)
        elif qc in ('Pass', 'Fail', 'Caution', 'Pending', 'No QC'):
            qs = qs.filter(qc_results__qc_status=qc)

        # Sort 
        sort = self.request.GET.get('sort', '').strip()
        direction = self.request.GET.get('dir', 'desc').strip()
        prefix = '-' if direction == 'desc' else ''

        sort_map = {
            'name':    f'{prefix}sample_id',      # sample_id = correct numeric sort
            'date':    f'{prefix}date_received',
            'project': f'{prefix}project__project_name',
            'case':    f'{prefix}specimen__case__case_name',
        }

        # Default: sample_id descending (newest first)
        order = sort_map.get(sort, '-sample_id')
        return qs.order_by(order)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['projects'] = Project.objects.order_by('project_name')

        # Clean query string for pagination: remove page, keep everything else
        params = self.request.GET.copy()
        params.pop('page', None)
        ctx['filter_qs'] = params.urlencode()

        ctx['next_name_dir'] = 'asc'
        ctx['next_case_dir'] = 'asc'
        ctx['next_project_dir'] = 'asc'
        ctx['next_date_dir'] = 'asc'

        current_sort = self.request.GET.get('sort')
        current_dir = self.request.GET.get('dir', 'asc')

        if current_sort == 'name':
            ctx['next_name_dir'] = 'desc' if current_dir == 'asc' else 'asc'

        if current_sort == 'case':
            ctx['next_case_dir'] = 'desc' if current_dir == 'asc' else 'asc'

        if current_sort == 'project':
            ctx['next_project_dir'] = 'desc' if current_dir == 'asc' else 'asc'

        if current_sort == 'date':
            ctx['next_date_dir'] = 'desc' if current_dir == 'asc' else 'asc'
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

@login_required
def import_samples(request):
    if request.method == "POST":
        csv_file = request.FILES.get("file")

        if not csv_file:
            messages.error(request, "No file provided.")
            return redirect("sample-import")

        try:
            decoded_file = csv_file.read().decode("utf-8")
            io_string = io.StringIO(decoded_file)
            reader = csv.DictReader(io_string)

            created = 0

            for row in reader:
                # required fields 
                project = Project.objects.get(project_id=row["project_id"])
                specimen = Specimen.objects.get(specimen_id=row["specimen_id"])

                location = None
                if row.get("location_id"):
                    location = Location.objects.get(location_id=row["location_id"])

                sample = Sample.objects.create(
                    project=project,
                    specimen=specimen,
                    location=location,
                    sample_type=row.get("sample_type", "DNA"),
                    receiving_condition=row.get("receiving_condition", ""),
                    volume_received=row.get("volume_received") or None,
                    concentration=row.get("concentration") or None,
                    notes=row.get("notes", "")
                )

                created += 1

            messages.success(request, f"Imported {created} samples.")
            return redirect("sample-list")

        except Exception as e:
            messages.error(request, f"Import failed: {e}")

    return render(request, "samples/import_samples.html")


# SAMPLE DETAIL 

@login_required
def sample_detail(request, sample_id):
    sample = get_object_or_404(
        Sample.objects.select_related(
            'specimen__case__client',
            'specimen__specimen_type',
            'project__client',
            'location',
        ).prefetch_related('qc_results__batch'),
        pk=sample_id
    )

    qc_results = sample.qc_results.order_by('-created_at').select_related('batch')

    # Other samples in the same case (excluding this one)
    related_samples = (
        Sample.objects
        .filter(specimen__case=sample.specimen.case)
        .exclude(pk=sample_id)
        .prefetch_related('qc_results')
        .order_by('sample_name')[:10]
    )

    return render(request, 'samples/sample_detail.html', {
        'sample':          sample,
        'qc_results':      qc_results,
        'related_samples': related_samples,
    })


# BULK ACTION 

@login_required
def sample_bulk_action(request):
    if request.method != 'POST':
        return redirect('sample-list')

    action   = request.POST.get('action')
    ids      = request.POST.getlist('selected_ids')
    samples  = Sample.objects.filter(pk__in=ids)

    if action == 'change_location':
        from locations.models import Location
        locations = Location.objects.all()
        return render(request, 'samples/bulk_change_location.html', {
            'samples':   samples,
            'locations': locations,
        })

    elif action == 'change_condition':
        conditions = Sample.RECEIVING_CONDITION_CHOICES
        return render(request, 'samples/bulk_change_condition.html', {
            'samples':    samples,
            'conditions': conditions,
        })

    elif action == 'apply_location':
        location_id = request.POST.get('location')
        from locations.models import Location
        location = get_object_or_404(Location, pk=location_id)
        updated  = samples.update(location=location)
        messages.success(request, f"Location updated for {updated} sample(s).")

    elif action == 'apply_condition':
        condition = request.POST.get('receiving_condition')
        updated   = samples.update(receiving_condition=condition)
        messages.success(request, f"Condition updated for {updated} sample(s).")

    return redirect('sample-list')


# EXPORT CSV 

@login_required
def sample_export_csv(request):
    ids_param = request.GET.get('ids', '')
    if ids_param:
        ids     = [i for i in ids_param.split(',') if i.strip().isdigit()]
        samples = Sample.objects.filter(pk__in=ids).select_related(
            'specimen__case', 'specimen__specimen_type', 'project', 'location'
        ).prefetch_related('qc_results')
    else:
        # Export all (respecting current filters if passed)
        samples = Sample.objects.all().select_related(
            'specimen__case', 'specimen__specimen_type', 'project', 'location'
        ).prefetch_related('qc_results')

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="samples_export.csv"'

    writer = csv.writer(response)
    writer.writerow([
        'sample_name', 'sample_type', 'case_name', 'specimen_type', 'concentration', 'volume',
        'project', 'date_received', 'receiving_condition',
        'location', 'qc_status', 'notes'
    ])

    for s in samples:
        latest_qc = s.qc_results.first()
        writer.writerow([
            s.sample_name,
            s.specimen.case.case_name,
            s.specimen.specimen_type.specimen_type,
            s.sample_type,
            s.concentration if s.concentration is not None else '',
            s.volume_received if s.volume_received is not None else '',
            s.project.project_name,
            s.date_received.isoformat(),
            s.receiving_condition or '',
            s.location.locationName if s.location else '',
            latest_qc.qc_status if latest_qc else 'No QC',
            s.notes or '',
        ])

    return response


#IMPORT CSV 

CSV_COLUMNS = [
    {
        'name': 'CaseID',
        'required': True,
        'description': 'Case identifier. Created automatically if missing.'
    },
    {
        'name': 'SpecimenType',
        'required': True,
        'description': 'e.g. FFPE, smallEVs, Blood'
    },
    {
        'name': 'NucleidType',
        'required': True,
        'description': 'DNA or RNA'
    },
    {
        'name': 'Concentration(ng/ul)',
        'required': False,
        'description': 'Sample concentration'
    },
    {
        'name': 'Volume(uL)',
        'required': False,
        'description': 'Sample volume'
    },
]

@login_required
def sample_import(request):
    preview_rows = []
    preview_errors = []

    projects = Project.objects.select_related('client').order_by('project_name')

    if request.method == 'POST':

        csv_file = request.FILES.get('csv_file')
        project_id = request.POST.get('project')
        action = request.POST.get('action', 'preview')

        if not csv_file:
            messages.error(request, 'Please select a CSV file.')

        elif not project_id:
            messages.error(request, 'Please select a project.')

        elif not csv_file.name.endswith('.csv'):
            messages.error(request, 'File must be a CSV file.')

        else:

            try:
                project = Project.objects.select_related('client').get(
                    project_id=project_id
                )

                decoded = csv_file.read().decode('utf-8')
                reader = csv.DictReader(io.StringIO(decoded))
                rows = list(reader)

                required_columns = [
                    'CaseID',
                    'SpecimenType',
                    'NucleidType',
                    'Concentration(ng/ul)',
                    'Volume(uL)',
                ]

                # Validate headers
                if rows:
                    missing = [
                        col for col in required_columns
                        if col not in rows[0]
                    ]

                    if missing:
                        messages.error(
                            request,
                            f"Missing required column(s): {', '.join(missing)}"
                        )

                for row in rows:

                    error = None

                    case_name = row.get('CaseID', '').strip()
                    specimen_type = row.get('SpecimenType', '').strip()
                    nucleid_type = row.get('NucleidType', '').strip().upper()
                    concentration = row.get('Concentration(ng/ul)', '').strip()
                    volume = row.get('Volume(uL)', '').strip()

                    if not case_name:
                        error = "Missing CaseID"

                    elif not specimen_type:
                        error = "Missing SpecimenType"

                    elif nucleid_type not in ('DNA', 'RNA'):
                        error = "NucleidType must be DNA or RNA"

                    preview_rows.append({
                        'case_name': case_name,
                        'specimen_type': specimen_type,
                        'sample_type': nucleid_type,
                        'concentration': concentration,
                        'volume': volume,
                        'error': error,
                        'raw': row,
                    })

                    if error:
                        preview_errors.append(error)

               
                # IMPORT
                if action == 'import' and not preview_errors:

                    created = 0

                    for item in preview_rows:

                        row = item['raw']

                        case_name = row['CaseID'].strip()
                        specimen_type_name = row['SpecimenType'].strip()

                        sample_type = row['NucleidType'].strip().upper()

                        concentration = (
                            float(row['Concentration(ng/ul)'])
                            if row.get('Concentration(ng/ul)')
                            else None
                        )

                        volume = (
                            float(row['Volume(uL)'])
                            if row.get('Volume(uL)')
                            else None
                        )

                        # CASE

                        case, _ = Case.objects.get_or_create(
                            case_name=case_name,
                            defaults={
                                'client': project.client
                            }
                        )

                        # SPECIMEN TYPE

                        spec_type, _ = SpecimenType.objects.get_or_create(
                            specimen_type=specimen_type_name
                        )

                        # SPECIMEN

                        specimen, _ = Specimen.objects.get_or_create(
                            case=case,
                            specimen_type=spec_type
                        )

                        # SAMPLE
                        Sample.objects.create(
                            specimen=specimen,
                            project=project,
                            sample_type=sample_type,
                            concentration=concentration,
                            volume_received=volume,
                        )

                        created += 1

                    messages.success(
                        request,
                        f"Successfully imported {created} sample(s)."
                    )

                    return redirect('sample-list')

                elif action == 'import' and preview_errors:

                    messages.error(
                        request,
                        f"Fix {len(preview_errors)} error(s) before importing."
                    )

            except Exception as e:
                messages.error(request, f"Import failed: {e}")

    return render(
        request,
        'samples/sample_import.html',
        {
            'projects': projects,
            'preview_rows': preview_rows,
            'preview_errors': preview_errors,
        }
    )

@login_required
def sample_import_template(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = (
        'attachment; filename="sample_import_template.csv"'
    )

    writer = csv.writer(response)

    writer.writerow([
        'CaseID',
        'SpecimenType',
        'NucleidType',
        'Concentration(ng/ul)',
        'Volume(uL)',
    ])

    examples = [
        ['Y1V9RH', 'smallEVs',   'RNA', '250.7564', '788'],
        ['WYL6O2', 'LargeEVs',   'RNA', '387.5995', '425'],
        ['08Q2T8', 'FrzT',       'DNA', '243.9815', '612'],
        ['MCF10A', 'FFPE',       'RNA', '175.2200', '500'],
        ['MCF10A', 'Cells',      'DNA', '86.4200',  '100'],
        ['PDX-001','EV',         'DNA', '42.5000',  '50'],
        ['CTRL01', 'Bld',        'RNA', '12.9000',  '250'],
    ]

    for row in examples:
        writer.writerow(row)

    return response

@login_required
def sample_add(request):
    form = SampleAddForm(request.POST or None)

    if request.method == 'POST':
        # Get case by name — create if doesn't exist
        project_id = request.POST.get('project')
        case_name  = request.POST.get('case_name', '').strip()

        try:
            project = Project.objects.get(pk=project_id)
        except Project.DoesNotExist:
            messages.error(request, 'Invalid project.')
            return render(request, 'samples/sample_add.html', {'form': form})

        if not case_name:
            messages.error(request, 'Case name is required.')
            return render(request, 'samples/sample_add.html', {'form': form})

        # get_or_create case under the project's client
        case, case_created = Case.objects.get_or_create(
            case_name=case_name,
            client=project.client,
        )

        specimen_type_id = request.POST.get('specimen_type')
        sample_type      = request.POST.get('sample_type')

        if not specimen_type_id or not sample_type:
            messages.error(request, 'Specimen type and nucleic type are required.')
            return render(request, 'samples/sample_add.html', {'form': form})

        try:
            specimen_type = SpecimenType.objects.get(pk=specimen_type_id)
            specimen, _   = Specimen.objects.get_or_create(
                case=case, specimen_type=specimen_type
            )

            location_id = request.POST.get('location') or None
            location    = Location.objects.get(pk=location_id) if location_id else None

            sample = Sample(
                specimen            = specimen,
                project             = project,
                sample_type         = sample_type,
                receiving_condition = request.POST.get('receiving_condition', ''),
                location            = location,
                volume_received     = request.POST.get('volume_received') or None,
                concentration       = request.POST.get('concentration') or None,
                notes               = request.POST.get('notes', ''),
            )
            sample.save()

            if case_created:
                messages.info(request, f'New case "{case_name}" was created.')
            messages.success(request, f'Sample {sample.sample_name} created.')
            return redirect('sample-detail', sample_id=sample.sample_id)

        except Exception as e:
            messages.error(request, f'Could not create sample: {e}')

    return render(request, 'samples/sample_add.html', {'form': form})


# AJAX Load cases for a projct
@login_required
def ajax_cases_for_project(request):
    '''
    Called by JS when the user picks a project.
    Returns JSON list of cases belonging to that project's client.
    '''
    project_id = request.GET.get('project_id')
    cases = []
    client_name = ''
    try:
        project    = Project.objects.select_related('client').get(pk=project_id)
        client_name = project.client.client_name
        cases = list(
            Case.objects.filter(client=project.client)
            .order_by('case_name')
            .values('case_id', 'case_name')
        )
    except (Project.DoesNotExist, ValueError, TypeError):
        pass
    return JsonResponse({'cases': cases, 'client_name': client_name})

# Case 

from django.db.models import Count


@login_required
def case_detail(request, case_id):

    case = get_object_or_404(
        Case.objects.select_related('client'),
        pk=case_id
    )

    specimens = (
        Specimen.objects
        .filter(case=case)
        .select_related('specimen_type')
    )

    samples = (
        Sample.objects
        .filter(specimen__case=case)
        .select_related(
            'project',
            'specimen__specimen_type',
            'location'
        )
        .prefetch_related('qc_results')
        .order_by('-sample_id')
    )

    return render(
        request,
        'samples/case_detail.html',
        {
            'case': case,
            'specimens': specimens,
            'samples': samples,
        }
    )

@login_required
def case_list(request):
    from django.db.models import Count, Q
    from qc.models import SampleQC

    cases = Case.objects.select_related('client').order_by('case_name')

    case_data = []
    for case in cases:
        samples      = Sample.objects.filter(specimen__case=case)
        sample_count = samples.count()
        dna_count    = samples.filter(sample_type='DNA').count()
        rna_count    = samples.filter(sample_type='RNA').count()

        qc_qs      = SampleQC.objects.filter(sample__specimen__case=case)
        qc_pass    = qc_qs.filter(qc_status='Pass').count()
        qc_fail    = qc_qs.filter(qc_status='Fail').count()
        qc_caution = qc_qs.filter(qc_status='Caution').count()
        qc_pending = max(sample_count - qc_qs.exclude(qc_status='Pending').count(), 0)

        total = qc_pass + qc_fail + qc_caution + qc_pending
        def pct(n): return round((n / total * 100) if total > 0 else 0)

        case.specimen_count  = case.specimens.count()
        case.sample_count    = sample_count
        case.dna_count       = dna_count
        case.rna_count       = rna_count
        case.qc_pass         = qc_pass
        case.qc_fail         = qc_fail
        case.qc_caution      = qc_caution
        case.qc_pending      = qc_pending
        case.qc_pass_pct     = pct(qc_pass)
        case.qc_fail_pct     = pct(qc_fail)
        case.qc_caution_pct  = pct(qc_caution)
        case.qc_pending_pct  = pct(qc_pending)
        case_data.append(case)

    clients = Client.objects.order_by('client_name')

    return render(request, 'samples/case_list.html', {
        'cases':   case_data,
        'clients': clients,
    })