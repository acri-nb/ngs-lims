from django.urls import path
from . import views

urlpatterns = [
    
    path('samples/', views.SampleListView.as_view(), name='sample-list'),
    path('samples/<int:sample_id>/',  views.sample_detail,         name='sample-detail'),
    path('samples/bulk/',             views.sample_bulk_action,    name='sample-bulk-action'),
    path('samples/export/',           views.sample_export_csv,     name='sample-export-csv'),
    path('samples/import/',           views.sample_import,         name='sample-import'),
    path('samples/import/template/',  views.sample_import_template,name='sample-import-template'),
    path('samples/add/',                views.sample_add,               name='sample-add'),
    path('samples/ajax/cases/',         views.ajax_cases_for_project,   name='ajax-cases-for-project'),
    
    path('cases/', views.case_list, name='case-list'),
    path('cases/<int:case_id>/', views.case_detail, name='case-detail'),
    path('clients/', views.client_list , name='client-list'),
    path('clients/<int:client_pk>/', views.client_detail, name='client-detail'),
    path( "projects/", views.project_list, name="projects-list"),
    path( "projects/<int:project_id>/", views.project_detail, name="projects-detail" ),
]