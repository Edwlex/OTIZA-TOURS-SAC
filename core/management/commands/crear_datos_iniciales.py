from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from core.models import Sede

class Command(BaseCommand):
    help = 'Crea sedes y usuarios de prueba'

    def handle(self, *args, **options):
        Usuario = get_user_model()
        
        # Crear sedes
        sedes = {
            'Sede Trujillo': 'Prol. Unión N.° 1477, Trujillo',
            'Sede Julcán': 'Cal. La Cultura S/N, Julcán',
            'Sede Mache': 'Cal. Las Maravillas N.° 102, Mache',
            'Oficina Central': 'Sede Administrativa Principal - Trujillo'
        }
        
        for nombre, direccion in sedes.items():
            Sede.objects.get_or_create(
                nombre=nombre,
                defaults={'direccion': direccion}
            )
            self.stdout.write(self.style.SUCCESS(f'Sede {nombre} creada'))
        
        # Crear usuarios
        usuarios = [
            {
                'username': 'admin_general',
                'password': 'OtizaAdmin#2026',
                'email': 'admin@otizatours.com',
                'sede': 'Oficina Central',
                'es_superuser': True
            },
            {
                'username': 'sede_trujillo',
                'password': 'OtzTRU#8472',
                'email': 'trujillo@otizatours.com',
                'sede': 'Sede Trujillo',
                'es_superuser': False
            },
            {
                'username': 'sede_julcan',
                'password': 'OtzJUL#5918',
                'email': 'julcan@otizatours.com',
                'sede': 'Sede Julcán',
                'es_superuser': False
            },
            {
                'username': 'sede_mache',
                'password': 'OtzMAC#3264',
                'email': 'mache@otizatours.com',
                'sede': 'Sede Mache',
                'es_superuser': False
            }
        ]
        
        for user_data in usuarios:
            sede = Sede.objects.get(nombre=user_data['sede'])
            
            # ✅ Usar get_or_create en lugar de create_user/create_superuser
            user, creado = Usuario.objects.get_or_create(
                username=user_data['username'],
                defaults={
                    'email': user_data['email'],
                    'sede': sede,
                    'first_name': user_data['username'].title(),
                    'is_staff': user_data['es_superuser'],
                    'is_superuser': user_data['es_superuser'],
                    'es_cajero': not user_data['es_superuser'],
                    'activo': True
                }
            )
            
            # ✅ Actualizar contraseña SIEMPRE (por si se resetea)
            user.set_password(user_data['password'])
            user.save()
            
            status = "creado" if creado else "actualizado"
            self.stdout.write(self.style.SUCCESS(f'Usuario {user_data["username"]} {status}'))