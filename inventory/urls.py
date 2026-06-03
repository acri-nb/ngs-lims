from django.urls import path
from . import views

urlpatterns = [
    path('',views.inventory_dashboard,name='inventory-dashboard'),
    path('receipt/add/',views.inventory_receipt_add,name='inventory-receipt-add'),
    path('adjust/<int:inventory_id>/',views.inventory_adjust,name='inventory-adjust'),
]