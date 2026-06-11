from django.urls import path
from . import views

urlpatterns = [
    path('',                                          views.qc_project_list,  name='qc-project-list'),
    path('project/<int:project_id>/',                 views.qc_batch_board,   name='qc-batch-board'),
    path('project/<int:project_id>/diff/',            views.qc_diff_preview,  name='qc-diff-preview'),
    path('project/<int:project_id>/save/',            views.qc_save_board,    name='qc-save-board'),
    path('project/<int:project_id>/audit-log/',       views.qc_audit_log,     name='qc-audit-log'),
]