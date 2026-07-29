import logging
from django.db.models import Count, Max
from django.utils import timezone
from core.models import Venta

logger = logging.getLogger('core.fidelizacion_service')

class FidelizacionService:
    """Servicio para manejar la lógica del programa de fidelización"""
    
    VIAJES_PARA_PREMIO = 12
    
    @staticmethod
    def obtener_progreso_clientes(filtro='todos', sede=None):
        """
        Obtiene clientes agrupados por DNI con su conteo de viajes y progreso hacia el premio.
        
        Args:
            filtro: 'todos', 'premios' (listos para canjear), 'cerca' (faltan <= 2)
            sede: Objeto Sede. Si se proporciona, solo muestra clientes que han comprado en esta sede,
                  pero el conteo de viajes ('viajes') es GLOBAL (compartido entre sedes).
        """
        logger.info(f"FIDELIZACION - Consultando progreso (filtro: {filtro}, sede: {sede.nombre if sede else 'Global'})...")
        
        # 1. Si hay una sede específica, primero obtenemos los DNIs que han comprado en esta sede
        if sede:
            dnis_en_sede = Venta.objects.filter(
                sede_venta=sede,
                numero_documento__isnull=False
            ).exclude(
                numero_documento=''
            ).values_list('numero_documento', flat=True).distinct()
            
            # Base queryset: solo estos DNIs, pero contaremos TODOS sus viajes (globales)
            base_qs = Venta.objects.filter(numero_documento__in=dnis_en_sede)
        else:
            # Admin: todos los DNIs del sistema sin filtro de sede
            base_qs = Venta.objects
            
        # 2. Agrupar ventas por documento de identidad (conteo GLOBAL de viajes)
        clientes_qs = base_qs.values(
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
                'viajes': viajes, # ← Este es el conteo GLOBAL
                'viajes_ciclo': progreso_restante,
                'faltan': faltan,
                'tiene_premio': tiene_premio_pendiente,
                'porcentaje': min(100, ((viajes % FidelizacionService.VIAJES_PARA_PREMIO) / FidelizacionService.VIAJES_PARA_PREMIO) * 100) if faltan > 0 else 100,
                'ultimo_viaje': cliente.get('ultimo_viaje').strftime('%d/%m/%Y') if cliente.get('ultimo_viaje') else 'N/A'
            })
        
        # 3. Aplicar filtros de estado
        if filtro == 'premios':
            lista_clientes = [c for c in lista_clientes if c['tiene_premio']]
        elif filtro == 'cerca':
            lista_clientes = [c for c in lista_clientes if 0 < c['faltan'] <= 2]
            
        # 4. Ordenar: Primero los que tienen premio pendiente, luego los más cercanos, luego por cantidad de viajes
        lista_clientes.sort(key=lambda x: (not x['tiene_premio'], x['faltan'] if x['faltan'] > 0 else 999, -x['viajes']))
        
        logger.info(f"FIDELIZACION - {len(lista_clientes)} clientes encontrados.")
        return lista_clientes
    
    @staticmethod
    def obtener_kpis_fidelizacion(sede=None):
        """Calcula KPIs rápidos para la vista (Admin o Cajero)"""
        logger.info(f"FIDELIZACION - Calculando KPIs (sede: {sede.nombre if sede else 'Global'})...")
        
        # Reutilizamos el método anterior para garantizar consistencia en los números
        todos_los_clientes = FidelizacionService.obtener_progreso_clientes(filtro='todos', sede=sede)
        
        total_clientes = len(todos_los_clientes)
        premios_pendientes = sum(1 for c in todos_los_clientes if c['tiene_premio'])
        cercanos = sum(1 for c in todos_los_clientes if 0 < c['faltan'] <= 2)
        
        # Claves alineadas con tu template (pendientes, entregados, cercanos)
        return {
            'total_clientes': total_clientes,
            'pendientes': premios_pendientes,
            'entregados': 0, # Placeholder hasta que creemos el modelo de canjes
            'cercanos': cercanos
        }