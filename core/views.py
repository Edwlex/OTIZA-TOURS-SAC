import io
import json
from datetime import datetime, timedelta

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q, Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.utils import timezone
from xhtml2pdf import pisa



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
    """Dashboard único que se adapta según el usuario"""
    usuario = request.user
    sede = usuario.sede

    if sede.nombre == 'central':
        return dashboard_admin_simple(request, usuario, sede)
    else:
        return dashboard_cajero(request, usuario, sede)


def dashboard_cajero(request, usuario, sede):
    """Dashboard para cajeros de Trujillo, Julcán y Mache"""
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
        viajes_totales = 11  # Simulado
        viajes_restantes = 12 - (viajes_totales % 12)

        if viajes_restantes == 0:
            alerta_fidelizacion = {
                'tipo': 'success',
                'titulo': '🎉 ¡CLIENTE GANADOR!',
                'mensaje': 'Ha completado 12 viajes. Entregue Rasca y Gana.',
                'dni': cliente_busqueda
            }
        elif viajes_restantes == 1:
            alerta_fidelizacion = {
                'tipo': 'warning',
                'titulo': '⚠️ ¡CASI LO LOGRA!',
                'mensaje': 'Le falta 1 viaje para su Rasca y Gana.',
                'dni': cliente_busqueda
            }

    contexto = {
        'usuario': usuario, 'sede': sede, 'es_admin': False,
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


@login_required 
def dashboard_admin_simple(request, usuario, sede):
    """
    Dashboard COMPLETO con filtros, KPIs, gráficos, tops y tabla detallada
    """
    hoy = timezone.now().date()

    # Obtener filtros
    periodo = request.GET.get('periodo', 'hoy')
    sede_filtro = request.GET.get('sede', '')
    fecha_desde = request.GET.get('fecha_desde', '')
    fecha_hasta = request.GET.get('fecha_hasta', '')

    contexto = {
        'usuario': usuario,
        'sede': sede,
        'es_admin': True,
        'fecha': hoy,
        'periodo': periodo,
        'sede_filtro': sede_filtro,
        'fecha_desde': fecha_desde,
        'fecha_hasta': fecha_hasta,

        # KPIs del Día
        'ingresos_totales': 4580.00,
        'total_ventas': 45,
        'total_pasajeros': 1247,
        'total_viajes': 12,
        'ocupacion_promedio': 78,

        # Gráfico de Tendencia
        'dias_semana': ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Hoy'],
        'ventas_por_dia': [8500, 9200, 10100, 9800, 11200, 13500, 4580],

        # Ingresos por Sede
        'sedes': ['Trujillo', 'Julcán', 'Mache'],
        'ingresos_por_sede': [2540, 1320, 720],

        # Resumen por Sede
        'resumen_por_sede': [
            {'nombre': 'Trujillo', 'ventas': 25, 'monto': 2540.00, 'porcentaje': 55},
            {'nombre': 'Julcán', 'ventas': 12, 'monto': 1320.00, 'porcentaje': 29},
            {'nombre': 'Mache', 'ventas': 8, 'monto': 720.00, 'porcentaje': 16},
        ],

        # Top 3 Rutas
        'top_rutas': [
            {'ruta': 'Trujillo → Julcán', 'ventas': 8, 'ingresos': 2400.00},
            {'ruta': 'Trujillo → Mache', 'ventas': 6, 'ingresos': 1800.00},
            {'ruta': 'Julcán → Trujillo', 'ventas': 5, 'ingresos': 1250.00},
        ],

        # Vehículos Activos
        'vehiculos_activos': [
            {'placa': 'ABC-123', 'chofer': 'Juan Pérez', 'estado': 'En ruta'},
            {'placa': 'XYZ-789', 'chofer': 'María López', 'estado': 'En terminal'},
            {'placa': 'DEF-456', 'chofer': 'Carlos Ruiz', 'estado': 'En ruta'},
        ],

        # Detalle de Ventas (TABLA COMPLETA)
        'detalle_ventas': [
            {'fecha': '2026-07-17', 'hora': '08:00', 'sede': 'Trujillo', 'ruta': 'Trujillo → Julcán', 
             'vehiculo': 'ABC-123', 'chofer': 'Juan Pérez', 'pasajeros': 18, 'ingreso': 450.00},
            {'fecha': '2026-07-17', 'hora': '10:30', 'sede': 'Trujillo', 'ruta': 'Trujillo → Mache', 
             'vehiculo': 'XYZ-789', 'chofer': 'María López', 'pasajeros': 12, 'ingreso': 360.00},
            {'fecha': '2026-07-17', 'hora': '14:00', 'sede': 'Julcán', 'ruta': 'Julcán → Trujillo', 
             'vehiculo': 'DEF-456', 'chofer': 'Carlos Ruiz', 'pasajeros': 15, 'ingreso': 375.00},
            {'fecha': '2026-07-17', 'hora': '16:30', 'sede': 'Mache', 'ruta': 'Mache → Trujillo', 
             'vehiculo': 'GHI-321', 'chofer': 'Luis Martínez', 'pasajeros': 10, 'ingreso': 300.00},
        ],

        # Incidencias
        'incidencias_pendientes': [
            {'sede': 'Trujillo', 'descripcion': 'Retraso en salida 08:00', 'fecha': hoy},
            {'sede': 'Mache', 'descripcion': 'Cliente sin cambio', 'fecha': hoy},
        ],
    }

    return render(request, 'dashboard/dashboard_admin_simple.html', contexto)


# ==================== VENTAS (CRÍTICAS PARA MVP) ====================
@login_required
def ventas_lista(request):
    """Lista de ventas - Adaptable para admin y cajero"""
    usuario = request.user
    sede = usuario.sede

    if sede.nombre == 'central':
        return ventas_lista_admin(request, usuario, sede)
    else:
        return ventas_lista_cajero(request, usuario, sede)


def ventas_lista_admin(request, usuario, sede):
    """Lista de ventas para ADMIN (vista consolidada)"""
    contexto = {
        'usuario': usuario,
        'sede': sede,
        'es_admin': True,
        'ventas': [
            {'id': 1, 'fecha': '2026-07-17', 'hora': '08:00', 'sede': 'Trujillo', 
             'ruta': 'Trujillo → Julcán', 'vehiculo': 'ABC-123', 'chofer': 'Juan Pérez', 
             'pasajeros': 18, 'ingreso': 450.00, 'estado': 'Completado'},
            {'id': 2, 'fecha': '2026-07-17', 'hora': '10:30', 'sede': 'Trujillo', 
             'ruta': 'Trujillo → Mache', 'vehiculo': 'XYZ-789', 'chofer': 'María López', 
             'pasajeros': 12, 'ingreso': 360.00, 'estado': 'Completado'},
            {'id': 3, 'fecha': '2026-07-17', 'hora': '14:00', 'sede': 'Julcán', 
             'ruta': 'Julcán → Trujillo', 'vehiculo': 'DEF-456', 'chofer': 'Carlos Ruiz', 
             'pasajeros': 15, 'ingreso': 375.00, 'estado': 'Completado'},
            {'id': 4, 'fecha': '2026-07-17', 'hora': '16:30', 'sede': 'Mache', 
             'ruta': 'Mache → Trujillo', 'vehiculo': 'GHI-321', 'chofer': 'Luis Martínez', 
             'pasajeros': 10, 'ingreso': 300.00, 'estado': 'Completado'},
        ],
        'total_ventas': 45,
        'total_ingresos': 4580.00,
    }
    return render(request, 'admin/ventas_lista.html', contexto)


def ventas_lista_cajero(request, usuario, sede):
    """Lista de ventas para CAJERO (vista por sede)"""
    return render(request, 'ventas/lista.html')


@login_required
def nueva_venta(request, viaje_id):
    """Paso 1: Mapa de asientos"""
    viaje = {
        'id': viaje_id, 
        'hora_salida': '08:00',
        'ruta': 'Trujillo → Julcán', 
        'fecha': '2026-07-15',
        'vehiculo': {'placa': 'ABC-123', 'modelo': 'Toyota Hiace'},
        'precio_base': 25.00,
        'chofer': 'Juan Pérez'
    }
    return render(request, 'ventas/mapa_asientos.html', {'viaje': viaje})

@login_required
def mapa_asientos(request, viaje_id):
    """Paso 2: Mapa interactivo de asientos"""
    return render(request, 'ventas/mapa_asientos.html')

@login_required
def procesar_venta(request):
    """Paso 3: Procesar venta y generar ticket"""
    if request.method == 'POST':
        messages.success(request, '✅ Venta registrada correctamente')
        return redirect('core:dashboard')
    return redirect('core:dashboard')


# ==================== CLIENTES Y FIDELIZACIÓN ====================
@login_required
def historial_cliente(request, dni):
    """Historial de viajes de un cliente por DNI"""
    cliente = {
        'dni': dni, 'nombre': 'Juan Pérez',
        'total_viajes': 11, 'proximo_premio_en': 1
    }
    return render(request, 'clientes/historial.html', {'cliente': cliente})

@login_required
def fidelizacion_cliente(request):
    """Vista de fidelización: clientes cercanos a completar 12 viajes"""
    clientes_cercanos = [
        {'dni': '12345678', 'nombre': 'Juan Pérez', 'viajes': 11, 'faltan': 1},
        {'dni': '87654321', 'nombre': 'María López', 'viajes': 10, 'faltan': 2},
    ]
    return render(request, 'clientes/fidelizacion.html', {'clientes_cercanos': clientes_cercanos})

@login_required
def buscar_cliente_view(request):
    """Vista para la página de buscar cliente"""
    contexto = {
        'cliente_busqueda': request.GET.get('dni_cliente', ''),
    }
    return render(request, 'clientes/buscar.html', contexto)


# ==================== INCIDENCIAS ====================
@login_required
def incidencias_lista(request):
    """Lista de incidencias - Adaptable para admin y cajero"""
    usuario = request.user
    sede = usuario.sede

    if sede.nombre == 'central':
        return incidencias_lista_admin(request, usuario, sede)
    else:
        return incidencias_lista_cajero(request, usuario, sede)


def incidencias_lista_admin(request, usuario, sede):
    """Lista de incidencias para ADMIN (todas las sedes)"""
    estado_filtro = request.GET.get('estado', '')
    sede_filtro = request.GET.get('sede', '')

    contexto = {
        'usuario': usuario,
        'sede': sede,
        'es_admin': True,
        'estado_filtro': estado_filtro,
        'sede_filtro': sede_filtro,
        'total_incidencias': 12,
        'pendientes': 5,
        'en_proceso': 3,
        'resueltas': 4,
        'incidencias': [
            {
                'id': 1, 'fecha': '2026-07-17', 'hora': '08:15', 'sede': 'Trujillo',
                'tipo': 'Retraso', 'descripcion': 'Retraso en salida 08:00 - Vehículo ABC-123',
                'prioridad': 'Alta', 'estado': 'Pendiente', 'reportado_por': 'Juan Pérez',
                'fecha_resolucion': None
            },
            {
                'id': 2, 'fecha': '2026-07-17', 'hora': '09:30', 'sede': 'Mache',
                'tipo': 'Cliente', 'descripcion': 'Cliente sin cambio - No pudo pagar pasaje',
                'prioridad': 'Media', 'estado': 'En Proceso', 'reportado_por': 'Carlos Ruiz',
                'fecha_resolucion': None
            },
            {
                'id': 3, 'fecha': '2026-07-16', 'hora': '14:20', 'sede': 'Julcán',
                'tipo': 'Vehículo', 'descripcion': 'Falla mecánica menor - Vehículo XYZ-789',
                'prioridad': 'Alta', 'estado': 'Resuelta', 'reportado_por': 'María López',
                'fecha_resolucion': '2026-07-16 16:00'
            },
        ],
    }
    return render(request, 'admin/incidencias_lista.html', contexto)


def incidencias_lista_cajero(request, usuario, sede):
    """Lista de incidencias para CAJERO (solo su sede)"""
    contexto = {
        'usuario': usuario,
        'sede': sede,
        'es_admin': False,
        'incidencias': [],
    }
    return render(request, 'incidencias/lista.html')


# ==================== ADMIN - VISTAS ESPECÍFICAS ====================
@login_required
def fidelizacion_admin(request):
    """Vista de fidelización para Admin"""
    clientes_cercanos = [
        {'dni': '12345678', 'nombre': 'Juan Pérez', 'viajes': 11, 'faltan': 1, 'sede': 'Trujillo'},
        {'dni': '87654321', 'nombre': 'María López', 'viajes': 10, 'faltan': 2, 'sede': 'Julcán'},
        {'dni': '45678912', 'nombre': 'Carlos Ruiz', 'viajes': 11, 'faltan': 1, 'sede': 'Mache'},
    ]
    contexto = {
        'usuario': request.user,
        'sede': request.user.sede,
        'es_admin': True,
        'clientes_cercanos': clientes_cercanos,
        'total_clientes': 142,
        'premios_pendientes': 8,
        'premios_entregados_mes': 24
    }
    return render(request, 'admin/fidelizacion.html', contexto)


# ==================== ADMIN - GESTIÓN DE VEHÍCULOS ====================
@login_required
def vehiculos_lista(request):
    """Lista de vehículos del sistema"""
    vehiculos = [
        {'id': 1, 'placa': 'ABC-123', 'modelo': 'Toyota Hiace', 'año': 2022, 'asientos': 20, 'estado': 'Activo'},
        {'id': 2, 'placa': 'XYZ-789', 'modelo': 'Nissan Urvan', 'año': 2021, 'asientos': 20, 'estado': 'Activo'},
        {'id': 3, 'placa': 'DEF-456', 'modelo': 'Toyota Coaster', 'año': 2020, 'asientos': 25, 'estado': 'Mantenimiento'},
        {'id': 4, 'placa': 'GHI-321', 'modelo': 'Mercedes Sprinter', 'año': 2023, 'asientos': 18, 'estado': 'Activo'},
    ]
    contexto = {
        'usuario': request.user,
        'sede': request.user.sede,
        'es_admin': True,
        'vehiculos': vehiculos,
        'total_vehiculos': len(vehiculos),
        'activos': sum(1 for v in vehiculos if v['estado'] == 'Activo'),
    }
    return render(request, 'admin/vehiculos.html', contexto)

@login_required
def vehiculo_nuevo(request):
    """Crear nuevo vehículo"""
    if request.method == 'POST':
        messages.success(request, 'Vehículo registrado correctamente')
        return redirect('core:vehiculos_lista')
    return render(request, 'admin/vehiculo_form.html')

@login_required
def vehiculo_editar(request, id):
    """Editar vehículo"""
    if request.method == 'POST':
        messages.success(request, 'Vehículo actualizado correctamente')
        return redirect('core:vehiculos_lista')
    return render(request, 'admin/vehiculo_form.html')

@login_required
def vehiculo_eliminar(request, id):
    """Eliminar vehículo"""
    messages.success(request, 'Vehículo eliminado correctamente')
    return redirect('core:vehiculos_lista')


# ==================== ADMIN - GESTIÓN DE CHOFERES ====================
@login_required
def choferes_lista(request):
    """Lista de choferes del sistema"""
    choferes = [
        {'id': 1, 'nombre': 'Juan Pérez', 'dni': '12345678', 'licencia': 'A1-234567', 'telefono': '987654321', 'estado': 'Activo'},
        {'id': 2, 'nombre': 'María López', 'dni': '87654321', 'licencia': 'A1-765432', 'telefono': '987123456', 'estado': 'Activo'},
        {'id': 3, 'nombre': 'Carlos Ruiz', 'dni': '45678912', 'licencia': 'A1-456789', 'telefono': '987456123', 'estado': 'Vacaciones'},
    ]
    contexto = {
        'usuario': request.user,
        'sede': request.user.sede,
        'es_admin': True,
        'choferes': choferes,
        'total_choferes': len(choferes),
    }
    return render(request, 'admin/choferes.html', contexto)

@login_required
def chofer_nuevo(request):
    """Crear nuevo chofer"""
    if request.method == 'POST':
        messages.success(request, 'Chofer registrado correctamente')
        return redirect('core:choferes_lista')
    return render(request, 'admin/chofer_form.html')

@login_required
def chofer_editar(request, id):
    """Editar chofer"""
    if request.method == 'POST':
        messages.success(request, 'Chofer actualizado correctamente')
        return redirect('core:choferes_lista')
    return render(request, 'admin/chofer_form.html')

@login_required
def chofer_eliminar(request, id):
    """Eliminar chofer"""
    messages.success(request, 'Chofer eliminado correctamente')
    return redirect('core:choferes_lista')


# ==================== ADMIN - GESTIÓN DE RUTAS ====================
@login_required
def rutas_lista(request):
    """Lista de rutas del sistema"""
    rutas = [
        {'id': 1, 'origen': 'Trujillo', 'destino': 'Julcán', 'distancia': '85 km', 'duracion': '2h 30min', 'precio_base': 25.00},
        {'id': 2, 'origen': 'Trujillo', 'destino': 'Mache', 'distancia': '120 km', 'duracion': '3h 15min', 'precio_base': 30.00},
        {'id': 3, 'origen': 'Julcán', 'destino': 'Trujillo', 'distancia': '85 km', 'duracion': '2h 30min', 'precio_base': 25.00},
        {'id': 4, 'origen': 'Mache', 'destino': 'Trujillo', 'distancia': '120 km', 'duracion': '3h 15min', 'precio_base': 30.00},
    ]
    contexto = {
        'usuario': request.user,
        'sede': request.user.sede,
        'es_admin': True,
        'rutas': rutas,
        'total_rutas': len(rutas),
    }
    return render(request, 'admin/rutas.html', contexto)

@login_required
def ruta_nuevo(request):
    """Crear nueva ruta"""
    if request.method == 'POST':
        messages.success(request, 'Ruta registrada correctamente')
        return redirect('core:rutas_lista')
    return render(request, 'admin/ruta_form.html')

@login_required
def ruta_editar(request, id):
    """Editar ruta"""
    if request.method == 'POST':
        messages.success(request, 'Ruta actualizada correctamente')
        return redirect('core:rutas_lista')
    return render(request, 'admin/ruta_form.html')

@login_required
def ruta_eliminar(request, id):
    """Eliminar ruta"""
    messages.success(request, 'Ruta eliminada correctamente')
    return redirect('core:rutas_lista')


# ==================== ADMIN - ASIGNACIÓN DE VIAJES ====================
@login_required
def asignacion_viajes(request):
    """Programación y asignación de viajes"""
    viajes_programados = [
        {'id': 1, 'fecha': '2026-07-17', 'hora': '08:00', 'ruta': 'Trujillo → Julcán', 'vehiculo': 'ABC-123', 'chofer': 'Juan Pérez', 'asientos_disponibles': 12, 'estado': 'Programado'},
        {'id': 2, 'fecha': '2026-07-17', 'hora': '10:30', 'ruta': 'Trujillo → Mache', 'vehiculo': 'XYZ-789', 'chofer': 'María López', 'asientos_disponibles': 8, 'estado': 'Programado'},
        {'id': 3, 'fecha': '2026-07-17', 'hora': '14:00', 'ruta': 'Julcán → Trujillo', 'vehiculo': 'DEF-456', 'chofer': 'Carlos Ruiz', 'asientos_disponibles': 0, 'estado': 'Agotado'},
    ]
    contexto = {
        'usuario': request.user,
        'sede': request.user.sede,
        'es_admin': True,
        'viajes_programados': viajes_programados,
    }
    return render(request, 'admin/asignacion_viajes.html', contexto)


# ==================== ADMIN - GESTIÓN DE USUARIOS ====================
@login_required
def usuarios_lista(request):
    """Lista de usuarios del sistema (cajeros)"""
    usuarios = [
        {'id': 1, 'username': 'cajero_trujillo', 'nombre': 'Ana García', 'rol': 'Cajero', 'sede': 'Trujillo', 'estado': 'Activo'},
        {'id': 2, 'username': 'cajero_julcan', 'nombre': 'Luis Martínez', 'rol': 'Cajero', 'sede': 'Julcán', 'estado': 'Activo'},
        {'id': 3, 'username': 'cajero_mache', 'nombre': 'Carmen Silva', 'rol': 'Cajero', 'sede': 'Mache', 'estado': 'Inactivo'},
    ]
    contexto = {
        'usuario': request.user,
        'sede': request.user.sede,
        'es_admin': True,
        'usuarios': usuarios,
        'total_usuarios': len(usuarios),
    }
    return render(request, 'admin/usuarios.html', contexto)

@login_required
def usuario_nuevo(request):
    """Abrir formulario visual para nuevo usuario/cajero"""
    return render(request, 'admin/usuario_form.html')

@login_required
def usuario_editar(request, id):
    """Abrir formulario visual para editar usuario"""
    return render(request, 'admin/usuario_form.html')

@login_required
def usuario_eliminar(request, id):
    """Simulación visual de eliminación"""
    messages.success(request, 'Usuario eliminado correctamente (Simulación)')
    return redirect('core:usuarios_lista')


# ==================== NOTIFICACIONES ====================
@login_required
def notificaciones_lista(request):
    """Centro de notificaciones automáticas del sistema"""
    usuario = request.user
    sede = usuario.sede

    notificaciones = [
        {
            'id': 1, 'tipo': 'fidelizacion', 'categoria': 'alerta',
            'titulo': '¡Cliente Ganador!',
            'descripcion': 'El cliente Juan Pérez (DNI: 12345678) completó 12 viajes. Entregar premio Rasca y Gana.',
            'prioridad': 'alta', 'leida': False, 'fecha': 'Hace 5 minutos',
            'icono': 'fa-gift', 'color': 'yellow'
        },
        {
            'id': 2, 'tipo': 'operativa', 'categoria': 'alerta',
            'titulo': '⚠️ Retraso en Viaje',
            'descripcion': 'Viaje 08:00 Trujillo→Julcán (ABC-123) reportó 15 min de retraso.',
            'prioridad': 'urgente', 'leida': False, 'fecha': 'Hace 22 minutos',
            'icono': 'fa-exclamation-triangle', 'color': 'red'
        },
    ]

    no_leidas = sum(1 for n in notificaciones if not n['leida'])

    contexto = {
        'usuario': usuario,
        'sede': sede,
        'notificaciones': notificaciones,
        'no_leidas_count': no_leidas,
    }
    return render(request, 'notificaciones/lista.html', contexto)


# ==================== PERFIL DE USUARIO ====================
@login_required
def mi_perfil(request):
    """Vista de mi perfil de usuario"""
    if request.method == 'POST':
        messages.success(request, 'Perfil actualizado correctamente')
        return redirect('core:mi_perfil')

    contexto = {
        'usuario': request.user,
        'sede': request.user.sede,
    }
    return render(request, 'cuenta/mi_perfil.html', contexto)


# ==================== REPORTES UNIFICADOS ====================
@login_required
def reportes_unificados(request):
    usuario = request.user
    sede = usuario.sede
    periodo = request.GET.get('periodo', 'diario')
    fecha_seleccionada = request.GET.get('fecha', timezone.now().date().isoformat())

    contexto = {
        'usuario': usuario, 'sede': sede, 'es_admin': False,
        'periodo': periodo, 'fecha_seleccionada': fecha_seleccionada,
    }

    if periodo == 'diario':
        contexto.update({
            'titulo_periodo': f"Reporte del día {fecha_seleccionada}",
            'total_ventas': 1540.00, 'total_viajes': 8, 'total_pasajeros': 142, 'total_boletos': 154,
            'chart_labels': ['06:00', '08:00', '10:00', '12:00', '14:00', '16:00', '18:00'],
            'chart_data': [250, 450, 380, 320, 290, 180, 120],
            'ventas_detalle': [{'hora': '08:30', 'ruta': 'Trujillo → Julcán', 'vehiculo': 'ABC-123', 'pasajeros': 18, 'metodo_pago': 'efectivo', 'monto': 450.00}]
        })
    elif periodo == 'semanal':
        contexto.update({
            'titulo_periodo': "Reporte de la Semana Actual",
            'total_ventas': 10780.00, 'total_viajes': 56, 'total_pasajeros': 994,
            'dia_rentable': 'Viernes', 'monto_dia_rentable': 2100.00,
            'chart_labels': ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo'],
            'chart_data': [1240, 1580, 1320, 1680, 2100, 1760, 1100],
            'metodos_pago_labels': ['Efectivo', 'Yape', 'Plin', 'Transferencia'],
            'metodos_pago_data': [65, 20, 10, 5]
        })
    elif periodo == 'mensual':
        contexto.update({
            'titulo_periodo': "Reporte del Mes Actual",
            'total_ventas': 45680.00, 'total_viajes': 240, 'total_pasajeros': 4256, 'premios_entregados': 18,
            'chart_labels': ['Sem 1', 'Sem 2', 'Sem 3', 'Sem 4'],
            'chart_data': [10500, 12300, 11800, 11080],
            'rutas_detalle': [{'ruta': 'Trujillo → Julcán', 'viajes': 60, 'pasajeros': 1080, 'ingresos': 27000, 'ocupacion': 75, 'rendimiento': 'Excelente'}]
        })
    else: # Anual
        contexto.update({
            'titulo_periodo': "Reporte Anual 2026",
            'total_ventas': 548160.00, 'total_viajes': 2880, 'total_pasajeros': 51072, 'premios_entregados': 216,
            'chart_labels': ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic'],
            'chart_data': [40000, 42000, 45000, 43000, 46000, 48000, 45680, 0, 0, 0, 0, 0]
        })

    return render(request, 'reportes/reportes_unificados.html', contexto)


# ==================== PORTAL CHOFERES ====================
@login_required
def chofer_reservar(request):
    """Portal exclusivo para choferes - Reservar asiento"""
    if not hasattr(request.user, 'rol') or request.user.rol != 'chofer':
        messages.error(request, 'Acceso denegado. Solo choferes pueden acceder.')
        return redirect('core:dashboard')

    viajes = [
        {'id': 1, 'ruta': 'Trujillo → Julcán', 'hora': '08:00 AM', 'vehiculo': 'ABC-123', 'libres': 12},
        {'id': 2, 'ruta': 'Trujillo → Mache', 'hora': '10:30 AM', 'vehiculo': 'XYZ-789', 'libres': 3},
        {'id': 3, 'ruta': 'Julcán → Trujillo', 'hora': '14:00 PM', 'vehiculo': 'DEF-456', 'libres': 0},
    ]

    mis_reservas = [
        {'id': 1, 'asiento': '02A', 'ruta': 'Trujillo → Julcán', 'hora': '08:00 AM', 'fecha': 'Hoy'},
    ]

    contexto = {
        'usuario': request.user,
        'vehiculo': {'placa': 'ABC-123'},
        'viajes': viajes,
        'mis_reservas': mis_reservas,
        'reservas_count': len(mis_reservas),
        'fecha_actual': timezone.now(),
    }

    return render(request, 'chofer/reservar_asiento.html', contexto)


@login_required
def chofer_confirmar_reserva(request):
    """Confirmar reserva de asiento por chofer"""
    if request.method == 'POST' and hasattr(request.user, 'rol') and request.user.rol == 'chofer':
        asiento = request.POST.get('asiento')
        viaje_id = request.POST.get('viaje_id')

        messages.success(request, f'✅ Asiento {asiento} reservado exitosamente')
        return redirect('core:chofer_reservar')

    return redirect('core:dashboard')


@login_required
def chofer_cancelar_reserva(request, reserva_id):
    """Cancelar reserva del chofer"""
    if hasattr(request.user, 'rol') and request.user.rol == 'chofer':
        messages.success(request, 'Reserva cancelada correctamente')

    return redirect('core:chofer_reservar')


# ==================== IMPRESIÓN DE TICKETS ====================
@login_required
def descargar_ticket_pdf(request, ticket_id):  # ← ticket_id DEBE estar aquí
    """Genera y descarga el ticket en PDF (Compatible con Windows)"""
    from xhtml2pdf import pisa
    import io
    from django.http import HttpResponse
    from django.template.loader import render_to_string
    from django.utils import timezone
    
    # Datos simulados (tu compañero conectará a BD después)
    ticket_data = {
        'id': ticket_id,
        'numero': f"TK-{ticket_id:04d}",
        'fecha_emision': timezone.now().strftime("%d/%m/%Y %H:%M"),
        'ruta': 'Trujillo → Julcán',
        'hora': '08:00 AM',
        'vehiculo': 'ABC-123',
        'pasajero': 'JUAN PEREZ',
        'dni': '12345678',
        'asiento': '03',
        'monto': 25.00,
        'es_premiado': False
    }
    
    # Renderizar HTML
    html_string = render_to_string('ventas/ticket_pdf.html', {'ticket': ticket_data})
    
    # Generar PDF en memoria
    result = io.BytesIO()
    pdf = pisa.CreatePDF(
        io.BytesIO(html_string.encode("UTF-8")),
        result,
        encoding='UTF-8'
    )
    
    if pdf.err:
        return HttpResponse("Error al generar el PDF", status=500)
    
    # Retornar archivo
    response = HttpResponse(result.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="ticket_{ticket_data["numero"]}.pdf"'
    return response

@login_required
def ver_ticket(request, venta_id):
    # Obtener datos de la venta desde BD
    ticket = get_object_or_404(Venta, id=venta_id)
    return render(request, 'ventas/ticket.html', {'ticket': ticket})