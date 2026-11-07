#!/bin/bash
# Generated evidence sheet, alternatives, 3D model, pre-session questions with doubt grouping, tracking,
# end-of-project report, projection mode, cohorts and the emergency (SOS) code.
set -u +B
S="${PRUEBAS_TMP:-$(mktemp -d)}/mejoras"
APP="$(cd "$(dirname "$0")/.." && pwd)"
rm -rf "$S"; mkdir -p "$S"
export APP_DB_PATH=$S/repo.sqlite3 APP_UPLOAD_DIR=$S/files APP_BACKUP_DIR=$S/backups APP_DEMO_AUTH=1 PORT=8766 APP_BACKUP_HOURS=0 \
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
for u in admin prof inn ana luis bea cata dani; do login $u; done
IC=$(req prof -d '{"project_id":"incentiva","section":"Bioanálisis","days":7}' $B/api/admin/join-codes | val "d['code']")
NC=$(req inn -d '{"project_id":"innova","days":7}' $B/api/admin/join-codes | val "d['code']")
for u in ana luis bea; do req $u -d "{\"code\":\"$IC\"}" $B/api/join > /dev/null; done
for u in cata dani; do req $u -d "{\"code\":\"$NC\"}" $B/api/join > /dev/null; done
check "la cohorte actual se informa en /api/me" "$(req ana $B/api/me)" '"cohort": "2026-2"'

base='"project_id":"incentiva","section":"Bioanálisis","summary":"S","video_url":"https://youtu.be/dQw4w9WgXcQ","video_length_confirmed":true,"consent_confirmed":true,"project_fields":{"challenge":"Seguimiento","research_question":"¿P?","evidence":"a; b; c","community":"C","solution":"So","indicator":"I","limitations":"L"}'
# Alternatives
check "alternativa con porcentaje fuera de rango" "$(req ana -d "{$base,\"team_name\":\"E1\",\"title\":\"T\",\"members\":\"Ana\",\"alternatives\":{\"items\":[{\"name\":\"A\",\"scores\":[10,20,30,140,10,10,10]}]}}" $B/api/submissions)" "de 0 a 100 %.*\[400\]"
check "entrega sin ficha adjunta (se genera)" "$(req ana -d "{$base,\"team_name\":\"E1\",\"title\":\"Con alternativas\",\"members\":\"Ana\nLuis luis@mail.pucv.cl\",\"alternatives\":{\"items\":[{\"name\":\"A\",\"scores\":[100,90,80,100,90,80,100]},{\"name\":\"B\",\"scores\":[10,20,10,20,10,20,10]}],\"chosen\":0}}" $B/api/submissions)" '"id": .*ficha de evidencia generada.*\[201\]'
SID=$(req ana "$B/api/my-submissions?project=incentiva" | val "d[0]['id']")
ficha=$(req ana $B/api/submissions/$SID/ficha)
check "ficha generada con campos" "$ficha" '"label": "Pregunta de investigación", "value": "¿P?"'
check "ficha con porcentaje por criterio y promedio" "$ficha" '"scores": \[100, 90, 80, 100, 90, 80, 100\], "average": 91.*"average": 14.*"chosen": 0'
check "las alternativas declaran su escala en porcentaje" "$ficha" '"scale": "percent"'
js_alt=$(cat static/app.js)
check "el formulario puntúa cada criterio de 0 a 100 %" "$js_alt" 'Puntúen cada criterio de 0 a 100 %'
check "la tabla muestra el porcentaje de cada criterio" "$js_alt" 'alternativeCell('
check "el formulario calcula el promedio mientras se puntúa" "$js_alt" "function updateAlternativeAverages("
check "las comparaciones antiguas en 1–3 se siguen mostrando" "$js_alt" "alt.scale!=='percent'"
check "integrante por correo ve la ficha" "$(req luis $B/api/submissions/$SID/ficha)" "\[200\]"
check "otro estudiante no la ve antes de publicar" "$(req bea $B/api/submissions/$SID/ficha)" "\[403\]"
check "otra asignatura no la ve" "$(req cata $B/api/submissions/$SID/ficha)" "\[403\]"
req prof -d "{\"kind\":\"submission\",\"id\":$SID,\"decision\":\"publish\"}" $B/api/admin/review > /dev/null
check "publicada: el curso ve la ficha" "$(req bea $B/api/submissions/$SID/ficha)" "\[200\]"
check "catálogo con alternativas y cohorte" "$(req bea "$B/api/resources?project=incentiva")" '"cohort": "2026-2".*"chosen": 0'

# 3D model
inn='"project_id":"innova","summary":"S","video_url":"https://youtu.be/dQw4w9WgXcQ","video_length_confirmed":true,"consent_confirmed":true,"members":"Cata","project_fields":{"alteration":"HBB","process":"Traducción","effect":"x","phenotype":"x","technique":"PCR","controls":"x"}'
BAD=$(printf 'no es un modelo' | base64)
check "STL inválido" "$(req cata -d "{$inn,\"team_name\":\"N1\",\"title\":\"Mal\",\"model_file_base64\":\"$BAD\",\"model_filename\":\"m.stl\"}" $B/api/submissions)" "STL válido.*\[400\]"
STL=$(python3 -c "
import struct,base64
tri=[(0,0,0),(1,0,0),(0,1,0)]
data=b'x'*80+struct.pack('<I',1)+struct.pack('<3f',0,0,1)+b''.join(struct.pack('<3f',*v) for v in tri)+b'\0\0'
print(base64.b64encode(data).decode())")
check "STL válido" "$(req cata -d "{$inn,\"team_name\":\"N1\",\"title\":\"Con modelo\",\"model_file_base64\":\"$STL\",\"model_filename\":\"modelo.stl\"}" $B/api/submissions)" "\[201\]"
MID=$(req cata "$B/api/my-submissions?project=innova" | val "d[0]['id']")
check "el equipo descarga su modelo" "$(curl -s -b $S/cata.jar -o /dev/null -w '%{http_code} %{content_type}' $B/api/submissions/$MID/model)" "200 model/stl"
check "el modelo no se ve antes de publicar" "$(req dani $B/api/submissions/$MID/model)" "\[403\]"
req inn -d "{\"kind\":\"submission\",\"id\":$MID,\"decision\":\"publish\"}" $B/api/admin/review > /dev/null
check "catálogo marca el modelo 3D" "$(req dani "$B/api/resources?project=innova")" '"has_model": 1'

# Pre-session questions and doubt grouping
pre=$(req inn -d '{"project_id":"innova","title":"Antes del 9","kind":"previa"}' $B/api/admin/tickets)
PCODE=$(echo "$pre" | val "d['code']"); PID2=$(req inn $B/api/admin/tickets | val "d[0]['id']")
check "preguntas previas por defecto" "$(req cata $B/api/tickets/$PCODE)" '"kind": "previa".*todavía no entiendes'
check "el estudiante ve el tipo" "$(req cata "$B/api/my-tickets?project=innova")" '"kind": "previa"'
req cata -d '{"answers":["la metilación del promotor","PCR","¿controles?"]}' $B/api/tickets/$PCODE/answer > /dev/null
req dani -d '{"answers":["no entiendo la metilación","Southern","¿cómo leerlo?"]}' $B/api/tickets/$PCODE/answer > /dev/null
resp=$(req inn $B/api/admin/tickets/$PID2/responses)
check "palabras frecuentes" "$resp" '"word": "metilación", "count": 2'
AID=$(echo "$resp" | val "d['answers'][0]['id']"); AID2=$(echo "$resp" | val "d['answers'][1]['id']")
check "categoría con pregunta inválida" "$(req inn -d "{\"answer_id\":\"$AID\",\"question\":9,\"tag\":\"x\"}" $B/api/admin/tickets/$PID2/tag)" "\[400\]"
check "docente de otra asignatura no categoriza" "$(req prof -d "{\"answer_id\":\"$AID\",\"question\":0,\"tag\":\"x\"}" $B/api/admin/tickets/$PID2/tag)" "\[403\]"
req inn -d "{\"answer_id\":\"$AID\",\"question\":0,\"tag\":\"Metilación\"}" $B/api/admin/tickets/$PID2/tag > /dev/null
req inn -d "{\"answer_id\":\"$AID2\",\"question\":0,\"tag\":\"Metilación\"}" $B/api/admin/tickets/$PID2/tag > /dev/null
check "duda dominante" "$(req inn $B/api/admin/tickets/$PID2/responses)" '"dominant": "Metilación"'
check "CSV con categorías" "$(curl -s -b $S/inn.jar $B/api/admin/tickets/$PID2/responses.csv | head -2)" "categoría 1"
req inn -d "{\"answer_id\":\"$AID2\",\"question\":0,\"tag\":\"\"}" $B/api/admin/tickets/$PID2/tag > /dev/null
check "borrar una categoría" "$(req inn $B/api/admin/tickets/$PID2/responses)" '"tags": \[{"tag": "Metilación", "count": 1}\]'

# Tracking, report and projection
track=$(req prof "$B/api/admin/tracking?project=incentiva")
check "seguimiento por paralelo" "$track" '"section": "Bioanálisis", "members": 3, "linked": 2, "teams": 1, "published": 1'
check "persona sin entrega asociada" "$(echo "$track" | val "[p['email'] for p in d['people'] if not p['status']]")" "bea@mail.pucv.cl"
check "seguimiento de otra asignatura" "$(req prof "$B/api/admin/tracking?project=innova")" "\[403\]"
check "informe con indicadores y series" "$(req inn "$B/api/admin/report?project=innova")" '"statuses": {"published": 1}.*"doubts": \[{"tag": "Metilación", "n": 1}\]'
check "proyección lista los publicados" "$(req prof "$B/api/admin/projection?project=incentiva&section=Bioan%C3%A1lisis")" '"path": "/incentiva/recurso/con-alternativas"'
check "QR de un trabajo" "$(curl -s -b $S/prof.jar -o /dev/null -w '%{http_code} %{content_type}' "$B/api/admin/qr.svg?path=/incentiva/recurso/con-alternativas")" "200 image/svg+xml"
check "QR solo para páginas del sitio" "$(req prof "$B/api/admin/qr.svg?path=https://evil.example")" "\[400\]"
check "estudiante no usa el modo proyección" "$(req ana "$B/api/admin/projection?project=incentiva")" "\[403\]"

# Cohorts
check "solo administración abre cohortes" "$(req prof -d '{"name":"2027-1"}' $B/api/admin/cohorts)" "\[403\]"
check "nombre de cohorte inválido" "$(req admin -d '{"name":"<x>"}' $B/api/admin/cohorts)" "\[400\]"
check "abrir cohorte 2027-1" "$(req admin -d '{"name":"2027-1"}' $B/api/admin/cohorts)" "\[201\]"
check "cohorte duplicada" "$(req admin -d '{"name":"2027-1"}' $B/api/admin/cohorts)" "\[409\]"
check "la nueva cohorte es la actual" "$(req prof $B/api/admin/cohorts)" '"current": "2027-1"'
check "códigos del curso anteriores desactivados" "$(req ana -d "{\"code\":\"$IC\"}" $B/api/join)" "\[400\]"
check "mismo nombre de equipo en la nueva cohorte" "$(req ana -d "{$base,\"team_name\":\"E1\",\"title\":\"Segunda cohorte\",\"members\":\"Ana\"}" $B/api/submissions)" "\[201\]"
check "indicadores de la nueva cohorte" "$(req prof "$B/api/admin/indicators?project=incentiva")" '"Entregas publicadas", "value": 0'
check "indicadores de la cohorte archivada" "$(req prof "$B/api/admin/indicators?project=incentiva&cohort=2026-2")" '"Entregas publicadas", "value": 1'
check "lo archivado sigue en el catálogo" "$(req bea "$B/api/resources?project=incentiva")" "Con alternativas"

# Course (or phase) code + institutional address, without Google or a personal code
cc() { curl -s -c "$S/$1.cc" "${J[@]}" -w ' [%{http_code}]' -d "{\"email\":\"$1@$3\",\"code\":\"$2\"}" $B/auth/code; }
OC=$(req prof -d '{"project_id":"incentiva","section":"Oftalmología","label":"Semestre","days":30}' $B/api/admin/join-codes | val "d['code']")
check "estudiante nueva entra con código del curso" "$(cc nueva "$OC" mail.pucv.cl)" "\[302\]"
check "queda en la asignatura y su paralelo" "$(curl -s -b "$S/nueva.cc" $B/api/me)" '"active_projects": \["incentiva"\].*Oftalmolog'
check "correo no institucional con código del curso" "$(cc ajena "$OC" gmail.com)" "\[400\]"
check "docente no entra con código del curso" "$(cc prof "$OC" mail.pucv.cl)" "cuentas docentes.*\[403\]"
check "administración no entra con código del curso" "$(cc admin "$OC" mail.pucv.cl)" "\[403\]"
RC=$(req inn -d '{"project_id":"innova","days":30,"roster":"Eva@mail.pucv.cl; x@gmail.com\ngus@mail.pucv.cl"}' $B/api/admin/join-codes)
check "código con lista del curso" "$RC" '"roster_size": 2'
RC=$(echo "$RC" | val "d['code']")
check "correo de la lista entra" "$(cc eva "$RC" mail.pucv.cl)" "\[302\]"
check "correo fuera de la lista no entra" "$(cc fede "$RC" mail.pucv.cl)" "no está en la lista.*\[403\]"
check "unirse con sesión respeta la lista" "$(req bea -d "{\"code\":\"$RC\"}" $B/api/join)" "\[400\]"
check "la lista muestra cuántos correos" "$(req inn $B/api/admin/join-codes)" '"roster_size": 2'
nocheck "la lista no expone los correos" "$(req inn $B/api/admin/join-codes)" "gus@mail.pucv.cl"
list=$(req prof $B/api/admin/join-codes)
check "los usos se cuentan" "$list" '"uses": 1'
req prof -d "{\"id\":$(echo "$list" | val "[c['id'] for c in d if c['label']=='Semestre'][0]")}" $B/api/admin/join-codes/disable > /dev/null
check "código desactivado ya no permite entrar" "$(cc otra "$OC" mail.pucv.cl)" "\[400\]"

# Drive sharing check (only drive.google.com is ever asked; other links are not fetched)
check "revisión de video sin sesión" "$(curl -s -w ' [%{http_code}]' "$B/api/video-check?url=x")" "\[401\]"
check "revisión de video ajeno a Drive" "$(req ana "$B/api/video-check?url=https%3A%2F%2Fexample.com%2Ffile%2Fd%2F1234567890abc")" '"status": "unknown"'

# Pages
for page in /ficha/1 /informe/innova /proyeccion/incentiva; do check "página $page" "$(curl -s -o /dev/null -w '%{http_code}' $B$page)" "200"; done
kill $PID; wait $PID 2>/dev/null

# Emergency (SOS) code: any domain, always admin, never stored in the repository
rm -rf "$S/sos"; mkdir -p "$S/sos"
SOSOUT=$(APP_DB_PATH=$S/sos/repo.sqlite3 python3 server.py codigo-sos Rescate@Gmail.com)
SOSCODE=$(echo "$SOSOUT" | sed -n 's/^Código SOS para [^:]*: //p')
check "el código SOS se genera" "$SOSCODE" '^[A-Z0-9]\{4\}-[A-Z0-9]\{4\}-[A-Z0-9]\{4\}-[A-Z0-9]\{4\}$'
nocheck "el archivo guarda el hash, no el código" "$(cat $S/sos/sos.txt)" "$SOSCODE"
APP_DB_PATH=$S/sos/repo.sqlite3 APP_UPLOAD_DIR=$S/sos/files APP_DEMO_AUTH=0 PUCV_ADMIN_EMAILS= python3 server.py > "$S/sos.log" 2>&1 & PID=$!; sleep 1.2
sos() { curl -s -c "$S/sos.jar" "${J[@]}" -w ' [%{http_code}]' -d "{\"email\":\"$1\",\"code\":\"$2\"}" $B/auth/code; }
check "SOS con código equivocado" "$(sos rescate@gmail.com AAAA-BBBB-CCCC-DDDD)" "\[400\]"
check "SOS con otro correo" "$(sos otro@gmail.com "$SOSCODE")" "\[400\]"
check "SOS correcto entra" "$(sos rescate@gmail.com "$SOSCODE")" "\[302\]"
check "SOS entra como administración" "$(curl -s -b "$S/sos.jar" $B/api/me)" '"role": "admin"'
check "el ingreso SOS queda registrado" "$(cat $S/sos.log)" "Ingreso con código SOS: rescate@gmail.com"
kill $PID; wait $PID 2>/dev/null
check "ningún archivo SOS en el repositorio" "$(git ls-files | grep -c 'sos.txt')" "^0$"

grep -i traceback -A6 "$S/server.log" "$S/sos.log" | head -20
