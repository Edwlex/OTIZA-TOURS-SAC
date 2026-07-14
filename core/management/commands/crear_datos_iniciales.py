from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from core.models import Sede

class Command(BaseCommand):
    help = 'Crea sedes y usuarios de prueba'

    def handle(self, *args, **options):
        Usuario = get_user_model()
        
        # Crear sedes
        sedes = {
            'trujillo': 'Av. España 123, Trujillo',
            'julcan': 'Jr. Lima 456, Julcán',
            'mache': 'Calle Principal 789, Mache',
            'central': 'Oficina Central'
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
                'username': 'admin',
                'password': 'admin123',
                'email': 'admin@otizatours.com',
                'sede': 'central',
                'es_superuser': True
            },
            {
                'username': 'cajero_trujillo',
                'password': 'cajero123',
                'email': 'trujillo@otizatours.com',
                'sede': 'trujillo',
                'es_superuser': False
            },
            {
                'username': 'cajero_julcan',
                'password': 'cajero123',
                'email': 'julcan@otizatours.com',
                'sede': 'julcan',
                'es_superuser': False
            },
            {
                'username': 'cajero_mache',
                'password': 'cajero123',
                'email': 'mache@otizatours.com',
                'sede': 'mache',
                'es_superuser': False
            }
        ]
        
        for user_data in usuarios:
            sede = Sede.objects.get(nombre=user_data['sede'])
            
            if user_data['es_superuser']:
                Usuario.objects.create_superuser(
                    username=user_data['username'],
                    password=user_data['password'],
                    email=user_data['email'],
                    sede=sede,
                    first_name=user_data['username'].title()
                )
            else:
                Usuario.objects.create_user(
                    username=user_data['username'],
                    password=user_data['password'],
                    email=user_data['email'],
                    sede=sede,
                    first_name=user_data['username'].title()
                )
            self.stdout.write(self.style.SUCCESS(f'Usuario {user_data["username"]} creado'))
        
        self.stdout.write(self.style.SUCCESS('\n✅ ¡Todos los datos iniciales creados!'))