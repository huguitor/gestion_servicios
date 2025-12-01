# sistema_general/settings.py
import sys
import os
from pathlib import Path
from corsheaders.defaults import default_headers

# Build paths inside the project like this: BASE_DIR / 'subdir'.
if getattr(sys, 'frozen', False):
    # Si estamos en el ejecutable (PyInstaller)
    # BASE_DIR: Carpeta temporal donde se descomprime el código y estáticos (_MEIxxxx)
    BASE_DIR = Path(sys._MEIPASS)
    # DATA_DIR: Carpeta donde está el .exe (para guardar DB y media persistentes)
    DATA_DIR = Path(sys.executable).parent
else:
    # Modo desarrollo normal
    BASE_DIR = Path(__file__).resolve().parent.parent
    DATA_DIR = BASE_DIR

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

# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': DATA_DIR / 'db.sqlite3',
    }
}

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

# Static files (CSS, JavaScript, Images)
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_URL = '/media/'
MEDIA_ROOT = DATA_DIR / 'media'

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