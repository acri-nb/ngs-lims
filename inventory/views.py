from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from datetime import timedelta

from .models import Inventory, InventoryReceipt, Product, Supplier, ProductSupplier

from locations.models import Location

LOW_STOCK_THRESHOLD  = 0.25   # below 25% of original qty = low
CRITICAL_THRESHOLD   = 0.10   # below 10% = critical

# UNIT GROUPS shown in the receipt form 

UNIT_GROUPS = [
    {
        'label': 'Volume',
        'units': [
            {'value': 'µL',  'label': 'µL'},
            {'value': 'mL',  'label': 'mL'},
            {'value': 'L',   'label': 'L'},
        ]
    },
    {
        'label': 'Count / packaging',
        'units': [
            {'value': 'bottle',  'label': 'bottle'},
            {'value': 'bottles', 'label': 'bottles'},
            {'value': 'pack',    'label': 'pack'},
            {'value': 'box',     'label': 'box'},
            {'value': 'MM',      'label': 'MM'},
            {'value': 'tube',    'label': 'tube'},
            {'value': 'tubes',   'label': 'tubes'},
            {'value': 'kit',     'label': 'kit'},
            {'value': 'vial',    'label': 'vial'},
            {'value': 'vials',   'label': 'vials'},
            {'value': 'each',    'label': 'each'},
        ]
    },
    {
        'label': 'Mass',
        'units': [
            {'value': 'µg',  'label': 'µg'},
            {'value': 'mg',  'label': 'mg'},
            {'value': 'g',   'label': 'g'},
        ]
    },
    {
        'label': 'Reactions / preps',
        'units': [
            {'value': 'rxn',   'label': 'rxn'},
            {'value': 'preps', 'label': 'preps'},
            {'value': 'reactions', 'label': 'reactions'},
        ]
    },
    
]

def _stock_status(inventory_item):
    """
    Returns (status_string, pct_int) for a given Inventory row.
    Uses quantity_received from the receipt as the baseline.
    """
    original = inventory_item.receipt.quantity_received
    current  = inventory_item.quantity_on_hand

    if original <= 0:
        return 'empty', 0

    pct = min(100, round((current / original) * 100))

    if current <= 0:
        status = 'empty'
    elif pct <= CRITICAL_THRESHOLD * 100:
        status = 'critical'
    elif pct <= LOW_STOCK_THRESHOLD * 100:
        status = 'low'
    else:
        status = 'ok'

    return status, pct



@login_required
def inventory_dashboard(request):
    today      = timezone.localdate()
    in_30_days = today + timedelta(days=30)

    # Inventory with stock status annotations
    inventory_qs = (
        Inventory.objects
        .select_related('product', 'location', 'receipt')
        .order_by('product__product_name')
    )

    inventory_data = []
    low_stock_count     = 0
    in_stock_count      = 0
    expiring_soon_count = 0

    for item in inventory_qs:
        status, pct = _stock_status(item)
        expiring_soon = (
            item.receipt.expiration_date and
            today <= item.receipt.expiration_date <= in_30_days
        )
        if expiring_soon:
            expiring_soon_count += 1
        if status in ('low', 'critical'):
            low_stock_count += 1
        if status != 'empty':
            in_stock_count += 1

        item.stock_status  = status
        item.stock_pct     = pct
        item.expiring_soon = expiring_soon
        inventory_data.append(item)

    receipts  = InventoryReceipt.objects.select_related(
        'product', 'supplier', 'location', 'received_by'
    ).order_by('-date_received')

    products  = Product.objects.prefetch_related('suppliers', 'inventory_entries').order_by('product_name')
    suppliers = Supplier.objects.prefetch_related('products').order_by('supplier_name')
    locations = Location.objects.all()

    return render(request, 'inventory/inventory_dashboard.html', {
        'inventory':          inventory_data,
        'receipts':           receipts,
        'products':           products,
        'suppliers':          suppliers,
        'locations':          locations,
        'total_products':     products.count(),
        'in_stock_count':     in_stock_count,
        'low_stock_count':    low_stock_count,
        'expiring_soon_count':expiring_soon_count,
    })



@login_required
def inventory_receipt_add(request):
    from django.contrib.auth import get_user_model
    User = get_user_model()

    if request.method == 'POST':
        try:
            product   = Product.objects.get(pk=request.POST['product'])
            supplier  = Supplier.objects.get(pk=request.POST['supplier'])
            location  = Location.objects.get(pk=request.POST['location'])
            received_by = User.objects.get(pk=request.POST['received_by'])

            expiry = request.POST.get('expiration_date') or None

            receipt = InventoryReceipt(
                product             = product,
                supplier            = supplier,
                location            = location,
                received_by         = received_by,
                lot_number          = request.POST['lot_number'],
                receiving_condition = request.POST['receiving_condition'],
                quantity_received   = int(request.POST['quantity_received']),
                quantity_unit       = request.POST.get('quantity_unit', ''),
                date_received       = request.POST['date_received'],
                expiration_date     = expiry,
                receipt_notes       = request.POST.get('receipt_notes', '') or None,
            )
            receipt.save()   # triggers Inventory creation in model.save()
            messages.success(request, f"Receipt logged: {product.product_name} — Lot {receipt.lot_number}.")
            return redirect('inventory-dashboard')

        except Exception as e:
            messages.error(request, f"Could not save receipt: {e}")

    # Build product list with supplier IDs for the JS filter
    products = Product.objects.prefetch_related('suppliers').order_by('product_name')
    for p in products:
        p.supplier_ids = ','.join(str(s.supplier_id) for s in p.suppliers.all())

    suppliers = Supplier.objects.order_by('supplier_name')
    locations = Location.objects.order_by('storageType', 'locationName')
    lab_users = User.objects.filter(is_active=True).order_by('username')

    return render(request, 'inventory/receipt_form.html', {
        'products':    products,
        'suppliers':   suppliers,
        'locations':   locations,
        'lab_users':   lab_users,
        'unit_groups': UNIT_GROUPS,
        'today':       timezone.localdate().isoformat(),
    })


@login_required
def inventory_adjust(request, inventory_id):
    item = get_object_or_404(Inventory, pk=inventory_id)

    if request.method == 'POST':
        try:
            new_qty = int(request.POST['quantity_on_hand'])
            if new_qty < 0:
                raise ValueError("Quantity cannot be negative.")
            item.quantity_on_hand = new_qty
            item.save()
            messages.success(request, f"Stock updated: {item.product.product_name} → {new_qty} {item.quantity_unit}")
            return redirect('inventory-dashboard')
        except Exception as e:
            messages.error(request, f"Could not update: {e}")

    return render(request, 'inventory/inventory_adjust.html', {'item': item})