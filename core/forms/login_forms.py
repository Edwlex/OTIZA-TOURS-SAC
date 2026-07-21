from django import forms
from django.core.exceptions import ValidationError
from core.models import Sede

class LoginForm(forms.Form):
    """Formulario de login con validación de sede"""
    
    username = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'w-full pl-10 pr-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:border-otiza-green',
            'placeholder': 'Ingresa tu usuario'
        })
    )
    
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'w-full pl-10 pr-10 py-3 border border-gray-300 rounded-lg focus:outline-none focus:border-otiza-green',
            'placeholder': '••••••••'
        })
    )
    
    sede = forms.ChoiceField(
        choices=[],  # Se llenará dinámicamente
        widget=forms.Select(attrs={
            'class': 'w-full pl-10 pr-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:border-otiza-green'
        })
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Cargar sedes activas dinámicamente
        sedes_activas = Sede.objects.filter(activa=True).values_list('nombre', 'nombre')
        self.fields['sede'].choices = [
            ('Sede Trujillo', '📍 Agencia Trujillo'),
            ('Sede Julcán', ' Agencia Julcán'),
            ('Sede Mache', '📍 Agencia Mache'),
            ('Oficina Central', '🏢 Sede Central (Dueño)'),  
        ]
    
    def clean(self):
        cleaned_data = super().clean()
        username = cleaned_data.get('username')
        password = cleaned_data.get('password')
        sede_nombre = cleaned_data.get('sede')
        
        if username and password and sede_nombre:
            from core.services.auth_service import AuthService
            try:
                user = AuthService.authenticate_user(username, password, sede_nombre)
                if user is None:
                    raise ValidationError("Usuario o contraseña incorrectos")
                self.user = user
            except ValidationError as e:
                raise ValidationError(str(e))
        
        return cleaned_data
    
    def get_user(self):
        return getattr(self, 'user', None)