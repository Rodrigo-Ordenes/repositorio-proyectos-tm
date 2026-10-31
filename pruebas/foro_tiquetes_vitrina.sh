#!/bin/bash
# End-to-end checks for P2: embedded video, forum threads, control questions, showcase, exit tickets, peer review.
set -u +B
S="${PRUEBAS_TMP:-$(mktemp -d)}/p2"
APP="$(cd "$(dirname "$0")/.." && pwd)"
rm -rf "$S"; mkdir -p "$S"
export APP_DB_PATH=$S/repo.sqlite3 APP_UPLOAD_DIR=$S/files APP_BACKUP_DIR=$S/backups APP_DEMO_AUTH=1 PORT=8766 \
  PUCV_ADMIN_EMAILS=admin@mail.pucv.cl PUCV_INCENTIVA_ADMINS=prof@mail.pucv.cl PUCV_OPEN_PROJECTS=incentiva
B=http://localhost:8766
J=(-H "Content-Type: application/json")
check() { if echo "$2" | grep -q -- "$3"; then echo "OK   $1"; else echo "FAIL $1 -> $(echo "$2" | head -c 400)"; fi; }
nocheck() { if echo "$2" | grep -q -- "$3"; then echo "FAIL $1 -> $(echo "$2" | head -c 400)"; else echo "OK   $1"; fi; }
login() { curl -s -c "$S/$1.jar" "${J[@]}" -d "{\"email\":\"$1@mail.pucv.cl\"}" $B/auth/demo -o /dev/null; }
req() { local who=$1; shift; curl -s -b "$S/$who.jar" "${J[@]}" -w ' [%{http_code}]\n' "$@"; }
val() { python3 -c "import sys,json;d=json.loads(sys.stdin.read().rsplit(' [',1)[0]);print(eval(sys.argv[1]))" "$1"; }

cd "$APP"
check "unidad: enlaces de video" "$(python3 -c "
import server as s
cases={'https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=3':'nocookie.com/embed/dQw4w9WgXcQ','https://youtu.be/dQw4w9WgXcQ':'embed/dQw4w9WgXcQ',
 'https://m.youtube.com/shorts/dQw4w9WgXcQ':'embed/dQw4w9WgXcQ','https://drive.google.com/file/d/1AbCdEfGhIjKlMn/view?usp=sharing':'file/d/1AbCdEfGhIjKlMn/preview',
 'http://youtu.be/dQw4w9WgXcQ':'', 'https://evil.com/watch?v=dQw4w9WgXcQ':'', 'https://youtube.com/watch?v=bad\"id':''}
print(all((exp in s.video_embed_url(u)) if exp else s.video_embed_url(u)=='' for u,exp in cases.items()))")" "True"
check "unidad: integrantes con correo" "$(python3 -c "
import server as s
print(s.clean_members('Ana Pérez ana.perez@mail.pucv.cl\nLuis Soto <luis@pucv.cl>\nx@gmail.com\n\nana pérez'))")" "(\['Ana Pérez', 'Luis Soto', 'X'\], \['ana.perez@mail.pucv.cl', 'luis@pucv.cl', ''\])"
check "unidad: integrantes en una línea con comas" "$(python3 -c "import server as s;print(s.clean_members('Ana, Luis, Pedro'))")" "(\['Ana', 'Luis', 'Pedro'\], \['', '', ''\])"
check "unidad: formato de preguntas" "$(python3 -c "
import server as s
q,e=s.parse_quiz('¿Control?\n* Negativo\nPositivo\nExplicación: porque sí\n\n¿Otra?\nA\n*B')
print(q[0]['correct'],q[1]['correct'],q[0]['explanation'],e=='' , s.parse_quiz('Sin correcta\nA\nB')[1][:20], s.parse_quiz(s.quiz_text(q))[0]==q)")" "0 1 porque sí True Revisa la pregunta « True"

python3 "$APP/server.py" > "$S/server.log" 2>&1 & PID=$!; sleep 1.2
for u in admin prof ana luis bea carla; do login $u; done
check "CSP permite el reproductor" "$(curl -s -D - -o /dev/null $B/)" "frame-src https://www.youtube-nocookie.com https://drive.google.com"
C=$(req prof -d '{"project_id":"incentiva","section":"Oftalmología","days":7}' $B/api/admin/join-codes | val "d['code']")
for u in ana luis bea; do req $u -d "{\"code\":\"$C\"}" $B/api/join > /dev/null; done
check "lector: vitrina en /api/me" "$(req carla $B/api/me)" '"reader_projects": \["incentiva"\]'

base='"project_id":"incentiva","section":"Oftalmología","summary":"Tamizaje","evidence_url":"https://example.org/f","video_length_confirmed":true,"consent_confirmed":true,"project_fields":{"challenge":"Acceso rural","research_question":"¿Mejora el acceso?","evidence":"Fuente 1; fuente 2; fuente 3","solution":"Propuesta de prueba","community":"Mayores","indicator":"Derivación","limitations":"Conectividad"}'
check "entrega con correos, subtítulos y vitrina" "$(req ana -d "{$base,\"team_name\":\"Equipo 4\",\"title\":\"Teleoftalmología\",\"video_url\":\"https://youtu.be/dQw4w9WgXcQ\",\"members\":\"Ana Pérez ana@mail.pucv.cl\nLuis Soto luis@mail.pucv.cl\",\"has_subtitles\":true,\"showcase_consent\":true}" $B/api/submissions)" "\[201\]"
check "entrega sin vitrina" "$(req bea -d "{$base,\"team_name\":\"Equipo 7\",\"title\":\"Ruta escolar\",\"video_url\":\"https://example.org/v.mp4\",\"members\":\"Bea\"}" $B/api/submissions)" "\[201\]"
for id in $(req prof $B/api/admin/pending | val "' '.join(str(x['id']) for x in d['submissions'])"); do req prof -d "{\"kind\":\"submission\",\"id\":$id,\"decision\":\"publish\"}" $B/api/admin/review > /dev/null; done
res=$(req bea "$B/api/resources?project=incentiva")
check "ficha con video insertable" "$res" '"embed_url": "https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ?rel=0&cc_load_policy=1"'
check "ficha con subtítulos declarados" "$res" '"has_subtitles": 1'
check "pregunta guía por defecto" "$res" '"guide_question": "¿Qué evidencia muestra'
RID=$(echo "$res" | val "[r['id'] for r in d if r['title']=='Teleoftalmología'][0]")
SLUG=$(echo "$res" | val "[r['slug'] for r in d if r['title']=='Teleoftalmología'][0]")
RID2=$(echo "$res" | val "[r['id'] for r in d if r['title']=='Ruta escolar'][0]")

# Forum
check "comentario de estudiante va a revisión" "$(req bea -d "{\"project_id\":\"incentiva\",\"slug\":\"$SLUG\",\"body\":\"¿Cómo miden la derivación?\"}" $B/api/comments)" '"status": "review"'
CID=$(req prof $B/api/admin/pending | val "d['comments'][0]['id']")
req prof -d "{\"kind\":\"comment\",\"id\":$CID,\"decision\":\"publish\"}" $B/api/admin/review > /dev/null
check "respuesta del equipo autor (por correo) marcada" "$(req luis -d "{\"project_id\":\"incentiva\",\"slug\":\"$SLUG\",\"body\":\"Con el registro del CESFAM\",\"parent_id\":$CID}" $B/api/comments)" '"status": "review"'
check "revisión muestra insignia equipo" "$(req prof $B/api/admin/pending)" '"badge": "equipo", "parent_id": '$CID
TID=$(req prof $B/api/admin/pending | val "d['comments'][0]['id']")
req prof -d "{\"kind\":\"comment\",\"id\":$TID,\"decision\":\"publish\"}" $B/api/admin/review > /dev/null
check "docente publica directo" "$(req prof -d "{\"project_id\":\"incentiva\",\"slug\":\"$SLUG\",\"body\":\"Buena respuesta\",\"parent_id\":$TID}" $B/api/comments)" '"status": "published"'
thread=$(req bea "$B/api/projects/incentiva/resources/$SLUG/comments")
check "respuesta a respuesta queda en el mismo hilo" "$(echo "$thread" | val "sorted({c['parent_id'] for c in d if c['parent_id']})")" "^\[$CID\]$"
check "hilo con insignias" "$thread" '"badge": "docente"'
check "respuesta a comentario ajeno a la ficha" "$(req bea -d "{\"project_id\":\"incentiva\",\"slug\":\"$SLUG\",\"body\":\"x\",\"parent_id\":99999}" $B/api/comments)" "\[404\]"

# Control questions
check "preguntas inválidas" "$(req prof -d "{\"id\":$RID,\"title\":\"Teleoftalmología\",\"category\":\"Video-prototipo\",\"summary\":\"Tamizaje\",\"status\":\"published\",\"quiz\":\"Pregunta\nA\nB\"}" $B/api/admin/resources/update)" "marcada con \*.*\[400\]"
QUIZ='¿Qué mide el indicador?\n* Derivaciones concretadas\nNúmero de videos\nExplicación: mide el resultado en la comunidad.\n\n¿Qué limita la solución?\nEl idioma\n* La conectividad'
check "guardar preguntas y pregunta guía" "$(req prof -d "{\"id\":$RID,\"title\":\"Teleoftalmología\",\"category\":\"Video-prototipo\",\"summary\":\"Tamizaje\",\"status\":\"published\",\"guide_question\":\"¿Funcionaría en Putaendo?\",\"quiz\":\"$QUIZ\"}" $B/api/admin/resources/update)" "\[200\]"
q=$(req bea $B/api/quiz/$RID)
check "estudiante ve preguntas sin respuestas" "$q" '"attempt": null'
nocheck "no se filtra la respuesta correcta" "$q" '"correct"'
check "responder" "$(req bea -d '{"answers":[0,0]}' $B/api/quiz/$RID)" '"score": 1, "total": 2, "correct": \[0, 1\]'
req bea -d '{"answers":[0,1]}' $B/api/quiz/$RID > /dev/null
check "solo cuenta el primer intento" "$(req bea $B/api/quiz/$RID)" '"score": 1'
check "respuestas incompletas" "$(req luis -d '{"answers":[0]}' $B/api/quiz/$RID)" "\[400\]"
check "resultados agregados para la docente" "$(req prof $B/api/admin/resources | val "[r['quiz_stats'] for r in d if r['id']==$RID][0]")" "'respondents': 1.*'correct_share': 1.0.*'correct_share': 0.0"
check "pregunta guía editada" "$(req bea "$B/api/resources?project=incentiva")" '"guide_question": "¿Funcionaría en Putaendo?"'

# Peer review
check "autor no coevalúa su trabajo" "$(req ana -d "{\"scores\":{\"territory\":3,\"evidence\":3,\"feasibility\":3,\"ethics\":3,\"communication\":3},\"strength\":\"a\",\"suggestion\":\"b\"}" $B/api/peer/$RID)" "\[403\]"
check "integrante por correo tampoco" "$(req luis $B/api/peer/$RID)" '"is_author": true, "can_review": false'
check "falta un criterio" "$(req bea -d '{"scores":{"territory":3},"strength":"a","suggestion":"b"}' $B/api/peer/$RID)" "Fundamento científico.*\[400\]"
check "coevaluación de par" "$(req bea -d '{"scores":{"territory":4,"evidence":3,"feasibility":2,"ethics":3,"communication":4},"strength":"Clara","suggestion":"Citar más estudios"}' $B/api/peer/$RID)" "\[200\]"
req bea -d '{"scores":{"territory":4,"evidence":4,"feasibility":2,"ethics":3,"communication":4},"strength":"Clara","suggestion":"Citar más estudios locales"}' $B/api/peer/$RID > /dev/null
peer=$(req ana $B/api/peer/$RID)
check "equipo ve promedio y comentario actualizado" "$peer" '"count": 1.*"overall": 3.4.*Citar más estudios locales'
nocheck "equipo no ve quién evaluó" "$peer" "bea"
check "docente ve resumen" "$(req prof $B/api/admin/peer-summary)" '"overall": 3.4'
check "CSV de coevaluación con evaluador" "$(req prof $B/api/admin/peer-reviews.csv)" "bea@mail.pucv.cl"
check "estudiante no ve el resumen docente" "$(req bea $B/api/admin/peer-summary)" "\[403\]"

# Showcase / reader mode
reader=$(req carla "$B/api/resources?project=incentiva")
check "lector ve el trabajo autorizado" "$reader" "Teleoftalmología"
nocheck "lector no ve el trabajo sin autorización" "$reader" "Ruta escolar"
check "lector no ve archivos ni preguntas" "$(echo "$reader" | val "[(r['has_file'],r['quiz_count']) for r in d]")" "\[(0, 0)\]"
check "lector no comenta" "$(req carla -d "{\"project_id\":\"incentiva\",\"slug\":\"$SLUG\",\"body\":\"hola\"}" $B/api/comments)" "\[403\]"
check "lector no responde preguntas" "$(req carla $B/api/quiz/$RID)" "\[404\]"
check "lector no coevalúa" "$(req carla $B/api/peer/$RID)" "\[404\]"
check "Innova sigue cerrado para lectores" "$(req carla "$B/api/resources?project=innova")" "\[403\]"

# Exit tickets
tk=$(req prof -d '{"project_id":"incentiva","title":"Sesión 2 nov","hours":2}' $B/api/admin/tickets)
check "crear tiquete" "$tk" "/tiquete/.*\[201\]"
CODE=$(echo "$tk" | val "d['code']")
TKID=$(req prof $B/api/admin/tickets | val "d[0]['id']")
check "preguntas estándar por defecto" "$(req bea $B/api/tickets/$CODE)" "el desafío de tu equipo.*profundizar.*riesgos"
check "QR en SVG" "$(curl -s -b $S/prof.jar -D - -o $S/qr.svg $B/api/admin/tickets/$TKID/qr.svg)" "image/svg+xml"
check "estudiante no ve el QR" "$(req bea $B/api/admin/tickets/$TKID/qr.svg)" "\[403\]"
check "respuestas incompletas" "$(req bea -d '{"answers":["a",""]}' $B/api/tickets/$CODE/answer)" "\[400\]"
check "responder tiquete" "$(req bea -d '{"answers":["=HYPERLINK(1)","PCR","Videos"]}' $B/api/tickets/$CODE/answer)" "anónima.*\[201\]"
check "una sola respuesta por persona" "$(req bea -d '{"answers":["a","b","c"]}' $B/api/tickets/$CODE/answer)" "\[409\]"
check "fuera del curso no responde" "$(req carla -d '{"answers":["a","b","c"]}' $B/api/tickets/$CODE/answer)" "\[404\]"
req luis -d '{"answers":["Indicadores","Muestreo","Teleconsulta"]}' $B/api/tickets/$CODE/answer > /dev/null
check "respuestas anónimas (sin columna de persona)" "$(sqlite3 $S/repo.sqlite3 'PRAGMA table_info(exit_ticket_answers)')" "answered_on"
nocheck "respuestas sin user_id" "$(sqlite3 $S/repo.sqlite3 'PRAGMA table_info(exit_ticket_answers)')" "user_id"
csv=$(curl -s -b $S/prof.jar $B/api/admin/tickets/$TKID/responses.csv)
check "CSV con BOM y preguntas" "$(echo "$csv" | head -1 | xxd | head -1)" "efbb bf"
check "CSV neutraliza fórmulas" "$csv" "'=HYPERLINK(1)"
check "contador de respuestas" "$(req prof $B/api/admin/tickets)" '"answers": 2'
check "enlace de retroalimentación debe ser https" "$(req prof -d "{\"id\":$TKID,\"feedback_url\":\"http://x\"}" $B/api/admin/tickets/update)" "\[400\]"
check "cerrar con audio" "$(req prof -d "{\"id\":$TKID,\"feedback_url\":\"https://example.org/audio.m4a\",\"active\":false}" $B/api/admin/tickets/update)" "\[200\]"
check "tiquete cerrado" "$(req ana -d '{"answers":["a","b","c"]}' $B/api/tickets/$CODE/answer)" "cerró.*\[409\]"
check "estudiante ve la retroalimentación" "$(req ana "$B/api/my-tickets?project=incentiva")" '"feedback_url": "https://example.org/audio.m4a"'
check "página del tiquete existe" "$(curl -s -o /dev/null -w '%{http_code}' $B/tiquete/$CODE)" "200"
check "otros recursos siguen bien" "$(req bea "$B/api/resources?project=innova")" "\[403\]"
kill $PID; wait $PID 2>/dev/null
grep -i "traceback" -A5 "$S/server.log" | head -20
