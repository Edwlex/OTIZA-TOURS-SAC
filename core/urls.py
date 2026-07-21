from django.urls import path
from django.views.generic import RedirectView
from . import views

app_name = 'core'

urlpatterns = [
    # Redirect raíz a login
    path('', RedirectView.as_view(url='/login/', permanent=False)),
    
    # ==================== AUTH ====================
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    
    # ==================== DASHBOARD ====================
    path('dashboard/', views.dashboard_view, name='dashboard'),
    
    # ==================== VENTAS ====================
    path('ventas/', views.ventas_lista, name='ventas_lista'),
    path('ventas/nuevo/<int:viaje_id>/', views.nueva_venta, name='venta_create'),
    path('ventas/mapa-asientos/<int:viaje_id>/', views.mapa_asientos, name='mapa_asientos'),
    path('ventas/procesar/', views.procesar_venta, name='procesar_venta'),
    
    # ==================== TICKETS ====================
    # Redirige a descargar_ticket_pdf para que coincida con la función de views.py
    path('ventas/ticket/<int:ticket_id>/', views.descargar_ticket_pdf, name='ver_ticket'),
    path('tickets/<int:ticket_id>/pdf/', views.descargar_ticket_pdf, name='descargar_ticket_pdf'),
    # Agrega al final de urlpatterns:
    path('tickets/<int:venta_id>/pdf/', views.descargar_ticket_pdf, name='descargar_ticket_pdf'),

    # ==================== CLIENTES Y FIDELIZACIÓN ====================
    path('clientes/historial/<str:dni>/', views.historial_cliente, name='cliente_historial'),
    path('clientes/fidelizacion/', views.fidelizacion_cliente, name='fidelizacion'),
    path('clientes/buscar/', views.buscar_cliente_view, name='buscar_cliente'),

    # ==================== REPORTES ====================
    path('reportes/', views.reportes_unificados, name='reportes_unificados'),
    
    # ==================== NOTIFICACIONES ====================
    path('notificaciones/', views.notificaciones_lista, name='notificaciones_lista'),

    # ==================== PERFIL ====================
    path('perfil/', views.mi_perfil, name='mi_perfil'),
    
    # ==================== ADMIN - FIDELIZACIÓN ====================
    path('panel-admin/fidelizacion/', views.fidelizacion_admin, name='fidelizacion_admin'),
    
    # ==================== ADMIN - GESTIÓN DEL SISTEMA ====================
    path('panel-admin/vehiculos/', views.vehiculos_lista, name='vehiculos_lista'),
    path('panel-admin/vehiculos/nuevo/', views.vehiculo_nuevo, name='vehiculo_nuevo'),
    path('panel-admin/vehiculos/editar/<int:id>/', views.vehiculo_editar, name='vehiculo_editar'),
    path('panel-admin/vehiculos/eliminar/<int:id>/', views.vehiculo_eliminar, name='vehiculo_eliminar'),

    path('panel-admin/choferes/', views.choferes_lista, name='choferes_lista'),
    path('panel-admin/choferes/nuevo/', views.chofer_nuevo, name='chofer_nuevo'),
    path('panel-admin/choferes/editar/<int:id>/', views.chofer_editar, name='chofer_editar'),
    path('panel-admin/choferes/eliminar/<int:id>/', views.chofer_eliminar, name='chofer_eliminar'),

    path('panel-admin/rutas/', views.rutas_lista, name='rutas_lista'),
    path('panel-admin/rutas/nuevo/', views.ruta_nuevo, name='ruta_nuevo'),
    path('panel-admin/rutas/editar/<int:id>/', views.ruta_editar, name='ruta_editar'),
    path('panel-admin/rutas/eliminar/<int:id>/', views.ruta_eliminar, name='ruta_eliminar'),

    path('panel-admin/asignacion-viajes/', views.asignacion_viajes, name='asignacion_viajes'),
    path('panel-admin/usuarios/', views.usuarios_lista, name='usuarios_lista'),
    path('panel-admin/usuarios/nuevo/', views.usuario_nuevo, name='usuario_nuevo'),
    path('panel-admin/usuarios/<int:id>/editar/', views.usuario_editar, name='usuario_editar'),
    path('panel-admin/usuarios/<int:id>/eliminar/', views.usuario_eliminar, name='usuario_eliminar'),  
    
    # ==================== INCIDENCIAS ====================
    path('incidencias/', views.incidencias_lista, name='incidencias_lista'),

    # ==================== PORTAL CHOFERES ====================
    path('chofer/reservar/', views.chofer_reservar, name='chofer_reservar'),
    path('chofer/confirmar-reserva/', views.chofer_confirmar_reserva, name='chofer_confirmar_reserva'),
    path('chofer/cancelar-reserva/<int:reserva_id>/', views.chofer_cancelar_reserva, name='chofer_cancelar_reserva'),
]