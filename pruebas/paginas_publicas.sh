#!/bin/bash
# Public pages, template downloads, theme script, diagnostics and the challenge loader.
set -u +B
S="${PRUEBAS_TMP:-$(mktemp -d)}/extra"
APP="$(cd "$(dirname "$0")/.." && pwd)"
rm -rf "$S"; mkdir -p "$S"
export APP_DB_PATH=$S/repo.sqlite3 APP_UPLOAD_DIR=$S/files APP_BACKUP_DIR=$S/backups PORT=8766 PUCV_ADMIN_EMAILS=admin@mail.pucv.cl
B=http://localhost:8766
check() { if echo "$2" | grep -q -- "$3"; then echo "OK   $1"; else echo "FAIL $1 -> $(echo "$2" | head -c 200)"; fi; }
code() { curl -s -o /dev/null -w '%{http_code} %{content_type}' "$B$1"; }
cd "$APP"
python3 server.py > "$S/log" 2>&1 & PID=$!; sleep 1.2
for page in /kit /kit/incentiva /kit/innova /ayuda /privacidad /consentimiento /tiquete/ABC123 /encuesta/ABC123; do check "página pública $page" "$(code $page)" "^200 text/html"; done
check "ruta inexistente" "$(code /kit/otra)" "^404"
check "tema antes de pintar" "$(code /static/theme.js)" "^200 text/javascript"
for f in kit-incentiva.pdf kit-innova.pdf consentimiento.pdf; do check "descarga $f" "$(code /materiales/$f)" "^200 application/pdf"; done
for f in ficha-evidencia-incentiva.docx matriz-diagnostica-innova.docx; do check "descarga $f" "$(code /materiales/$f)" "^200 application/vnd.openxmlformats"; done
check "PDF íntegro" "$(curl -s $B/materiales/kit-innova.pdf | head -c 5)" "%PDF-"
check "no expone otros archivos" "$(code '/materiales/~$triz-diagnostica-innova.docx')" "^404"
check "sin salir de la carpeta" "$(code /materiales/../server.py)" "^404"
check "sin servir el código" "$(code /server.py)" "^404"
check "sin servir la carpeta del curso" "$(code '/Innova%20en%20el%20aula%202S%202026/Tiquetes%20de%20Salida.docx')" "^404"
check "selectores CSS sin espacios tras los dos puntos" "$(python3 -c "
import re,sys
css=open(sys.argv[1]).read()
bad=[m.group(1).strip() for m in re.finditer(r'(?:^|})\\s*([^{}@]+?)\\{', css) if re.search(r'[\\w\\])]: +[:a-z(]', m.group(1))]
print(len(bad), bad[:3])" "$APP/static/styles.css")" "^0 \\[\\]"
check "CSP del reproductor y foco" "$(curl -s -D - -o /dev/null $B/)" "frame-src https://www.youtube-nocookie.com"
check "seis desafíos listos como borradores al iniciar" "$(sqlite3 "$S/repo.sqlite3" "select count(*) from resources where project_id='incentiva' and category like 'Desafío ·%' and status='draft'")" "^6$"
kill $PID; wait $PID 2>/dev/null
check "diagnóstico detecta configuración incompleta" "$(python3 server.py diagnostico; echo "salida=$?")" "salida=1"
check "diagnóstico aprueba configuración completa" "$(APP_BASE_URL=https://repo.example APP_DEMO_AUTH=0 python3 server.py diagnostico | tail -1; echo "salida=${PIPESTATUS[0]}")" "Listo para publicar"
check "borradores de desafíos idempotentes" "$(python3 server.py borradores-desafios; python3 server.py borradores-desafios)" "^0 borradores"
check "desafíos con estructura de expediente" "$(sqlite3 $S/repo.sqlite3 "select count(*) from resources where category like 'Desafío ·%' and content like '%## Barreras de acceso%' and content like '%ficticias%'")" "^6$"
grep -i traceback -A5 "$S/log" | head
