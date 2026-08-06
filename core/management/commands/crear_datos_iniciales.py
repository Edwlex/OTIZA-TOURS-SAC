from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from core.models import Sede

class Command(BaseCommand):
    help = 'Crea sedes y usuarios iniciales (Admin, Cajeros y Chofer genérico)'

    def handle(self, *args, **options):
        Usuario = get_user_model()
        
        self.stdout.write(self.style.WARNING('🔄 Iniciando creación de datos iniciales...'))

        # 1. CREAR SEDES
        sedes_data = {
            'Sede Trujillo': 'Prol. Unión N.° 1477, Trujillo',
            'Sede Julcán': 'Cal. La Cultura S/N, Julcán',
            'Sede Mache': 'Cal. Las Maravillas N.° 102, Mache',
            'Oficina Central': 'Sede Administrativa Principal - Trujillo',
            'Unidad Móvil': 'Unidad Móvil (Para Choferes)' # ✅ Agregada para el chofer
        }
        
        sedes_creadas = {}
        for nombre, direccion in sedes_data.items():
            sede, creada = Sede.objects.get_or_create(
                nombre=nombre,
                defaults={'direccion': direccion}
            )
            sedes_creadas[nombre] = sede
            status = "creada" if creada else "ya existía"
            self.stdout.write(self.style.SUCCESS(f'✅ Sede "{nombre}" {status}'))

        # 2. CREAR USUARIOS ADMIN Y CAJEROS
        usuarios_data = [
            {
                'username': 'admin_general',
                'password': 'OtizaAdmin#2026',
                'email': 'admin@otizatours.com',
                'sede_nombre': 'Oficina Central',
                'es_superuser': True,
                'es_cajero': False
            },
            {
                'username': 'sede_trujillo',
                'password': 'OtzTRU#8472',
                'email': 'trujillo@otizatours.com',
                'sede_nombre': 'Sede Trujillo',
                'es_superuser': False,
                'es_cajero': True
            },
            {
                'username': 'sede_julcan',
                'password': 'OtzJUL#5918',
                'email': 'julcan@otizatours.com',
                'sede_nombre': 'Sede Julcán',
                'es_superuser': False,
                'es_cajero': True
            },
            {
                'username': 'sede_mache',
                'password': 'OtzMAC#3264',
                'email': 'mache@otizatours.com',
                'sede_nombre': 'Sede Mache',
                'es_superuser': False,
                'es_cajero': True
            }
        ]
        
        for data in usuarios_data:
            sede = sedes_creadas[data['sede_nombre']]
            
            user, creado = Usuario.objects.get_or_create(
                username=data['username'],
                defaults={
                    'email': data['email'],
                    'sede': sede,
                    'first_name': data['username'].replace('_', ' ').title(),
                    'is_staff': data['es_superuser'],
                    'is_superuser': data['es_superuser'],
                    'es_cajero': data['es_cajero'],
                    'es_chofer': False,
                    'activo': True
                }
            )
            
            # ✅ Siempre actualizamos la contraseña por seguridad
            user.set_password(data['password'])
            user.save()
            
            status = "creado" if creado else "actualizado"
            self.stdout.write(self.style.SUCCESS(f'✅ Usuario "{data["username"]}" {status}'))

        # 3. CREAR USUARIO GENÉRICO "CHOFER"
        chofer_data = {
            'username': 'chofer',
            'password': 'ChoferOtiza26',
            'email': 'chofer@otizatours.com',
            'sede': sedes_creadas['Unidad Móvil']
        }
        
        chofer, creado = Usuario.objects.get_or_create(
            username=chofer_data['username'],
            defaults={
                'email': chofer_data['email'],
                'sede': chofer_data['sede'],
                'first_name': 'ACCESO',
                'last_name': 'CHOFER',
                'es_chofer': True,
                'es_cajero': False,
                'is_staff': False,
                'is_superuser': False,
                'activo': True
            }
        )
        
        # ✅ Actualizar contraseña y sede por si acaso
        chofer.set_password(chofer_data['password'])
        chofer.sede = chofer_data['sede']
        chofer.save()
        
        status = "creado" if creado else "actualizado"
        self.stdout.write(self.style.SUCCESS(f'✅ Usuario genérico "chofer" {status}'))

        self.stdout.write(self.style.SUCCESS('\n🎉 ¡Proceso de inicialización completado con éxito!'))