from django.urls import path
from . import views

urlpatterns = [
    path('',                                views.libprep_list,         name='libprep-list'),
    path('batch/<int:batch_id>/',           views.libprep_detail,       name='libprep-detail'),
    path('batch/<int:batch_id>/mastermix/save/', views.libprep_mastermix_save, name='libprep-mastermix-save'),
    path('batch/<int:batch_id>/mastermix/print/', views.libprep_mastermix_print, name='libprep-mastermix-print'),
    
    path('projects/',                       views.libprep_project_list, name='libprep-project-list'),
    path('newbatch/<int:project_id>/',      views.libprep_new_batch,    name='libprep-new-batch'),
    path('newbatch/<int:project_id>/check/', views.libprep_check_batch, name='libprep-check-batch'),
    
]

