import logging
from django.core.exceptions import ValidationError
from core.models import Usuario, Sede

logger = logging.getLogger('core.usuario_service')


class UsuarioService:
    """Servicio para manejar la lógica de negocio de usuarios/cajeros"""
    
    @staticmethod
    def crear_usuario(username, password, email, first_name, last_name, sede_asignada, 
                      telefono, es_cajero, creado_por):
        """
        Crea un nuevo usuario (cajero)
        
        Args:
            username: Nombre de usuario único
            password: Contraseña
            email: Email
            first_name: Nombre
            last_name: Apellido
            sede_asignada: Objeto Sede
            telefono: Teléfono
            es_cajero: Boolean (True para cajero)
            creado_por: Usuario que crea el usuario
            
        Returns:
            Usuario: El usuario creado
            
        Raises:
            ValidationError: Si hay datos inválidos o el usuario ya existe
        """
        logger.info("=" * 60)
        logger.info("CREAR_USUARIO - Iniciando creación de usuario")
        logger.info(f"  - Username: {username}")
        logger.info(f"  - Email: {email}")
        logger.info(f"  - Sede asignada: {sede_asignada}")
        logger.info(f"  - Es cajero: {es_cajero}")
        logger.info(f"  - Creado por: {creado_por.username}")
        
        # 1. Validar que el username no exista
        if Usuario.objects.filter(username=username).exists():
            logger.error(f"  - ERROR: El usuario {username} ya existe")
            raise ValidationError(f"El usuario {username} ya está registrado en el sistema")
        
        # 2. Validar que el email no exista
        if Usuario.objects.filter(email=email).exists():
            logger.error(f"  - ERROR: El email {email} ya existe")
            raise ValidationError(f"El email {email} ya está registrado en el sistema")
        
        # 3. Validar contraseña
        if len(password) < 6:
            logger.error(f"  - ERROR: Contraseña muy corta")
            raise ValidationError("La contraseña debe tener al menos 6 caracteres")
        
        # 4. Crear el usuario
        logger.info("  - Creando usuario en BD...")
        usuario = Usuario.objects.create_user(
            username=username,
            password=password,
            email=email,
            first_name=first_name,
            last_name=last_name,
            sede=sede_asignada,
            telefono=telefono,
            es_cajero=es_cajero,
            activo=True
        )
        
        logger.info(f"  - Usuario creado con ID: {usuario.id}")
        logger.info("CREAR_USUARIO - Completado exitosamente")
        logger.info("=" * 60)
        
        return usuario
    
    @staticmethod
    def editar_usuario(usuario_id, **kwargs):
        """
        Edita un usuario existente
        
        Args:
            usuario_id: ID del usuario
            **kwargs: Campos a actualizar
            
        Returns:
            Usuario: El usuario actualizado
        """
        logger.info(f"EDITAR_USUARIO - Actualizando usuario {usuario_id}")
        
        try:
            usuario = Usuario.objects.get(id=usuario_id)
        except Usuario.DoesNotExist:
            logger.error(f"  - ERROR: Usuario {usuario_id} no encontrado")
            raise ValidationError(f"El usuario {usuario_id} no existe")
        
        # Si se está cambiando el username, validar que no exista
        if 'username' in kwargs:
            nuevo_username = kwargs['username']
            if Usuario.objects.filter(username=nuevo_username).exclude(id=usuario_id).exists():
                logger.error(f"  - ERROR: El usuario {nuevo_username} ya existe")
                raise ValidationError(f"El usuario {nuevo_username} ya está registrado")
        
        # Si se está cambiando el email, validar que no exista
        if 'email' in kwargs:
            nuevo_email = kwargs['email']
            if Usuario.objects.filter(email=nuevo_email).exclude(id=usuario_id).exists():
                logger.error(f"  - ERROR: El email {nuevo_email} ya existe")
                raise ValidationError(f"El email {nuevo_email} ya está registrado")
        
        # Actualizar campos
        for campo, valor in kwargs.items():
            if hasattr(usuario, campo):
                setattr(usuario, campo, valor)
                logger.info(f"  - Actualizado {campo}: {valor}")
        
        usuario.save()
        logger.info(f"EDITAR_USUARIO - Usuario {usuario_id} actualizado exitosamente")
        
        return usuario
    
    @staticmethod
    def eliminar_usuario(usuario_id):
        """
        Elimina un usuario (solo si no tiene ventas asociadas)
        
        Args:
            usuario_id: ID del usuario
            
        Raises:
            ValidationError: Si el usuario tiene ventas asociadas
        """
        logger.info(f"ELIMINAR_USUARIO - Eliminando usuario {usuario_id}")
        
        try:
            usuario = Usuario.objects.get(id=usuario_id)
        except Usuario.DoesNotExist:
            logger.error(f"  - ERROR: Usuario {usuario_id} no encontrado")
            raise ValidationError(f"El usuario {usuario_id} no existe")
        
        # Validar que no tenga ventas
        if usuario.ventas.exists():
            logger.error(f"  - ERROR: Usuario {usuario.username} tiene ventas asociadas")
            raise ValidationError(
                f"No se puede eliminar el usuario {usuario.username} porque tiene ventas asociadas"
            )
        
        usuario.delete()
        logger.info(f"ELIMINAR_USUARIO - Usuario {usuario_id} eliminado exitosamente")
    
    @staticmethod
    def obtener_usuarios_por_sede(sede, solo_activos=True):
        """
        Obtiene usuarios filtrados por sede
        
        Args:
            sede: Objeto Sede
            solo_activos: Si True, solo retorna usuarios activos
            
        Returns:
            QuerySet: Usuarios filtrados
        """
        logger.info(f"OBTENER_USUARIOS - Consultando usuarios para sede: {sede}")
        
        usuarios = Usuario.objects.filter(sede=sede)
        
        if solo_activos:
            usuarios = usuarios.filter(activo=True)
            logger.info("  - Filtrado: solo activos")
        
        logger.info(f"  - Total usuarios encontrados: {usuarios.count()}")
        
        return usuarios
    
    @staticmethod
    def obtener_todos_usuarios(solo_activos=True):
        """
        Obtiene todos los usuarios (para admin)
        
        Args:
            solo_activos: Si True, solo retorna usuarios activos
            
        Returns:
            QuerySet: Todos los usuarios
        """
        logger.info("OBTENER_TODOS_USUARIOS - Consultando todos los usuarios")
        
        usuarios = Usuario.objects.all()
        
        if solo_activos:
            usuarios = usuarios.filter(activo=True)
            logger.info("  - Filtrado: solo activos")
        
        logger.info(f"  - Total usuarios encontrados: {usuarios.count()}")
        
        return usuarios