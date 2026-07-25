from django import forms
from django.core.exceptions import ValidationError
from core.models import Usuario, Sede
from datetime import date


class ChoferForm(forms.ModelForm):
    """Formulario profesional para crear/editar choferes"""
    
    class Meta:
        model = Usuario
        fields = [
            'username', 'email', 'first_name', 'last_name',
            'telefono', 'licencia_conducir', 'categoria_licencia',
            'fecha_vencimiento_licencia', 'sede', 'activo'
        ]
        widgets = {
            'username': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500',
                'placeholder': 'DNI del chofer (8 dígitos)',
                'maxlength': '8'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500',
                'placeholder': 'chofer@otizatours.com'
            }),
            'first_name': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500',
                'placeholder': 'Juan Carlos'
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500',
                'placeholder': 'Pérez García'
            }),
            'telefono': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500',
                'placeholder': '987654321',
                'maxlength': '9'
            }),
            'licencia_conducir': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500',
                'placeholder': 'A1-234567'
            }),
            'categoria_licencia': forms.Select(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500'
            }),
            'fecha_vencimiento_licencia': forms.DateInput(attrs={
                'type': 'date',
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500',
                'min': date.today().isoformat()
            }),
            'sede': forms.Select(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500'
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