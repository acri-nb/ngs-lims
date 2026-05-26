from django.contrib import admin
from .models import SampleQCBatch, BatchSample, SampleQC

from django import forms
from django.shortcuts import render, redirect
from django.contrib import messages

from locations.models import Location

class BatchSampleInline(admin.TabularInline):
    """
    Shows all samples assigned to a batch directly on the batch page.
    You can add/remove samples from a batch without leaving the batch form.
    """
    model = BatchSample
    extra = 1
    autocomplete_fields = ['sample']    # search box instead of a giant dropdown


class SampleQCInline(admin.TabularInline):
    """
    Shows all QC results for a batch on the batch page.
    Read-only here — edit individual results from their own page.
    """
    model = SampleQC
    extra = 0
    fields = ['sample', 'qc_status', 'qubit_nm', 'rin', 'dv200', 'nanodrop_260_230', 'notes']
    readonly_fields = ['created_at', 'updated_at']

    def get_readonly_fields(self, request, obj=None):
        return self.readonly_fields
    
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
    # Restrict the sample dropdown to only samples in this batch
        if db_field.name == 'sample' and request._current_obj is not None:
            kwargs['queryset'] = request._current_obj.samples.all()
        return super().formfield_for_foreignkey(db_field, request, **kwargs)



class ChangeSampleLocationForm(forms.Form):

    _selected_action = forms.CharField(
        widget=forms.MultipleHiddenInput
    )

    new_location = forms.ModelChoiceField(
        queryset=Location.objects.all(),
        label='New Location'
    )

def move_samples_to_location(modeladmin, request, queryset):

    if 'apply' in request.POST:

        form = ChangeSampleLocationForm(request.POST)

        if form.is_valid():

            new_location = form.cleaned_data['new_location']

            updated_count = 0

            # Avoid updating the same sample twice
            updated_samples = set()

            for batch in queryset:

                for sample in batch.samples.all():

                    if sample.pk in updated_samples:
                        continue

                    sample.location = new_location
                    sample.save(update_fields=['location'])

                    updated_samples.add(sample.pk)
                    updated_count += 1

            modeladmin.message_user(
                request,
                f"{updated_count} samples moved to '{new_location}'.",
                messages.SUCCESS
            )

            return redirect(request.get_full_path())

    else:

        form = ChangeSampleLocationForm(
            initial={
                '_selected_action': request.POST.getlist('_selected_action')
            }
        )

    return render(
        request,
        'admin/change_sample_location.html',
        {
            'items': queryset,
            'form': form,
            'title': 'Move samples to a new location',
        }
    )


move_samples_to_location.short_description = (
    "Move all samples in selected batches to another location"
)


@admin.register(SampleQCBatch)
class SampleQCBatchAdmin(admin.ModelAdmin):
    list_display = ['batch_name', 'date_batched', 'created_by', 'sample_count']
    search_fields = ['batch_name', 'created_by']
    ordering = ['-date_batched']
    inlines = [BatchSampleInline, SampleQCInline]

    actions = ['move_samples_to_location']
    
    def move_samples_to_location(self, request, queryset):
        return move_samples_to_location(self, request, queryset)

    @admin.display(description='# Samples')
    def sample_count(self, obj):
        return obj.sample_count

    # Stash the current batch object so the inline can access it
    def get_form(self, request, obj=None, **kwargs):
        request._current_obj = obj
        return super().get_form(request, obj, **kwargs)

    def get_inlines(self, request, obj):
        request._current_obj = obj
        return super().get_inlines(request, obj)

@admin.register(BatchSample)
class BatchSampleAdmin(admin.ModelAdmin):
    list_display = ['batch', 'sample']
    search_fields = ['batch__batch_name', 'sample__sample_name']
    list_filter = ['batch']
    autocomplete_fields = ['sample', 'batch']


class ChangeBatchForm(forms.Form):
    _selected_action = forms.CharField(widget=forms.MultipleHiddenInput)
    
    new_batch = forms.ModelChoiceField(
        queryset=SampleQCBatch.objects.all(),
        label='New Batch'
    )

def move_to_batch(modeladmin, request, queryset):

    if 'apply' in request.POST:

        form = ChangeBatchForm(request.POST)

        if form.is_valid():

            new_batch = form.cleaned_data['new_batch']

            updated_count = 0

            for qc in queryset:

                old_batch = qc.batch

                # Remove old junction
                BatchSample.objects.filter(
                    batch=old_batch,
                    sample=qc.sample
                ).delete()

                # Update QC batch
                qc.batch = new_batch
                qc.save()

                # Create new junction
                BatchSample.objects.get_or_create(
                    batch=new_batch,
                    sample=qc.sample
                )

                updated_count += 1

            modeladmin.message_user(
                request,
                f"{updated_count} QC records moved to batch '{new_batch}'.",
                messages.SUCCESS
            )

            return redirect(request.get_full_path())

    else:

        form = ChangeBatchForm(
            initial={
                '_selected_action': request.POST.getlist('_selected_action')
            }
        )

    return render(
        request,
        'admin/change_batch.html',
        {
            'items': queryset,
            'form': form,
            'title': 'Move selected QC records to another batch',
        }
    )


move_to_batch.short_description = "Move selected QC records to another batch"

@admin.register(SampleQC)
class SampleQCAdmin(admin.ModelAdmin):
    list_display = [
        'sample', 'batch', 'qc_status',
        'qubit_nm', 'rin', 'dv200', 'nanodrop_260_230', 'nanodrop_260_280',
        'created_at'
    ]
    search_fields = ['sample__sample_name', 'batch__batch_name']
    list_filter = ['qc_status', 'batch']
    readonly_fields = ['created_at', 'updated_at']

    actions = ['move_to_batch']

    def move_to_batch(self, request, queryset):
        return move_to_batch(self, request, queryset)

    # group fields into sections on the detail page
    fieldsets = (
        ('Sample & Batch', {
            'fields': ('sample', 'batch')
        }),
        ('QC Metrics — Shared', {
            'fields': ('qubit_nm',)
        }),
        ('QC Metrics — RNA only', {
            'fields': ('rin', 'dv200'),
            'classes': ('collapse',),   # collapsed by default, expand when needed
        }),
        ('QC Metrics — DNA only', {
            'fields': ('nanodrop_260_230','nanodrop_260_280'),
            'classes': ('collapse',),
        }),
        ('Audit', {
            'fields': ('created_at', 'updated_at', 'notes', 'edited_by'),
            'classes': ('collapse',),
        }),
    )