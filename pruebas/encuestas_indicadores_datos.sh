#!/bin/bash
# End-to-end checks for P3: staff roles, KPSI/perception surveys, indicators, data requests, cohort closure, seeds.
set -u +B
S="${PRUEBAS_TMP:-$(mktemp -d)}/p3"
APP="$(cd "$(dirname "$0")/.." && pwd)"
rm -rf "$S"; mkdir -p "$S"
export APP_DB_PATH=$S/repo.sqlite3 APP_UPLOAD_DIR=$S/files APP_BACKUP_DIR=$S/backups APP_DEMO_AUTH=1 PORT=8766 \
  PUCV_ADMIN_EMAILS=admin@mail.pucv.cl PUCV_INCENTIVA_ADMINS=prof@mail.pucv.cl PUCV_INCENTIVA_DEADLINE=2099-12-31 \
  APP_CASES_DIR=/nonexistent
B=http://localhost:8766
J=(-H "Content-Type: application/json")
check() { if echo "$2" | grep -q -- "$3"; then echo "OK   $1"; else echo "FAIL $1 -> $(echo "$2" | head -c 400)"; fi; }
nocheck() { if echo "$2" | grep -q -- "$3"; then echo "FAIL $1 -> $(echo "$2" | head -c 400)"; else echo "OK   $1"; fi; }
login() { curl -s -c "$S/$1.jar" "${J[@]}" -d "{\"email\":\"$1@mail.pucv.cl\"}" $B/auth/demo -o /dev/null; }
req() { local who=$1; shift; curl -s -b "$S/$who.jar" "${J[@]}" -w ' [%{http_code}]\n' "$@"; }
val() { python3 -c "import sys,json;d=json.loads(sys.stdin.read().rsplit(' [',1)[0]);print(eval(sys.argv[1]))" "$1"; }

cd "$APP"
python3 "$APP/server.py" > "$S/server.log" 2>&1 & PID=$!; sleep 1.2
check "casos desde seeds/ sin la carpeta del curso" "$(sqlite3 $S/repo.sqlite3 "select min(length(content)) from resources where project_id='innova'")" "^[0-9]\{4\}$"
for u in admin prof prof2 ana luis bea; do login $u; done

# Staff roles
check "editor no gestiona el equipo docente" "$(req prof -d '{"email":"prof2@mail.pucv.cl","project_id":"innova"}' $B/api/admin/staff)" "\[403\]"
check "correo no PUCV rechazado" "$(req admin -d '{"email":"x@gmail.com","project_id":"innova"}' $B/api/admin/staff)" "\[400\]"
check "asignar docente desde el panel" "$(req admin -d '{"email":"prof2@mail.pucv.cl","project_id":"innova"}' $B/api/admin/staff)" "\[201\]"
check "rige sin volver a iniciar sesión" "$(req prof2 $B/api/me)" '"role": "editor".*"managed_projects": \["innova"\]'
check "nuevo docente revisa su asignatura" "$(req prof2 $B/api/admin/pending)" "\[200\]"
check "lista del equipo docente" "$(req admin $B/api/admin/staff)" '"configured": \[{"email": "prof@mail.pucv.cl"'
req admin -d '{"email":"prof2@mail.pucv.cl","project_id":"innova","action":"remove"}' $B/api/admin/staff > /dev/null
check "quitar el rol" "$(req prof2 $B/api/admin/pending)" "\[403\]"

# Course activity to measure
C=$(req prof -d '{"project_id":"incentiva","section":"Bioanálisis","days":7}' $B/api/admin/join-codes | val "d['code']")
for u in ana luis bea; do req $u -d "{\"code\":\"$C\"}" $B/api/join > /dev/null; done
base='"project_id":"incentiva","section":"Bioanálisis","summary":"S","evidence_url":"https://example.org/f","video_url":"https://youtu.be/dQw4w9WgXcQ","video_length_confirmed":true,"consent_confirmed":true,"project_fields":{"challenge":"Seguimiento","research_question":"¿Mejora el acceso?","evidence":"Fuente 1; fuente 2; fuente 3","solution":"Propuesta de prueba","community":"C","indicator":"I","limitations":"L"}'
req ana -d "{$base,\"team_name\":\"Equipo 1\",\"title\":\"Vitrina sí\",\"members\":\"Ana Demo ana@mail.pucv.cl\nLuis Demo luis@mail.pucv.cl\",\"has_subtitles\":true,\"showcase_consent\":true,\"ai_declaration\":\"Canva\"}" $B/api/submissions > /dev/null
req bea -d "{$base,\"team_name\":\"Equipo 2\",\"title\":\"Vitrina no\",\"members\":\"Bea\"}" $B/api/submissions > /dev/null
for id in $(req prof $B/api/admin/pending | val "' '.join(str(x['id']) for x in d['submissions'])"); do req prof -d "{\"kind\":\"submission\",\"id\":$id,\"decision\":\"publish\"}" $B/api/admin/review > /dev/null; done
SLUG=$(req bea "$B/api/resources?project=incentiva" | val "[r['slug'] for r in d if r['title']=='Vitrina sí'][0]")
RID=$(req bea "$B/api/resources?project=incentiva" | val "[r['id'] for r in d if r['title']=='Vitrina sí'][0]")
req ana -d "{\"project_id\":\"incentiva\",\"slug\":\"$SLUG\",\"body\":\"Pregunta de Ana\"}" $B/api/comments > /dev/null
req bea -d '{"scores":{"territory":4,"evidence":3,"feasibility":3,"ethics":3,"communication":4},"strength":"a","suggestion":"b"}' $B/api/peer/$RID > /dev/null

# Surveys
check "tipo inválido" "$(req prof -d '{"project_id":"incentiva","kind":"otro","moment":"entrada"}' $B/api/admin/surveys)" "\[400\]"
check "KPSI de entrada con plantilla" "$(req prof -d '{"project_id":"incentiva","kind":"kpsi","moment":"entrada","title":"KPSI entrada"}' $B/api/admin/surveys)" "/encuesta/.*\[201\]"
IN=$(req prof $B/api/admin/surveys | val "d[0]['code']")
check "la plantilla trae 7 enunciados y 4 niveles" "$(req ana $B/api/surveys/$IN | val "(len(d['items']),len(d['scale']))")" "(7, 4)"
check "valores fuera de escala" "$(req ana -d '{"values":[1,2,3,4,5,1,1]}' $B/api/surveys/$IN/answer)" "\[400\]"
req ana -d '{"values":[1,1,2,2,1,1,2]}' $B/api/surveys/$IN/answer > /dev/null
req bea -d '{"values":[2,1,2,1,1,2,2],"comment":"Me cuesta el indicador"}' $B/api/surveys/$IN/answer > /dev/null
check "una respuesta por persona" "$(req ana -d '{"values":[1,1,1,1,1,1,1]}' $B/api/surveys/$IN/answer)" "\[409\]"
check "KPSI de salida" "$(req prof -d '{"project_id":"incentiva","kind":"kpsi","moment":"salida","title":"KPSI salida"}' $B/api/admin/surveys)" "\[201\]"
OUT=$(req prof $B/api/admin/surveys | val "d[0]['code']"); OUTID=$(req prof $B/api/admin/surveys | val "d[0]['id']")
req ana -d '{"values":[4,3,3,3,4,3,4]}' $B/api/surveys/$OUT/answer > /dev/null
req bea -d '{"values":[3,3,3,4,3,3,4]}' $B/api/surveys/$OUT/answer > /dev/null
res=$(req prof $B/api/admin/surveys/$OUTID/results)
check "comparación entrada/salida por enunciado" "$res" '"mean": 3.5, "top_share": 1.0.*"baseline_mean": 1.5, "delta": 2.0'
check "resultados indican la encuesta base" "$res" '"baseline": {"title": "KPSI entrada", "respondents": 2}'
check "CSV de encuesta" "$(curl -s -b $S/prof.jar $B/api/admin/surveys/$OUTID/responses.csv | head -2)" "respuesta,Formulo una pregunta"
check "QR de encuesta" "$(curl -s -b $S/prof.jar -o /dev/null -w '%{content_type}' $B/api/admin/surveys/$OUTID/qr.svg)" "image/svg+xml"
check "encuesta en la lista del estudiante" "$(req luis "$B/api/my-surveys?project=incentiva")" '"answered": false, "open": true'
check "percepción usa escala de acuerdo" "$(req prof -d '{"project_id":"incentiva","kind":"percepcion","moment":"cierre"}' $B/api/admin/surveys)" "\[201\]"
check "plantilla de percepción" "$(req luis $B/api/surveys/$(req prof $B/api/admin/surveys | val "d[0]['code']"))" '"scale": \["Muy en desacuerdo"'
check "respuestas sin persona" "$(sqlite3 $S/repo.sqlite3 'PRAGMA table_info(survey_answers)' | grep -c user)" "^0$"
check "página de encuesta" "$(curl -s -o /dev/null -w '%{http_code}' $B/encuesta/$OUT)" "200"

# Indicators
ind=$(req prof "$B/api/admin/indicators?project=incentiva")
check "indicadores: equipos y plazo" "$ind" '"Equipos con entrega", "value": 2.*Equipos que entregaron hasta el 2099-12-31", "value": "2 (100%)"'
check "indicadores: subtítulos e IA" "$ind" '"Videos con subtítulos declarados", "value": "1 de 2 (50%)".*"Entregas con declaración de IA", "value": "1 de 2 (50%)"'
check "indicadores: encuestas y coevaluación" "$ind" '"Evaluaciones entre pares", "value": 1.*"Encuestas aplicadas (KPSI y percepción)", "value": 3'
check "indicadores por paralelo" "$ind" "Equipos con entrega · Bioanálisis"
check "indicadores CSV" "$(curl -s -b $S/prof.jar "$B/api/admin/indicators.csv?project=incentiva" | sed -n 2p)" "Participación,Estudiantes con acceso,3"
check "editor no ve otra asignatura" "$(req prof "$B/api/admin/indicators?project=innova")" "\[403\]"

# Right of access and erasure
check "solo admin exporta datos" "$(req prof "$B/api/admin/person?email=ana@mail.pucv.cl")" "\[403\]"
check "exportar datos de una persona" "$(req admin "$B/api/admin/person?email=ana@mail.pucv.cl" | python3 -c "import sys,json;d=json.loads(sys.stdin.read().rsplit(' [',1)[0]);print(d['entregas'][0]['title'],d['comentarios'][0]['body'])")" "Vitrina sí Pregunta de Ana"
check "confirmación obligatoria" "$(req admin -d '{"email":"ana@mail.pucv.cl","confirm":"otra@mail.pucv.cl"}' $B/api/admin/person/delete)" "\[400\]"
check "eliminar datos de una persona" "$(req admin -d '{"email":"ana@mail.pucv.cl","confirm":"ana@mail.pucv.cl"}' $B/api/admin/person/delete)" "\[200\]"
check "su sesión ya no vale" "$(req ana $B/api/me)" '"user": null'
check "su nombre sale del trabajo publicado" "$(sqlite3 $S/repo.sqlite3 "select members,member_emails from submissions where team_name='Equipo 1'")" '^\["Luis Demo"\]|\["luis@mail.pucv.cl"\]$'
check "el trabajo del equipo sigue publicado" "$(req bea "$B/api/resources?project=incentiva")" "Vitrina sí"
check "su comentario se borró" "$(sqlite3 $S/repo.sqlite3 "select count(*) from comments")" "^0$"
check "respuestas anónimas se conservan" "$(sqlite3 $S/repo.sqlite3 "select count(*) from survey_answers")" "^4$"

# Cohort closure
check "cierre requiere frase" "$(req admin -d '{"confirm":"si"}' $B/api/admin/cohort/close)" "\[400\]"
check "cerrar cohorte" "$(req admin -d '{"confirm":"CERRAR COHORTE"}' $B/api/admin/cohort/close)" "anonimizadas.*antes-del-cierre"
check "respaldo previo creado" "$(ls $S/backups)" "antes-del-cierre-.*zip"
check "estudiantes anonimizados" "$(sqlite3 $S/repo.sqlite3 "select count(*) from users where email like '%@mail.pucv.cl'")" "^2$"
check "docentes conservan su cuenta" "$(sqlite3 $S/repo.sqlite3 "select group_concat(email) from users where email like '%@mail.pucv.cl'")" "admin.*prof"
check "trabajo con vitrina sigue publicado" "$(sqlite3 $S/repo.sqlite3 "select r.status from resources r join submissions s on s.id=r.source_submission_id where s.showcase_consent=1")" "^published$"
check "trabajo sin vitrina retirado" "$(sqlite3 $S/repo.sqlite3 "select r.status from resources r join submissions s on s.id=r.source_submission_id where s.showcase_consent=0")" "^draft$"
check "sin nombres de integrantes" "$(sqlite3 $S/repo.sqlite3 "select distinct members from submissions")" '^\[\]$'
check "códigos del curso desactivados" "$(sqlite3 $S/repo.sqlite3 "select max(active) from join_codes")" "^0$"
kill $PID; wait $PID 2>/dev/null
grep -i "traceback" -A6 "$S/server.log" | head -20
