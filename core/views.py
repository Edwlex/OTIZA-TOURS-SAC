
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum, Q
from django.utils import timezone 
import json

# Configuración de sedes
CONFIG_SEDES = {
    'trujillo': {
        'nombre': 'Trujillo',
        'rutas': [
            {'valor': 'trujillo-julcan', 'etiqueta': 'Trujillo → Julcán'},
            {'valor': 'trujillo-mache', 'etiqueta': 'Trujillo → Mache'}
        ]
    },
    'julcan': {
        'nombre': 'Julcán',
        'rutas': [
            {'valor': 'julcan-trujillo', 'etiqueta': 'Julcán → Trujillo'},
            {'valor': 'julcan-mache', 'etiqueta': 'Julcán → Mache'}
        ]
    },
    'mache': {
        'nombre': 'Mache',
        'rutas': [
            {'valor': 'mache-trujillo', 'etiqueta': 'Mache → Trujillo'},
            {'valor': 'mache-julcan', 'etiqueta': 'Mache → Julcán'}
        ]
    },
    'central': {
        'nombre': 'Sede Central',
        'rutas': [
            {'valor': 'todas', 'etiqueta': 'Todas las Rutas'},
            {'valor': 'trujillo-julcan', 'etiqueta': 'Trujillo ↔ Julcán'},
            {'valor': 'trujillo-mache', 'etiqueta': 'Trujillo ↔ Mache'},
            {'valor': 'julcan-mache', 'etiqueta': 'Julcán ↔ Mache'}
        ]
    }
}

def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        sede = request.POST.get('sede')
        
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            # Guardar sede en sesión
            request.session['sede_usuario'] = sede
            return redirect('core:dashboard')
        else:
            messages.error(request, 'Usuario o contraseña incorrectos')
    
    return render(request, 'login.html')


@login_required
def dashboard_view(request):
    """
    Dashboard único que se adapta según el tipo de usuario:
    - Cajeros (sedes): ven solo datos de su sede
    - Admin (Sede Central): ve todo consolidado
    """
    usuario = request.user
    sede = usuario.sede
    
    # Verificar si es admin (Sede Central)
    es_admin = sede.nombre == 'central'
    
    if es_admin:
        return dashboard_admin(request, usuario, sede)
    else:
        return dashboard_cajero(request, usuario, sede)


def dashboard_cajero(request, usuario, sede):
    """
    Dashboard para cajeros de Trujillo, Julcán y Mache
    Incluye:
    - Resumen de ventas del día
    - Control de fidelización (rasca y gana)
    - Próximos viajes con asignación de combis
    - Búsqueda de historial de clientes
    """
    hoy = timezone.now().date()
    
    # ==================== DATOS DE EJEMPLO (HARDCODED POR AHORA) ====================
    # Después reemplazar con consultas reales a BD
    
    # Ventas del día
    ventas_hoy = 15
    monto_total_hoy = 1540.00
    viajes_completados_hoy = 8
    
    # Próximos viajes (asignación de combis)
    proximos_viajes = [
        {
            'id': 1,
            'hora_salida': '08:00',
            'ruta': 'Trujillo → Julcán',
            'vehiculo': {'placa': 'ABC-123', 'modelo': 'Toyota Hiace'},
            'asientos_disponibles': 5,
            'asientos_totales': 20,
            'estado': 'Disponible'
        },
        {
            'id': 2,
            'hora_salida': '10:30',
            'ruta': 'Trujillo → Mache',
            'vehiculo': {'placa': 'XYZ-789', 'modelo': 'Nissan Urvan'},
            'asientos_disponibles': 12,
            'asientos_totales': 20,
            'estado': 'Disponible'
        },
        {
            'id': 3,
            'hora_salida': '14:00',
            'ruta': 'Trujillo → Julcán',
            'vehiculo': {'placa': 'MNO-456', 'modelo': 'Hyundai H350'},
            'asientos_disponibles': 0,
            'asientos_totales': 20,
            'estado': 'Completo'
        }
    ]
    
    # Viajes recientes (para mostrar en tabla)
    viajes_recientes = [
        {
            'fecha': '2026-07-14',
            'hora': '08:00',
            'ruta_origen': 'Trujillo',
            'ruta_destino': 'Julcán',
            'vehiculo': {'placa': 'ABC-123', 'nombre': 'Combi 1'},
            'asientos_ocupados': 18,
            'ingreso': 450.00,
            'estado': 'Completado'
        },
        {
            'fecha': '2026-07-14',
            'hora': '10:30',
            'ruta_origen': 'Trujillo',
            'ruta_destino': 'Mache',
            'vehiculo': {'placa': 'XYZ-789', 'nombre': 'Combi 2'},
            'asientos_ocupados': 15,
            'ingreso': 375.00,
            'estado': 'En Ruta'
        }
    ]
    
    # ==================== SISTEMA DE FIDELIZACIÓN ====================
    # Ejemplo: Cliente busca su historial
    cliente_busqueda = request.GET.get('dni_cliente', '')
    alerta_fidelizacion = None
    
    if cliente_busqueda:
        # Simular búsqueda de cliente (después será consulta a BD)
        cliente_ejemplo = {
            'dni': '12345678',
            'nombre': 'Juan Pérez',
            'viajes_totales': 11,  # ← Le falta 1 para el rasca y gana
            'ultimo_viaje': '2026-07-10'
        }
        
        viajes_restantes = 12 - (cliente_ejemplo['viajes_totales'] % 12)
        
        if viajes_restantes == 0:
            # ¡GANÓ! Ya completó 12 viajes
            alerta_fidelizacion = {
                'tipo': 'success',
                'titulo': '🎉 ¡CLIENTE GANADOR!',
                'mensaje': f"{cliente_ejemplo['nombre']} ha completado 12 viajes. Entregue Rasca y Gana.",
                'dni': cliente_ejemplo['dni'],
                'viajes_completados': 12
            }
        elif viajes_restantes == 1:
            # Le falta 1 viaje
            alerta_fidelizacion = {
                'tipo': 'warning',
                'titulo': '⚠️ ¡CASI LO LOGRA!',
                'mensaje': f"A {cliente_ejemplo['nombre']} le falta 1 viaje para su Rasca y Gana.",
                'dni': cliente_ejemplo['dni'],
                'viajes_actuales': cliente_ejemplo['viajes_totales'],
                'viajes_restantes': 1
            }
        else:
            # Información normal
            alerta_fidelizacion = {
                'tipo': 'info',
                'titulo': '📊 Historial del Cliente',
                'mensaje': f"{cliente_ejemplo['nombre']} tiene {cliente_ejemplo['viajes_totales']} viajes. Le faltan {viajes_restantes} para Rasca y Gana.",
                'dni': cliente_ejemplo['dni'],
                'viajes_actuales': cliente_ejemplo['viajes_totales'],
                'viajes_restantes': viajes_restantes
            }
    
    # ==================== CONTEXTO PARA TEMPLATE ====================
    contexto = {
        # Info del usuario
        'usuario': usuario,
        'sede': sede,
        'es_cajero': True,
        'es_admin': False,
        
        # Resumen del día
        'ventas_hoy': ventas_hoy,
        'monto_total_hoy': monto_total_hoy,
        'viajes_completados_hoy': viajes_completados_hoy,
        
        # Próximos viajes (con asignación de combis)
        'proximos_viajes': proximos_viajes,
        
        # Viajes recientes
        'viajes_recientes': viajes_recientes,
        
        # Fidelización
        'alerta_fidelizacion': alerta_fidelizacion,
        'cliente_busqueda': cliente_busqueda,
        
        # Filtros disponibles
        'rutas_disponibles': [
            {'valor': 'trujillo-julcan', 'etiqueta': 'Trujillo → Julcán'},
            {'valor': 'trujillo-mache', 'etiqueta': 'Trujillo → Mache'},
            {'valor': 'julcan-mache', 'etiqueta': 'Julcán → Mache'},
        ]
    }
    
    return render(request, 'dashboard/dashboard_cajero.html', contexto)


def dashboard_admin(request, usuario, sede):
    """
    Dashboard para el Dueño (Sede Central)
    Ve TODO consolidado de las 3 sedes
    """
    hoy = timezone.now().date()
    
    # ==================== DATOS DE EJEMPLO ====================
    # Resumen consolidado de las 3 sedes
    resumen_sedes = [
        {'sede': 'Trujillo', 'ventas_hoy': 8, 'monto': 850.00, 'viajes': 5},
        {'sede': 'Julcán', 'ventas_hoy': 4, 'monto': 420.00, 'viajes': 2},
        {'sede': 'Mache', 'ventas_hoy': 3, 'monto': 270.00, 'viajes': 1},
    ]
    
    total_ventas = sum(s['ventas_hoy'] for s in resumen_sedes)
    total_monto = sum(s['monto'] for s in resumen_sedes)
    total_viajes = sum(s['viajes'] for s in resumen_sedes)
    
    # Incidencias/reportes de las sedes
    incidencias = [
        {'sede': 'Trujillo', 'tipo': 'Reclamo', 'descripcion': 'Retraso en salida', 'fecha': '2026-07-14', 'estado': 'Pendiente'},
        {'sede': 'Julcán', 'tipo': 'Sugerencia', 'descripcion': 'Mejorar aire acondicionado', 'fecha': '2026-07-13', 'estado': 'Atendida'},
    ]
    
    contexto = {
        'usuario': usuario,
        'sede': sede,
        'es_cajero': False,
        'es_admin': True,
        
        # Totales consolidados
        'total_ventas': total_ventas,
        'total_monto': total_monto,
        'total_viajes': total_viajes,
        
        # Resumen por sede
        'resumen_sedes': resumen_sedes,
        
        # Incidencias
        'incidencias': incidencias,
    }
    
    return render(request, 'dashboard/dashboard_admin.html', contexto)


@login_required
def logout_view(request):
    logout(request)
    return redirect('core:login') 