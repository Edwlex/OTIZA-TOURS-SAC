from django import forms
from django.core.exceptions import ValidationError
from core.models import Incidencia

class IncidenciaForm(forms.ModelForm):
    """Formulario para crear nuevas incidencias (Cajero y Admin)"""
    
    class Meta:
        model = Incidencia
        # Solo pedimos tipo y descripción. 
        # La sede y el usuario se asignan automáticamente en la vista por seguridad.
        # El estado y la solución se manejan en la vista de "Actualizar Estado".
        fields = ['tipo', 'descripcion']
        
        widgets = {
            'tipo': forms.Select(attrs={
                'class': 'w-full px-4 py-2.5 border border-slate-300 rounded-lg focus:ring-2 focus:ring-otiza-green text-sm'
            }),
            'descripcion': forms.Textarea(attrs={
                'rows': 4,
                'class': 'w-full px-4 py-2.5 border border-slate-300 rounded-lg focus:ring-2 focus:ring-otiza-green text-sm',
                'placeholder': 'Describe el problema o sugerencia con el mayor detalle posible...'
            }),
        }

    def clean_descripcion(self):
        """Validación extra para asegurar que la descripción no esté vacía o sea solo espacios"""
        descripcion = self.cleaned_data.get('descripcion', '').strip()
        if not descripcion:
            raise ValidationError("La descripción es obligatoria y no puede estar vacía.")
        return descripcion