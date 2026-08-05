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
    path('ventas/exportar/', views.ventas_exportar, name='ventas_exportar'),
    path('ventas/confirmar-pago-reserva/<int:asiento_id>/', views.confirmar_pago_reserva, name='confirmar_pago_reserva'),
    path('ventas/liberar-reserva/<int:asiento_id>/', views.liberar_reserva, name='liberar_reserva'),
    
    path('boletos/<int:boleto_id>/pdf/', views.descargar_boleto_pdf, name='descargar_boleto_pdf'),
    path('boletos/<int:boleto_id>/', views.ver_boleto, name='ver_boleto'),  
    # Debe coincidir EXACTAMENTE con el nombre en el template


    # ==================== CLIENTES Y FIDELIZACIÓN ====================
    path('clientes/historial/<str:dni>/', views.historial_cliente, name='cliente_historial'),
    path('clientes/fidelizacion/', views.fidelizacion_cliente, name='fidelizacion'),
    path('clientes/buscar/', views.buscar_cliente, name='buscar_cliente'),

    # ==================== REPORTES ====================
    path('reportes/', views.reportes_unificados, name='reportes_unificados'),
    
    # ==================== NOTIFICACIONES ====================
    path('notificaciones/', views.notificaciones_lista, name='notificaciones_lista'),
    path('notificaciones/<int:notif_id>/leer/', views.marcar_notificacion_leida, name='marcar_notificacion_leida'),
    path('notificaciones/todas-leer/', views.marcar_todas_leidas, name='marcar_todas_leidas'),
    path('notificaciones/api/contador/', views.notificaciones_contador_api, name='notificaciones_contador_api'),

    # ==================== PERFIL ====================
    path('perfil/', views.mi_perfil, name='mi_perfil'),
    
    # ==================== ADMIN - FIDELIZACIÓN ====================
    path('panel-admin/fidelizacion/', views.fidelizacion_admin, name='fidelizacion_admin'),
    
    # ==================== ADMIN - VEHÍCULOS ====================
    path('panel-admin/vehiculos/', views.vehiculos_lista, name='vehiculos_lista'),
    path('panel-admin/vehiculos/nuevo/', views.vehiculo_nuevo, name='vehiculo_nuevo'),
    path('panel-admin/vehiculos/editar/<int:id>/', views.vehiculo_editar, name='vehiculo_editar'),
    path('panel-admin/vehiculos/eliminar/<int:id>/', views.vehiculo_eliminar, name='vehiculo_eliminar'),


    # ==================== INCIDENCIAS ====================
    path('incidencias/', views.incidencias_lista, name='incidencias_lista'),
    path('incidencias/nuevo/', views.incidencia_nuevo, name='incidencia_nuevo'), # ← ESTA ES LA ÚNICA QUE NECESITAS
    path('incidencias/actualizar/<int:id>/', views.incidencia_actualizar_estado, name='incidencia_actualizar_estado'),
    path('incidencias/detalle/<int:id>/', views.incidencia_ver_detalle, name='incidencia_ver_detalle'),
    path('incidencias/<int:incidencia_id>/eliminar/', views.incidencia_eliminar, name='incidencia_eliminar'),

    # ==================== ADMIN - GESTIÓN DE CHOFERES ====================
    path('panel-admin/choferes/', views.choferes_lista, name='choferes_lista'),
    path('panel-admin/choferes/nuevo/', views.chofer_nuevo, name='chofer_nuevo'),
    path('panel-admin/choferes/editar/<int:id>/', views.chofer_editar, name='chofer_editar'),
    path('panel-admin/choferes/eliminar/<int:id>/', views.chofer_eliminar, name='chofer_eliminar'),

    # ==================== ADMIN - GESTIÓN DE RUTAS ====================
    path('panel-admin/rutas/', views.rutas_lista, name='rutas_lista'),
    path('panel-admin/rutas/nuevo/', views.ruta_nuevo, name='ruta_nuevo'),
    path('panel-admin/rutas/editar/<int:id>/', views.ruta_editar, name='ruta_editar'),
    path('panel-admin/rutas/eliminar/<int:id>/', views.ruta_eliminar, name='ruta_eliminar'),

    # ==================== ADMIN - ASIGNACIÓN DE VIAJES ====================
    path('panel-admin/asignacion-viajes/', views.asignacion_viajes, name='asignacion_viajes'),
    path('panel-admin/viajes/nuevo/', views.viaje_nuevo, name='viaje_nuevo'),
    path('panel-admin/viajes/editar/<int:id>/', views.viaje_editar, name='viaje_editar'),
    path('panel-admin/viajes/eliminar/<int:id>/', views.viaje_eliminar, name='viaje_eliminar'),
    path('panel-admin/viajes/generar-proximos-7-dias/', views.generar_proximos_7_dias, name='generar_proximos_7_dias'),
    path('panel-admin/viajes/<int:viaje_id>/crear-regreso/', 
     views.crear_viaje_regreso, 
     name='crear_viaje_regreso'),

    # Agrega esta línea en urls.py
    path('ventas/procesar-reserva/', views.procesar_reserva, name='procesar_reserva'),
    path('ventas/procesar-reserva/<int:asiento_id>/', views.procesar_reserva_pago, name='procesar_reserva_pago'),
    path('ventas/liberar-reserva/<int:asiento_id>/', views.liberar_reserva, name='liberar_reserva'),
    path('ventas/confirmacion/<int:venta_id>/', views.confirmacion_venta, name='confirmacion_venta'),
    path('ventas/confirmar-pago-reserva-chofer/<int:asiento_id>/', views.confirmar_pago_reserva_chofer, name='confirmar_pago_reserva_chofer'),


    path('panel-admin/horarios-fijos/', views.horarios_fijos_lista, name='horarios_fijos_lista'),
    path('panel-admin/horarios-fijos/eliminar/<int:id>/', views.horario_fijo_eliminar, name='horario_fijo_eliminar'),
    path('panel-admin/horarios-fijos/editar/<int:id>/', views.horario_fijo_editar, name='horario_fijo_editar'),

    # ==================== ADMIN - GESTIÓN DE USUARIOS ====================
    path('panel-admin/usuarios/', views.usuarios_lista, name='usuarios_lista'),
    path('panel-admin/usuarios/nuevo/', views.usuario_nuevo, name='usuario_nuevo'),
    path('panel-admin/usuarios/editar/<int:id>/', views.usuario_editar, name='usuario_editar'),
    path('panel-admin/usuarios/eliminar/<int:id>/', views.usuario_eliminar, name='usuario_eliminar'),

    
    # ==================== INCIDENCIAS ====================
    path('incidencias/', views.incidencias_lista, name='incidencias_lista'),

        # ==================== DOCUMENTOS (HOJA DE RUTA Y MANIFIESTO) ====================
    path('documentos/hoja-ruta/nuevo/', views.hoja_ruta_nuevo, name='hoja_ruta_nuevo'),
    path('documentos/hoja-ruta/<int:id>/pdf/', views.hoja_ruta_pdf, name='hoja_ruta_pdf'),
    path('documentos/hoja-ruta/generar/<int:viaje_id>/', views.hoja_ruta_generar, name='hoja_ruta_generar'),


        # ==================== DOCUMENTOS: MANIFIESTOS ====================
    path('manifiestos/', views.manifiestos_lista, name='manifiestos_lista'),
    path('manifiestos/viajes-disponibles/', views.viajes_disponibles_manifiesto, name='viajes_disponibles_manifiesto'),
    path('manifiestos/generar/<int:viaje_id>/', views.manifiesto_generar, name='manifiesto_generar'),
    path('manifiestos/<int:id>/pdf/', views.manifiesto_pdf, name='manifiesto_pdf'),
    path('manifiestos/limpiar-sesion/', views.manifiesto_limpiar_sesion, name='manifiesto_limpiar_sesion'),
    path('manifiestos/<int:manifiesto_id>/eliminar/', views.manifiesto_eliminar, name='manifiesto_eliminar'),

    # Hoja de Ruta
    path('documentos/hoja-ruta/', views.hoja_ruta_lista, name='hoja_ruta_lista'),
    path('documentos/hoja-ruta/nuevo/', views.hoja_ruta_nuevo, name='hoja_ruta_nuevo'),
    path('documentos/hoja-ruta/generar/<int:viaje_id>/', views.hoja_ruta_generar, name='hoja_ruta_generar'),
    path('documentos/hoja-ruta/<int:id>/pdf/', views.hoja_ruta_pdf, name='hoja_ruta_pdf'),
    path('documentos/hoja-ruta/historial/', views.hoja_ruta_historial, name='hoja_ruta_historial'),
    path('documentos/hoja-ruta/limpiar-sesion/', views.hoja_ruta_limpiar_sesion, name='hoja_ruta_limpiar_sesion'),
    path('documentos/hoja-ruta/<int:hoja_id>/eliminar/', views.hoja_ruta_eliminar, name='hoja_ruta_eliminar'),



    # ==================== PORTAL CHOFERES ====================
    path('chofer/login/', views.login_chofer_view, name='login_chofer'),
    path('chofer/seleccionar-identidad/', views.chofer_seleccionar_identidad, name='chofer_seleccionar_identidad'),
    path('chofer/panel/', views.panel_chofer, name='panel_chofer'),
    path('chofer/reservar/<int:viaje_id>/', views.chofer_reservar_asientos, name='chofer_reservar_asientos'),
    path('chofer/logout/', views.chofer_logout, name='chofer_logout'),
    path('chofer/incidencias/', views.chofer_incidencias, name='chofer_incidencias'),
    path('chofer/incidencias/nueva/', views.chofer_nueva_incidencia, name='chofer_nueva_incidencia'),
]