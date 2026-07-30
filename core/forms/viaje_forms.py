from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.db.models import Q
from core.models import Viaje, Ruta, Vehiculo, Sede, Usuario
from datetime import date, datetime, time


class ViajeForm(forms.ModelForm):
    """Formulario para crear/editar viajes"""
    
    class Meta:
        model = Viaje
        fields = [
            'ruta', 'vehiculo', 'sede_salida', 'chofer_asignado',
            'fecha_salida', 'hora_salida'
        ]
        widgets = {
            'ruta': forms.Select(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500'
            }),
            'vehiculo': forms.Select(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500'
            }),
            'sede_salida': forms.Select(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500'
            }),
            'chofer_asignado': forms.Select(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500'
            }),
            'fecha_salida': forms.DateInput(attrs={
                'type': 'date',
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500',
                'min': date.today().isoformat(),
            }),
            'hora_salida': forms.TimeInput(attrs={
                'type': 'time',
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500',
            }),
        }
        labels = {
            'chofer_asignado': 'Chofer Asignado',
        }
        help_texts = {
            'chofer_asignado': 'Selecciona el chofer que realizará este viaje',
        }

    def __init__(self, *args, **kwargs):
        self.usuario = kwargs.pop('usuario', None)
        super().__init__(*args, **kwargs)
        
        if self.usuario:
            # 1. Filtrar choferes disponibles
            if self.usuario.is_superuser or self.usuario.sede.nombre == 'Oficina Central':
                self.fields['chofer_asignado'].queryset = Usuario.objects.filter(
                    es_chofer=True, activo=True
                )
            else:
                self.fields['chofer_asignado'].queryset = Usuario.objects.filter(
                    es_chofer=True, activo=True, sede=self.usuario.sede
                )
            
            self.fields['chofer_asignado'].label_from_instance = lambda obj: f"{obj.get_full_name()} ({obj.username})"
            
            # 2. Filtrar vehículos y bloquear sede para cajeros/no-admins
            if not self.usuario.is_superuser and self.usuario.sede.nombre != 'Oficina Central':
                self.fields['vehiculo'].queryset = Vehiculo.objects.filter(
                    sede_asignada=self.usuario.sede, activo=True
                )
                self.fields['sede_salida'].initial = self.usuario.sede
                self.fields['sede_salida'].widget.attrs['readonly'] = True 

        def clean(self):
            cleaned_data = super().clean()
            
            ruta = cleaned_data.get('ruta')
            sede_salida = cleaned_data.get('sede_salida')
            fecha_salida = cleaned_data.get('fecha_salida')
            hora_salida = cleaned_data.get('hora_salida')
            
            # ==========================================
            # 1. VALIDACIÓN Y AUTO-ASIGNACIÓN DE SEDE (SÚPER FLEXIBLE)
            # ==========================================
            if ruta:
                origen = ruta.origen.strip()
                
                # Función para normalizar texto (quitar tildes, minúsculas, espacios)
                def normalizar(texto):
                    import unicodedata
                    # Quitar tildes: "Julcán" -> "Julcan"
                    texto_normalizado = unicodedata.normalize('NFKD', texto)
                    texto_sin_tildes = ''.join([c for c in texto_normalizado if not unicodedata.combining(c)])
                    # Convertir a minúsculas y quitar "sede" si está al inicio
                    texto_limpio = texto_sin_tildes.lower().strip()
                    if texto_limpio.startswith('sede '):
                        texto_limpio = texto_limpio[5:]  # Quitar "sede "
                    return texto_limpio
                
                # Normalizar el origen de la ruta
                origen_normalizado = normalizar(origen)
                
                # Buscar todas las sedes y comparar normalizadas
                todas_las_sedes = Sede.objects.all()
                sede_encontrada = None
                
                for sede in todas_las_sedes:
                    sede_normalizada = normalizar(sede.nombre)
                    # Si el origen normalizado está contenido en la sede normalizada
                    if origen_normalizado in sede_normalizada or sede_normalizada in origen_normalizado:
                        sede_encontrada = sede
                        break
                
                if not sede_encontrada:
                    # Mostrar todas las sedes disponibles para ayudar al debug
                    sedes_disponibles = ", ".join([s.nombre for s in todas_las_sedes])
                    raise ValidationError(
                        f"No hay una sede registrada para '{origen}'. "
                        f"Sedes disponibles: {sedes_disponibles}. "
                        f"Configúrala primero en el panel de administración."
                    )

                # Si no eligió sede, la asignamos automáticamente
                if not sede_salida:
                    cleaned_data['sede_salida'] = sede_encontrada
                # Si eligió una manualmente, validamos que COINCIDA con el origen
                elif sede_salida.id != sede_encontrada.id:
                    raise ValidationError(
                        f"La sede de salida DEBE ser '{sede_encontrada.nombre}' (origen de la ruta). "
                        f"Seleccionaste '{sede_salida.nombre}'. Corrige la selección."
                    )
            
            # ==========================================
            # 2. VALIDACIÓN DE FECHA/HORA (NO PASADO)
            # ==========================================
            if fecha_salida and hora_salida:
                viaje_dt = datetime.combine(fecha_salida, hora_salida)
                ahora_local = timezone.localtime(timezone.now())
                ahora_naive = ahora_local.replace(tzinfo=None)
                
                if viaje_dt < ahora_naive:
                    raise ValidationError(
                        f"No se puede programar un viaje en el pasado. "
                        f"Ahora: {ahora_naive.strftime('%d/%m %H:%M')} | "
                        f"Viaje: {viaje_dt.strftime('%d/%m %H:%M')}"
                    )
            
            return cleaned_data