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
    Dashboard MINIMALISTA para el dueño (Sede Central)
    Solo muestra: totales consolidados + resumen por sede + incidencias pendientes
    """
    # Datos hardcodeados (después serán queries reales a BD)
    contexto = {
        'usuario': usuario,
        'sede': sede,
        'es_admin': True,
        
        # 🔹 KPIs Consolidados del Día
        'recaudacion_total': 4580.00,
        'total_ventas': 45,
        'total_viajes': 12,
        
        # 🔹 Resumen Simple por Sede (sin código, solo nombre)
        'resumen_por_sede': [
            {'nombre': 'Trujillo', 'ventas': 25, 'monto': 2540.00, 'porcentaje': 55},
            {'nombre': 'Julcán', 'ventas': 12, 'monto': 1320.00, 'porcentaje': 29},
            {'nombre': 'Mache', 'ventas': 8, 'monto': 720.00, 'porcentaje': 16},
        ],
        
        # 🔹 Incidencias Pendientes (solo las no resueltas)
        'incidencias_pendientes': [
            {'sede': 'Trujillo', 'descripcion': 'Retraso en salida 08:00', 'fecha': '2026-07-16'},
            {'sede': 'Mache', 'descripcion': 'Cliente sin cambio', 'fecha': '2026-07-16'},
        ],
    }
    
    return render(request, 'dashboard/dashboard_admin_simple.html', contexto)


# ==================== VENTAS (CRÍTICAS PARA MVP) ====================
@login_required
def ventas_lista(request):
    """Lista de ventas del día"""
    return render(request, 'ventas/lista.html')

@login_required
def nueva_venta(request, viaje_id):
    """Paso 1: Mapa de asientos (Ahora muestra mapa_asientos.html)"""
    viaje = {
        'id': viaje_id, 
        'hora_salida': '08:00',
        'ruta': 'Trujillo → Julcán', 
        'fecha': '2026-07-15',
        'vehiculo': {'placa': 'ABC-123', 'modelo': 'Toyota Hiace'},
        'precio_base': 25.00,
        'chofer': 'Juan Pérez'  # Agregué esto para que no falle el header
    }
    # CAMBIA ESTA LÍNEA: Ahora apunta al archivo correcto
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


# ==================== CLIENTES Y FIDELIZACIÓN (CRÍTICO ANTI-FRAUDE) ====================
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
        # Pasamos el DNI si viene en la URL para que el input lo recuerde
        'cliente_busqueda': request.GET.get('dni_cliente', ''),
    }
    # Renderizamos la plantilla que creaste
    return render(request, 'clientes/buscar.html', contexto)


# ==================== REPORTES BÁSICOS (CAJERO) ====================
@login_required
def reporte_diario(request):
    """Reporte diario para cajero (solo su sede)"""
    contexto = {
        'usuario': request.user, 
        'sede': request.user.sede, 
        'es_admin': False,
        'fecha': timezone.now().date(),
        'total_ventas': 15,
        'recaudacion_total': 1540.00
    }
    return render(request, 'reportes/diario.html', contexto)

@login_required
def reporte_semanal(request):
    """Reporte semanal para cajero"""
    return render(request, 'reportes/semanal.html')

@login_required
def reporte_mensual(request):
    """Reporte mensual para cajero"""
    return render(request, 'reportes/mensual.html')


# ==================== INCIDENCIAS (SIMPLE) ====================
@login_required
def incidencias_lista(request):
    """Lista de incidencias para cajero/admin"""
    contexto = {
        'usuario': request.user,
        'sede': request.user.sede,
        'es_admin': request.user.sede.nombre == 'central',
        'incidencias': []  # Después vendrá de BD
    }
    return render(request, 'incidencias/lista.html', contexto)


@login_required
def reporte_consolidado(request):
    """Vista del reporte consolidado admin con análisis completo"""
    
    # Obtener período seleccionado (default: hoy)
    periodo = request.GET.get('periodo', 'hoy')
    
    # Datos hardcodeados de ejemplo (después vendrán de BD)
    contexto = {
        'usuario': request.user,
        'sede': request.user.sede,
        'es_admin': True,
        'periodo': periodo,
        
        # 🔹 KPIs Consolidados
        'ingresos_totales': 15840.00,
        'total_viajes': 48,
        'total_pasajeros': 1247,
        'ocupacion_promedio': 78,
        
        # 🔹 Comparación vs período anterior
        'ingresos_variacion': 12.5,
        'viajes_variacion': 8.3,
        'pasajeros_variacion': 15.2,
        'ocupacion_variacion': 5.1,
        
        # 🔹 Datos para Gráfico de Tendencia (últimos 7 días)
        'dias_semana': ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom'],
        'ventas_por_dia': [8500, 9200, 10100, 9800, 11200, 13500, 15840],
        
        # 🔹 Ingresos por Sede (para gráfico de barras)
        'sedes': ['Trujillo', 'Julcán', 'Mache'],
        'ingresos_por_sede': [8540, 4320, 2980],
        
        # 🔹 Top 5 Rutas Más Rentables
        'top_rutas': [
            {'ruta': 'Trujillo → Julcán', 'ventas': 156, 'ingresos': 4680.00},
            {'ruta': 'Trujillo → Mache', 'ventas': 124, 'ingresos': 3720.00},
            {'ruta': 'Julcán → Trujillo', 'ventas': 98, 'ingresos': 2940.00},
            {'ruta': 'Mache → Trujillo', 'ventas': 87, 'ingresos': 2610.00},
            {'ruta': 'Julcán → Mache', 'ventas': 45, 'ingresos': 1350.00},
            {'ruta': 'Mache → Julcán', 'ventas': 60, 'ingresos': 1000.00},
        ],
        
        # 🔹 Top Vehículos (por ingresos)
        'top_vehiculos': [
            {'placa': 'ABC-123', 'modelo': 'Toyota Hiace', 'ingresos': 4580.00, 'viajes': 18},
            {'placa': 'XYZ-789', 'modelo': 'Nissan Urvan', 'ingresos': 3920.00, 'viajes': 15},
            {'placa': 'DEF-456', 'modelo': 'Toyota Coaster', 'ingresos': 3150.00, 'viajes': 12},
        ],
        
        # 🔹 Top Choferes (por ventas)
        'top_choferes': [
            {'nombre': 'Juan Pérez', 'ventas': 45, 'ingresos': 3200.00},
            {'nombre': 'María López', 'ventas': 38, 'ingresos': 2800.00},
            {'nombre': 'Carlos Ruiz', 'ventas': 32, 'ingresos': 2100.00},
        ],
    }
    
    return render(request, 'core/reporte_consolidado.html', contexto)

# ==================== ADMIN - VISTAS ESPECÍFICAS ====================

@login_required
def fidelizacion_admin(request):
    """Vista de fidelización para Admin (ve todos los clientes de todas las sedes)"""
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


@login_required
def reporte_diario_admin(request):
    """Reporte diario consolidado para Admin (ve todas las sedes)"""
    hoy = timezone.now().date()
    
    contexto = {
        'usuario': request.user,
        'sede': request.user.sede,
        'es_admin': True,
        'fecha': hoy,
        'total_ventas': 45,
        'recaudacion_total': 4580.00,
        'desglose_por_sede': [
            {'sede': 'Trujillo', 'ventas': 25, 'monto': 2540.00},
            {'sede': 'Julcán', 'ventas': 12, 'monto': 1320.00},
            {'sede': 'Mache', 'ventas': 8, 'monto': 720.00},
        ]
    }
    
    return render(request, 'admin/reporte_diario.html', contexto)

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


# ==================== ADMIN - CONFIGURACIÓN ====================
@login_required
def configuracion(request):
    """Configuración del sistema"""
    contexto = {
        'usuario': request.user,
        'sede': request.user.sede,
        'es_admin': True,
    }
    
    return render(request, 'admin/configuracion.html', contexto)

@login_required
def notificaciones_lista(request):
    """Lista de notificaciones"""
    contexto = {
        'notificaciones': [],  # Aquí iría tu queryset
        'no_leidas_count': 3,
    }
    return render(request, 'notificaciones/lista.html', contexto)

@login_required
def mi_perfil(request):
    """Vista de mi perfil de usuario"""
    if request.method == 'POST':
        # Aquí tu compañero agregará la lógica para actualizar datos
        messages.success(request, 'Perfil actualizado correctamente')
        return redirect('core:mi_perfil')
    
    contexto = {
        'usuario': request.user,
        'sede': request.user.sede,
    }
    return render(request, 'cuenta/mi_perfil.html', contexto)