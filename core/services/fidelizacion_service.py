import logging
from django.db.models import Count, Max
from django.utils import timezone
from core.models import Venta

logger = logging.getLogger('core.fidelizacion_service')


class FidelizacionService:
    """Servicio para manejar la lógica del programa de fidelización"""
    
    VIAJES_PARA_PREMIO = 12
    
    @staticmethod
    def obtener_progreso_clientes(filtro='todos'):
        """
        Obtiene clientes agrupados por DNI con su conteo de viajes y progreso hacia el premio.
        
        Args:
            filtro: 'todos', 'premios' (listos para canjear), 'cerca' (faltan ≤ 3)
            
        Returns:
            list: Lista de diccionarios con datos del cliente
        """
        logger.info(f"FIDELIZACION - Consultando progreso de clientes (filtro: {filtro})...")
        
        # 1. Agrupar ventas por documento de identidad
        clientes_qs = Venta.objects.values(
            'numero_documento', 
            'nombre_cliente', 
            'telefono_cliente'
        ).annotate(
            total_viajes=Count('id'),
            ultimo_viaje=Max('fecha_venta')
        ).filter(
            numero_documento__isnull=False
        ).exclude(
            numero_documento=''
        )
        
        lista_clientes = []
        for cliente in clientes_qs:
            dni = cliente['numero_documento']
            viajes = cliente['total_viajes']
            
            # Calcular progreso cíclico (cada 12 viajes = 1 premio)
            progreso_restante = viajes % FidelizacionService.VIAJES_PARA_PREMIO
            faltan = 0 if progreso_restante == 0 else FidelizacionService.VIAJES_PARA_PREMIO - progreso_restante
            tiene_premio_pendiente = (viajes > 0 and progreso_restante == 0)
            
            lista_clientes.append({
                'dni': dni,
                'nombre': cliente['nombre_cliente'] or 'Cliente Sin Nombre',
                'telefono': cliente['telefono_cliente'],
                'viajes': viajes,
                'faltan': faltan,
                'tiene_premio': tiene_premio_pendiente,
                'porcentaje': min(100, (viajes / FidelizacionService.VIAJES_PARA_PREMIO) * 100) if faltan > 0 else 100,
                'ultimo_viaje': cliente.get('ultimo_viaje')
            })
        
        # 2. Aplicar filtros
        if filtro == 'premios':
            lista_clientes = [c for c in lista_clientes if c['tiene_premio']]
        elif filtro == 'cerca':
            lista_clientes = [c for c in lista_clientes if 0 < c['faltan'] <= 3]
            
        # 3. Ordenar por cantidad de viajes (descendente)
        lista_clientes.sort(key=lambda x: x['viajes'], reverse=True)
        
        logger.info(f"FIDELIZACION - {len(lista_clientes)} clientes encontrados.")
        return lista_clientes
    
    @staticmethod
    def obtener_kpis_fidelizacion():
        """Calcula KPIs rápidos para la vista admin"""
        logger.info("FIDELIZACION - Calculando KPIs...")
        
        # Total clientes únicos con al menos 1 venta
        total_clientes = Venta.objects.values('numero_documento').distinct().count()
        
        # Clientes que ya completaron ciclos de 12 viajes
        clientes = FidelizacionService.obtener_progreso_clientes()
        premios_pendientes = sum(1 for c in clientes if c['tiene_premio'])
        
        # Para MVP: Los entregados se manejan externamente o por registro manual.
        # Aquí retornamos 0, pero en producción iría a un modelo `PremioCanjeado`
        return {
            'total_clientes': total_clientes,
            'premios_pendientes': premios_pendientes,
            'premios_entregados_mes': 0 
        }