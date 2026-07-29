from django import forms
from django.core.exceptions import ValidationError
from core.models import Usuario, Vehiculo, Sede


from django import forms
from core.models import Vehiculo, Usuario


class VehiculoForm(forms.ModelForm):
    class Meta:
        model = Vehiculo
        # ✅ Eliminamos 'sede_asignada' y agregamos 'rutas_asignadas'
        fields = ['placa', 'marca', 'modelo', 'año', 'capacidad_asientos', 'rutas_asignadas', 'chofer_asignado', 'activo']
        
        widgets = {
            'placa': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500',
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
                'placeholder': '2024',
                'min': '2000',
                'max': '2030'
            }),
            'capacidad_asientos': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500',
                'placeholder': '20',
                'min': '10',
                'max': '50'
            }),
            'rutas_asignadas': forms.SelectMultiple(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500',
                'size': '4'  # Muestra 4 opciones visibles
            }),
            'chofer_asignado': forms.Select(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500'
            }),
            'activo': forms.CheckboxInput(attrs={
                'class': 'rounded border-gray-300 text-indigo-600 focus:ring-indigo-500'
            }),
        }
        
        labels = {
            'rutas_asignadas': 'Rutas Asignadas',
            'chofer_asignado': 'Chofer Asignado',
        }
        
        help_texts = {
            'rutas_asignadas': 'Mantén presionado Ctrl (Cmd en Mac) para seleccionar múltiples rutas',
        }

    def __init__(self, *args, **kwargs):
        self.usuario = kwargs.pop('usuario', None)
        super().__init__(*args, **kwargs)
        
        # Personalizar etiqueta de choferes
        self.fields['chofer_asignado'].label_from_instance = lambda obj: f"{obj.get_full_name()} ({obj.username})"
        
        # Personalizar etiqueta de rutas
        self.fields['rutas_asignadas'].label_from_instance = lambda obj: f"{obj.origen} → {obj.destino} ({obj.duracion_estimada})"
    
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