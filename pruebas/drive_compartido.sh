#!/bin/bash
# Classification of Drive sharing from the anonymous answer Drive gives (measured on 30 real links, Nov 2026):
# 200 public, 401/403 needs sign-in (private for the class), 404 missing, anything else unknown.
set -u
APP="$(cd "$(dirname "$0")/.." && pwd)"
check() { if echo "$2" | grep -q -- "$3"; then echo "OK   $1"; else echo "FAIL $1 -> $(echo "$2" | head -c 300)"; fi; }
cls() { (cd "$APP" && python3 -c "import server,sys;print(server.classify_drive_response(int(sys.argv[1]),sys.argv[2]))" "$1" "${2:-}" 2>&1); }
check "200: el curso puede verlo" "$(cls 200)" "^public$"
check "401: pide iniciar sesión, es privado" "$(cls 401)" "^private$"
check "403: sin permiso, es privado" "$(cls 403)" "^private$"
check "redirección al inicio de sesión de Google es privado" "$(cls 302 https://accounts.google.com/ServiceLogin?continue=x)" "^private$"
check "redirección a otro lugar no se puede determinar" "$(cls 302 https://drive.google.com/otra)" "^unknown$"
check "404: no existe" "$(cls 404)" "^missing$"
check "error del servidor de Drive no se puede determinar" "$(cls 500)" "^unknown$"
check "enlaces ajenos a Drive no se consultan" "$(cd "$APP" && python3 -c "import server;print(server.drive_sharing_status('https://example.com/file/d/1234567890abcdef/view'))")" "^unknown$"
check "enlaces de Drive sin archivo no se consultan" "$(cd "$APP" && python3 -c "import server;print(server.drive_sharing_status('https://drive.google.com/drive/folders/abc'))")" "^unknown$"
