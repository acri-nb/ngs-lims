from django.urls import path
from . import views



##URLConf
#urlpatterns = [
#    path('hello/', views.say_hello),    
#]

urlpatterns = [
    path('',         views.home,                    name='home'),
    path('samples/', views.SampleListView.as_view(), name='sample-list'),
]