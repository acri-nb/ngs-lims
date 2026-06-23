from datetime import date

from django.test import TestCase
from django.contrib.auth import get_user_model

from inventory.models import (
    Product,
    Supplier,
    ProductSupplier,
    InventoryReceipt,
    Inventory,
)

from inventory.views import _stock_status

from locations.models import Location

User = get_user_model()


class StockStatusTests(TestCase):

    def setUp(self):

        self.user = User.objects.create_user(
            username="tester"
        )

        self.location = Location.objects.create(
            locationName=Location.YETI,
            storageType=Location.FREEZER80C
        )

        self.product = Product.objects.create(
            product_name="Kit",
            product_ref_number="KIT001"
        )

        self.supplier = Supplier.objects.create(
            supplier_name="Vendor",
            contact_name="Contact",
            contact_email="vendor@test.com"
        )

        ProductSupplier.objects.create(
            product=self.product,
            supplier=self.supplier
        )

    def create_inventory(self, original_qty, current_qty):

        receipt = InventoryReceipt.objects.create(
            product=self.product,
            supplier=self.supplier,
            lot_number=f"LOT{original_qty}",
            location=self.location,
            quantity_received=original_qty,
            quantity_unit="tubes",
            date_received=date.today(),
            received_by=self.user
        )

        inventory = Inventory.objects.get(receipt=receipt)
        inventory.quantity_on_hand = current_qty
        inventory.save()

        return inventory

    def test_stock_status_ok(self):

        item = self.create_inventory(100, 90)

        status, pct = _stock_status(item)

        self.assertEqual(status, "ok")
        self.assertEqual(pct, 90)

    def test_stock_status_low(self):

        item = self.create_inventory(100, 20)

        status, pct = _stock_status(item)

        self.assertEqual(status, "low")

    def test_stock_status_critical(self):

        item = self.create_inventory(100, 5)

        status, pct = _stock_status(item)

        self.assertEqual(status, "critical")

    def test_stock_status_empty(self):

        item = self.create_inventory(100, 0)

        status, pct = _stock_status(item)

        self.assertEqual(status, "empty")
        self.assertEqual(pct, 0)