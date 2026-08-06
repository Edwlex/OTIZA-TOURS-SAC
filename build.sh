#!/usr/bin/env bash
# exit on error
set -o errexit

# Instalar dependencias
pip install -r requirements.txt

# Recopilar archivos estáticos
python manage.py collectstatic --no-input

# Ejecutar migraciones
python manage.py migrate

# Crear/actualizar datos iniciales (sedes, usuarios admin, cajeros, chofer)
python manage.py crear_datos_iniciales

echo "✅ Build completado exitosamente"