# sistema_general/settings.py
from pathlib import Path
from corsheaders.defaults import default_headers  # <-- import para poder extender headers

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'django-insecure-@iq9o=e3cn)6gbcscd59wht+dxm05(-c187@t^lekob$&+36ii'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = ['*']

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
    'corsheaders',  # <-- importante: debe estar antes de CommonMiddleware
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
    'rest_framework.authtoken',  # Para autenticación por token
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',  # <-- debe ir primero para CORS
    'django.middleware.security.SecurityMiddleware',
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
# https://docs.djangoproject.com/en/5.2/ref/settings/#databases
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# Password validation
# https://docs.djangoproject.com/en/5.2/ref/settings/#auth-password-validators
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
# https://docs.djangoproject.com/en/5.2/topics/i18n/
LANGUAGE_CODE = 'es-AR'
TIME_ZONE = 'America/Argentina/Buenos_Aires'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.2/howto/static-files/
STATIC_URL = 'static/'
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Default primary key field type
# https://docs.djangoproject.com/en/5.2/ref/settings/#default-auto-field
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