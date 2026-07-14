from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    # Auth
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    
    # Dashboard (se adapta según el usuario)
    path('dashboard/', views.dashboard_view, name='dashboard'),
    
    # 🔹 VENTAS - COMENTAR HASTA QUE EXISTA LA VISTA
    # path('ventas/nuevo/<int:viaje_id>/', views.nueva_venta, name='venta_create'),
    
    # 🔹 CLIENTES - COMENTAR HASTA QUE EXISTA LA VISTA
    # path('clientes/historial/<str:dni>/', views.historial_cliente, name='cliente_historial'),
    
    # 🔹 REPORTES - COMENTAR HASTA QUE EXISTA LA VISTA
    # path('reportes/diario/', views.reporte_diario, name='reporte_diario'),
    # path('reportes/semanal/', views.reporte_semanal, name='reporte_semanal'),
    # path('reportes/mensual/', views.reporte_mensual, name='reporte_mensual'),
]