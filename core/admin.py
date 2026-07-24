from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Sede, Usuario, Vehiculo, Ruta, Viaje, AsientoViaje, Venta, Incidencia

# ==================== SEDE ====================
@admin.register(Sede)
class SedeAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'direccion', 'telefono', 'activa', 'creada_en')
    list_filter = ('activa',)
    search_fields = ('nombre', 'direccion')

# ==================== USUARIO ====================
@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    list_display = ('username', 'email', 'sede', 'es_cajero', 'activo', 'is_staff')
    list_filter = ('sede', 'es_cajero', 'activo', 'is_staff')
    search_fields = ('username', 'email', 'first_name', 'last_name')
    fieldsets = UserAdmin.fieldsets + (
        ('Información Otiza', {'fields': ('sede', 'telefono', 'es_cajero', 'activo')}),
    )

# ==================== VEHÍCULO ====================
@admin.register(Vehiculo)
class VehiculoAdmin(admin.ModelAdmin):
    list_display = ('placa', 'marca', 'modelo', 'año', 'capacidad_asientos', 'sede_asignada', 'activo')
    list_filter = ('sede_asignada', 'activo', 'marca')
    search_fields = ('placa', 'marca', 'modelo')

# ==================== RUTA ====================
@admin.register(Ruta)
class RutaAdmin(admin.ModelAdmin):
    list_display = ('origen', 'destino', 'distancia_km', 'duracion_estimada', 'precio_base', 'activa')
    list_filter = ('origen', 'destino', 'activa')
    search_fields = ('origen', 'destino')

# ==================== VIAJE ====================
@admin.register(Viaje)
class ViajeAdmin(admin.ModelAdmin):
    list_display = ('ruta', 'vehiculo', 'sede_salida', 'fecha_salida', 'hora_salida', 'estado')
    list_filter = ('estado', 'sede_salida', 'fecha_salida')
    search_fields = ('ruta__origen', 'ruta__destino', 'vehiculo__placa')
    date_hierarchy = 'fecha_salida'

# ==================== ASIENTO VIAJE ====================
@admin.register(AsientoViaje)
class AsientoViajeAdmin(admin.ModelAdmin):
    list_display = ('viaje', 'numero_asiento', 'estado', 'precio', 'vendido_en')
    list_filter = ('estado', 'viaje')
    search_fields = ('numero_asiento',)

# ==================== VENTA ====================
@admin.register(Venta)
class VentaAdmin(admin.ModelAdmin):
    list_display = ('numero_ticket', 'nombre_cliente', 'viaje', 'asiento', 'monto_total', 'fecha_venta', 'sede_venta', 'cajero')
    list_filter = ('sede_venta', 'fecha_venta', 'tipo_documento')
    search_fields = ('numero_ticket', 'nombre_cliente', 'numero_documento')
    date_hierarchy = 'fecha_venta'

# ==================== INCIDENCIA ====================
@admin.register(Incidencia)
class IncidenciaAdmin(admin.ModelAdmin):
    list_display = ('tipo', 'sede_reporte', 'reportado_por', 'estado', 'fecha_reporte')
    list_filter = ('tipo', 'estado', 'sede_reporte')
    search_fields = ('descripcion', 'reportado_por__username')
    date_hierarchy = 'fecha_reporte'