import logging
from datetime import date
from django.core.exceptions import ValidationError
from django.utils import timezone
from core.models import Usuario, Sede

logger = logging.getLogger('core.chofer_service')


class ChoferService:
    """Servicio para manejar la lógica de negocio de choferes"""
    
    @staticmethod
    def crear_chofer(username, password, email, first_name, last_name, dni, 
                    licencia_conducir, categoria_licencia, fecha_vencimiento_licencia,
                    telefono, sede_asignada, creado_por, **kwargs):
        """
        Crea un nuevo chofer (usuario con rol de chofer)
        
        Args:
            username: Nombre de usuario único
            password: Contraseña
            email: Email
            first_name: Nombre
            last_name: Apellido
            dni: DNI (8 dígitos)
            licencia_conducir: Número de licencia
            categoria_licencia: Categoría (A-IIA, A-IIIB, etc.)
            fecha_vencimiento_licencia: Fecha de vencimiento
            telefono: Teléfono
            sede_asignada: Objeto Sede
            creado_por: Usuario que crea el chofer
            **kwargs: Argumentos adicionales (ej: rutas_asignadas)
            
        Returns:
            Usuario: El chofer creado
            
        Raises:
            ValidationError: Si hay datos inválidos
        """
        logger.info("=" * 60)
        logger.info("CREAR_CHOFER - Iniciando creación de chofer")
        logger.info(f"  - Username: {username}")
        logger.info(f"  - DNI: {dni}")
        logger.info(f"  - Licencia: {licencia_conducir}")
        logger.info(f"  - Sede asignada: {sede_asignada}")
        logger.info(f"  - Creado por: {creado_por.username}")
        
        # 1. Validar DNI (8 dígitos)
        if not dni.isdigit() or len(dni) != 8:
            logger.error(f"  - ERROR: DNI inválido: {dni}")
            raise ValidationError("El DNI debe tener exactamente 8 dígitos numéricos")
        
        # 2. Validar que el DNI no exista ya
        if Usuario.objects.filter(username=dni).exists():
            logger.error(f"  - ERROR: DNI {dni} ya registrado")
            raise ValidationError(f"El DNI {dni} ya está registrado en el sistema")
        
        # 3. Validar licencia
        if not licencia_conducir or len(licencia_conducir) < 5:
            logger.error(f"  - ERROR: Licencia inválida: {licencia_conducir}")
            raise ValidationError("El número de licencia debe tener al menos 5 caracteres")
        
        # 4. Validar fecha de vencimiento
        if fecha_vencimiento_licencia and fecha_vencimiento_licencia < date.today():
            logger.warning(f"  - WARNING: Licencia vencida: {fecha_vencimiento_licencia}")
        
        # 5. Validar categoría de licencia
        categorias_validas = ['A-I', 'A-IIA', 'A-IIIB', 'A-IIIa', 'A-IIIb', 'A-IIIc', 'B-I', 'B-IIa', 'B-IIb', 'B-IIIa', 'B-IIIb', 'B-IIIc', 'C-I', 'C-IIa', 'C-IIb', 'C-IIIa', 'C-IIIb', 'C-IIIc']
        if categoria_licencia and categoria_licencia.upper() not in [c.upper() for c in categorias_validas]:
            logger.warning(f"  - WARNING: Categoría no estándar: {categoria_licencia}")
        

        # 6. Crear el usuario chofer
        logger.info("  - Creando chofer en BD...")
        chofer = Usuario.objects.create_user(
            username=username,
            password=password,
            email=email,
            first_name=first_name,
            last_name=last_name,
            sede=sede_asignada,
            telefono=telefono,
            # Flags de rol
            es_cajero=False,
            es_chofer=True,
            # 🔒 Flags de Django (CRÍTICO para que no aparezca como admin)
            is_staff=False,
            is_superuser=False,
            activo=True,
            licencia_conducir=licencia_conducir.upper(),
            categoria_licencia=categoria_licencia.upper() if categoria_licencia else '',
            fecha_vencimiento_licencia=fecha_vencimiento_licencia
        )
        
        # ✅ NUEVO: Asignar rutas si vienen en kwargs
        if 'rutas_asignadas' in kwargs and kwargs['rutas_asignadas']:
            chofer.rutas_asignadas.set(kwargs['rutas_asignadas'])
            logger.info(f"  - Rutas asignadas: {kwargs['rutas_asignadas'].count()} rutas")
        
        logger.info(f"  - Chofer creado con ID: {chofer.id}")
        logger.info("CREAR_CHOFER - Completado exitosamente")
        logger.info("=" * 60)
        
        return chofer
    
    @staticmethod
    def editar_chofer(chofer_id, **kwargs):
        """
        Edita un chofer existente
        
        Args:
            chofer_id: ID del chofer
            **kwargs: Campos a actualizar
            
        Returns:
            Usuario: El chofer actualizado
        """
        logger.info(f"EDITAR_CHOFER - Actualizando chofer {chofer_id}")
        
        try:
            chofer = Usuario.objects.get(id=chofer_id, es_chofer=True)
        except Usuario.DoesNotExist:
            logger.error(f"  - ERROR: Chofer {chofer_id} no encontrado")
            raise ValidationError(f"El chofer {chofer_id} no existe")
        
        # Si se está cambiando el DNI, validar
        if 'username' in kwargs:
            nuevo_dni = kwargs['username']
            if not nuevo_dni.isdigit() or len(nuevo_dni) != 8:
                logger.error(f"  - ERROR: DNI inválido: {nuevo_dni}")
                raise ValidationError("El DNI debe tener exactamente 8 dígitos numéricos")
            
            if Usuario.objects.filter(username=nuevo_dni).exclude(id=chofer_id).exists():
                logger.error(f"  - ERROR: DNI {nuevo_dni} ya existe")
                raise ValidationError(f"El DNI {nuevo_dni} ya está registrado")
        
        # Actualizar campos
        for campo, valor in kwargs.items():
            if hasattr(chofer, campo):
                setattr(chofer, campo, valor)
                logger.info(f"  - Actualizado {campo}: {valor}")
        
        chofer.save()
        logger.info(f"EDITAR_CHOFER - Chofer {chofer_id} actualizado exitosamente")
        
        return chofer
    
    @staticmethod
    def eliminar_chofer(chofer_id):
        """
        Elimina un chofer (solo si no tiene viajes asignados)
        
        Args:
            chofer_id: ID del chofer
            
        Raises:
            ValidationError: Si el chofer tiene viajes asociados
        """
        logger.info(f"ELIMINAR_CHOFER - Eliminando chofer {chofer_id}")
        
        try:
            chofer = Usuario.objects.get(id=chofer_id, es_chofer=True)
        except Usuario.DoesNotExist:
            logger.error(f"  - ERROR: Chofer {chofer_id} no encontrado")
            raise ValidationError(f"El chofer {chofer_id} no existe")
        
        # Validar que no tenga viajes asignados (si existe el campo chofer en Viaje)
        # Por ahora, solo lo desactivamos en lugar de eliminarlo
        chofer.activo = False
        chofer.save()
        logger.info(f"ELIMINAR_CHOFER - Chofer {chofer_id} desactivado (no eliminado por seguridad)")
        
        return chofer
    
    @staticmethod
    def obtener_choferes_por_sede(sede, solo_activos=True):
        """
        Obtiene choferes filtrados por sede
        
        Args:
            sede: Objeto Sede
            solo_activos: Si True, solo retorna choferes activos
            
        Returns:
            QuerySet: Choferes filtrados
        """
        logger.info(f"OBTENER_CHOFERES - Consultando choferes para sede: {sede}")
        
        choferes = Usuario.objects.filter(sede=sede, es_chofer=True)
        
        if solo_activos:
            choferes = choferes.filter(activo=True)
            logger.info("  - Filtrado: solo activos")
        
        logger.info(f"  - Total choferes encontrados: {choferes.count()}")
        
        return choferes
    
    @staticmethod
    def obtener_todos_choferes(solo_activos=True):
        """
        Obtiene todos los choferes (para admin)
        
        Args:
            solo_activos: Si True, solo retorna choferes activos
            
        Returns:
            QuerySet: Todos los choferes
        """
        logger.info("OBTENER_TODOS_CHOFERES - Consultando todos los choferes")
        
        choferes = Usuario.objects.filter(es_chofer=True)
        
        if solo_activos:
            choferes = choferes.filter(activo=True)
            logger.info("  - Filtrado: solo activos")
        
        logger.info(f"  - Total choferes encontrados: {choferes.count()}")
        
        return choferes
    
    @staticmethod
    def verificar_licencia_vigente(chofer):
        """
        Verifica si la licencia del chofer está vigente
        
        Args:
            chofer: Objeto Usuario (chofer)
            
        Returns:
            bool: True si está vigente, False si está vencida
        """
        if not chofer.fecha_vencimiento_licencia:
            return False
        
        return chofer.fecha_vencimiento_licencia >= date.today()