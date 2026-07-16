from django.db import models
from django.utils.translation import gettext_lazy as _

from locations.models import Location

from django.contrib.auth import get_user_model

User = get_user_model()

# Models for Supplier, Product, ProductSupplier, InventoryReceipt, Inventory, TempLog

class Supplier(models.Model):

    supplier_id = models.AutoField(primary_key=True)
    supplier_name = models.CharField(max_length=255)
    contact_name = models.CharField(max_length=255)
    contact_email = models.EmailField(max_length=255)

    class Meta:
        ordering = ['supplier_name']

    def __str__(self):
        return self.supplier_name


class Product(models.Model):

    product_id = models.AutoField(primary_key=True)
    product_name = models.CharField(max_length=255)
    product_ref_number = models.CharField(max_length=100)

    # Many-to-many with Supplier through ProductSupplier junction
    suppliers = models.ManyToManyField(
        Supplier,
        through='ProductSupplier',
        related_name='products'
    )

    product_notes = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        ordering = ['product_name']

    def __str__(self):
        return f"{self.product_name} ({self.product_ref_number})"


class ProductSupplier(models.Model):
    """
    Junction table, Supplier has many product, Product has many suppliers.
    """
    product_supplier_id = models.AutoField(primary_key=True)
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,       # if product is deleted, remove the link
        related_name='product_suppliers'
    )
    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.PROTECT,       # cannot delete a supplier that is linked to products
        related_name='product_suppliers'
    )

    class Meta:
        unique_together = ('product', 'supplier')   # no duplicate links
        verbose_name = "Product Supplier"
        verbose_name_plural = "Product Suppliers"

    def __str__(self):
        return f"{self.product} — {self.supplier}"



class InventoryReceipt(models.Model):
    
    """
    Records a physical shipment arriving at the lab.
    One receipt = one delivery from one supplier for one product lot.
    A receipt creates one or more Inventory rows when stock is put away.
    """


    receipt_id = models.AutoField(primary_key=True)

    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,       # cannot delete a product that has receipts
        related_name='receipts'
    )
    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.PROTECT,       # tracks which supplier shipped this specific lot
        related_name='receipts'
    )
    lot_number = models.CharField(max_length=100)



    # Receiving condition choices
    FROZEN = 'Frozen'
    ONICE = 'On Ice'
    ROOMTEMP = 'Room-Temperature'
    RECEIVING_CONDITION_CHOICES = [
        (FROZEN,       _('Frozen')),
        (ONICE,    _('On Ice')),
        (ROOMTEMP, _('Room-Temperature')),
    ]

    receiving_condition = models.CharField(
        max_length=50,
        choices=RECEIVING_CONDITION_CHOICES,
        default=ROOMTEMP
    )

    location = models.ForeignKey(
       Location,
       on_delete=models.PROTECT,
       related_name='inventory_receipts'
    )   
    quantity_received = models.IntegerField(default=0)
    
    quantity_unit = models.CharField(
        max_length=50,
        blank=True
    )

    User = get_user_model()

    date_received = models.DateField()
    expiration_date = models.DateField(null=True, blank=True)   # some items don't expire

    receipt_notes = models.CharField(max_length=255, null=True, blank=True)
       
    received_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='inventory_receipts_received'
    )

    def save(self, *args, **kwargs):

        is_new = self.pk is None

        super().save(*args, **kwargs)

        # Only create inventory on first creation
        if is_new:

            inventory, created = Inventory.objects.get_or_create(
                product=self.product,
                location=self.location,
                receipt=self,
                quantity_unit=self.quantity_unit,
                defaults={
                    'quantity_on_hand': self.quantity_received
                }
            )

            # If somehow already exists
            if not created:
                inventory.quantity_on_hand += self.quantity_received
                inventory.save()



    class Meta:
        ordering = ['-date_received']
        unique_together = ('product', 'lot_number')   # same lot can't be received twice for same product
        verbose_name = "Inventory Receipt"
        verbose_name_plural = "Inventory Receipts"

    def __str__(self):
        return f"{self.product} — Lot {self.lot_number} ({self.date_received})"

    @property
    def is_expired(self):
        if not self.expiration_date:
            return False
        from django.utils import timezone
        return self.expiration_date < timezone.now().date()


class Inventory(models.Model):
    """
    Current stock level for a product at a specific location,
    traceable back to the receipt (lot) it came from.
    One receipt can create multiple inventory rows if stock is
    split across different locations.
    """
    inventory_id = models.AutoField(primary_key=True)
    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name='inventory_entries'
    )
    location = models.ForeignKey(
        Location,
        on_delete=models.PROTECT,       # cannot delete a location that has stock in it
        related_name='inventory_entries'
    )
    receipt = models.ForeignKey(
        InventoryReceipt,
        on_delete=models.PROTECT,       # keep lot traceability — never silently lose it
        related_name='inventory_entries'
    )
    quantity_on_hand = models.IntegerField(default=0)

    quantity_unit = models.CharField(
        max_length=50,
        blank=True
    )

    last_updated = models.DateField(auto_now=True)

    class Meta:
        verbose_name = "Inventory"
        verbose_name_plural = "Inventory"
        unique_together = ('product', 'location', 'receipt')    # no duplicate stock rows

    def __str__(self):
        return f"{self.product} @ {self.location} — qty: {self.quantity_on_hand}"