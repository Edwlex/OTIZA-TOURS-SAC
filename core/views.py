# ==================== IMPORTS ESTÁNDAR ====================
import os
import re
import secrets
from io import BytesIO
import json
import logging
import random 
from datetime import datetime, timedelta,time   

# ==================== DJANGO CORE ====================
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.http import HttpResponse, JsonResponse, HttpResponseRedirect
from django.db.models import Count, Q, Sum, IntegerField
from django.db.models.functions import ExtractHour, Cast
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.utils import timezone

# ==================== PDFs ====================
try:
    from xhtml2pdf import pisa
except ImportError:
    pisa = None

# ==================== SERVICIOS OTIZA ====================
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

# ==================== FORMULARIOS ====================
from core.forms.chofer_forms import ChoferForm
from core.forms.incidencia_forms import IncidenciaForm
from core.forms.login_forms import LoginForm
from core.forms.ruta_forms import RutaForm
from core.forms.usuario_forms import UsuarioForm
from core.forms.venta_forms import VentaFiltroForm
from core.forms.vehiculo_forms import VehiculoForm
from core.forms.viaje_forms import ViajeForm
from core.forms import ManifiestoForm, PasajeroFormSet
from core.models import HojaRuta
from core.forms import HojaRutaForm

# ==================== MODELOS ====================
from core.models import Incidencia, Ruta, Sede, Usuario, Vehiculo, Viaje, Venta, AsientoViaje, HorarioFijo, Manifiesto, PasajeroManifiesto

# ==================== LOGGERS ====================
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
    """Vista de login con autenticación por sede, roles y logging detallado"""
    
    logger_auth.info("=" * 60)
    logger_auth.info("INTENTO DE ACCESO A LOGIN")
    logger_auth.info(f"IP: {request.META.get('REMOTE_ADDR')}")
    logger_auth.info(f"Método: {request.method}")
    
    # ✅ 1. LÓGICA DE REDIRECCIÓN SI YA ESTÁ AUTENTICADO
    if request.user.is_authenticated:
        logger_auth.info(f"Usuario {request.user.username} ya está autenticado. Evaluando redirección por rol...")
        
        # A) Si es Chofer
        if hasattr(request.user, 'es_chofer') and request.user.es_chofer:
            if request.session.get('chofer_actual'):
                logger_auth.info("-> Es Chofer con identidad activa. Redirigiendo a Panel Chofer.")
                return redirect('core:panel_chofer')
            else:
                logger_auth.info("-> Es Chofer sin identidad. Redirigiendo a Selección de Identidad.")
                return redirect('core:chofer_seleccionar_identidad')
        
        # B) Si es Administrador o Staff
        if request.user.is_superuser or request.user.is_staff:
            logger_auth.info("-> Es Admin/Staff. Redirigiendo a Dashboard.")
            return redirect('core:dashboard') 
        
        # C) Si es Cajero / Encargado de Sede (Por defecto)
        logger_auth.info("-> Es usuario de Sede. Redirigiendo a Dashboard.")
        return redirect('core:dashboard')
    
    # ✅ 2. PROCESAMIENTO DEL FORMULARIO (POST)
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
            logger_auth.info("[OK] Formulario es VÁLIDO")
            user = form.get_user()
            
            if user:
                logger_auth.info(f"[OK] Usuario encontrado: {user.username}")
                logger_auth.info(f"   - Email: {user.email}")
                logger_auth.info(f"   - Sede: {user.sede}")
                logger_auth.info(f"   - Activo: {user.is_active}")
                logger_auth.info(f"   - Es Chofer: {getattr(user, 'es_chofer', False)}")
                
                try:
                    login(request, user)
                    logger_auth.info(f"[OK] SESIÓN INICIADA EXITOSAMENTE")
                    
                    # Guardar datos en sesión
                    if user.sede:
                        request.session['sede_usuario'] = user.sede.nombre
                        request.session['sede_id'] = user.sede.id
                        logger_auth.info(f"   - Sede guardada en sesión: {user.sede.nombre}")
                    
                    logger_auth.info(f"   - Session ID: {request.session.session_key}")
                    
                    messages.success(
                        request, 
                        f'¡Bienvenido {user.get_full_name() or user.username}!'
                    )
                    
                    # 🎯 3. LÓGICA DE REDIRECCIÓN INTELIGENTE SEGÚN EL ROL
                    next_url = request.GET.get('next')
                    if not next_url:
                        # ✅ AQUÍ ESTÁ LA CLAVE: Si es chofer, lo mandamos a elegir identidad
                        if getattr(user, 'es_chofer', False) or user.username == 'chofer':
                            next_url = 'core:chofer_seleccionar_identidad'
                            logger_auth.info("-> Redirigiendo a: Selección de Identidad de Chofer")
                        elif user.is_superuser or user.is_staff:
                            next_url = 'core:dashboard'
                            logger_auth.info("-> Redirigiendo a: Dashboard Admin")
                        else:
                            next_url = 'core:dashboard'
                            logger_auth.info("-> Redirigiendo a: Dashboard Sede")
                            
                    logger_auth.info(f"-> Redirigiendo a: {next_url}")
                    logger_auth.info("=" * 60)
                    
                    return redirect(next_url)
                    
                except Exception as e:
                    logger_auth.error(f"[ERROR] Excepción al iniciar sesión: {str(e)}")
                    messages.error(request, f"Error interno al iniciar sesión: {str(e)}")
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
                
    # ✅ 4. MOSTRAR FORMULARIO (GET)
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



@login_required
def dashboard_cajero(request, usuario, sede):
    """Dashboard para cajeros - VERSIÓN FINAL LIMPIA"""
    
    # 1. OBTENER HORA Y FECHA LOCAL
    ahora_local = timezone.localtime(timezone.now())
    hoy = ahora_local.date()
    
    # 2. RANGO PARA VENTAS
    inicio_dia = ahora_local.replace(hour=0, minute=0, second=0, microsecond=0)
    fin_dia = ahora_local.replace(hour=23, minute=59, second=59, microsecond=999999)
    
    # ==================== 1. KPIs DEL DÍA ====================
    ventas_hoy_qs = Venta.objects.filter(sede_venta=sede, fecha_venta__range=(inicio_dia, fin_dia))
    ventas_hoy = ventas_hoy_qs.count()
    monto_total_hoy = ventas_hoy_qs.aggregate(total=Sum('monto_total'))['total'] or 0
    total_pasajeros_hoy = ventas_hoy
    
    viajes_completados_hoy = Viaje.objects.filter(
        sede_salida=sede, fecha_salida=hoy, estado__in=['finalizado', 'completado', 'terminado']
    ).count()
    
    # ==================== 2. PRÓXIMOS VIAJES (SOLO HOY, FUTUROS) ====================
    proximos_viajes_qs = Viaje.objects.filter(
        sede_salida=sede,
        fecha_salida=hoy,
        estado__in=['programado', 'en_curso', 'activo', 'pendiente']
    ).select_related('ruta', 'vehiculo').prefetch_related('asientos').order_by('hora_salida')[:5]
    
    proximos_viajes = []
    for viaje in proximos_viajes_qs:
        asientos = viaje.asientos.all()
        total = asientos.count()
        disponibles = asientos.filter(estado='disponible').count()
        ocupacion = ((total - disponibles) / total * 100) if total > 0 else 0
        
        proximos_viajes.append({
            'id': viaje.id,
            'hora_salida': viaje.hora_salida.strftime('%H:%M') if viaje.hora_salida else 'N/A',
            'ruta': f"{viaje.ruta.origen} → {viaje.ruta.destino}",
            'vehiculo': {'placa': viaje.vehiculo.placa, 'modelo': viaje.vehiculo.modelo},
            'asientos_disponibles': disponibles,
            'asientos_totales': total,
            'estado': viaje.get_estado_display(),
            'porcentaje_ocupacion': round(ocupacion, 1),
        })
    
    # ==================== 3. VIAJES RECIENTES ====================
    fecha_desde = hoy - timedelta(days=3)
    viajes_recientes_qs = Viaje.objects.filter(
        sede_salida=sede, fecha_salida__gte=fecha_desde, estado__in=['finalizado', 'completado', 'terminado']
    ).select_related('ruta', 'vehiculo').order_by('-fecha_salida', '-hora_salida')[:5]
    
    viajes_recientes = []
    for viaje in viajes_recientes_qs:
        ingresos = viaje.ventas.aggregate(total=Sum('monto_total'))['total'] or 0
        pasajeros = viaje.ventas.count()
        viajes_recientes.append({
            'fecha': viaje.fecha_salida.strftime('%d/%m/%Y') if viaje.fecha_salida else 'N/A',
            'hora': viaje.hora_salida.strftime('%H:%M') if viaje.hora_salida else 'N/A',
            'ruta_origen': viaje.ruta.origen,
            'ruta_destino': viaje.ruta.destino,
            'vehiculo': {'placa': viaje.vehiculo.placa},
            'asientos_ocupados': pasajeros,
            'ingreso': ingresos,
            'estado': 'Completado'
        })
    
    # ==================== 4. FIDELIZACIÓN ====================
    clientes_cercanos = []
    try:
        clientes_sede = FidelizacionService.obtener_progreso_clientes(filtro='cerca')
        for cliente in clientes_sede:
            ventas_cliente_en_sede = Venta.objects.filter(numero_documento=cliente['dni'], sede_venta=sede).count()
            if ventas_cliente_en_sede > 0:
                clientes_cercanos.append({
                    'dni': cliente['dni'], 'nombre': cliente['nombre'],
                    'viajes_en_sede': ventas_cliente_en_sede, 'faltan_para_premio': cliente['faltan']
                })
    except Exception:
        pass
    
    # ==================== 5. NOTIFICACIONES ====================
    notificaciones_no_leidas = Notificacion.objects.filter(sede_id=sede.id, leida=False).order_by('-fecha_creacion')[:10]
    notificaciones_leidas = Notificacion.objects.filter(sede_id=sede.id, leida=True).order_by('-fecha_creacion')[:5]
    total_notificaciones = notificaciones_no_leidas.count()
    
    # ==================== 6. CONTEXTO BASE ====================
    contexto = {
        'usuario': usuario, 'sede': sede, 'es_admin': False, 'fecha_actual': hoy,
        'ventas_hoy': ventas_hoy, 'monto_total_hoy': monto_total_hoy,
        'viajes_completados_hoy': viajes_completados_hoy, 'total_pasajeros_hoy': total_pasajeros_hoy,
        'proximos_viajes': proximos_viajes, 'viajes_recientes': viajes_recientes,
        'clientes_cercanos': clientes_cercanos[:3], 'alerta_fidelizacion': clientes_cercanos[0] if clientes_cercanos else None,
        'cliente_busqueda': request.GET.get('dni_cliente', ''),
        'notificaciones_no_leidas': notificaciones_no_leidas, 'notificaciones_leidas': notificaciones_leidas,
        'total_notificaciones': total_notificaciones,
    }
    
    # ==================== 7. DATOS PARA GRÁFICOS ====================
    ventas_por_hora = Venta.objects.filter(sede_venta=sede, fecha_venta__range=(inicio_dia, fin_dia)).annotate(hora=ExtractHour('fecha_venta')).values('hora').annotate(total=Sum('monto_total')).order_by('hora')
    
    horas_labels = [f"{h:02d}:00" for h in range(6, 20)]
    ventas_hora_data = [0] * 14
    for item in ventas_por_hora:
        hora_idx = item['hora'] - 6
        if 0 <= hora_idx < 14:
            ventas_hora_data[hora_idx] = float(item['total'] or 0)
    
    rutas_ocupacion = Viaje.objects.filter(sede_salida=sede, fecha_salida=hoy, estado__in=['programado', 'en_curso', 'activo', 'pendiente', 'finalizado', 'completado']).select_related('ruta').prefetch_related('asientos')
    
    rutas_labels, rutas_data = [], []
    colores_rutas = ['#10B981', '#3B82F6', '#F59E0B', '#8B5CF6', '#EF4444']
    
    for i, viaje in enumerate(rutas_ocupacion[:4]):
        asientos = viaje.asientos.all()
        total = asientos.count()
        ocupados = asientos.filter(estado__in=['vendido', 'reservado']).count()
        porcentaje = (ocupados / total * 100) if total > 0 else 0
        rutas_labels.append(f"{viaje.ruta.origen}→{viaje.ruta.destino}")
        rutas_data.append(round(porcentaje, 1))
    
    if not rutas_labels:
        rutas_labels, rutas_data = ['Sin datos'], [0]
    
    asientos_disponibles_total = sum(v['asientos_disponibles'] for v in proximos_viajes)
    asientos_totales_total = sum(v['asientos_totales'] for v in proximos_viajes)
    
    contexto.update({
        'ventas_hora_labels': horas_labels, 'ventas_hora_data': ventas_hora_data,
        'rutas_labels': rutas_labels, 'rutas_data': rutas_data, 'rutas_colores': colores_rutas[:len(rutas_labels)],
        'asientos_disponibles_total': asientos_disponibles_total, 'asientos_totales_total': asientos_totales_total,
        'porcentaje_disponibilidad': round((asientos_disponibles_total / asientos_totales_total * 100) if asientos_totales_total > 0 else 0, 1),
    })
    
    return render(request, 'dashboard/dashboard_cajero.html', contexto)


@login_required
def dashboard_admin_simple(request, usuario, sede):
    """Dashboard COMPLETO para admin con datos REALES de BD"""
    from core.models import Venta, Viaje, AsientoViaje, Ruta, Vehiculo, Incidencia
    from django.db.models import Sum, Count, Q, Avg
    from django.db.models.functions import TruncDate
    import calendar
    
    # ✅ Obtener la fecha LOCAL (Perú)
    hoy = timezone.localtime(timezone.now()).date()
    
    # --- 1. PROCESAR FILTROS ---
    periodo = request.GET.get('periodo', 'hoy')
    sede_filtro = request.GET.get('sede', '')
    fecha_desde = request.GET.get('fecha_desde', '')
    fecha_hasta = request.GET.get('fecha_hasta', '')
    
    # Definir rango de fechas según período
    if periodo == 'semana':
        fecha_inicio = hoy - timedelta(days=hoy.weekday())
        fecha_fin = hoy
    elif periodo == 'mes':
        fecha_inicio = hoy.replace(day=1)
        fecha_fin = hoy
    elif periodo == 'anio':
        fecha_inicio = hoy.replace(month=1, day=1)
        fecha_fin = hoy
    elif fecha_desde and fecha_hasta:
        try:
            fecha_inicio = timezone.datetime.strptime(fecha_desde, '%Y-%m-%d').date()
            fecha_fin = timezone.datetime.strptime(fecha_hasta, '%Y-%m-%d').date()
        except ValueError:
            fecha_inicio = hoy
            fecha_fin = hoy
    else:
        fecha_inicio = hoy
        fecha_fin = hoy
    
    # --- 2. FILTRO DE SEDE ---
    filtro_sede = Q()
    if sede_filtro and sede_filtro != 'Todas las sedes':
        filtro_sede &= Q(sede_venta__nombre=sede_filtro)
    
    # Filtro base de fechas
    filtro_fecha = Q(fecha_venta__range=[fecha_inicio, fecha_fin + timedelta(days=1)])
    
    # --- 3. KPIs CON DATOS REALES ---
    stats = Venta.objects.filter(filtro_fecha & filtro_sede).aggregate(
        ingresos=Sum('monto_total'),
        ventas=Count('id'),
        pasajeros=Count('id')  # 1 venta = 1 pasajero
    )
    
    ingresos_totales = stats['ingresos'] or 0
    total_ventas = stats['ventas'] or 0
    total_pasajeros = stats['pasajeros'] or 0
    
    # Ocupación promedio (ventas / asientos totales de viajes programados)
    viajes_periodo = Viaje.objects.filter(
        fecha_salida__range=[fecha_inicio, fecha_fin],
        sede_salida=sede if not usuario.is_superuser else None
    ).select_related('vehiculo').prefetch_related('asientos')
    
    asientos_totales = sum(v.vehiculo.capacidad_asientos for v in viajes_periodo)
    asientos_vendidos = total_ventas
    ocupacion_promedio = round((asientos_vendidos / asientos_totales * 100), 1) if asientos_totales > 0 else 0
    
    # --- 4. DATOS PARA GRÁFICA DE TENDENCIA ---
    ventas_por_dia_qs = Venta.objects.filter(filtro_fecha & filtro_sede).annotate(
        dia=TruncDate('fecha_venta')
    ).values('dia').annotate(
        total=Sum('monto_total')
    ).order_by('dia')
    
    # Generar labels y datos para todos los días del período
    chart_labels = []
    chart_data = []
    current_date = fecha_inicio
    
    while current_date <= fecha_fin:
        chart_labels.append(current_date.strftime('%d/%m'))
        # Buscar si hay venta para este día
        venta_dia = next((v for v in ventas_por_dia_qs if v['dia'] == current_date), None)
        chart_data.append(float(venta_dia['total']) if venta_dia else 0)
        current_date += timedelta(days=1)
    
    # --- 5. DATOS PARA GRÁFICA POR SEDE (solo si es admin global) ---
    if usuario.is_superuser or sede.nombre == 'Oficina Central':
        ingresos_por_sede_qs = Venta.objects.filter(filtro_fecha).values(
            'sede_venta__nombre'
        ).annotate(
            total=Sum('monto_total')
        ).order_by('-total')
        
        sede_labels = [item['sede_venta__nombre'] or 'Sin sede' for item in ingresos_por_sede_qs]
        sede_data = [float(item['total'] or 0) for item in ingresos_por_sede_qs]
    else:
        # Si no es admin global, solo muestra su sede
        sede_labels = [sede.nombre]
        sede_data = [ingresos_totales]
    
    # --- 6. TOP RUTAS ---
    top_rutas_qs = Venta.objects.filter(filtro_fecha & filtro_sede).values(
        'viaje__ruta__origen', 'viaje__ruta__destino'
    ).annotate(
        ventas=Count('id'),
        ingresos=Sum('monto_total')
    ).order_by('-ingresos')[:3]
    
    top_rutas = [
        {
            'ruta': f"{item['viaje__ruta__origen']} → {item['viaje__ruta__destino']}",
            'ventas': item['ventas'],
            'ingresos': item['ingresos'] or 0
        } for item in top_rutas_qs
    ]
    
    # --- 7. VEHÍCULOS ACTIVOS HOY ---
    vehiculos_filter = Q(fecha_salida=hoy, estado__in=['programado', 'en_curso'])
    if not usuario.is_superuser:
        vehiculos_filter &= Q(sede_salida=sede)
    
    vehiculos_activos_qs = Viaje.objects.filter(vehiculos_filter).select_related(
        'vehiculo', 'chofer_asignado'
    )[:5]
    
    vehiculos_activos = [
        {
            'placa': v.vehiculo.placa,
            'chofer': v.chofer_asignado.get_full_name() if v.chofer_asignado else 'Sin asignar',
            'estado': 'En ruta' if v.estado == 'en_curso' else 'Disponible'
        } for v in vehiculos_activos_qs
    ]
    
    # --- 8. DETALLE DE VENTAS RECIENTES ---
    detalle_ventas_qs = Venta.objects.filter(filtro_fecha & filtro_sede).select_related(
        'viaje__ruta', 'viaje__vehiculo', 'viaje__chofer_asignado', 'sede_venta'
    ).order_by('-fecha_venta')[:10]
    
    detalle_ventas = [
        {
            'fecha': v.fecha_venta.strftime('%d/%m/%Y'),
            'hora': v.fecha_venta.strftime('%H:%M'),
            'sede': v.sede_venta.nombre,
            'ruta': f"{v.viaje.ruta.origen} → {v.viaje.ruta.destino}",
            'vehiculo': v.viaje.vehiculo.placa,
            'chofer': v.viaje.chofer_asignado.get_full_name() if v.viaje.chofer_asignado else '-',
            'pasajeros': 1,
            'ingreso': v.monto_total
        } for v in detalle_ventas_qs
    ]
    
    # --- 9. INCIDENCIAS PENDIENTES ---
    incidencias_filter = Q(estado='pendiente')
    if not usuario.is_superuser:
        incidencias_filter &= Q(sede_reporte=sede)
    
    incidencias_pendientes = Incidencia.objects.filter(incidencias_filter).select_related(
        'sede_reporte'
    ).order_by('-fecha_reporte')[:5]
    
    # --- 10. CONTEXTO FINAL ---
    contexto = {
        'usuario': usuario,
        'sede': sede,
        'es_admin': True,
        'fecha': hoy,
        'periodo': periodo,
        'sede_filtro': sede_filtro,
        'fecha_desde': fecha_desde,
        'fecha_hasta': fecha_hasta,
        
        # KPIs
        'ingresos_totales': ingresos_totales,
        'total_ventas': total_ventas,
        'total_pasajeros': total_pasajeros,
        'ocupacion_promedio': ocupacion_promedio,
        
        # Gráficas
        'chart_labels': chart_labels,
        'chart_data': chart_data,
        'sede_labels': sede_labels,
        'sede_data': sede_data,
        
        # Secciones
        'top_rutas': top_rutas,
        'vehiculos_activos': vehiculos_activos,
        'detalle_ventas': detalle_ventas,
        'incidencias_pendientes': incidencias_pendientes,
        
        # Flags para mensajes vacíos
        'hay_ventas': total_ventas > 0,
        'hay_rutas': len(top_rutas) > 0,
        'hay_vehiculos': len(vehiculos_activos) > 0,
        'hay_incidencias': len(incidencias_pendientes) > 0,

        'hay_filtros_activos': (periodo != 'hoy' or sede_filtro != '' or fecha_desde != '' or fecha_hasta != '')
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
    
    # Obtener ventas y KPIs
    ventas = VentaService.obtener_ventas_filtradas(filtros, es_admin=True)
    kpis = VentaService.calcular_kpis(ventas)
    
    # ✅ Obtener rutas activas ordenadas desde la BD
    rutas_activas = Ruta.objects.filter(activa=True).order_by('origen', 'destino')
    
    # ✅ Detectar si hay filtros activos para el mensaje amigable
    hay_filtros_activos = bool(request.GET)
    
    contexto = {
        'usuario': usuario, 
        'sede': sede, 
        'es_admin': True,
        'ventas': ventas,
        'form': form,
        'rutas_activas': rutas_activas,  # ← Rutas dinámicas
        'total_monto': kpis['total_monto'],
        'total_boletos': kpis['total_boletos'],
        'promedio_venta': kpis['promedio_venta'],
        'hay_filtros_activos': hay_filtros_activos,  # ← Para el mensaje
    }
    return render(request, 'admin/ventas_lista.html', contexto)





from datetime import datetime, time # ✅ Asegúrate de tener esto importado arriba

@login_required
def ventas_lista_cajero(request, usuario, sede):
    """Lista de ventas para CAJERO - CON FILTRO DE FECHA FUNCIONAL""" 
    
    form = VentaFiltroForm(request.GET)
    filtros = form.cleaned_data if form.is_valid() else {}
    
    # Obtener ventas y KPIs
    ventas = VentaService.obtener_ventas_filtradas(filtros, es_admin=False, sede=sede)
    kpis = VentaService.calcular_kpis(ventas)
    
    # ===== FECHA Y HORA ACTUAL LOCAL =====
    ahora_local = timezone.localtime(timezone.now())
    hoy = ahora_local.date()
    ahora = ahora_local.time()
    
    # ✅ 1. OBTENER FECHA DEL FILTRO (o usar hoy por defecto)
    fecha_filtro_str = request.GET.get('fecha', '')
    if fecha_filtro_str:
        try:
            from datetime import datetime as dt
            fecha_filtro = dt.strptime(fecha_filtro_str, '%Y-%m-%d').date()
        except ValueError:
            fecha_filtro = hoy
    else:
        fecha_filtro = hoy
    
    # ✅ 2. CONSTRUIR QUERYSET DE VIAJES SEGÚN LA FECHA
    if fecha_filtro < hoy:
        # Si es una fecha PASADA, traemos TODOS los viajes de ese día (sin importar estado)
        viajes_qs = Viaje.objects.filter(fecha_salida=fecha_filtro)
    elif fecha_filtro == hoy:
        # ✅ Si es HOY, traemos TODOS los viajes del día (sin importar si ya pasaron)
        # La lógica de 'esta_pasado' se encargará de marcarlos como bloqueados en el template
        viajes_qs = Viaje.objects.filter(
            fecha_salida=hoy,
            estado__in=['programado', 'en_curso', 'pendiente', 'activo', 'finalizado', 'completado', 'terminado']
        )
    else:
        # Si es una fecha FUTURA, traemos los programados
        viajes_qs = Viaje.objects.filter(fecha_salida=fecha_filtro, estado__in=['programado', 'pendiente', 'activo'])
    
    # Aplicar otros filtros (ruta, buscador)
    if filtros.get('ruta'):
        viajes_qs = viajes_qs.filter(ruta_id=filtros['ruta'])
    if filtros.get('buscador') or request.GET.get('q'):
        buscador = filtros.get('buscador') or request.GET.get('q', '')
        viajes_qs = viajes_qs.filter(
            Q(ruta__origen__icontains=buscador) |
            Q(ruta__destino__icontains=buscador) |
            Q(vehiculo__placa__icontains=buscador)
        )
    
    viajes_qs = viajes_qs.select_related('ruta', 'vehiculo', 'chofer_asignado', 'sede_salida') \
                         .prefetch_related('asientos') \
                         .order_by('fecha_salida', 'hora_salida')
    
    # ✅ 3. PROCESAR VIAJES Y MARCAR SI ESTÁN PASADOS
    viajes_disponibles = []
    for viaje in viajes_qs:
        asientos_lista = list(viaje.asientos.all())
        total = len(asientos_lista)
        disponibles = sum(1 for a in asientos_lista if a.estado == 'disponible')
        
        chofer_obj = viaje.chofer_asignado
        nombre_chofer = chofer_obj.get_full_name() if chofer_obj else 'Por asignar'
        
        # Lógica para marcar como pasado
        esta_pasado = False
        if fecha_filtro < hoy:
            esta_pasado = True
        elif fecha_filtro == hoy and viaje.hora_salida:
            from datetime import datetime, time
            hora_viaje = viaje.hora_salida.time() if isinstance(viaje.hora_salida, datetime) else viaje.hora_salida
            if isinstance(hora_viaje, time) and hora_viaje < ahora:
                esta_pasado = True
        
        viajes_disponibles.append({
            'id': viaje.id,
            'hora_salida': viaje.hora_salida,
            'ruta': viaje.ruta,
            'vehiculo': viaje.vehiculo,
            'chofer_nombre': nombre_chofer,
            'asientos_totales': total,
            'asientos_disponibles': disponibles,
            'precio_base': viaje.ruta.precio_base,
            'estado': viaje.estado,
            'sede_salida_nombre': viaje.sede_salida.nombre if viaje.sede_salida else 'Global',
            'esta_pasado': esta_pasado,
            'fecha_salida': viaje.fecha_salida,
        })
    
    # Debug
    print(f"\n{'='*60}")
    print(f" DEBUG VENTAS_LISTA | Fecha filtro: {fecha_filtro} | Hoy: {hoy}")
    print(f"🔍 Total viajes encontrados: {len(viajes_disponibles)}")
    print(f"{'='*60}\n")
    
    contexto = {
        'usuario': usuario,
        'sede': sede,
        'es_admin': False,
        'hoy': hoy,
        'ventas': ventas,
        'form': form,
        'total_monto': kpis['total_monto'],
        'total_boletos': kpis['total_boletos'],
        'promedio_venta': kpis['promedio_venta'],
        'viajes_disponibles': viajes_disponibles,
        'rutas_activas': Ruta.objects.filter(activa=True).order_by('origen', 'destino'),
        'hay_filtros_activos': bool(request.GET),
    }
    
    return render(request, 'ventas/lista.html', contexto)



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
    """Mostrar mapa de asientos - CON VALIDACIÓN CORRECTA DE FECHA Y ORDEN NUMÉRICO"""
    
    usuario = request.user
    viaje = get_object_or_404(Viaje, id=viaje_id)
    
    # ===== 1. VALIDACIÓN DE TIEMPO (CORREGIDA) =====
    ahora = timezone.localtime(timezone.now())
    hoy = ahora.date()
    ahora_hora = ahora.time()
    
    #  Bloquear si la fecha es ANTERIOR a hoy
    if viaje.fecha_salida < hoy:
        messages.error(request, f'⚠️ Este viaje ({viaje.fecha_salida}) ya ha pasado')
        return redirect('core:ventas_lista')
    
    #  Bloquear si es HOY pero la hora YA PASÓ
    if viaje.fecha_salida == hoy and viaje.hora_salida < ahora_hora:
        messages.error(request, f'⚠️ El viaje de hoy a las {viaje.hora_salida.strftime("%H:%M")} ya ha partido')
        return redirect('core:ventas_lista')

    # Verificar estado del viaje
    if viaje.estado not in ['programado', 'en_curso']:
        messages.error(request, 'Este viaje no está disponible para la venta')
        return redirect('core:ventas_lista')
    
    # ===== 2. OBTENER ASIENTOS (TU LÓGICA DE ORDEN) =====
    # Ordena numéricamente (1, 2, 3... 10) en lugar de alfabético (1, 10, 2)
    asientos_qs = viaje.asientos.all().annotate(
        num_asiento_int=Cast('numero_asiento', IntegerField())
    ).order_by('num_asiento_int')
    
    # Convertir a lista para usar índices en el template [0], [1], [2]...
    asientos = list(asientos_qs)
    
    asientos_libres = len([a for a in asientos if a.estado == 'disponible'])
    
    contexto = {
        'usuario': usuario,
        'viaje': viaje,
        'asientos': asientos,  # ← Lista ordenada numéricamente
        'asientos_libres': asientos_libres,
        'precio_base': viaje.ruta.precio_base,
        'puede_liberar_reservas': usuario.is_superuser or usuario.sede.nombre == 'Oficina Central',
    }
    
    return render(request, 'ventas/mapa_asientos.html', contexto)

    

logger = logging.getLogger(__name__)

from django.utils import timezone
from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.db.models import Max
from datetime import datetime
import random
import logging

logger = logging.getLogger(__name__)

# ✅ FUNCIÓN PARA GENERAR NÚMERO CORRELATIVO
def generar_numero_correlativo():
    """Genera el siguiente número correlativo de boleto"""
    ultimo_numero = Venta.objects.aggregate(max_num=Max('numero_correlativo'))['max_num']
    if ultimo_numero is None:
        return 1
    return ultimo_numero + 1


@login_required
def procesar_venta(request):
    """Procesar la venta de un asiento"""
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método no permitido'}, status=400)
    
    usuario = request.user
    
    # Obtener datos del formulario
    viaje_id = request.POST.get('viaje_id')
    asiento_numero = request.POST.get('asiento_numero')
    dni_pasajero = request.POST.get('dni_pasajero')
    nombre_pasajero = request.POST.get('nombre_pasajero')
    telefono_pasajero = request.POST.get('telefono_pasajero')
    email_pasajero = request.POST.get('email_pasajero', '')
    ruc_cliente = request.POST.get('ruc_cliente', '')
    razon_social = request.POST.get('razon_social', '')
    metodo_pago = request.POST.get('metodo_pago', 'efectivo')
    
    # Validar datos obligatorios
    if not all([viaje_id, asiento_numero, dni_pasajero, nombre_pasajero]):
        return JsonResponse({'success': False, 'error': 'Faltan datos obligatorios'}, status=400)
    
    # Obtener objetos
    viaje = get_object_or_404(Viaje, id=viaje_id)
    asiento = get_object_or_404(AsientoViaje, numero_asiento=asiento_numero, viaje=viaje)
    
    # ===== ✅ VALIDACIÓN CORREGIDA: Usar hora LOCAL =====
    ahora_local = timezone.localtime(timezone.now())
    hoy_local = ahora_local.date()
    hora_local = ahora_local.time()
    
    # Combinar fecha y hora del viaje para comparar
    viaje_dt = datetime.combine(viaje.fecha_salida, viaje.hora_salida)
    if timezone.is_naive(viaje_dt):
        viaje_dt = timezone.make_aware(viaje_dt)
    
    # ✅ Solo bloquear si el viaje YA PASÓ (fecha y hora local)
    if viaje_dt < ahora_local:
        return JsonResponse({
            'success': False, 
            'error': f'El viaje del {viaje.fecha_salida.strftime("%d/%m")} a las {viaje.hora_salida.strftime("%H:%M")} ya ha partido'
        }, status=400)
    
    # Verificar que el asiento esté disponible
    if asiento.estado != 'disponible':
        return JsonResponse({'success': False, 'error': 'Este asiento ya no está disponible'}, status=409)
    
    try:
        # Generar número de ticket (se mantiene para el nombre del archivo)
        ticket_numero = f"TKT-{timezone.now().strftime('%y%m%d')}-{random.randint(1000, 9999)}"
        
        # ✅ Generar número correlativo
        numero_correlativo = generar_numero_correlativo()
        
        # Crear venta
        venta = Venta.objects.create(
            viaje=viaje,
            asiento=asiento,
            sede_venta=usuario.sede,
            cajero=usuario,
            numero_documento=dni_pasajero,
            nombre_cliente=nombre_pasajero,
            telefono_cliente=telefono_pasajero,
            email_cliente=email_pasajero,
            ruc_cliente=ruc_cliente,
            razon_social=razon_social,
            metodo_pago=metodo_pago,
            monto_total=viaje.ruta.precio_base,
            numero_ticket=ticket_numero,
            numero_correlativo=numero_correlativo,  # ✅ NUEVO CAMPO
            fecha_venta=timezone.now()
        )
        
        # Marcar asiento como vendido
        asiento.estado = 'vendido'
        asiento.save()
        
        # ✅ Formatear número correlativo (000001, 000002, etc.)
        numero_formateado = f"{numero_correlativo:06d}"
        
        # ✅ Devolver JSON exitoso CON 'tipo' y número correlativo
        return JsonResponse({
            'success': True,
            'venta_id': venta.id,
            'asiento': venta.asiento.numero_asiento,
            'ruta': f"{venta.viaje.ruta.origen} → {venta.viaje.ruta.destino}",
            'fecha': venta.viaje.fecha_salida.strftime('%d/%m/%Y'),
            'hora': venta.viaje.hora_salida.strftime('%H:%M'),
            'pasajero': venta.nombre_cliente,
            'total': str(venta.monto_total),
            'tipo': 'venta',  # ← Para que el JS sepa qué color poner
            'numero_correlativo': numero_formateado,  # ✅ NUEVO: Para mostrar en el frontend
        })
        
    except Exception as e:
        logger.error(f"Error al procesar venta: {str(e)}", exc_info=True)
        return JsonResponse({'success': False, 'error': f'Error al registrar: {str(e)}'}, status=500)

    
    
# ==================== CLIENTES Y FIDELIZACIÓN ====================
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from core.models import Venta
import logging

logger = logging.getLogger('core.views')

@login_required
def fidelizacion_cliente(request):
    """
    Vista de fidelización: Buscador por DNI con progreso GLOBAL (todas las sedes).
    No muestra resultados hasta que se busca un DNI válido.
    """
    usuario = request.user
    sede = usuario.sede
    
    # 1. Capturar la búsqueda
    busqueda = request.GET.get('q', '').strip()
    
    cliente_detalle = None
    viajes_cliente = []
    progreso_porcentaje = 0
    proximo_premio_en = 0
    
    # 2. Si hay una búsqueda por DNI (8 dígitos)
    if busqueda and len(busqueda) == 8 and busqueda.isdigit():
        
        # Buscamos en TODAS las sedes (sin filtro de sede) para el conteo GLOBAL
        ventas_qs = Venta.objects.filter(
            numero_documento__iexact=busqueda
        ).select_related('viaje__ruta', 'viaje__vehiculo', 'asiento').order_by('-fecha_venta')
        
        if ventas_qs.exists():
            ultima_venta = ventas_qs.first()
            total_viajes = ventas_qs.count()
            
            # 3. Lógica de fidelización global (cada 12 viajes = 1 premio)
            viajes_para_premio = 12
            progreso_restante = total_viajes % viajes_para_premio
            proximo_premio_en = 0 if progreso_restante == 0 else (viajes_para_premio - progreso_restante)
            progreso_porcentaje = min(100, (progreso_restante / viajes_para_premio) * 100) if proximo_premio_en > 0 else 100
            
            # 4. Datos del cliente
            cliente_detalle = {
                'dni': busqueda,
                'nombre': ultima_venta.nombre_cliente or 'Cliente sin nombre',
                'telefono': ultima_venta.telefono_cliente or '-',
                'total_viajes': total_viajes,
                'proximo_premio_en': proximo_premio_en
            }
            
            # 5. Construir historial de viajes (últimos 20)
            for v in ventas_qs[:20]:
                viajes_cliente.append({
                    'fecha': v.fecha_venta.strftime('%d/%m/%Y'),
                    'hora': v.fecha_venta.strftime('%H:%M'),
                    'ruta': f"{v.viaje.ruta.origen} → {v.viaje.ruta.destino}",
                    'vehiculo': v.viaje.vehiculo.placa,
                    'asiento': v.asiento.numero_asiento if v.asiento else '-',
                    'monto': v.monto_total,
                    'estado': 'Completado'
                })

    # 6. Enviar al template
    contexto = {
        'usuario': usuario,
        'sede': sede,
        'busqueda_actual': busqueda,
        'cliente_detalle': cliente_detalle,
        'progreso_porcentaje': progreso_porcentaje,
        'viajes_cliente': viajes_cliente,
    }
    
    return render(request, 'clientes/fidelizacion.html', contexto)


from django.contrib import messages
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from core.models import Venta

@login_required
def historial_cliente(request, dni):
    """Vista dedicada para ver el historial de un cliente específico por DNI (usada desde el botón de la tabla)"""
    usuario = request.user
    
    # 1. Buscar ventas de este DNI en TODAS las sedes (conteo global)
    ventas_qs = Venta.objects.filter(
        numero_documento__iexact=dni
    ).select_related('viaje__ruta', 'viaje__vehiculo', 'asiento').order_by('-fecha_venta')
    
    if not ventas_qs.exists():
        messages.error(request, f'No se encontraron viajes para el DNI {dni}')
        return redirect('core:fidelizacion')
    
    # 2. Datos del cliente y progreso
    ultima_venta = ventas_qs.first()
    total_viajes = ventas_qs.count()
    
    viajes_para_premio = 12
    progreso_restante = total_viajes % viajes_para_premio
    proximo_premio_en = 0 if progreso_restante == 0 else (viajes_para_premio - progreso_restante)
    progreso_porcentaje = min(100, (progreso_restante / viajes_para_premio) * 100) if proximo_premio_en > 0 else 100
    
    cliente_detalle = {
        'dni': dni,
        'nombre': ultima_venta.nombre_cliente or 'Cliente sin nombre',
        'telefono': ultima_venta.telefono_cliente or '-',
        'total_viajes': total_viajes,
        'proximo_premio_en': proximo_premio_en
    }
    
    # 3. Construir historial (últimos 50 viajes)
    viajes_cliente = []
    for v in ventas_qs[:50]:
        viajes_cliente.append({
            'fecha': v.fecha_venta.strftime('%d/%m/%Y'),
            'hora': v.fecha_venta.strftime('%H:%M'),
            'ruta': f"{v.viaje.ruta.origen} → {v.viaje.ruta.destino}",
            'vehiculo': v.viaje.vehiculo.placa,
            'asiento': v.asiento.numero_asiento if v.asiento else '-',
            'monto': v.monto_total,
            'estado': 'Completado'
        })
        
    contexto = {
        'usuario': usuario,
        'cliente': cliente_detalle,
        'progreso_porcentaje': progreso_porcentaje,
        'viajes_cliente': viajes_cliente,
    }
    
    # ⚠️ IMPORTANTE: Cambia 'clientes/historial_cliente.html' por el nombre real 
    # de tu archivo de historial si se llama diferente (ej: 'clientes/historial.html')
    return render(request, 'clientes/historial_cliente.html', contexto)


@login_required
def buscar_cliente(request):
    from core.services.cliente_service import ClienteService
    
    usuario = request.user
    dni_busqueda = request.GET.get('dni', '').strip()
    
    # Capturar filtros
    ruta_id = request.GET.get('ruta') or None
    periodo = request.GET.get('periodo') or None
    fecha_desde = request.GET.get('fecha_desde') or None
    fecha_hasta = request.GET.get('fecha_hasta') or None
    page = request.GET.get('page', 1)
    
    cliente = None
    error = None
    
    if dni_busqueda:
        if len(dni_busqueda) == 8 and dni_busqueda.isdigit():
            cliente = ClienteService.buscar_por_dni(
                dni=dni_busqueda, 
                ruta_id=ruta_id, 
                periodo=periodo, 
                fecha_desde=fecha_desde, 
                fecha_hasta=fecha_hasta,
                page=page
            )
            if not cliente:
                error = f'No se encontraron ventas para el DNI {dni_busqueda}'
        else:
            error = 'El DNI debe tener exactamente 8 dígitos'
    
    # Para el dropdown de rutas
    rutas_activas = Ruta.objects.filter(activa=True).order_by('origen', 'destino')
    
    # Limpiar el 'page' de los parámetros GET para que la paginación funcione bien con los filtros
    get_params = request.GET.copy()
    if 'page' in get_params:
        del get_params['page']
    querystring = get_params.urlencode()
    
    contexto = {
        'usuario': usuario,
        'dni_busqueda': dni_busqueda,
        'cliente': cliente,
        'error': error,
        'rutas_activas': rutas_activas,
        'querystring': querystring, # Para los botones de paginación
        # Mantener valores seleccionados en los filtros
        'filtro_ruta': ruta_id,
        'filtro_periodo': periodo,
        'filtro_fecha_desde': fecha_desde,
        'filtro_fecha_hasta': fecha_hasta,
    }
    
    return render(request, 'clientes/buscar_cliente.html', contexto)

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


from django.contrib import messages
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from core.services.incidencia_service import IncidenciaService
from core.forms.incidencia_forms import IncidenciaForm # Asegúrate de tener este import

@login_required
def incidencias_lista_cajero(request, usuario, sede):
    """Lista de incidencias para CAJERO (solo su sede)"""
    estado_filtro = request.GET.get('estado', '')
    tipo_filtro = request.GET.get('tipo', '')
    
    # Obtenemos solo las incidencias de esta sede
    incidencias = IncidenciaService.obtener_incidencias_filtradas(
        sede=sede, 
        estado=estado_filtro, 
        tipo=tipo_filtro, 
        es_admin=False
    )
    
    contexto = {
        'usuario': usuario,
        'sede': sede,
        'es_admin': False,
        'incidencias': incidencias,
        'total_incidencias': incidencias.count(),
        'pendientes': incidencias.filter(estado='pendiente').count(),
        'en_proceso': incidencias.filter(estado='en_proceso').count(),
        'resueltas': incidencias.filter(estado='resuelta').count(),
        'estado_filtro': estado_filtro,
        'tipo_filtro': tipo_filtro,
    }
    # ⚠️ IMPORTANTE: Asegúrate de que este archivo exista en core/templates/cajero/
    return render(request, 'incidencias/incidencias_lista.html', contexto)


from django.contrib import messages
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from core.forms.incidencia_forms import IncidenciaForm

@login_required
def incidencia_nuevo(request):
    """Crear nueva incidencia"""
    usuario = request.user
    
    if request.method == 'POST':
        form = IncidenciaForm(request.POST)
        
        if form.is_valid():
            # 1. Crear incidencia sin guardar aún en la BD
            incidencia = form.save(commit=False)
            
            # 2. ✅ ASIGNAR LOS CAMPOS CON LOS NOMBRES EXACTOS DE TU MODELO
            incidencia.reportado_por = usuario
            
            # Asignar la sede del usuario
            if hasattr(usuario, 'sede') and usuario.sede:
                incidencia.sede_reporte = usuario.sede
            else:
                # Fallback por si el usuario no tiene sede asignada
                from core.models import Sede
                incidencia.sede_reporte = Sede.objects.first()
            
            # 3. Guardar finalmente en la base de datos
            incidencia.save()
            
            messages.success(request, '✅ Incidencia registrada correctamente')
            return redirect('core:incidencias_lista')  # Asegúrate que este nombre de URL sea el correcto
        else:
            messages.error(request, '❌ Por favor corrige los errores en el formulario')
    else:
        # GET: Mostrar formulario vacío (la sede se asignará automáticamente al guardar)
        form = IncidenciaForm()
    
    contexto = {
        'form': form,
        'usuario': usuario,
    }
    
    return render(request, 'incidencias/incidencia_nuevo.html', contexto)



@login_required
def incidencia_actualizar_estado(request, id):
    """Actualizar estado de incidencia (Admin)"""
    usuario = request.user
    
    # Verificar permisos de admin
    if not usuario.is_superuser and usuario.sede.nombre != 'Oficina Central':
        messages.error(request, 'No tienes permisos para cambiar el estado de incidencias')
        return redirect('core:incidencias_lista')
    
    try:
        incidencia = Incidencia.objects.get(id=id)
        
        if request.method == 'POST':
            nuevo_estado = request.POST.get('estado')
            solucion = request.POST.get('solucion', '')
            
            # Validar estado
            estados_validos = ['pendiente', 'en_proceso', 'resuelta']
            if nuevo_estado not in estados_validos:
                messages.error(request, 'Estado no válido')
                return redirect('core:incidencias_lista')
            
            # Actualizar
            incidencia.estado = nuevo_estado
            
            # Si es resuelta, guardar la solución
            if nuevo_estado == 'resuelta':
                incidencia.solucion = solucion
                incidencia.fecha_resolucion = timezone.now()
            
            incidencia.save()
            
            messages.success(request, f'✅ Estado actualizado a "{nuevo_estado}"')
            
    except Incidencia.DoesNotExist:
        messages.error(request, 'Incidencia no encontrada')
    except Exception as e:
        messages.error(request, f'Error al actualizar: {str(e)}')
    
    return redirect('core:incidencias_lista')


@login_required
def incidencia_ver_detalle(request, id):
    """Ver detalle completo de incidencia (AJAX)"""
    try:
        incidencia = Incidencia.objects.select_related(
            'sede_reporte', 
            'reportado_por'
        ).get(id=id)
        
        # Verificar permisos (admin o misma sede)
        if not request.user.is_superuser and incidencia.sede_reporte != request.user.sede:
            return JsonResponse({'error': 'No autorizado'}, status=403)
        
        data = {
            'id': incidencia.id,
            'tipo': incidencia.get_tipo_display(),
            'descripcion': incidencia.descripcion,
            'estado': incidencia.get_estado_display(),
            'sede': incidencia.sede_reporte.nombre,
            'reportado_por': incidencia.reportado_por.get_full_name() or incidencia.reportado_por.username,
            'fecha_reporte': incidencia.fecha_reporte.strftime('%d/%m/%Y %H:%M'),
            'solucion': incidencia.solucion or 'No aplica',
            'fecha_resolucion': incidencia.fecha_resolucion.strftime('%d/%m/%Y %H:%M') if incidencia.fecha_resolucion else 'Pendiente',
        }
        
        return JsonResponse(data)
        
    except Incidencia.DoesNotExist:
        return JsonResponse({'error': 'Incidencia no encontrada'}, status=404)


@login_required
def incidencia_eliminar(request, incidencia_id):
    """Eliminar una incidencia"""
    try:
        incidencia = Incidencia.objects.get(id=incidencia_id)
        
        # Verificar permisos (solo admin o el que la reportó)
        if request.user.is_superuser or incidencia.reportado_por == request.user:
            incidencia.delete()
            messages.success(request, '✅ Incidencia eliminada correctamente')
        else:
            messages.error(request, '❌ No tienes permisos para eliminar esta incidencia')
            
    except Incidencia.DoesNotExist:
        messages.error(request, '❌ La incidencia no existe')
    except Exception as e:
        messages.error(request, f'❌ Error al eliminar: {str(e)}')
    
    return redirect('core:incidencias_lista')




@login_required
def incidencia_ver(request, incidencia_id):
    """Ver detalle de una incidencia desde la sede"""
    incidencia = get_object_or_404(Incidencia, id=incidencia_id)
    
    # Verificar que la incidencia pertenezca a la sede del usuario
    if request.user.sede != incidencia.sede_reporte and not request.user.is_superuser:
        messages.error(request, '❌ No tienes permiso para ver esta incidencia.')
        return redirect('core:incidencias_lista')
    
    contexto = {
        'incidencia': incidencia,
        'sede': request.user.sede,
    }
    return render(request, 'incidencias/incidencia_ver.html', contexto)




# ==================== ADMIN - FIDELIZACIÓN ====================

@login_required
def fidelizacion_admin(request):
    """Vista de fidelización para ADMIN (ve todos los clientes de todas las sedes)"""
    usuario = request.user
    sede = usuario.sede
    
    # Verificar permisos de admin
    if sede.nombre != 'Oficina Central' and not usuario.is_superuser:
        messages.error(request, 'No tienes permisos para ver la fidelización global')
        return redirect('core:dashboard')
    
    filtro = request.GET.get('filtro', 'todos')
    busqueda = request.GET.get('q', '').strip()
    
    try:
        # ← SEDE=None: Trae a TODOS los clientes del sistema sin filtros de sucursal
        clientes = FidelizacionService.obtener_progreso_clientes(filtro=filtro, sede=None)
        kpis = FidelizacionService.obtener_kpis_fidelizacion(sede=None)
        
        if busqueda:
            clientes = [c for c in clientes if busqueda in c['dni'] or busqueda.lower() in c['nombre'].lower()]
            
    except Exception as e:
        logger.error(f"FIDELIZACION_ADMIN_VIEW - Error: {str(e)}", exc_info=True)
        clientes, kpis = [], {'total_clientes': 0, 'pendientes': 0, 'entregados': 0, 'cercanos': 0}
    
    contexto = {
        'usuario': usuario,
        'sede': sede,
        'es_admin': True,
        'clientes_fidelizacion': clientes,
        'stats': kpis,
        'filtro_actual': filtro,
        'busqueda_actual': busqueda
    }
    
    return render(request, 'admin/fidelizacion.html', contexto)

# ==================== ADMIN - VEHÍCULOS ====================

@login_required
def vehiculos_lista(request):
    """Lista de vehículos - CON RUTAS Y CHOFER"""
    usuario = request.user
    
    # QuerySet base con prefetch para ManyToMany
    if usuario.is_superuser or usuario.sede.nombre == 'Oficina Central':
        # Admin: ve todos los vehículos con sus rutas y chofer
        vehiculos_qs = Vehiculo.objects.all().prefetch_related('rutas_asignadas', 'chofer_asignado')
    else:
        # Cajero: ve vehículos de rutas de su sede (lógica adaptable)
        # Opcional: filtrar por rutas que pasan por su sede
        vehiculos_qs = Vehiculo.objects.filter(
            rutas_asignadas__origen__icontains=usuario.sede.nombre.split()[-1]
        ).prefetch_related('rutas_asignadas', 'chofer_asignado').distinct()
    
    total_vehiculos = vehiculos_qs.count()
    activos = vehiculos_qs.filter(activo=True).count()
    
    contexto = {
        'usuario': usuario,
        'vehiculos': vehiculos_qs,
        'total_vehiculos': total_vehiculos,
        'activos': activos,
        'es_admin': usuario.is_superuser or usuario.sede.nombre == 'Oficina Central',
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
                
                # ✅ EXTRAEMOS TODOS LOS CAMPOS, INCLUYENDO CHOFER Y RUTAS
                kwargs_vehiculo = {
                    'placa': form.cleaned_data['placa'],
                    'marca': form.cleaned_data['marca'],
                    'modelo': form.cleaned_data['modelo'],
                    'año': form.cleaned_data['año'],
                    'capacidad_asientos': form.cleaned_data['capacidad_asientos'],
                    'chofer_asignado': form.cleaned_data.get('chofer_asignado'),       # <-- AGREGADO
                    'rutas_asignadas': form.cleaned_data.get('rutas_asignadas'),       # <-- AGREGADO
                    'creado_por': usuario
                }
                
                # Llamamos al servicio desempaquetando el diccionario
                vehiculo = VehiculoService.crear_vehiculo(**kwargs_vehiculo)
                
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
            logger_vehiculo.info(f"VEHICULO_ELIMINAR - Eliminando vehículo {id} ({vehiculo.placa})")
            
            # Verificar si tiene viajes asociados
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
                logger_vehiculo.info(f"VEHICULO_ELIMINAR - Vehículo {id} eliminado")
                
        except Exception as e:
            messages.error(request, f'Error al eliminar: {str(e)}')
            logger_vehiculo.error(f"VEHICULO_ELIMINAR - Error: {str(e)}", exc_info=True)
    
    return redirect('core:vehiculos_lista')


# ==================== ADMIN - CHOFERES ====================

@login_required
def choferes_lista(request):
    """Lista de choferes reales (excluye la cuenta genérica 'chofer')"""
    usuario = request.user
    sede = usuario.sede
    
    # 1. Consulta base: Solo usuarios que son choferes, EXCLUYENDO la cuenta genérica
    base_query = Usuario.objects.filter(es_chofer=True).exclude(username='chofer')
    
    # 2. Aplicar filtro según el rol del usuario
    if sede.nombre == 'Oficina Central' or usuario.is_superuser:
        # El admin ve todos los choferes reales de todas las sedes
        choferes = base_query.select_related('sede')
    else:
        # El encargado ve solo los choferes reales de su propia sede
        choferes = base_query.filter(sede=sede).select_related('sede')
    
    # 3. Cálculos de estadísticas basados en la lista ya filtrada
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
    """Crear nuevo chofer"""
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
                
                # Generar contraseña temporal
                password_temporal = secrets.token_urlsafe(8)
                
                # 1. Determinar la sede asignada (la que eligió en el formulario o la del admin por defecto)
                sede_asignada = form.cleaned_data.get('sede') or usuario.sede
                
                # 2. Creamos el chofer (¡Ahora sí pasamos sede_asignada y rutas_asignadas!)
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
                    telefono=form.cleaned_data.get('telefono', ''),
                    sede_asignada=sede_asignada,          # ✅ ¡ESTE ERA EL QUE FALTABA!
                    creado_por=usuario,
                    rutas_asignadas=form.cleaned_data.get('rutas_asignadas') # ✅ El servicio lo procesa con **kwargs
                )

                # 3. Mensaje de éxito y redirección
                messages.success(request, f'Chofer {chofer.get_full_name()} creado exitosamente. Contraseña temporal: {password_temporal}')
                return redirect('core:choferes_lista') 
                
            except ValidationError as e:
                logger_chofer.error(f"CHOFER_NUEVO - Error de validación: {str(e)}")
                messages.error(request, str(e))
            except Exception as e:
                # Nota: Quité el emoji ❌ del log para evitar el error UnicodeEncodeError de Windows
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
                
                # Actualizar datos básicos
                chofer.username = form.cleaned_data['username']
                chofer.email = form.cleaned_data['email']
                chofer.first_name = form.cleaned_data['first_name']
                chofer.last_name = form.cleaned_data['last_name']
                chofer.telefono = form.cleaned_data.get('telefono', '')
                chofer.licencia_conducir = form.cleaned_data['licencia_conducir']
                chofer.categoria_licencia = form.cleaned_data['categoria_licencia']
                chofer.fecha_vencimiento_licencia = form.cleaned_data['fecha_vencimiento_licencia']
                chofer.activo = form.cleaned_data['activo']
                
                # ✅ CAMBIO: Actualizar rutas asignadas en lugar de sede
                if 'rutas_asignadas' in form.cleaned_data:
                    chofer.rutas_asignadas.set(form.cleaned_data['rutas_asignadas'])
                
                # Si hay contraseña nueva
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


from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model

@login_required
def chofer_eliminar(request, id):  # ✅ CAMBIADO: de 'chofer_id' a 'id'
    """Eliminar permanentemente un chofer de la base de datos"""
    if request.method == 'POST':
        Usuario = get_user_model()
        
        try:
            # 1. Buscamos al chofer usando 'id'
            chofer = Usuario.objects.get(id=id, es_chofer=True)
            
            # 2. ELIMINACIÓN PERMANENTE (Hard Delete)
            chofer.delete()
            
            messages.success(request, '✅ Chofer eliminado permanentemente de la base de datos.')
            
        except Usuario.DoesNotExist:
            messages.error(request, '❌ El chofer no existe.')
        except Exception as e:
            # Si el chofer está asignado a un vehículo o viaje, Django lo bloqueará
            messages.error(request, f'❌ No se puede eliminar: {str(e)}. Primero desasígnalo de vehículos o viajes.')
            
    # Redirigir a la lista (Asegúrate de que 'choferes_lista' sea el nombre correcto en tu urls.py)
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
    """Lista de usuarios/cajeros - EXCLUYE CHOFERES"""
    usuario = request.user
    sede = usuario.sede
    es_admin = usuario.is_superuser or sede.nombre == 'Oficina Central'
    
    if es_admin:
        # ✅ Solo usuarios que NO son choferes
        usuarios = Usuario.objects.filter(es_chofer=False).select_related('sede')
    else:
        # ✅ Solo de su sede y que NO son choferes
        usuarios = Usuario.objects.filter(sede=sede, es_chofer=False).select_related('sede')
        
    total_usuarios = usuarios.count()
    activos = usuarios.filter(activo=True).count()
    
    contexto = {
        'usuario': usuario,
        'sede': sede,
        'es_admin': es_admin,
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
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from core.models import Notificacion

# ==================== NOTIFICACIONES ====================

@login_required
def notificaciones_lista(request):
    """Muestra el centro de notificaciones del cajero/admin desde la Base de Datos"""
    usuario = request.user
    sede = usuario.sede
    
    # ✅ FILTRO MEJORADO: Usamos el ID de la sede para evitar problemas de nombres
    notificaciones_qs = Notificacion.objects.filter(
        sede_id=sede.id  
    ).order_by('-fecha_creacion')
    
    no_leidas_count = notificaciones_qs.filter(leida=False).count()
    
    contexto = {
        'usuario': usuario,
        'sede': sede,
        'notificaciones': notificaciones_qs,
        'no_leidas_count': no_leidas_count,
    }
    
    return render(request, 'notificaciones/lista.html', contexto)

@login_required
@require_POST
def marcar_notificacion_leida(request, notif_id):
    """AJAX: Marca una notificación específica como leída sin recargar la página"""
    try:
        notif = Notificacion.objects.get(id=notif_id)
        
        # ✅ Seguridad: verificar por ID de sede
        if notif.sede_id == request.user.sede.id or notif.sede is None:
            notif.leida = True
            notif.save()
            
            # Recalcular contador actualizado
            no_leidas = Notificacion.objects.filter(
                sede_id=request.user.sede.id, 
                leida=False
            ).count()
            
            return JsonResponse({'status': 'success', 'no_leidas': no_leidas})
            
        return JsonResponse({'status': 'error', 'message': 'No autorizado'}, status=403)
        
    except Notificacion.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'No encontrada'}, status=404)


@login_required
@require_POST
def marcar_todas_leidas(request):
    """Elimina todas las notificaciones leídas del usuario"""
    # ✅ ELIMINAR en lugar de solo marcar
    eliminadas = Notificacion.objects.filter(
        sede_id=request.user.sede.id,
        leida=True
    ).delete()[0]
    
    return JsonResponse({
        'status': 'success', 
        'no_leidas': 0,
        'eliminadas': eliminadas,
        'mensaje': f'Se eliminaron {eliminadas} notificaciones'
    })

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
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils import timezone
from django.db.models import Sum, Count
from datetime import datetime, timedelta
from core.models import Venta
import logging

logger = logging.getLogger('core.views')

@login_required
def reportes_unificados(request):
    usuario = request.user
    sede = usuario.sede
    # Ajusta esta condición según cómo identifiques al admin en tu modelo
    es_admin = (sede.nombre == 'Oficina Central' or getattr(usuario, 'is_superuser', False))
    
    periodo = request.GET.get('periodo', 'diario')
    fecha_str = request.GET.get('fecha', timezone.now().date().isoformat())
    
    try:
        fecha_seleccionada = datetime.strptime(fecha_str, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        fecha_seleccionada = timezone.now().date()
        
    hoy = timezone.now().date()
    
    # 1. QUERYSET BASE: Admin ve todo, Cajero SOLO su sede
    qs = Venta.objects.all() if es_admin else Venta.objects.filter(sede_venta=sede)
    
    chart_labels = []
    chart_data = []
    metodos_pago_labels = ['Efectivo', 'Yape', 'Plin', 'Tarjeta']
    metodos_pago_data = [0.0, 0.0, 0.0, 0.0]
    rutas_detalle = []
    ventas_detalle = []
    dia_rentable = "--"
    premios_entregados = 0 # Actualiza esto si tienes un modelo de canjes
    
    # 2. FILTROS POR PERÍODO Y CONSTRUCCIÓN DE GRÁFICOS
    if periodo == 'diario':
        qs = qs.filter(fecha_venta__date=fecha_seleccionada)
        titulo_periodo = f"Reporte del día {fecha_seleccionada.strftime('%d/%m/%Y')}"
        
        horas = [f"{h:02d}:00" for h in range(6, 22)] # 6am a 10pm
        chart_labels = horas
        for h in range(6, 22):
            monto = qs.filter(fecha_venta__hour=h).aggregate(total=Sum('monto_total'))['total'] or 0
            chart_data.append(float(monto))
            
    elif periodo == 'semanal':
        fecha_inicio = fecha_seleccionada - timedelta(days=6)
        qs = qs.filter(fecha_venta__date__range=[fecha_inicio, fecha_seleccionada])
        titulo_periodo = f"Reporte Semanal ({fecha_inicio.strftime('%d/%m')} - {fecha_seleccionada.strftime('%d/%m')})"
        
        dias_semana = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom']
        chart_labels = dias_semana
        data_semanal = []
        for i in range(7):
            dia = fecha_inicio + timedelta(days=i)
            monto = qs.filter(fecha_venta__date=dia).aggregate(total=Sum('monto_total'))['total'] or 0
            data_semanal.append(float(monto))
        chart_data = data_semanal
        
        if data_semanal and max(data_semanal) > 0:
            dia_rentable = dias_semana[data_semanal.index(max(data_semanal))]
            
    elif periodo == 'mensual':
        mes = int(request.GET.get('mes', hoy.month))
        anio = int(request.GET.get('anio', hoy.year))
        qs = qs.filter(fecha_venta__year=anio, fecha_venta__month=mes)
        titulo_periodo = f"Reporte de {datetime(anio, mes, 1).strftime('%B %Y')}"
        
        chart_labels = ['Sem 1', 'Sem 2', 'Sem 3', 'Sem 4']
        for i in range(1, 5):
            monto = qs.filter(fecha_venta__day__range=[(i-1)*7+1, i*7]).aggregate(total=Sum('monto_total'))['total'] or 0
            chart_data.append(float(monto))
            
    else: # anual
        anio = int(request.GET.get('anio', hoy.year))
        qs = qs.filter(fecha_venta__year=anio)
        titulo_periodo = f"Reporte Anual {anio}"
        
        chart_labels = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']
        for m in range(1, 13):
            monto = qs.filter(fecha_venta__month=m).aggregate(total=Sum('monto_total'))['total'] or 0
            chart_data.append(float(monto))

    # 3. CALCULAR KPIs GLOBALES (sobre el queryset YA filtrado)
    total_ventas = qs.aggregate(total=Sum('monto_total'))['total'] or 0
    total_pasajeros = qs.count() # Asumiendo 1 venta = 1 pasajero
    total_boletos = qs.count()
    total_viajes = qs.values('viaje').distinct().count()
    
    # 4. TABLA DE DETALLE (Últimas 15 ventas del período)
    ventas_qs_detalle = qs.select_related('viaje__ruta', 'viaje__vehiculo').order_by('-fecha_venta')[:15]
    for v in ventas_qs_detalle:
        # ⚠️ IMPORTANTE: Si tu campo se llama 'forma_pago' o similar, cámbialo aquí
        metodo = getattr(v, 'metodo_pago', 'efectivo') or 'efectivo'
        ventas_detalle.append({
            'hora': v.fecha_venta.strftime('%d/%m %H:%M') if periodo != 'diario' else v.fecha_venta.strftime('%H:%M'),
            'ruta': f"{v.viaje.ruta.origen} → {v.viaje.ruta.destino}" if v.viaje and v.viaje.ruta else 'N/A',
            'vehiculo': v.viaje.vehiculo.placa if v.viaje and v.viaje.vehiculo else 'N/A',
            'pasajeros': 1, 
            'metodo_pago': metodo.lower(),
            'monto': v.monto_total
        })
        
        # Acumular para el gráfico de métodos de pago (convertimos Decimal a float para el gráfico)
        monto_venta = float(v.monto_total) if v.monto_total else 0.0
        
        if metodo == 'efectivo': metodos_pago_data[0] += monto_venta
        elif metodo == 'yape': metodos_pago_data[1] += monto_venta
        elif metodo == 'plin': metodos_pago_data[2] += monto_venta
        else: metodos_pago_data[3] += monto_venta

    # 5. TABLA DE RENDIMIENTO POR RUTA (Solo Mensual/Anual)
    if periodo in ['mensual', 'anual']:
        rutas_qs = qs.values('viaje__ruta__origen', 'viaje__ruta__destino').annotate(
            viajes=Count('viaje', distinct=True),
            pasajeros=Count('id'),
            ingresos=Sum('monto_total')
        ).order_by('-ingresos')[:5]
        
        for r in rutas_qs:
            origen = r['viaje__ruta__origen'] or 'N/A'
            destino = r['viaje__ruta__destino'] or 'N/A'
            # Cálculo aproximado de ocupación (ajusta el '20' si tienes un campo de capacidad en Vehiculo)
            ocupacion = min(100, int((r['pasajeros'] / max(1, r['viajes'] * 20)) * 100))
            rendimiento = 'Excelente' if ocupacion >= 70 else 'Regular'
            
            rutas_detalle.append({
                'ruta': f"{origen} → {destino}",
                'viajes': r['viajes'],
                'pasajeros': r['pasajeros'],
                'ingresos': r['ingresos'] or 0,
                'ocupacion': ocupacion,
                'rendimiento': rendimiento
            })

    contexto = {
        'usuario': usuario,
        'sede': sede,
        'es_admin': es_admin,
        'periodo': periodo,
        'fecha_seleccionada': fecha_seleccionada.isoformat(),
        'titulo_periodo': titulo_periodo,
        'total_ventas': total_ventas,
        'total_viajes': total_viajes,
        'total_pasajeros': total_pasajeros,
        'total_boletos': total_boletos,
        'dia_rentable': dia_rentable,
        'premios_entregados': premios_entregados,
        'chart_labels': chart_labels,
        'chart_data': chart_data,
        'metodos_pago_labels': metodos_pago_labels,
        'metodos_pago_data': metodos_pago_data,
        'ventas_detalle': ventas_detalle,
        'rutas_detalle': rutas_detalle,
    }
    
    # ⚠️ VERIFICA QUE ESTA RUTA COINCIDA CON DONDE GUARDASTE EL HTML
    return render(request, 'reportes/reportes_unificados.html', contexto)


# ==================== BOLETOS ====================

@login_required
def ver_boleto(request, boleto_id):  # ← DEBE ser 'boleto_id' para coincidir con la URL
    """Muestra el boleto con modal de confirmación"""
    
    # Obtener la venta
    venta = get_object_or_404(Venta, id=boleto_id)
    
    # Preparar datos del boleto para el template
    boleto = {
        'numero': venta.numero_ticket,
        'pasajero': venta.nombre_cliente,
        'dni': venta.numero_documento,
        'ruc': getattr(venta, 'ruc_cliente', '') or '',  # Si no existe, devuelve vacío
        'razon_social': getattr(venta, 'razon_social', '') or '',
        'origen': venta.viaje.ruta.origen,
        'destino': venta.viaje.ruta.destino,
        'dia': venta.viaje.fecha_salida.strftime('%d'),
        'mes': venta.viaje.fecha_salida.strftime('%m'),
        'anio': venta.viaje.fecha_salida.strftime('%Y'),
        'hora': venta.viaje.hora_salida.strftime('%H:%M'),
        'asiento': venta.asiento.numero_asiento,
        'valor': venta.monto_total,
        'es_premiado': False,  # Aquí iría lógica de fidelización después
    }
    
    contexto = {
        'venta': venta,
        'boleto': boleto,  # ← Datos formateados para el template
    }
    
    return render(request, 'ventas/boleto.html', contexto)


def link_callback(uri, rel):
    """
    Convierte URIs de HTML a rutas absolutas del sistema de archivos
    para que xhtml2pdf pueda encontrar e incrustar imágenes/estilos.
    """
    result = None
 
    if uri.startswith(settings.STATIC_URL):
        path = os.path.join(settings.STATIC_ROOT if settings.STATIC_ROOT else '', uri.replace(settings.STATIC_URL, ""))
        if not os.path.isfile(path):
            for static_dir in getattr(settings, 'STATICFILES_DIRS', []):
                posible = os.path.join(static_dir, uri.replace(settings.STATIC_URL, ""))
                if os.path.isfile(posible):
                    path = posible
                    break
        result = path
 
    elif uri.startswith(settings.MEDIA_URL):
        result = os.path.join(settings.MEDIA_ROOT, uri.replace(settings.MEDIA_URL, ""))
 
    else:
        return uri
 
    if not os.path.isfile(result):
        raise Exception(
            f'[link_callback] No se encontró el archivo: {result} (uri original: {uri}). '
            f'Verifica que el logo esté en esa carpeta.'
        )
    return result
 

@login_required
def ver_ticket(request, venta_id):
    """Muestra la vista previa HTML del boleto"""
    venta = get_object_or_404(Venta, id=venta_id)
    return render(request, 'ventas/boleto.html', {'venta': venta})




import base64
import os
from django.conf import settings

@login_required
def descargar_boleto_pdf(request, boleto_id):
    """Genera y descarga el PDF del boleto con imagen en Base64"""
    
    try:
        from xhtml2pdf import pisa
    except ImportError:
        return HttpResponse("Error: Librería xhtml2pdf no instalada", status=500)
    
    from io import BytesIO
    from django.template.loader import render_to_string
    from django.http import HttpResponse
    from django.shortcuts import get_object_or_404
    from core.models import Venta
    
    venta = get_object_or_404(Venta, id=boleto_id)
    
    # ✅ 1. BUSCAR LA RUTA DE LA IMAGEN
    logo_filename = 'otiza.png'
    logo_path = None
    
    if hasattr(settings, 'STATICFILES_DIRS'):
        for static_dir in settings.STATICFILES_DIRS:
            possible_path = os.path.join(static_dir, 'images', logo_filename)
            if os.path.exists(possible_path):
                logo_path = possible_path
                print(f"✅ Logo encontrado en: {logo_path}")
                break
    
    # ✅ 2. CONVERTIR LA IMAGEN A BASE64
    logo_base64 = None
    if logo_path:
        try:
            with open(logo_path, "rb") as image_file:
                encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
                logo_base64 = f"data:image/png;base64,{encoded_string}"
                print("✅ Imagen convertida a Base64 exitosamente")
        except Exception as e:
            print(f"❌ Error al leer la imagen: {e}")
    else:
        print("❌ No se encontró la imagen en las rutas estáticas")
    
    # ✅ 3. PREPARAR DATOS
    numero_correlativo = venta.numero_correlativo or 0
    numero_formateado = f"{numero_correlativo:06d}"
    
    boleto = {
        'numero': numero_formateado,
        'pasajero': venta.nombre_cliente,
        'dni': venta.numero_documento,
        'telefono': venta.telefono_cliente,
        'ruc': venta.ruc_cliente or '',
        'razon_social': venta.razon_social or '',
        'origen': venta.viaje.ruta.origen,
        'destino': venta.viaje.ruta.destino,
        'dia': venta.viaje.fecha_salida.strftime('%d'),
        'mes': venta.viaje.fecha_salida.strftime('%m'),
        'anio': venta.viaje.fecha_salida.strftime('%Y'),
        'hora': venta.viaje.hora_salida.strftime('%H:%M'),
        'asiento': venta.asiento.numero_asiento,
        'valor': venta.monto_total,
        'es_premiado': False,
        'logo_base64': logo_base64,  # ✅ PASAMOS LA IMAGEN EN BASE64
    }
    
    # ✅ 4. GENERAR PDF
    html_string = render_to_string('ventas/boleto_pdf.html', {'boleto': boleto})
    result = BytesIO()
    
    if pisa is None:
        return HttpResponse("Error crítico: xhtml2pdf no cargó correctamente", status=500)
    
    pdf = pisa.CreatePDF(BytesIO(html_string.encode("UTF-8")), result, encoding="UTF-8")
    
    if pdf.err:
        return HttpResponse("Error al generar PDF", status=500)
    
    response = HttpResponse(result.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="boleto_{numero_formateado}.pdf"'
    
    return response




# ==================== ADMIN - ASIGNACIÓN DE VIAJES ====================

def _parsear_duracion(duracion_texto):
    """Parsea duración estimada y retorna (horas, minutos)"""
    duracion_texto = str(duracion_texto).lower().strip()
    horas = 0
    minutos = 0
    
    match_horas = re.search(r'(\d+)\s*(?:hora|horas|h)\b', duracion_texto)
    if match_horas:
        horas = int(match_horas.group(1))
    
    match_minutos = re.search(r'(\d+)\s*(?:min|minutos|m)\b', duracion_texto)
    if match_minutos:
        minutos = int(match_minutos.group(1))
    
    return horas, minutos


# ==================== LOGGER ====================
logger = logging.getLogger('core.viajes_views')


@login_required
def asignacion_viajes(request):
    """Lista de viajes para Admin/Cajeros - CON KPIs y comparación CORRECTA de fecha/hora (LOCAL)"""
    
    usuario = request.user
    sede = usuario.sede
    
    # ✅ FECHAS Y HORAS LOCALES (Lima) - Corrección del desfase UTC
    ahora_local = timezone.localtime(timezone.now())
    hoy = ahora_local.date()
    hora_actual = ahora_local.time()
    
    # ===== FILTRO DE FECHAS =====
    fecha_inicio_str = request.GET.get('fecha_inicio', hoy.strftime('%Y-%m-%d'))
    fecha_fin_str = request.GET.get('fecha_fin', (hoy + timedelta(days=7)).strftime('%Y-%m-%d'))
    
    try:
        fecha_inicio = datetime.strptime(fecha_inicio_str, '%Y-%m-%d').date()
        fecha_fin = datetime.strptime(fecha_fin_str, '%Y-%m-%d').date()
    except ValueError:
        fecha_inicio = hoy
        fecha_fin = hoy + timedelta(days=7)
    
    # ===== QUERYSET BASE (CORREGIDO: Todos ven todos los viajes) =====
    # Se eliminó el filtro `sede_salida=sede` para que cajeros vean la operación completa
    viajes_qs = Viaje.objects.filter(
        fecha_salida__range=[fecha_inicio, fecha_fin]
    ).select_related('ruta', 'vehiculo', 'chofer_asignado')
    
    # ===== KPIs (Usando hora local para comparaciones correctas) =====
    kpis_qs = viajes_qs.filter(estado='programado').filter(
        Q(fecha_salida__gt=hoy) | 
        Q(fecha_salida=hoy, hora_salida__gte=hora_actual)
    )
    viajes_programados = kpis_qs.count()
    asientos_disponibles = AsientoViaje.objects.filter(viaje__in=kpis_qs, estado='disponible').count()
    viajes_agotados = kpis_qs.annotate(libres=Count('asientos', filter=Q(asientos__estado='disponible'))).filter(libres=0).count()
    
    # ===== CALCULAR ESTADO VISUAL =====
    viajes_list = list(viajes_qs.order_by('-fecha_salida', '-hora_salida'))
    
    for viaje in viajes_list:
        fecha_hora_salida = datetime.combine(viaje.fecha_salida, viaje.hora_salida)
        if timezone.is_naive(fecha_hora_salida):
            fecha_hora_salida = timezone.make_aware(fecha_hora_salida)
            
        # Determinar estado visual comparando con la hora LOCAL
        if viaje.estado == 'cancelado':
            viaje.estado_display = 'cancelado'
        elif fecha_hora_salida < ahora_local:
            viaje.estado_display = 'finalizado'
        elif viaje.estado == 'en_curso':
            viaje.estado_display = 'en_curso'
        else:
            viaje.estado_display = 'programado'

    # ===== CONTEXTO =====
    contexto = {
        'usuario': usuario,
        'sede': sede,
        'es_admin': usuario.is_superuser or (sede and sede.nombre == 'Oficina Central'),
        
        'viajes': viajes_list, 
        'total_viajes': len(viajes_list),
        
        'fecha_inicio': fecha_inicio,
        'fecha_fin': fecha_fin,
        'hoy': hoy,
        'ahora': hora_actual,
        
        'viajes_programados': viajes_programados,
        'asientos_disponibles': asientos_disponibles,
        'viajes_agotados': viajes_agotados,
        'horarios_count': HorarioFijo.objects.filter(activa=True).count(),
    }
    
    return render(request, 'admin/asignacion_viajes.html', contexto)


@login_required
def viaje_nuevo(request):
    """Crear nuevo viaje (Admin) - CON CORRECCIÓN DE TIMEZONE"""
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
                
                # Obtener datos limpios
                ruta = form.cleaned_data['ruta']
                vehiculo = form.cleaned_data['vehiculo']
                sede_salida = form.cleaned_data['sede_salida']
                fecha_salida = form.cleaned_data['fecha_salida']
                hora_salida = form.cleaned_data['hora_salida']
                chofer_asignado = form.cleaned_data.get('chofer_asignado')
                
                # ✅ CORRECCIÓN: Comparar datetime completos en zona local (naive)
                ahora_local = timezone.localtime(timezone.now())  # Convierte UTC → America/Lima
                
                # Crear datetime completo del viaje (naive)
                viaje_dt = datetime.combine(fecha_salida, hora_salida)
                
                # Convertir ahora_local a naive para comparar correctamente
                ahora_naive = ahora_local.replace(tzinfo=None)
                
                logger_viaje.info(f"VIAJE_NUEVO - Ahora (naive): {ahora_naive}")
                logger_viaje.info(f"VIAJE_NUEVO - Viaje dt (naive): {viaje_dt}")
                
                # Validar que no sea en el pasado
                if viaje_dt < ahora_naive:
                    messages.error(
                        request, 
                        f' No puedes crear un viaje en el pasado. '
                        f'Ahora: {ahora_naive.strftime("%d/%m %H:%M")} | '
                        f'Viaje: {viaje_dt.strftime("%d/%m %H:%M")}'
                    )
                    return render(request, 'admin/viaje_form.html', {
                        'form': form, 
                        'usuario': usuario, 
                        'es_admin': True,
                        'choferes_por_ruta': json.dumps(_obtener_choferes_por_ruta())
                    })
                
                # Calcular hora de llegada
                horas, minutos = _parsear_duracion(ruta.duracion_estimada)
                salida_dt = datetime.combine(fecha_salida, hora_salida)
                llegada_dt = salida_dt + timedelta(hours=horas, minutes=minutos)
                
                # Crear viaje
                viaje = ViajeService.crear_viaje(
                    ruta=ruta,
                    vehiculo=vehiculo,
                    sede_salida=sede_salida,
                    chofer_asignado=chofer_asignado,
                    fecha_salida=fecha_salida,
                    hora_salida=hora_salida,
                    fecha_llegada=llegada_dt.date(),
                    hora_llegada=llegada_dt.time(),
                    creado_por=usuario
                )
                
                messages.success(request, f'✅ Viaje creado exitosamente. ID: {viaje.id}')
                logger_viaje.info(f"VIAJE_NUEVO - Viaje {viaje.id} creado")
                
                return redirect('core:asignacion_viajes')
                
            except Exception as e:
                logger_viaje.error(f"VIAJE_NUEVO - Error: {str(e)}", exc_info=True)
                messages.error(request, f'❌ Error al crear: {str(e)}')
        else:
            # Convierte los errores a texto plano sin emojis ni caracteres raros para el log
            error_msg = str(form.errors).replace('⚠️', '[WARNING]').encode('ascii', 'ignore').decode('ascii')
            logger_viaje.error(f"VIAJE_NUEVO - Formulario inválido: {error_msg}")
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
    else:
        form = ViajeForm(usuario=usuario)
    
    # Preparar datos para filtrar choferes por ruta
    contexto = {
        'usuario': usuario,
        'form': form,
        'es_admin': True,
        'choferes_por_ruta': json.dumps(_obtener_choferes_por_ruta()),
    }
    
    return render(request, 'admin/viaje_form.html', contexto)


def _obtener_choferes_por_ruta():
    """
    Retorna un diccionario con la estructura:
    {ruta_id: [{'id': chofer_id, 'nombre': 'Nombre Chofer'}, ...]}
    """
    
    choferes_data = {}
    
    for ruta in Ruta.objects.filter(activa=True):
        # Obtener choferes que tienen ESTA ruta en sus rutas_asignadas
        choferes_ruta = Usuario.objects.filter(
            es_chofer=True, 
            activo=True, 
            rutas_asignadas=ruta
        ).distinct()
        
        choferes_data[str(ruta.id)] = [
            {'id': c.id, 'nombre': f"{c.first_name} {c.last_name} ({c.username})"} 
            for c in choferes_ruta
        ]
    
    return choferes_data


@login_required
def viaje_editar(request, id):
    """Editar viaje existente (Admin) - CON VALIDACIÓN CORREGIDA DE FECHA+HORA"""
    
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
                logger_viaje.info(f"VIAJE_EDITAR - Formulario válido, actualizando...")
                
                # Obtener datos
                ruta = form.cleaned_data['ruta']
                fecha_salida = form.cleaned_data['fecha_salida']
                hora_salida = form.cleaned_data['hora_salida']
                chofer_asignado = form.cleaned_data.get('chofer_asignado')
                
                # ✅ VALIDACIÓN CORREGIDA: Comparar fecha + hora completos
                ahora_local = timezone.localtime(timezone.now())
                ahora_naive = ahora_local.replace(tzinfo=None)
                
                # Combinar fecha y hora del viaje para comparar
                viaje_dt = datetime.combine(fecha_salida, hora_salida)
                
                # Validar que no sea en el pasado
                if viaje_dt < ahora_naive:
                    messages.error(
                        request, 
                        f'❌ No puedes editar un viaje en el pasado. '
                        f'Ahora: {ahora_naive.strftime("%d/%m %H:%M")} | '
                        f'Viaje: {viaje_dt.strftime("%d/%m %H:%M")}'
                    )
                    return render(request, 'admin/viaje_form.html', {
                        'form': form, 
                        'usuario': usuario, 
                        'viaje': viaje, 
                        'es_admin': True,
                        'choferes_por_ruta': json.dumps(_obtener_choferes_por_ruta())
                    })
                
                # Calcular nueva hora de llegada si cambió
                if form.has_changed():
                    horas, minutos = _parsear_duracion(ruta.duracion_estimada)
                    salida_dt = datetime.combine(fecha_salida, hora_salida)
                    llegada_dt = salida_dt + timedelta(hours=horas, minutes=minutos)
                    
                    form.instance.fecha_llegada = llegada_dt.date()
                    form.instance.hora_llegada = llegada_dt.time()
                
                # Actualizar chofer si cambió
                if 'chofer_asignado' in form.changed_data:
                    form.instance.chofer_asignado = chofer_asignado
                
                # Guardar cambios
                form.save()
                
                messages.success(request, f'✅ Viaje {id} actualizado correctamente')
                logger_viaje.info(f"VIAJE_EDITAR - Viaje {id} actualizado")
                
                return redirect('core:asignacion_viajes')
                
            except Exception as e:
                logger_viaje.error(f"VIAJE_EDITAR - Error: {str(e)}", exc_info=True)
                messages.error(request, f'❌ Error al actualizar: {str(e)}')
        else:
            logger_viaje.error(f"VIAJE_EDITAR - Formulario inválido: {form.errors}")
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
    else:
        form = ViajeForm(instance=viaje, usuario=usuario)
    
    # Preparar datos para filtrar choferes por ruta
    contexto = {
        'usuario': usuario,
        'form': form,
        'viaje': viaje,
        'es_admin': True,
        'choferes_por_ruta': json.dumps(_obtener_choferes_por_ruta()),
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

@login_required
def generar_proximos_7_dias(request):
    """
    Genera viajes para los PRÓXIMOS 7 DÍAS desde HOY.
    Simple, directo y sin complicaciones.
    """
    
    if request.method != 'POST':
        messages.error(request, 'Método no permitido')
        return redirect('core:asignacion_viajes')
    
    if not (request.user.is_superuser or request.user.sede.nombre == 'Oficina Central'):
        messages.error(request, 'No tienes permisos')
        return redirect('core:asignacion_viajes')
    
    # ===== CONFIGURACIÓN =====
    hoy = timezone.now().date()
    dias_a_generar = 7
    viajes_creados = 0
    viajes_saltados = 0
    errores = []
    
    # ===== OBTENER HORARIOS FIJOS ACTIVOS =====
    horarios = HorarioFijo.objects.filter(activa=True).select_related('ruta', 'vehiculo')
    
    if not horarios.exists():
        messages.error(request, '⚠️ No hay horarios fijos configurados. Ve a "Horarios Fijos" para crear uno.')
        return redirect('core:asignacion_viajes')
    
    # ===== GENERAR PARA CADA DÍA (HOY + 6 DÍAS) =====
    for i in range(dias_a_generar):
        fecha_objetivo = hoy + timedelta(days=i)
        dia_semana = fecha_objetivo.weekday() + 1  # 1=Lun, 7=Dom
        
        for horario in horarios:
            # ¿Este horario aplica para este día de la semana?
            if str(dia_semana) not in horario.dias_semana:
                continue
            
            # ✅ VALIDACIÓN CORREGIDA: Verificar que la ruta tenga origen válido
            if not horario.ruta.origen:
                errores.append(f"Ruta {horario.ruta} no tiene origen definido")
                continue
            
            # Determinar sede_salida buscando por nombre de origen
            try:
                sede_salida = Sede.objects.get(nombre__icontains=horario.ruta.origen)
            except Sede.DoesNotExist:
                # Fallback: usar la sede del usuario o la primera disponible
                sede_salida = request.user.sede if hasattr(request.user, 'sede') else Sede.objects.first()
                if not sede_salida:
                    errores.append(f"No se pudo determinar sede para {horario.ruta.origen}")
                    continue
            
            # ¿Ya existe este viaje?
            existe = Viaje.objects.filter(
                ruta=horario.ruta,
                vehiculo=horario.vehiculo,
                fecha_salida=fecha_objetivo,
                hora_salida=horario.hora_salida
            ).exists()
            
            if existe:
                viajes_saltados += 1
                continue
            
            try:
                # Calcular hora de llegada (simple: +2 horas por defecto)
                duracion_texto = str(horario.ruta.duracion_estimada).lower()
                horas_duracion = 2
                if 'h' in duracion_texto:
                    try:
                        horas_duracion = int(duracion_texto.split('h')[0].strip())
                    except:
                        pass
                
                salida_dt = datetime.combine(fecha_objetivo, horario.hora_salida)
                llegada_dt = salida_dt + timedelta(hours=horas_duracion)
                
                # ✅ Crear viaje con sede_salida determinada
                viaje = Viaje.objects.create(
                    ruta=horario.ruta,
                    vehiculo=horario.vehiculo,
                    sede_salida=sede_salida,  # ← Determinada dinámicamente
                    fecha_salida=fecha_objetivo,
                    hora_salida=horario.hora_salida,
                    fecha_llegada=llegada_dt.date(),
                    hora_llegada=llegada_dt.time(),
                    estado='programado'
                )
                
                # Generar asientos automáticamente
                capacidad = horario.vehiculo.capacidad_asientos or 20
                for num in range(1, capacidad + 1):
                    AsientoViaje.objects.create(
                        viaje=viaje,
                        numero_asiento=str(num),
                        estado='disponible',
                        precio=horario.ruta.precio_base or 50
                    )
                
                viajes_creados += 1
                
            except Exception as e:
                errores.append(f"Error al crear viaje: {str(e)}")
    
    # ===== MOSTRAR RESULTADOS =====
    if viajes_creados > 0:
        messages.success(request, f'✅ Se crearon {viajes_creados} viajes para los próximos 7 días')
    
    if viajes_saltados > 0:
        messages.info(request, f'ℹ️ Se omitieron {viajes_saltados} viajes que ya existían')
    
    if errores:
        for error in errores[:3]:  # Mostrar solo los primeros 3
            messages.error(request, f'❌ {error}')
    
    return redirect('core:asignacion_viajes')

@login_required
def horarios_fijos_lista(request):
    """Lista y crea horarios fijos"""
    if not (request.user.is_superuser or request.user.sede.nombre == 'Oficina Central'):
        messages.error(request, 'No tienes permisos')
        return redirect('core:dashboard')
    
    horarios = HorarioFijo.objects.select_related('ruta', 'vehiculo').all()
    
    if request.method == 'POST':
        ruta_id = request.POST.get('ruta')
        vehiculo_id = request.POST.get('vehiculo')
        hora_salida = request.POST.get('hora_salida')
        dias_semana = request.POST.get('dias_semana', '1,2,3,4,5,6,7')
        
        try:
            HorarioFijo.objects.create(
                ruta_id=ruta_id,
                vehiculo_id=vehiculo_id,
                hora_salida=hora_salida,
                dias_semana=dias_semana,
                activa=True
            )
            messages.success(request, '✅ Horario fijo creado')
        except Exception as e:
            messages.error(request, f'Error: {str(e)}')
        
        return redirect('core:horarios_fijos_lista')
    
    contexto = {
        'usuario': request.user,
        'horarios': horarios,
        'rutas': Ruta.objects.filter(activa=True),
        'vehiculos': Vehiculo.objects.filter(activo=True),
    }
    return render(request, 'admin/horarios_fijos.html', contexto)

@login_required
def horario_fijo_editar(request, id):
    """Edita un horario fijo"""
    if not (request.user.is_superuser or request.user.sede.nombre == 'Oficina Central'):
        messages.error(request, 'No tienes permisos')
        return redirect('core:dashboard')
    
    horario = get_object_or_404(HorarioFijo, id=id)
    
    if request.method == 'POST':
        horario.ruta_id = request.POST.get('ruta')
        horario.vehiculo_id = request.POST.get('vehiculo')
        horario.hora_salida = request.POST.get('hora_salida')
        horario.dias_semana = request.POST.get('dias_semana', '1,2,3,4,5,6,7')
        horario.save()
        messages.success(request, '✅ Horario actualizado')
        return redirect('core:horarios_fijos_lista')
    
    contexto = {
        'usuario': request.user,
        'horario': horario,
        'rutas': Ruta.objects.filter(activa=True),
        'vehiculos': Vehiculo.objects.filter(activo=True),
    }
    return render(request, 'admin/horario_fijo_editar.html', contexto)


@login_required
def horario_fijo_eliminar(request, id):
    """Elimina un horario fijo"""
    if not (request.user.is_superuser or request.user.sede.nombre == 'Oficina Central'):
        messages.error(request, 'No tienes permisos')
        return redirect('core:dashboard')
    
    if request.method == 'POST':
        try:
            horario = HorarioFijo.objects.get(id=id)
            horario.delete()
            messages.success(request, '✅ Horario eliminado')
        except:
            messages.error(request, 'Error al eliminar')
    
    return redirect('core:horarios_fijos_lista')

@login_required
def crear_viaje_regreso(request, viaje_id):
    """
    Crea automáticamente un viaje de regreso basado en un viaje existente.
    Ej: Si vino Trujillo→Julcán, crea Julcán→Trujillo con el mismo vehículo.
    """
    
    if request.method != 'POST':
        messages.error(request, 'Método no permitido')
        return redirect('core:asignacion_viajes')
    
    # Obtener viaje original
    viaje_origen = get_object_or_404(Viaje, id=viaje_id)
    
    # Buscar ruta inversa
    try:
        ruta_regreso = Ruta.objects.get(
            origen=viaje_origen.ruta.destino,
            destino=viaje_origen.ruta.origen
        )
    except Ruta.DoesNotExist:
        messages.error(request, f'No existe ruta de regreso: {viaje_origen.ruta.destino} → {viaje_origen.ruta.origen}')
        return redirect('core:asignacion_viajes')
    
    # Calcular hora de salida (30 min después de la llegada, configurable)
    hora_llegada = datetime.combine(viaje_origen.fecha_salida, viaje_origen.hora_llegada)
    hora_salida_regreso = (hora_llegada + timedelta(minutes=30)).time()
    
    # Determinar sede de salida (la sede de destino del viaje original)
    try:
        sede_salida = Sede.objects.get(nombre__icontains=viaje_origen.ruta.destino)
    except Sede.DoesNotExist:
        sede_salida = request.user.sede
    
    # Verificar si ya existe
    existe = Viaje.objects.filter(
        ruta=ruta_regreso,
        vehiculo=viaje_origen.vehiculo,
        fecha_salida=viaje_origen.fecha_salida,
        hora_salida=hora_salida_regreso
    ).exists()
    
    if existe:
        messages.warning(request, 'Ya existe un viaje de regreso para esta fecha/hora')
        return redirect('core:asignacion_viajes')
    
    # Calcular hora de llegada del regreso
    duracion_texto = str(ruta_regreso.duracion_estimada).lower()
    horas_duracion = 2
    if 'h' in duracion_texto:
        try:
            horas_duracion = int(duracion_texto.split('h')[0].strip())
        except:
            pass
    
    salida_dt = datetime.combine(viaje_origen.fecha_salida, hora_salida_regreso)
    llegada_dt = salida_dt + timedelta(hours=horas_duracion)
    
    # Crear viaje de regreso
    viaje_regreso = Viaje.objects.create(
        ruta=ruta_regreso,
        vehiculo=viaje_origen.vehiculo,
        sede_salida=sede_salida,
        fecha_salida=viaje_origen.fecha_salida,
        hora_salida=hora_salida_regreso,
        fecha_llegada=llegada_dt.date(),
        hora_llegada=llegada_dt.time(),
        estado='programado'
    )
    
    # Generar asientos automáticamente
    capacidad = viaje_origen.vehiculo.capacidad_asientos or 20
    for num in range(1, capacidad + 1):
        AsientoViaje.objects.create(
            viaje=viaje_regreso,
            numero_asiento=str(num),
            estado='disponible',
            precio=ruta_regreso.precio_base or 50
        )
    
    messages.success(request, f'✅ Viaje de regreso creado: {ruta_regreso} a las {hora_salida_regreso.strftime("%H:%M")}')
    return redirect('core:asignacion_viajes')


@login_required
def procesar_reserva_pago(request, asiento_id):
    """Convierte una reserva en venta confirmada"""
    
    asiento = get_object_or_404(AsientoViaje, id=asiento_id, estado='reservado')
    
    # Verificar permisos
    if request.user.sede != asiento.viaje.sede_salida and not request.user.is_superuser:
        messages.error(request, 'No tienes permisos para confirmar esta reserva')
        return redirect('core:venta_pasajes')
    
    # Cambiar estado a vendido
    asiento.estado = 'vendido'
    asiento.save()
    
    # Crear venta (puedes reutilizar tu lógica existente)
    Venta.objects.create(
        viaje=asiento.viaje,
        asiento=asiento,
        sede_venta=request.user.sede,
        cajero=request.user,
        nombre_cliente=asiento.nombre_reserva,
        telefono_cliente=asiento.telefono_reserva,
        monto_total=asiento.viaje.ruta.precio_base,
        metodo_pago='efectivo',  # O pedir que elijan
        numero_ticket=f"RES-{asiento.viaje.id}-{asiento.numero_asiento}"
    )
    
    messages.success(request, f'✅ Reserva del asiento {asiento.numero_asiento} confirmada como venta')
    return redirect('core:venta_pasajes')

@login_required
def procesar_reserva(request):
    """Procesa la RESERVA de un asiento"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método no permitido'}, status=400)
    
    viaje_id = request.POST.get('viaje_id')
    asiento_numero = request.POST.get('asiento_numero')
    dni_pasajero = request.POST.get('dni_pasajero', '')
    nombre = request.POST.get('nombre_pasajero')  # ← Este es el nombre
    telefono = request.POST.get('telefono_pasajero')
    
    if not all([viaje_id, asiento_numero, nombre]):
        return JsonResponse({'success': False, 'error': 'Faltan datos'}, status=400)
    
    try:
        viaje = get_object_or_404(Viaje, id=viaje_id)
        asiento = get_object_or_404(AsientoViaje, viaje=viaje, numero_asiento=asiento_numero)
        
        if asiento.estado != 'disponible':
            return JsonResponse({'success': False, 'error': 'Asiento no disponible'}, status=409)
        
        # ✅ GUARDAR EL NOMBRE CORRECTAMENTE
        asiento.estado = 'reservado'
        asiento.nombre_reserva = nombre.strip().upper()  # ← Guardar nombre limpio
        asiento.numero_documento_reserva = dni_pasajero
        asiento.telefono_reserva = telefono
        asiento.fecha_reserva = timezone.now()
        asiento.save()
        
        return JsonResponse({
            'success': True,
            'asiento_id': asiento.id,
            'asiento': asiento.numero_asiento,
            'tipo': 'reserva',
            'nombre': nombre  # ← Devolver el nombre
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
    

# ==================== LIBERAR RESERVA ====================
@login_required
@require_POST
def liberar_reserva(request, asiento_id):
    """Libera un asiento reservado (solo la sede de origen puede hacerlo)"""
    try:
        asiento = AsientoViaje.objects.select_related('viaje').get(id=asiento_id)
        
        # ✅ VERIFICACIÓN DE SEGURIDAD: Solo la sede de origen puede liberar
        if request.user.sede.id != asiento.viaje.sede_salida.id:
            return JsonResponse({
                'success': False, 
                'error': f'⚠️ No autorizado. Solo la sede de origen ({asiento.viaje.sede_salida.nombre}) puede liberar esta reserva.'
            })
        
        if asiento.estado != 'reservado':
            return JsonResponse({'success': False, 'error': 'El asiento no está reservado'})
        
        # ✅ LIBERAR ASIENTO
        asiento.estado = 'disponible'
        asiento.nombre_reserva = ''
        asiento.numero_documento_reserva = ''
        asiento.telefono_reserva = ''
        asiento.email_reserva = ''
        asiento.ruc_reserva = ''
        asiento.razon_social_reserva = ''
        asiento.metodo_pago_reserva = ''
        asiento.reservado_por_chofer = False
        asiento.tipo_reserva_chofer = ''
        asiento.chofer_reserva = None
        asiento.fecha_reserva = None
        asiento.save()
        
        return JsonResponse({
            'success': True,
            'asiento': asiento.numero_asiento,
            'mensaje': f'✅ Asiento {asiento.numero_asiento} liberado correctamente.'
        })
        
    except AsientoViaje.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Asiento no encontrado'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def confirmacion_venta(request, venta_id):
    """Muestra la confirmación de venta con resumen y botones"""
    
    venta = get_object_or_404(Venta, id=venta_id)
    
    # Preparar datos del boleto para impresión
    boleto = {
        'numero': venta.numero_ticket,
        'pasajero': venta.nombre_cliente,
        'dni': venta.numero_documento,
        'ruc': venta.ruc_cliente or '',
        'razon_social': venta.razon_social or '',
        'origen': venta.viaje.ruta.origen,
        'destino': venta.viaje.ruta.destino,
        'dia': venta.viaje.fecha_salida.strftime('%d'),
        'mes': venta.viaje.fecha_salida.strftime('%m'),
        'anio': venta.viaje.fecha_salida.strftime('%Y'),
        'hora': venta.viaje.hora_salida.strftime('%H:%M'),
        'asiento': venta.asiento.numero_asiento,
        'valor': venta.monto_total,
        'es_premiado': False,
    }
    
    contexto = {
        'venta': venta,
        'boleto': boleto,
    }
    
    return render(request, 'ventas/confirmacion_venta.html', contexto)


# ==================== CONFIRMAR PAGO DE RESERVA NORMAL (SIN COBRO DEL CHOFER) ==========
@login_required
@require_POST
def confirmar_pago_reserva(request, asiento_id):
    """La cajera confirma el pago de una reserva (normal o sin cobro del chofer)"""
    try:
        asiento = AsientoViaje.objects.select_related('viaje', 'viaje__ruta', 'chofer_reserva').get(id=asiento_id)
        
        # ✅ VERIFICACIÓN DE SEGURIDAD: Solo la sede de origen puede confirmar
        if request.user.sede.id != asiento.viaje.sede_salida.id:
            return JsonResponse({
                'success': False, 
                'error': f'⚠️ No autorizado. Solo la sede de origen ({asiento.viaje.sede_salida.nombre}) puede procesar esta reserva.'
            })
        
        if asiento.estado != 'reservado':
            return JsonResponse({'success': False, 'error': 'El asiento no está en estado reservado'})
        
        # ✅ Retornar datos del asiento para que el frontend muestre el formulario completo
        return JsonResponse({
            'success': True,
            'asiento_id': asiento.id,
            'numero_asiento': asiento.numero_asiento,
            'nombre_reserva': asiento.nombre_reserva or '',
            'dni_reserva': asiento.numero_documento_reserva or '',
            'telefono_reserva': asiento.telefono_reserva or '',
            'email_reserva': asiento.email_reserva or '',
            'ruc_reserva': asiento.ruc_reserva or '',
            'razon_social_reserva': asiento.razon_social_reserva or '',
            'metodo_pago_reserva': asiento.metodo_pago_reserva or 'efectivo',
            'precio': float(asiento.precio or 0),
            'ruta': f"{asiento.viaje.ruta.origen} → {asiento.viaje.ruta.destino}",
            'fecha': asiento.viaje.fecha_salida.strftime('%d/%m/%Y'),
            'hora': asiento.viaje.hora_salida.strftime('%H:%M'),
            'viaje_id': asiento.viaje.id,
            'reservado_por_chofer': asiento.reservado_por_chofer,
            'tipo_reserva_chofer': asiento.tipo_reserva_chofer or '',
        })
        
    except AsientoViaje.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Asiento no encontrado'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


# ==================== PROCESAR PAGO FINAL DE RESERVA ==================== 
from django.utils import timezone
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.db.models import Max
import random

# ✅ FUNCIÓN PARA GENERAR NÚMERO CORRELATIVO
def generar_numero_correlativo():
    """Genera el siguiente número correlativo de boleto"""
    from core.models import Venta
    ultimo_numero = Venta.objects.aggregate(max_num=Max('numero_correlativo'))['max_num']
    if ultimo_numero is None:
        return 1
    return ultimo_numero + 1


@login_required
@require_POST
def procesar_pago_reserva_final(request):
    """Procesa el pago final de una reserva completando todos los campos"""
    try:
        asiento_id = request.POST.get('asiento_id')
        asiento = AsientoViaje.objects.select_related('viaje', 'viaje__ruta').get(id=asiento_id)
        
        # ✅ VERIFICACIÓN DE SEGURIDAD: Solo la sede de origen
        if request.user.sede.id != asiento.viaje.sede_salida.id:
            return JsonResponse({
                'success': False, 
                'error': f'⚠️ No autorizado. Solo la sede de origen puede procesar esta reserva.'
            })
        
        if asiento.estado != 'reservado':
            return JsonResponse({'success': False, 'error': 'El asiento ya no está reservado'})
        
        # ✅ Obtener datos del formulario
        email_pasajero = request.POST.get('email_pasajero', '').strip()
        ruc_cliente = request.POST.get('ruc_cliente', '').strip()
        razon_social = request.POST.get('razon_social', '').strip().upper()
        metodo_pago = request.POST.get('metodo_pago', 'efectivo')
        
        # ✅ GENERAR NÚMERO DE TICKET INTERNO (por si lo necesitas de respaldo)
        ahora = timezone.now()
        fecha_str = ahora.strftime('%y%m%d')
        random_str = f"{random.randint(1000, 9999)}"
        numero_ticket = f"TKT-{fecha_str}-{random_str}"
        
        # ✅ GENERAR NÚMERO CORRELATIVO (000001, 000002...) DE FORMA SEGURA
        ultimo_numero = Venta.objects.aggregate(max_num=Max('numero_correlativo'))['max_num']
        numero_correlativo = (ultimo_numero or 0) + 1
        
        # ✅ CREAR LA VENTA (Venta ya está importada arriba en el archivo)
        venta = Venta.objects.create(
            tipo_documento='ticket',
            numero_documento=asiento.numero_documento_reserva or '',
            nombre_cliente=asiento.nombre_reserva or 'Pasajero',
            telefono_cliente=asiento.telefono_reserva or '',
            email_cliente=email_pasajero,
            ruc_cliente=ruc_cliente,
            razon_social=razon_social,
            asiento=asiento,
            viaje=asiento.viaje,
            sede_venta=request.user.sede,
            cajero=request.user,
            monto_total=asiento.precio,
            numero_ticket=numero_ticket,
            numero_correlativo=numero_correlativo,  # ✅ SE GUARDA EL CORRELATIVO
            metodo_pago=metodo_pago,
            observaciones=f"Reserva confirmada - Pago procesado en sede"
        )
        
        # ✅ MARCAR ASIENTO COMO VENDIDO
        asiento.estado = 'vendido'
        asiento.fecha_venta = timezone.now()
        asiento.email_reserva = email_pasajero
        asiento.ruc_reserva = ruc_cliente
        asiento.razon_social_reserva = razon_social
        asiento.metodo_pago_reserva = metodo_pago
        asiento.save()
        
        # Marcar notificaciones como leídas
        Notificacion.objects.filter(
            sede_id=request.user.sede.id,
            tipo='reserva_chofer',
            leida=False
        ).update(leida=True)
        
        return JsonResponse({
            'success': True,
            'venta_id': venta.id,
            'numero_ticket': f"{numero_correlativo:06d}",  # ✅ Devuelve el correlativo formateado (ej: 000031)
            'numero_correlativo': f"{numero_correlativo:06d}",
            'asiento': asiento.numero_asiento,
            'ruta': f"{asiento.viaje.ruta.origen} → {asiento.viaje.ruta.destino}",
            'fecha': asiento.viaje.fecha_salida.strftime('%d/%m/%Y'),
            'hora': asiento.viaje.hora_salida.strftime('%H:%M'),
            'pasajero': asiento.nombre_reserva or 'Sin nombre',
            'total': float(asiento.precio or 0),
            'mensaje': f'✅ Pago confirmado. Asiento {asiento.numero_asiento} vendido.'
        })
        
    except AsientoViaje.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Asiento no encontrado'})
    except Exception as e:
        import traceback
        traceback.print_exc() # Esto te mostrará el error exacto en consola si vuelve a fallar
        return JsonResponse({'success': False, 'error': f'Error interno: {str(e)}'})


from django.utils import timezone
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from core.models import HojaRuta, Viaje
from core.forms import HojaRutaForm

@login_required
def hoja_ruta_nuevo(request):
    """Crear nueva hoja de ruta"""
    sede = request.user.sede
    
    viaje_id = request.GET.get('viaje_id') or request.POST.get('viaje')
    
    if not viaje_id:
        messages.error(request, '⚠️ Debes seleccionar un viaje primero.')
        return redirect('core:hoja_ruta_lista')
        
    try:
        viaje = Viaje.objects.get(id=viaje_id, sede_salida=sede)
    except Viaje.DoesNotExist:
        messages.error(request, '❌ El viaje no es válido.')
        return redirect('core:hoja_ruta_lista')

    if HojaRuta.objects.filter(viaje=viaje).exists():
        messages.warning(request, '⚠️ Ya existe una hoja de ruta para este viaje.')
        return redirect('core:hoja_ruta_lista')

    if request.method == 'POST':
        form = HojaRutaForm(request.POST)
        if form.is_valid():
            hoja = form.save(commit=False)
            hoja.sede = sede
            hoja.viaje = viaje
            
            # Auto-llenar datos
            hoja.fecha_inicio = viaje.fecha_salida
            hoja.fecha_llegada = getattr(viaje, 'fecha_llegada_estimada', None) or viaje.fecha_salida
            hoja.hora_salida = viaje.hora_salida
            hoja.hora_llegada = getattr(viaje, 'hora_llegada_estimada', None) or viaje.hora_salida
            hoja.placa = viaje.vehiculo.placa if viaje.vehiculo else 'S/N'
            
            if not hoja.lugar_embarque:
                hoja.lugar_embarque = viaje.ruta.origen if viaje.ruta else sede.nombre
            if not hoja.lugar_desembarque:
                hoja.lugar_desembarque = viaje.ruta.destino if viaje.ruta else 'Destino'

            contador = HojaRuta.objects.filter(sede=sede).count() + 1
            hoja.numero_documento = f"HR-{sede.nombre[:3].upper()}-{timezone.now().strftime('%Y%m%d')}-{contador:04d}"
            
            hoja.save()
            
            # ✅ ACTUALIZAR LA SESIÓN CON EL NUEVO ID
            request.session['ultima_hoja_ruta_id'] = hoja.id
            
            messages.success(request, '✅ Hoja de Ruta generada exitosamente.')
            return redirect('core:hoja_ruta_lista')
    else:
        initial_data = {
            'lugar_embarque': viaje.ruta.origen if viaje.ruta else '',
            'lugar_desembarque': viaje.ruta.destino if viaje.ruta else '',
        }
        chofer = viaje.chofer_asignado
        if chofer:
            initial_data['conductor1_nombre'] = chofer.get_full_name()
            initial_data['conductor1_licencia'] = getattr(chofer, 'licencia_conducir', getattr(chofer, 'brevete', ''))
        
        form = HojaRutaForm(initial=initial_data)
        
    return render(request, 'documentos/hoja_ruta_form.html', {
        'form': form,
        'sede': sede,
        'viaje': viaje
    })


# ==================== MANIFIESTO ====================

logger = logging.getLogger('core.manifiestos')


# ==================== 1. LISTA DE VIAJES DISPONIBLES ====================

@login_required
def viajes_disponibles_manifiesto(request):
    """Lista de viajes para generar manifiesto (Unificada)"""
    sede = request.user.sede
    fecha = request.GET.get('fecha', timezone.now().date().isoformat())
    
    # Obtenemos TODOS los viajes de la fecha
    viajes = Viaje.objects.filter(
        sede_salida=sede,
        fecha_salida=fecha
    ).select_related('ruta', 'vehiculo', 'chofer_asignado').annotate(
        total_asientos=Count('asientos'),
        asientos_vendidos=Count('asientos', filter=Q(asientos__estado='vendido')),
        tiene_manifiesto=Count('manifiesto')
    ).order_by('hora_salida')
    
    contexto = {
        'sede': sede,
        'viajes': viajes,
        'fecha': fecha,
    }
    return render(request, 'documentos/viajes_disponibles.html', contexto)

@login_required
def manifiesto_eliminar(request, manifiesto_id):
    """Elimina un manifiesto para que el viaje vuelva a estar pendiente"""
    if request.method == 'POST':
        try:
            manifiesto = Manifiesto.objects.get(id=manifiesto_id, sede=request.user.sede)
            manifiesto.delete()
            
            # ✅ LIMPIAR LA SESIÓN SI EL ID ELIMINADO ERA EL ÚLTIMO
            if request.session.get('ultimo_manifiesto_id') == manifiesto_id:
                del request.session['ultimo_manifiesto_id']
            
            messages.success(request, '✅ Manifiesto eliminado. El viaje está disponible nuevamente.')
        except Manifiesto.DoesNotExist:
            messages.error(request, '❌ El manifiesto no existe.')
            
    return redirect('core:viajes_disponibles_manifiesto')

# ==================== 2. GENERAR / EDITAR MANIFIESTO ====================
@login_required
def manifiesto_generar(request, viaje_id):
    """Generar manifiesto desde un viaje (auto-llenado)"""
    sede = request.user.sede
    viaje = get_object_or_404(Viaje, id=viaje_id, sede_salida=sede)
    
    # Verificar si ya existe manifiesto para este viaje
    if Manifiesto.objects.filter(viaje=viaje).exists():
        messages.warning(request, '⚠️ Ya existe un manifiesto para este viaje')
        return redirect('core:viajes_disponibles_manifiesto')
    
    if request.method == 'POST':
        form = ManifiestoForm(request.POST)
        formset = PasajeroFormSet(request.POST)
        
        if form.is_valid() and formset.is_valid():
            manifiesto = form.save(commit=False)
            manifiesto.sede = sede
            manifiesto.viaje = viaje
            manifiesto.fecha_viaje = viaje.fecha_salida
            
            # ✅ GENERAR NÚMERO CORRELATIVO (000001, 000002, etc.)
            from django.db.models import Max
            ultimo_numero = Manifiesto.objects.filter(sede=sede).aggregate(max_num=Max('numero_correlativo'))['max_num']
            manifiesto.numero_correlativo = (ultimo_numero or 0) + 1
            
            # ✅ GENERAR NÚMERO DE DOCUMENTO CON FORMATO ANTIGUO (por compatibilidad)
            contador = manifiesto.numero_correlativo
            manifiesto.numero_documento = f"MAN-{sede.nombre[:3].upper()}-{timezone.now().strftime('%Y%m%d')}-{contador:04d}"
            manifiesto.save()
            
            # Guardar pasajeros
            pasajeros = formset.save(commit=False)
            for p in pasajeros:
                p.manifiesto = manifiesto
                p.save()
            
            # ✅ ACTUALIZAR LA SESIÓN CON EL NUEVO ID
            request.session['ultimo_manifiesto_id'] = manifiesto.id
            
            messages.success(request, '✅ Manifiesto generado exitosamente. El PDF se abrirá en una nueva pestaña.')
            return redirect('core:viajes_disponibles_manifiesto')
    else:
        # Auto-llenar formulario con datos del viaje
        chofer = viaje.chofer_asignado
        initial_data = {
            'conductor_nombre': chofer.get_full_name() if chofer else '',
            'placa': viaje.vehiculo.placa if viaje.vehiculo else '',
            'hora_salida': viaje.hora_salida,
            'brevete': chofer.licencia_conducir if chofer else '',
            'destino_origen': viaje.ruta.origen if viaje.ruta else '',
            'destino_final': viaje.ruta.destino if viaje.ruta else '',
        }
        
        # Auto-llenar pasajeros desde ventas
        ventas = Venta.objects.filter(
            viaje=viaje,
        ).select_related('asiento').order_by('asiento__numero_asiento')
        
        initial_pasajeros = []
        for idx, v in enumerate(ventas[:16], start=1):
            initial_pasajeros.append({
                'numero': idx,
                'nombre': (v.nombre_cliente or 'CLIENTE').strip(),
                'dni': (v.numero_documento or '00000000').strip().replace('/', ''),
                'destino': (viaje.ruta.destino if viaje.ruta else '').strip()
            })
        
        form = ManifiestoForm(initial=initial_data)
        formset = PasajeroFormSet(initial=initial_pasajeros)
    
    contexto = {
        'form': form,
        'formset': formset,
        'viaje': viaje,
        'sede': sede,
    }
    return render(request, 'documentos/manifiesto_generar.html', contexto)

# ==================== 3. GENERAR PDF ====================
import base64
import os
from django.conf import settings
from django.db.models import Max
from io import BytesIO
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from django.contrib.auth.decorators import login_required
from xhtml2pdf import pisa

@login_required
def manifiesto_pdf(request, id):
    """Genera y descarga el PDF del manifiesto con Logo Base64 y Número Correlativo"""
    manifiesto = get_object_or_404(Manifiesto, id=id, sede=request.user.sede)
    
    # ✅ 1. BUSCAR Y CONVERTIR LOGO A BASE64
    logo_filename = 'otiza.png'
    logo_path = None
    
    if hasattr(settings, 'STATICFILES_DIRS'):
        for static_dir in settings.STATICFILES_DIRS:
            possible_path = os.path.join(static_dir, 'images', logo_filename)
            if os.path.exists(possible_path):
                logo_path = possible_path
                break
    
    logo_base64 = None
    if logo_path:
        try:
            with open(logo_path, "rb") as image_file:
                encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
                logo_base64 = f"data:image/png;base64,{encoded_string}"
                print("✅ Logo del manifiesto convertido a Base64")
        except Exception as e:
            print(f"❌ Error al leer imagen del manifiesto: {e}")
    
    # ✅ 2. FORMATEAR NÚMERO CORRELATIVO (001 - 000001)
    sede_codigo = f"{manifiesto.sede.id:03d}"  # Ej: 001, 002, 003
    numero_correlativo = manifiesto.numero_correlativo or 0
    numero_manifiesto = f"{sede_codigo} - {numero_correlativo:06d}"  # Ej: 001 - 000001
    
    # ✅ 3. PREPARAR CONTEXTO
    context = {
        'manifiesto': manifiesto,
        'logo_base64': logo_base64,              # ✅ Logo en Base64
        'numero_manifiesto': numero_manifiesto,  # ✅ Número formateado
    }
    
    # ✅ 4. GENERAR PDF
    html_string = render_to_string('documentos/manifiesto_pdf.html', context)
    
    result = BytesIO()
    pisa_status = pisa.CreatePDF(BytesIO(html_string.encode('UTF-8')), result, encoding='UTF-8')
    
    if pisa_status.err:
        return HttpResponse('Error al generar el PDF', status=500)
    
    response = HttpResponse(result.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="Manifiesto_{numero_manifiesto.replace(' - ', '_')}.pdf"'
    
    return response


# ==================== 4. HISTORIAL DE MANIFIESTOS ====================
@login_required
def manifiestos_lista(request):
    """Lista histórica de manifiestos generados, filtrable por fecha"""
    sede = request.user.sede
    fecha_filtro = request.GET.get('fecha', timezone.now().date().isoformat())
    
    manifiestos_qs = Manifiesto.objects.filter(
        sede=sede,
        fecha_emision=fecha_filtro
    ).select_related('viaje', 'viaje__ruta').order_by('-fecha_creacion')
    
    contexto = {
        'sede': sede,
        'manifiestos': manifiestos_qs,
        'fecha_filtro': fecha_filtro,
        'total': manifiestos_qs.count(),
    }
    return render(request, 'documentos/manifiestos_lista.html', contexto)


@login_required
def manifiesto_limpiar_sesion(request):
    """Limpia el ID del último manifiesto de la sesión"""
    if request.method == 'POST' and 'ultimo_manifiesto_id' in request.session:
        del request.session['ultimo_manifiesto_id']
    from django.http import JsonResponse
    return JsonResponse({'status': 'ok'})

@login_required
def hoja_ruta_lista(request):
    """Lista de viajes para generar hoja de ruta (Unificada)"""
    sede = request.user.sede
    fecha = request.GET.get('fecha', timezone.now().date().isoformat())
    
    # Obtenemos TODOS los viajes de la fecha
    viajes = Viaje.objects.filter(
        sede_salida=sede,
        fecha_salida=fecha
    ).select_related('ruta', 'vehiculo', 'chofer_asignado').annotate(
        total_asientos=Count('asientos'),
        asientos_vendidos=Count('asientos', filter=Q(asientos__estado='vendido')),
        tiene_hoja_ruta=Count('hoja_ruta') # Cuenta si tiene hoja asociada
    ).order_by('hora_salida')
    
    contexto = {
        'sede': sede,
        'viajes': viajes,
        'fecha': fecha,
    }
    return render(request, 'documentos/hoja_ruta_lista.html', contexto)

@login_required
def hoja_ruta_eliminar(request, hoja_id):
    """Elimina una hoja de ruta"""
    if request.method == 'POST':
        try:
            hoja = HojaRuta.objects.get(id=hoja_id, sede=request.user.sede)
            hoja.delete()
            
            # ✅ LIMPIAR LA SESIÓN SI EL ID ELIMINADO ERA EL ÚLTIMO
            if request.session.get('ultima_hoja_ruta_id') == hoja_id:
                del request.session['ultima_hoja_ruta_id']
            
            messages.success(request, '✅ Hoja de ruta eliminada. El viaje está disponible nuevamente.')
        except HojaRuta.DoesNotExist:
            messages.error(request, ' La hoja de ruta no existe.')
            
    return redirect('core:hoja_ruta_lista')


@login_required
def hoja_ruta_historial(request):
    """Historial de hojas de ruta generadas con filtro por fecha"""
    sede = request.user.sede
    fecha_filtro = request.GET.get('fecha', timezone.now().date().isoformat())
    
    # Filtrar hojas de ruta de esta sede por fecha de emision
    hojas_qs = HojaRuta.objects.filter(
        sede=sede,
        fecha_emision=fecha_filtro
    ).select_related('viaje').order_by('-fecha_creacion')
    
    contexto = {
        'sede': sede,
        'hojas': hojas_qs,
        'fecha_filtro': fecha_filtro,
        'total': hojas_qs.count(),
    }
    return render(request, 'documentos/hoja_ruta_historial.html', contexto)

@login_required
def hoja_ruta_generar(request, viaje_id):
    """Generar hoja de ruta desde un viaje específico"""
    sede = request.user.sede
    viaje = get_object_or_404(Viaje, id=viaje_id, sede_salida=sede)
    
    # Verificar si ya existe hoja de ruta
    if HojaRuta.objects.filter(viaje=viaje).exists():
        messages.warning(request, '⚠️ Ya existe una hoja de ruta para este viaje')
        return redirect('core:hoja_ruta_lista')
    
    if request.method == 'POST':
        form = HojaRutaForm(request.POST)
        if form.is_valid():
            hoja = form.save(commit=False)
            hoja.sede = sede
            hoja.viaje = viaje
            
            # Auto-llenar campos obligatorios
            hoja.fecha_inicio = viaje.fecha_salida
            hoja.fecha_llegada = getattr(viaje, 'fecha_llegada_estimada', viaje.fecha_salida) or viaje.fecha_salida
            hoja.hora_salida = viaje.hora_salida
            hoja.hora_llegada = getattr(viaje, 'hora_llegada_estimada', viaje.hora_salida) or viaje.hora_salida
            hoja.placa = viaje.vehiculo.placa if viaje.vehiculo else ''
            
            # Lugares
            hoja.lugar_embarque = form.cleaned_data.get('lugar_embarque', viaje.ruta.origen if viaje.ruta else '')
            hoja.lugar_desembarque = form.cleaned_data.get('lugar_desembarque', viaje.ruta.destino if viaje.ruta else '')
            
            # Número único
            contador = HojaRuta.objects.filter(sede=sede).count() + 1
            hoja.numero_documento = f"HR-{sede.nombre[:3].upper()}-{timezone.now().strftime('%Y%m%d')}-{contador:04d}"
            
            hoja.save()
            
            messages.success(request, '✅ Hoja de Ruta generada exitosamente.')
            
            # 💡 REDIRECCIÓN CORREGIDA: Guarda y regresa al historial/lista.
            # No redirigir directamente al PDF para evitar descargas/aperturas no deseadas.
            return redirect('core:hoja_ruta_historial') 
            
    else:
        initial_data = {
            'lugar_embarque': viaje.ruta.origen if viaje.ruta else '',
            'lugar_desembarque': viaje.ruta.destino if viaje.ruta else '',
        }
        
        chofer = viaje.chofer_asignado
        if chofer:
            initial_data.update({
                'conductor1_nombre': chofer.get_full_name(),
                'conductor1_licencia': getattr(chofer, 'licencia_conducir', getattr(chofer, 'brevete', '')),
            })
        
        form = HojaRutaForm(initial=initial_data)
    
    return render(request, 'documentos/hoja_ruta_generar.html', {
        'form': form,
        'viaje': viaje,
        'sede': sede
    })


@login_required
def hoja_ruta_pdf(request, id):
    """Generar vista de PDF de la hoja de ruta"""
    hoja = get_object_or_404(HojaRuta, id=id, sede=request.user.sede)
    
    # Renderizamos la plantilla HTML ajustada
    context = {'hoja': hoja}
    html_string = render_to_string('documentos/hoja_ruta_pdf.html', context)
    
    response = HttpResponse(content_type='application/pdf')
    # inline = Visualizar en pestaña nueva sin forzar descarga local automática
    response['Content-Disposition'] = f'inline; filename="Hoja_Ruta_{hoja.numero_documento}.pdf"'
    
    pisa_status = pisa.CreatePDF(BytesIO(html_string.encode('UTF-8')), dest=response, encoding='UTF-8')
    
    if pisa_status.err:
        return HttpResponse('Error al generar el PDF', status=500)
    
    return response

@login_required
def hoja_ruta_limpiar_sesion(request):
    """Limpia el ID de la última hoja de ruta de la sesión (llamado vía AJAX)"""
    if request.method == 'POST' and 'ultima_hoja_ruta_id' in request.session:
        del request.session['ultima_hoja_ruta_id']
    from django.http import JsonResponse
    return JsonResponse({'status': 'ok'})



# 2. SELECCIÓN DE IDENTIDAD (Jala los choferes reales de la BD)
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from core.models import Usuario

@login_required
def chofer_seleccionar_identidad(request):
    """El chofer genérico selecciona su identidad y verifica con DNI"""
    
    # Si ya tiene identidad en sesión, que pase directo al panel
    if request.session.get('chofer_id'):
        return redirect('core:panel_chofer')
    
    # Jalamos los choferes reales de la BD (excluyendo la cuenta genérica 'chofer')
    choferes_reales = Usuario.objects.filter(
        es_chofer=True, 
        activo=True
    ).exclude(username='chofer').order_by('first_name')
    
    if request.method == 'POST':
        chofer_id = request.POST.get('chofer_id')
        dni_ingresado = request.POST.get('dni_ingresado', '').strip()
        
        if not chofer_id or not dni_ingresado:
            messages.error(request, '❌ Debes seleccionar tu nombre e ingresar tu DNI.')
            return render(request, 'chofer/seleccionar_identidad.html', {'choferes': choferes_reales})
        
        try:
            # Buscamos al chofer seleccionado en la BD
            chofer_obj = Usuario.objects.get(id=chofer_id, es_chofer=True, activo=True)
            
            # 🔒 VALIDACIÓN DE SEGURIDAD ESTRICTA:
            # El DNI ingresado debe ser EXACTAMENTE IGUAL al username (DNI) del chofer en la BD
            if chofer_obj.username != dni_ingresado:
                messages.error(
                    request, 
                    f'❌ ACCESO DENEGADO: El DNI ingresado NO coincide con {chofer_obj.get_full_name()}. Verifica tus datos.'
                )
                # Retornamos el formulario de nuevo para que lo intente correctamente
                return render(request, 'chofer/seleccionar_identidad.html', {'choferes': choferes_reales})
            
            # Si todo está correcto, guardamos en sesión
            request.session['chofer_id'] = chofer_obj.id
            request.session['chofer_nombre'] = chofer_obj.get_full_name() or chofer_obj.username
            request.session['chofer_dni'] = chofer_obj.username
            
            messages.success(request, f'✅ Identidad verificada. Bienvenido, {request.session["chofer_nombre"]}')
            return redirect('core:panel_chofer')
            
        except Usuario.DoesNotExist:
            messages.error(request, '❌ Error al verificar la identidad en el sistema.')
            
    return render(request, 'chofer/seleccionar_identidad.html', {'choferes': choferes_reales})

# 2. Panel Principal del Chofer
from django.utils import timezone
from zoneinfo import ZoneInfo

@login_required
def panel_chofer(request):
    """Panel principal del chofer - Muestra todos los viajes de la fecha filtrada"""
    if not request.session.get('chofer_id'):
        return redirect('core:chofer_seleccionar_identidad')
    
    # Fecha y hora local (Lima)
    lima_tz = ZoneInfo('America/Lima')
    ahora_local = timezone.now().astimezone(lima_tz)
    hoy = ahora_local.date()
    hora_actual = ahora_local.time()
    
    # Filtros
    fecha_filtro = request.GET.get('fecha', hoy.isoformat())
    ruta_filtro = request.GET.get('ruta', '')
    
    # Query base: TODOS los viajes de la fecha filtrada
    viajes_qs = Viaje.objects.filter(
        fecha_salida=fecha_filtro
    ).select_related('ruta', 'vehiculo', 'chofer_asignado', 'sede_salida')
    
    if ruta_filtro:
        viajes_qs = viajes_qs.filter(ruta_id=ruta_filtro)
    
    viajes_qs = viajes_qs.order_by('hora_salida')
    rutas = Ruta.objects.filter(activa=True).order_by('origen', 'destino')
    
    # ✅ ANOTAR cada viaje con si está pasado o no
    viajes_con_estado = []
    for viaje in viajes_qs:
        esta_pasado = False
        if fecha_filtro < hoy.isoformat():
            # Fecha anterior a hoy = pasado
            esta_pasado = True
        elif fecha_filtro == hoy.isoformat() and viaje.hora_salida and viaje.hora_salida < hora_actual:
            # Hoy pero hora ya pasó = pasado
            esta_pasado = True
        
        viajes_con_estado.append({
            'viaje': viaje,
            'esta_pasado': esta_pasado
        })
    
    contexto = {
        'viajes_con_estado': viajes_con_estado,
        'rutas': rutas,
        'fecha_filtro': fecha_filtro,
        'ruta_filtro': ruta_filtro,
        'total_viajes': len(viajes_con_estado),
        'hoy': hoy,
        'chofer_nombre': request.session.get('chofer_nombre'),
    }
    
    return render(request, 'chofer/panel_chofer.html', contexto)



from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from core.models import Viaje, AsientoViaje, Notificacion

@login_required
def chofer_reservar_asientos(request, viaje_id):
    """Vista para que el chofer reserve asientos (CON o SIN pago)"""
    if not request.session.get('chofer_id'):
        return redirect('core:chofer_seleccionar_identidad')
    
    viaje = get_object_or_404(Viaje, id=viaje_id)
    
    # Obtener o crear asientos del viaje
    asientos = []
    for i in range(1, viaje.vehiculo.capacidad_asientos + 1):
        asiento, creado = AsientoViaje.objects.get_or_create(
            viaje=viaje,
            numero_asiento=str(i),
            defaults={
                'estado': 'disponible',
                'precio': viaje.ruta.precio_base
            }
        )
        asientos.append(asiento)
    
    if request.method == 'POST':
        asiento_numero = request.POST.get('asiento_numero')
        tipo_reserva = request.POST.get('tipo_reserva')  # 'con_cobro' o 'sin_cobro'
        dni_pasajero = request.POST.get('dni_pasajero', '').strip()
        nombre_pasajero = request.POST.get('nombre_pasajero', '').strip().upper()
        telefono_pasajero = request.POST.get('telefono_pasajero', '').strip()
        
        # Campos adicionales (solo para con_cobro)
        email_pasajero = request.POST.get('email_pasajero', '').strip()
        ruc_cliente = request.POST.get('ruc_cliente', '').strip()
        razon_social = request.POST.get('razon_social', '').strip().upper()
        metodo_pago = request.POST.get('metodo_pago', 'efectivo')
        
        asiento = AsientoViaje.objects.filter(viaje=viaje, numero_asiento=asiento_numero).first()
        
        if not asiento:
            messages.error(request, f'❌ El asiento {asiento_numero} no existe')
            return redirect('core:chofer_reservar_asientos', viaje_id=viaje_id)
        
        if asiento.estado != 'disponible':
            messages.error(request, f'❌ El asiento {asiento_numero} ya está {asiento.estado}')
            return redirect('core:chofer_reservar_asientos', viaje_id=viaje_id)
        
        # ✅ RESERVAR ASIENTO (MORADO)
        asiento.estado = 'reservado'
        asiento.nombre_reserva = nombre_pasajero
        asiento.numero_documento_reserva = dni_pasajero
        asiento.telefono_reserva = telefono_pasajero
        asiento.reservado_por_chofer = True
        asiento.tipo_reserva_chofer = tipo_reserva
        asiento.nombre_chofer_reserva = request.session.get('chofer_nombre')
        asiento.chofer_reserva = request.user
        asiento.fecha_reserva = timezone.now()
        
        # Guardar campos adicionales si existen
        if email_pasajero:
            asiento.email_reserva = email_pasajero
        if ruc_cliente:
            asiento.ruc_reserva = ruc_cliente
        if razon_social:
            asiento.razon_social_reserva = razon_social
        if metodo_pago and tipo_reserva == 'con_cobro':
            asiento.metodo_pago_reserva = metodo_pago
            
        asiento.save()
        
        # ✅ CREAR NOTIFICACIÓN SOLO PARA LA SEDE DE ORIGEN DEL VIAJE
        tipo_mensaje = "CON COBRO" if tipo_reserva == 'con_cobro' else "SIN COBRO"
        mensaje_cobro = "El chofer YA COBRÓ el pasaje." if tipo_reserva == 'con_cobro' else "El pasajero debe pagar en sede."
        
        # ✅ La notificación va a la sede de ORIGEN del viaje (sede_salida)
        # Si el viaje es Trujillo → Julcán, solo Trujillo recibe la notificación
        sede_origen = viaje.sede_salida
        
        if sede_origen:
            try:
                Notificacion.objects.create(
                    titulo=f"🚌 RESERVA DE CHOFER - {tipo_mensaje}",
                    descripcion=(
                        f"Asiento {asiento_numero} reservado por {request.session.get('chofer_nombre')}.\n"
                        f"Pasajero: {nombre_pasajero} (DNI: {dni_pasajero})\n"
                        f"Ruta: {viaje.ruta.origen} → {viaje.ruta.destino}\n"
                        f"{mensaje_cobro}"
                    ),
                    tipo='reserva_chofer',
                    categoria='alerta',
                    sede=sede_origen,  # ✅ SOLO la sede de origen recibe la notificación
                    leida=False
                )
                print(f"✅ Notificación creada para sede de origen: {sede_origen.nombre}")
            except Exception as e:
                print(f"❌ Error al crear notificación: {e}")
        else:
            print(f"❌ El viaje no tiene sede de salida asignada")
        
        tipo_texto = "con cobro" if tipo_reserva == 'con_cobro' else "sin cobro"
        messages.success(
            request, 
            f'✅ Asiento {asiento_numero} reservado {tipo_texto}.\n'
            f'La sede {viaje.sede_salida.nombre} ha sido notificada.'
        )
        return redirect('core:panel_chofer')
    
    contexto = {
        'viaje': viaje,
        'asientos': asientos,
        'chofer_nombre': request.session.get('chofer_nombre'),
    }
    return render(request, 'chofer/reservar_asientos.html', contexto)

# 4. Cerrar Sesión del Chofer
from django.contrib.auth import logout
from django.shortcuts import redirect
from django.contrib import messages

def chofer_logout(request):
    """Cerrar sesión del chofer completamente"""
    
    # 1. Cierra la sesión de Django
    logout(request)
    
    # 2. Limpia las variables de sesión del chofer
    if 'chofer_id' in request.session:
        del request.session['chofer_id']
    if 'chofer_nombre' in request.session:
        del request.session['chofer_nombre']
    if 'chofer_dni' in request.session:
        del request.session['chofer_dni']
    
    messages.info(request, '👋 Sesión cerrada correctamente')
    
    # 3. Redirige al login general
    return redirect('core:login')


@login_required
def chofer_incidencias(request):
    """Lista de incidencias reportadas por el chofer"""
    if not request.session.get('chofer_id'):
        return redirect('core:chofer_seleccionar_identidad')
    
    chofer_nombre = request.session.get('chofer_nombre')
    chofer_id = request.session.get('chofer_id')
    
    # ✅ CAMBIAR 'fecha_creacion' POR 'fecha_reporte'
    incidencias = Incidencia.objects.filter(
        reportado_por_id=chofer_id
    ).order_by('-fecha_reporte')
    
    contexto = {
        'incidencias': incidencias,
        'chofer_nombre': chofer_nombre,
    }
    return render(request, 'chofer/incidencias.html', contexto)


from django import forms
from core.models import Incidencia

# Formulario específico para choferes (sin campo de sede)
class ChoferIncidenciaForm(forms.ModelForm):
    class Meta:
        model = Incidencia
        fields = ['tipo', 'descripcion']
        widgets = {
            'tipo': forms.Select(attrs={
                'class': 'w-full px-4 py-2.5 border border-slate-300 rounded-lg focus:ring-2 focus:ring-emerald-500 text-sm'
            }),
            'descripcion': forms.Textarea(attrs={
                'class': 'w-full px-4 py-2.5 border border-slate-300 rounded-lg focus:ring-2 focus:ring-emerald-500 text-sm',
                'rows': 5,
                'placeholder': 'Describe detalladamente la incidencia...'
            }),
        }

@login_required
def chofer_nueva_incidencia(request):
    """Vista para que el chofer reporte una nueva incidencia"""
    if not request.session.get('chofer_id'):
        return redirect('core:chofer_seleccionar_identidad')
    
    chofer_nombre = request.session.get('chofer_nombre')
    chofer_id = request.session.get('chofer_id')
    
    if request.method == 'POST':
        form = ChoferIncidenciaForm(request.POST)
        if form.is_valid():
            incidencia = form.save(commit=False)
            # ✅ GUARDAR EL CHOFER REAL, NO EL USUARIO GENÉRICO
            incidencia.reportado_por_id = chofer_id  # ID del chofer real
            incidencia.sede_reporte = request.user.sede  # Unidad Móvil
            incidencia.estado = 'pendiente'
            incidencia.save()
            
            messages.success(request, '✅ Incidencia reportada correctamente. Será revisada por el administrador.')
            return redirect('core:chofer_incidencias')
    else:
        form = ChoferIncidenciaForm()
    
    contexto = {
        'form': form,
        'chofer_nombre': chofer_nombre,
    }
    return render(request, 'chofer/nueva_incidencia.html', contexto)


@login_required
def chofer_eliminar_incidencia(request, incidencia_id):
    """Eliminar incidencia reportada por el chofer (solo si está pendiente)"""
    if not request.session.get('chofer_id'):
        return redirect('core:chofer_seleccionar_identidad')
    
    chofer_id = request.session.get('chofer_id')
    
    try:
        incidencia = Incidencia.objects.get(id=incidencia_id, reportado_por_id=chofer_id)
        
        # Solo se puede eliminar si está pendiente
        if incidencia.estado == 'pendiente':
            incidencia.delete()
            messages.success(request, '✅ Incidencia eliminada correctamente.')
        else:
            messages.error(request, '❌ No se puede eliminar una incidencia que ya está en proceso o resuelta.')
    except Incidencia.DoesNotExist:
        messages.error(request, '❌ Incidencia no encontrada.')
    
    return redirect('core:chofer_incidencias')

@login_required
def chofer_ver_incidencia(request, incidencia_id):
    """Ver detalle de una incidencia"""
    if not request.session.get('chofer_id'):
        return redirect('core:chofer_seleccionar_identidad')
    
    chofer_id = request.session.get('chofer_id')
    
    try:
        incidencia = Incidencia.objects.get(id=incidencia_id, reportado_por_id=chofer_id)
        contexto = {
            'incidencia': incidencia,
            'chofer_nombre': request.session.get('chofer_nombre'),
        }
        return render(request, 'chofer/ver_incidencia.html', contexto)
    except Incidencia.DoesNotExist:
        messages.error(request, '❌ Incidencia no encontrada.')
        return redirect('core:chofer_incidencias')

    

from django.db.models import Sum, Count, Max
from core.models import Venta, AsientoViaje, Viaje, Ruta, Notificacion, Usuario
import random
from django.utils import timezone

@login_required
@require_POST
def confirmar_pago_reserva_chofer(request, asiento_id):
    """La cajera confirma que el pasajero de reserva de chofer llegó (CON COBRO)"""
    try:
        asiento = AsientoViaje.objects.select_related('viaje', 'viaje__ruta', 'chofer_reserva').get(id=asiento_id)
        
        # ✅ VERIFICACIÓN DE SEGURIDAD: Solo la sede de origen puede confirmar
        if request.user.sede.id != asiento.viaje.sede_salida.id:
            return JsonResponse({
                'success': False, 
                'error': f'⚠️ No autorizado. Solo la sede de origen ({asiento.viaje.sede_salida.nombre}) puede confirmar esta reserva.'
            })
        
        # Verificaciones
        if not asiento.reservado_por_chofer:
            return JsonResponse({'success': False, 'error': 'Este asiento no es una reserva de chofer'})
        
        if asiento.tipo_reserva_chofer != 'con_cobro':
            return JsonResponse({'success': False, 'error': 'Esta reserva no es de tipo "con cobro"'})
        
        if asiento.estado != 'reservado':
            return JsonResponse({'success': False, 'error': 'El asiento no está en estado reservado'})
        
        # ✅ GENERAR NÚMERO DE TICKET INTERNO
        ahora = timezone.now()
        fecha_str = ahora.strftime('%y%m%d')
        random_str = f"{random.randint(1000, 9999)}"
        numero_ticket = f"TKT-{fecha_str}-{random_str}"
        
        # ✅ GENERAR NÚMERO CORRELATIVO (000001, 000002...)
        ultimo_numero = Venta.objects.aggregate(max_num=Max('numero_correlativo'))['max_num']
        numero_correlativo = (ultimo_numero or 0) + 1
        
        nombre_chofer = ""
        if asiento.chofer_reserva:
            nombre_chofer = asiento.chofer_reserva.get_full_name() or asiento.chofer_reserva.username
        
        # ✅ CREAR LA VENTA (Venta ya está importada arriba en el archivo)
        venta = Venta.objects.create(
            tipo_documento='ticket',
            numero_documento=asiento.numero_documento_reserva or '',
            nombre_cliente=asiento.nombre_reserva or 'Pasajero',
            telefono_cliente=asiento.telefono_reserva or '',
            email_cliente=asiento.email_reserva or '',
            ruc_cliente=asiento.ruc_reserva or '',
            razon_social=asiento.razon_social_reserva or '',
            asiento=asiento,
            viaje=asiento.viaje,
            sede_venta=request.user.sede,
            cajero=request.user,
            monto_total=asiento.precio,
            numero_ticket=numero_ticket,
            numero_correlativo=numero_correlativo,  # ✅ NUEVO: Guarda el correlativo
            metodo_pago=asiento.metodo_pago_reserva or 'efectivo',
            observaciones=f"Reserva confirmada por chofer: {nombre_chofer}" if nombre_chofer else ""
        )
        
        # ✅ MARCAR ASIENTO COMO VENDIDO
        asiento.estado = 'vendido'
        asiento.fecha_venta = timezone.now()
        asiento.save()
        
        # Marcar notificaciones como leídas
        Notificacion.objects.filter(
            sede_id=request.user.sede.id,
            tipo='reserva_chofer',
            leida=False
        ).update(leida=True)
        
        return JsonResponse({
            'success': True,
            'asiento': asiento.numero_asiento,
            'asiento_id': asiento.id,
            'venta_id': venta.id,
            'ruta': f"{asiento.viaje.ruta.origen} → {asiento.viaje.ruta.destino}",
            'fecha': asiento.viaje.fecha_salida.strftime('%d/%m/%Y'),
            'hora': asiento.viaje.hora_salida.strftime('%H:%M'),
            'pasajero': asiento.nombre_reserva or 'Sin nombre',
            'total': float(asiento.precio or 0),
            'numero_ticket': f"{numero_correlativo:06d}",  # ✅ Devuelve el correlativo formateado (ej: 000031)
            'mensaje': f'✅ Pago confirmado. Asiento {asiento.numero_asiento} vendido.'
        })
        
    except AsientoViaje.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Asiento no encontrado'})
    except Exception as e:
        print(f"❌ ERROR en confirmar_pago_reserva_chofer: {str(e)}")
        import traceback
        traceback.print_exc() # Esto te mostrará el error exacto en consola si vuelve a fallar
        return JsonResponse({'success': False, 'error': f'Error interno: {str(e)}'})


@login_required
def notificaciones_contador_api(request):
    """API: Retorna el contador de notificaciones no leídas de RESERVA CON COBRO (para polling rápido)"""
    
    # ✅ Solo contamos las notificaciones de reserva de chofer que sean CON COBRO
    # Filtramos por el título que generamos: "🚌 RESERVA DE CHOFER - CON COBRO"
    no_leidas_con_cobro = Notificacion.objects.filter(
        sede_id=request.user.sede.id,
        leida=False,
        titulo__icontains="CON COBRO"  # ✅ Filtra solo las de CON COBRO para la alerta urgente
    ).count()
    
    # También contamos el total de no leídas para el badge del sidebar (todas, incluyendo SIN COBRO)
    total_no_leidas = Notificacion.objects.filter(
        sede_id=request.user.sede.id,
        leida=False
    ).count()
    
    return JsonResponse({
        'no_leidas_con_cobro': no_leidas_con_cobro,
        'total_no_leidas': total_no_leidas
    })


from django.db.models import Sum
from django.utils import timezone
from datetime import datetime, timedelta

@login_required
def transacciones_sede(request):
    """Detalle de transacciones de la sede actual - Por defecto muestra solo hoy"""
    sede = request.user.sede
    
    # ✅ FECHA DE HOY POR DEFECTO
    hoy = timezone.localtime(timezone.now()).date()
    
    # Filtro de fecha (si no viene, usa hoy)
    fecha_filtro = request.GET.get('fecha', hoy.isoformat())
    
    # Queryset base: solo ventas de esta sede
    ventas_qs = Venta.objects.filter(sede_venta=sede).select_related(
        'viaje', 'viaje__ruta', 'asiento', 'asiento__viaje', 'cajero'
    )
    
    # ✅ Aplicar filtro de fecha (siempre habrá una fecha: hoy o la filtrada)
    if fecha_filtro:
        try:
            fecha_obj = datetime.strptime(fecha_filtro, '%Y-%m-%d').date()
            inicio_dia = datetime.combine(fecha_obj, datetime.min.time())
            fin_dia = datetime.combine(fecha_obj, datetime.max.time())
            ventas_qs = ventas_qs.filter(fecha_venta__range=(inicio_dia, fin_dia))
        except ValueError:
            pass
    
    ventas_qs = ventas_qs.order_by('-fecha_venta')
    
    # Calcular total
    total_monto = ventas_qs.aggregate(total=Sum('monto_total'))['total'] or 0
    
    # Preparar lista de transacciones
    transacciones = []
    for venta in ventas_qs:
        # ✅ FORMATEAR NÚMERO CORRELATIVO (000001, 000002, etc.)
        num_corr = venta.numero_correlativo or 0
        numero_formateado = f"{num_corr:06d}"
        
        transacciones.append({
            'ticket': numero_formateado,  # ✅ CAMBIADO: Ahora muestra el correlativo
            'numero_ticket_interno': venta.numero_ticket,  # ✅ Por si lo necesitas después
            'fecha': venta.fecha_venta,
            'cliente': venta.nombre_cliente,
            'dni': venta.numero_documento,
            'ruta': f"{venta.viaje.ruta.origen} → {venta.viaje.ruta.destino}" if venta.viaje and venta.viaje.ruta else 'N/A',
            'asiento': f"Asiento {venta.asiento.numero_asiento}" if venta.asiento else 'N/A',
            'sede': venta.sede_venta.nombre,
            'monto': venta.monto_total,
        })
    
    contexto = {
        'transacciones': transacciones,
        'total_transacciones': len(transacciones),
        'total_monto': total_monto,
        'fecha_filtro': fecha_filtro,
        'sede': sede,
    }
    
    return render(request, 'ventas/transacciones_sede.html', contexto)