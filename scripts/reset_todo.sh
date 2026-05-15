#!/usr/bin/env bash
#
# reset_todo.sh — Re-inicializa el sistema en blanco.
#
# Hace un backup previo en /var/backups/gestion/ y después:
#   1. flush de la base de datos
#   2. limpia data/media/
#   3. limpia data/backups/
#   4. crea un nuevo superusuario (interactivo)
#
# Pensado para volver a un estado limpio antes de poner el sistema en
# producción. NO es para uso rutinario.

set -euo pipefail

# ----------------------------------------------------------------------------
# Localizar paths a partir del propio script — funciona desde cualquier cwd.
# ----------------------------------------------------------------------------
SCRIPT_DIR="$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PROJECT_DIR="$( dirname -- "$SCRIPT_DIR" )"
VENV="$PROJECT_DIR/venv"
DATA_DIR="$PROJECT_DIR/data"
MEDIA_DIR="$DATA_DIR/media"
BACKUPS_LOCAL="$DATA_DIR/backups"
DB_FILE="$DATA_DIR/database.sqlite3"
BACKUP_TARGET_DIR="/var/backups/gestion"
TS="$(date +%Y%m%d_%H%M%S)"

# Color helpers — solo si la terminal soporta colores.
if [[ -t 1 ]]; then
  R='\033[0;31m'; G='\033[0;32m'; Y='\033[0;33m'; B='\033[0;34m'; N='\033[0m'
else
  R=''; G=''; Y=''; B=''; N=''
fi

info()  { printf "${B}ℹ️  %s${N}\n" "$*"; }
ok()    { printf "${G}✅ %s${N}\n" "$*"; }
warn()  { printf "${Y}⚠️  %s${N}\n" "$*"; }
err()   { printf "${R}❌ %s${N}\n" "$*" >&2; }

# ----------------------------------------------------------------------------
# Sanity checks — antes de pedir confirmación, asegurarnos de que estamos en
# un repo válido. Si algo de esto falla, no tiene sentido seguir.
# ----------------------------------------------------------------------------
if [[ ! -f "$PROJECT_DIR/manage.py" ]]; then
  err "No encuentro manage.py en $PROJECT_DIR — ¿este script está en el lugar correcto?"
  exit 1
fi

if [[ ! -x "$VENV/bin/python" ]]; then
  err "No encuentro el virtualenv en $VENV — activá o creá el venv primero."
  exit 1
fi

# Advertencia si Django parece estar corriendo — no bloqueante pero útil.
if command -v ss &>/dev/null && ss -ltn 2>/dev/null | grep -q ':8000 '; then
  warn "Hay algo escuchando en :8000 (Django probablemente). Conviene pararlo antes."
fi

# ----------------------------------------------------------------------------
# 1. Advertencia + confirmación explícita
# ----------------------------------------------------------------------------
echo
printf "${R}══════════════════════════════════════════════════════════════════${N}\n"
printf "${R}⚠️  ATENCIÓN: Esto borrará TODOS los datos, archivos y backups.${N}\n"
printf "${R}══════════════════════════════════════════════════════════════════${N}\n"
echo
echo "Se van a borrar:"
echo "  • Toda la base de datos ($DB_FILE)"
echo "  • Todos los archivos en $MEDIA_DIR (fotos, logos, adjuntos, etc.)"
echo "  • Todos los backups locales en $BACKUPS_LOCAL"
echo
echo "Antes de borrar nada, se hará un backup previo en:"
echo "  $BACKUP_TARGET_DIR"
echo
read -p "¿Estás seguro? (escribí SI para continuar): " CONFIRM
if [[ "$CONFIRM" != "SI" ]]; then
  err "Cancelado. No se hizo nada."
  exit 1
fi

# ----------------------------------------------------------------------------
# 2. Preparar directorio de backup destino — puede requerir sudo la 1ra vez.
# ----------------------------------------------------------------------------
if [[ ! -d "$BACKUP_TARGET_DIR" ]]; then
  info "El directorio $BACKUP_TARGET_DIR no existe. Lo creo (requiere sudo)..."
  sudo mkdir -p "$BACKUP_TARGET_DIR"
  sudo chown "$USER":"$USER" "$BACKUP_TARGET_DIR"
fi
if [[ ! -w "$BACKUP_TARGET_DIR" ]]; then
  err "No tengo permiso de escritura en $BACKUP_TARGET_DIR. Corregí permisos y reintentá."
  exit 1
fi

# ----------------------------------------------------------------------------
# 3. Backup previo: dump JSON + copia consistente de la BD + tar de media/
# ----------------------------------------------------------------------------
BACKUP_FILE="$BACKUP_TARGET_DIR/reset_backup_${TS}.tar.gz"
info "Generando backup previo: $BACKUP_FILE"

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

# Activar venv para los próximos comandos Python.
# shellcheck source=/dev/null
source "$VENV/bin/activate"
cd "$PROJECT_DIR"

# 3a. Dump JSON (excluyendo tablas internas de Django que loaddata recrea solo)
python manage.py dumpdata \
  --natural-foreign --natural-primary \
  --indent 2 \
  --exclude contenttypes \
  --exclude auth.permission \
  --exclude admin.logentry \
  --exclude sessions \
  --output "$TMP/db.json" 2>/dev/null

# 3b. Copia consistente de la BD SQLite (.backup API, soporta concurrencia)
python - <<PY
import sqlite3
src = sqlite3.connect(r"$DB_FILE")
dst = sqlite3.connect(r"$TMP/database.sqlite3")
with dst:
    src.backup(dst)
dst.close(); src.close()
PY

# 3c. Tar.gz de todo. media/ se incluye solo si existe y tiene contenido.
TAR_ARGS=( -czf "$BACKUP_FILE" -C "$TMP" db.json database.sqlite3 )
if [[ -d "$MEDIA_DIR" ]] && [[ -n "$(ls -A "$MEDIA_DIR" 2>/dev/null)" ]]; then
  TAR_ARGS+=( -C "$DATA_DIR" media )
fi
tar "${TAR_ARGS[@]}"
BACKUP_SIZE="$(du -h "$BACKUP_FILE" | cut -f1)"
ok "Backup guardado ($BACKUP_SIZE): $BACKUP_FILE"

# ----------------------------------------------------------------------------
# 4. Flush de la base de datos
# ----------------------------------------------------------------------------
info "Limpiando base de datos (manage.py flush)..."
python manage.py flush --no-input
ok "Base de datos limpiada."

# ----------------------------------------------------------------------------
# 5. Borrar archivos en media/
# ----------------------------------------------------------------------------
if [[ -d "$MEDIA_DIR" ]]; then
  info "Borrando contenido de $MEDIA_DIR..."
  # Usar `find` para no fallar si el dir está vacío y para borrar también dotfiles.
  find "$MEDIA_DIR" -mindepth 1 -delete
  ok "media/ limpio."
else
  info "$MEDIA_DIR no existe, lo creo vacío."
  mkdir -p "$MEDIA_DIR"
fi

# ----------------------------------------------------------------------------
# 6. Borrar backups locales (data/backups/)
# ----------------------------------------------------------------------------
if [[ -d "$BACKUPS_LOCAL" ]]; then
  info "Borrando contenido de $BACKUPS_LOCAL..."
  find "$BACKUPS_LOCAL" -mindepth 1 -delete
  ok "data/backups/ limpio."
else
  mkdir -p "$BACKUPS_LOCAL"
fi

# ----------------------------------------------------------------------------
# 7. Crear superusuario nuevo (interactivo)
# ----------------------------------------------------------------------------
echo
info "Creando superusuario nuevo (interactivo)."
echo "   Vas a tener que ingresar usuario, email y contraseña."
echo
python manage.py createsuperuser

# ----------------------------------------------------------------------------
# 8. Mensaje final
# ----------------------------------------------------------------------------
echo
ok "Sistema inicializado. Podés arrancar Django normalmente."
echo
echo "Backup previo:    $BACKUP_FILE"
echo "Para restaurarlo: tar -xzf '$BACKUP_FILE' -C /tmp/restore && ..."
echo
