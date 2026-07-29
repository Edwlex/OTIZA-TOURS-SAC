from core.models import Venta, Ruta
from django.core.paginator import Paginator
from django.utils import timezone
from datetime import timedelta
from django.db.models import Sum

class ClienteService:
    """Servicio para buscar cliente por DNI con filtros y paginación"""
    
    @staticmethod
    def buscar_por_dni(dni, ruta_id=None, periodo=None, fecha_desde=None, fecha_hasta=None, page=1):
        dni_limpio = dni.strip()
        if not dni_limpio or len(dni_limpio) != 8:
            return None
            
        # 1. Query Base
        ventas_qs = Venta.objects.filter(
            numero_documento__iexact=dni_limpio
        ).select_related('viaje__ruta', 'viaje__vehiculo', 'asiento').order_by('-fecha_venta')
        
        if not ventas_qs.exists():
            return None
        
        # 2. APLICAR FILTROS
        hoy = timezone.now().date()
        
        # Filtro por Ruta
        if ruta_id:
            ventas_qs = ventas_qs.filter(viaje__ruta_id=ruta_id)
            
        # Filtro por Tiempo
        if periodo == 'semana':
            ventas_qs = ventas_qs.filter(fecha_venta__date__gte=hoy - timedelta(days=7))
        elif periodo == 'mes':
            ventas_qs = ventas_qs.filter(fecha_venta__date__gte=hoy - timedelta(days=30))
        elif periodo == '6meses':
            ventas_qs = ventas_qs.filter(fecha_venta__date__gte=hoy - timedelta(days=180))
        elif periodo == 'anio':
            ventas_qs = ventas_qs.filter(fecha_venta__date__gte=hoy - timedelta(days=365))
        elif periodo == 'custom' and fecha_desde and fecha_hasta:
            ventas_qs = ventas_qs.filter(fecha_venta__date__range=[fecha_desde, fecha_hasta])
            
        # 3. CALCULAR TOTALES DEL FILTRO (KPIs)
        total_gastado_filtrado = ventas_qs.aggregate(total=Sum('monto_total'))['total'] or 0
        total_viajes_filtrados = ventas_qs.count()
        
        # 4. CONSTRUIR HISTORIAL Y PAGINAR
        historial_completo = []
        for v in ventas_qs:
            historial_completo.append({
                'fecha': v.fecha_venta.strftime('%d/%m/%Y %H:%M'),
                'ruta': f"{v.viaje.ruta.origen} → {v.viaje.ruta.destino}",
                'vehiculo': v.viaje.vehiculo.placa,
                'asiento': v.asiento.numero_asiento if v.asiento else '-',
                'precio': v.monto_total,
                'ticket': v.numero_ticket,
                'sede': v.sede_venta.nombre if v.sede_venta else '-'
            })
            
        # Paginación (10 viajes por página)
        paginator = Paginator(historial_completo, 10)
        page_obj = paginator.get_page(page)
        
        # 5. DATOS DEL CLIENTE (Siempre de la venta más reciente global)
        ultima_venta = Venta.objects.filter(numero_documento__iexact=dni_limpio).order_by('-fecha_venta').first()
        
        return {
            'dni': dni_limpio,
            'nombre': ultima_venta.nombre_cliente,
            'telefono': ultima_venta.telefono_cliente,
            'email': ultima_venta.email_cliente,
            'total_viajes_global': Venta.objects.filter(numero_documento__iexact=dni_limpio).count(),
            'historial': page_obj, # ← Ahora es un objeto paginado
            'total_gastado_filtrado': total_gastado_filtrado,
            'total_viajes_filtrados': total_viajes_filtrados
        }