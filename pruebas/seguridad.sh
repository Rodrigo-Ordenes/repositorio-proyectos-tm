#!/bin/bash
# Regression checks for the security review fixes, CSRF/rate limits, text materials and drafts.
set -u +B
S="${PRUEBAS_TMP:-$(mktemp -d)}/sec"
APP="$(cd "$(dirname "$0")/.." && pwd)"
rm -rf "$S"; mkdir -p "$S"
export APP_DB_PATH=$S/repo.sqlite3 APP_UPLOAD_DIR=$S/files APP_BACKUP_DIR=$S/backups APP_DEMO_AUTH=1 PORT=8766 \
  PUCV_ADMIN_EMAILS=admin@mail.pucv.cl,jefa@mail.pucv.cl PUCV_INCENTIVA_ADMINS=prof@mail.pucv.cl PUCV_INNOVA_ADMINS=innova@mail.pucv.cl TRUST_PROXY=1
B=http://localhost:8766
J=(-H "Content-Type: application/json")
check() { if echo "$2" | grep -q -- "$3"; then echo "OK   $1"; else echo "FAIL $1 -> $(echo "$2" | head -c 300)"; fi; }
login() { curl -s -c "$S/$1.jar" "${J[@]}" -d "{\"email\":\"$1@mail.pucv.cl\"}" $B/auth/demo -o /dev/null; }
req() { local who=$1; shift; curl -s -b "$S/$who.jar" "${J[@]}" -w ' [%{http_code}]\n' "$@"; }
val() { python3 -c "import sys,json;d=json.loads(sys.stdin.read().rsplit(' [',1)[0]);print(eval(sys.argv[1]))" "$1"; }
start() { python3 "$APP/server.py" >> "$S/server.log" 2>&1 & PID=$!; sleep 1.2; }

# Migration of the anonymous tables from the old rowid layout keeps the data.
python3 - "$APP" <<'EOF'
import sys
sys.path.insert(0, sys.argv[1]); import server
server.init_db()
db = server.connect()
db.executescript("""INSERT INTO users(id,email,display_name) VALUES (3,'u3@mail.pucv.cl','U3'),(7,'u7@mail.pucv.cl','U7');
INSERT INTO exit_tickets(id,project_id,code,title,questions,created_at,closes_at) VALUES (1,'incentiva','OLD123','Antiguo','["q"]',0,0);
DROP TABLE exit_ticket_answers; DROP TABLE exit_ticket_respondents;
CREATE TABLE exit_ticket_answers (id TEXT PRIMARY KEY, ticket_id INTEGER NOT NULL REFERENCES exit_tickets(id), answers TEXT NOT NULL, answered_on TEXT NOT NULL);
CREATE TABLE exit_ticket_respondents (ticket_id INTEGER NOT NULL REFERENCES exit_tickets(id), user_id INTEGER NOT NULL REFERENCES users(id), PRIMARY KEY(ticket_id, user_id));
INSERT INTO exit_ticket_respondents VALUES (1,7); INSERT INTO exit_ticket_answers VALUES ('b',1,'["de 7"]','2026-10-30');
INSERT INTO exit_ticket_respondents VALUES (1,3); INSERT INTO exit_ticket_answers VALUES ('a',1,'["de 3"]','2026-10-30');""")
db.execute("PRAGMA foreign_keys=OFF"); db.execute("INSERT INTO exit_ticket_answers VALUES ('z',99,'[1]','2026-10-30')"); db.commit()
EOF
start
check "tablas anónimas sin rowid" "$(sqlite3 $S/repo.sqlite3 "select count(*) from sqlite_master where sql like '%WITHOUT ROWID%'")" "^4$"
check "migración conserva respuestas" "$(sqlite3 $S/repo.sqlite3 'select count(*) from exit_ticket_answers')" "^2$"
check "orden físico ya no es el de inserción" "$(sqlite3 $S/repo.sqlite3 'select group_concat(user_id) from exit_ticket_respondents')" "^3,7$"
check "secure_delete activo" "$(python3 -c "import sys;sys.path.insert(0,'$APP');import server;print(server.connect().execute('PRAGMA secure_delete').fetchone()[0])")" "^1$"
for u in admin prof innova ana bea; do login $u; done

# 1. Editors cannot obtain sign-in codes for staff or for people of other courses
r=$(req prof -d '{"project_id":"incentiva","emails":"jefa@mail.pucv.cl innova@mail.pucv.cl nueva@mail.pucv.cl"}' $B/api/admin/access-codes)
check "editor: rechaza código para admin y otra docente" "$r" '"refused": \["jefa@mail.pucv.cl", "innova@mail.pucv.cl"\]'
check "editor: sí emite para estudiante nueva" "$r" '"email": "nueva@mail.pucv.cl"'
IC=$(req innova -d '{"project_id":"innova","days":3}' $B/api/admin/join-codes | val "d['code']")
req bea -d "{\"code\":\"$IC\"}" $B/api/join > /dev/null
check "editor: rechaza estudiante de otra asignatura" "$(req prof -d '{"project_id":"incentiva","emails":"bea@mail.pucv.cl"}' $B/api/admin/access-codes)" '"refused": \["bea@mail.pucv.cl"\]'
check "admin global sí puede" "$(req admin -d '{"project_id":"incentiva","emails":"jefa@mail.pucv.cl"}' $B/api/admin/access-codes)" '"refused": \[\]'

# 2. Revocation sticks; a rejected request does not block the class code
PC=$(req prof -d '{"project_id":"incentiva","days":3}' $B/api/admin/join-codes | val "d['code']")
req ana -d "{\"code\":\"$PC\"}" $B/api/join > /dev/null
MID=$(req prof $B/api/admin/members | val "[m['id'] for m in d if m['email']=='ana@mail.pucv.cl'][0]")
req prof -d "{\"kind\":\"membership\",\"id\":$MID,\"decision\":\"revoke\"}" $B/api/admin/review > /dev/null
check "retirada: no vuelve con el código" "$(req ana -d "{\"code\":\"$PC\"}" $B/api/join)" "\[403\]"
check "retirada: no puede volver a solicitar" "$(req ana -d '{"project_id":"incentiva"}' $B/api/access-requests)" "\[403\]"
check "retirada: sigue fuera tras intentarlo" "$(req ana -d "{\"code\":\"$PC\"}" $B/api/join)" "\[403\]"
ACODE=$(req prof -d '{"project_id":"incentiva","emails":"ana@mail.pucv.cl"}' $B/api/admin/access-codes | val "d['codes'][0]['code']")
curl -s -c $S/ana.jar "${J[@]}" -d "{\"email\":\"ana@mail.pucv.cl\",\"code\":\"$ACODE\"}" $B/auth/code -o /dev/null
check "código personal de la docente restituye" "$(req ana $B/api/me)" '"active_projects": \["incentiva"\]'
login carla
req carla -d '{"project_id":"incentiva"}' $B/api/access-requests > /dev/null
RQ=$(req prof $B/api/admin/pending | val "d['access_requests'][0]['id']")
req prof -d "{\"kind\":\"access_request\",\"id\":$RQ,\"decision\":\"reject\"}" $B/api/admin/review > /dev/null
check "solicitud rechazada no bloquea el código" "$(req carla -d "{\"code\":\"$PC\"}" $B/api/join)" "\[200\]"

# 3. Evidence and comments of retired work
PDF=$(printf '%%PDF-1.4 ficha' | base64)
req carla -d "{\"project_id\":\"incentiva\",\"section\":\"Bioanálisis\",\"team_name\":\"E1\",\"title\":\"Ficha retirable\",\"summary\":\"S\",\"members\":\"Carla\",\"video_url\":\"https://youtu.be/dQw4w9WgXcQ\",\"evidence_file_base64\":\"$PDF\",\"evidence_filename\":\"f.pdf\",\"video_length_confirmed\":true,\"consent_confirmed\":true,\"project_fields\":{\"challenge\":\"Seguimiento\",\"research_question\":\"¿Mejora el acceso?\",\"evidence\":\"Fuente 1; fuente 2; fuente 3\",\"solution\":\"Propuesta de prueba\",\"community\":\"C\",\"indicator\":\"I\",\"limitations\":\"L\"}}" $B/api/submissions > /dev/null
SID=$(req prof $B/api/admin/pending | val "d['submissions'][0]['id']")
req prof -d "{\"kind\":\"submission\",\"id\":$SID,\"decision\":\"publish\"}" $B/api/admin/review > /dev/null
RID=$(req ana "$B/api/resources?project=incentiva" | val "[r['id'] for r in d if r['title']=='Ficha retirable'][0]")
SLUG=$(req ana "$B/api/resources?project=incentiva" | val "[r['slug'] for r in d if r['title']=='Ficha retirable'][0]")
req prof -d "{\"project_id\":\"incentiva\",\"slug\":\"$SLUG\",\"body\":\"Comentario docente\"}" $B/api/comments > /dev/null
check "publicada: ficha descargable" "$(req ana $B/api/submissions/$SID/evidence)" "%PDF-1.4 ficha"
req prof -d "{\"id\":$RID,\"title\":\"Ficha retirable\",\"category\":\"Video-prototipo\",\"summary\":\"S\",\"status\":\"draft\"}" $B/api/admin/resources/update > /dev/null
check "retirada: ficha ya no se descarga" "$(req ana $B/api/submissions/$SID/evidence)" "\[403\]"
check "retirada: comentarios ocultos" "$(req ana "$B/api/projects/incentiva/resources/$SLUG/comments")" '^\[\] \[200\]'
check "retirada: la docente sí los ve" "$(req prof "$B/api/projects/incentiva/resources/$SLUG/comments")" "Comentario docente"
check "retirada: el equipo autor conserva su ficha" "$(req carla $B/api/submissions/$SID/evidence)" "%PDF-1.4 ficha"

# 5. Spoofed X-Forwarded-For no longer resets the per-IP limit
for i in $(seq 1 30); do curl -s -o /dev/null "${J[@]}" -H "X-Forwarded-For: 10.0.0.$i, 200.1.1.1" -d "{\"email\":\"x$i@mail.pucv.cl\",\"code\":\"AAAA-BBBB\"}" $B/auth/code; done
check "límite por IP con cabecera falsificada" "$(curl -s -o /dev/null -w '%{http_code}' "${J[@]}" -H 'X-Forwarded-For: 9.9.9.9, 200.1.1.1' -d '{"email":"y@mail.pucv.cl","code":"AAAA-BBBB"}' $B/auth/code)" "429"

# 6. Malformed input answers 400 instead of dropping the connection
check "id enorme" "$(curl -s -b $S/ana.jar -o /dev/null -w '%{http_code}' $B/api/peer/99999999999999999999999)" "400"
check "número 1e400" "$(curl -s -b $S/prof.jar -o /dev/null -w '%{http_code}' "${J[@]}" -d '{"project_id":"incentiva","days":1e400}' $B/api/admin/join-codes)" "400"
check "cuerpo no UTF-8" "$(printf '{"email":"\xff"}' | curl -s -o /dev/null -w '%{http_code}' "${J[@]}" --data-binary @- $B/auth/code)" "400"
TK=$(req prof -d '{"project_id":"incentiva","title":"T","questions":5}' $B/api/admin/tickets)
check "preguntas con tipo incorrecto usan las estándar" "$TK" "\[201\]"
check "respuestas como texto" "$(req ana -d '{"answers":"abc"}' $B/api/tickets/$(echo "$TK" | val "d['code']")/answer)" "\[400\]"

# CSRF Origin check and comment limit
check "POST desde otro sitio bloqueado" "$(curl -s -b $S/ana.jar -o /dev/null -w '%{http_code}' "${J[@]}" -H 'Origin: https://evil.example' -d '{"project_id":"incentiva"}' $B/api/access-requests)" "403"
check "POST con Origin del mismo sitio" "$(curl -s -b $S/carla.jar -o /dev/null -w '%{http_code}' "${J[@]}" -H 'Origin: http://localhost:8766' -d '{"project_id":"incentiva"}' $B/api/access-requests)" "200"
check "Origin null bloqueado" "$(curl -s -o /dev/null -w '%{http_code}' "${J[@]}" -H 'Origin: null' -d '{}' $B/auth/code)" "403"
req prof -d "{\"id\":$RID,\"title\":\"Ficha retirable\",\"category\":\"Video-prototipo\",\"summary\":\"S\",\"status\":\"published\"}" $B/api/admin/resources/update > /dev/null
for i in $(seq 1 20); do req ana -d "{\"project_id\":\"incentiva\",\"slug\":\"$SLUG\",\"body\":\"c$i\"}" $B/api/comments > /dev/null; done
check "límite de 20 comentarios por hora" "$(req ana -d "{\"project_id\":\"incentiva\",\"slug\":\"$SLUG\",\"body\":\"otro\"}" $B/api/comments)" "\[429\]"
check "CSV neutraliza tabulación" "$(python3 -c "
import sys;sys.path.insert(0,'$APP');import server,io
class F(server.App):
    def __init__(s): s.out=None
    def send_bytes(s,b,*a,**k): s.out=b
f=F();f.send_csv('x.csv',['a'],[['\tcmd']]);print(f.out.decode())")" "'	cmd"

# Text materials and drafts
check "material solo texto como borrador" "$(req prof -d '{"project_id":"incentiva","title":"Desafío nuevo","category":"Desafío · Seguimiento","summary":"S","content":"## Problema\nTexto\n- punto","status":"draft"}' $B/api/admin/resources)" "Borrador guardado.*\[201\]"
check "borrador oculto a estudiantes" "$(req ana "$B/api/resources?project=incentiva" | grep -c 'Desafío nuevo')" "^0$"
check "material sin texto ni archivo" "$(req prof -d '{"project_id":"incentiva","title":"x","category":"x","summary":"x"}' $B/api/admin/resources)" "\[400\]"
python3 "$APP/server.py" borradores-desafios > "$S/drafts.txt"
check "carga de los 6 borradores" "$(cat $S/drafts.txt)" "^6 borradores"
check "borradores con categoría de desafío" "$(sqlite3 $S/repo.sqlite3 "select count(*) from resources where category like 'Desafío ·%' and status='draft'")" "^7$"

# Removed admin loses the role without signing in again
login jefa
kill $PID; wait $PID 2>/dev/null
PUCV_ADMIN_EMAILS=admin@mail.pucv.cl start
check "admin quitado pierde el rol" "$(req jefa $B/api/me)" '"role": "student"'

# Cohort closure deletes evidence of work without showcase consent
req admin -d '{"confirm":"CERRAR COHORTE"}' $B/api/admin/cohort/close > /dev/null
check "cierre borra fichas sin autorización de vitrina" "$(ls $S/files | wc -l | tr -d ' ')" "^0$"
kill $PID; wait $PID 2>/dev/null
grep -i "traceback" -A6 "$S/server.log" | head -20
