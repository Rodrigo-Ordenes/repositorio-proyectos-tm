#!/bin/bash
# Fixes from the a–e walkthrough (student on a 375 px phone, teacher on the panel), Nov 2026.
set -u +B
S="${PRUEBAS_TMP:-$(mktemp -d)}/usabilidad"
APP="$(cd "$(dirname "$0")/.." && pwd)"
rm -rf "$S"; mkdir -p "$S"
export APP_DB_PATH=$S/repo.sqlite3 APP_UPLOAD_DIR=$S/files APP_BACKUP_DIR=$S/backups PORT=8766 APP_DEMO_AUTH=1 APP_BACKUP_HOURS=0 TRUST_PROXY=0 \
  PUCV_ADMIN_EMAILS=admin@mail.pucv.cl PUCV_INCENTIVA_ADMINS=prof@mail.pucv.cl APP_BASE_URL=http://localhost:8766
B=http://localhost:8766
J=(-H "Content-Type: application/json")
check() { if echo "$2" | grep -q -- "$3"; then echo "OK   $1"; else echo "FAIL $1 -> $(echo "$2" | head -c 300)"; fi; }
login() { curl -s -c "$S/$1.jar" "${J[@]}" -d "{\"email\":\"$1@mail.pucv.cl\"}" $B/auth/demo -o /dev/null; }

cd "$APP"
python3 server.py > "$S/server.log" 2>&1 & PID=$!; sleep 1.2
login prof
# 1. The projection QR opens the work straight at the peer review
QR=$(curl -s -b "$S/prof.jar" "$B/api/admin/qr.svg?path=/incentiva/recurso/trabajo-1")
EXPECTED=$(python3 -c "import qr;print(qr.svg('http://localhost:8766/incentiva/recurso/trabajo-1#coevaluacion'))")
check "el QR de la proyección lleva a la coevaluación" "$([ "$QR" = "$EXPECTED" ] && echo igual || echo distinto)" "^igual$"
check "el QR sigue rechazando rutas ajenas" "$(curl -s -b "$S/prof.jar" -w ' [%{http_code}]' "$B/api/admin/qr.svg?path=https://evil.example")" "\[400\]"
kill "$PID"; wait "$PID" 2>/dev/null || true

js=$(cat static/app.js)
check "la ficha tiene destino #coevaluacion" "$js" 'id="coevaluacion"'
check "la ficha tiene destino #foro" "$js" 'id="foro"'
check "atajos al foro y la coevaluación arriba de la ficha" "$js" 'class="jump-links"'
check "quien escanea sin sesión vuelve a la ficha después de entrar" "$js" "setItem('afterLogin',path+location.hash)"
# 2–3. Invitation on a phone: the address field is reachable and the student lands in the invited subject
check "con invitación, el correo recibe el foco" "$js" "params.has('unirse')) document.querySelector('#code-email')"
check "tras unirse, va directo a la asignatura" "$js" "history.replaceState({},'',\`/\${joined.project_id}\`)"
check "tras entrar con código, la página parte arriba" "$js" "await bootstrap();window.scrollTo(0,0);"
# 4. Delivery draft survives a reload or an expired session
check "borrador local de la entrega" "$js" "entrega-borrador:"
check "el borrador se borra al enviar" "$js" "removeItem(draftKey)"
# 5. Every field has an accessible name
check "enlace de material adicional con etiqueta" "$js" '<label for="s-evidence">'
check "enunciados de la encuesta con nombre accesible" "$js" 'id="sv-items" aria-label='
grep -i traceback -A6 "$S/server.log" | head -20
