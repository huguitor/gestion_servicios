@echo off
echo === Construyendo BackendLabServicios.exe ===
echo.
pyinstaller --onefile --name "BackendLabServicios" --add-data "db.sqlite3;." --add-data "media;media" --add-data "staticfiles;staticfiles" --add-data "sistema_general;sistema_general" --hidden-import="django.core.handlers.wsgi" --hidden-import="waitress" --hidden-import="whitenoise" --hidden-import="whitenoise.middleware" servidor.py
echo.
echo === Construccion finalizada ===
pause
