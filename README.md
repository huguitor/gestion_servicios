# 🖥️ Lab Servicios - App de Escritorio (Tkinter)

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![Tkinter](https://img.shields.io/badge/Tkinter-GUI-orange)
![PyInstaller](https://img.shields.io/badge/PyInstaller-6.17.0-green)
![License](https://img.shields.io/badge/License-MIT-yellow)
![GitHub last commit](https://img.shields.io/github/last-commit/huguitor/gestion_servicios)
![GitHub repo size](https://img.shields.io/github/repo-size/huguitor/gestion_servicios)

Aplicación de escritorio para gestión comercial desarrollada en Python con Tkinter. 
Conecta con backend Django REST API para un sistema completo de gestión.

## 📦 Descarga Rápida

[![Download Executable](https://img.shields.io/badge/Download-LabServicios.exe-blue)](https://github.com/huguitor/gestion_servicios/releases/latest)

**Descarga la última versión:** [LabServicios.exe](https://github.com/huguitor/gestion_servicios/releases)

### Instalación en 3 pasos:
1. **Descarga** `LabServicios.exe` de [Releases](https://github.com/huguitor/gestion_servicios/releases)
2. **Ejecuta** el backend desde [app_servicios](https://github.com/huguitor/app_servicios)
3. **Abre** `LabServicios.exe` e ingresa:
   - Usuario: `admin`
   - Contraseña: `Donato2019`

## 🚀 Características Destacadas

### 📊 Dashboard Inteligente
- Estadísticas en tiempo real
- Resumen financiero automático
- Gráficos de conversión de presupuestos
- Acceso rápido a todos los módulos

### 👥 Gestión Completa
| Módulo | Icono | Descripción |
|--------|-------|-------------|
| **Clientes** | 👥 | Gestión completa de clientes con historial |
| **Proveedores** | 🏢 | Control de proveedores y contactos |
| **Productos** | 📦 | Catálogo con imágenes, stock y precios |
| **Servicios** | 🔧 | Servicios con descripción y precios |
| **Presupuestos** | 💰 | Creación, seguimiento y PDF profesional |
| **Impuestos** | 📊 | Configuración de tasas y cálculos |
| **Categorías** | 📑 | Organización por categorías |
| **Marcas** | 🏷️ | Gestión de marcas y proveedores |

### 🎯 Funcionalidades Avanzadas
- ✅ **Login seguro** con autenticación por tokens
- ✅ **Generación de PDFs** profesionales con ReportLab
- ✅ **Búsqueda avanzada** en todos los módulos
- ✅ **Interfaz responsive** adaptable a diferentes pantallas
- ✅ **Atajos de teclado** para productividad
- ✅ **Exportación de datos** en múltiples formatos
- ✅ **Backup automático** de configuraciones

## 🏗️ Arquitectura Técnica

## 🔐 SECRET_KEY

La clave de Django se resuelve en este orden:

1. Variable de entorno `DJANGO_SECRET_KEY` (recomendado en servidor).
2. Archivo `data/secret_key.txt`, autogenerado en el primer arranque si no existe (modo .exe / instalaciones locales).

Nunca se almacena en el repositorio. `data/` ya está en `.gitignore`.

## 🐞 DEBUG

`DEBUG=False` por defecto. Para desarrollo:
- `manage.py runserver` lo activa automáticamente.
- En cualquier otro arranque (gunicorn, waitress), definir `DJANGO_DEBUG=1` en el entorno.

En producción nunca exponer una instancia con `DEBUG=True`: el panel de error filtra `settings`, stack traces y variables.

## 🧹 Deuda técnica conocida: rutas duplicadas en `sistema_general/urls.py`

Cada app de negocio está montada dos veces: con prefijo `/api/` (forma actual) y sin prefijo (forma legacy). Ej:

```
path('api/clientes/', include('clientes.urls')),
...
path('clientes/', include('clientes.urls')),   # legacy
```

**Por qué no se eliminó la forma legacy:** el cliente de escritorio Tkinter (repo separado: `huguitor/app_servicios`) consume exclusivamente las rutas legacy. Análisis del cliente al 2026-05-14: 27 referencias a paths sin `/api/`, ninguna a `/api/`. Ver `api_client.py` y `*_manager.py` en ese repo.

**Por qué no es un problema de seguridad:** `CORS_URLS_REGEX` limita CORS a `^/api/.*$`. Por lo tanto:
- Las rutas legacy no devuelven headers CORS → no son alcanzables desde un navegador en otro origen.
- Sólo clientes nativos (Tkinter, scripts CLI) pueden usarlas, y ya están autenticados por token.

La duplicación es estética/de mantenimiento, no de superficie de ataque.

**Cómo cerrarla cuando se haga un release nuevo del cliente Tkinter:**

1. En el repo `huguitor/app_servicios`, modificar `config.py`:
   ```python
   @classmethod
   def get_api_url(cls, endpoint):
       return f"{cls.API_BASE_URL}/api{endpoint}"
   ```
   Y verificar que todos los managers pasen por `Config.get_api_url(...)` (algunos como `remitos_manager.py` hacen `self.client.get("/remitos/...")` directo y habrá que normalizarlos).
2. Build y distribuir el nuevo `LabServicios.exe`.
3. Después de confirmar que no quedan clientes viejos hablando con las rutas legacy (habilitar `--access-logfile -` en gunicorn unos días y verificar), eliminar del backend el bloque "RUTAS SIN PREFIJO" en `sistema_general/urls.py:39-50`.
