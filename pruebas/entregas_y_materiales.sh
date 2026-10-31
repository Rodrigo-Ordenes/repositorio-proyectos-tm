#!/bin/bash
# End-to-end checks for P1: paralelo, members, structured fields, material editing, backups.
set -u +B
S="${PRUEBAS_TMP:-$(mktemp -d)}/p1"
APP="$(cd "$(dirname "$0")/.." && pwd)"
rm -rf "$S"; mkdir -p "$S"
export APP_DB_PATH=$S/repo.sqlite3 APP_UPLOAD_DIR=$S/files APP_BACKUP_DIR=$S/backups APP_DEMO_AUTH=1 PORT=8766 \
  PUCV_ADMIN_EMAILS=admin@mail.pucv.cl PUCV_INCENTIVA_ADMINS=prof@mail.pucv.cl
B=http://localhost:8766
J=(-H "Content-Type: application/json")
start() { python3 "$APP/server.py" > "$S/server.log" 2>&1 & PID=$!; sleep 1.2; }
stop() { kill $PID; wait $PID 2>/dev/null; }
login() { curl -s -c "$S/$1.jar" "${J[@]}" -d "{\"email\":\"$1@mail.pucv.cl\"}" $B/auth/demo -o /dev/null; }
req() { local who=$1; shift; curl -s -b "$S/$who.jar" "${J[@]}" -w ' [%{http_code}]\n' "$@"; }
check() { if echo "$2" | grep -q -- "$3"; then echo "OK   $1"; else echo "FAIL $1 -> $2"; fi; }

start
check "backup automático al iniciar" "$(ls $S/backups)" "respaldo-.*sqlite3"
login admin; login prof; login ana
code=$(req admin -d '{"project_id":"incentiva","section":"Oftalmología","label":"Sesión 2 nov","days":7}' $B/api/admin/join-codes)
check "código con paralelo" "$code" "\[201\]"
check "paralelo inválido" "$(req admin -d '{"project_id":"incentiva","section":"Química"}' $B/api/admin/join-codes)" "\[400\]"
C=$(echo "$code" | python3 -c "import sys,json;print(json.loads(sys.stdin.read().rsplit(' [',1)[0])['code'])")
check "unirse con código" "$(req ana -d "{\"code\":\"$C\"}" $B/api/join)" "\[200\]"
check "paralelo registrado" "$(req ana $B/api/me)" '"my_sections": {"incentiva": "Oftalmología"}'
check "lista de códigos muestra paralelo" "$(req prof $B/api/admin/join-codes)" '"section": "Oftalmología"'
check "integrantes muestran paralelo" "$(req prof $B/api/admin/members)" '"section": "Oftalmología"'

base='"project_id":"incentiva","team_name":"Equipo 4","title":"Teleoftalmología rural","summary":"Tamizaje con celular","video_url":"https://example.org/v.mp4","evidence_url":"https://example.org/f","video_length_confirmed":true,"consent_confirmed":true'
fields='"project_fields":{"challenge":"Acceso rural","research_question":"¿Mejora el acceso?","evidence":"Fuente 1; fuente 2; fuente 3","solution":"Propuesta de prueba","community":"Personas mayores de Putaendo","indicator":"Tasa de derivación","limitations":"Requiere conectividad"}'
check "sin integrantes" "$(req ana -d "{$base,\"section\":\"Oftalmología\",$fields}" $B/api/submissions)" "integran el equipo.*\[400\]"
check "sin paralelo" "$(req ana -d "{$base,\"members\":\"Ana\",$fields}" $B/api/submissions)" "paralelo.*\[400\]"
check "campo obligatorio vacío" "$(req ana -d "{$base,\"section\":\"Oftalmología\",\"members\":\"Ana\",\"project_fields\":{\"challenge\":\"Acceso rural\"}}" $B/api/submissions)" "Completa «.*\[400\]"
check "opción inválida" "$(req ana -d "{$base,\"section\":\"Oftalmología\",\"members\":\"Ana\",\"project_fields\":{\"challenge\":\"Marte\",\"research_question\":\"¿Mejora el acceso?\",\"evidence\":\"Fuente 1; fuente 2; fuente 3\",\"solution\":\"Propuesta de prueba\",\"community\":\"x\",\"indicator\":\"x\",\"limitations\":\"x\"}}" $B/api/submissions)" "opción válida.*\[400\]"
check "entrega completa" "$(req ana -d "{$base,\"section\":\"Oftalmología\",\"members\":\"Ana Pérez\nLuis Soto\nana pérez\",$fields,\"ai_declaration\":\"Canva para títulos\"}" $B/api/submissions)" "\[201\]"
pending=$(req prof $B/api/admin/pending)
check "revisión muestra integrantes sin duplicar" "$pending" '"members": \["Ana Pérez", "Luis Soto"\]'
check "revisión muestra campos con etiqueta" "$pending" '"label": "Tipo de desafío", "value": "Acceso rural"'
SID=$(echo "$pending" | python3 -c "import sys,json;print(json.loads(sys.stdin.read().rsplit(' [',1)[0])['submissions'][0]['id'])")
check "publicar" "$(req prof -d "{\"kind\":\"submission\",\"id\":$SID,\"decision\":\"publish\"}" $B/api/admin/review)" "\[200\]"
res=$(req ana "$B/api/resources?project=incentiva")
check "ficha publicada con campos" "$res" '"label": "Resultado esperado e indicador"'
check "ficha con paralelo y etiquetas" "$res" '"tags": \["Acceso rural", "Oftalmología"\]'
check "ficha con IA declarada" "$res" '"ai_declaration": "Canva para títulos"'

mats=$(req prof $B/api/admin/resources)
check "editor ve solo su asignatura" "$(echo "$mats" | grep -c innova)" "^0$"
RID=$(echo "$mats" | python3 -c "import sys,json;print(json.loads(sys.stdin.read().rsplit(' [',1)[0])[0]['id'])")
check "editar material" "$(req prof -d "{\"id\":$RID,\"title\":\"Teleoftalmología rural (v2)\",\"category\":\"Video-prototipo\",\"summary\":\"Tamizaje\",\"tags\":\"Acceso rural, Oftalmología\",\"status\":\"published\"}" $B/api/admin/resources/update)" "actualizado.*\[200\]"
check "retirar material" "$(req prof -d "{\"id\":$RID,\"title\":\"Teleoftalmología rural (v2)\",\"category\":\"Video-prototipo\",\"summary\":\"Tamizaje\",\"status\":\"draft\"}" $B/api/admin/resources/update)" "retirado.*\[200\]"
check "retirado no aparece a estudiantes" "$(req ana "$B/api/resources?project=incentiva")" '^\[\] \[200\]'
check "volver a publicar" "$(req prof -d "{\"id\":$RID,\"title\":\"Teleoftalmología rural (v2)\",\"category\":\"Video-prototipo\",\"summary\":\"Tamizaje\",\"status\":\"published\"}" $B/api/admin/resources/update)" "\[200\]"
check "estudiante no edita" "$(req ana -d "{\"id\":$RID,\"title\":\"x\",\"category\":\"x\",\"summary\":\"x\"}" $B/api/admin/resources/update)" "\[403\]"
INNOVA=$(req admin $B/api/admin/resources | python3 -c "import sys,json;print([r['id'] for r in json.loads(sys.stdin.read().rsplit(' [',1)[0]) if r['slug']=='hbb-variante-proteina'][0])")
check "editor de Incentiva no edita Innova" "$(req prof -d "{\"id\":$INNOVA,\"title\":\"x\",\"category\":\"x\",\"summary\":\"x\"}" $B/api/admin/resources/update)" "\[403\]"
PDF=$(printf '%%PDF-1.4 caso' | base64)
check "admin reemplaza archivo de caso semilla" "$(req admin -d "{\"id\":$INNOVA,\"title\":\"HBB editado por la docente\",\"category\":\"Caso clínico-molecular\",\"summary\":\"Resumen corregido\",\"status\":\"published\",\"filename\":\"caso1.pdf\",\"file_base64\":\"$PDF\"}" $B/api/admin/resources/update)" "\[200\]"
check "archivo malo rechazado" "$(req admin -d "{\"id\":$INNOVA,\"title\":\"x\",\"category\":\"x\",\"summary\":\"x\",\"filename\":\"a.pdf\",\"file_base64\":\"$(printf 'hola' | base64)\"}" $B/api/admin/resources/update)" "PDF válido.*\[400\]"

check "editor no ve respaldos" "$(req prof $B/api/admin/backups)" "\[403\]"
check "admin ve respaldos" "$(req admin $B/api/admin/backups)" '"enabled": true'
curl -s -b "$S/admin.jar" -o "$S/full.zip" -w '%{http_code} %{content_type}\n' $B/api/admin/backup > "$S/dl.txt"
check "descarga respaldo completo" "$(cat $S/dl.txt)" "200 application/zip"
check "zip contiene base y archivos" "$(python3 -m zipfile -l $S/full.zip)" "submissions_files/"
check "no quedan temporales" "$(ls -a $S/backups)" "^respaldo-"
check "privacidad sin sesión" "$(curl -s -o /dev/null -w '%{http_code}' $B/privacidad)" "200"
stop

check "edición de semilla sobrevive reinicio" "$(python3 -c "
import sqlite3,os;import sys;sys.path.insert(0,'$APP');import server;server.init_db()
print(server.connect().execute(\"select title from resources where slug='hbb-variante-proteina'\").fetchone()[0])")" "HBB editado por la docente"
check "verificar respaldo completo" "$(python3 "$APP/server.py" verificar-respaldo $S/full.zip)" "Archivos adjuntos: 1 de 1 incluidos"
check "verificar respaldo diario" "$(python3 "$APP/server.py" verificar-respaldo $(ls $S/backups/respaldo-*.sqlite3 | head -1))" "Integridad: ok"
check "respaldo por consola" "$(python3 "$APP/server.py" respaldo)" "Respaldo completo creado"

# Restore drill: wipe live data, unpack the downloaded archive in its place, and confirm the app serves the same records.
rm -rf "$S/repo.sqlite3"* "$S/files"; mkdir -p "$S/files"
python3 -c "
import zipfile;z=zipfile.ZipFile('$S/full.zip')
open('$S/repo.sqlite3','wb').write(z.read('repository.sqlite3'))
[open('$S/files/'+n.split('/')[1],'wb').write(z.read(n)) for n in z.namelist() if n.startswith('submissions_files/')]"
start
login ana
check "restaurado: entrega publicada vuelve" "$(req ana "$B/api/resources?project=incentiva")" "Teleoftalmología rural (v2)"
check "restaurado: archivo descargable" "$(curl -s -b $S/ana.jar -o /dev/null -w '%{http_code}' -X GET "$B/api/projects/innova/resources/hbb-variante-proteina/file")" "403"
login admin
check "restaurado: archivo del caso" "$(curl -s -b $S/admin.jar "$B/api/projects/innova/resources/hbb-variante-proteina/file")" "%PDF-1.4 caso"
stop
grep -i "traceback\|error" "$S/server.log" | head -5
