from django.urls import path
from . import views

urlpatterns = [
    
    path('samples/', views.SampleListView.as_view(), name='sample-list'),

    path('clients/', views.client_list , name='client-list'),
    path('clients/<int:client_pk>/', views.client_detail, name='client-detail'),
    path( "projects/", views.project_list, name="project-list"),
    path( "projects/<int:project_id>/", views.project_detail, name="project-detail" ),
]