# ==================== IMPORTS GLOBALES (AL INICIO) ====================
import logging
import re
import io
import secrets
import json
from datetime import datetime, timedelta

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import HttpResponse
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.utils import timezone

# xhtml2pdf para tickets (si lo usas)
try:
    from xhtml2pdf import pisa
except ImportError:
    pisa = None

# Servicios
from core.services.auth_service import AuthService
from core.services.chofer_service import ChoferService
from core.services.dashboard_service import DashboardService
from core.services.fidelizacion_service import FidelizacionService
from core.services.incidencia_service import IncidenciaService
from core.services.ruta_service import RutaService
from core.services.usuario_service import UsuarioService
from core.services.venta_service import VentaService
from core.services.vehiculo_service import VehiculoService
from core.services.viaje_service import ViajeService

# Formularios
from core.forms.chofer_forms import ChoferForm
from core.forms.incidencia_forms import IncidenciaForm
from core.forms.login_forms import LoginForm
from core.forms.ruta_forms import RutaForm
from core.forms.usuario_forms import UsuarioForm
from core.forms.venta_forms import VentaFiltroForm
from core.forms.vehiculo_forms import VehiculoForm
from core.forms.viaje_forms import ViajeForm

# Modelos
from core.models import Incidencia, Ruta, Sede, Usuario, Vehiculo, Viaje, Venta

# ==================== CONFIGURACIÓN DE LOGGERS ====================
logger = logging.getLogger('core.views')
logger_auth = logging.getLogger('core.auth')
logger_venta = logging.getLogger('core.venta_views')
logger_incidencia = logging.getLogger('core.incidencia_views')
logger_fidelizacion = logging.getLogger('core.fidelizacion_views')
logger_vehiculo = logging.getLogger('core.vehiculo_views')
logger_chofer = logging.getLogger('core.chofer_views')
logger_ruta = logging.getLogger('core.ruta_views')
logger_usuario = logging.getLogger('core.usuario_views')
logger_viaje = logging.getLogger('core.viajes_views')


# ==================== AUTH ====================

def login_view(request):
    """Vista de login con autenticación por sede y logging detallado"""
    
    logger_auth.info("=" * 60)
    logger_auth.info("INTENTO DE LOGIN INICIADO")
    logger_auth.info(f"IP: {request.META.get('REMOTE_ADDR')}")
    logger_auth.info(f"Método: {request.method}")
    
    if request.user.is_authenticated:
        logger_auth.warning(f"Usuario {request.user.username} ya está autenticado. Redirigiendo...")
        return redirect('core:dashboard')
    
    if request.method == 'POST':
        logger_auth.info("-" * 60)
        logger_auth.info("PROCESANDO FORMULARIO DE LOGIN")
        
        username = request.POST.get('username', '')
        password = request.POST.get('password', '')
        sede_nombre = request.POST.get('sede', '')
        
        logger_auth.info(f"Username recibido: {username}")
        logger_auth.info(f"Sede seleccionada: {sede_nombre}")
        logger_auth.info(f"Password recibido: {'*' * len(password) if password else 'VACÍO'}")
        
        form = LoginForm(request.POST)
        
        if form.is_valid():
            logger_auth.info("[OK] Formulario es VALIDO")
            user = form.get_user()
            
            if user:
                logger_auth.info(f"[OK] Usuario encontrado: {user.username}")
                logger_auth.info(f"   - Email: {user.email}")
                logger_auth.info(f"   - Sede: {user.sede}")
                logger_auth.info(f"   - Activo: {user.is_active}")
                logger_auth.info(f"   - Staff: {user.is_staff}")
                
                try:
                    login(request, user)
                    logger_auth.info(f"[OK] SESION INICIADA EXITOSAMENTE")
                    
                    request.session['sede_usuario'] = user.sede.nombre
                    request.session['sede_id'] = user.sede.id
                    logger_auth.info(f"   - Sede guardada en sesión: {user.sede.nombre}")
                    logger_auth.info(f"   - Session ID: {request.session.session_key}")
                    
                    messages.success(
                        request, 
                        f'¡Bienvenido {user.get_full_name() or user.username}! Sede: {user.sede.get_nombre_display()}'
                    )
                    
                    next_url = request.GET.get('next', 'core:dashboard')
                    logger_auth.info(f" Redirigiendo a: {next_url}")
                    logger_auth.info("=" * 60)
                    
                    return redirect(next_url)
                    
                except Exception as e:
                    logger_auth.error(f"[ERROR] Error al iniciar sesión: {str(e)}")
                    messages.error(request, f"Error al iniciar sesión: {str(e)}")
            else:
                logger_auth.error("[ERROR] form.get_user() retornó None")
                messages.error(request, "Error interno al obtener usuario")
        else:
            logger_auth.error("[ERROR] Formulario NO es válido")
            logger_auth.error(f"Errores del formulario: {form.errors}")
            
            for field, errors in form.errors.items():
                for error in errors:
                    logger_auth.error(f"   - {field}: {error}")
                    messages.error(request, f"{field}: {error}")
            
            for error in form.non_field_errors():
                logger_auth.error(f"   - Non-field error: {error}")
                messages.error(request, error)
    else:
        logger_auth.info("Método GET - Mostrando formulario de login")
        form = LoginForm()
    
    logger_auth.info("=" * 60)
    return render(request, 'login.html', {'form': form})


def logout_view(request):
    """Cerrar sesión con logging"""
    username = request.user.username if request.user.is_authenticated else 'ANÓNIMO'
    logger_auth.info(f"CERRANDO SESIÓN para usuario: {username}")
    
    logout(request)
    messages.info(request, 'Sesión cerrada correctamente')
    
    logger_auth.info("Redirigiendo a login")
    return redirect('core:login')


# ==================== DASHBOARD ====================
@login_required
def dashboard_view(request):
    """Dashboard único que se adapta según el usuario"""
    usuario = request.user
    sede = usuario.sede
    
    if sede.nombre == 'Oficina Central' or usuario.is_superuser:
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

    asientos_disponibles_total = sum(v['asientos_disponibles'] for v in proximos_viajes)
    asientos_totales_total = sum(v['asientos_totales'] for v in proximos_viajes)
    porcentaje_disponibilidad = (asientos_disponibles_total / asientos_totales_total * 100) if asientos_totales_total > 0 else 0

    cliente_busqueda = request.GET.get('dni_cliente', '')
    alerta_fidelizacion = None

    if cliente_busqueda:
        viajes_totales = 11
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
    """Dashboard COMPLETO para admin con filtros reales"""
    hoy = timezone.now().date()
    
    periodo = request.GET.get('periodo', 'hoy')
    sede_filtro = request.GET.get('sede', '')
    fecha_desde = request.GET.get('fecha_desde', '')
    fecha_hasta = request.GET.get('fecha_hasta', '')
    
    if periodo == 'semana':
        fecha_calculo = hoy - timedelta(days=hoy.weekday())
    elif periodo == 'mes':
        fecha_calculo = hoy.replace(day=1)
    elif periodo == 'anio':
        fecha_calculo = hoy.replace(month=1, day=1)
    elif fecha_desde:
        try:
            fecha_calculo = timezone.datetime.strptime(fecha_desde, '%Y-%m-%d').date()
        except ValueError:
            fecha_calculo = hoy
    else:
        fecha_calculo = hoy
    
    sede_para_filtro = None
    if sede_filtro and sede_filtro != '':
        sede_para_filtro = get_object_or_404(Sede, nombre=sede_filtro)
    else:
        sede_para_filtro = sede
    
    data = DashboardService.obtener_datos_dashboard(
        fecha=fecha_calculo,
        es_admin=True,
        sede=sede_para_filtro
    )
    
    contexto = {
        'usuario': usuario,
        'sede': sede,
        'es_admin': True,
        'fecha': fecha_calculo,
        'periodo': periodo,
        'sede_filtro': sede_filtro,
        'fecha_desde': fecha_desde,
        'fecha_hasta': fecha_hasta,
        'ingresos_totales': data['ingresos_totales'],
        'total_ventas': data['total_boletos'],
        'total_pasajeros': data['total_pasajeros'],
        'total_viajes': data['total_viajes'],
        'ocupacion_promedio': data['ocupacion_promedio'],
        'dias_semana': data['dias_semana'],
        'ventas_por_dia': data['ventas_por_dia'],
        'sedes': data['sedes'],
        'ingresos_por_sede': data['ingresos_por_sede'],
        'resumen_por_sede': [
            {'nombre': s, 'ventas': 0, 'monto': m, 'porcentaje': 0} 
            for s, m in zip(data['sedes'], data['ingresos_por_sede'])
        ],
        'actividad_reciente': [
            {
                'hora': v.fecha_venta.strftime('%H:%M'),
                'cliente': v.nombre_cliente or 'Pax Anónimo',
                'ruta': f"{v.viaje.ruta.origen} → {v.viaje.ruta.destino}",
                'monto': v.monto_total
            } for v in data['actividad_reciente']
        ],
        'incidencias_pendientes': [
            {
                'sede': inc.sede_reporte.nombre,
                'descripcion': inc.descripcion[:60] + ('...' if len(inc.descripcion) > 60 else ''),
                'fecha': inc.fecha_reporte
            } for inc in data['incidencias_pendientes']
        ],
    }
    
    return render(request, 'dashboard/dashboard_admin_simple.html', contexto)


# ==================== VENTAS ====================

@login_required
def ventas_lista(request):
    """Lista de ventas - Adaptable para admin y cajero"""
    usuario = request.user
    sede = usuario.sede
    
    if sede.nombre == 'Oficina Central' or usuario.is_superuser:
        return ventas_lista_admin(request, usuario, sede)
    else:
        return ventas_lista_cajero(request, usuario, sede)


@login_required
def ventas_lista_admin(request, usuario, sede):
    """Lista de ventas para ADMIN (todas las sedes)"""
    form = VentaFiltroForm(request.GET)
    filtros = form.cleaned_data if form.is_valid() else {}
    
    ventas = VentaService.obtener_ventas_filtradas(filtros, es_admin=True)
    kpis = VentaService.calcular_kpis(ventas)
    
    contexto = {
        'usuario': usuario, 'sede': sede, 'es_admin': True,
        'ventas': ventas,
        'form': form,
        'total_monto': kpis['total_monto'],
        'total_boletos': kpis['total_boletos'],
        'promedio_venta': kpis['promedio_venta'],
    }
    return render(request, 'admin/ventas_lista.html', contexto)


@login_required
def ventas_lista_cajero(request, usuario, sede):
    """Lista de ventas para CAJERO (solo su sede)"""
    form = VentaFiltroForm(request.GET)
    filtros = form.cleaned_data if form.is_valid() else {}
    
    ventas = VentaService.obtener_ventas_filtradas(filtros, es_admin=False, sede=sede)
    kpis = VentaService.calcular_kpis(ventas)
    
    contexto = {
        'usuario': usuario, 'sede': sede, 'es_admin': False,
        'ventas': ventas,
        'form': form,
        'total_monto': kpis['total_monto'],
        'total_boletos': kpis['total_boletos'],
        'promedio_venta': kpis['promedio_venta'],
    }
    return render(request, 'cajero/ventas_lista.html', contexto)


@login_required
def ventas_exportar(request):
    """Exporta la lista de ventas filtrada a Excel"""
    form = VentaFiltroForm(request.GET)
    filtros = form.cleaned_data if form.is_valid() else {}
    
    es_admin = request.user.is_superuser or request.user.sede.nombre == 'Oficina Central'
    sede = request.user.sede if not es_admin else None
    
    ventas = VentaService.obtener_ventas_filtradas(filtros, es_admin=es_admin, sede=sede)
    buffer = VentaService.generar_excel_ventas(ventas)
    
    filename = f"ventas_otiza_{timezone.now().strftime('%Y%m%d_%H%M')}.xlsx"
    
    response = HttpResponse(
        buffer.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


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
    
    if sede.nombre == 'Oficina Central' or usuario.is_superuser:
        return incidencias_lista_admin(request, usuario, sede)
    else:
        return incidencias_lista_cajero(request, usuario, sede)


@login_required
def incidencias_lista_admin(request, usuario, sede):
    """Lista de incidencias para ADMIN (todas las sedes)"""
    estado_filtro = request.GET.get('estado', '')
    tipo_filtro = request.GET.get('tipo', '')
    sede_filtro = request.GET.get('sede', '')
    
    sede_obj = Sede.objects.filter(nombre=sede_filtro).first() if sede_filtro else None
    
    incidencias = IncidenciaService.obtener_incidencias_filtradas(
        sede=sede_obj,
        estado=estado_filtro,
        tipo=tipo_filtro,
        es_admin=True
    )
    
    total = incidencias.count()
    pendientes = incidencias.filter(estado='pendiente').count()
    en_proceso = incidencias.filter(estado='en_proceso').count()
    resueltas = incidencias.filter(estado='resuelta').count()
    
    contexto = {
        'usuario': usuario, 'sede': sede, 'es_admin': True,
        'incidencias': incidencias,
        'total_incidencias': total, 'pendientes': pendientes,
        'en_proceso': en_proceso, 'resueltas': resueltas,
        'estado_filtro': estado_filtro, 'tipo_filtro': tipo_filtro,
        'sede_filtro': sede_filtro,
        'sedes': Sede.objects.filter(activa=True),
    }
    return render(request, 'admin/incidencias_lista.html', contexto)


@login_required
def incidencias_lista_cajero(request, usuario, sede):
    """Lista de incidencias para CAJERO (solo su sede)"""
    incidencias = IncidenciaService.obtener_incidencias_filtradas(
        sede=sede, es_admin=False
    )
    contexto = {
        'usuario': usuario, 'sede': sede, 'es_admin': False,
        'incidencias': incidencias,
        'total_incidencias': incidencias.count(),
        'pendientes': incidencias.filter(estado='pendiente').count(),
    }
    return render(request, 'cajero/incidencias_lista.html', contexto)


@login_required
def incidencia_nuevo(request):
    """Crear nueva incidencia"""
    usuario = request.user
    
    if request.method == 'POST':
        form = IncidenciaForm(request.POST, usuario=usuario)
        if form.is_valid():
            try:
                incidencia = IncidenciaService.crear_incidencia(
                    tipo=form.cleaned_data['tipo'],
                    descripcion=form.cleaned_data['descripcion'],
                    sede_reporte=form.cleaned_data['sede_reporte'],
                    reportado_por=usuario
                )
                messages.success(request, 'Incidencia creada exitosamente')
                return redirect('core:incidencias_lista')
            except ValidationError as e:
                messages.error(request, str(e))
    else:
        form = IncidenciaForm(usuario=usuario)
        
    return render(request, 'admin/incidencia_form.html', {'form': form, 'usuario': usuario})


@login_required
def incidencia_actualizar_estado(request, id):
    """Actualizar estado de incidencia (Admin)"""
    usuario = request.user
    incidencia = get_object_or_404(Incidencia, id=id)
    
    if request.method == 'POST':
        nuevo_estado = request.POST.get('estado')
        solucion = request.POST.get('solucion', '')
        
        try:
            IncidenciaService.actualizar_estado(id, nuevo_estado, solucion)
            messages.success(request, f'Incidencia marcada como {nuevo_estado.replace("_", " ")}')
        except ValidationError as e:
            messages.error(request, str(e))
            
    return redirect('core:incidencias_lista')


@login_required
def incidencia_eliminar(request, id):
    """Eliminar incidencia (Admin)"""
    usuario = request.user
    if not usuario.is_superuser:
        messages.error(request, 'Solo administradores pueden eliminar incidencias')
        return redirect('core:incidencias_lista')
        
    if request.method == 'POST':
        try:
            IncidenciaService.eliminar_incidencia(id)
            messages.success(request, 'Incidencia eliminada')
        except ValidationError as e:
            messages.error(request, str(e))
            
    return redirect('core:incidencias_lista')


# ==================== ADMIN - FIDELIZACIÓN ====================

@login_required
def fidelizacion_admin(request):
    """Vista de fidelización para Admin"""
    usuario = request.user
    sede = usuario.sede
    
    if sede.nombre != 'Oficina Central' and not usuario.is_superuser:
        messages.error(request, 'No tienes permisos para ver la fidelización global')
        return redirect('core:dashboard')
    
    filtro = request.GET.get('filtro', 'todos')
    
    try:
        logger_fidelizacion.info(f"FIDELIZACION_VIEW - Cargando datos con filtro: {filtro}")
        clientes = FidelizacionService.obtener_progreso_clientes(filtro)
        kpis = FidelizacionService.obtener_kpis_fidelizacion()
        
        contexto = {
            'usuario': usuario,
            'sede': sede,
            'es_admin': True,
            'clientes_cercanos': clientes,
            'total_clientes': kpis['total_clientes'],
            'premios_pendientes': kpis['premios_pendientes'],
            'premios_entregados_mes': kpis['premios_entregados_mes'],
            'filtro_actual': filtro,
        }
        
        return render(request, 'admin/fidelizacion.html', contexto)
        
    except Exception as e:
        logger_fidelizacion.error(f"FIDELIZACION_VIEW - Error: {str(e)}", exc_info=True)
        messages.error(request, f'Error al cargar datos de fidelización: {str(e)}')
        return redirect('core:dashboard')


# ==================== ADMIN - VEHÍCULOS ====================

@login_required
def vehiculos_lista(request):
    """Lista de vehículos"""
    usuario = request.user
    sede = usuario.sede
    
    if sede.nombre == 'Oficina Central' or usuario.is_superuser:
        vehiculos = Vehiculo.objects.all().select_related('sede_asignada')
        total_vehiculos = vehiculos.count()
        activos = vehiculos.filter(activo=True).count()
    else:
        vehiculos = Vehiculo.objects.filter(sede_asignada=sede).select_related('sede_asignada')
        total_vehiculos = vehiculos.count()
        activos = vehiculos.filter(activo=True).count()
    
    contexto = {
        'usuario': usuario,
        'sede': sede,
        'es_admin': usuario.is_superuser or sede.nombre == 'Oficina Central',
        'vehiculos': vehiculos,
        'total_vehiculos': total_vehiculos,
        'activos': activos,
    }
    
    return render(request, 'admin/vehiculos.html', contexto)


@login_required
def vehiculo_nuevo(request):
    """Crear nuevo vehículo"""
    usuario = request.user
    
    if not usuario.is_superuser and usuario.sede.nombre != 'Oficina Central':
        messages.error(request, 'No tienes permisos para crear vehículos')
        return redirect('core:vehiculos_lista')
    
    if request.method == 'POST':
        logger_vehiculo.info(f"VEHICULO_NUEVO - POST recibido de {usuario.username}")
        form = VehiculoForm(request.POST, usuario=usuario)
        
        if form.is_valid():
            try:
                logger_vehiculo.info("VEHICULO_NUEVO - Formulario válido, creando vehículo...")
                
                vehiculo = VehiculoService.crear_vehiculo(
                    placa=form.cleaned_data['placa'],
                    marca=form.cleaned_data['marca'],
                    modelo=form.cleaned_data['modelo'],
                    año=form.cleaned_data['año'],
                    capacidad_asientos=form.cleaned_data['capacidad_asientos'],
                    sede_asignada=form.cleaned_data['sede_asignada'],
                    creado_por=usuario
                )
                
                messages.success(
                    request, 
                    f'Vehículo {vehiculo.placa} creado exitosamente con {vehiculo.capacidad_asientos} asientos.'
                )
                logger_vehiculo.info(f"VEHICULO_NUEVO - Vehículo {vehiculo.id} creado exitosamente")
                
                return redirect('core:vehiculos_lista')
                
            except ValidationError as e:
                logger_vehiculo.error(f"VEHICULO_NUEVO - Error de validación: {str(e)}")
                messages.error(request, str(e))
            except Exception as e:
                logger_vehiculo.error(f"VEHICULO_NUEVO - Error inesperado: {str(e)}", exc_info=True)
                messages.error(request, f'Error al crear el vehículo: {str(e)}')
        else:
            logger_vehiculo.error(f"VEHICULO_NUEVO - Formulario inválido: {form.errors}")
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
    else:
        form = VehiculoForm(usuario=usuario)
    
    contexto = {
        'usuario': usuario,
        'form': form,
        'es_admin': True,
    }
    
    return render(request, 'admin/vehiculo_form.html', contexto)


@login_required
def vehiculo_editar(request, id):
    """Editar vehículo existente"""
    usuario = request.user
    vehiculo = get_object_or_404(Vehiculo, id=id)
    
    if not usuario.is_superuser and usuario.sede.nombre != 'Oficina Central':
        messages.error(request, 'No tienes permisos para editar vehículos')
        return redirect('core:vehiculos_lista')
    
    if request.method == 'POST':
        logger_vehiculo.info(f"VEHICULO_EDITAR - POST para vehículo {id}")
        form = VehiculoForm(request.POST, instance=vehiculo, usuario=usuario)
        
        if form.is_valid():
            try:
                logger_vehiculo.info(f"VEHICULO_EDITAR - Actualizando vehículo {id}...")
                form.save()
                messages.success(request, 'Vehículo actualizado exitosamente')
                logger_vehiculo.info(f"VEHICULO_EDITAR - Vehículo {id} actualizado")
                return redirect('core:vehiculos_lista')
            except Exception as e:
                logger_vehiculo.error(f"VEHICULO_EDITAR - Error: {str(e)}", exc_info=True)
                messages.error(request, f'Error al actualizar: {str(e)}')
        else:
            logger_vehiculo.error(f"VEHICULO_EDITAR - Formulario inválido: {form.errors}")
    else:
        form = VehiculoForm(instance=vehiculo, usuario=usuario)
    
    contexto = {
        'usuario': usuario,
        'form': form,
        'vehiculo': vehiculo,
        'es_admin': True,
    }
    
    return render(request, 'admin/vehiculo_form.html', contexto)


@login_required
def vehiculo_eliminar(request, id):
    """Eliminar vehículo"""
    usuario = request.user
    
    if not usuario.is_superuser and usuario.sede.nombre != 'Oficina Central':
        messages.error(request, 'No tienes permisos para eliminar vehículos')
        return redirect('core:vehiculos_lista')
    
    vehiculo = get_object_or_404(Vehiculo, id=id)
    
    if request.method == 'POST':
        try:
            logger_vehiculo.info(f"VEHICULO_ELIMINAR - Eliminando vehículo {id}")
            
            if vehiculo.viajes.exists():
                num_viajes = vehiculo.viajes.count()
                messages.error(
                    request, 
                    f'No se puede eliminar: El vehículo {vehiculo.placa} tiene {num_viajes} viajes asociados'
                )
                logger_vehiculo.error(f"VEHICULO_ELIMINAR - No se puede eliminar, tiene {num_viajes} viajes")
            else:
                vehiculo.delete()
                messages.success(request, f'Vehículo {vehiculo.placa} eliminado correctamente')
                logger_vehiculo.info(f"VEHICULO_ELIMINAR - Vehículo {id} eliminado exitosamente")
                
        except Exception as e:
            messages.error(request, f'Error al eliminar: {str(e)}')
            logger_vehiculo.error(f"VEHICULO_ELIMINAR - Error: {str(e)}", exc_info=True)
    
    return redirect('core:vehiculos_lista')


# ==================== ADMIN - CHOFERES ====================

@login_required
def choferes_lista(request):
    """Lista de choferes"""
    usuario = request.user
    sede = usuario.sede
    
    if sede.nombre == 'Oficina Central' or usuario.is_superuser:
        choferes = Usuario.objects.filter(es_chofer=True).select_related('sede')
        total_choferes = choferes.count()
        activos = choferes.filter(activo=True).count()
    else:
        choferes = Usuario.objects.filter(sede=sede, es_chofer=True).select_related('sede')
        total_choferes = choferes.count()
        activos = choferes.filter(activo=True).count()
    
    contexto = {
        'usuario': usuario,
        'sede': sede,
        'es_admin': usuario.is_superuser or sede.nombre == 'Oficina Central',
        'choferes': choferes,
        'total_choferes': total_choferes,
        'activos': activos,
    }
    
    return render(request, 'admin/choferes.html', contexto)


@login_required
def chofer_nuevo(request):
    """Crear nuevo chofer - SIN contraseña manual"""
    usuario = request.user
    
    if not usuario.is_superuser and usuario.sede.nombre != 'Oficina Central':
        messages.error(request, 'No tienes permisos para crear choferes')
        return redirect('core:choferes_lista')
    
    if request.method == 'POST':
        logger_chofer.info(f"CHOFER_NUEVO - POST recibido de {usuario.username}")
        form = ChoferForm(request.POST, usuario=usuario)
        
        if form.is_valid():
            try:
                logger_chofer.info("CHOFER_NUEVO - Formulario válido, creando chofer...")
                
                password_temporal = secrets.token_urlsafe(8)
                
                chofer = ChoferService.crear_chofer(
                    username=form.cleaned_data['username'],
                    password=password_temporal,
                    email=form.cleaned_data['email'],
                    first_name=form.cleaned_data['first_name'],
                    last_name=form.cleaned_data['last_name'],
                    dni=form.cleaned_data['username'],
                    licencia_conducir=form.cleaned_data['licencia_conducir'],
                    categoria_licencia=form.cleaned_data['categoria_licencia'],
                    fecha_vencimiento_licencia=form.cleaned_data['fecha_vencimiento_licencia'],
                    telefono=form.cleaned_data['telefono'],
                    sede_asignada=form.cleaned_data['sede'],
                    creado_por=usuario
                )
                
                messages.success(
                    request, 
                    f'Chofer {chofer.first_name} {chofer.last_name} creado exitosamente.\n'
                    f'Contraseña temporal: {password_temporal}'
                )
                logger_chofer.info(f"CHOFER_NUEVO - Chofer {chofer.id} creado exitosamente")
                
                return redirect('core:choferes_lista')
                
            except ValidationError as e:
                logger_chofer.error(f"CHOFER_NUEVO - Error de validación: {str(e)}")
                messages.error(request, str(e))
            except Exception as e:
                logger_chofer.error(f"CHOFER_NUEVO - Error inesperado: {str(e)}", exc_info=True)
                messages.error(request, f'Error al crear el chofer: {str(e)}')
    else:
        form = ChoferForm(usuario=usuario)
    
    contexto = {
        'usuario': usuario,
        'form': form,
        'es_admin': True,
    }
    
    return render(request, 'admin/chofer_form.html', contexto)


@login_required
def chofer_editar(request, id):
    """Editar chofer existente"""
    usuario = request.user
    chofer = get_object_or_404(Usuario, id=id, es_chofer=True)
    
    if not usuario.is_superuser and usuario.sede.nombre != 'Oficina Central':
        messages.error(request, 'No tienes permisos para editar choferes')
        return redirect('core:choferes_lista')
    
    if request.method == 'POST':
        logger_chofer.info(f"CHOFER_EDITAR - POST para chofer {id}")
        form = ChoferForm(request.POST, instance=chofer, usuario=usuario)
        
        if form.is_valid():
            try:
                logger_chofer.info(f"CHOFER_EDITAR - Actualizando chofer {id}...")
                
                chofer.email = form.cleaned_data['email']
                chofer.first_name = form.cleaned_data['first_name']
                chofer.last_name = form.cleaned_data['last_name']
                chofer.licencia_conducir = form.cleaned_data['licencia_conducir']
                chofer.categoria_licencia = form.cleaned_data['categoria_licencia']
                chofer.fecha_vencimiento_licencia = form.cleaned_data['fecha_vencimiento_licencia']
                chofer.telefono = form.cleaned_data['telefono']
                chofer.sede = form.cleaned_data['sede']
                chofer.activo = form.cleaned_data['activo']
                
                if form.cleaned_data.get('password'):
                    chofer.set_password(form.cleaned_data['password'])
                
                chofer.save()
                
                messages.success(request, 'Chofer actualizado exitosamente')
                logger_chofer.info(f"CHOFER_EDITAR - Chofer {id} actualizado")
                return redirect('core:choferes_lista')
            except Exception as e:
                logger_chofer.error(f"CHOFER_EDITAR - Error: {str(e)}", exc_info=True)
                messages.error(request, f'Error al actualizar: {str(e)}')
        else:
            logger_chofer.error(f"CHOFER_EDITAR - Formulario inválido: {form.errors}")
    else:
        form = ChoferForm(instance=chofer, usuario=usuario)
    
    contexto = {
        'usuario': usuario,
        'form': form,
        'chofer': chofer,
        'es_admin': True,
    }
    
    return render(request, 'admin/chofer_form.html', contexto)


@login_required
def chofer_eliminar(request, id):
    """Eliminar/Desactivar chofer"""
    usuario = request.user
    chofer = get_object_or_404(Usuario, id=id, es_chofer=True)
    
    if not usuario.is_superuser and usuario.sede.nombre != 'Oficina Central':
        messages.error(request, 'No tienes permisos para eliminar choferes')
        return redirect('core:choferes_lista')
    
    if request.method == 'POST':
        try:
            logger_chofer.info(f"CHOFER_ELIMINAR - Desactivando chofer {id}")
            ChoferService.eliminar_chofer(id)
            messages.success(request, f'Chofer {chofer.first_name} {chofer.last_name} desactivado exitosamente')
            logger_chofer.info(f"CHOFER_ELIMINAR - Chofer {id} desactivado")
        except ValidationError as e:
            logger_chofer.error(f"CHOFER_ELIMINAR - Error: {str(e)}")
            messages.error(request, str(e))
        except Exception as e:
            logger_chofer.error(f"CHOFER_ELIMINAR - Error inesperado: {str(e)}", exc_info=True)
            messages.error(request, f'Error al desactivar: {str(e)}')
    
    return redirect('core:choferes_lista')


# ==================== ADMIN - RUTAS ====================

@login_required
def rutas_lista(request):
    """Lista de rutas"""
    usuario = request.user
    sede = usuario.sede
    
    if sede.nombre == 'Oficina Central' or usuario.is_superuser:
        rutas = Ruta.objects.all()
        total_rutas = rutas.count()
        activas = rutas.filter(activa=True).count()
    else:
        rutas = Ruta.objects.filter(activa=True)
        total_rutas = rutas.count()
        activas = rutas.count()
    
    contexto = {
        'usuario': usuario,
        'sede': sede,
        'es_admin': usuario.is_superuser or sede.nombre == 'Oficina Central',
        'rutas': rutas,
        'total_rutas': total_rutas,
        'activas': activas,
    }
    
    return render(request, 'admin/rutas.html', contexto)


@login_required
def ruta_nuevo(request):
    """Crear nueva ruta"""
    usuario = request.user
    
    if not usuario.is_superuser and usuario.sede.nombre != 'Oficina Central':
        messages.error(request, 'No tienes permisos para crear rutas')
        return redirect('core:rutas_lista')
    
    if request.method == 'POST':
        logger_ruta.info(f"RUTA_NUEVO - POST recibido de {usuario.username}")
        form = RutaForm(request.POST, usuario=usuario)
        
        if form.is_valid():
            try:
                logger_ruta.info("RUTA_NUEVO - Formulario válido, creando ruta...")
                
                ruta = RutaService.crear_ruta(
                    origen=form.cleaned_data['origen'],
                    destino=form.cleaned_data['destino'],
                    distancia_km=form.cleaned_data['distancia_km'],
                    duracion_estimada=form.cleaned_data['duracion_estimada'],
                    precio_base=form.cleaned_data['precio_base'],
                    creado_por=usuario
                )
                
                messages.success(
                    request, 
                    f'Ruta {ruta.origen} → {ruta.destino} creada exitosamente. '
                    f'Duración: {ruta.duracion_estimada}, Precio: S/ {ruta.precio_base}'
                )
                logger_ruta.info(f"RUTA_NUEVO - Ruta {ruta.id} creada exitosamente")
                
                return redirect('core:rutas_lista')
                
            except ValidationError as e:
                logger_ruta.error(f"RUTA_NUEVO - Error de validación: {str(e)}")
                messages.error(request, str(e))
            except Exception as e:
                logger_ruta.error(f"RUTA_NUEVO - Error inesperado: {str(e)}", exc_info=True)
                messages.error(request, f'Error al crear la ruta: {str(e)}')
        else:
            logger_ruta.error(f"RUTA_NUEVO - Formulario inválido: {form.errors}")
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
    else:
        form = RutaForm(usuario=usuario)
    
    contexto = {
        'usuario': usuario,
        'form': form,
        'es_admin': True,
    }
    
    return render(request, 'admin/ruta_form.html', contexto)


@login_required
def ruta_editar(request, id):
    """Editar ruta existente"""
    usuario = request.user
    ruta = get_object_or_404(Ruta, id=id)
    
    if not usuario.is_superuser and usuario.sede.nombre != 'Oficina Central':
        messages.error(request, 'No tienes permisos para editar rutas')
        return redirect('core:rutas_lista')
    
    if request.method == 'POST':
        logger_ruta.info(f"RUTA_EDITAR - POST para ruta {id}")
        form = RutaForm(request.POST, instance=ruta, usuario=usuario)
        
        if form.is_valid():
            try:
                logger_ruta.info(f"RUTA_EDITAR - Actualizando ruta {id}...")
                form.save()
                messages.success(request, f'Ruta {ruta.origen} → {ruta.destino} actualizada correctamente')
                logger_ruta.info(f"RUTA_EDITAR - Ruta {id} actualizada")
                return redirect('core:rutas_lista')
            except Exception as e:
                logger_ruta.error(f"RUTA_EDITAR - Error: {str(e)}", exc_info=True)
                messages.error(request, f'Error al actualizar: {str(e)}')
        else:
            logger_ruta.error(f"RUTA_EDITAR - Formulario inválido: {form.errors}")
    else:
        form = RutaForm(instance=ruta, usuario=usuario)
    
    contexto = {
        'usuario': usuario,
        'form': form,
        'ruta': ruta,
        'es_admin': True,
    }
    
    return render(request, 'admin/ruta_form.html', contexto)


@login_required
def ruta_eliminar(request, id):
    """Eliminar ruta"""
    usuario = request.user
    
    if not usuario.is_superuser and usuario.sede.nombre != 'Oficina Central':
        messages.error(request, 'No tienes permisos para eliminar rutas')
        return redirect('core:rutas_lista')
    
    ruta = get_object_or_404(Ruta, id=id)
    
    if request.method == 'POST':
        try:
            logger_ruta.info(f"RUTA_ELIMINAR - Eliminando ruta {id}")
            
            if ruta.viajes.exists():
                num_viajes = ruta.viajes.count()
                messages.error(
                    request, 
                    f'No se puede eliminar: La ruta {ruta.origen} → {ruta.destino} tiene {num_viajes} viajes programados'
                )
                logger_ruta.error(f"RUTA_ELIMINAR - No se puede eliminar, tiene {num_viajes} viajes")
            else:
                ruta.delete()
                messages.success(request, f'Ruta {ruta.origen} → {ruta.destino} eliminada correctamente')
                logger_ruta.info(f"RUTA_ELIMINAR - Ruta {id} eliminada exitosamente")
                
        except Exception as e:
            messages.error(request, f'Error al eliminar: {str(e)}')
            logger_ruta.error(f"RUTA_ELIMINAR - Error: {str(e)}", exc_info=True)
    
    return redirect('core:rutas_lista')


# ==================== ADMIN - USUARIOS ====================

@login_required
def usuarios_lista(request):
    """Lista de usuarios/cajeros"""
    usuario = request.user
    sede = usuario.sede
    
    if sede.nombre == 'Oficina Central' or usuario.is_superuser:
        usuarios = Usuario.objects.all().select_related('sede')
        total_usuarios = usuarios.count()
        activos = usuarios.filter(activo=True).count()
    else:
        usuarios = Usuario.objects.filter(sede=sede).select_related('sede')
        total_usuarios = usuarios.count()
        activos = usuarios.filter(activo=True).count()
    
    contexto = {
        'usuario': usuario,
        'sede': sede,
        'es_admin': usuario.is_superuser or sede.nombre == 'Oficina Central',
        'usuarios': usuarios,
        'total_usuarios': total_usuarios,
        'activos': activos,
    }
    
    return render(request, 'admin/usuarios.html', contexto)


@login_required
def usuario_nuevo(request):
    """Crear nuevo usuario/cajero"""
    usuario = request.user
    
    if not usuario.is_superuser and usuario.sede.nombre != 'Oficina Central':
        messages.error(request, 'No tienes permisos para crear usuarios')
        return redirect('core:usuarios_lista')
    
    if request.method == 'POST':
        logger_usuario.info(f"USUARIO_NUEVO - POST recibido de {usuario.username}")
        form = UsuarioForm(request.POST, usuario=usuario)
        
        if form.is_valid():
            try:
                logger_usuario.info("USUARIO_NUEVO - Formulario válido, creando usuario...")
                
                nuevo_usuario = UsuarioService.crear_usuario(
                    username=form.cleaned_data['username'],
                    password=form.cleaned_data['password'],
                    email=form.cleaned_data['email'],
                    first_name=form.cleaned_data['first_name'],
                    last_name=form.cleaned_data['last_name'],
                    sede_asignada=form.cleaned_data['sede'],
                    telefono=form.cleaned_data['telefono'],
                    es_cajero=form.cleaned_data['es_cajero'],
                    creado_por=usuario
                )
                
                messages.success(
                    request, 
                    f'Usuario {nuevo_usuario.username} creado exitosamente.'
                )
                logger_usuario.info(f"USUARIO_NUEVO - Usuario {nuevo_usuario.id} creado exitosamente")
                
                return redirect('core:usuarios_lista')
                
            except ValidationError as e:
                logger_usuario.error(f"USUARIO_NUEVO - Error de validación: {str(e)}")
                messages.error(request, str(e))
            except Exception as e:
                logger_usuario.error(f"USUARIO_NUEVO - Error inesperado: {str(e)}", exc_info=True)
                messages.error(request, f'Error al crear el usuario: {str(e)}')
        else:
            logger_usuario.error(f"USUARIO_NUEVO - Formulario inválido: {form.errors}")
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
    else:
        form = UsuarioForm(usuario=usuario)
    
    contexto = {
        'usuario': usuario,
        'form': form,
        'es_admin': True,
    }
    
    return render(request, 'admin/usuario_form.html', contexto)


@login_required
def usuario_editar(request, id):
    """Editar usuario existente - SIN cambio de contraseña"""
    usuario = request.user
    usuario_editar = get_object_or_404(Usuario, id=id)
    
    if not usuario.is_superuser and usuario.sede.nombre != 'Oficina Central':
        messages.error(request, 'No tienes permisos para editar usuarios')
        return redirect('core:usuarios_lista')
    
    if request.method == 'POST':
        logger_usuario.info(f"USUARIO_EDITAR - POST para usuario {id}")
        form = UsuarioForm(request.POST, instance=usuario_editar, usuario=usuario)
        
        if form.is_valid():
            try:
                logger_usuario.info(f"USUARIO_EDITAR - Actualizando usuario {id}...")
                
                usuario_editar.username = form.cleaned_data['username']
                usuario_editar.email = form.cleaned_data['email']
                usuario_editar.first_name = form.cleaned_data['first_name']
                usuario_editar.last_name = form.cleaned_data['last_name']
                usuario_editar.telefono = form.cleaned_data['telefono']
                usuario_editar.sede = form.cleaned_data['sede']
                usuario_editar.es_cajero = form.cleaned_data['es_cajero']
                usuario_editar.activo = form.cleaned_data['activo']
                
                usuario_editar.save()
                
                messages.success(request, 'Usuario actualizado exitosamente')
                logger_usuario.info(f"USUARIO_EDITAR - Usuario {id} actualizado")
                return redirect('core:usuarios_lista')
            except Exception as e:
                logger_usuario.error(f"USUARIO_EDITAR - Error: {str(e)}", exc_info=True)
                messages.error(request, f'Error al actualizar: {str(e)}')
        else:
            logger_usuario.error(f"USUARIO_EDITAR - Formulario inválido: {form.errors}")
    else:
        form = UsuarioForm(instance=usuario_editar, usuario=usuario)
    
    contexto = {
        'usuario': usuario,
        'form': form,
        'usuario_editar': usuario_editar,
        'es_admin': True,
    }
    
    return render(request, 'admin/usuario_form.html', contexto)


@login_required
def usuario_eliminar(request, id):
    """Eliminar usuario"""
    usuario = request.user
    usuario_eliminar = get_object_or_404(Usuario, id=id)
    
    if not usuario.is_superuser and usuario.sede.nombre != 'Oficina Central':
        messages.error(request, 'No tienes permisos para eliminar usuarios')
        return redirect('core:usuarios_lista')
    
    if request.method == 'POST':
        try:
            logger_usuario.info(f"USUARIO_ELIMINAR - Eliminando usuario {id}")
            UsuarioService.eliminar_usuario(id)
            messages.success(request, f'Usuario {usuario_eliminar.username} eliminado exitosamente')
            logger_usuario.info(f"USUARIO_ELIMINAR - Usuario {id} eliminado")
        except ValidationError as e:
            logger_usuario.error(f"USUARIO_ELIMINAR - Error: {str(e)}")
            messages.error(request, str(e))
        except Exception as e:
            logger_usuario.error(f"USUARIO_ELIMINAR - Error inesperado: {str(e)}", exc_info=True)
            messages.error(request, f'Error al eliminar: {str(e)}')
    
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
    else:
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
def descargar_ticket_pdf(request, ticket_id):
    """Genera y descarga el ticket en PDF"""
    
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
    
    html_string = render_to_string('ventas/ticket_pdf.html', {'ticket': ticket_data})
    
    result = io.BytesIO()
    if pisa:
        pdf = pisa.CreatePDF(
            io.BytesIO(html_string.encode("UTF-8")),
            result,
            encoding='UTF-8'
        )
        
        if pdf.err:
            return HttpResponse("Error al generar el PDF", status=500)
    
    response = HttpResponse(result.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="ticket_{ticket_data["numero"]}.pdf"'
    return response

@login_required
def ver_ticket(request, venta_id):
    ticket = get_object_or_404(Venta, id=venta_id)
    return render(request, 'ventas/ticket.html', {'ticket': ticket})


# ==================== ADMIN - ASIGNACIÓN DE VIAJES ====================

# Función auxiliar para parsear duración (MISMA LÓGICA EN TODAS PARTES)
def _parsear_duracion(duracion_texto):
    """Parsea duración estimada y retorna (horas, minutos)"""
    duracion_texto = str(duracion_texto).lower().strip()
    horas = 0
    minutos = 0
    
    # Regex para horas: acepta "1 hora", "2 horas", "1h", "2 h"
    match_horas = re.search(r'(\d+)\s*(?:hora|horas|h)\b', duracion_texto)
    if match_horas:
        horas = int(match_horas.group(1))
    
    # Regex para minutos: acepta "30 min", "30 minutos", "30m", "30 m"
    match_minutos = re.search(r'(\d+)\s*(?:min|minutos|m)\b', duracion_texto)
    if match_minutos:
        minutos = int(match_minutos.group(1))
    
    return horas, minutos


@login_required
def asignacion_viajes(request):
    """Lista de viajes para Admin (todas las sedes)"""
    usuario = request.user
    sede = usuario.sede
    
    if sede.nombre == 'Oficina Central' or usuario.is_superuser:
        viajes = Viaje.objects.all().select_related('ruta', 'vehiculo', 'sede_salida')
    else:
        viajes = Viaje.objects.filter(sede_salida=sede).select_related('ruta', 'vehiculo')
    
    contexto = {
        'usuario': usuario,
        'sede': sede,
        'es_admin': usuario.is_superuser or sede.nombre == 'Oficina Central',
        'viajes': viajes,
        'total_viajes': viajes.count(),
    }
    
    return render(request, 'admin/asignacion_viajes.html', contexto)


@login_required
def viaje_nuevo(request):
    """Crear nuevo viaje (Admin) - Con cálculo automático de llegada"""
    usuario = request.user
    
    if not usuario.is_superuser and usuario.sede.nombre != 'Oficina Central':
        messages.error(request, 'No tienes permisos para crear viajes')
        return redirect('core:asignacion_viajes')
    
    if request.method == 'POST':
        logger_viaje.info(f"VIAJE_NUEVO - POST recibido de {usuario.username}")
        form = ViajeForm(request.POST, usuario=usuario)
        
        if form.is_valid():
            try:
                logger_viaje.info("VIAJE_NUEVO - Formulario válido, creando viaje...")
                
                ruta = form.cleaned_data['ruta']
                fecha_salida = form.cleaned_data['fecha_salida']
                hora_salida = form.cleaned_data['hora_salida']
                
                # Parsear duración con regex robusto (MISMA FUNCIÓN QUE EL SERVICIO)
                horas, minutos = _parsear_duracion(ruta.duracion_estimada)
                
                # Calcular llegada
                salida_dt = datetime.combine(fecha_salida, hora_salida)
                llegada_dt = salida_dt + timedelta(hours=horas, minutes=minutos)
                
                fecha_llegada = llegada_dt.date()
                hora_llegada = llegada_dt.time()
                
                viaje = ViajeService.crear_viaje(
                    ruta=ruta,
                    vehiculo=form.cleaned_data['vehiculo'],
                    sede_salida=form.cleaned_data['sede_salida'],
                    fecha_salida=fecha_salida,
                    hora_salida=hora_salida,
                    fecha_llegada=fecha_llegada,
                    hora_llegada=hora_llegada,
                    creado_por=usuario
                )
                
                messages.success(
                    request, 
                    f'Viaje creado exitosamente. Llegada estimada: {hora_llegada.strftime("%H:%M")}'
                )
                logger_viaje.info(f"VIAJE_NUEVO - Viaje {viaje.id} creado exitosamente")
                
                return redirect('core:asignacion_viajes')
                
            except ValidationError as e:
                logger_viaje.error(f"VIAJE_NUEVO - Error de validación: {str(e)}")
                
                if 'pasado' in str(e).lower() or 'fecha' in str(e).lower():
                    messages.error(
                        request, 
                        '⚠️ No se puede crear un viaje en el pasado. Por favor selecciona una fecha y hora futuras.'
                    )
                else:
                    messages.error(request, str(e))
            except Exception as e:
                logger_viaje.error(f"VIAJE_NUEVO - Error inesperado: {str(e)}", exc_info=True)
                messages.error(request, f'Error al crear el viaje: {str(e)}')
        else:
            logger_viaje.error(f"VIAJE_NUEVO - Formulario inválido: {form.errors}")
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
    else:
        form = ViajeForm(usuario=usuario)
    
    contexto = {
        'usuario': usuario,
        'form': form,
        'es_admin': True,
    }
    
    return render(request, 'admin/viaje_form.html', contexto)


@login_required
def viaje_editar(request, id):
    """Editar viaje existente (Admin) - Con recálculo automático de llegada"""
    usuario = request.user
    viaje = get_object_or_404(Viaje, id=id)
    
    if not usuario.is_superuser and usuario.sede.nombre != 'Oficina Central':
        messages.error(request, 'No tienes permisos para editar viajes')
        return redirect('core:asignacion_viajes')
    
    if request.method == 'POST':
        logger_viaje.info(f"VIAJE_EDITAR - POST para viaje {id}")
        form = ViajeForm(request.POST, instance=viaje, usuario=usuario)
        
        if form.is_valid():
            try:
                logger_viaje.info(f"VIAJE_EDITAR - Actualizando viaje {id}...")
                
                # Solo recalcular si cambió hora_salida o ruta
                if form.has_changed():
                    ruta = form.cleaned_data['ruta']
                    fecha_salida = form.cleaned_data['fecha_salida']
                    hora_salida = form.cleaned_data['hora_salida']
                    
                    # Parsear duración con regex robusto (MISMA FUNCIÓN)
                    horas, minutos = _parsear_duracion(ruta.duracion_estimada)
                    
                    # Calcular llegada
                    salida_dt = datetime.combine(fecha_salida, hora_salida)
                    llegada_dt = salida_dt + timedelta(hours=horas, minutes=minutos)
                    
                    # Actualizar instancia antes de guardar
                    form.instance.fecha_llegada = llegada_dt.date()
                    form.instance.hora_llegada = llegada_dt.time()
                
                form.save()
                messages.success(request, 'Viaje actualizado exitosamente')
                logger_viaje.info(f"VIAJE_EDITAR - Viaje {id} actualizado")
                return redirect('core:asignacion_viajes')
            except Exception as e:
                logger_viaje.error(f"VIAJE_EDITAR - Error: {str(e)}", exc_info=True)
                messages.error(request, f'Error al actualizar: {str(e)}')
        else:
            logger_viaje.error(f"VIAJE_EDITAR - Formulario inválido: {form.errors}")
    else:
        form = ViajeForm(instance=viaje, usuario=usuario)
    
    contexto = {
        'usuario': usuario,
        'form': form,
        'viaje': viaje,
        'es_admin': True,
    }
    
    return render(request, 'admin/viaje_form.html', contexto)


@login_required
def viaje_eliminar(request, id):
    """Eliminar viaje (Admin)"""
    usuario = request.user
    
    if not usuario.is_superuser and usuario.sede.nombre != 'Oficina Central':
        messages.error(request, 'No tienes permisos para eliminar viajes')
        return redirect('core:asignacion_viajes')
    
    viaje = get_object_or_404(Viaje, id=id)
    
    if request.method == 'POST':
        try:
            logger_viaje.info(f"VIAJE_ELIMINAR - Eliminando viaje {id}")
            
            if viaje.ventas.exists():
                messages.error(request, f'No se puede eliminar: El viaje tiene {viaje.ventas.count()} ventas registradas')
                logger_viaje.error(f"VIAJE_ELIMINAR - No se puede eliminar, tiene ventas")
            else:
                viaje.delete()
                messages.success(request, f'Viaje {viaje.ruta} del {viaje.fecha_salida} eliminado correctamente')
                logger_viaje.info(f"VIAJE_ELIMINAR - Viaje {id} eliminado exitosamente")
                
        except Exception as e:
            messages.error(request, f'Error al eliminar: {str(e)}')
            logger_viaje.error(f"VIAJE_ELIMINAR - Error: {str(e)}", exc_info=True)
    
    return redirect('core:asignacion_viajes')