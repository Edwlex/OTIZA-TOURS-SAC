import logging
from django.db.models import Q, Sum, Avg, Count 
from django.utils import timezone
from core.models import Venta, Sede

logger = logging.getLogger('core.venta_service')


class VentaService:
    """Servicio para manejar consultas y KPIs de ventas"""
    
    @staticmethod
    def obtener_ventas_filtradas(filtros=None, es_admin=False, sede=None):
        """
        Obtiene ventas aplicando filtros dinámicos
        
        Args:
            filtros: Dict con fecha_desde, fecha_hasta, ruta, buscador
            es_admin: Si True, ignora filtro de sede
            sede: Objeto Sede (para cajeros)
            
        Returns:
            QuerySet: Ventas filtradas y optimizadas
        """
        logger.info("VENTA_SERVICE - Consultando ventas con filtros...")
        
        # Optimización: select_related para evitar N+1 queries
        qs = Venta.objects.select_related(
            'viaje__ruta', 'viaje__vehiculo', 
            'sede_venta', 'cajero', 'asiento'
        ).order_by('-fecha_venta')
        
        # Filtro por sede (cajero solo ve lo suyo)
        if not es_admin and sede:
            qs = qs.filter(sede_venta=sede)
            logger.info(f"  - Filtrado por sede: {sede}")
            
        if filtros:
            # Rango de fechas
            if filtros.get('fecha_desde'):
                qs = qs.filter(fecha_venta__date__gte=filtros['fecha_desde'])
            if filtros.get('fecha_hasta'):
                qs = qs.filter(fecha_venta__date__lte=filtros['fecha_hasta'])
                
            # Filtro por ruta
            if filtros.get('ruta'):
                qs = qs.filter(viaje__ruta_id=filtros['ruta'])
                
            # Buscador global (ticket, cliente, ruta)
            buscador = filtros.get('buscador', '').strip()
            if buscador:
                qs = qs.filter(
                    Q(numero_ticket__icontains=buscador) |
                    Q(nombre_cliente__icontains=buscador) |
                    Q(viaje__ruta__origen__icontains=buscador) |
                    Q(viaje__ruta__destino__icontains=buscador)
                )
                logger.info(f"  - Búsqueda: '{buscador}'")
                
        logger.info(f"  - Total ventas encontradas: {qs.count()}")
        return qs
    
    @staticmethod
    def calcular_kpis(ventas_qs):
        """Calcula KPIs financieros y operativos"""
        logger.info("VENTA_SERVICE - Calculando KPIs...")
        
        kpis = ventas_qs.aggregate(
            total_monto=Sum('monto_total'),
            promedio=Avg('monto_total'),
            total_boletos=Count('id')
        )
        
        return {
            'total_monto': kpis['total_monto'] or 0,
            'total_boletos': kpis['total_boletos'] or 0,
            'promedio_venta': kpis['promedio'] or 0
        }