from django.contrib import admin

# samples/admin.py
from django.contrib import admin
from .models import Client, Case, Specimen, SpecimenType, Sample, Project

class CaseInline(admin.TabularInline):
    model = Case
    extra = 1          # shows one empty row ready to fill
    fields = ['case_name']

class ProjectInline(admin.TabularInline):
    model = Project
    extra = 1
    fields = ['project_name', 'sequencing_type']

@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ['client_name', 'organisation_name']
    search_fields = ['client_name', 'organisation_name']
    inlines = [CaseInline, ProjectInline]   # create cases/projects directly from client page


class SpecimenInline(admin.TabularInline):
    model = Specimen
    extra = 1
    fields = ['specimen_type']
    autocomplete_fields = ['specimen_type']


@admin.register(Case)
class CaseAdmin(admin.ModelAdmin):
    list_display = ['case_name', 'client']
    search_fields = ['case_name']
    list_filter = ['client']
    inlines = [SpecimenInline]

class SampleInline(admin.TabularInline):
    model = Sample
    extra = 0
    fields = ['sample_name', 'sample_type', 'date_received']
    readonly_fields = ['sample_name', 'date_received']   
    autocomplete_fields = ['project']   
    show_change_link = True  

@admin.register(SpecimenType)
class SpecimenTypeAdmin(admin.ModelAdmin):
    list_display = ['specimen_type']
    search_fields = ['specimen_type']

#TODO Sample in specimen does not work (/samples/specimen/<ID>/change/)
@admin.register(Specimen)
class SpecimenAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'specimen_type', 'case']
    search_fields = ['case__case_name', 'specimen_type__specimen_type']
    list_filter = ['specimen_type']
    autocomplete_fields = ['specimen_type']
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