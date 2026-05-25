from django import forms
from locations.models import Location
from .models import Sample


class BulkLocationForm(forms.Form):
    location = forms.ModelChoiceField(
        queryset=Location.objects.all(),
        required=True
    )

class BulkReceivingConditionForm(forms.Form):
    receiving_condition = forms.ChoiceField(
        choices=Sample.RECEIVING_CONDITION_CHOICES,
        required=True
    )