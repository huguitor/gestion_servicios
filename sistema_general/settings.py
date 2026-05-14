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
# SECRET_KEY: en servidor se toma de DJANGO_SECRET_KEY; en distribución .exe
# se autogenera y persiste en data/secret_key.txt (data/ está en .gitignore).
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY')
if not SECRET_KEY:
    key_file = DATA_DIR_ABS / 'secret_key.txt'
    if key_file.exists():
        SECRET_KEY = key_file.read_text().strip()
    else:
        from django.core.management.utils import get_random_secret_key
        SECRET_KEY = get_random_secret_key()
        key_file.write_text(SECRET_KEY)
        try:
            key_file.chmod(0o600)
        except OSError:
            pass  # Windows ignora chmod POSIX

# DEBUG: False por defecto (servidor, gunicorn, .exe). Se activa explícitamente
# con DJANGO_DEBUG=1, o automáticamente al usar `manage.py runserver`.
_debug_env = os.environ.get('DJANGO_DEBUG')
if _debug_env is not None:
    DEBUG = _debug_env.lower() in ('1', 'true', 'yes', 'on')
elif getattr(sys, 'frozen', False):
    DEBUG = False
else:
    DEBUG = 'runserver' in sys.argv

ALLOWED_HOSTS = ['localhost', '127.0.0.1', '192.168.0.14']   

# CORS
# - Tkinter y admin no requieren CORS (no son browsers o son same-origin).
# - El frontend web público (catálogo y pedidos) consume /api/ desde otro origen.
# Política: allowlist explícita. Orígenes LAN cubiertos por regex; orígenes
# públicos se agregan vía env var DJANGO_CORS_ORIGINS (lista separada por comas).

CORS_ALLOWED_ORIGIN_REGEXES = [
    r"^http://localhost(:\d+)?$",
    r"^http://127\.0\.0\.1(:\d+)?$",
    r"^http://192\.168\.0\.\d+(:\d+)?$",
]

_extra_origins = os.environ.get("DJANGO_CORS_ORIGINS", "").strip()
CORS_ALLOWED_ORIGINS = [o.strip() for o in _extra_origins.split(",") if o.strip()]

# Sólo aplicar CORS a /api/. El admin, /media/ y /static/ son same-origin.
CORS_URLS_REGEX = r"^/api/.*$"

CORS_ALLOW_HEADERS = list(default_headers) + ["Range"]
CORS_EXPOSE_HEADERS = ["Content-Range"]

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
    'web_clientes',
    'proveedores',
    'productos',
    'categorias',
    'marcas',
    'presupuestos',
    'remitos',
    'impuestos',
    'comprobantes',
    'pedidos',
    'web_publica',
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
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

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
        #'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
    ],
    # ⭐ Deshabilitar CSRF para APIs (seguro con Token Authentication)
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
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