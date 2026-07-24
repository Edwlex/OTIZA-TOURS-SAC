from django import forms
from core.models import Viaje, Ruta, Vehiculo, Sede


class ViajeForm(forms.ModelForm):
    """Formulario para crear/editar viajes"""
    
    class Meta:
        model = Viaje
        fields = [
            'ruta', 'vehiculo', 'sede_salida',
            'fecha_salida', 'hora_salida',
            'fecha_llegada', 'hora_llegada'
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
            'fecha_llegada': forms.DateInput(attrs={
                'type': 'date',
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500'
            }),
            'hora_llegada': forms.TimeInput(attrs={
                'type': 'time',
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500'
            }),
        }
    
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