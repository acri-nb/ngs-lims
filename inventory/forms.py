from django import forms
from .models import Inventory


class BulkQuantityForm(forms.Form):
    def __init__(self, *args, inventory_items=None, **kwargs):
        super().__init__(*args, **kwargs)
        if inventory_items:
            for item in inventory_items:
                self.fields[f'qty_{item.inventory_id}'] = forms.IntegerField(
                    label=f"{item.product.product_name} @ {item.location}: Lot {item.receipt.lot_number}",
                    initial=item.quantity_on_hand,
                    min_value=0,
                )