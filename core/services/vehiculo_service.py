import logging
from django.core.exceptions import ValidationError
from core.models import Vehiculo, Sede

logger = logging.getLogger('core.vehiculo_service')


class VehiculoService:
    """Servicio para manejar la lógica de negocio de vehículos"""
    
    @staticmethod
    def crear_vehiculo(placa, marca, modelo, año, capacidad_asientos, creado_por, chofer_asignado=None, rutas_asignadas=None, **kwargs):
        """
        Crea un nuevo vehículo y asigna sus relaciones
        """
        from django.utils import timezone
        from django.core.exceptions import ValidationError
        
        logger.info("=" * 60)
        logger.info("CREAR_VEHICULO - Iniciando creación de vehicle")
        logger.info(f"  - Placa: {placa}")
        logger.info(f"  - Marca: {marca}")
        logger.info(f"  - Modelo: {modelo}")
        logger.info(f"  - Año: {año}")
        logger.info(f"  - Capacidad: {capacidad_asientos} asientos")
        logger.info(f"  - Chofer: {chofer_asignado.username if chofer_asignado else 'Ninguno'}")
        logger.info(f"  - Rutas: {rutas_asignadas.count() if rutas_asignadas else 0} asignadas")
        logger.info(f"  - Creado por: {creado_por.username}")
        
        # 1. Validar que la placa no exista
        if Vehiculo.objects.filter(placa=placa.upper()).exists():
            logger.error(f"  - ERROR: La placa {placa} ya existe")
            raise ValidationError(f"La placa {placa} ya está registrada en el sistema")
        
        # 2. Validar año
        año_actual = timezone.now().year
        if año < 1990 or año > año_actual + 1:
            logger.error(f"  - ERROR: Año inválido: {año}")
            raise ValidationError(f"El año debe estar entre 1990 y {año_actual + 1}")
        
        # 3. Validar capacidad de asientos
        if capacidad_asientos < 1 or capacidad_asientos > 100:
            logger.error(f"  - ERROR: Capacidad inválida: {capacidad_asientos}")
            raise ValidationError("La capacidad de asientos debe estar entre 1 y 100")
        
        # 4. Crear el vehículo (Sin las rutas, porque es ManyToMany)
        logger.info("  - Creando vehículo en BD...")
        vehiculo = Vehiculo.objects.create(
            placa=placa.upper(),
            marca=marca,
            modelo=modelo,
            año=año,
            capacidad_asientos=capacidad_asientos,
            chofer_asignado=chofer_asignado,  # ✅ El ForeignKey SÍ se puede guardar aquí
            activo=True
        )
        
        # 5. ✅ ASIGNAR RUTAS (ManyToMany) DESPUÉS de que el vehículo ya tiene ID
        if rutas_asignadas:
            vehiculo.rutas_asignadas.set(rutas_asignadas)
            logger.info(f"  - Se asignaron {rutas_asignadas.count()} rutas al vehículo")
        
        logger.info(f"  - Vehículo creado con ID: {vehiculo.id}")
        logger.info("CREAR_VEHICULO - Completado exitosamente")
        logger.info("=" * 60)
        
        return vehiculo

    
    
    @staticmethod
    def editar_vehiculo(vehiculo_id, **kwargs):
        """
        Edita un vehículo existente
        
        Args:
            vehiculo_id: ID del vehículo
            **kwargs: Campos a actualizar
            
        Returns:
            Vehiculo: El vehículo actualizado
        """
        logger.info(f"EDITAR_VEHICULO - Actualizando vehículo {vehiculo_id}")
        
        try:
            vehiculo = Vehiculo.objects.get(id=vehiculo_id)
        except Vehiculo.DoesNotExist:
            logger.error(f"  - ERROR: Vehículo {vehiculo_id} no encontrado")
            raise ValidationError(f"El vehículo {vehiculo_id} no existe")
        
        # Si se está cambiando la placa, validar que no exista
        if 'placa' in kwargs:
            nueva_placa = kwargs['placa'].upper()
            if Vehiculo.objects.filter(placa=nueva_placa).exclude(id=vehiculo_id).exists():
                logger.error(f"  - ERROR: La placa {nueva_placa} ya existe")
                raise ValidationError(f"La placa {nueva_placa} ya está registrada")
            kwargs['placa'] = nueva_placa
        
        # Actualizar campos
        for campo, valor in kwargs.items():
            if hasattr(vehiculo, campo):
                setattr(vehiculo, campo, valor)
                logger.info(f"  - Actualizado {campo}: {valor}")
        
        vehiculo.save()
        logger.info(f"EDITAR_VEHICULO - Vehículo {vehiculo_id} actualizado exitosamente")
        
        return vehiculo
    
    @staticmethod
    def eliminar_vehiculo(vehiculo_id):
        """
        Elimina un vehículo (solo si no tiene viajes asociados)
        
        Args:
            vehiculo_id: ID del vehículo
            
        Raises:
            ValidationError: Si el vehículo tiene viajes asociados
        """
        logger.info(f"ELIMINAR_VEHICULO - Eliminando vehículo {vehiculo_id}")
        
        try:
            vehiculo = Vehiculo.objects.get(id=vehiculo_id)
        except Vehiculo.DoesNotExist:
            logger.error(f"  - ERROR: Vehículo {vehiculo_id} no encontrado")
            raise ValidationError(f"El vehículo {vehiculo_id} no existe")
        
        # Validar que no tenga viajes
        if vehiculo.viajes.exists():
            logger.error(f"  - ERROR: Vehículo {vehiculo.placa} tiene viajes asociados")
            raise ValidationError(
                f"No se puede eliminar el vehículo {vehiculo.placa} porque tiene viajes asociados"
            )
        
        vehiculo.delete()
        logger.info(f"ELIMINAR_VEHICULO - Vehículo {vehiculo_id} eliminado exitosamente")
    
    @staticmethod
    def obtener_vehiculos_por_sede(sede, solo_activos=True):
        """
        Obtiene vehículos filtrados por sede
        
        Args:
            sede: Objeto Sede
            solo_activos: Si True, solo retorna vehículos activos
            
        Returns:
            QuerySet: Vehículos filtrados
        """
        logger.info(f"OBTENER_VEHICULOS - Consultando vehículos para sede: {sede}")
        
        vehiculos = Vehiculo.objects.filter(sede_asignada=sede)
        
        if solo_activos:
            vehiculos = vehiculos.filter(activo=True)
            logger.info("  - Filtrado: solo activos")
        
        logger.info(f"  - Total vehículos encontrados: {vehiculos.count()}")
        
        return vehiculos
    
    @staticmethod
    def obtener_todos_vehiculos(solo_activos=True):
        """
        Obtiene todos los vehículos (para admin)
        
        Args:
            solo_activos: Si True, solo retorna vehículos activos
            
        Returns:
            QuerySet: Todos los vehículos
        """
        logger.info("OBTENER_TODOS_VEHICULOS - Consultando todos los vehículos")
        
        vehiculos = Vehiculo.objects.all()
        
        if solo_activos:
            vehiculos = vehiculos.filter(activo=True)
            logger.info("  - Filtrado: solo activos")
        
        logger.info(f"  - Total vehículos encontrados: {vehiculos.count()}")
        
        return vehiculos