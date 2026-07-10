"""
URL configuration for ngs_lims project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
import debug_toolbar
from samples.views_auth import smart_redirect, researcher_portal, researcher_project_detail
from samples.views import home

admin.site.site_header = 'ngs-lims Admin'
admin.site.index_title = 'Admin'

urlpatterns = [
    path('',smart_redirect,name='smart-redirect'),
    
    path('dashboard/', home,                     name='home'),
    path('portal/',    researcher_portal,         name='researcher-portal'),
    path('portal/projects/<int:project_id>/',researcher_project_detail,name='researcher-projects-detail'),

    path('',            include('samples.urls')),
    path('locations/', include('locations.urls')),
    path('inventory/', include('inventory.urls')),
    path('qc/', include('qc.urls')),
    path('library/', include('library.urls')),
    path('accounts/',  include('django.contrib.auth.urls')),
    path('admin/',     admin.site.urls),
    path('__debug__/', include(debug_toolbar.urls)),
]

