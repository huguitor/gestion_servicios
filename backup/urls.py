# gestion/backup/urls.py
from django.urls import path
from . import views

urlpatterns = [
    # Info
    path('tipos/', views.tipos_disponibles, name='backup-tipos'),

    # Exportación
    path('clientes/', views.backup_clientes, name='backup-clientes'),
    path('productos/', views.backup_productos, name='backup-productos'),
    path('servicios/', views.backup_servicios, name='backup-servicios'),
    path('presupuestos/', views.backup_presupuestos, name='backup-presupuestos'),
    path('remitos/', views.backup_remitos, name='backup-remitos'),
    path('configuracion/', views.backup_configuracion, name='backup-configuracion'),
    path('media/', views.backup_media, name='backup-media'),
    path('database/', views.backup_database, name='backup-database'),
    path('todo/', views.backup_todo, name='backup-todo'),

    # Restauración
    path('restore/clientes/', views.restore_clientes, name='backup-restore-clientes'),
    path('restore/productos/', views.restore_productos, name='backup-restore-productos'),
    path('restore/servicios/', views.restore_servicios, name='backup-restore-servicios'),
    path('restore/presupuestos/', views.restore_presupuestos, name='backup-restore-presupuestos'),
    path('restore/remitos/', views.restore_remitos, name='backup-restore-remitos'),
    path('restore/configuracion/', views.restore_configuracion, name='backup-restore-configuracion'),
    path('restore/todo/', views.restore_todo_view, name='backup-restore-todo'),

    # Historial
    path('historial/', views.historial_list, name='backup-historial-list'),
    path('historial/<str:filename>/', views.historial_download, name='backup-historial-download'),
    path('historial/<str:filename>/delete/', views.historial_delete, name='backup-historial-delete'),
]
