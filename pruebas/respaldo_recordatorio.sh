#!/bin/bash
# Reminder of the last full backup downloaded off-site: who, when and a warning after 7 days.
set -u +B
S="${PRUEBAS_TMP:-$(mktemp -d)}/respaldo"
APP="$(cd "$(dirname "$0")/.." && pwd)"
rm -rf "$S"; mkdir -p "$S"
export APP_DB_PATH=$S/repo.sqlite3 APP_UPLOAD_DIR=$S/files APP_BACKUP_DIR=$S/backups PORT=8766 APP_DEMO_AUTH=1 APP_BACKUP_HOURS=0 TRUST_PROXY=0 \
  PUCV_ADMIN_EMAILS=admin@mail.pucv.cl PUCV_INCENTIVA_ADMINS=prof@mail.pucv.cl
B=http://localhost:8766
J=(-H "Content-Type: application/json")
check() { if echo "$2" | grep -q -- "$3"; then echo "OK   $1"; else echo "FAIL $1 -> $(echo "$2" | head -c 300)"; fi; }
login() { curl -s -c "$S/$1.jar" "${J[@]}" -d "{\"email\":\"$1@mail.pucv.cl\"}" $B/auth/demo -o /dev/null; }
req() { local who=$1; shift; curl -s -b "$S/$who.jar" "${J[@]}" -w ' [%{http_code}]\n' "$@"; }

cd "$APP"
python3 server.py > "$S/server.log" 2>&1 & PID=$!; sleep 1.2
for u in admin prof; do login $u; done
check "sin descargas: el aviso pide el primer respaldo" "$(req admin $B/api/admin/backups)" '"last_download": null.*"download_overdue": true'
check "la docente de asignatura no descarga el respaldo" "$(curl -s -o /dev/null -w '%{http_code}' -b "$S/prof.jar" $B/api/admin/backup)" "403"
check "la descarga entrega un zip" "$(curl -s -b "$S/admin.jar" $B/api/admin/backup | head -c 2)" "PK"
info=$(req admin $B/api/admin/backups)
check "queda registrada quién y cuándo descargó" "$info" '"last_download": {"at": [0-9]*, "by": "admin@mail.pucv.cl"}'
check "recién descargado no hay aviso" "$info" '"download_overdue": false'
check "la descarga queda en la auditoría" "$(req admin $B/api/admin/audit)" '"event_type": "full_backup_downloaded"'
sqlite3 "$S/repo.sqlite3" "UPDATE settings SET value=json_set(value,'\$.at',CAST(strftime('%s','now') AS INTEGER)-8*86400) WHERE key='last_full_backup_download'"
check "después de 7 días vuelve el aviso" "$(req admin $B/api/admin/backups)" '"download_overdue": true'
check "el aviso indica los días transcurridos" "$(req admin $B/api/admin/backups)" '"days_since_download": 8'
kill "$PID"; wait "$PID" 2>/dev/null || true
grep -i traceback -A6 "$S/server.log" | head -20
