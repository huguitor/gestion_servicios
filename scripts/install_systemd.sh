#!/usr/bin/env bash
#
# install_systemd.sh — Instala y habilita los servicios systemd del sistema.
#
# Hay que correrlo con sudo:    sudo bash install_systemd.sh
#
# Lo que hace:
#   1. Copia las .service a /etc/systemd/system/
#   2. systemctl daemon-reload
#   3. Recopila estáticos de Django (para que el admin tenga su CSS)
#   4. Mata cualquier instancia manual corriendo en :8000 y :5173
#   5. Habilita y arranca los servicios
#   6. Muestra el estado final

set -euo pipefail

SCRIPT_DIR="$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PROJECT_DIR="$( dirname -- "$SCRIPT_DIR" )"
SERVICES_DIR="$SCRIPT_DIR/systemd"

if [[ $EUID -ne 0 ]]; then
  echo "❌ Este script tiene que correr con sudo: sudo bash install_systemd.sh" >&2
  exit 1
fi

# Usuario que será dueño del proceso. Por default, el dueño del proyecto.
APP_USER="$(stat -c '%U' "$PROJECT_DIR/manage.py")"
echo "ℹ️  Usuario de los servicios: $APP_USER"

# --- 1. Copiar archivos .service ---
echo "1/6 — Copiando archivos .service a /etc/systemd/system/..."
for svc in gestion-backend.service gestion-frontend.service; do
  cp -v "$SERVICES_DIR/$svc" "/etc/systemd/system/$svc"
done

# --- 2. Recargar systemd ---
echo "2/6 — Recargando systemd..."
systemctl daemon-reload

# --- 3. collectstatic para el admin ---
echo "3/6 — Recopilando estáticos del admin..."
sudo -u "$APP_USER" -- bash -c "
  cd '$PROJECT_DIR' && \
  source venv/bin/activate && \
  python manage.py collectstatic --no-input
" 2>&1 | tail -3

# --- 4. Matar procesos manuales en los puertos ---
echo "4/6 — Limpiando procesos previos en :8000 y :5173..."
fuser -k 8000/tcp 5173/tcp 2>/dev/null || true
sleep 2

# --- 5. Habilitar + arrancar ---
echo "5/6 — Habilitando servicios para arranque automático..."
systemctl enable gestion-frontend.service gestion-backend.service
echo "   Iniciando gestion-frontend (build inicial, ~2s)..."
systemctl restart gestion-frontend.service
# El build es oneshot — esperamos a que termine para que backend lo tenga listo.
systemctl is-active --quiet gestion-frontend.service || true
echo "   Iniciando gestion-backend..."
systemctl restart gestion-backend.service
sleep 3

# --- 6. Estado final ---
echo
echo "6/6 — Estado final:"
echo "─────────────────────────────────────────────────────────"
systemctl --no-pager status gestion-frontend.service | head -6
echo "─────────────────────────────────────────────────────────"
systemctl --no-pager status gestion-backend.service | head -6
echo "─────────────────────────────────────────────────────────"

IPS="$(hostname -I | tr ' ' '\n' | grep -v '^$' | head -3 | paste -sd, -)"
echo
echo "✅ Listo. URLs de acceso:"
for ip in $(hostname -I); do
  echo "   http://$ip:8000"
done
echo
echo "Comandos útiles:"
echo "   sudo systemctl status  gestion-backend.service"
echo "   sudo systemctl restart gestion-backend.service"
echo "   sudo systemctl stop    gestion-backend.service gestion-frontend.service"
echo "   sudo journalctl -u gestion-backend.service -f"
echo "   bash $SCRIPT_DIR/status.sh   # vista rápida del estado"
