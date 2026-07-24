from django import forms
from core.models import Ruta, Sede


class VentaFiltroForm(forms.Form):
    """Formulario para filtrar lista de ventas"""
    
    fecha_desde = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 text-sm'
        })
    )
    fecha_hasta = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 text-sm'
        })
    )
    ruta = forms.ModelChoiceField(
        queryset=Ruta.objects.filter(activa=True).order_by('origen'),
        required=False,
        empty_label=" Todas las rutas",
        widget=forms.Select(attrs={
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 text-sm'
        })
    )
    buscador = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': '🔍 Buscar por ticket, cliente o ruta...',
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 text-sm'
        })
    )