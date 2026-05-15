#!/usr/bin/env bash
#
# status.sh — Vista rápida de cómo están los servicios + URL de acceso.
# No requiere sudo (solo lectura).

set -euo pipefail

if [[ -t 1 ]]; then
  G='\033[0;32m'; R='\033[0;31m'; Y='\033[0;33m'; B='\033[0;34m'; D='\033[0;90m'; N='\033[0m'
else
  G=''; R=''; Y=''; B=''; D=''; N=''
fi

# ─────────────────────────────────────────────────────────────────────────
# Para cada servicio: estado + uptime + última línea de log.
# ─────────────────────────────────────────────────────────────────────────
service_status() {
  local svc="$1"
  if ! systemctl list-unit-files "$svc" &>/dev/null; then
    printf "${R}● %s${N} — no instalado (correr install_systemd.sh)\n" "$svc"
    return
  fi
  local active enabled
  active="$(systemctl is-active "$svc" 2>/dev/null || echo unknown)"
  enabled="$(systemctl is-enabled "$svc" 2>/dev/null || echo unknown)"
  local icon color
  case "$active" in
    active)   icon="●"; color="$G" ;;
    inactive) icon="○"; color="$D" ;;
    failed)   icon="●"; color="$R" ;;
    *)        icon="?"; color="$Y" ;;
  esac
  printf "${color}%s %s${N}  active=${color}%s${N}  enabled=%s\n" \
    "$icon" "$svc" "$active" "$enabled"
  # Última línea relevante del journal
  local last
  last="$(journalctl -u "$svc" --no-pager -n 1 -o cat 2>/dev/null | tr -d '\n' | cut -c1-100)"
  if [[ -n "$last" ]]; then
    printf "  ${D}↳ último log:${N} %s\n" "$last"
  fi
}

# ─────────────────────────────────────────────────────────────────────────
# Banner
# ─────────────────────────────────────────────────────────────────────────
printf "${B}═══════════════════════════════════════════════════════════${N}\n"
printf "${B}  Gestión Comercial — Estado del sistema${N}\n"
printf "${B}═══════════════════════════════════════════════════════════${N}\n"
echo

# Servicios
echo "Servicios:"
service_status gestion-frontend.service
service_status gestion-backend.service
echo

# Puerto 8000 — comprobar que algo escucha ahí
if ss -ltn 2>/dev/null | grep -q ':8000 '; then
  printf "${G}✓ Algo está escuchando en :8000${N}\n"
else
  printf "${R}✗ Nada está escuchando en :8000${N}\n"
fi

# HTTP check al endpoint público
if command -v curl &>/dev/null; then
  http_code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 3 http://127.0.0.1:8000/api/configuracion/configuracion/config_login/ || echo 'sin respuesta')"
  if [[ "$http_code" == "200" ]]; then
    printf "${G}✓ API responde OK (HTTP 200)${N}\n"
  else
    printf "${R}✗ API no responde correctamente (HTTP %s)${N}\n" "$http_code"
  fi
fi
echo

# URLs de acceso
echo "URLs de acceso desde la LAN:"
HAS_IP=0
for ip in $(hostname -I); do
  printf "  ${B}http://%s:8000${N}\n" "$ip"
  HAS_IP=1
done
if [[ $HAS_IP -eq 0 ]]; then
  printf "  ${R}(sin IPs de red — revisar conexión)${N}\n"
fi
echo

# Tamaño BD + último backup
DB="/var/www/gestion_servicios/data/database.sqlite3"
if [[ -f "$DB" ]]; then
  size="$(du -h "$DB" | cut -f1)"
  mtime="$(stat -c '%y' "$DB" | cut -d. -f1)"
  printf "Base de datos: ${D}%s · %s${N}\n" "$size" "$mtime"
fi

LAST_BACKUP="$(ls -t /var/www/gestion_servicios/data/backups/*.{json,zip,db} 2>/dev/null | head -1 || true)"
if [[ -n "${LAST_BACKUP:-}" ]]; then
  size="$(du -h "$LAST_BACKUP" | cut -f1)"
  mtime="$(stat -c '%y' "$LAST_BACKUP" | cut -d. -f1)"
  printf "Último backup: ${D}%s · %s${N}\n" "$size" "$mtime"
  printf "               ${D}%s${N}\n" "$(basename "$LAST_BACKUP")"
else
  printf "${D}Sin backups guardados${N}\n"
fi
echo

# Tips
printf "${D}Comandos útiles:${N}\n"
printf "${D}  sudo systemctl restart gestion-backend${N}\n"
printf "${D}  sudo journalctl -u gestion-backend -f${N}\n"
printf "${D}  sudo journalctl -u gestion-backend -n 50${N}\n"
