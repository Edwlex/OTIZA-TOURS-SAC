from django import forms
from django.core.exceptions import ValidationError
from core.models import Usuario, Sede


class UsuarioForm(forms.ModelForm):
    """Formulario para crear/editar usuarios/cajeros - SIN gestión de contraseña"""
    
    class Meta:
        model = Usuario
        fields = [
            'username', 'email', 'first_name', 'last_name',
            'telefono', 'sede', 'es_cajero', 'activo'
        ]
        widgets = {
            'username': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500',
                'placeholder': 'cajero_trujillo',
                'maxlength': '150'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500',
                'placeholder': 'cajero@otizatours.com'
            }),
            'first_name': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500',
                'placeholder': 'Ana'
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500',
                'placeholder': 'García'
            }),
            'telefono': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500',
                'placeholder': '987654321'
            }),
            'sede': forms.Select(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500'
            }),
            'es_cajero': forms.CheckboxInput(attrs={
                'class': 'w-4 h-4 text-indigo-600 border-gray-300 rounded focus:ring-indigo-500'
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
        """Validar username"""
        username = self.cleaned_data.get('username', '')
        
        if len(username) < 4:
            raise ValidationError("El nombre de usuario debe tener al menos 4 caracteres")
        
        # Verificar que no exista (solo al crear)
        if not self.instance.pk:
            if Usuario.objects.filter(username=username).exists():
                raise ValidationError("Este nombre de usuario ya está registrado")
        
        return username
    
    def clean_email(self):
        """Validar email"""
        email = self.cleaned_data.get('email', '')
        
        if not email:
            raise ValidationError("El email es obligatorio")
        
        # Verificar que no exista (solo al crear)
        if not self.instance.pk:
            if Usuario.objects.filter(email=email).exists():
                raise ValidationError("Este email ya está registrado")
        
        return email
    
    def clean_telefono(self):
        """Validar teléfono"""
        telefono = self.cleaned_data.get('telefono', '')
        
        if telefono and (not telefono.isdigit() or len(telefono) != 9):
            raise ValidationError("El teléfono debe tener 9 dígitos numéricos")
        
        return telefono
    # ✅ ELIMINADO: clean_password ya no es necesario