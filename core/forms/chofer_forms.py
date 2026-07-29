from django import forms
from django.core.exceptions import ValidationError
from core.models import Usuario, Sede
from datetime import date


class ChoferForm(forms.ModelForm):
    class Meta:
        model = Usuario
        fields = [
            'username', 'email', 'first_name', 'last_name', 'telefono',
            'licencia_conducir', 'categoria_licencia', 'fecha_vencimiento_licencia',
            'rutas_asignadas', 'activo'
        ]
        widgets = {
            'username': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500',
                'placeholder': 'DNI del chofer'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500',
                'placeholder': 'email@ejemplo.com'
            }),
            'first_name': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500',
                'placeholder': 'Nombre'
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500',
                'placeholder': 'Apellido'
            }),
            'telefono': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500',
                'placeholder': '999888777'
            }),
            'licencia_conducir': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500',
                'placeholder': 'D-12345678'
            }),
            'categoria_licencia': forms.Select(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500'
            }),
            'fecha_vencimiento_licencia': forms.DateInput(attrs={
                'type': 'date',
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500'
            }),
            'rutas_asignadas': forms.SelectMultiple(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500',
                'size': '5'  # Mostrar 5 opciones visibles
            }),
            'activo': forms.CheckboxInput(attrs={
                'class': 'rounded border-gray-300 text-indigo-600 focus:ring-indigo-500'
            }),
        }
        labels = {
            'rutas_asignadas': 'Rutas Asignadas',
        }
        help_texts = {
            'rutas_asignadas': 'Selecciona las rutas que este chofer puede manejar',
        }
    
    def __init__(self, *args, **kwargs):
        self.usuario = kwargs.pop('usuario', None)
        super().__init__(*args, **kwargs)
        
        # Si hay un usuario no-admin, limitar sedes
        if self.usuario and not self.usuario.is_superuser:
            self.fields['sede'].queryset = Sede.objects.filter(
                nombre=self.usuario.sede.nombre
            )
    
    def clean_username(self):
        """Validar DNI (username)"""
        username = self.cleaned_data.get('username', '')
        
        if not username.isdigit() or len(username) != 8:
            raise ValidationError("El DNI debe tener exactamente 8 dígitos numéricos")
        
        # Verificar que no exista (solo al crear)
        if not self.instance.pk:
            if Usuario.objects.filter(username=username).exists():
                raise ValidationError("Este DNI ya está registrado en el sistema")
        
        return username
    
    def clean_licencia_conducir(self):
        """Validar licencia"""
        licencia = self.cleaned_data.get('licencia_conducir', '')
        
        if not licencia or len(licencia) < 5:
            raise ValidationError("El número de licencia debe tener al menos 5 caracteres")
        
        return licencia.upper()
    
    def clean_telefono(self):
        """Validar teléfono"""
        telefono = self.cleaned_data.get('telefono', '')
        
        if telefono and (not telefono.isdigit() or len(telefono) != 9):
            raise ValidationError("El teléfono debe tener 9 dígitos numéricos")
        
        return telefono
    
    def clean_fecha_vencimiento_licencia(self):
        """Validar fecha de vencimiento"""
        fecha = self.cleaned_data.get('fecha_vencimiento_licencia')
        
        if fecha and fecha < date.today():
            raise ValidationError("La fecha de vencimiento no puede ser anterior a hoy")
        
        return fecha