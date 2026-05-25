from django.contrib import admin
from django.utils.html import format_html

from .models import Supplier, Product, ProductSupplier, InventoryReceipt, Inventory

from django.http import HttpResponseRedirect
from django.shortcuts import render
from .forms import BulkQuantityForm

class ProductSupplierInline(admin.TabularInline):
    """Shows which products a supplier provides, directly on the supplier page."""
    model = ProductSupplier
    extra = 1
    autocomplete_fields = ['product']


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ['supplier_name', 'contact_name', 'contact_email']
    search_fields = ['supplier_name', 'contact_name', 'contact_email']
    ordering = ['supplier_name']
    inlines = [ProductSupplierInline]



class ProductSupplierInlineFromProduct(admin.TabularInline):
    """Shows which suppliers provide this product, directly on the product page."""
    model = ProductSupplier
    extra = 1
    autocomplete_fields = ['supplier']
    verbose_name = "Supplier"
    verbose_name_plural = "Suppliers for this product"


class InventoryReceiptInline(admin.TabularInline):
    """Shows all receipts for a product on the product page."""
    model = InventoryReceipt
    extra = 0
    fields = ['supplier', 'lot_number', 'date_received', 'expiration_date', 'receiving_condition', 'received_by']
    readonly_fields = ['date_received']
    show_change_link = True     # click through to the full receipt page


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['product_name', 'product_ref_number', 'supplier_list']
    list_filter = ['suppliers']
    search_fields = ['product_name', 'product_ref_number', "suppliers"]
    ordering = ['product_name']
    inlines = [ProductSupplierInlineFromProduct, InventoryReceiptInline]

    @admin.display(description='Suppliers')
    def supplier_list(self, obj):
        """Shows comma-separated supplier names in the list view."""
        suppliers = obj.suppliers.all()
        if not suppliers:
            return '—'
        return ', '.join(s.supplier_name for s in suppliers)



@admin.register(ProductSupplier)
class ProductSupplierAdmin(admin.ModelAdmin):
    list_display = ['product', 'supplier']
    search_fields = ['product__product_name', 'supplier__supplier_name']
    autocomplete_fields = ['product', 'supplier']



class InventoryInline(admin.TabularInline):
    """Shows where stock from this receipt was put away."""
    model = Inventory
    extra = 1
    fields = ['product', 'location', 'quantity_on_hand']
    autocomplete_fields = ['location']


@admin.register(InventoryReceipt)
class InventoryReceiptAdmin(admin.ModelAdmin):
    list_display = [
        'product', 'supplier', 'lot_number',
        'date_received', 'expiration_date',
        'receiving_condition', 'expiry_status'
    ]
    search_fields = ['product__product_name', 'supplier__supplier_name', 'lot_number']
    list_filter = ['receiving_condition', 'supplier']
    ordering = ['-date_received']
    autocomplete_fields = ['product', 'supplier']
    
    

    fieldsets = (
        ('Product & Supplier', {
            'fields': ('product', 'supplier', 'lot_number', "location")
        }),
        ('Receipt Details', {
            'fields': ('receiving_condition', 'quantity_received', 'quantity_unit', 'date_received', 'expiration_date', 'receipt_notes', 'received_by')
        }),
    )


    def get_readonly_fields(self, request, obj=None):

        readonly = list(self.readonly_fields)

        # After creation lock critical inventory fields
        if obj:
            readonly.extend([
                'product',
                'location',
                'quantity_received',
                'supplier',
                'lot_number'
            ])

        return readonly


    @admin.display(description='Expiry')
    def expiry_status(self, obj):
        """Shows a coloured indicator for expired items in the list."""
        if not obj.expiration_date:
            return '—'
        if obj.is_expired:
            return format_html(
                '<span style="color: #c0392b; font-weight: bold;">Expired {}</span>',
                obj.expiration_date
            )
        return format_html(
            '<span style="color: #27ae60;">Valid until {}</span>',
            obj.expiration_date
        )


@admin.register(Inventory)
class InventoryAdmin(admin.ModelAdmin):
    list_display = ['product', 'location', 'quantity_on_hand', 'quantity_unit', 'last_updated', 'lot_number']
    search_fields = ['product__product_name', 'location__locationName', 'receipt__lot_number']
    list_filter = ['location', 'product']
    ordering = ['product__product_name']
    autocomplete_fields = ['product', 'location', 'receipt']
    readonly_fields = ['last_updated']
    actions = ['bulk_edit_quantity']  

    def bulk_edit_quantity(self, request, queryset):
        items = list(queryset.select_related('product', 'location', 'receipt'))

        if 'apply' in request.POST:
            form = BulkQuantityForm(request.POST, inventory_items=items)
            if form.is_valid():
                updated = 0
                for item in items:
                    new_qty = form.cleaned_data.get(f'qty_{item.inventory_id}')
                    if new_qty is not None and new_qty != item.quantity_on_hand:
                        item.quantity_on_hand = new_qty
                        item.save(update_fields=['quantity_on_hand', 'last_updated'])
                        updated += 1
                self.message_user(request, f"Updated quantity for {updated} item(s).")
                return HttpResponseRedirect(request.get_full_path())
        else:
            form = BulkQuantityForm(inventory_items=items)

        return render(
            request,
            'admin/bulk_edit_quantity.html',
            {'items': items, 'form': form}
        )

    bulk_edit_quantity.short_description = "Edit quantity for selected items"

    #TODO Inventory status (low inventory vs OK)

    @admin.display(description='Lot Number')
    def lot_number(self, obj):
        return obj.receipt.lot_number


from .forms import BulkQuantityForm

@admin.action(description='Edit quantity for selected items')
def bulk_edit_quantity(self, request, queryset):
    items = list(queryset.select_related('product', 'location', 'receipt'))

    if 'apply' in request.POST:
        form = BulkQuantityForm(request.POST, inventory_items=items)
        if form.is_valid():
            updated = 0
            for item in items:
                new_qty = form.cleaned_data.get(f'qty_{item.inventory_id}')
                if new_qty is not None and new_qty != item.quantity_on_hand:
                    item.quantity_on_hand = new_qty
                    item.save(update_fields=['quantity_on_hand', 'last_updated'])
                    updated += 1
            self.message_user(request, f"Updated quantity for {updated} item(s).")
            return HttpResponseRedirect(request.get_full_path())
    else:
        form = BulkQuantityForm(inventory_items=items)

    return render(
        request,
        'admin/bulk_edit_quantity.html',
        {'items': items, 'form': form}
    )
