import logging
from django.utils import timezone
from django.core.exceptions import ValidationError
from core.models import Incidencia, Sede, Usuario

logger = logging.getLogger('core.incidencia_service')


class IncidenciaService:
    """Servicio para manejar la lógica de negocio de incidencias"""
    
    @staticmethod
    def crear_incidencia(tipo, descripcion, sede_reporte, reportado_por):
        """
        Crea una nueva incidencia
        
        Args:
            tipo: Tipo de incidencia (reclamo, sugerencia, incidente, otro)
            descripcion: Descripción detallada
            sede_reporte: Objeto Sede
            reportado_por: Objeto Usuario
            
        Returns:
            Incidencia: La incidencia creada
            
        Raises:
            ValidationError: Si faltan datos obligatorios
        """
        logger.info("=" * 60)
        logger.info("CREAR_INCIDENCIA - Iniciando creación")
        logger.info(f"  - Tipo: {tipo}")
        logger.info(f"  - Sede: {sede_reporte}")
        logger.info(f"  - Reportado por: {reportado_por.username}")
        
        if not descripcion or not descripcion.strip():
            logger.error("  - ERROR: Descripción vacía")
            raise ValidationError("La descripción es obligatoria")
            
        logger.info("  - Creando incidencia en BD...")
        incidencia = Incidencia.objects.create(
            tipo=tipo,
            descripcion=descripcion.strip(),
            sede_reporte=sede_reporte,
            reportado_por=reportado_por,
            estado='pendiente'
        )
        
        logger.info(f"  - Incidencia creada con ID: {incidencia.id}")
        logger.info("CREAR_INCIDENCIA - Completado exitosamente")
        logger.info("=" * 60)
        
        return incidencia
    
    @staticmethod
    def actualizar_estado(incidencia_id, nuevo_estado, solucion=None):
        """
        Actualiza el estado de una incidencia
        
        Args:
            incidencia_id: ID de la incidencia
            nuevo_estado: 'pendiente', 'en_proceso', 'resuelta'
            solucion: Texto de solución (obligatorio si estado=resuelta)
            
        Returns:
            Incidencia: La incidencia actualizada
        """
        logger.info(f"ACTUALIZAR_INCIDENCIA - ID {incidencia_id} -> {nuevo_estado}")
        
        try:
            incidencia = Incidencia.objects.get(id=incidencia_id)
        except Incidencia.DoesNotExist:
            logger.error(f"  - ERROR: Incidencia {incidencia_id} no encontrada")
            raise ValidationError("La incidencia no existe")
        
        # Validaciones de estado
        estados_validos = ['pendiente', 'en_proceso', 'resuelta']
        if nuevo_estado not in estados_validos:
            logger.error(f"  - ERROR: Estado inválido: {nuevo_estado}")
            raise ValidationError(f"Estado debe ser uno de: {estados_validos}")
            
        if nuevo_estado == 'resuelta' and not solucion:
            logger.error("  - ERROR: Falta solución para estado 'resuelta'")
            raise ValidationError("Debe proporcionar una solución al marcar como resuelta")
            
        # Actualizar campos
        incidencia.estado = nuevo_estado
        if nuevo_estado == 'resuelta':
            incidencia.solucion = solucion.strip()
            incidencia.fecha_resolucion = timezone.now()
            
        incidencia.save()
        logger.info(f"ACTUALIZAR_INCIDENCIA - Incidencia {incidencia_id} actualizada")
        
        return incidencia
    
    @staticmethod
    def eliminar_incidencia(incidencia_id):
        """Elimina una incidencia (solo admin)"""
        logger.info(f"ELIMINAR_INCIDENCIA - ID {incidencia_id}")
        try:
            incidencia = Incidencia.objects.get(id=incidencia_id)
            incidencia.delete()
            logger.info(f"ELIMINAR_INCIDENCIA - Incidencia {incidencia_id} eliminada")
        except Incidencia.DoesNotExist:
            logger.error(f"  - ERROR: Incidencia {incidencia_id} no encontrada")
            raise ValidationError("La incidencia no existe")
    
    @staticmethod
    def obtener_incidencias_filtradas(sede=None, estado=None, tipo=None, es_admin=False):
        """
        Obtiene incidencias con filtros
        
        Args:
            sede: Objeto Sede (obligatorio para cajero)
            estado: Filtro por estado
            tipo: Filtro por tipo
            es_admin: Si True, ignora filtro de sede
            
        Returns:
            QuerySet: Incidencias filtradas
        """
        logger.info("OBTENER_INCIDENCIAS - Consultando con filtros")
        
        queryset = Incidencia.objects.all().select_related('sede_reporte', 'reportado_por')
        
        if not es_admin and sede:
            queryset = queryset.filter(sede_reporte=sede)
            logger.info(f"  - Filtrado por sede: {sede}")
            
        if estado:
            queryset = queryset.filter(estado=estado)
            logger.info(f"  - Filtrado por estado: {estado}")
            
        if tipo:
            queryset = queryset.filter(tipo=tipo)
            logger.info(f"  - Filtrado por tipo: {tipo}")
            
        logger.info(f"  - Total incidencias encontradas: {queryset.count()}")
        return queryset