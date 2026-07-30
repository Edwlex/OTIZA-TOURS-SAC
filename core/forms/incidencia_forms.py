from django import forms
from django.core.exceptions import ValidationError
from core.models import Incidencia

class IncidenciaForm(forms.ModelForm):
    class Meta:
        model = Incidencia
        # ✅ SOLO LOS CAMPOS QUE REALMENTE EXISTEN EN TU MODELO
        fields = ['tipo', 'descripcion']
        
        widgets = {
            'tipo': forms.Select(attrs={
                'class': 'w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-emerald-500'
            }),
            'descripcion': forms.Textarea(attrs={
                'rows': 4,
                'class': 'w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-emerald-500',
                'placeholder': 'Describe el problema o sugerencia con el mayor detalle posible...'
            }),
        }

    def clean_descripcion(self):
        """Validación extra para asegurar que la descripción no esté vacía"""
        descripcion = self.cleaned_data.get('descripcion', '').strip()
        if not descripcion:
            raise ValidationError("La descripción es obligatoria y no puede estar vacía.")
        return descripcion