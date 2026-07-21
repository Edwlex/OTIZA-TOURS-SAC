from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone

# ==================== SEDES ====================
class Sede(models.Model):
    NOMBRE_SEDES = [
        ('Sede Trujillo', 'Trujillo'),
        ('Sede Julcán', 'Julcán'),
        ('Sede Mache', 'Mache'),
        ('Oficina Central', 'Sede Central (Dueño)'),
    ]
    
    nombre = models.CharField(max_length=50, choices=NOMBRE_SEDES, unique=True)
    direccion = models.CharField(max_length=200, blank=True)
    telefono = models.CharField(max_length=20, blank=True)
    activa = models.BooleanField(default=True)
    creada_en = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.get_nombre_display()
    
    class Meta:
        verbose_name = 'Sede'
        verbose_name_plural = 'Sedes'


# ==================== USUARIOS ====================
class Usuario(AbstractUser):
    sede = models.ForeignKey(Sede, on_delete=models.PROTECT, related_name='usuarios')
    telefono = models.CharField(max_length=20, blank=True)
    es_cajero = models.BooleanField(default=True)
    activo = models.BooleanField(default=True)
    
    def __str__(self):
        return f"{self.username} - {self.sede}"
    
    class Meta:
        verbose_name = 'Usuario'
        verbose_name_plural = 'Usuarios'
        # Evita que se creen usuarios duplicados
        constraints = [
            models.UniqueConstraint(fields=['username', 'sede'], name='unique_usuario_sede')
        ]


# ==================== VEHÍCULOS ====================
class Vehiculo(models.Model):
    placa = models.CharField(max_length=20, unique=True)
    marca = models.CharField(max_length=50)
    modelo = models.CharField(max_length=50)
    año = models.IntegerField()
    capacidad_asientos = models.IntegerField(default=20)
    sede_asignada = models.ForeignKey(Sede, on_delete=models.PROTECT, related_name='vehiculos')
    activo = models.BooleanField(default=True)
    
    def __str__(self):
        return f"{self.placa} - {self.marca} {self.modelo}"
    
    class Meta:
        verbose_name = 'Vehículo'
        verbose_name_plural = 'Vehículos'


# ==================== RUTAS ====================
class Ruta(models.Model):
    origen = models.CharField(max_length=50)  # Ej: Trujillo
    destino = models.CharField(max_length=50)  # Ej: Julcán
    distancia_km = models.DecimalField(max_digits=5, decimal_places=2)
    duracion_estimada = models.CharField(max_length=50)  # Ej: "2 horas"
    precio_base = models.DecimalField(max_digits=8, decimal_places=2)
    activa = models.BooleanField(default=True)
    
    def __str__(self):
        return f"{self.origen} → {self.destino}"
    
    class Meta:
        verbose_name = 'Ruta'
        verbose_name_plural = 'Rutas'
        unique_together = ['origen', 'destino']


# ==================== VIAJES ====================
class Viaje(models.Model):
    ESTADO_VIAJE = [
        ('programado', 'Programado'),
        ('en_curso', 'En Curso'),
        ('finalizado', 'Finalizado'),
        ('cancelado', 'Cancelado'),
    ]
    
    ruta = models.ForeignKey(Ruta, on_delete=models.PROTECT, related_name='viajes')
    vehiculo = models.ForeignKey(Vehiculo, on_delete=models.PROTECT, related_name='viajes')
    sede_salida = models.ForeignKey(Sede, on_delete=models.PROTECT, related_name='viajes_salida')
    fecha_salida = models.DateField()
    hora_salida = models.TimeField()
    fecha_llegada = models.DateField()
    hora_llegada = models.TimeField()
    estado = models.CharField(max_length=20, choices=ESTADO_VIAJE, default='programado')
    creado_en = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.ruta} - {self.fecha_salida} {self.hora_salida}"
    
    class Meta:
        verbose_name = 'Viaje'
        verbose_name_plural = 'Viajes'
        ordering = ['fecha_salida', 'hora_salida']


# ==================== ASIENTOS DE VIAJE ====================
class AsientoViaje(models.Model):
    ESTADO_ASIENTO = [
        ('disponible', 'Disponible'),
        ('reservado', 'Reservado'),
        ('vendido', 'Vendido'),
        ('bloqueado', 'Bloqueado'),
    ]
    
    viaje = models.ForeignKey(Viaje, on_delete=models.CASCADE, related_name='asientos')
    numero_asiento = models.CharField(max_length=10)  # Ej: "A4", "B12"
    estado = models.CharField(max_length=20, choices=ESTADO_ASIENTO, default='disponible')
    precio = models.DecimalField(max_digits=8, decimal_places=2)
    vendido_en = models.DateTimeField(null=True, blank=True)
    
    # 🔒 CONSTRAINT ANTI-CONCURRENCIA: Un asiento no puede venderse 2 veces en el mismo viaje
    class Meta:
        verbose_name = 'Asiento de Viaje'
        verbose_name_plural = 'Asientos de Viaje'
        unique_together = ['viaje', 'numero_asiento']
        constraints = [
            models.UniqueConstraint(
                fields=['viaje', 'numero_asiento', 'estado'],
                condition=models.Q(estado='vendido'),
                name='unique_asiento_vendido_por_viaje'
            )
        ]
    
    def __str__(self):
        return f"{self.viaje} - Asiento {self.numero_asiento} ({self.estado})"


# ==================== VENTAS ====================
class Venta(models.Model):
    TIPO_DOCUMENTO = [
        ('boleta', 'Boleta'),
        ('factura', 'Factura'),
        ('ticket', 'Ticket'),
    ]
    
    # Datos del cliente
    tipo_documento = models.CharField(max_length=20, choices=TIPO_DOCUMENTO, default='ticket')
    numero_documento = models.CharField(max_length=20, blank=True)  # DNI opcional
    nombre_cliente = models.CharField(max_length=100, blank=True)
    telefono_cliente = models.CharField(max_length=20, blank=True)
    
    # Datos de la transacción
    asiento = models.ForeignKey(AsientoViaje, on_delete=models.PROTECT, related_name='ventas')
    viaje = models.ForeignKey(Viaje, on_delete=models.PROTECT, related_name='ventas')
    sede_venta = models.ForeignKey(Sede, on_delete=models.PROTECT, related_name='ventas')
    cajero = models.ForeignKey(Usuario, on_delete=models.PROTECT, related_name='ventas')
    
    monto_total = models.DecimalField(max_digits=10, decimal_places=2)
    fecha_venta = models.DateTimeField(auto_now_add=True)
    numero_ticket = models.CharField(max_length=50, unique=True)  # Generar automáticamente
    observaciones = models.TextField(blank=True)
    
    def __str__(self):
        return f"Venta {self.numero_ticket} - {self.asiento}"
    
    class Meta:
        verbose_name = 'Venta'
        verbose_name_plural = 'Ventas'
        ordering = ['-fecha_venta']


# ==================== INCIDENCIAS/REPORTES ====================
class Incidencia(models.Model):
    TIPO_INCIDENCIA = [
        ('reclamo', 'Reclamo'),
        ('sugerencia', 'Sugerencia'),
        ('incidente', 'Incidente'),
        ('otro', 'Otro'),
    ]
    
    ESTADO_INCIDENCIA = [
        ('pendiente', 'Pendiente'),
        ('atendida', 'Atendida'),
        ('resuelta', 'Resuelta'),
    ]
    
    tipo = models.CharField(max_length=20, choices=TIPO_INCIDENCIA)
    descripcion = models.TextField()
    sede_reporte = models.ForeignKey(Sede, on_delete=models.PROTECT, related_name='incidencias')
    reportado_por = models.ForeignKey(Usuario, on_delete=models.PROTECT, related_name='incidencias')
    estado = models.CharField(max_length=20, choices=ESTADO_INCIDENCIA, default='pendiente')
    fecha_reporte = models.DateTimeField(auto_now_add=True)
    fecha_resolucion = models.DateTimeField(null=True, blank=True)
    solucion = models.TextField(blank=True)
    
    def __str__(self):
        return f"{self.get_tipo_display()} - {self.sede_reporte} ({self.estado})"
    
    class Meta:
        verbose_name = 'Incidencia'
        verbose_name_plural = 'Incidencias'
        ordering = ['-fecha_reporte']