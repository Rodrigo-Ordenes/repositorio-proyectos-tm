#!/bin/bash
# Projection mode for the 18 Nov session: nine published works, filters, permissions and the client safeguards.
set -u +B
S="${PRUEBAS_TMP:-$(mktemp -d)}/proyeccion"
APP="$(cd "$(dirname "$0")/.." && pwd)"
rm -rf "$S"; mkdir -p "$S"
export APP_DB_PATH=$S/repo.sqlite3 APP_UPLOAD_DIR=$S/files APP_BACKUP_DIR=$S/backups PORT=8766 APP_DEMO_AUTH=1 APP_BACKUP_HOURS=0 TRUST_PROXY=0 \
  PUCV_ADMIN_EMAILS=admin@mail.pucv.cl PUCV_INCENTIVA_ADMINS=prof@mail.pucv.cl
B=http://localhost:8766
J=(-H "Content-Type: application/json")
check() { if echo "$2" | grep -q -- "$3"; then echo "OK   $1"; else echo "FAIL $1 -> $(echo "$2" | head -c 300)"; fi; }
login() { curl -s -c "$S/$1.jar" "${J[@]}" -d "{\"email\":\"$1@mail.pucv.cl\"}" $B/auth/demo -o /dev/null; }
req() { local who=$1; shift; curl -s -b "$S/$who.jar" "${J[@]}" -w ' [%{http_code}]\n' "$@"; }
val() { python3 -c "import sys,json;d=json.loads(sys.stdin.read().rsplit(' [',1)[0]);print(eval(sys.argv[1]))" "$1"; }

cd "$APP"
python3 server.py > "$S/server.log" 2>&1 & PID=$!; sleep 1.2
login prof
BC=$(req prof -d '{"project_id":"incentiva","section":"Bioanálisis","days":7}' $B/api/admin/join-codes | val "d['code']")
OC=$(req prof -d '{"project_id":"incentiva","section":"Oftalmología","days":7}' $B/api/admin/join-codes | val "d['code']")
videos="https://youtu.be/dQw4w9WgXcQ https://youtu.be/AAAAAAAAAAA https://vimeo.com/76979871 https://drive.google.com/file/d/1APSRoW8XLWShNkeuC7--84XSoyMdcPrP/view https://youtu.be/9bZkp7q19f0 https://youtu.be/kJQP7kiw5Fk https://youtu.be/OPf0YbXqDm0 https://youtu.be/RgKAFK5djSk https://youtu.be/jNQXAC9IVRw"
i=0
for video in $videos; do i=$((i+1)); u=est$i; login $u
  if [ $i -le 6 ]; then code=$BC; section="Bioanálisis"; else code=$OC; section="Oftalmología"; fi
  req $u -d "{\"code\":\"$code\"}" $B/api/join > /dev/null
  req $u -d "{\"project_id\":\"incentiva\",\"section\":\"$section\",\"team_name\":\"Equipo $i\",\"title\":\"Trabajo $i\",\"members\":\"Est $i\",\"summary\":\"R\",\"video_url\":\"$video\",\"video_length_confirmed\":true,\"consent_confirmed\":true,\"project_fields\":{\"challenge\":\"Seguimiento\",\"research_question\":\"P\",\"evidence\":\"a; b; c\",\"community\":\"C\",\"solution\":\"S\",\"indicator\":\"I\",\"limitations\":\"L\"}}" $B/api/submissions > /dev/null
done
for id in $(sqlite3 "$S/repo.sqlite3" "select id from submissions"); do req prof -d "{\"kind\":\"submission\",\"id\":$id,\"decision\":\"publish\"}" $B/api/admin/review > /dev/null; done
all=$(req prof "$B/api/admin/projection?project=incentiva&cohort=2026-2")
check "proyección con nueve trabajos publicados" "$(echo "$all" | val 'len(d)')" "^9$"
check "orden por paralelo y equipo" "$(echo "$all" | val "' '.join(x['team_name'][-1] for x in d)")" "^1 2 3 4 5 6 7 8 9$"
check "Vimeo no se incrusta: se ofrece abrirlo aparte" "$(echo "$all" | val "[x['embed_url'] for x in d if 'vimeo' in x['media_url']][0]")" "^$"
check "YouTube inexistente se incrusta igual (el aviso queda en la página)" "$(echo "$all" | val "[x['embed_url'] for x in d if 'AAAAAAAAAAA' in x['media_url']][0]")" "youtube-nocookie.com/embed/AAAAAAAAAAA"
check "cada trabajo trae su ruta para el QR" "$(echo "$all" | val "all(x['path'].startswith('/incentiva/recurso/') for x in d)")" "^True$"
check "filtro por paralelo" "$(req prof "$B/api/admin/projection?project=incentiva&cohort=2026-2&section=Oftalmolog%C3%ADa" | val 'len(d)')" "^3$"
qrpath=$(echo "$all" | val "d[0]['path']")
check "QR del trabajo" "$(curl -s -b "$S/prof.jar" "$B/api/admin/qr.svg?path=$qrpath" | head -c 4)" "<svg"
check "un estudiante no abre la proyección" "$(req est1 "$B/api/admin/projection?project=incentiva&cohort=2026-2")" "\[403\]"
check "página de proyección" "$(curl -s -o /dev/null -w '%{http_code}' $B/proyeccion/incentiva)" "200"
kill "$PID"; wait "$PID" 2>/dev/null || true

# Client safeguards (the countdown follows the clock, the video always has a way out, keyboard focus is kept)
js=$(cat static/app.js)
check "el temporizador se calcula con la hora, no con tics" "$js" "deadline-Date.now()"
check "al volver a la pestaña se recalcula el tiempo" "$js" "document.onvisibilitychange"
check "pausa y reanudación" "$js" "'Reanudar'"
check "salida si el video no carga" "$js" "Ábrelo en una pestaña nueva"
check "atajos de teclado visibles" "$js" "Espacio iniciar o pausar"
check "el foco vuelve al botón usado" "$js" "move(1,'proj-next')"
grep -i traceback -A6 "$S/server.log" | head -20
