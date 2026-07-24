from django import forms
from django.core.exceptions import ValidationError
from core.models import Ruta


class RutaForm(forms.ModelForm):
    """Formulario para crear/editar rutas"""
    
    class Meta:
        model = Ruta
        fields = ['origen', 'destino', 'distancia_km', 'duracion_estimada', 'precio_base', 'activa']
        widgets = {
            'origen': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500',
                'placeholder': 'Trujillo',
                'list': 'origen-list'
            }),
            'destino': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500',
                'placeholder': 'Julcán',
                'list': 'destino-list'
            }),
            'distancia_km': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500',
                'placeholder': '85.50',
                'step': '0.01',
                'min': '0.01'
            }),
            'duracion_estimada': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500',
                'placeholder': '2 horas 30 min'
            }),
            'precio_base': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500',
                'placeholder': '25.00',
                'step': '0.01',
                'min': '0.01'
            }),
            'activa': forms.CheckboxInput(attrs={
                'class': 'w-4 h-4 text-indigo-600 border-gray-300 rounded focus:ring-indigo-500'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        self.usuario = kwargs.pop('usuario', None)
        super().__init__(*args, **kwargs)
    
    def clean_origen(self):
        """Validar origen"""
        origen = self.cleaned_data.get('origen', '').strip()
        
        if not origen:
            raise ValidationError("El origen es obligatorio")
        
        if len(origen) < 3:
            raise ValidationError("El nombre de la ciudad debe tener al menos 3 caracteres")
        
        return origen.title()
    
    def clean_destino(self):
        """Validar destino"""
        destino = self.cleaned_data.get('destino', '').strip()
        
        if not destino:
            raise ValidationError("El destino es obligatorio")
        
        if len(destino) < 3:
            raise ValidationError("El nombre de la ciudad debe tener al menos 3 caracteres")
        
        return destino.title()
    
    def clean(self):
        """Validación cruzada entre origen y destino"""
        cleaned_data = super().clean()
        origen = cleaned_data.get('origen')
        destino = cleaned_data.get('destino')
        
        if origen and destino:
            if origen.strip().lower() == destino.strip().lower():
                raise ValidationError("El origen y destino no pueden ser la misma ciudad")
            
            # Verificar que no exista la ruta (solo al crear)
            if not self.instance.pk:
                if Ruta.objects.filter(
                    origen__iexact=origen,
                    destino__iexact=destino
                ).exists():
                    raise ValidationError(
                        f"La ruta {origen} → {destino} ya está registrada"
                    )
        
        return cleaned_data
    
    def clean_distancia_km(self):
        """Validar distancia"""
        distancia = self.cleaned_data.get('distancia_km')
        
        if distancia is None or distancia <= 0:
            raise ValidationError("La distancia debe ser mayor a 0 km")
        
        return distancia
    
    def clean_precio_base(self):
        """Validar precio"""
        precio = self.cleaned_data.get('precio_base')
        
        if precio is None or precio <= 0:
            raise ValidationError("El precio base debe ser mayor a 0")
        
        return precio