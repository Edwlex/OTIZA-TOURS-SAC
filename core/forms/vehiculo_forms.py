from django import forms
from django.core.exceptions import ValidationError
from core.models import Vehiculo, Sede


class VehiculoForm(forms.ModelForm):
    """Formulario para crear/editar vehículos"""
    
    class Meta:
        model = Vehiculo
        fields = ['placa', 'marca', 'modelo', 'año', 'capacidad_asientos', 'sede_asignada', 'activo']
        widgets = {
            'placa': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 uppercase',
                'placeholder': 'ABC-123',
                'maxlength': '20'
            }),
            'marca': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500',
                'placeholder': 'Toyota'
            }),
            'modelo': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500',
                'placeholder': 'Hiace'
            }),
            'año': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500',
                'min': '1990',
                'max': '2030'
            }),
            'capacidad_asientos': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500',
                'min': '1',
                'max': '100'
            }),
            'sede_asignada': forms.Select(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500'
            }),
            'activo': forms.CheckboxInput(attrs={
                'class': 'w-4 h-4 text-indigo-600 border-gray-300 rounded focus:ring-indigo-500'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        self.usuario = kwargs.pop('usuario', None)
        super().__init__(*args, **kwargs)
        
        # Si hay un usuario no-admin, limitar sedes
        if self.usuario and not self.usuario.is_superuser:
            self.fields['sede_asignada'].queryset = Sede.objects.filter(
                nombre=self.usuario.sede.nombre
            )
    
    def clean_placa(self):
        """Validar formato de placa"""
        placa = self.cleaned_data.get('placa', '').upper()
        
        if len(placa) < 6:
            raise ValidationError("La placa debe tener al menos 6 caracteres")
        
        return placa
    
    def clean_año(self):
        """Validar año"""
        from django.utils import timezone
        año = self.cleaned_data.get('año')
        año_actual = timezone.now().year
        
        if año < 1990 or año > año_actual + 1:
            raise ValidationError(f"El año debe estar entre 1990 y {año_actual + 1}")
        
        return año
    
    def clean_capacidad_asientos(self):
        """Validar capacidad"""
        capacidad = self.cleaned_data.get('capacidad_asientos')
        
        if capacidad < 1 or capacidad > 100:
            raise ValidationError("La capacidad debe estar entre 1 y 100 asientos")
        
        return capacidad