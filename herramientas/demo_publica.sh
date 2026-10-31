#!/bin/bash
# Classroom demo: a separate database with fictional data, reachable on the local network and through a temporary
# public https address (localhost.run, free, no account). Run from the project folder: bash herramientas/demo_publica.sh
# The address changes each time the tunnel reconnects; for a stable one, deploy on Render (README).
set -u
cd "$(dirname "$0")/.."
DEMO="${DEMO_DIR:-$HOME/repositorio-demo}"
PORT="${DEMO_PORT:-8100}"
mkdir -p "$DEMO"
lsof -ti:"$PORT" -sTCP:LISTEN | xargs kill 2>/dev/null; sleep 1
start_server() {
  APP_DB_PATH=$DEMO/repo.sqlite3 APP_UPLOAD_DIR=$DEMO/files APP_BACKUP_DIR=$DEMO/backups HOST=0.0.0.0 PORT=$PORT \
    PUCV_ADMIN_EMAILS=docente@mail.pucv.cl PUCV_OPEN_PROJECTS=innova APP_DEMO_AUTH="$1" APP_BASE_URL="$2" \
    nohup python3 server.py > "$DEMO/server.log" 2>&1 &
  sleep 1.5
}
if [ ! -f "$DEMO/repo.sqlite3" ]; then
  start_server 1 "http://127.0.0.1:$PORT"
  python3 herramientas/datos_demo.py "http://127.0.0.1:$PORT"
  lsof -ti:"$PORT" -sTCP:LISTEN | xargs kill; sleep 1
fi
for who in docente@mail.pucv.cl "sofia.demo@mail.pucv.cl incentiva" "camila.demo@mail.pucv.cl innova"; do
  APP_DB_PATH=$DEMO/repo.sqlite3 python3 server.py codigo $who 30 | head -1
done
pkill -f "nokey@localhost.run" 2>/dev/null
ssh -o StrictHostKeyChecking=accept-new -o ServerAliveInterval=30 -R 80:localhost:"$PORT" nokey@localhost.run > "$DEMO/tunnel.log" 2>&1 &
for _ in $(seq 1 20); do URL=$(grep -o -E "https://[a-z0-9-]+\.lhr\.life" "$DEMO/tunnel.log" | tail -1); [ -n "$URL" ] && break; sleep 1; done
start_server 0 "${URL:-http://127.0.0.1:$PORT}"
IP=$(ipconfig getifaddr en0 2>/dev/null || hostname -I 2>/dev/null | cut -d' ' -f1)
echo
echo "Demo pública:  ${URL:-(el túnel no respondió; usa la red local)}"
echo "Red local:     http://$IP:$PORT"
echo "Entrar con «Tengo un código de ingreso» y uno de los códigos de arriba."
