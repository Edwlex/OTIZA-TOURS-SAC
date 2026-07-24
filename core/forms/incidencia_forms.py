from django import forms
from core.models import Incidencia, Sede


class IncidenciaForm(forms.ModelForm):
    """Formulario para crear/editar incidencias"""
    
    class Meta:
        model = Incidencia
        fields = ['tipo', 'descripcion', 'sede_reporte', 'estado', 'solucion']
        widgets = {
            'tipo': forms.Select(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500'
            }),
            'descripcion': forms.Textarea(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500',
                'rows': 4,
                'placeholder': 'Describa el problema o sugerencia con detalle...'
            }),
            'sede_reporte': forms.Select(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500'
            }),
            'estado': forms.Select(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500'
            }),
            'solucion': forms.Textarea(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500',
                'rows': 3,
                'placeholder': 'Detalle de la solución aplicada...'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        self.usuario = kwargs.pop('usuario', None)
        super().__init__(*args, **kwargs)
        
        # Si es cajero, bloquear cambio de sede y estado
        if self.usuario and not self.usuario.is_superuser:
            self.fields['sede_reporte'].initial = self.usuario.sede
            self.fields['sede_reporte'].widget.attrs['readonly'] = True
            self.fields['estado'].widget.attrs['disabled'] = True
            
    def clean_descripcion(self):
        descripcion = self.cleaned_data.get('descripcion', '').strip()
        if not descripcion:
            raise ValidationError("La descripción es obligatoria")
        return descripcion