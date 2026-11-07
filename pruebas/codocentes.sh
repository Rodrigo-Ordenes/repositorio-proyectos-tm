#!/bin/bash
# A subject's teacher manages co-teachers of HER subjects only, without global tools; never leaves a subject without teachers.
set -u +B
S="${PRUEBAS_TMP:-$(mktemp -d)}/codocentes"
APP="$(cd "$(dirname "$0")/.." && pwd)"
rm -rf "$S"; mkdir -p "$S"
export APP_DB_PATH=$S/repo.sqlite3 APP_UPLOAD_DIR=$S/files APP_BACKUP_DIR=$S/backups PORT=8766 APP_DEMO_AUTH=1 APP_BACKUP_HOURS=0 TRUST_PROXY=0 \
  PUCV_ADMIN_EMAILS=admin@mail.pucv.cl PUCV_INCENTIVA_ADMINS= PUCV_INNOVA_ADMINS=inn@mail.pucv.cl
B=http://localhost:8766
J=(-H "Content-Type: application/json")
check() { if echo "$2" | grep -q -- "$3"; then echo "OK   $1"; else echo "FAIL $1 -> $(echo "$2" | head -c 300)"; fi; }
nocheck() { if echo "$2" | grep -q -- "$3"; then echo "FAIL $1 -> $(echo "$2" | head -c 300)"; else echo "OK   $1"; fi; }
login() { curl -s -c "$S/$1.jar" "${J[@]}" -d "{\"email\":\"$1@pucv.cl\"}" $B/auth/demo -o /dev/null; }
req() { local who=$1; shift; curl -s -b "$S/$who.jar" "${J[@]}" -w ' [%{http_code}]\n' "$@"; }
staff() { req $1 -d "{\"email\":\"$2@pucv.cl\",\"project_id\":\"$3\"${4:+,\"action\":\"$4\"}}" $B/api/admin/staff; }
cd "$APP"
python3 server.py > "$S/server.log" 2>&1 & PID=$!; sleep 1.2
curl -s -c "$S/admin.jar" "${J[@]}" -d '{"email":"admin@mail.pucv.cl"}' $B/auth/demo -o /dev/null
for u in ale co1 co2 est inn; do login $u; done
check "la administración asigna a la profesora en Incentiva" "$(staff admin ale incentiva)" "\[201\]"
check "la profesora agrega una codocente en su asignatura" "$(staff ale co1 incentiva)" "\[201\]"
check "la codocente nueva ya gestiona la asignatura" "$(req co1 $B/api/me)" '"managed_projects": \["incentiva"\]'
check "no puede agregar en una asignatura ajena" "$(staff ale co2 innova)" "\[403\]"
check "un estudiante no gestiona el equipo" "$(staff est co2 incentiva)" "\[403\]"
list=$(req ale $B/api/admin/staff)
check "la profesora ve el equipo de su asignatura" "$list" "co1@pucv.cl"
nocheck "no ve el equipo de otra asignatura" "$list" "inn@pucv.cl"
nocheck "no ve los correos de la administración global" "$list" "admin@mail.pucv.cl"
check "la codocente puede retirarse si queda otra docente" "$(staff co1 co1 incentiva remove)" "\[200\]"
check "la última docente no puede retirarse" "$(staff ale ale incentiva remove)" "última docente.*\[409\]"
check "la profesora sigue en su asignatura" "$(req ale $B/api/me)" '"managed_projects": \["incentiva"\]'
staff ale co2 incentiva > /dev/null
check "con otra docente, ya puede retirarse" "$(staff ale ale incentiva remove)" "\[200\]"
check "la administración puede corregir una asignación equivocada" "$(staff admin co2 incentiva remove)" "\[200\]"
audit=$(req admin $B/api/admin/audit)
check "la incorporación queda en la auditoría con quién la hizo" "$audit" '"event_type": "staff_added", "actor_email": "ale@pucv.cl", "subject_email": "co1@pucv.cl"'
check "el retiro queda en la auditoría" "$audit" '"event_type": "staff_removed", "actor_email": "co1@pucv.cl"'
check "la docente no consulta la auditoría global" "$(req co2 $B/api/admin/audit)" "\[403\]"
check "la docente no descarga el respaldo completo" "$(curl -s -o /dev/null -w '%{http_code}' -b "$S/co2.jar" $B/api/admin/backup)" "403"
kill "$PID"; wait "$PID" 2>/dev/null || true
js=$(cat static/app.js)
check "el panel muestra «Equipo docente» a quien gestiona una asignatura" "$js" "managedProjects.length?staffPanel()"
grep -i traceback -A6 "$S/server.log" | head -20
