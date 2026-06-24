from django.urls import path
from . import views

urlpatterns = [
    path('',                          views.libprep_list,   name='libprep-list'),
    path('batch/<int:batch_id>/',     views.libprep_detail, name='libprep-detail'),
]

