import logging
from django.core.exceptions import ValidationError
from core.models import Ruta

logger = logging.getLogger('core.ruta_service')


class RutaService:
    """Servicio para manejar la lógica de negocio de rutas"""
    
    @staticmethod
    def crear_ruta(origen, destino, distancia_km, duracion_estimada, precio_base, creado_por):
        """
        Crea una nueva ruta
        
        Args:
            origen: Ciudad de origen
            destino: Ciudad de destino
            distancia_km: Distancia en kilómetros
            duracion_estimada: Duración estimada (ej: "2 horas 30 min")
            precio_base: Precio base del pasaje
            creado_por: Usuario que crea la ruta
            
        Returns:
            Ruta: La ruta creada
            
        Raises:
            ValidationError: Si hay datos inválidos o la ruta ya existe
        """
        logger.info("=" * 60)
        logger.info("CREAR_RUTA - Iniciando creación de ruta")
        logger.info(f"  - Origen: {origen}")
        logger.info(f"  - Destino: {destino}")
        logger.info(f"  - Distancia: {distancia_km} km")
        logger.info(f"  - Duración: {duracion_estimada}")
        logger.info(f"  - Precio base: S/ {precio_base}")
        logger.info(f"  - Creado por: {creado_por.username}")
        
        # 1. Validar que origen y destino no sean iguales
        if origen.strip().lower() == destino.strip().lower():
            logger.error(f"  - ERROR: Origen y destino no pueden ser iguales")
            raise ValidationError("El origen y destino no pueden ser la misma ciudad")
        
        # 2. Validar que la ruta no exista ya
        if Ruta.objects.filter(
            origen__iexact=origen.strip(),
            destino__iexact=destino.strip()
        ).exists():
            logger.error(f"  - ERROR: La ruta {origen} → {destino} ya existe")
            raise ValidationError(
                f"La ruta {origen} → {destino} ya está registrada en el sistema"
            )
        
        # 3. Validar distancia
        if distancia_km <= 0:
            logger.error(f"  - ERROR: Distancia inválida: {distancia_km}")
            raise ValidationError("La distancia debe ser mayor a 0 km")
        
        # 4. Validar precio
        if precio_base <= 0:
            logger.error(f"  - ERROR: Precio inválido: {precio_base}")
            raise ValidationError("El precio base debe ser mayor a 0")
        
        # 5. Crear la ruta
        logger.info("  - Creando ruta en BD...")
        ruta = Ruta.objects.create(
            origen=origen.strip().title(),
            destino=destino.strip().title(),
            distancia_km=distancia_km,
            duracion_estimada=duracion_estimada.strip(),
            precio_base=precio_base,
            activa=True
        )
        
        logger.info(f"  - Ruta creada con ID: {ruta.id}")
        logger.info("CREAR_RUTA - Completado exitosamente")
        logger.info("=" * 60)
        
        return ruta
    
    @staticmethod
    def editar_ruta(ruta_id, **kwargs):
        """
        Edita una ruta existente
        
        Args:
            ruta_id: ID de la ruta
            **kwargs: Campos a actualizar
            
        Returns:
            Ruta: La ruta actualizada
        """
        logger.info(f"EDITAR_RUTA - Actualizando ruta {ruta_id}")
        
        try:
            ruta = Ruta.objects.get(id=ruta_id)
        except Ruta.DoesNotExist:
            logger.error(f"  - ERROR: Ruta {ruta_id} no encontrada")
            raise ValidationError(f"La ruta {ruta_id} no existe")
        
        # Si se está cambiando origen o destino, validar
        if 'origen' in kwargs or 'destino' in kwargs:
            nuevo_origen = kwargs.get('origen', ruta.origen)
            nuevo_destino = kwargs.get('destino', ruta.destino)
            
            if nuevo_origen.strip().lower() == nuevo_destino.strip().lower():
                logger.error(f"  - ERROR: Origen y destino no pueden ser iguales")
                raise ValidationError("El origen y destino no pueden ser la misma ciudad")
            
            # Verificar que no exista otra ruta con esos valores
            if Ruta.objects.filter(
                origen__iexact=nuevo_origen.strip(),
                destino__iexact=nuevo_destino.strip()
            ).exclude(id=ruta_id).exists():
                logger.error(f"  - ERROR: La ruta {nuevo_origen} → {nuevo_destino} ya existe")
                raise ValidationError(
                    f"La ruta {nuevo_origen} → {nuevo_destino} ya está registrada"
                )
            
            kwargs['origen'] = nuevo_origen.strip().title()
            kwargs['destino'] = nuevo_destino.strip().title()
        
        # Validar distancia si se está cambiando
        if 'distancia_km' in kwargs and kwargs['distancia_km'] <= 0:
            logger.error(f"  - ERROR: Distancia inválida: {kwargs['distancia_km']}")
            raise ValidationError("La distancia debe ser mayor a 0 km")
        
        # Validar precio si se está cambiando
        if 'precio_base' in kwargs and kwargs['precio_base'] <= 0:
            logger.error(f"  - ERROR: Precio inválido: {kwargs['precio_base']}")
            raise ValidationError("El precio base debe ser mayor a 0")
        
        # Actualizar campos
        for campo, valor in kwargs.items():
            if hasattr(ruta, campo):
                setattr(ruta, campo, valor)
                logger.info(f"  - Actualizado {campo}: {valor}")
        
        ruta.save()
        logger.info(f"EDITAR_RUTA - Ruta {ruta_id} actualizada exitosamente")
        
        return ruta
    
    @staticmethod
    def eliminar_ruta(ruta_id):
        """
        Elimina una ruta (solo si no tiene viajes asociados)
        
        Args:
            ruta_id: ID de la ruta
            
        Raises:
            ValidationError: Si la ruta tiene viajes asociados
        """
        logger.info(f"ELIMINAR_RUTA - Eliminando ruta {ruta_id}")
        
        try:
            ruta = Ruta.objects.get(id=ruta_id)
        except Ruta.DoesNotExist:
            logger.error(f"  - ERROR: Ruta {ruta_id} no encontrada")
            raise ValidationError(f"La ruta {ruta_id} no existe")
        
        # Validar que no tenga viajes
        if ruta.viajes.exists():
            logger.error(f"  - ERROR: Ruta {ruta} tiene viajes asociados")
            raise ValidationError(
                f"No se puede eliminar la ruta {ruta} porque tiene viajes asociados"
            )
        
        ruta.delete()
        logger.info(f"ELIMINAR_RUTA - Ruta {ruta_id} eliminada exitosamente")
    
    @staticmethod
    def obtener_rutas_activas():
        """
        Obtiene todas las rutas activas
        
        Returns:
            QuerySet: Rutas activas
        """
        logger.info("OBTENER_RUTAS_ACTIVAS - Consultando rutas activas")
        
        rutas = Ruta.objects.filter(activa=True)
        logger.info(f"  - Total rutas activas: {rutas.count()}")
        
        return rutas
    
    @staticmethod
    def obtener_todas_rutas(incluir_inactivas=False):
        """
        Obtiene todas las rutas
        
        Args:
            incluir_inactivas: Si True, incluye rutas inactivas
            
        Returns:
            QuerySet: Rutas
        """
        logger.info("OBTENER_TODAS_RUTAS - Consultando todas las rutas")
        
        rutas = Ruta.objects.all()
        
        if not incluir_inactivas:
            rutas = rutas.filter(activa=True)
            logger.info("  - Filtrado: solo activas")
        
        logger.info(f"  - Total rutas encontradas: {rutas.count()}")
        
        return rutas
    
    @staticmethod
    def obtener_rutas_por_origen(origen):
        """
        Obtiene rutas que salen de una ciudad específica
        
        Args:
            origen: Ciudad de origen
            
        Returns:
            QuerySet: Rutas desde esa ciudad
        """
        logger.info(f"OBTENER_RUTAS_POR_ORIGEN - Consultando rutas desde: {origen}")
        
        rutas = Ruta.objects.filter(origen__iexact=origen, activa=True)
        logger.info(f"  - Rutas encontradas: {rutas.count()}")
        
        return rutas