from django.urls import path
from . import views

urlpatterns = [
    path('',                                views.libprep_list,         name='libprep-list'),
    path('batch/<int:batch_id>/',           views.libprep_detail,       name='libprep-detail'),

    path('projects/',                       views.libprep_project_list, name='libprep-project-list'),
    path('newbatch/<int:project_id>/',      views.libprep_new_batch,    name='libprep-new-batch'),
    path('newbatch/<int:project_id>/check/', views.libprep_check_batch, name='libprep-check-batch'),
]

