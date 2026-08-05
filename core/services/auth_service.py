import logging
from django.contrib.auth import authenticate
from django.core.exceptions import ValidationError
from core.models import Usuario, Sede

logger = logging.getLogger('core.auth_service')

class AuthService:
    """Servicio para manejar la autenticación de usuarios"""
    
    @staticmethod
    def authenticate_user(username, password, sede_nombre):
        """
        Autentica un usuario y verifica que pertenezca a la sede seleccionada
        """
        logger.info(f"[DEBUG] AUTHENTICATE_USER llamado")
        logger.info(f"   - Username: {username}")
        logger.info(f"   - Sede solicitada: {sede_nombre}")
        
        # 1. Verificar que la sede exista (necesario para validar a los demás usuarios)
        try:
            logger.debug(f"Buscando sede: {sede_nombre}")
            sede = Sede.objects.get(nombre=sede_nombre, activa=True)
            logger.info(f"[OK] Sede encontrada: {sede.nombre}")
        except Sede.DoesNotExist:
            logger.error(f"[ERROR] Sede NO encontrada: {sede_nombre} (o está inactiva)")
            raise ValidationError(f"La sede seleccionada no existe o está inactiva")
        
        # 2. Autenticar usuario con Django
        logger.debug(f"Intentando autenticar usuario: {username}")
        user = authenticate(username=username, password=password)
        
        if user is None:
            logger.error(f"[ERROR] Autenticación fallida - Usuario/contraseña incorrectos")
            return None
        
        logger.info(f"[OK] Autenticación Django exitosa para: {user.username}")
        
        # 3. ✅ AQUÍ ESTÁ LA NUEVA LÓGICA DE VALIDACIÓN DE SEDE ✅
        if username == 'chofer':
            # Si es el usuario genérico "chofer", omitimos la validación estricta.
            # Su sede real es "Unidad Móvil", pero el formulario puede enviar "Oficina Central" u otra.
            logger.info(f"[OK] Usuario 'chofer' omitiendo validación estricta de sede (pertenece a Unidad Móvil)")
        else:
            # Para TODOS los demás usuarios (cajeros, admin), la validación es estricta
            if user.sede != sede:
                logger.error(f"[ERROR] Usuario {username} NO pertenece a la sede {sede_nombre}")
                logger.error(f"   - Pertenece a: {user.sede.nombre if user.sede else 'Ninguna'}")
                raise ValidationError(
                    f"El usuario {username} no pertenece a la sede {sede.get_nombre_display()}"
                )
            logger.info(f"[OK] Usuario {username} pertenece correctamente a {sede.nombre}")
        
        # 4. Verificar que el usuario esté activo
        if not user.is_active:
            logger.error(f" Cuenta de {username} está DESACTIVADA")
            raise ValidationError(f"La cuenta de {username} está desactivada")
        
        logger.info(f"[OK] Usuario {username} está ACTIVO")
        logger.info(f"[OK] AUTENTICACIÓN COMPLETADA EXITOSAMENTE")
        
        return user
    
    @staticmethod
    def get_user_sede(user):
        """Obtiene la sede del usuario de forma segura"""
        return getattr(user, 'sede', None) 