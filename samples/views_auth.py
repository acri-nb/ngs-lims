"""
samples/views_auth.py

Handles:
  - Smart login redirect (researcher vs lab staff)
  - Researcher portal views
  - Access control mixin/decorator for all views
"""

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout
from django.http import Http404
from django.views.generic import View

from .models import Client, Project, Sample, UserProfile
from qc.models import SampleQC


#get client from logged-in user

def get_user_client(user):
    """
    Returns the Client linked to this user, or None if they are lab staff.
    """
    try:
        return user.profile.client
    except (UserProfile.DoesNotExist, AttributeError):
        return None


def is_researcher(user):
    return get_user_client(user) is not None


# ── SMART LOGIN REDIRECT ───

@login_required
def smart_redirect(request):
    """
    Called after login instead of going straight to home.
    Researchers → their portal. Lab staff → dashboard.
    """
    if is_researcher(request.user):
        return redirect('researcher-portal')
    return redirect('home')


# ──ACCESS CONTROL DECORATOR───

def lab_staff_required(view_func):
    """
    Decorator — blocks researcher accounts from lab-internal views.
    Redirects them to their portal instead.
    """
    @login_required
    def wrapper(request, *args, **kwargs):
        if is_researcher(request.user):
            return redirect('researcher-portal')
        return view_func(request, *args, **kwargs)
    return wrapper


@login_required
def researcher_portal(request):
    """
    Landing page for researchers — shows only their client's projects.
    Lab staff who land here get sent to the dashboard.
    """
    client = get_user_client(request.user)
    if not client:
        return redirect('home')

    projects = client.projects.order_by('-date_created')

    project_data = []
    for project in projects:
        samples      = project.samples.all()
        sample_count = samples.count()

        qc_qs      = SampleQC.objects.filter(sample__project=project)
        qc_pass    = qc_qs.filter(qc_status='Pass').count()
        qc_fail    = qc_qs.filter(qc_status='Fail').count()
        qc_caution = qc_qs.filter(qc_status='Caution').count()
        qc_pending = max(sample_count - qc_qs.exclude(qc_status='Pending').count(), 0)

        total_qc = qc_pass + qc_fail + qc_caution + qc_pending
        def pct(n): return round((n / total_qc * 100) if total_qc > 0 else 0)

        project_data.append({
            'project':        project,
            'sample_count':   sample_count,
            'qc_pass':        qc_pass,
            'qc_fail':        qc_fail,
            'qc_caution':     qc_caution,
            'qc_pending':     qc_pending,
            'qc_pass_pct':    pct(qc_pass),
            'qc_fail_pct':    pct(qc_fail),
            'qc_caution_pct': pct(qc_caution),
        })

    return render(request, 'samples/researcher_portal.html', {
        'client':   client,
        'projects': project_data,
    })


@login_required
def researcher_project_detail(request, project_id):
    """
    Shows one project's samples — ONLY accessible if:
      - User is a researcher AND the project belongs to their client
      - OR user is lab staff (they can see everything)
    """
    project = get_object_or_404(Project, pk=project_id)

    client = get_user_client(request.user)
    if client and project.client != client:
        # Researcher trying to access another client's project — block it
        raise Http404

    samples = (
        project.samples
        .select_related('specimen__case', 'specimen__specimen_type', 'location')
        .prefetch_related('qc_results')
        .order_by('specimen__case__case_name', 'sample_name')
    )

    total_samples    = samples.count()
    qc_pass_count    = SampleQC.objects.filter(sample__project=project, qc_status='Pass').count()
    qc_fail_count    = SampleQC.objects.filter(sample__project=project, qc_status='Fail').count()
    qc_caution_count = SampleQC.objects.filter(sample__project=project, qc_status='Caution').count()
    qc_pending_count = max(
        total_samples - SampleQC.objects.filter(sample__project=project).exclude(qc_status='Pending').count(),
        0
    )

    # Build per-sample pipeline stage
    from .views import _pipeline_stage  # reuse the helper from views.py
    sample_data = []
    for sample in samples:
        latest_qc   = sample.qc_results.order_by('-created_at').first()
        qc_status   = latest_qc.qc_status if latest_qc else None
        stage, icon = _pipeline_stage(sample)
        sample_data.append({
            'sample':         sample,
            'qc_status':      qc_status,
            'pipeline_stage': stage,
            'pipeline_icon':  icon,
        })

    # Use researcher template if researcher, full template if lab staff
    template = 'samples/researcher_project_detail.html' if client else 'samples/project_detail.html'

    return render(request, template, {
        'project':          project,
        'samples':          sample_data,
        'total_samples':    total_samples,
        'qc_pass_count':    qc_pass_count,
        'qc_fail_count':    qc_fail_count,
        'qc_caution_count': qc_caution_count,
        'qc_pending_count': qc_pending_count,
    })
