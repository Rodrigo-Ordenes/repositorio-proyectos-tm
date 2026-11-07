#!/bin/bash
# Teacher notices: pending counter in the page and hourly e-mail digest, against a fake SMTP server (no real e-mail is sent).
set -u +B
S="${PRUEBAS_TMP:-$(mktemp -d)}/avisos"
APP="$(cd "$(dirname "$0")/.." && pwd)"
rm -rf "$S"; mkdir -p "$S"
export APP_DB_PATH=$S/repo.sqlite3 APP_UPLOAD_DIR=$S/files APP_BACKUP_DIR=$S/backups APP_DEMO_AUTH=1 APP_BACKUP_HOURS=0 TRUST_PROXY=0 \
  PUCV_ADMIN_EMAILS=admin@mail.pucv.cl PUCV_INCENTIVA_ADMINS=prof@mail.pucv.cl PUCV_INNOVA_ADMINS=inn@mail.pucv.cl APP_ENV_FILE=$S/no.env
check() { if echo "$2" | grep -q -- "$3"; then echo "OK   $1"; else echo "FAIL $1 -> $(echo "$2" | head -c 300)"; fi; }
cd "$APP"
python3 pruebas/aux/avisos_docente.py 2>"$S/err.log"
grep -i traceback -A8 "$S/err.log" | head -20
check "SMTP sin cifrado solo hacia esta misma máquina" "$(SMTP_HOST=smtp.example.cl SMTP_SECURITY=none SMTP_FROM=a@b.cl APP_BASE_URL=https://x.cl python3 -c 'import server;print(server.email_ready())')" "^False$"
js=$(cat static/app.js)
check "contador en «Revisión» con nombre accesible" "$js" "aria-label=\"Revisión, \${"
check "el contador se actualiza cada 2 minutos con la pestaña visible" "$js" "120000"
check "botón de correo de prueba en el panel" "$js" "Enviar correo de prueba a mi dirección"
check "el cron envía el resumen de pendientes" "$(cat server.py)" "notify_pending_digest()"
