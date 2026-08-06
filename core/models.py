from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from datetime import datetime, timedelta
from django.conf import settings

import re

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
    
    # ✅ NUEVO CAMPO: Calle específica para la Hoja de Ruta
    calle = models.CharField(
        max_length=200, 
        blank=True, 
        null=True, 
        help_text="Calle específica para hoja de ruta (ej: Cal. La Cultura S/N)"
    )
    
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
    # CATEGORÍAS DE LICENCIA
    CATEGORIAS_LICENCIA = [
        ('', 'Seleccione categoría...'),
        ('A-I', 'A-I (Motocicletas)'),
        ('A-IIA', 'A-IIA (Automóviles particulares)'),
        ('A-IIB', 'A-IIB (Automóviles públicos - Taxis)'),
        ('A-IIIa', 'A-IIIa (Buses pequeños < 20 pasajeros)'),
        ('A-IIIb', 'A-IIIb (Buses medianos 20-50 pasajeros)'),
        ('A-IIIc', 'A-IIIc (Buses grandes > 50 pasajeros)'),
        ('B-I', 'B-I (Camionetas ligeras)'),
        ('B-IIa', 'B-IIa (Camiones medianos)'),
        ('B-IIb', 'B-IIb (Camiones pesados)'),
        ('B-IIIa', 'B-IIIa (Camiones articulados)'),
        ('B-IIIb', 'B-IIIb (Camiones especiales)'),
        ('C-I', 'C-I (Maquinaria liviana)'),
        ('C-IIa', 'C-IIa (Maquinaria pesada)'),
        ('C-IIb', 'C-IIb (Maquinaria especial)'),
    ]
    
    sede = models.ForeignKey(Sede, on_delete=models.PROTECT, related_name='usuarios')
    telefono = models.CharField(max_length=20, blank=True)
    es_cajero = models.BooleanField(default=True)
    activo = models.BooleanField(default=True)
    
    # Campos específicos para choferes
    licencia_conducir = models.CharField(max_length=20, blank=True, help_text="Número de licencia de conducir")
    categoria_licencia = models.CharField(max_length=10, choices=CATEGORIAS_LICENCIA, blank=True, help_text="Categoría de licencia")
    fecha_vencimiento_licencia = models.DateField(null=True, blank=True, help_text="Fecha de vencimiento de licencia")
    es_chofer = models.BooleanField(default=False, help_text="¿Es chofer activo?")
    
    # NUEVO: Rutas que el chofer puede manejar
    rutas_asignadas = models.ManyToManyField(
        'Ruta',  # Relación con el modelo Ruta
        blank=True,
        related_name='choferes', # Para poder hacer ruta.choferes.all()
        help_text='Rutas que este chofer está autorizado a conducir'
    )
    
    def __str__(self):
        return f"{self.username} - {self.sede}"
    
    class Meta:
        verbose_name = 'Usuario'
        verbose_name_plural = 'Usuarios'
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
    
    # CAMBIO: De sede_asignada a rutas_asignadas (ManyToMany)
    rutas_asignadas = models.ManyToManyField(
        'core.Ruta',
        blank=True,
        related_name='vehiculos',
        help_text='Rutas que puede realizar este vehículo'
    )
    
    chofer_asignado = models.ForeignKey(
        Usuario, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='vehiculos_asignados',
        limit_choices_to={'es_chofer': True},
        help_text='Chofer asignado a este vehículo'
    )
    activo = models.BooleanField(default=True)
    
    def __str__(self):
        return f"{self.placa} - {self.marca} {self.modelo}"
    
    def get_rutas_display(self):
        """Obtener rutas como texto"""
        return ", ".join([f"{r.origen}→{r.destino}" for r in self.rutas_asignadas.all()])
    
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
    
    # ✅ NUEVO CAMPO: Chofer asignado al viaje
    chofer_asignado = models.ForeignKey(
        Usuario,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='viajes_asignados',
        limit_choices_to={'es_chofer': True},
        help_text='Chofer asignado para este viaje'
    )
    
    fecha_salida = models.DateField()
    hora_salida = models.TimeField()
    fecha_llegada = models.DateField()
    hora_llegada = models.TimeField()
    estado = models.CharField(max_length=20, choices=ESTADO_VIAJE, default='programado')
    creado_en = models.DateTimeField(auto_now_add=True)

    # --- LÓGICA DE HORA DE LLEGADA (Tu código original) ---
    def obtener_hora_llegada(self):
        """Calcula la hora de llegada usando la misma lógica robusta del servicio"""
        
        if self.hora_salida and self.ruta and self.ruta.duracion_estimada:
            duracion_texto = str(self.ruta.duracion_estimada).lower().strip()
            horas = 0
            minutos = 0
            
            # Regex para horas
            match_horas = re.search(r'(\d+)\s*(?:hora|horas|h)\b', duracion_texto)
            if match_horas:
                horas = int(match_horas.group(1))
            
            # Regex para minutos
            match_minutos = re.search(r'(\d+)\s*(?:min|minutos|m)\b', duracion_texto)
            if match_minutos:
                minutos = int(match_minutos.group(1))
            
            # Calcular llegada
            salida_dt = datetime.combine(self.fecha_salida, self.hora_salida)
            llegada_dt = salida_dt + timedelta(hours=horas, minutes=minutos)
            
            return llegada_dt.strftime('%H:%M')
        
        # Fallback
        return self.hora_salida.strftime('%H:%M') if self.hora_salida else "--:--"
    
    # --- FIN DE LA LÓGICA ---

    def __str__(self):
        return f"{self.ruta} - {self.fecha_salida} {self.hora_salida}"
    
    class Meta:
        verbose_name = 'Viaje'
        verbose_name_plural = 'Viajes'
        ordering = ['fecha_salida', 'hora_salida']


# ==================== ASIENTOS DE VIAJE ====================

from django.db import models

class AsientoViaje(models.Model):
    ESTADO_ASIENTO = [
        ('disponible', 'Disponible'),
        ('reservado', 'Reservado'),
        ('vendido', 'Vendido'),
        ('bloqueado', 'Bloqueado'),
    ]
    
    viaje = models.ForeignKey('Viaje', on_delete=models.CASCADE, related_name='asientos')
    numero_asiento = models.CharField(max_length=10)  # Ej: "A4", "B12", "5"
    estado = models.CharField(max_length=20, choices=ESTADO_ASIENTO, default='disponible')
    precio = models.DecimalField(max_digits=8, decimal_places=2)
    vendido_en = models.DateTimeField(null=True, blank=True)
    
    # ==========================================
    # ✅ CAMPOS PARA RESERVA (Cajera o Chofer)
    # ==========================================
    nombre_reserva = models.CharField(max_length=100, blank=True, null=True, help_text="Nombre del pasajero")
    telefono_reserva = models.CharField(max_length=20, blank=True, null=True, help_text="Celular del pasajero")
    numero_documento_reserva = models.CharField(max_length=20, blank=True, null=True, help_text="DNI del pasajero")
    fecha_reserva = models.DateTimeField(blank=True, null=True, help_text="Fecha y hora de la reserva")
    nota_reserva = models.TextField(blank=True, null=True, help_text="Ej: 'Paga al llegar', 'Equipaje extra'")
    
    # ✅ CAMPOS ADICIONALES PARA FACTURACIÓN Y PAGO
    email_reserva = models.EmailField(blank=True, null=True, help_text="Correo electrónico del pasajero")
    ruc_reserva = models.CharField(max_length=20, blank=True, null=True, help_text="RUC del cliente")
    razon_social_reserva = models.CharField(max_length=150, blank=True, null=True, help_text="Razón social")
    metodo_pago_reserva = models.CharField(max_length=20, blank=True, null=True, help_text="Método de pago: efectivo, yape, plin")
    
    # ==========================================
    # ✅ CAMPOS ESPECÍFICOS PARA LÓGICA DE CHOFER
    # ==========================================
    reservado_por_chofer = models.BooleanField(default=False, help_text="True si la reserva la hizo un chofer en ruta")
    
    tipo_reserva_chofer = models.CharField(max_length=20, blank=True, null=True, choices=[
        ('con_cobro', 'Con Cobro (Chofer ya cobró)'),
        ('sin_cobro', 'Sin Cobro (Pendiente de pago en sede)')
    ], help_text="Estado del pago de la reserva del chofer")
    
    # ✅ CORRECCIÓN: Usamos ForeignKey para jalar el chofer desde la BD
    chofer_reserva = models.ForeignKey(
        'Usuario',  # Apunta a tu modelo de usuarios
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        limit_choices_to={'es_chofer': True},  # ⚠️ CLAVE: Solo muestra en la lista a los usuarios que son choferes
        related_name='asientos_reservados',
        help_text="Chofer real de la base de datos que hizo la reserva"
    )
    # ==========================================
    
    class Meta:
        verbose_name = 'Asiento de Viaje'
        verbose_name_plural = 'Asientos de Viaje'
        unique_together = ['viaje', 'numero_asiento']
        ordering = ['numero_asiento']
    
    def __str__(self):
        return f"Viaje {self.viaje.id} - Asiento {self.numero_asiento} ({self.get_estado_display()})"

    
# ==================== VENTAS ====================

from django.db import models

class Venta(models.Model):
    TIPO_DOCUMENTO = [
        ('boleta', 'Boleta'),
        ('factura', 'Factura'),
        ('ticket', 'Ticket'),
    ]
    
    METODO_PAGO = [
        ('efectivo', 'Efectivo'),
        ('yape', 'Yape'),
        ('plin', 'Plin'),
    ]
    
    # ===== DATOS DEL CLIENTE =====
    tipo_documento = models.CharField(max_length=20, choices=TIPO_DOCUMENTO, default='ticket')
    numero_documento = models.CharField(max_length=20, blank=True)  # DNI opcional
    nombre_cliente = models.CharField(max_length=100, blank=True)
    telefono_cliente = models.CharField(max_length=20, blank=True)
    email_cliente = models.EmailField(blank=True, null=True)
    
    # ✅ NUEVOS CAMPOS (para empresas/facturación)
    ruc_cliente = models.CharField(max_length=20, blank=True, null=True, help_text="RUC del cliente")
    razon_social = models.CharField(max_length=150, blank=True, null=True, help_text="Razón social (empresas)")
    
    # ===== DATOS DE LA TRANSACCIÓN =====
    asiento = models.ForeignKey('AsientoViaje', on_delete=models.PROTECT, related_name='ventas')
    viaje = models.ForeignKey('Viaje', on_delete=models.PROTECT, related_name='ventas')
    sede_venta = models.ForeignKey('Sede', on_delete=models.PROTECT, related_name='ventas')
    cajero = models.ForeignKey('Usuario', on_delete=models.PROTECT, related_name='ventas')
    
    monto_total = models.DecimalField(max_digits=10, decimal_places=2)
    fecha_venta = models.DateTimeField(auto_now_add=True)
    numero_ticket = models.CharField(max_length=50, unique=True)  # Generar automáticamente (TKT-...)
    
    # ✅ NUEVO CAMPO: Número correlativo del boleto (000001, 000002, etc.)
    numero_correlativo = models.PositiveIntegerField(
        null=True, 
        blank=True, 
        help_text="Número correlativo del boleto (000001, 000002, etc.)"
    )
    
    metodo_pago = models.CharField(max_length=20, choices=METODO_PAGO, default='efectivo')
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


class HorarioFijo(models.Model):
    """Define los horarios que se repiten diariamente"""
    ruta = models.ForeignKey('Ruta', on_delete=models.PROTECT)
    vehiculo = models.ForeignKey('Vehiculo', on_delete=models.PROTECT)
    hora_salida = models.TimeField(help_text="Ej: 08:00, 10:30")
    dias_semana = models.CharField(
        max_length=20,
        default="1,2,3,4,5,6,7",
        help_text="Días: 1=Lun, 2=Mar, ..., 7=Dom (separados por coma)"
    )
    activa = models.BooleanField(default=True)
    
    def __str__(self):
        return f"{self.ruta} - {self.hora_salida.strftime('%H:%M')}"
    
    class Meta:
        verbose_name = 'Horario Fijo'
        verbose_name_plural = 'Horarios Fijos'
        ordering = ['hora_salida']



class Notificacion(models.Model):
    TIPO_CHOICES = [
        ('fidelizacion', 'Fidelización'),
        ('operativa', 'Operativa'),
        ('comunicado', 'Comunicado'),
        ('venta', 'Venta'),
    ]
    CATEGORIA_CHOICES = [
        ('alerta', 'Alerta'),
        ('comunicado', 'Comunicado'),
        ('info', 'Información'),
    ]
    
    titulo = models.CharField(max_length=200)
    descripcion = models.TextField()
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    categoria = models.CharField(max_length=20, choices=CATEGORIA_CHOICES, default='alerta')
    leida = models.BooleanField(default=False)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    
    # Si es null, es para todas las sedes o todos los usuarios
    sede = models.ForeignKey('Sede', on_delete=models.SET_NULL, null=True, blank=True, related_name='notificaciones')
    usuario_destino = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='notificaciones')

    class Meta:
        ordering = ['-fecha_creacion']

    def __str__(self):
        return f"[{self.get_tipo_display()}] {self.titulo}"





class Manifiesto(models.Model):
    sede = models.ForeignKey('Sede', on_delete=models.CASCADE, related_name='manifiestos')
    viaje = models.ForeignKey('Viaje', on_delete=models.CASCADE, related_name='manifiesto', null=True, blank=True)
    numero_documento = models.CharField(max_length=50, unique=True)
    fecha_emision = models.DateField(default=timezone.now)
    fecha_viaje = models.DateField()
    conductor_nombre = models.CharField(max_length=100)
    placa = models.CharField(max_length=20)
    hora_salida = models.TimeField()
    brevete = models.CharField(max_length=50)
    destino_origen = models.CharField(max_length=100)
    destino_final = models.CharField(max_length=100)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    
    # ✅ NUEVO CAMPO: Número correlativo del manifiesto
    numero_correlativo = models.PositiveIntegerField(
        null=True, 
        blank=True, 
        help_text="Número correlativo del manifiesto (ej: 1, 2, 3...)"
    )

    class Meta:
        ordering = ['-fecha_creacion']

    def __str__(self):
        return f"Manifiesto {self.numero_documento}"


    

class PasajeroManifiesto(models.Model):
    manifiesto = models.ForeignKey(Manifiesto, on_delete=models.CASCADE, related_name='pasajeros')
    numero = models.IntegerField()
    nombre = models.CharField(max_length=100)
    dni = models.CharField(max_length=20)
    destino = models.CharField(max_length=100)

    class Meta:
        ordering = ['numero']

    def __str__(self):
        return f"{self.numero}. {self.nombre}"




class HojaRuta(models.Model):
    sede = models.ForeignKey('Sede', on_delete=models.CASCADE, related_name='hojas_ruta')
    viaje = models.ForeignKey('Viaje', on_delete=models.CASCADE, related_name='hoja_ruta')
    numero_documento = models.CharField(max_length=50, unique=True)
    fecha_emision = models.DateField(auto_now_add=True)
    
    # ✅ NUEVO CAMPO: Número correlativo (000001, 000002, etc.)
    numero_correlativo = models.PositiveIntegerField(
        null=True, 
        blank=True, 
        help_text="Número correlativo de la hoja de ruta"
    )
    
    # Datos del viaje (se copian para tener histórico)
    placa = models.CharField(max_length=20)
    fecha_inicio = models.DateField()
    fecha_llegada = models.DateField()
    hora_salida = models.TimeField()
    hora_llegada = models.TimeField()
    lugar_embarque = models.CharField(max_length=200)
    lugar_desembarque = models.CharField(max_length=200)
    
    # Conductores (hasta 3)
    conductor1_nombre = models.CharField(max_length=100, blank=True, null=True)
    conductor1_licencia = models.CharField(max_length=50, blank=True, null=True)
    conductor1_hora_inicio = models.CharField(max_length=10, blank=True, null=True)
    conductor1_hora_fin = models.CharField(max_length=10, blank=True, null=True)
    
    conductor2_nombre = models.CharField(max_length=100, blank=True, null=True)
    conductor2_licencia = models.CharField(max_length=50, blank=True, null=True)
    conductor2_hora_inicio = models.CharField(max_length=10, blank=True, null=True)
    conductor2_hora_fin = models.CharField(max_length=10, blank=True, null=True)
    
    conductor3_nombre = models.CharField(max_length=100, blank=True, null=True)
    conductor3_licencia = models.CharField(max_length=50, blank=True, null=True)
    
    # Incidentes (hasta 4 bloques)
    incidente1_nombres = models.CharField(max_length=100, blank=True, null=True)
    incidente1_constancia = models.TextField(blank=True, null=True)
    incidente1_firma = models.CharField(max_length=100, blank=True, null=True)
    incidente1_dni = models.CharField(max_length=20, blank=True, null=True)
    
    incidente2_nombres = models.CharField(max_length=100, blank=True, null=True)
    incidente2_constancia = models.TextField(blank=True, null=True)
    incidente2_firma = models.CharField(max_length=100, blank=True, null=True)
    incidente2_dni = models.CharField(max_length=20, blank=True, null=True)
    
    incidente3_nombres = models.CharField(max_length=100, blank=True, null=True)
    incidente3_constancia = models.TextField(blank=True, null=True)
    incidente3_firma = models.CharField(max_length=100, blank=True, null=True)
    incidente3_dni = models.CharField(max_length=20, blank=True, null=True)
    
    incidente4_nombres = models.CharField(max_length=100, blank=True, null=True)
    incidente4_constancia = models.TextField(blank=True, null=True)
    incidente4_firma = models.CharField(max_length=100, blank=True, null=True)
    incidente4_dni = models.CharField(max_length=20, blank=True, null=True)
    
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-fecha_creacion']

    def __str__(self):
        return f"Hoja de Ruta {self.numero_documento} - {self.viaje}"


from django.db import models
from django.utils import timezone

class ClienteFidelizacion(models.Model):
    dni = models.CharField(max_length=8, unique=True)
    nombre_completo = models.CharField(max_length=200)
    telefono = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    total_viajes = models.IntegerField(default=0)
    viajes_pendientes_premio = models.IntegerField(default=0)  # Viajes para completar 12
    ultimo_viaje_fecha = models.DateField(null=True, blank=True)
    fecha_registro = models.DateTimeField(auto_now_add=True)
    activo = models.BooleanField(default=True)
    
    def __str__(self):
        return f"{self.nombre_completo} - {self.dni} ({self.total_viajes} viajes)"
    
    class Meta:
        verbose_name = "Cliente Fidelización"
        verbose_name_plural = "Clientes Fidelización"


class PremioFidelizacion(models.Model):
    cliente = models.ForeignKey(ClienteFidelizacion, on_delete=models.CASCADE, related_name='premios')
    fecha_ganado = models.DateTimeField(auto_now_add=True)
    fecha_entregado = models.DateTimeField(null=True, blank=True)
    descripcion = models.CharField(max_length=200, default="Rasca y Gana - 12 viajes")
    entregado = models.BooleanField(default=False)
    
    def __str__(self):
        return f"{self.cliente.nombre_completo} - {'Entregado' if self.entregado else 'Pendiente'}"
    
    class Meta:
        verbose_name = "Premio Fidelización"
        verbose_name_plural = "Premios Fidelización"