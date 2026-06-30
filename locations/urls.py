from django.urls import path
from . import views

urlpatterns = [
    path('logs/',                           views.location_list,          name='location-list'),
    path('history/',                   views.location_history_index, name='locations'),
    path('<int:location_pk>/log/',     views.add_temp_log,           name='location-add-log'),
    path('<int:location_pk>/history/', views.location_log_history,   name='location-log-history'),
    path('log/<int:log_pk>/edit/',     views.edit_temp_log,          name='templog-edit'),

    path('rack/',                         views.inventory_home,   name='rack-home'),
    path('rack/search/',                  views.inventory_search, name='rack-search'),
    path('rack/list/',                    views.rack_list_json,   name='rack-list-json'),
    path('rack/<int:rack_pk>/',           views.rack_detail,      name='rack-detail'),
    path('rack/<int:rack_pk>/slots/',     views.rack_slots_json,  name='rack-slots-json'),

    path('rack/plate/<int:plate_pk>/',         views.plate_detail, name='plate-detail'),
    path('rack/plate/<int:plate_pk>/move/',    views.move_plate,   name='plate-move'),
    path('rack/plate/well/<int:well_pk>/',     views.well_detail,  name='well-detail'),
]