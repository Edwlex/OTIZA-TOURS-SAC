from django.urls import path
from django.views.generic import RedirectView
from . import views

app_name = 'core'

urlpatterns = [
    # Redirect raíz
    path('', RedirectView.as_view(url='/login/', permanent=False)),
    
    # Auth
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    
    # Dashboard
    path('dashboard/', views.dashboard_view, name='dashboard'),
    
    # Ventas
    path('ventas/', views.ventas_lista, name='ventas_lista'),
    path('ventas/nuevo/<int:viaje_id>/', views.nueva_venta, name='venta_create'),
    path('ventas/mapa-asientos/<int:viaje_id>/', views.mapa_asientos, name='mapa_asientos'),
    path('ventas/procesar/', views.procesar_venta, name='procesar_venta'),
    
    # Clientes
    path('clientes/historial/<str:dni>/', views.historial_cliente, name='cliente_historial'),
    path('clientes/fidelizacion/', views.fidelizacion_cliente, name='fidelizacion'),
    
    # Reportes
    path('reportes/diario/', views.reporte_diario, name='reporte_diario'),
    path('reportes/semanal/', views.reporte_semanal, name='reporte_semanal'),
    path('reportes/mensual/', views.reporte_mensual, name='reporte_mensual'),
    
    # Incidencias
    path('incidencias/', views.incidencias_lista, name='incidencias_lista'),
]