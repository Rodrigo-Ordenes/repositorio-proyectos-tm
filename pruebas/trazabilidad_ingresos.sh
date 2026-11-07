#!/bin/bash
# Course-code activity is visible only to the teaching team for that course.
set -u +B
S="${PRUEBAS_TMP:-$(mktemp -d)}/trazabilidad"
APP="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p "$S"
export APP_DB_PATH=$S/repo.sqlite3 APP_UPLOAD_DIR=$S/files APP_BACKUP_DIR=$S/backups PORT=8766 APP_DEMO_AUTH=1 APP_BACKUP_HOURS=0 \
  PUCV_ADMIN_EMAILS=admin@mail.pucv.cl PUCV_INCENTIVA_ADMINS=prof@mail.pucv.cl PUCV_INNOVA_ADMINS=inn@mail.pucv.cl
B=http://localhost:8766
J=(-H "Content-Type: application/json")
check() { if echo "$2" | grep -q -- "$3"; then echo "OK   $1"; else echo "FAIL $1 -> $(echo "$2" | head -c 300)"; fi; }
nocheck() { if echo "$2" | grep -q -- "$3"; then echo "FAIL $1 -> $(echo "$2" | head -c 300)"; else echo "OK   $1"; fi; }
login() { curl -s -c "$S/$1.jar" "${J[@]}" -d "{\"email\":\"$1@mail.pucv.cl\"}" $B/auth/demo -o /dev/null; }
req() { local who=$1; shift; curl -s -b "$S/$who.jar" "${J[@]}" -w ' [%{http_code}]\n' "$@"; }
val() { python3 -c "import sys,json;d=json.loads(sys.stdin.read().rsplit(' [',1)[0]);print(eval(sys.argv[1]))" "$1"; }

cd "$APP"
python3 server.py > "$S/server.log" 2>&1 & PID=$!; sleep 1.2
for u in admin prof inn ana outside; do login "$u"; done
IC=$(req prof -d '{"project_id":"incentiva","section":"Bioanálisis","days":14,"roster":"ana@mail.pucv.cl"}' $B/api/admin/join-codes | val "d['code']")
NC=$(req inn -d '{"project_id":"innova","days":14}' $B/api/admin/join-codes | val "d['code']")
IC_FORMAT="$IC"
NC_FORMAT="$NC"
req ana -d "{\"code\":\"$IC\"}" $B/api/join > /dev/null
req outside -d "{\"code\":\"$IC\"}" $B/api/join > /dev/null
check "un código inexistente se rechaza" "$(req ana -d '{"code":"0000-0000"}' $B/api/join)" '\[400\]'
check "un código inexistente no crea un registro" "$(sqlite3 "$S/repo.sqlite3" "SELECT count(*) FROM audit_events WHERE event_type='course_code_login'")" '^1$'
LIST=$(req prof $B/api/admin/join-codes)
check "la docente ve el correo y fecha asociados a su código" "$LIST" '"entries":.*"email": "ana@mail.pucv.cl", "created_at": [0-9]'
nocheck "un correo rechazado no aparece como ingreso" "$LIST" '"email": "outside@mail.pucv.cl"'
nocheck "la lista completa del curso no se expone" "$LIST" '"roster":'
OTHER=$(req inn $B/api/admin/join-codes)
check "docente ve el código de su asignatura" "$OTHER" "\"code\": \"$NC_FORMAT\""
nocheck "otra asignatura no recibe este código ni sus ingresos" "$OTHER" "$IC_FORMAT"
check "estudiante sin gestión no puede consultar ingresos" "$(req ana $B/api/admin/join-codes)" '\[403\]'

# An expired event is purged on the next successful audit write.
sqlite3 "$S/repo.sqlite3" "INSERT INTO audit_events(event_type,actor_email,subject_email,project_id,entity_type,entity_id,created_at) VALUES('course_code_login','ana@mail.pucv.cl','ana@mail.pucv.cl','incentiva','join_code',1,CAST(strftime('%s','now') AS INTEGER)-181*86400);"
req ana -d "{\"code\":\"$IC\"}" $B/api/join > /dev/null
check "los ingresos con más de 180 días se eliminan al registrar" "$(sqlite3 "$S/repo.sqlite3" "SELECT count(*) FROM audit_events WHERE created_at < CAST(strftime('%s','now') AS INTEGER)-180*86400")" '^0$'
AUDIT_SQL=$(sqlite3 "$S/repo.sqlite3" "SELECT sql FROM sqlite_master WHERE type='table' AND name='audit_events'")
check "la tabla de auditoría se crea" "$AUDIT_SQL" '^CREATE TABLE'
nocheck "auditoría no depende de la cuenta para conservar el rastro" "$AUDIT_SQL" 'REFERENCES users'

kill "$PID"; wait "$PID" 2>/dev/null || true
