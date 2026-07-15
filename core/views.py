from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.db.models import Sum, Count, Q
from django.utils import timezone
from datetime import datetime, timedelta
import json

# ==================== AUTH ====================
def login_view(request):
    """Vista de login con selección de sede"""
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        sede = request.POST.get('sede')
        
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            request.session['sede_usuario'] = sede
            return redirect('core:dashboard')
        else:
            messages.error(request, 'Usuario o contraseña incorrectos')
    
    return render(request, 'login.html')

@login_required
def logout_view(request):
    """Cerrar sesión"""
    logout(request)
    return redirect('core:login')

# ==================== DASHBOARD ====================
@login_required
def dashboard_view(request):
    """Dashboard principal del cajero"""
    usuario = request.user
    sede = usuario.sede
    
    # Verificar si es admin
    if sede.nombre == 'central':
        return dashboard_admin(request, usuario, sede)
    else:
        return dashboard_cajero(request, usuario, sede)

def dashboard_cajero(request, usuario, sede):
    """Dashboard para cajeros"""
    hoy = timezone.now().date()
    
    # Datos hardcodeados (después serán consultas a BD)
    ventas_hoy = 15
    monto_total_hoy = 1540.00
    viajes_completados_hoy = 8
    
    proximos_viajes = [
        {
            'id': 1, 'hora_salida': '08:00', 'ruta': 'Trujillo → Julcán',
            'vehiculo': {'placa': 'ABC-123', 'modelo': 'Toyota Hiace'},
            'asientos_disponibles': 5, 'asientos_totales': 20,
            'estado': 'Disponible', 'porcentaje_ocupacion': 75
        },
        {
            'id': 2, 'hora_salida': '10:30', 'ruta': 'Trujillo → Mache',
            'vehiculo': {'placa': 'XYZ-789', 'modelo': 'Nissan Urvan'},
            'asientos_disponibles': 12, 'asientos_totales': 20,
            'estado': 'Disponible', 'porcentaje_ocupacion': 40
        },
    ]
    
    viajes_recientes = [
        {
            'fecha': '2026-07-14', 'hora': '08:00',
            'ruta_origen': 'Trujillo', 'ruta_destino': 'Julcán',
            'vehiculo': {'placa': 'ABC-123'},
            'asientos_ocupados': 18, 'ingreso': 450.00, 'estado': 'Completado'
        },
    ]
    
    # Cálculos
    asientos_disponibles_total = sum(v['asientos_disponibles'] for v in proximos_viajes)
    asientos_totales_total = sum(v['asientos_totales'] for v in proximos_viajes)
    porcentaje_disponibilidad = (asientos_disponibles_total / asientos_totales_total * 100) if asientos_totales_total > 0 else 0
    
    # Sistema de fidelización
    cliente_busqueda = request.GET.get('dni_cliente', '')
    alerta_fidelizacion = None
    
    if cliente_busqueda:
        # Simular búsqueda
        viajes_totales = 11
        viajes_restantes = 12 - (viajes_totales % 12)
        
        if viajes_restantes == 0:
            alerta_fidelizacion = {
                'tipo': 'success',
                'titulo': '¡CLIENTE GANADOR!',
                'mensaje': f'El cliente ha completado 12 viajes. Entregue Rasca y Gana.',
                'dni': cliente_busqueda
            }
        elif viajes_restantes == 1:
            alerta_fidelizacion = {
                'tipo': 'warning',
                'titulo': '⚠️ ¡CASI LO LOGRA!',
                'mensaje': f'Al cliente le falta 1 viaje para su Rasca y Gana.',
                'dni': cliente_busqueda
            }
    
    contexto = {
        'usuario': usuario, 'sede': sede,
        'ventas_hoy': ventas_hoy, 'monto_total_hoy': monto_total_hoy,
        'viajes_completados_hoy': viajes_completados_hoy,
        'proximos_viajes': proximos_viajes, 'viajes_recientes': viajes_recientes,
        'asientos_disponibles_total': asientos_disponibles_total,
        'asientos_totales_total': asientos_totales_total,
        'porcentaje_disponibilidad': porcentaje_disponibilidad,
        'alerta_fidelizacion': alerta_fidelizacion,
        'cliente_busqueda': cliente_busqueda
    }
    
    return render(request, 'dashboard/dashboard_cajero.html', contexto)

def dashboard_admin(request, usuario, sede):
    """Dashboard para admin"""
    contexto = {
        'usuario': usuario, 'sede': sede,
        'total_ventas': 15, 'total_monto': 1540.00
    }
    return render(request, 'dashboard/dashboard_admin.html', contexto)

# ==================== VENTAS ====================
@login_required
def ventas_lista(request):
    """Lista de ventas"""
    return render(request, 'ventas/lista.html')

@login_required
def nueva_venta(request, viaje_id):
    """Nueva venta - Selección de viaje"""
    viaje = {
        'id': viaje_id, 'hora_salida': '08:00',
        'ruta': 'Trujillo → Julcán', 'fecha': '2026-07-15',
        'vehiculo': {'placa': 'ABC-123', 'modelo': 'Toyota Hiace'},
        'precio_base': 25.00
    }
    return render(request, 'ventas/nuevo_viaje.html', {'viaje': viaje})

@login_required
def mapa_asientos(request, viaje_id):
    """Mapa de asientos"""
    return render(request, 'ventas/mapa_asientos.html')

@login_required
def procesar_venta(request):
    """Procesar venta"""
    if request.method == 'POST':
        messages.success(request, '✅ Venta registrada correctamente')
        return redirect('core:dashboard')
    return redirect('core:dashboard')

# ==================== CLIENTES ====================
@login_required
def historial_cliente(request, dni):
    """Historial de cliente por DNI"""
    cliente = {
        'dni': dni, 'nombre': 'Juan Pérez',
        'total_viajes': 11, 'proximo_premio_en': 1
    }
    return render(request, 'clientes/historial.html', {'cliente': cliente})

@login_required
def fidelizacion_cliente(request):
    """Vista de fidelización"""
    clientes_cercanos = [
        {'dni': '12345678', 'nombre': 'Juan Pérez', 'viajes': 11, 'faltan': 1},
        {'dni': '87654321', 'nombre': 'María López', 'viajes': 10, 'faltan': 2},
    ]
    contexto = {'clientes_cercanos': clientes_cercanos}
    return render(request, 'clientes/fidelizacion.html', contexto)

# ==================== REPORTES ====================
@login_required
def reporte_diario(request):
    """Reporte diario"""
    return render(request, 'reportes/diario.html')

@login_required
def reporte_semanal(request):
    """Reporte semanal"""
    return render(request, 'reportes/semanal.html')

@login_required
def reporte_mensual(request):
    """Reporte mensual"""
    return render(request, 'reportes/mensual.html')

# ==================== INCIDENCIAS ====================
@login_required
def incidencias_lista(request):
    """Lista de incidencias"""
    return render(request, 'incidencias/lista.html')