from django.contrib import admin
from django.utils.html import format_html

from .models import Supplier, Product, ProductSupplier, InventoryReceipt, Inventory, TempLog



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
    search_fields = ['product_name', 'product_ref_number']
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
    inlines = [InventoryInline]

    fieldsets = (
        ('Product & Supplier', {
            'fields': ('product', 'supplier', 'lot_number')
        }),
        ('Receipt Details', {
            'fields': ('receiving_condition', 'date_received', 'expiration_date', 'received_by')
        }),
    )

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
    list_display = ['product', 'location', 'quantity_on_hand', 'last_updated', 'lot_number']
    search_fields = ['product__product_name', 'location__locationName', 'receipt__lot_number']
    list_filter = ['location', 'product']
    ordering = ['product__product_name']
    autocomplete_fields = ['product', 'location', 'receipt']

    fieldsets = (
        ('Stock', {
            'fields': ('product', 'location', 'receipt', 'quantity_on_hand')
        }),
        ('Audit', {
            'fields': ('last_updated',),
            'classes': ('collapse',),
        }),
    )
    readonly_fields = ['last_updated']

    @admin.display(description='Lot Number')
    def lot_number(self, obj):
        return obj.receipt.lot_number


@admin.register(TempLog)
class TempLogAdmin(admin.ModelAdmin):
    list_display = [
        'location', 'date_logged',
        'current_temp_c', 'max_temp_c', 'min_temp_c',
        'max_humidity', 'min_humidity'
    ]
    search_fields = ['location__locationName']
    list_filter = ['location']
    ordering = ['-date_logged']
    autocomplete_fields = ['location']

    fieldsets = (
        ('Location & Date', {
            'fields': ('location', 'date_logged')
        }),
        ('Temperature (°C)', {
            'fields': ('current_temp_c', 'max_temp_c', 'min_temp_c')
        }),
        ('Humidity — Rooms only', {
            'fields': ('max_humidity', 'min_humidity'),
            'classes': ('collapse',),
        }),
    )