#!/bin/bash
# Runs every end-to-end suite against throwaway databases (port 8766 must be free) and exits 1 if any check fails.
# Needs python3, curl and sqlite3. Usage: bash pruebas/ejecutar.sh [suite …]
cd "$(dirname "$0")"
export PRUEBAS_TMP="$(mktemp -d)"
trap 'rm -rf "$PRUEBAS_TMP"' EXIT
if lsof -ti:8766 >/dev/null 2>&1; then echo "El puerto 8766 está ocupado: cierra lo que lo usa y vuelve a intentar."; exit 2; fi
suites=("$@")
[ ${#suites[@]} -eq 0 ] && suites=(acceso entregas_y_materiales foro_tiquetes_vitrina encuestas_indicadores_datos seguridad paginas_publicas mejoras trazabilidad_ingresos auditoria_global respaldo_recordatorio)
total_ok=0; total_fail=0
for suite in "${suites[@]}"; do
  out=$(bash "./$suite.sh" 2>&1)
  ok=$(echo "$out" | grep -c '^OK   ')
  fail=$(echo "$out" | grep -c '^FAIL ')
  printf '%-30s %3d correctas, %d con fallas\n' "$suite" "$ok" "$fail"
  echo "$out" | grep -E '^FAIL |Traceback' | sed 's/^/    /'
  total_ok=$((total_ok + ok)); total_fail=$((total_fail + fail))
done
echo "Total: $total_ok verificaciones correctas, $total_fail con fallas."
[ "$total_fail" -eq 0 ]
