import logging
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db.models import Q
from core.models import Viaje, AsientoViaje, Vehiculo, Ruta, Sede
from datetime import datetime, timedelta
from django.utils import timezone
import re

from otiza_backend import settings  

logger = logging.getLogger('core.viaje_service')


class ViajeService:
    """Servicio para manejar la lógica de negocio de viajes"""
    
    @staticmethod
    def crear_viaje(ruta, vehiculo, sede_salida, fecha_salida, hora_salida, 
                    fecha_llegada, hora_llegada, creado_por, chofer_asignado=None):
        """
        Crea un nuevo viaje y genera automáticamente los asientos disponibles
        La fecha y hora de llegada se calculan automáticamente desde la duración de la ruta
        """
        import re  # ← Asegúrate de tener este import

        print("=" * 70)
        print(f"settings.TIME_ZONE: {settings.TIME_ZONE}")
        print(f"fecha_salida: {fecha_salida} (type: {type(fecha_salida)})")
        print(f"hora_salida: {hora_salida} (type: {type(hora_salida)})")
        print(f"timezone.now() (UTC): {timezone.now()}")
        print(f"timezone.localtime(): {timezone.localtime(timezone.now())}")
        print(f"viaje_dt_naive: {datetime.combine(fecha_salida, hora_salida)}")
        print("=" * 70)
        logger.info("=" * 60)
        logger.info("CREAR_VIAJE - Iniciando creación de viaje")
        logger.info(f"  - Ruta: {ruta.origen} -> {ruta.destino}")
        logger.info(f"  - Vehículo: {vehiculo}")
        logger.info(f"  - Sede salida: {sede_salida}")
        logger.info(f"  - Fecha/Hora salida: {fecha_salida} {hora_salida}")
        logger.info(f"  - Duración ruta: {ruta.duracion_estimada}")
        logger.info(f"  - Creado por: {creado_por.username}")

        # ===== VALIDACIÓN: NO VIAJES EN EL PASADO =====
        viaje_dt_naive = datetime.combine(fecha_salida, hora_salida)
        ahora_local = timezone.localtime(timezone.now())
        ahora_naive = ahora_local.replace(tzinfo=None)
        
        logger.info(f"  - Validación: viaje_dt={viaje_dt_naive}, ahora={ahora_naive}")
        
        if viaje_dt_naive < ahora_naive:
            logger.error(f"  - ERROR: Intento de crear viaje en el pasado")
            raise ValidationError(
                f"No se puede programar un viaje en el pasado. "
                f"Ahora: {ahora_naive.strftime('%d/%m %H:%M')} | "
                f"Viaje: {viaje_dt_naive.strftime('%d/%m %H:%M')}"
            )
        
        # 1. Validar que el vehículo esté activo
        if not vehiculo.activo:
            logger.error(f"  - ERROR: Vehículo {vehiculo.placa} está inactivo")
            raise ValidationError(f"El vehículo {vehiculo.placa} está inactivo")
        
        # 2. Validar rutas asignadas (warning, no error)
        if not vehiculo.rutas_asignadas.filter(
            Q(origen__icontains=sede_salida.nombre) | 
            Q(destino__icontains=sede_salida.nombre)
        ).exists():
            logger.warning(f"  - WARNING: Vehículo {vehiculo.placa} no tiene rutas asignadas para {sede_salida}")
        
        # ===== ✅ VALIDACIÓN CORREGIDA: SOLAPAMIENTO DE HORAS =====
        # Verificar si el vehículo ya tiene viajes en esa fecha
        viajes_existentes = Viaje.objects.filter(
            vehiculo=vehiculo,
            fecha_salida=fecha_salida,
            estado__in=['programado', 'en_curso']
        )
        
        if viajes_existentes.exists():
            # Función helper para parsear duración (inline)
            def _parsear_duracion(texto):
                texto = str(texto).lower().strip()
                horas = minutos = 0
                match_h = re.search(r'(\d+)\s*(?:hora|horas|h)\b', texto)
                if match_h: horas = int(match_h.group(1))
                match_m = re.search(r'(\d+)\s*(?:min|minutos|m)\b', texto)
                if match_m: minutos = int(match_m.group(1))
                if horas == 0 and minutos == 0: horas = 2  # fallback
                return horas, minutos
            
            # Validar solapamiento con cada viaje existente
            for viaje_existente in viajes_existentes:
                # Combinar fecha+hora
                existente_dt = datetime.combine(viaje_existente.fecha_salida, viaje_existente.hora_salida)
                nuevo_dt = datetime.combine(fecha_salida, hora_salida)
                
                # Calcular duraciones
                nuevo_h, nuevo_m = _parsear_duracion(ruta.duracion_estimada)
                nueva_duracion = timedelta(hours=nuevo_h, minutes=nuevo_m)
                
                ext_h, ext_m = _parsear_duracion(viaje_existente.ruta.duracion_estimada)
                existente_duracion = timedelta(hours=ext_h, minutes=ext_m)
                
                # Calcular rangos de tiempo
                nuevo_fin = nuevo_dt + nueva_duracion
                existente_fin = existente_dt + existente_duracion
                
                # ✅ Hay solapamiento si los rangos se intersectan
                if nuevo_dt < existente_fin and nuevo_fin > existente_dt:
                    logger.error(f"  - ERROR: Conflicto de horario con vehículo {vehiculo.placa}")
                    raise ValidationError(
                        f"El vehículo {vehiculo.placa} ya tiene un viaje programado para {fecha_salida} "
                        f"a las {viaje_existente.hora_salida.strftime('%H:%M')} que se solapa con la hora seleccionada."
                    )
            # ✅ Si llegó aquí, no hay solapamiento → Permitir creación
        
        # 3. Calcular fecha y hora de llegada automáticamente
        logger.info("  - Calculando hora de llegada...")
        
        duracion_texto = str(ruta.duracion_estimada).lower().strip()
        horas = 0
        minutos = 0
        
        # Regex para horas
        match_horas = re.search(r'(\d+)\s*(?:hora|horas|h)\b', duracion_texto)
        if match_horas:
            horas = int(match_horas.group(1))
            logger.info(f"  - Horas extraídas: {horas}")
        
        # Regex para minutos
        match_minutos = re.search(r'(\d+)\s*(?:min|minutos|m)\b', duracion_texto)
        if match_minutos:
            minutos = int(match_minutos.group(1))
            logger.info(f"  - Minutos extraídos: {minutos}")
        
        # Fallback
        if horas == 0 and minutos == 0:
            logger.warning(f"  - WARNING: No se pudo parsear '{duracion_texto}', usando 2 horas por defecto")
            horas = 2
        
        # Calcular llegada
        duracion_total = timedelta(hours=horas, minutes=minutos)
        datetime_salida = timezone.datetime.combine(fecha_salida, hora_salida)
        datetime_llegada = datetime_salida + duracion_total
        
        fecha_llegada = datetime_llegada.date()
        hora_llegada = datetime_llegada.time()
        
        logger.info(f"  - Duración parseada: {horas}h {minutos}min")
        logger.info(f"  - Salida: {fecha_salida} {hora_salida} → Llegada: {fecha_llegada} {hora_llegada}")
        
        # 4. Crear el viaje
        logger.info("  - Creando viaje en BD...")
        viaje = Viaje.objects.create(
            ruta=ruta,
            vehiculo=vehiculo,
            sede_salida=sede_salida,
            chofer_asignado=chofer_asignado,
            fecha_salida=fecha_salida,
            hora_salida=hora_salida,
            fecha_llegada=fecha_llegada,
            hora_llegada=hora_llegada,
            estado='programado'
        )
        
        logger.info(f"  - Viaje creado con ID: {viaje.id}")
        
        # 5. Generar asientos automáticamente
        logger.info(f"  - Generando {vehiculo.capacidad_asientos} asientos...")
        asientos_creados = ViajeService._generar_asientos(viaje, vehiculo.capacidad_asientos, ruta.precio_base)
        
        logger.info(f"  - Asientos creados: {asientos_creados}")
        logger.info("CREAR_VIAJE - Completado exitosamente")
        logger.info("=" * 60)
        
        return viaje
    
    @staticmethod
    def _generar_asientos(viaje, capacidad, precio_base):
        """
        Genera los asientos para un viaje
        
        Args:
            viaje: Objeto Viaje
            capacidad: Número de asientos
            precio_base: Precio del pasaje
            
        Returns:
            int: Número de asientos creados
        """
        asientos_creados = 0
        
        # Generar asientos con formato: A1, A2, A3... (o A1, B1, C1 si es bus grande)
        for i in range(1, capacidad + 1):
            # Formato simple: 1, 2, 3, 4...
            numero_asiento = str(i)
            
            AsientoViaje.objects.create(
                viaje=viaje,
                numero_asiento=numero_asiento,
                estado='disponible',
                precio=precio_base
            )
            asientos_creados += 1
        
        return asientos_creados
    
    @staticmethod
    def editar_viaje(viaje_id, **kwargs):
        """
        Edita un viaje existente
        
        Args:
            viaje_id: ID del viaje
            **kwargs: Campos a actualizar (ruta, vehiculo, fecha_salida, etc.)
            
        Returns:
            Viaje: El viaje actualizado
        """
        logger.info(f"EDITAR_VIAJE - Actualizando viaje {viaje_id}")
        
        try:
            viaje = Viaje.objects.get(id=viaje_id)
        except Viaje.DoesNotExist:
            logger.error(f"  - ERROR: Viaje {viaje_id} no encontrado")
            raise ValidationError(f"El viaje {viaje_id} no existe")
        
        # Actualizar campos
        for campo, valor in kwargs.items():
            if hasattr(viaje, campo):
                setattr(viaje, campo, valor)
                logger.info(f"  - Actualizado {campo}: {valor}")
        
        viaje.save()
        logger.info(f"EDITAR_VIAJE - Viaje {viaje_id} actualizado exitosamente")
        
        return viaje
    
    @staticmethod
    def eliminar_viaje(viaje_id):
        """
        Elimina un viaje (solo si no tiene ventas)
        
        Args:
            viaje_id: ID del viaje
            
        Raises:
            ValidationError: Si el viaje tiene ventas asociadas
        """
        logger.info(f"ELIMINAR_VIAJE - Eliminando viaje {viaje_id}")
        
        try:
            viaje = Viaje.objects.get(id=viaje_id)
        except Viaje.DoesNotExist:
            logger.error(f"  - ERROR: Viaje {viaje_id} no encontrado")
            raise ValidationError(f"El viaje {viaje_id} no existe")
        
        # Validar que no tenga ventas
        if viaje.ventas.exists():
            logger.error(f"  - ERROR: Viaje {viaje_id} tiene ventas asociadas")
            raise ValidationError(
                f"No se puede eliminar el viaje {viaje_id} porque tiene ventas asociadas"
            )
        
        # Eliminar asientos (CASCADE) y viaje
        viaje.delete()
        logger.info(f"ELIMINAR_VIAJE - Viaje {viaje_id} eliminado exitosamente")
    
    @staticmethod
    def obtener_viajes_por_sede(sede, fecha=None, estado=None):
        """
        Obtiene viajes filtrados por sede, fecha y estado
        
        Args:
            sede: Objeto Sede
            fecha: Date (opcional)
            estado: String (opcional)
            
        Returns:
            QuerySet: Viajes filtrados
        """
        logger.info(f"OBTENER_VIAJES - Consultando viajes para sede: {sede}")
        
        viajes = Viaje.objects.filter(sede_salida=sede)
        
        if fecha:
            viajes = viajes.filter(fecha_salida=fecha)
            logger.info(f"  - Filtrado por fecha: {fecha}")
        
        if estado:
            viajes = viajes.filter(estado=estado)
            logger.info(f"  - Filtrado por estado: {estado}")
        
        logger.info(f"  - Total viajes encontrados: {viajes.count()}")
        
        return viajes
    
    @staticmethod
    def obtener_viajes_del_dia(sede):
        """
        Obtiene todos los viajes programados para hoy de una sede
        
        Args:
            sede: Objeto Sede
            
        Returns:
            QuerySet: Viajes de hoy
        """
        hoy = timezone.now().date()
        logger.info(f"OBTENER_VIAJES_DIA - Viajes de hoy ({hoy}) para sede: {sede}")
        
        viajes = Viaje.objects.filter(
            sede_salida=sede,
            fecha_salida=hoy,
            estado__in=['programado', 'en_curso']
        ).select_related('ruta', 'vehiculo').prefetch_related('asientos')
        
        logger.info(f"  - Viajes encontrados: {viajes.count()}")
        
        return viajes
    
    @staticmethod
    def calcular_asientos_disponibles(viaje):
        """
        Calcula cuántos asientos están disponibles en un viaje
        
        Args:
            viaje: Objeto Viaje
            
        Returns:
            dict: Información de asientos
        """
        asientos = viaje.asientos.all()
        total = asientos.count()
        disponibles = asientos.filter(estado='disponible').count()
        vendidos = asientos.filter(estado='vendido').count()
        ocupacion = (vendidos / total * 100) if total > 0 else 0
        
        return {
            'total': total,
            'disponibles': disponibles,
            'vendidos': vendidos,
            'ocupacion': round(ocupacion, 2)
        }