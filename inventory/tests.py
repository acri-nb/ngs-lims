# inventory/tests.py

from datetime import date, timedelta

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.db import IntegrityError

from inventory.models import (
    Supplier,
    Product,
    ProductSupplier,
    InventoryReceipt,
    Inventory,
)

from locations.models import Location

User = get_user_model()


class InventoryModelTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username="inventoryuser",
            password="test123"
        )

        self.location = Location.objects.create(
            locationName=Location.YETI,
            storageType=Location.FREEZER80C
        )

        self.supplier = Supplier.objects.create(
            supplier_name="Thermo Fisher",
            contact_name="John Doe",
            contact_email="john@example.com"
        )

        self.product = Product.objects.create(
            product_name="Qubit Reagent",
            product_ref_number="QUB-001"
        )

        ProductSupplier.objects.create(
            product=self.product,
            supplier=self.supplier
        )

    def test_supplier_str(self):
        self.assertEqual(
            str(self.supplier),
            "Thermo Fisher"
        )


    def test_product_str(self):
        self.assertEqual(
            str(self.product),
            "Qubit Reagent (QUB-001)"
        )


    def test_product_supplier_unique(self):

        with self.assertRaises(IntegrityError):
            ProductSupplier.objects.create(
                product=self.product,
                supplier=self.supplier
            )


    def test_receipt_creates_inventory_record(self):

        receipt = InventoryReceipt.objects.create(
            product=self.product,
            supplier=self.supplier,
            lot_number="LOT001",
            location=self.location,
            quantity_received=50,
            quantity_unit="tubes",
            date_received=date.today(),
            received_by=self.user
        )

        inventory = Inventory.objects.get(receipt=receipt)

        self.assertEqual(
            inventory.quantity_on_hand,
            50
        )

        self.assertEqual(
            inventory.product,
            self.product
        )

    def test_receipt_only_creates_one_inventory_row(self):

        receipt = InventoryReceipt.objects.create(
            product=self.product,
            supplier=self.supplier,
            lot_number="LOT001",
            location=self.location,
            quantity_received=50,
            quantity_unit="tubes",
            date_received=date.today(),
            received_by=self.user
        )

        receipt.receipt_notes = "Updated notes"
        receipt.save()

        self.assertEqual(
            Inventory.objects.filter(receipt=receipt).count(),
            1
        )

    def test_duplicate_lot_number_not_allowed(self):

        InventoryReceipt.objects.create(
            product=self.product,
            supplier=self.supplier,
            lot_number="LOT001",
            location=self.location,
            quantity_received=10,
            quantity_unit="tubes",
            date_received=date.today(),
            received_by=self.user
        )

        with self.assertRaises(IntegrityError):
            InventoryReceipt.objects.create(
                product=self.product,
                supplier=self.supplier,
                lot_number="LOT001",
                location=self.location,
                quantity_received=20,
                quantity_unit="tubes",
                date_received=date.today(),
                received_by=self.user
            )

    def test_same_lot_allowed_for_different_product(self):

        second_product = Product.objects.create(
            product_name="Nanodrop Buffer",
            product_ref_number="ND-001"
        )

        ProductSupplier.objects.create(
            product=second_product,
            supplier=self.supplier
        )

        InventoryReceipt.objects.create(
            product=self.product,
            supplier=self.supplier,
            lot_number="LOT001",
            location=self.location,
            quantity_received=10,
            quantity_unit="tubes",
            date_received=date.today(),
            received_by=self.user
        )

        receipt = InventoryReceipt.objects.create(
            product=second_product,
            supplier=self.supplier,
            lot_number="LOT001",
            location=self.location,
            quantity_received=20,
            quantity_unit="tubes",
            date_received=date.today(),
            received_by=self.user
        )

        self.assertIsNotNone(receipt)

    def test_receipt_is_expired(self):

        receipt = InventoryReceipt.objects.create(
            product=self.product,
            supplier=self.supplier,
            lot_number="LOT001",
            location=self.location,
            quantity_received=10,
            quantity_unit="tubes",
            date_received=date.today(),
            expiration_date=date.today() - timedelta(days=1),
            received_by=self.user
        )

        self.assertTrue(receipt.is_expired)

    def test_receipt_not_expired(self):

        receipt = InventoryReceipt.objects.create(
            product=self.product,
            supplier=self.supplier,
            lot_number="LOT002",
            location=self.location,
            quantity_received=10,
            quantity_unit="tubes",
            date_received=date.today(),
            expiration_date=date.today() + timedelta(days=30),
            received_by=self.user
        )

        self.assertFalse(receipt.is_expired)

    def test_receipt_without_expiration_not_expired(self):

        receipt = InventoryReceipt.objects.create(
            product=self.product,
            supplier=self.supplier,
            lot_number="LOT003",
            location=self.location,
            quantity_received=10,
            quantity_unit="tubes",
            date_received=date.today(),
            received_by=self.user
        )

        self.assertFalse(receipt.is_expired)

 
    def test_inventory_str(self):

        receipt = InventoryReceipt.objects.create(
            product=self.product,
            supplier=self.supplier,
            lot_number="LOT001",
            location=self.location,
            quantity_received=50,
            quantity_unit="tubes",
            date_received=date.today(),
            received_by=self.user
        )

        inventory = Inventory.objects.get(receipt=receipt)

        self.assertIn(
            "qty: 50",
            str(inventory)
        )

    def test_inventory_unique_constraint(self):

        receipt = InventoryReceipt.objects.create(
            product=self.product,
            supplier=self.supplier,
            lot_number="LOT001",
            location=self.location,
            quantity_received=50,
            quantity_unit="tubes",
            date_received=date.today(),
            received_by=self.user
        )

        with self.assertRaises(IntegrityError):
            Inventory.objects.create(
                product=self.product,
                location=self.location,
                receipt=receipt,
                quantity_on_hand=10
            )