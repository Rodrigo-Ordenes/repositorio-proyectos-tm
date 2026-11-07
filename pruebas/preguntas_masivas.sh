#!/bin/bash
# Pasting several questions at once (one per line) for exit tickets and pre-session questions.
set -u +B
S="${PRUEBAS_TMP:-$(mktemp -d)}/preguntas"
APP="$(cd "$(dirname "$0")/.." && pwd)"
rm -rf "$S"; mkdir -p "$S"
export APP_DB_PATH=$S/repo.sqlite3 APP_UPLOAD_DIR=$S/files APP_BACKUP_DIR=$S/backups PORT=8766 APP_DEMO_AUTH=1 APP_BACKUP_HOURS=0 TRUST_PROXY=0 \
  PUCV_ADMIN_EMAILS=admin@mail.pucv.cl PUCV_INNOVA_ADMINS=inn@mail.pucv.cl APP_ENV_FILE=$S/no.env
B=http://localhost:8766
J=(-H "Content-Type: application/json")
check() { if echo "$2" | grep -q -- "$3"; then echo "OK   $1"; else echo "FAIL $1 -> $(echo "$2" | head -c 300)"; fi; }
login() { curl -s -c "$S/$1.jar" "${J[@]}" -d "{\"email\":\"$1@mail.pucv.cl\"}" $B/auth/demo -o /dev/null; }
req() { local who=$1; shift; curl -s -b "$S/$who.jar" "${J[@]}" -w ' [%{http_code}]\n' "$@"; }
cd "$APP"
python3 server.py > "$S/server.log" 2>&1 & PID=$!; sleep 1.2
login inn
pasted=$(python3 -c 'import json;print(json.dumps({"project_id":"innova","title":"Sesión 9 nov","kind":"previa","hours":24,"questions_text":"1. ¿Qué es una mutación missense?\n\n- ¿Cómo afecta a la proteína PAH?\n• ¿Qué técnica la detecta?\n"}))')
res=$(req inn -d "$pasted" $B/api/admin/tickets)
check "preguntas pegadas crean el tiquete" "$res" "\[201\]"
saved=$(sqlite3 "$S/repo.sqlite3" "select questions from exit_tickets order by id desc limit 1")
check "se guardan limpias, sin numeración ni viñetas" "$saved" '\["¿Qué es una mutación missense?", "¿Cómo afecta a la proteína PAH?", "¿Qué técnica la detecta?"\]'
six=$(python3 -c 'import json;print(json.dumps({"project_id":"innova","title":"S","hours":24,"questions_text":"\n".join(f"P{i}?" for i in range(6))}))')
check "más de 5 preguntas se rechaza con un mensaje claro" "$(req inn -d "$six" $B/api/admin/tickets)" "máximo es 5 preguntas.*\[400\]"
both=$(python3 -c 'import json;print(json.dumps({"project_id":"innova","title":"S2","hours":24,"questions":["Antigua"],"questions_text":"Nueva?"}))')
req inn -d "$both" $B/api/admin/tickets > /dev/null
check "el texto pegado reemplaza a los campos sueltos" "$(sqlite3 "$S/repo.sqlite3" "select questions from exit_tickets order by id desc limit 1")" '^\["Nueva?"\]$'
long=$(python3 -c 'import json;print(json.dumps({"project_id":"innova","title":"S3","hours":24,"questions_text":"x"*500}))')
check "una pregunta de más de 400 caracteres se rechaza" "$(req inn -d "$long" $B/api/admin/tickets)" "400 caracteres.*\[400\]"
kill "$PID"; wait "$PID" 2>/dev/null || true
check "cuadro para pegar varias preguntas en el panel" "$(cat static/app.js)" 'id="tk-paste"'
check "procedimiento en la guía docente" "$(cat GUIA_DOCENTE.md)" "Pegar varias preguntas"
grep -i traceback -A6 "$S/server.log" | head -20
