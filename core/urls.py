from django.urls import path
from django.views.generic import RedirectView
from . import views

app_name = 'core'

urlpatterns = [
    # 🔹 Redirect raíz a login
    path('', RedirectView.as_view(url='/login/', permanent=False)),
    
    # ==================== AUTH ====================
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    
    # ==================== DASHBOARD ====================
    path('dashboard/', views.dashboard_view, name='dashboard'),
    
    # ==================== VENTAS (CRÍTICAS PARA MVP) ====================
    path('ventas/', views.ventas_lista, name='ventas_lista'),
    path('ventas/nuevo/<int:viaje_id>/', views.nueva_venta, name='venta_create'),
    path('ventas/mapa-asientos/<int:viaje_id>/', views.mapa_asientos, name='mapa_asientos'),
    path('ventas/procesar/', views.procesar_venta, name='procesar_venta'),
    
    # ==================== CLIENTES Y FIDELIZACIÓN (ANTI-FRAUDE) ====================
    path('clientes/historial/<str:dni>/', views.historial_cliente, name='cliente_historial'),
    path('clientes/fidelizacion/', views.fidelizacion_cliente, name='fidelizacion'),
    path('clientes/buscar/', views.buscar_cliente_view, name='buscar_cliente'),
    path('mi-perfil/', views.mi_perfil, name='mi_perfil'),
    
    # ==================== REPORTES BÁSICOS (CAJERO) ====================
    path('reportes/diario/', views.reporte_diario, name='reporte_diario'),
    path('reportes/semanal/', views.reporte_semanal, name='reporte_semanal'),
    path('reportes/mensual/', views.reporte_mensual, name='reporte_mensual'),
    
    # ==================== ADMIN - REPORTE CONSOLIDADO ====================
    path('admin/reporte-consolidado/', views.reporte_consolidado, name='reporte_consolidado'),

    # ==================== ADMIN - VISTAS ESPECÍFICAS ====================
    path('panel-admin/fidelizacion/', views.fidelizacion_admin, name='fidelizacion_admin'),
    path('panel-admin/reporte-diario/', views.reporte_diario_admin, name='reporte_diario_admin'),
    path('panel-admin/reporte-consolidado/', views.reporte_consolidado, name='reporte_consolidado'),

    # ==================== ADMIN - GESTIÓN DEL SISTEMA ====================
    path('panel-admin/vehiculos/', views.vehiculos_lista, name='vehiculos_lista'),
    path('panel-admin/vehiculos/nuevo/', views.vehiculo_nuevo, name='vehiculo_nuevo'),
    path('panel-admin/vehiculos/editar/<int:id>/', views.vehiculo_editar, name='vehiculo_editar'),
    path('panel-admin/vehiculos/eliminar/<int:id>/', views.vehiculo_eliminar, name='vehiculo_eliminar'),

    # Agrega esta línea en urlpatterns
    path('notificaciones/', views.notificaciones_lista, name='notificaciones_lista'),

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
    path('panel-admin/configuracion/', views.configuracion, name='configuracion'),
    
    # ==================== INCIDENCIAS (SIMPLE) ====================
    path('incidencias/', views.incidencias_lista, name='incidencias_lista'),

    
]