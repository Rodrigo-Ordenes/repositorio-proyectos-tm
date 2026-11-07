#!/bin/bash
# Comparative scale as percentages per level (KPSI 1–4, perception 1–5), with n, largest-remainder rounding and n < 5 hidden.
set -u +B
S="${PRUEBAS_TMP:-$(mktemp -d)}/kpsi"
APP="$(cd "$(dirname "$0")/.." && pwd)"
rm -rf "$S"; mkdir -p "$S"
export APP_DB_PATH=$S/repo.sqlite3 APP_UPLOAD_DIR=$S/files APP_BACKUP_DIR=$S/backups PORT=8766 APP_DEMO_AUTH=1 APP_BACKUP_HOURS=0 TRUST_PROXY=0 \
  PUCV_ADMIN_EMAILS=admin@mail.pucv.cl PUCV_INCENTIVA_ADMINS=prof@mail.pucv.cl APP_ENV_FILE=$S/no.env
B=http://localhost:8766
J=(-H "Content-Type: application/json")
check() { if echo "$2" | grep -q -- "$3"; then echo "OK   $1"; else echo "FAIL $1 -> $(echo "$2" | head -c 300)"; fi; }
login() { curl -s -c "$S/$1.jar" "${J[@]}" -d "{\"email\":\"$1@mail.pucv.cl\"}" $B/auth/demo -o /dev/null; }
req() { local who=$1; shift; curl -s -b "$S/$who.jar" "${J[@]}" -w ' [%{http_code}]\n' "$@"; }
val() { python3 -c "import sys,json;d=json.loads(sys.stdin.read().rsplit(' [',1)[0]);print(eval(sys.argv[1]))" "$1"; }
cd "$APP"
shares() { python3 -c "import server,sys,json;print(json.dumps(server.level_shares(json.loads(sys.argv[1]))))" "$1"; }
check "suma 100 por mayor resto (6 respuestas en 3 niveles)" "$(shares '[2,2,2,0]')" '"n": 6, "percent": \[34, 33, 33, 0\]'
check "suma 100 con 7 respuestas repartidas" "$(shares '[1,1,1,1,1,1,1]')" '"percent": \[15, 15, 14, 14, 14, 14, 14\]'
check "con menos de 5 respuestas no se muestran porcentajes" "$(shares '[1,2,1,0]')" '"n": 4, "percent": null'
check "sin respuestas" "$(shares '[0,0,0,0]')" '"n": 0, "percent": null'

python3 server.py > "$S/server.log" 2>&1 & PID=$!; sleep 1.2
login prof
CODE=$(req prof -d '{"project_id":"incentiva","days":7}' $B/api/admin/join-codes | val "d['code']")
req prof -d '{"project_id":"incentiva","kind":"kpsi","moment":"entrada","title":"KPSI entrada"}' $B/api/admin/surveys > /dev/null
IN=$(req prof $B/api/admin/surveys | val "d[0]['code']")
req prof -d '{"project_id":"incentiva","kind":"kpsi","moment":"salida","title":"KPSI salida"}' $B/api/admin/surveys > /dev/null
OUT=$(req prof $B/api/admin/surveys | val "d[0]['code']")
req prof -d '{"project_id":"incentiva","kind":"percepcion","moment":"cierre","title":"Percepción"}' $B/api/admin/surveys > /dev/null
PER=$(req prof $B/api/admin/surveys | val "d[0]['code']"); NPER=$(req prof $B/api/admin/surveys | val "len(d[0].get('items') or []) if False else 0")
NITEMS=$(req prof $B/api/surveys/$PER | val "len(d['items'])")
i=0
for u in a1 a2 a3 a4 a5 a6; do i=$((i+1)); login $u; req $u -d "{\"code\":\"$CODE\"}" $B/api/join > /dev/null
  req $u -d "{\"values\":[$(( (i%2)+1 )),1,1,1,1,1,1]}" $B/api/surveys/$IN/answer > /dev/null
  req $u -d "{\"values\":[$(( (i%3)+2 )),4,4,4,4,4,4]}" $B/api/surveys/$OUT/answer > /dev/null
  [ $i -le 3 ] && req $u -d "{\"values\":[$(python3 -c "print(','.join(['4']*$NITEMS))")]}" $B/api/surveys/$PER/answer > /dev/null
done
rep=$(req prof "$B/api/admin/report?project=incentiva&cohort=2026-2")
check "el informe trae porcentajes de entrada por nivel" "$(echo "$rep" | val "d['kpsi'][0]['before_levels']")" "'n': 6, 'percent': \[50, 50, 0, 0\]"
check "y de salida" "$(echo "$rep" | val "d['kpsi'][0]['after_levels']")" "'n': 6, 'percent': \[0, 34, 33, 33\]"
check "cada barra suma 100" "$(echo "$rep" | val "all(sum(x['after_levels']['percent'])==100 and sum(x['before_levels']['percent'])==100 for x in d['kpsi'])")" "^True$"
check "las etiquetas de la escala KPSI van con el informe" "$(echo "$rep" | val "len(d['kpsi_scale'])")" "^4$"
check "percepción con 3 respuestas: muestra insuficiente" "$(echo "$rep" | val "d['perception']['items'][0]['levels']")" "'n': 3, 'percent': None"
check "percepción usa la escala de 5 niveles" "$(echo "$rep" | val "len(d['perception']['scale'])")" "^5$"
kill "$PID"; wait "$PID" 2>/dev/null || true
js=$(cat static/app.js); css=$(cat static/styles.css)
check "gráfico de barras apiladas 100 %" "$js" "function stackedChart("
check "el gráfico avisa la muestra insuficiente" "$js" "muestra insuficiente"
check "valores escritos bajo cada barra" "$js" "stack-values"
check "rampa ordinal de 4 niveles validada (claro)" "$css" "--level4-1: #86b6ef"
check "rampa ordinal de 4 niveles validada (oscuro)" "$css" "--level4-1: #1c5cab"
check "rampa ordinal de 5 niveles" "$css" "--level5-5: #0d366b"
grep -i traceback -A6 "$S/server.log" | head -20
check "sin atributos style en el HTML generado (la CSP los bloquea)" "$(grep -c 'style=\"' static/app.js)" "^0$"
