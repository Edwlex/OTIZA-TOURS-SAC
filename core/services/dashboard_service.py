import logging
from datetime import timedelta
from django.utils import timezone
from django.db.models import Sum, Count, Q, F
from core.models import Venta, Viaje, AsientoViaje, Incidencia, Sede

logger = logging.getLogger('core.dashboard_service')

class DashboardService:
    """Servicio para calcular KPIs y datos del dashboard en tiempo real"""
    
    @staticmethod
    def obtener_datos_dashboard(fecha=None, es_admin=False, sede=None):
        """Calcula todos los datos necesarios para el dashboard"""
        fecha = fecha or timezone.now().date()
        logger.info(f"DASHBOARD_SERVICE - Calculando datos para: {fecha}")
        
        # 1. Queryset base de ventas del día
        ventas_qs = Venta.objects.filter(fecha_venta__date=fecha)
        if not es_admin and sede:
            ventas_qs = ventas_qs.filter(sede_venta=sede)
            
        # 2. KPIs Principales
        kpis = ventas_qs.aggregate(
            total_monto=Sum('monto_total'),
            total_boletos=Count('id')
        )
        
        # 3. Viajes del día
        viajes_qs = Viaje.objects.filter(fecha_salida=fecha)
        if not es_admin and sede:
            viajes_qs = viajes_qs.filter(sede_salida=sede)
            
        total_viajes = viajes_qs.count()
        viajes_completados = viajes_qs.filter(estado='finalizado').count()
        
        # 4. Ocupación Real (Asientos vendidos / Total asientos programados)
        asientos_qs = AsientoViaje.objects.filter(viaje__fecha_salida=fecha)
        if not es_admin and sede:
            asientos_qs = asientos_qs.filter(viaje__sede_salida=sede)
            
        total_asientos = asientos_qs.count()
        asientos_vendidos = asientos_qs.filter(estado='vendido').count()
        ocupacion = (asientos_vendidos / total_asientos * 100) if total_asientos > 0 else 0
        
        # 5. Tendencia Últimos 7 Días (Para gráfico de línea)
        hoy = timezone.now().date()
        hace_7_dias = hoy - timedelta(days=6)
        dias = []
        montos = []
        
        current = hace_7_dias
        while current <= hoy:
            monto_dia = Venta.objects.filter(
                fecha_venta__date=current,
                sede_venta=sede if not es_admin else None
            ).aggregate(total=Sum('monto_total'))['total'] or 0
            
            dias.append(current.strftime('%a')) # Lun, Mar...
            montos.append(float(monto_dia))
            current += timedelta(days=1)
            
        # 6. Ingresos por Sede (Para gráfico de barras)
        ingresos_por_sede_qs = ventas_qs.values('sede_venta__nombre').annotate(
            total=Sum('monto_total')
        ).order_by('-total')
        
        sedes_nombres = []
        sedes_montos = []
        for item in ingresos_por_sede_qs:
            sedes_nombres.append(item['sede_venta__nombre'])
            sedes_montos.append(float(item['total']))
            
        # 7. Actividad Reciente (Últimas 5 ventas)
        actividad_reciente = ventas_qs.select_related('cajero', 'viaje__ruta').order_by('-fecha_venta')[:5]
        
        # 8. Incidencias Pendientes
        incidencias_qs = Incidencia.objects.filter(estado='pendiente')
        if not es_admin and sede:
            incidencias_qs = incidencias_qs.filter(sede_reporte=sede)
        incidencias_pendientes = incidencias_qs.select_related('sede_reporte').order_by('-fecha_reporte')[:5]
        
        logger.info(f"DASHBOARD_SERVICE - Cálculo completado. Ventas: {kpis['total_boletos']}, Ocupación: {ocupacion:.1f}%")
        
        return {
            'ingresos_totales': kpis['total_monto'] or 0,
            'total_boletos': kpis['total_boletos'] or 0,
            'total_pasajeros': kpis['total_boletos'] or 0, # 1 boleto = 1 pasajero
            'total_viajes': total_viajes,
            'viajes_completados': viajes_completados,
            'ocupacion_promedio': round(ocupacion, 1),
            'dias_semana': dias,
            'ventas_por_dia': montos,
            'sedes': sedes_nombres,
            'ingresos_por_sede': sedes_montos,
            'actividad_reciente': actividad_reciente,
            'incidencias_pendientes': incidencias_pendientes,
        }