from django.core.management.base import BaseCommand
from django.utils import timezone
from core.models import Venta, AsientoViaje

class Command(BaseCommand):
    help = 'Limpia ventas y reservas, liberando asientos ocupados.'

    def add_arguments(self, parser):
        parser.add_argument('--sin-filtro', action='store_true', help='Eliminar TODO sin importar fecha (PELIGRO)')
        parser.add_argument('--viaje', type=int, help='ID del viaje específico a limpiar')
        parser.add_argument('--force', action='store_true', help='Ejecutar sin pedir confirmación')

    def handle(self, *args, **options):
        force = options['force']
        total_liberados = 0

        self.stdout.write(self.style.WARNING('\n INICIANDO LIMPIEZA DEL SISTEMA...'))

        # 1. OBTENER ASIENTOS A LIMPIAR (Reservados o Vendidos)
        qs_asientos = AsientoViaje.objects.filter(estado__in=['reservado', 'vendido'])

        if options['viaje']:
            qs_asientos = qs_asientos.filter(viaje_id=options['viaje'])
            self.stdout.write(f'🔍 Filtrando solo por Viaje ID: {options["viaje"]}')
        elif not options['sin_filtro']:  # ✅ CORREGIDO: sin_filtro (con guion bajo)
            # Si no es --sin-filtro, solo limpia los de HOY
            hoy = timezone.now().date()
            qs_asientos = qs_asientos.filter(viaje__fecha_salida=hoy)
            self.stdout.write(f'📅 Filtrando por fecha de hoy: {hoy}')

        total_a_limpiar = qs_asientos.count()

        if total_a_limpiar == 0:
            self.stdout.write(self.style.SUCCESS('\n✅ No hay asientos ocupados/reservados para limpiar.'))
            return

        self.stdout.write(self.style.ERROR(f'\n⚠️ ENCONTRADOS: {total_a_limpiar} asientos ocupados/reservados.'))

        # Confirmación
        if not force:
            response = input('\n¿Estás seguro de liberar todos estos asientos y borrar sus ventas? (s/n): ')
            if response.lower() != 's':
                self.stdout.write(self.style.WARNING('Operación cancelada.'))
                return

        # 2. EJECUTAR LIMPIEZA
        for asiento in qs_asientos:
            self.stdout.write(f'    Limpiando asiento {asiento.numero_asiento} (Estado actual: {asiento.estado})')

            # A. Borrar venta asociada si existe (evita errores de integridad)
            try:
                ventas_asociadas = Venta.objects.filter(asiento=asiento)
                if ventas_asociadas.exists():
                    self.stdout.write(f'      ️ Borrando venta {ventas_asociadas.first().numero_ticket}')
                    ventas_asociadas.delete()
            except Exception as e:
                self.stdout.write(f'      ⚠️ Error al borrar venta: {e}')

            # B. Liberar el asiento (volver a disponible)
            asiento.estado = 'disponible'
            asiento.nombre_reserva = None
            asiento.telefono_reserva = None
            asiento.save()

            total_liberados += 1
            self.stdout.write(self.style.SUCCESS(f'      ✅ Asiento liberado.'))

        # RESUMEN FINAL
        self.stdout.write(self.style.SUCCESS(f'\n{"="*50}'))
        self.stdout.write(self.style.SUCCESS(f'🎯 ¡LIMPIEZA COMPLETADA!'))
        self.stdout.write(self.style.SUCCESS(f'   ✅ {total_liberados} asientos liberados y listos para vender.'))
        self.stdout.write(self.style.SUCCESS(f'{"="*50}\n'))