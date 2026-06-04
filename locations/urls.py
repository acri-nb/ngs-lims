from django.urls import path
from . import views

urlpatterns = [
    path('',                           views.location_list,          name='location-list'),
    path('history/',                   views.location_history_index, name='locations'),
    path('<int:location_pk>/log/',     views.add_temp_log,           name='location-add-log'),
    path('<int:location_pk>/history/', views.location_log_history,   name='location-log-history'),
    path('log/<int:log_pk>/edit/',     views.edit_temp_log,          name='templog-edit'),
    
]
