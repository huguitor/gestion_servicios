# gestion/sistema_general/settings.py
import sys
import os
from pathlib import Path
from corsheaders.defaults import default_headers

# ========== CONFIGURACIÓN PARA .EXE Y DESARROLLO ==========
if getattr(sys, 'frozen', False):
    # MODO .EXE (PyInstaller)
    BASE_DIR = Path(sys._MEIPASS)  # Carpeta temporal del .exe
    DATA_DIR = Path(sys.executable).parent  # Carpeta donde está el .exe
    print("⚙️  MODO .EXE DETECTADO")  # ✅ Este print SÍ va en el .exe
else:
    # MODO DESARROLLO (runserver)
    BASE_DIR = Path(__file__).resolve().parent.parent  # Tu proyecto
    DATA_DIR = BASE_DIR  # Misma carpeta que el proyecto

# Crear carpeta 'data' para persistencia (base de datos y media)
DATA_DIR_ABS = DATA_DIR / 'data'
DATA_DIR_ABS.mkdir(exist_ok=True)
# ==========================================================

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'django-insecure-@iq9o=e3cn)6gbcscd59wht+dxm05(-c187@t^lekob$&+36ii'

# SECURITY WARNING: don't run with debug turned on in production!
# Si es ejecutable (frozen) -> DEBUG = False
# Si es desarrollo (runserver) -> DEBUG = True
DEBUG = not getattr(sys, 'frozen', False)

ALLOWED_HOSTS = ['localhost', '127.0.0.1', '0.0.0.0']   

# CORS settings
CORS_ALLOW_ALL_ORIGINS = True  # permite cualquier origen (ok para desarrollo)

# Extender los headers permitidos para incluir 'range', necesario para React Admin
CORS_ALLOW_HEADERS = list(default_headers) + [
    "Range",
]

# Exponer Content-Range para que React Admin pueda leer la paginación
CORS_EXPOSE_HEADERS = [
    "Content-Range",
]

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'corsheaders',
    'configuracion',
    'clientes',
    'proveedores',
    'productos',
    'categorias',
    'marcas',
    'presupuestos',
    'impuestos',
    'comprobantes',
    'django_filters',
    'rest_framework',
    'rest_framework.authtoken',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'sistema_general.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
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

WSGI_APPLICATION = 'sistema_general.wsgi.application'

# ========== BASE DE DATOS PERSISTENTE ==========
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': str(DATA_DIR_ABS / 'database.sqlite3'),  # data/database.sqlite3
    }
}
# ===============================================

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
LANGUAGE_CODE = 'es-AR'
TIME_ZONE = 'America/Argentina/Buenos_Aires'
USE_I18N = True
USE_TZ = True

# ========== ARCHIVOS ESTÁTICOS Y MEDIA ==========
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Media files (archivos subidos por usuarios) - PERSISTENTES
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(DATA_DIR_ABS, 'media')
# ================================================

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Configuración de Django REST Framework
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.TokenAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
    ],
}

# Configuración generosa para archivos adjuntos
MAX_TAMAÑO_ADJUNTO = 500 * 1024 * 1024  # 500 MB por archivo
MAX_ADJUNTOS_POR_PRESUPUESTO = 100  # Máximo de archivos por presupuesto
TIEMPO_SUBIDA_TIMEOUT = 300  # 5 minutos para subidas grandes

# Extensiones permitidas (lista amplia)
EXTENSIONES_PERMITIDAS = {
    'plano': ['pdf', 'dwg', 'dxf', 'skp', 'rvt', 'ifc'],
    'foto': ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp', 'heic', 'tiff'],
    'diagrama': ['pdf', 'png', 'jpg', 'jpeg', 'vsd', 'vsdx'],
    'contrato': ['pdf', 'doc', 'docx', 'xls', 'xlsx'],
    'comunicacion': ['pdf', 'eml', 'msg', 'txt'],
    'otro': ['zip', 'rar', '7z', 'csv', 'json', 'xml']
}

# Configuración Django para archivos grandes
DATA_UPLOAD_MAX_MEMORY_SIZE = 524288000  # 500 MB
FILE_UPLOAD_MAX_MEMORY_SIZE = 524288000  # 500 MB

# ========== DEBUG INFO SOLO CUANDO SE EJECUTA ==========
# Esto se ejecuta cuando Django inicia, NO al compilar
if __name__ == "__main__" or getattr(sys, 'frozen', False):
    print(f"🔧 MEDIA_ROOT configurado en: {MEDIA_ROOT}")
    print(f"🔧 DATA_DIR_ABS: {DATA_DIR_ABS}")