"""
Django settings for otiza_backend project.
"""

from pathlib import Path
import os
import dj_database_url  # ✅ AGREGADO: Para leer la URL de la BD de Railway

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# ==================== SEGURIDAD Y ENTORNO ====================
# ✅ 1. SECRET KEY: Usa la de Railway, si no existe, usa la local de respaldo
SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-1mf-_95pn8&**t!_(@s2h1!s=f^q9fbx@roh!dc2^*d6qn@ch!')

# ✅ 2. DEBUG: True en local, False en Railway (se controla con variable de entorno)
DEBUG = os.environ.get('DEBUG', 'True') == 'True'

# ✅ 3. ALLOWED HOSTS: Se llena desde Railway, en local permite localhost
ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', '127.0.0.1,localhost').split(',')

# ==================== APLICACIONES ====================
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'core',
]

# ==================== MIDDLEWARE ====================
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware', # ✅ AGREGADO: Para servir archivos estáticos en prod
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'otiza_backend.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'otiza_backend.wsgi.application'

# ==================== BASE DE DATOS ====================
# ✅ 4. DATABASE: Usa la URL de Railway. Si no existe, usa tu configuración local de respaldo.
# ✅ SSL se exige solo cuando DEBUG es False (es decir, en producción)
DATABASES = {
    'default': dj_database_url.config(
        default=os.environ.get('DATABASE_URL', 'postgresql://otiza_user:otiza_pass_2026@localhost:5432/otiza_db'),
        conn_max_age=600,
        ssl_require=os.environ.get('DEBUG', 'True') != 'True' 
    )
}

# ==================== VALIDACIÓN DE CONTRASEÑAS ====================
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ==================== INTERNACIONALIZACIÓN ====================
LANGUAGE_CODE = 'es-pe'
TIME_ZONE = 'America/Lima'
DEFAULT_TIME_ZONE = 'America/Lima'
USE_I18N = True
USE_TZ = True

# ==================== ARCHIVOS ESTÁTICOS Y MEDIA ====================
STATIC_URL = '/static/'
STATICFILES_DIRS = [
    BASE_DIR / 'core' / 'static',
]
STATIC_ROOT = BASE_DIR / 'staticfiles'

# ✅ Optimización de WhiteNoise para producción (compresión y caché)
STORAGES = {
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# ==================== CONFIGURACIÓN OTIZA TOURS ====================
AUTH_USER_MODEL = 'core.Usuario'

LOGIN_URL = 'core:login'
LOGIN_REDIRECT_URL = 'core:dashboard' 
LOGOUT_REDIRECT_URL = 'core:login'

# ==================== LOGGING CONFIGURATION ====================
LOGS_DIR = os.path.join(BASE_DIR, 'logs')
if not os.path.exists(LOGS_DIR):
    os.makedirs(LOGS_DIR)

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
        'detailed': {
            'format': '[{levelname}] {asctime} | {module}.{funcName} | {message}',
            'style': '{',
            'datefmt': '%Y-%m-%d %H:%M:%S',
        },
    },
    'handlers': {
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'detailed',
        },
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': os.path.join(LOGS_DIR, 'otiza.log'),
            'formatter': 'detailed',
        },
        'errors': {
            'level': 'ERROR',
            'class': 'logging.FileHandler',
            'filename': os.path.join(LOGS_DIR, 'otiza_errors.log'),
            'formatter': 'detailed',
        },
    },
    'root': {
        'handlers': ['console', 'file', 'errors'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
        'core': {
            'handlers': ['console', 'file', 'errors'],
            'level': 'DEBUG',
            'propagate': False,
        },
    },
}

# ==================== SESSION CONFIG ====================
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_COOKIE_AGE = 1800  # 30 minutos
SESSION_SAVE_EVERY_REQUEST = True 