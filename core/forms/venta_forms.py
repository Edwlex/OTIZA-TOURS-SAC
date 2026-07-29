from django import forms
from core.models import Ruta


class VentaFiltroForm(forms.Form):
    """Formulario para filtrar lista de ventas"""
    
    fecha_desde = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 text-sm',
            'placeholder': 'dd/mm/aaaa'
        })
    )
    
    fecha_hasta = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 text-sm',
            'placeholder': 'dd/mm/aaaa'
        })
    )
    
    ruta = forms.ChoiceField(
        required=False,
        choices=[],  # Se llena dinámicamente en __init__
        widget=forms.Select(attrs={
            'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 text-sm'
        })
    )
    
    buscador = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': '🔍 Buscar por ticket, cliente o DNI...',
            'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 text-sm'
        })
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # ✅ Cargar rutas activas dinámicamente desde la BD
        rutas_qs = Ruta.objects.filter(activa=True).order_by('origen', 'destino')
        self.fields['ruta'].choices = [('', ' Todas las rutas')] + [
            (ruta.id, f"{ruta.origen} → {ruta.destino}") for ruta in rutas_qs
        ]