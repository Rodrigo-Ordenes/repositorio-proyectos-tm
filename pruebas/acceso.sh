#!/bin/bash
# Sign-in and course access: personal codes, course codes, roles, returned deliveries and revocation.
set -u +B
S="${PRUEBAS_TMP:-$(mktemp -d)}/acceso"
APP="$(cd "$(dirname "$0")/.." && pwd)"
rm -rf "$S"; mkdir -p "$S"
export APP_DB_PATH=$S/repo.sqlite3 APP_UPLOAD_DIR=$S/files APP_BACKUP_DIR=$S/backups APP_DEMO_AUTH=1 PORT=8766 \
  PUCV_ADMIN_EMAILS=profe.innova@pucv.cl
B=http://localhost:8766
J=(-H "Content-Type: application/json")
check() { if echo "$2" | grep -q -- "$3"; then echo "OK   $1"; else echo "FAIL $1 -> $(echo "$2" | head -c 300)"; fi; }
login() { curl -s -c "$S/$1.jar" "${J[@]}" -d "{\"email\":\"$1\"}" $B/auth/demo -o /dev/null; }
req() { local who=$1; shift; curl -s -b "$S/$who.jar" "${J[@]}" -w ' [%{http_code}]\n' "$@"; }
val() { python3 -c "import sys,json;d=json.loads(sys.stdin.read().rsplit(' [',1)[0]);print(eval(sys.argv[1]))" "$1"; }

cd "$APP"
CODE=$(python3 server.py codigo ana.perez@mail.pucv.cl innova 5 | grep -oE '[A-Z0-9]{4}-[A-Z0-9]{4}')
python3 server.py > "$S/server.log" 2>&1 & PID=$!; sleep 1.2

check "código erróneo" "$(curl -s "${J[@]}" -w ' [%{http_code}]' -d '{"email":"ana.perez@mail.pucv.cl","code":"AAAA-BBBB"}' $B/auth/code)" "no coinciden.*\[400\]"
LOWER=$(echo "$CODE" | tr -d - | tr A-Z a-z)
check "código en minúsculas y sin guion" "$(curl -s "${J[@]}" -c $S/ana.jar -o /dev/null -w '%{http_code}' -d "{\"email\":\"Ana.Perez@mail.pucv.cl\",\"code\":\"$LOWER\"}" $B/auth/code)" "^302$"
check "el código da acceso a su asignatura" "$(req ana $B/api/me)" '"active_projects": \["innova"\]'
login profe.innova@pucv.cl; login bea@mail.pucv.cl; login cami@mail.pucv.cl
cp $S/profe.innova@pucv.cl.jar $S/adm.jar; cp $S/bea@mail.pucv.cl.jar $S/bea.jar; cp $S/cami@mail.pucv.cl.jar $S/cami.jar
JC=$(req adm -d '{"project_id":"innova","label":"Paralelo 1","days":7,"max_uses":1}' $B/api/admin/join-codes | val "d['code']")
check "código del curso" "$(req bea -d "{\"code\":\"$JC\"}" $B/api/join)" "ya tienes acceso.*\[200\]"
check "máximo de usos" "$(req cami -d "{\"code\":\"$JC\"}" $B/api/join)" "\[400\]"
check "códigos personales filtran correos no PUCV" "$(req adm -d '{"project_id":"innova","emails":"x@mail.pucv.cl, y@gmail.com\nZ@PUCV.CL","days":10}' $B/api/admin/access-codes)" '"invalid": \["y@gmail.com"\]'
check "estudiante no administra" "$(req bea -d '{"project_id":"innova"}' $B/api/admin/join-codes)" "\[403\]"

SUB='{"project_id":"innova","team_name":"Equipo HBB","title":"Cápsula","summary":"r","video_url":"https://example.com/v.mp4","evidence_url":"https://example.com/f","consent_confirmed":true,"video_length_confirmed":true,"members":"Bea","project_fields":{"alteration":"HBB","process":"Traducción","effect":"x","phenotype":"x","technique":"PCR","controls":"x"}}'
check "entrega" "$(req bea -d "$SUB" $B/api/submissions)" "\[201\]"
check "una entrega abierta por equipo" "$(req bea -d "$SUB" $B/api/submissions)" "\[409\]"
SID=$(req adm $B/api/admin/pending | val "d['submissions'][0]['id']")
req adm -d "{\"kind\":\"submission\",\"id\":$SID,\"decision\":\"reject\",\"note\":\"Falta subtitular\"}" $B/api/admin/review > /dev/null
check "el equipo ve la devolución y el comentario" "$(req bea "$B/api/my-submissions?project=innova")" '"status": "rejected", "review_note": "Falta subtitular"'
check "reenvío tras la devolución" "$(req bea -d "$SUB" $B/api/submissions)" "\[201\]"

MID=$(req adm $B/api/admin/members | val "[m['id'] for m in d if m['email'].startswith('ana')][0]")
req adm -d "{\"kind\":\"membership\",\"id\":$MID,\"decision\":\"revoke\"}" $B/api/admin/review > /dev/null
check "retirar acceso anula su código" "$(curl -s "${J[@]}" -o /dev/null -w '%{http_code}' -d "{\"email\":\"ana.perez@mail.pucv.cl\",\"code\":\"$CODE\"}" $B/auth/code)" "^400$"
for i in 1 2 3 4 5 6; do curl -s -o /dev/null "${J[@]}" -d '{"email":"intento@mail.pucv.cl","code":"AAAA-BBBB"}' $B/auth/code; done
check "bloqueo tras 6 intentos fallidos" "$(curl -s -o /dev/null -w '%{http_code}' "${J[@]}" -d '{"email":"intento@mail.pucv.cl","code":"AAAA-BBBB"}' $B/auth/code)" "^429$"
kill $PID; wait $PID 2>/dev/null
grep -i traceback -A5 "$S/server.log" | head
