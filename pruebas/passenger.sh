#!/bin/bash
# Passenger (cPanel «Python» app): passenger_wsgi.application answers exactly like the stdlib server,
# and maintenance runs from cron instead of background threads.
set -u +B
S="${PRUEBAS_TMP:-$(mktemp -d)}/passenger"
APP="$(cd "$(dirname "$0")/.." && pwd)"
rm -rf "$S"; mkdir -p "$S"
export APP_DB_PATH=$S/repo.sqlite3 APP_UPLOAD_DIR=$S/files APP_BACKUP_DIR=$S/backups PORT=8766 APP_DEMO_AUTH=1 APP_BACKUP_HOURS=24 TRUST_PROXY=0 \
  PUCV_ADMIN_EMAILS=admin@mail.pucv.cl APP_BASE_URL=http://localhost:8766
check() { if echo "$2" | grep -q -- "$3"; then echo "OK   $1"; else echo "FAIL $1 -> $(echo "$2" | head -c 300)"; fi; }
cd "$APP"
python3 server.py > "$S/server.log" 2>&1 & PID=$!; sleep 1.2
python3 pruebas/aux/comparar_wsgi.py http://localhost:8766 2>"$S/wsgi.err"
kill "$PID"; wait "$PID" 2>/dev/null || true
check "importar el adaptador no inicia hilos de fondo" "$(python3 -c "import threading,passenger_wsgi;print(threading.active_count())")" "^1$"
check "importar el adaptador prepara la base" "$(sqlite3 "$S/repo.sqlite3" "select count(*) from sqlite_master where name='users'")" "^1$"
rm -rf "$S/backups"
out=$(python3 server.py mantenimiento 2>&1)
check "mantenimiento crea el respaldo diario cuando corresponde" "$out" "Respaldo de la base:"
check "mantenimiento depura la auditoría" "$out" "Auditoría depurada"
check "mantenimiento no repite el respaldo dentro de las 24 h" "$(python3 server.py mantenimiento 2>&1)" "Respaldo al día"
check "la documentación trae el comando de cron" "$(cat MANUAL_DESPLIEGUE.md)" "server.py mantenimiento"
grep -i traceback -A8 "$S/server.log" "$S/wsgi.err" | head -20

# Shared configuration file outside the repository, for the Passenger app and for cron alike
mkdir -p "$S/cfg"; printf '# comentario\nAPP_DB_PATH=%s/cfg/otra.sqlite3\nSMTP_FROM="Avisos <avisos@example.cl>"\nPUCV_ADMIN_EMAILS=archivo@mail.pucv.cl\n' "$S" > "$S/cfg/config.env"; chmod 600 "$S/cfg/config.env"
got=$(cd "$APP" && env -u APP_DB_PATH APP_ENV_FILE="$S/cfg/config.env" PUCV_ADMIN_EMAILS=entorno@mail.pucv.cl python3 -c "import server;print(server.DB_PATH, server.SMTP_FROM, sorted(server.ADMIN_EMAILS))")
check "config.env define las rutas de datos" "$got" "cfg/otra.sqlite3"
check "config.env acepta valores entre comillas" "$got" "Avisos <avisos@example.cl>"
check "el entorno tiene prioridad sobre config.env" "$got" "entorno@mail.pucv.cl"
chmod 644 "$S/cfg/config.env"
check "config.env legible por otros: aviso" "$(cd "$APP" && APP_ENV_FILE="$S/cfg/config.env" python3 -c "import server" 2>&1)" "permisos 600"
check "sin config.env el servidor arranca igual" "$(cd "$APP" && APP_ENV_FILE="$S/no-existe.env" python3 -c "import server;print('ok')")" "^ok$"
check "config.env nunca en el repositorio" "$(cd "$APP" && git ls-files | grep -c 'config.env')" "^0$"
