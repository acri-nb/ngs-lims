from django.urls import path
from . import views

urlpatterns = [
    path('',                                          views.qc_batch_list,    name='qc-batch-list'),

    path('batch/<int:batch_id>/',                     views.qc_batch_detail,  name='qc-batch-detail'),
    path('batch/<int:batch_id>/import/',              views.qc_import_results, name='qc-import-results'),
    
    path('assign/',                                   views.qc_project_list,  name='qc-project-list'),
    path('assign/project/<int:project_id>/',          views.qc_batch_board,   name='qc-batch-board'),
    path('assign/project/<int:project_id>/diff/',     views.qc_diff_preview,  name='qc-diff-preview'),
    path('assign/project/<int:project_id>/save/',     views.qc_save_board,    name='qc-save-board'),
    path('assign/project/<int:project_id>/audit-log/',views.qc_audit_log,     name='qc-audit-log'),

    
]