from django.contrib import admin

# samples/admin.py
from django.contrib import admin
from .models import Client, Case, Specimen, Sample, Project

class CaseInline(admin.TabularInline):
    model = Case
    extra = 1          # shows one empty row ready to fill

class ProjectInline(admin.TabularInline):
    model = Project
    extra = 1

@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ['client_name', 'organisation_name']
    search_fields = ['client_name', 'organisation_name']
    inlines = [CaseInline, ProjectInline]   # create cases/projects directly from client page

class SpecimenInline(admin.TabularInline):
    model = Specimen
    extra = 1

@admin.register(Case)
class CaseAdmin(admin.ModelAdmin):
    list_display = ['case_name', 'client']
    search_fields = ['case_name']
    list_filter = ['client']
    inlines = [SpecimenInline]

class SampleInline(admin.TabularInline):
    model = Sample
    extra = 1

@admin.register(Specimen)
class SpecimenAdmin(admin.ModelAdmin):
    list_display = ['specimen_name', 'specimen_origin', 'case']
    list_filter = ['specimen_origin']
    inlines = [SampleInline]

@admin.register(Sample)
class SampleAdmin(admin.ModelAdmin):
    list_display = ['sample_name', 'sample_type', 'project', 'date_received', 'receiving_condition']
    search_fields = ['sample_name']
    list_filter = ['sample_type', 'receiving_condition', 'project']

@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ['project_name', 'client', 'sequencing_type', 'date_created']
    list_filter = ['sequencing_type', 'client']
    search_fields = ['project_name']