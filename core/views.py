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

# ==================== MODELOS ====================
from core.models import Incidencia, Ruta, Sede, Usuario, Vehiculo, Viaje, Venta, AsientoViaje, HorarioFijo

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


@login_required
def dashboard_cajero(request, usuario, sede):
    """Dashboard para cajeros - CON DATOS REALES DE SU SEDE y FILTRO DE PASADOS"""
    
    hoy = timezone.now().date()
    ahora = timezone.localtime(timezone.now()).time()  # ← AGREGADO: Hora actual local
    
    # ==================== 1. KPIs DEL DÍA (Solo de esta sede) ====================
    
    # Ventas de hoy para esta sede
    ventas_hoy_qs = Venta.objects.filter(
        sede_venta=sede,
        fecha_venta__date=hoy
    )
    ventas_hoy = ventas_hoy_qs.count()
    monto_total_hoy = ventas_hoy_qs.aggregate(total=Sum('monto_total'))['total'] or 0
    
    # Viajes completados hoy para esta sede
    viajes_completados_hoy = Viaje.objects.filter(
        sede_salida=sede,
        fecha_salida=hoy,
        estado='finalizado'
    ).count()
    
    # Pasajeros transportados hoy (1 venta = 1 pasajero)
    total_pasajeros_hoy = ventas_hoy_qs.count()
    
    # ==================== 2. PRÓXIMOS VIAJES (Solo de esta sede) - CORREGIDO ✅ ====================
    
    # FILTRO CLAVE: Excluir viajes pasados (fecha < hoy O fecha=hoy y hora < ahora)
    proximos_viajes_qs = Viaje.objects.filter(
        sede_salida=sede,
        fecha_salida=hoy,  # Solo hoy
        estado__in=['programado', 'en_curso'],
        hora_salida__gte=ahora  # ← SOLO viajes con hora >= ahora (excluye los pasados)
    ).select_related('ruta', 'vehiculo').prefetch_related('asientos').order_by('hora_salida')[:5]
    
    proximos_viajes = []
    for viaje in proximos_viajes_qs:
        asientos = viaje.asientos.all()
        total = asientos.count()
        disponibles = asientos.filter(estado='disponible').count()
        ocupacion = ((total - disponibles) / total * 100) if total > 0 else 0
        
        proximos_viajes.append({
            'id': viaje.id,
            'hora_salida': viaje.hora_salida.strftime('%H:%M'),
            'ruta': f"{viaje.ruta.origen} → {viaje.ruta.destino}",
            'vehiculo': {'placa': viaje.vehiculo.placa, 'modelo': viaje.vehiculo.modelo},
            'asientos_disponibles': disponibles,
            'asientos_totales': total,
            'estado': viaje.get_estado_display(),
            'porcentaje_ocupacion': round(ocupacion, 1)
        })
    
    # ==================== 3. VIAJES RECIENTES (Últimos 3 días, esta sede) ====================
    # (Este ya está bien, muestra viajes finalizados del pasado)
    
    viajes_recientes_qs = Viaje.objects.filter(
        sede_salida=sede,
        fecha_salida__gte=hoy - timedelta(days=3),
        estado='finalizado'
    ).select_related('ruta', 'vehiculo').order_by('-fecha_salida', '-hora_salida')[:5]
    
    viajes_recientes = []
    for viaje in viajes_recientes_qs:
        ingresos = viaje.ventas.aggregate(total=Sum('monto_total'))['total'] or 0
        pasajeros = viaje.ventas.count()
        
        viajes_recientes.append({
            'fecha': viaje.fecha_salida.strftime('%d/%m/%Y'),
            'hora': viaje.hora_salida.strftime('%H:%M'),
            'ruta_origen': viaje.ruta.origen,
            'ruta_destino': viaje.ruta.destino,
            'vehiculo': {'placa': viaje.vehiculo.placa},
            'asientos_ocupados': pasajeros,
            'ingreso': ingresos,
            'estado': 'Completado'
        })
    
    # ==================== 4. FIDELIZACIÓN ====================
    clientes_cercanos = []
    clientes_sede = FidelizacionService.obtener_progreso_clientes(filtro='cerca')
    
    for cliente in clientes_sede:
        ventas_cliente_en_sede = Venta.objects.filter(
            numero_documento=cliente['dni'],
            sede_venta=sede
        ).count()
        
        if ventas_cliente_en_sede > 0:
            clientes_cercanos.append({
                'dni': cliente['dni'],
                'nombre': cliente['nombre'],
                'viajes_en_sede': ventas_cliente_en_sede,
                'faltan_para_premio': cliente['faltan']
            })
    
    # ==================== 5. CONTEXTO BASE ====================
    
    contexto = {
        'usuario': usuario,
        'sede': sede,
        'es_admin': False,
        
        # KPIs
        'ventas_hoy': ventas_hoy,
        'monto_total_hoy': monto_total_hoy,
        'viajes_completados_hoy': viajes_completados_hoy,
        'total_pasajeros_hoy': total_pasajeros_hoy,
        
        # Listas
        'proximos_viajes': proximos_viajes,  # ← Ahora SIN viajes pasados
        'viajes_recientes': viajes_recientes,
        'clientes_cercanos': clientes_cercanos[:3],
        
        # Para búsqueda de cliente en fidelización
        'cliente_busqueda': request.GET.get('dni_cliente', ''),
    }
    
    # ==================== 6. DATOS PARA GRÁFICOS (Solo de esta sede) ====================
    
    # Gráfico 1: Ventas por hora (hoy)
    ventas_por_hora = Venta.objects.filter(
        sede_venta=sede,
        fecha_venta__date=hoy
    ).annotate(
        hora=ExtractHour('fecha_venta')
    ).values('hora').annotate(
        total=Sum('monto_total')
    ).order_by('hora')
    
    horas_labels = [f"{h:02d}:00" for h in range(6, 20)]
    ventas_hora_data = [0] * 14
    
    for item in ventas_por_hora:
        hora_idx = item['hora'] - 6
        if 0 <= hora_idx < 14:
            ventas_hora_data[hora_idx] = float(item['total'] or 0)
    
    # Gráfico 2: Ocupación por ruta (viajes de hoy) - CORREGIDO ✅
    # Solo incluir viajes FUTUROS o EN CURSO (no pasados)
    rutas_ocupacion = Viaje.objects.filter(
        sede_salida=sede,
        fecha_salida=hoy,
        hora_salida__gte=ahora,  # ← Excluir viajes pasados
        estado__in=['programado', 'en_curso']
    ).select_related('ruta').prefetch_related('asientos')
    
    rutas_labels = []
    rutas_data = []
    colores_rutas = ['#10B981', '#3B82F6', '#F59E0B', '#8B5CF6', '#EF4444']
    
    for i, viaje in enumerate(rutas_ocupacion[:4]):
        asientos = viaje.asientos.all()
        total = asientos.count()
        ocupados = asientos.filter(estado='vendido').count()
        porcentaje = (ocupados / total * 100) if total > 0 else 0
        
        rutas_labels.append(f"{viaje.ruta.origen}→{viaje.ruta.destino}")
        rutas_data.append(round(porcentaje, 1))
    
    if not rutas_labels:
        rutas_labels = ['Sin datos']
        rutas_data = [0]
    
    # ==================== CÁLCULOS PARA TARJETAS - CORREGIDO ✅ ====================
    
    # Calcular asientos disponibles SOLO de viajes futuros
    asientos_disponibles_total = sum(v['asientos_disponibles'] for v in proximos_viajes)
    asientos_totales_total = sum(v['asientos_totales'] for v in proximos_viajes)
    
    contexto.update({
        # Gráficos
        'ventas_hora_labels': horas_labels,
        'ventas_hora_data': ventas_hora_data,
        'rutas_labels': rutas_labels,
        'rutas_data': rutas_data,
        'rutas_colores': colores_rutas[:len(rutas_labels)],
        
        # Cálculos para tarjetas (AHORA CORRECTOS)
        'asientos_disponibles_total': asientos_disponibles_total,  # ← Será 0 si no hay viajes futuros
        'asientos_totales_total': asientos_totales_total,
        'porcentaje_disponibilidad': round(
            (asientos_disponibles_total / asientos_totales_total * 100) 
            if asientos_totales_total > 0 else 0, 1
        ),
    })
    
    return render(request, 'dashboard/dashboard_cajero.html', contexto)

@login_required
def dashboard_admin_simple(request, usuario, sede):
    """Dashboard COMPLETO para admin con datos REALES de BD"""
    from core.models import Venta, Viaje, AsientoViaje, Ruta, Vehiculo, Incidencia
    from django.db.models import Sum, Count, Q, Avg
    from django.db.models.functions import TruncDate
    import calendar
    
    hoy = timezone.now().date()
    
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


@login_required
def ventas_lista_cajero(request, usuario, sede):
    """Lista de ventas para CAJERO - AHORA COMPARTIDA ENTRE SEDES""" 
    
    form = VentaFiltroForm(request.GET)
    filtros = form.cleaned_data if form.is_valid() else {}
    
    # Obtener ventas y KPIs (el servicio YA no filtra por sede)
    ventas = VentaService.obtener_ventas_filtradas(filtros, es_admin=False, sede=sede)
    kpis = VentaService.calcular_kpis(ventas)
    
    # ===== FECHA Y HORA ACTUAL LOCAL =====
    ahora_local = timezone.localtime(timezone.now())
    hoy = ahora_local.date()
    ahora = ahora_local.time()
    
    # ===== QUERYSET DE VIAJES (sin cambios) =====
    viajes_qs = Viaje.objects.filter(
        estado__in=['programado', 'en_curso'],
    ).filter(
        Q(fecha_salida=hoy, hora_salida__gte=ahora) |
        Q(fecha_salida__gt=hoy)
    )
    
    
    if filtros.get('ruta'):
        viajes_qs = viajes_qs.filter(ruta_id=filtros['ruta'])
    if filtros.get('buscador'):
        buscador = filtros['buscador']
        viajes_qs = viajes_qs.filter(
            Q(ruta__origen__icontains=buscador) |
            Q(ruta__destino__icontains=buscador) |
            Q(vehiculo__placa__icontains=buscador)
        )
    
    viajes_qs = viajes_qs.select_related('ruta', 'vehiculo', 'chofer_asignado') \
                         .prefetch_related('asientos') \
                         .order_by('fecha_salida', 'hora_salida')
    
    # Procesar viajes
    viajes_disponibles = []
    for viaje in viajes_qs:
        asientos_lista = list(viaje.asientos.all())
        total = len(asientos_lista)
        disponibles = sum(1 for a in asientos_lista if a.estado == 'disponible')
        
        chofer_obj = viaje.chofer_asignado
        nombre_chofer = chofer_obj.get_full_name() if chofer_obj else 'Por asignar'
        
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
        })
    
    # ===== DEBUG EXTREMO: Imprimir TODO =====
    print(f"\n{'='*80}")
    print(f"DEBUG EXTREMO - VENTAS_LISTA_CAJERO")
    print(f"Usuario: {usuario.username} | Sede: {sede.nombre} (ID: {sede.id})")
    print(f"¿Es admin? {usuario.is_superuser}")
    print(f"Total ventas en queryset: {ventas.count()}")
    
    if ventas.count() > 0:
        print("📋 Primeras 3 ventas:")
        for v in ventas[:3]:
            print(f"   • Ticket: {v.numero_ticket} | Cliente: {v.nombre_cliente} | Sede Venta: {v.sede_venta}")
    else:
        print("⚠️ NO HAY VENTAS EN EL QUERYSET. Posibles causas:")
        print("   1. No hay ventas registradas en la BD")
        print("   2. Los filtros de fecha/ruta están vaciando el queryset")
        print("   3. Hay un filtro oculto en VentaService")
    
    print(f"{'='*80}\n")
    
    contexto = {
        'usuario': usuario,
        'sede': sede,
        'es_admin': False,
        'ventas': ventas,  # ← Ahora trae TODAS las ventas, sin filtro por sede
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
        # Generar número de ticket
        ticket_numero = f"TKT-{timezone.now().strftime('%y%m%d')}-{random.randint(1000, 9999)}"
        
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
            fecha_venta=timezone.now()
        )
        
        # Marcar asiento como vendido
        asiento.estado = 'vendido'
        asiento.save()
        
        # ✅ Devolver JSON exitoso CON 'tipo'
        return JsonResponse({
            'success': True,
            'venta_id': venta.id,
            'asiento': venta.asiento.numero_asiento,
            'ruta': f"{venta.viaje.ruta.origen} → {venta.viaje.ruta.destino}",
            'fecha': venta.viaje.fecha_salida.strftime('%d/%m/%Y'),
            'hora': venta.viaje.hora_salida.strftime('%H:%M'),
            'pasajero': venta.nombre_cliente,
            'total': str(venta.monto_total),
            'tipo': 'venta',  # ← ✅ AGREGADO: Para que el JS sepa qué color poner
        })
        
    except Exception as e:
        logger.error(f"Error al procesar venta: {str(e)}", exc_info=True)
        return JsonResponse({'success': False, 'error': f'Error al registrar: {str(e)}'}, status=500)
    
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
                    # ✅ CAMBIO: Usar rutas_asignadas en lugar de sede_asignada
                    rutas_asignadas=form.cleaned_data.get('rutas_asignadas', []),
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

@login_required
def descargar_boleto_pdf(request, boleto_id):
    """Genera y descarga el PDF del boleto con datos formateados"""
    
    # ✅ IMPORTAR DENTRO DE LA FUNCIÓN (evita errores de caché)
    try:
        from xhtml2pdf import pisa
    except ImportError:
        return HttpResponse("Error: Librería xhtml2pdf no instalada. Ejecuta: pip install xhtml2pdf", status=500)
    
    from io import BytesIO
    from django.template.loader import render_to_string
    from django.http import HttpResponse
    from django.shortcuts import get_object_or_404
    from core.models import Venta
    
    # Obtener venta
    venta = get_object_or_404(Venta, id=boleto_id)
    
    # Preparar datos formateados
    boleto = {
        'numero': venta.numero_ticket,
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
    }
    
    # Renderizar HTML
    html_string = render_to_string('ventas/boleto_pdf.html', {'boleto': boleto})
    
    # Crear PDF
    result = BytesIO()
    
    # ✅ VERIFICAR QUE pisa EXISTE ANTES DE USARLO
    if pisa is None:
        return HttpResponse("Error crítico: xhtml2pdf no cargó correctamente", status=500)
    
    pdf = pisa.CreatePDF(BytesIO(html_string.encode("UTF-8")), result, encoding="UTF-8")
    
    if pdf.err:
        return HttpResponse("Error al generar PDF", status=500)
    
    response = HttpResponse(result.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="boleto_{venta.numero_ticket}.pdf"'
    
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
            logger_viaje.error(f"VIAJE_NUEVO - Formulario inválido: {form.errors}")
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
    

@login_required
def liberar_reserva(request, asiento_id):
    """Libera una reserva (cuando el cliente no llegó)"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método no permitido'}, status=400)
    
    try:
        asiento = get_object_or_404(AsientoViaje, id=asiento_id)
        
        # Verificar que esté reservado
        if asiento.estado != 'reservado':
            return JsonResponse({
                'success': False, 
                'error': f'El asiento no está reservado (estado: {asiento.estado})'
            }, status=400)
        
        # Liberar el asiento
        asiento.estado = 'disponible'
        asiento.nombre_reserva = ''
        asiento.numero_documento_reserva = ''
        asiento.telefono_reserva = ''
        asiento.fecha_reserva = None
        asiento.save()
        
        return JsonResponse({
            'success': True,
            'asiento': asiento.numero_asiento,
            'message': f'Asiento {asiento.numero_asiento} liberado correctamente'
        })
        
    except Exception as e:
        logger.error(f"Error al liberar reserva: {str(e)}", exc_info=True)
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


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

@login_required
def confirmar_pago_reserva(request, asiento_id):
    """Convierte reserva en venta - AHORA USA EL DNI GUARDADO"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método no permitido'}, status=400)
    
    import random
    
    try:
        asiento = get_object_or_404(AsientoViaje, id=asiento_id)
        
        if asiento.estado != 'reservado':
            return JsonResponse({'success': False, 'error': 'El asiento no está reservado'}, status=400)
        
        # Crear la venta (USAR DNI GUARDADO)
        venta = Venta.objects.create(
            viaje=asiento.viaje,
            asiento=asiento,
            sede_venta=request.user.sede,
            cajero=request.user,
            numero_documento=asiento.numero_documento_reserva or '',  # ← USAR CAMPO DE RESERVA
            nombre_cliente=asiento.nombre_reserva or 'Cliente Reserva',
            telefono_cliente=asiento.telefono_reserva or '',
            metodo_pago='efectivo',
            monto_total=asiento.viaje.ruta.precio_base,
            numero_ticket=f"TKT-{timezone.now().strftime('%y%m%d')}-{random.randint(1000, 9999)}",
            fecha_venta=timezone.now()
        )
        
        asiento.estado = 'vendido'
        asiento.save()
        
        return JsonResponse({
            'success': True,
            'venta_id': venta.id,
            'asiento': venta.asiento.numero_asiento,
            'ruta': f"{venta.viaje.ruta.origen} → {venta.viaje.ruta.destino}",
            'fecha': venta.viaje.fecha_salida.strftime('%d/%m/%Y'),
            'hora': venta.viaje.hora_salida.strftime('%H:%M'),
            'pasajero': venta.nombre_cliente,
            'total': str(venta.monto_total),
            'tipo': 'venta'
        })
        
    except Exception as e:
        logger.error(f"Error al confirmar pago: {str(e)}", exc_info=True)
        return JsonResponse({'success': False, 'error': str(e)}, status=500)