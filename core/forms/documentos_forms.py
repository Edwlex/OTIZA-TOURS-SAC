from django import forms
from django.forms import inlineformset_factory
from core.models import HojaRuta, Manifiesto, PasajeroManifiesto, Viaje

class HojaRutaForm(forms.ModelForm):
    class Meta:
        model = HojaRuta
        fields = [
            'conductor1_nombre', 'conductor1_licencia', 
            'conductor1_hora_inicio', 'conductor1_hora_fin',
            'conductor2_nombre', 'conductor2_licencia',
            'conductor2_hora_inicio', 'conductor2_hora_fin',
            'conductor3_nombre', 'conductor3_licencia',
            'incidente1_nombres', 'incidente1_constancia',
            'incidente1_firma', 'incidente1_dni',
            'incidente2_nombres', 'incidente2_constancia',
            'incidente2_firma', 'incidente2_dni',
            'incidente3_nombres', 'incidente3_constancia',
            'incidente3_firma', 'incidente3_dni',
            'incidente4_nombres', 'incidente4_constancia',
            'incidente4_firma', 'incidente4_dni',
        ]
        widgets = {
            'conductor1_nombre': forms.TextInput(attrs={'class': 'w-full px-3 py-2 border border-slate-300 rounded-lg'}),
            'conductor1_licencia': forms.TextInput(attrs={'class': 'w-full px-3 py-2 border border-slate-300 rounded-lg'}),
            'conductor1_hora_inicio': forms.TextInput(attrs={'class': 'w-full px-3 py-2 border border-slate-300 rounded-lg'}),
            'conductor1_hora_fin': forms.TextInput(attrs={'class': 'w-full px-3 py-2 border border-slate-300 rounded-lg'}),
            
            'conductor2_nombre': forms.TextInput(attrs={'class': 'w-full px-3 py-2 border border-slate-300 rounded-lg'}),
            'conductor2_licencia': forms.TextInput(attrs={'class': 'w-full px-3 py-2 border border-slate-300 rounded-lg'}),
            'conductor2_hora_inicio': forms.TextInput(attrs={'class': 'w-full px-3 py-2 border border-slate-300 rounded-lg'}),
            'conductor2_hora_fin': forms.TextInput(attrs={'class': 'w-full px-3 py-2 border border-slate-300 rounded-lg'}),
            
            'conductor3_nombre': forms.TextInput(attrs={'class': 'w-full px-3 py-2 border border-slate-300 rounded-lg'}),
            'conductor3_licencia': forms.TextInput(attrs={'class': 'w-full px-3 py-2 border border-slate-300 rounded-lg'}),
            
            'incidente1_nombres': forms.TextInput(attrs={'class': 'w-full px-3 py-2 border border-slate-300 rounded-lg'}),
            'incidente1_constancia': forms.Textarea(attrs={'rows': 2, 'class': 'w-full px-3 py-2 border border-slate-300 rounded-lg'}),
            'incidente1_firma': forms.TextInput(attrs={'class': 'w-full px-3 py-2 border border-slate-300 rounded-lg'}),
            'incidente1_dni': forms.TextInput(attrs={'class': 'w-full px-3 py-2 border border-slate-300 rounded-lg'}),
            'incidente2_nombres': forms.TextInput(attrs={'class': 'w-full px-3 py-2 border border-slate-300 rounded-lg'}),
            'incidente2_constancia': forms.Textarea(attrs={'rows': 2, 'class': 'w-full px-3 py-2 border border-slate-300 rounded-lg'}),
            'incidente2_firma': forms.TextInput(attrs={'class': 'w-full px-3 py-2 border border-slate-300 rounded-lg'}),
            'incidente2_dni': forms.TextInput(attrs={'class': 'w-full px-3 py-2 border border-slate-300 rounded-lg'}),
            'incidente3_nombres': forms.TextInput(attrs={'class': 'w-full px-3 py-2 border border-slate-300 rounded-lg'}),
            'incidente3_constancia': forms.Textarea(attrs={'rows': 2, 'class': 'w-full px-3 py-2 border border-slate-300 rounded-lg'}),
            'incidente3_firma': forms.TextInput(attrs={'class': 'w-full px-3 py-2 border border-slate-300 rounded-lg'}),
            'incidente3_dni': forms.TextInput(attrs={'class': 'w-full px-3 py-2 border border-slate-300 rounded-lg'}),
            'incidente4_nombres': forms.TextInput(attrs={'class': 'w-full px-3 py-2 border border-slate-300 rounded-lg'}),
            'incidente4_constancia': forms.Textarea(attrs={'rows': 2, 'class': 'w-full px-3 py-2 border border-slate-300 rounded-lg'}),
            'incidente4_firma': forms.TextInput(attrs={'class': 'w-full px-3 py-2 border border-slate-300 rounded-lg'}),
            'incidente4_dni': forms.TextInput(attrs={'class': 'w-full px-3 py-2 border border-slate-300 rounded-lg'}),
        }

    def __init__(self, *args, **kwargs):
        self.sede = kwargs.pop('sede', None)
        self.hora_salida = kwargs.pop('hora_salida', None)
        self.hora_llegada = kwargs.pop('hora_llegada', None)
        
        super().__init__(*args, **kwargs)
        
        # ✅ FORZAR VALORES INICIALES DIRECTAMENTE EN LOS WIDGETS
        if self.hora_salida:
            self.fields['conductor1_hora_inicio'].widget.attrs['value'] = self.hora_salida
            self.fields['conductor2_hora_inicio'].widget.attrs['value'] = self.hora_salida
        
        if self.hora_llegada:
            self.fields['conductor1_hora_fin'].widget.attrs['value'] = self.hora_llegada
            self.fields['conductor2_hora_fin'].widget.attrs['value'] = self.hora_llegada


# ✅ FORMULARIO CORREGIDO: Usa los campos reales del modelo
class ManifiestoForm(forms.ModelForm):
    class Meta:
        model = Manifiesto
        # ⚠️ IMPORTANTE: Estos son los campos REALES del modelo actualizado
        fields = [
            'conductor_nombre', 'placa', 'hora_salida', 'brevete', 
            'destino_origen', 'destino_final'
        ]
        widgets = {
            'conductor_nombre': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-otiza-green'
            }),
            'placa': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-otiza-green'
            }),
            'hora_salida': forms.TimeInput(attrs={
                'type': 'time', 
                'class': 'w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-otiza-green'
            }),
            'brevete': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-otiza-green'
            }),
            'destino_origen': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-otiza-green'
            }),
            'destino_final': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-otiza-green'
            }),
        }


# Formset para pasajeros (16 pasajeros por defecto)
PasajeroFormSet = inlineformset_factory(
    Manifiesto, PasajeroManifiesto, 
    fields=['numero', 'nombre', 'dni', 'destino'],
    extra=16,
    can_delete=True,
    widgets={
        'numero': forms.NumberInput(attrs={'class': 'w-16 px-2 py-1 border border-slate-300 rounded text-center'}),
        'nombre': forms.TextInput(attrs={'class': 'w-full px-2 py-1 border border-slate-300 rounded'}),
        'dni': forms.TextInput(attrs={'class': 'w-full px-2 py-1 border border-slate-300 rounded'}),
        'destino': forms.TextInput(attrs={'class': 'w-full px-2 py-1 border border-slate-300 rounded'}),
    }
)