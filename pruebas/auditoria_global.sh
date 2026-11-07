#!/bin/bash
# Sensitive sign-ins and administration changes are visible only to global admins.
set -u +B
S="${PRUEBAS_TMP:-$(mktemp -d)}/auditoria"
APP="$(cd "$(dirname "$0")/.." && pwd)"
rm -rf "$S"; mkdir -p "$S"
export APP_DB_PATH=$S/repo.sqlite3 APP_UPLOAD_DIR=$S/files APP_BACKUP_DIR=$S/backups PORT=8766 APP_DEMO_AUTH=1 APP_BACKUP_HOURS=0 TRUST_PROXY=0 \
  PUCV_ADMIN_EMAILS=admin@mail.pucv.cl PUCV_INCENTIVA_ADMINS=prof@mail.pucv.cl PUCV_INNOVA_ADMINS=inn@mail.pucv.cl
B=http://localhost:8766
J=(-H "Content-Type: application/json")
check() { if echo "$2" | grep -q -- "$3"; then echo "OK   $1"; else echo "FAIL $1 -> $(echo "$2" | head -c 300)"; fi; }
nocheck() { if echo "$2" | grep -q -- "$3"; then echo "FAIL $1 -> $(echo "$2" | head -c 300)"; else echo "OK   $1"; fi; }
login() { curl -s -c "$S/$1.jar" "${J[@]}" -d "{\"email\":\"$1@mail.pucv.cl\"}" $B/auth/demo -o /dev/null; }
req() { local who=$1; shift; curl -s -b "$S/$who.jar" "${J[@]}" -w ' [%{http_code}]\n' "$@"; }
val() { python3 -c "import sys,json;d=json.loads(sys.stdin.read().rsplit(' [',1)[0]);print(eval(sys.argv[1]))" "$1"; }

SOSOUT=$(APP_DB_PATH=$APP_DB_PATH python3 "$APP/server.py" codigo-sos rescate@mail.pucv.cl)
SOSCODE=$(echo "$SOSOUT" | sed -n 's/^Código SOS para [^:]*: //p' | sed 's/ (válido.*//')
python3 "$APP/server.py" > "$S/server.log" 2>&1 & PID=$!; sleep 1.2
for u in admin prof inn ana beto; do login "$u"; done
check "ingreso SOS válido" "$(curl -s -c "$S/sos.jar" "${J[@]}" -d "{\"email\":\"rescate@mail.pucv.cl\",\"code\":\"$SOSCODE\"}" -w ' [%{http_code}]' $B/auth/code)" '\[302\]'

IC=$(req prof -d '{"project_id":"incentiva","days":14,"roster":"ana@mail.pucv.cl"}' $B/api/admin/join-codes | val "d['code']")
IC_ID=$(req prof $B/api/admin/join-codes | val "d[0]['id']")
req ana -d "{\"code\":\"$IC\"}" $B/api/join > /dev/null
req prof -d "{\"id\":$IC_ID}" $B/api/admin/join-codes/disable > /dev/null
req prof -d "{\"id\":$IC_ID}" $B/api/admin/join-codes/disable > /dev/null
req admin -d '{"email":"apoyo@mail.pucv.cl","project_id":"incentiva"}' $B/api/admin/staff > /dev/null
req admin -d '{"email":"apoyo@mail.pucv.cl","project_id":"incentiva"}' $B/api/admin/staff > /dev/null
req admin -d '{"email":"apoyo@mail.pucv.cl","project_id":"incentiva","action":"remove"}' $B/api/admin/staff > /dev/null
req admin -d '{"email":"apoyo@mail.pucv.cl","project_id":"incentiva","action":"remove"}' $B/api/admin/staff > /dev/null
MID=$(req prof $B/api/admin/members | val "[m['id'] for m in d if m['email']=='ana@mail.pucv.cl'][0]")
req prof -d "{\"kind\":\"membership\",\"id\":$MID,\"decision\":\"revoke\"}" $B/api/admin/review > /dev/null
req admin -d '{"email":"beto@mail.pucv.cl","confirm":"beto@mail.pucv.cl"}' $B/api/admin/person/delete > /dev/null
check "estudiante no puede ver el registro global" "$(req ana $B/api/admin/audit)" '\[403\]'
req admin -d '{"confirm":"CERRAR COHORTE"}' $B/api/admin/cohort/close > /dev/null

sqlite3 "$S/repo.sqlite3" "INSERT INTO audit_events(event_type,actor_email,entity_type,ip_hash,created_at) VALUES('expired_test','admin@mail.pucv.cl','test',printf('%064d',0),CAST(strftime('%s','now') AS INTEGER)-181*86400);"
AUDIT=$(req admin $B/api/admin/audit)
nocheck "la API no expone eventos de más de 180 días" "$AUDIT" 'expired_test'
check "la consulta elimina eventos vencidos" "$(sqlite3 "$S/repo.sqlite3" "SELECT count(*) FROM audit_events WHERE event_type='expired_test'")" '^0$'
check "la auditoría registra ingreso SOS" "$AUDIT" '"event_type": "sos_login"'
check "la auditoría registra ingreso por código del curso" "$AUDIT" '"event_type": "course_code_login"'
check "la auditoría registra creación de código" "$AUDIT" '"event_type": "course_code_created"'
check "la auditoría registra desactivación de código" "$AUDIT" '"event_type": "course_code_disabled"'
check "la auditoría registra alta docente" "$AUDIT" '"event_type": "staff_added"'
check "la auditoría registra retiro docente" "$AUDIT" '"event_type": "staff_removed"'
check "la auditoría registra retiro de acceso" "$AUDIT" '"event_type": "membership_revoked"'
check "la auditoría registra anonimización de persona" "$AUDIT" '"event_type": "person_anonymized"'
check "la auditoría registra cierre con anonimización de cohorte" "$AUDIT" '"event_type": "cohort_anonymized"'
check "la auditoría identifica quién incorporó a una persona docente" "$AUDIT" '"actor_email": "admin@mail.pucv.cl", "subject_email": "apoyo@mail.pucv.cl"'
check "repetir una desactivación no duplica el evento" "$(sqlite3 "$S/repo.sqlite3" "SELECT count(*) FROM audit_events WHERE event_type='course_code_disabled'")" '^1$'
check "repetir una incorporación docente no duplica el evento" "$(sqlite3 "$S/repo.sqlite3" "SELECT count(*) FROM audit_events WHERE event_type='staff_added'")" '^1$'
check "repetir un retiro docente no duplica el evento" "$(sqlite3 "$S/repo.sqlite3" "SELECT count(*) FROM audit_events WHERE event_type='staff_removed'")" '^1$'
check "docente de asignatura no puede ver el registro global" "$(req prof $B/api/admin/audit)" '\[403\]'
check "sin sesión no se puede ver el registro global" "$(curl -s -w ' [%{http_code}]' $B/api/admin/audit)" '\[401\]'
check "todas las acciones llevan una huella IP de 64 caracteres" "$(sqlite3 "$S/repo.sqlite3" "SELECT count(*) FROM audit_events WHERE length(ip_hash)<>64")" '^0$'
nocheck "ni la base de auditoría guarda la IP en claro" "$(sqlite3 "$S/repo.sqlite3" "SELECT group_concat(ip_hash,' ') FROM audit_events")" '127\.0\.0\.1'
EXPECTED_HASH=$(python3 - "$S/repo.sqlite3" <<'PY'
import hashlib, hmac, sqlite3, sys
db = sqlite3.connect(sys.argv[1])
salt = bytes.fromhex(db.execute("SELECT value FROM settings WHERE key='audit_ip_salt'").fetchone()[0])
print(hmac.new(salt, b"127.0.0.1", hashlib.sha256).hexdigest())
PY
)
check "la huella usa HMAC y la sal persistida" "$(sqlite3 "$S/repo.sqlite3" "SELECT ip_hash FROM audit_events WHERE event_type='sos_login' ORDER BY id DESC LIMIT 1")" "^$EXPECTED_HASH$"
nocheck "el servidor no imprime IP en claro en consola" "$(cat "$S/server.log")" '127\.0\.0\.1'

sqlite3 "$S/repo.sqlite3" "WITH RECURSIVE seq(x) AS (SELECT 1 UNION ALL SELECT x+1 FROM seq WHERE x<501) INSERT INTO audit_events(event_type,created_at) SELECT 'pagination_test',CAST(strftime('%s','now') AS INTEGER) FROM seq;"
PAGE1=$(req admin $B/api/admin/audit)
PAGE2=$(req admin $B/api/admin/audit?offset=500)
check "la auditoría pagina 500 eventos por solicitud" "$(echo "$PAGE1" | val 'len(d)')" '^500$'
check "la auditoría permite consultar eventos anteriores" "$(echo "$PAGE2" | val 'len(d)')" '^10$'

kill "$PID"; wait "$PID" 2>/dev/null || true
