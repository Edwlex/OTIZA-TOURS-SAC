from django.core.management.base import BaseCommand
from django.utils import timezone
from core.models import HorarioFijo, Viaje, AsientoViaje
from datetime import timedelta, datetime

class Command(BaseCommand):
    help = 'Genera viajes para los próximos N días basado en horarios fijos'
    
    def add_arguments(self, parser):
        parser.add_argument('--dias', type=int, default=7, help='Días a generar (default: 7)')
    
    def handle(self, *args, **options):
        dias = options['dias']
        hoy = timezone.now().date()
        viajes_creados = 0
        errores = 0
        
        self.stdout.write(self.style.SUCCESS(f' Buscando horarios fijos activos...'))
        
        # Obtener todos los horarios activos
        horarios = HorarioFijo.objects.filter(activa=True).select_related('ruta', 'vehiculo')
        self.stdout.write(f'📅 Encontrados {horarios.count()} horarios activos')
        
        if horarios.count() == 0:
            self.stdout.write(self.style.ERROR(' No hay horarios fijos configurados'))
            return
        
        for i in range(dias):
            fecha_objetivo = hoy + timedelta(days=i)
            dia_semana = fecha_objetivo.weekday() + 1  # 1=Lun, 7=Dom
            
            self.stdout.write(f'\n📅 Procesando {fecha_objetivo} (Día {dia_semana})')
            
            # Filtrar horarios para este día de la semana
            horarios_del_dia = [h for h in horarios if str(dia_semana) in h.dias_semana]
            
            if not horarios_del_dia:
                self.stdout.write(self.style.WARNING(f'  ️ No hay horarios para el día {dia_semana}'))
                continue
            
            for horario in horarios_del_dia:
                try:
                    # Validar que el vehículo tenga sede asignada
                    if not horario.vehiculo.sede_asignada:
                        self.stdout.write(self.style.ERROR(
                            f'  ❌ Vehículo {horario.vehiculo.placa} no tiene sede asignada'
                        ))
                        errores += 1
                        continue
                    
                    # Verificar si ya existe el viaje
                    existe = Viaje.objects.filter(
                        ruta=horario.ruta,
                        vehiculo=horario.vehiculo,
                        fecha_salida=fecha_objetivo,
                        hora_salida=horario.hora_salida
                    ).exists()
                    
                    if existe:
                        self.stdout.write(self.style.WARNING(
                            f'  ️ Ya existe: {horario.hora_salida} - {horario.ruta}'
                        ))
                        continue
                    
                    # Calcular hora de llegada
                    duracion_texto = str(horario.ruta.duracion_estimada).lower()
                    horas = 2  # Default
                    if 'h' in duracion_texto:
                        try:
                            horas = int(duracion_texto.split('h')[0].strip())
                        except:
                            pass
                    
                    salida_dt = datetime.combine(fecha_objetivo, horario.hora_salida)
                    llegada_dt = salida_dt + timedelta(hours=horas)
                    
                    # Crear viaje
                    viaje = Viaje.objects.create(
                        ruta=horario.ruta,
                        vehiculo=horario.vehiculo,
                        sede_salida=horario.vehiculo.sede_asignada,
                        fecha_salida=fecha_objetivo,
                        hora_salida=horario.hora_salida,
                        fecha_llegada=llegada_dt.date(),
                        hora_llegada=llegada_dt.time(),
                        estado='programado'
                    )
                    
                    # Generar asientos
                    capacidad = horario.vehiculo.capacidad_asientos or 20
                    for num in range(1, capacidad + 1):
                        AsientoViaje.objects.create(
                            viaje=viaje,
                            numero_asiento=str(num),
                            estado='disponible',
                            precio=horario.ruta.precio_base or 50
                        )
                    
                    viajes_creados += 1
                    self.stdout.write(self.style.SUCCESS(
                        f'  ✅ {horario.hora_salida}: {horario.ruta.origen} → {horario.ruta.destino}'
                    ))
                    
                except Exception as e:
                    errores += 1
                    self.stdout.write(self.style.ERROR(f'  ❌ Error: {str(e)}'))
        
        # Resumen final
        self.stdout.write('\n' + '='*60)
        self.stdout.write(self.style.SUCCESS(f'✅ GENERACIÓN COMPLETADA'))
        self.stdout.write(f'📊 Viajes creados: {viajes_creados}')
        self.stdout.write(f'⚠️ Errores/Saltados: {errores}')
        self.stdout.write('='*60)