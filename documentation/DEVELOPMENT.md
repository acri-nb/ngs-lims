# Developer Guide

This document covers the project structure, conventions used across the codebase, and step-by-step instructions for adding new Django apps, models, views, and pages.

---

## Project structure

```
ngs-lims/
  ngs_lims/          # Django project package, settings, root URLs, wsgi/asgi
  samples/           # Client, Case, Specimen, Sample, Project
  qc/                # SampleQCBatch, BatchSample, SampleQC, BatchAuditLog
  inventory/         # Supplier, Product, ProductSupplier, Inventory, InventoryReceipt
  locations/         # Location, TempLog, Plate, Rack
  templates/         # Project-level base templates (base.html, login.html, home.html)
  static/            # CSS and JS per-view (css/<view>.css, js/<view>.js)
  scripts/           # Backup and restore shell scripts
  mock_data/         # CSV files for development data seeding
```

Each Django app owns its own:

- `models.py`: data and relation layer
- `views.py`: request handling
- `urls.py`: URL patterns for the app
- `admin.py`: admin panel registration
- `templates/<app_name>/`: HTML templates
- `migrations/`: schema migrations

---

## Conventions

### Model IDs

All models use auto-incremented integer primary keys (`AutoField`). Where a human-readable identifier is needed (samples, batches), it is generated in `save()` using the auto-incremented PK formatted as uppercase hex, e.g.:

```python
def _generate_sample_name(self):
    hex_id = format(self.sample_id, '05X')
    return f"{case_name}-{specimen_type}-{sample_type}-{hex_id}"

def save(self, *args, **kwargs):
    super().save(*args, **kwargs)       # get the PK first
    self.sample_name = self._generate_sample_name()
    super().save(update_fields=['sample_name'])
```

Follow this two-save pattern whenever the generated identifier depends on the PK.

### on_delete behaviour

The codebase deliberately uses `PROTECT` for foreign keys that represent audit-critical relationships (you cannot delete a `Sample` that has QC results, or a `Supplier` that has receipts). Use `CASCADE` only on junction tables where the child row has no independent meaning without the parent. This is a deliberate choice to make sure no data is lost easily by accident because the data in the Lab is valuable.

### Authentication

Views that should be restricted to logged-in users use the `@login_required` decorator. Researcher vs. lab staff distinction is handled by checking whether `request.user.profile.is_researcher()` is true. Lab staff have no `UserProfile`; researchers do.

### Templates

All templates extend `templates/base.html`. The base template provides the navigation, authentication state, and message display. Every app template should start with:

```html
{% extends "base.html" %}
{% block content %}
...
{% endblock %}
```

### Static files

Per-view CSS and JS files live in `static/css/<view_name>.css` and `static/js/<view_name>.js`. They are loaded inside a `{% block extra_css %}` or `{% block extra_js %}` block in the extending template. There is no asset bundler, files are served directly by Nginx in production after `collectstatic`.

---

## Adding a new Django app

### Step 1: Create the app

```bash
python manage.py startapp <app_name>
```

### Step 2: Register the app

Add the app to `INSTALLED_APPS` in `ngs_lims/settings.py`:

```python
INSTALLED_APPS = [
    # ... existing apps
    '<app_name>',
]
```

### Step 3: Create models

Define models in `<app_name>/models.py`. Follow the existing conventions:

- Use `AutoField` for primary keys
- Use `PROTECT` for FK relationships unless the child is a junction row
- Add `__str__` to every model
- Add a `Meta` class with `verbose_name` and `verbose_name_plural` for readable admin labels

Run migrations after defining models:

```bash
python manage.py makemigrations <app_name>
python manage.py migrate
```

### Step 4: Register models in admin

In `<app_name>/admin.py`:

```python
from django.contrib import admin
from .models import MyModel

@admin.register(MyModel)
class MyModelAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'created_at')
    search_fields = ('name',)
    list_filter = ('some_field',)
```

### Step 5: Write views

Define views in `<app_name>/views.py`. Use function-based views for consistency with the rest of the project. Class-based views are used in `samples` for the sample list (`SampleListView`) either style is acceptable as long as it is consistent within the file.

```python
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import MyModel

@login_required
def my_model_list(request):
    items = MyModel.objects.all()
    return render(request, '<app_name>/my_model_list.html', {'items': items})
```

### Step 6: Create URL patterns

Create `<app_name>/urls.py`:

```python
from django.urls import path
from . import views

urlpatterns = [
    path('', views.my_model_list, name='my-model-list'),
    path('<int:pk>/', views.my_model_detail, name='my-model-detail'),
    path('new/', views.my_model_create, name='my-model-create'),
]
```

### Step 7: Include URLs in the root URL config

In `ngs_lims/urls.py`, add:

```python
path('<app_name>/', include('<app_name>.urls')),
```

### Step 8: Create templates

Create the directory `<app_name>/templates/<app_name>/` and add your HTML files:

```
<app_name>/templates/<app_name>/my_model_list.html
<app_name>/templates/<app_name>/my_model_detail.html
```

All templates extend `base.html`:

```html
{% extends "base.html" %}
{% load static %}

{% block extra_css %}
<link rel="stylesheet" href="{% static 'css/my_model_list.css' %}">
{% endblock %}

{% block content %}
<h1>My Models</h1>
...
{% endblock %}
```

### Step 9: Add static files

Create `static/css/<view_name>.css` and `static/js/<view_name>.js` as needed. Reference them in the template via `{% load static %}` and `{% static 'css/...' %}`.

---

## Adding a new page to an existing app

If the new page is logically part of an existing app (a new report view in `samples`), skip creating a new app and instead:

0. *Recommended adding your ideas to the Draw.io to help conceptualize*
1. Add the view function to the existing `views.py`
2. Add the URL pattern to the existing `urls.py`
3. Add the template to `<app_name>/templates/<app_name>/`
4. Add static files as needed


## Adding a new model to an existing app

1. Define the model in the app's `models.py`
2. Run `python manage.py makemigrations <app_name>`
3. Review the generated migration file
4. Run `python manage.py migrate`
5. Register the model in `admin.py`

If the model has a FK to a model in another app, import it explicitly:

```python
from samples.models import Project
```

Circular imports can occur if two apps import from each other. Resolve with a string reference in the FK:

```python
project = models.ForeignKey('samples.Project', on_delete=models.PROTECT)
```

---

## Working with the researcher portal

The portal (`/portal/`) is a separate, restricted view for external researchers. When adding features that researchers should be able to see (QC results for their own project), add a separate view that filters by `request.user.profile.client` rather than exposing the full staff view.

The pattern used in the existing codebase:

```python
from samples.models import UserProfile

@login_required
def researcher_something(request):
    try:
        profile = request.user.profile
        if not profile.is_researcher():
            return redirect('home')
        client = profile.client
    except UserProfile.DoesNotExist:
        return redirect('home')

    # Filter data to this client only
    projects = Project.objects.filter(client=client)
    ...
```

---

## Modifying the draw.io architecture diagram

The file `ngs-lims.drawio` contains the system design and workflow diagrams. Open it at [https://app.diagrams.net/](https://app.diagrams.net/) via File > Open from Device. After making changes, export and commit the updated file. Keep this diagram in sync with significant model or workflow changes.

---

## Running tests

The test files are minimal stubs (`tests.py` in each app). When adding new functionality, add test cases to the relevant `tests.py`:

```bash
python manage.py test <app_name>
python manage.py test          # run all tests
```

---

## Mock data

The `mock_data/` directory contains CSV files that can be used to seed a development database. There is no automated seeding script, import them manually through the admin panel or write a management command if repeated seeding is needed.