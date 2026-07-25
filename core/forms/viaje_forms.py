from django import forms
from core.models import Viaje, Ruta, Vehiculo, Sede


class ViajeForm(forms.ModelForm):
    """Formulario para crear/editar viajes"""
    
    class Meta:
        model = Viaje
        fields = [
            'ruta', 'vehiculo', 'sede_salida',
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
            'fecha_salida': forms.DateInput(attrs={
                'type': 'date',
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500'
            }),
            'hora_salida': forms.TimeInput(attrs={
                'type': 'time',
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500'
            }),
        }

        def clean(self):
            """Validación cruzada: Fecha y hora no pueden ser en el pasado"""
            from django.utils import timezone
            
            cleaned_data = super().clean()
            fecha_salida = cleaned_data.get('fecha_salida')
            hora_salida = cleaned_data.get('hora_salida')
            
            if fecha_salida and hora_salida:
                ahora = timezone.now()
                salida_dt = timezone.make_aware(
                    timezone.datetime.combine(fecha_salida, hora_salida)
                )
                
                # Validar que no sea en el pasado
                if salida_dt < ahora:
                    raise ValidationError(
                        "No se puede programar un viaje en el pasado. "
                        "La fecha y hora de salida deben ser iguales o posteriores a la actual."
                    )
                
                # Validar que no sea hoy con hora pasada
                if fecha_salida == ahora.date() and hora_salida < ahora.time():
                    raise ValidationError(
                        f"No se puede programar un viaje para hoy antes de la hora actual ({ahora.strftime('%H:%M')})."
                    )
            
            return cleaned_data
    
    def __init__(self, *args, **kwargs):
        self.usuario = kwargs.pop('usuario', None)
        super().__init__(*args, **kwargs)
        
        # Si hay un usuario, filtrar vehículos por su sede
        if self.usuario and not self.usuario.is_superuser:
            self.fields['vehiculo'].queryset = Vehiculo.objects.filter(
                sede_asignada=self.usuario.sede,
                activo=True
            )
            self.fields['sede_salida'].initial = self.usuario.sede
            self.fields['sede_salida'].widget.attrs['readonly'] = True