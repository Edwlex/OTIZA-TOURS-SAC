
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum, Q
import json

# Configuración de sedes
CONFIG_SEDES = {
    'trujillo': {
        'nombre': 'Trujillo',
        'rutas': [
            {'valor': 'trujillo-julcan', 'etiqueta': 'Trujillo → Julcán'},
            {'valor': 'trujillo-mache', 'etiqueta': 'Trujillo → Mache'}
        ]
    },
    'julcan': {
        'nombre': 'Julcán',
        'rutas': [
            {'valor': 'julcan-trujillo', 'etiqueta': 'Julcán → Trujillo'},
            {'valor': 'julcan-mache', 'etiqueta': 'Julcán → Mache'}
        ]
    },
    'mache': {
        'nombre': 'Mache',
        'rutas': [
            {'valor': 'mache-trujillo', 'etiqueta': 'Mache → Trujillo'},
            {'valor': 'mache-julcan', 'etiqueta': 'Mache → Julcán'}
        ]
    },
    'central': {
        'nombre': 'Sede Central',
        'rutas': [
            {'valor': 'todas', 'etiqueta': 'Todas las Rutas'},
            {'valor': 'trujillo-julcan', 'etiqueta': 'Trujillo ↔ Julcán'},
            {'valor': 'trujillo-mache', 'etiqueta': 'Trujillo ↔ Mache'},
            {'valor': 'julcan-mache', 'etiqueta': 'Julcán ↔ Mache'}
        ]
    }
}

def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        sede = request.POST.get('sede')
        
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            # Guardar sede en sesión
            request.session['sede_usuario'] = sede
            return redirect('dashboard')
        else:
            messages.error(request, 'Usuario o contraseña incorrectos')
    
    return render(request, 'login.html')

@login_required
def dashboard_view(request):
    # Obtener sede del usuario
    sede = request.session.get('sede_usuario', 'trujillo')
    config = CONFIG_SEDES.get(sede, CONFIG_SEDES['trujillo'])
    
    # Datos de ejemplo (REEMPLAZAR con consultas a BD)
    contexto = {
        'sede_usuario': sede,
        'es_cajero': sede != 'central',
        'titulo_dashboard': f"Reporte de Ventas - {config['nombre']}",
        'titulo_grafico': f"Ventas por Ruta - {config['nombre']}",
        'titulo_tabla': f"Viajes Recientes - {config['nombre']}",
        'rutas_disponibles': config['rutas'],
        'rutas_json': json.dumps(config['rutas']),
        'ingresos': 15450.00,
        'egresos': 4230.00,
        'ganancia_neta': 11220.00,
        'viajes_completados': 5,  # Para estrellas
        'viajes_faltantes': 7,
        'progreso_estrellas': 42,
        'viajes': [
            {'fecha': '2026-07-14', 'ruta_origen': 'Trujillo', 'ruta_destino': 'Julcán', 
             'vehiculo': {'placa': 'ABC-123', 'capacidad': 20}, 'asientos_ocupados': 18, 
             'ingreso': 450.00, 'estado': 'Completado'},
            {'fecha': '2026-07-14', 'ruta_origen': 'Trujillo', 'ruta_destino': 'Mache', 
             'vehiculo': {'placa': 'XYZ-789', 'capacidad': 20}, 'asientos_ocupados': 15, 
             'ingreso': 375.00, 'estado': 'En Ruta'},
        ]
    }
    
    return render(request, 'dashboard.html', contexto)

@login_required
def logout_view(request):
    logout(request)
    return redirect('login')