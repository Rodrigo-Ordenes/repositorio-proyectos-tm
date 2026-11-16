#!/bin/bash
# End-to-end checks for team drafts, editing sent deliveries with version backup + teacher notice,
# per-paralelo survey management, and selectable cases (7 Oftalmología + 7 Bioanálisis) in KPSI surveys.
set -u +B
S="${PRUEBAS_TMP:-$(mktemp -d)}/editar_entregas_encuestas"
APP="$(cd "$(dirname "$0")/.." && pwd)"
rm -rf "$S"; mkdir -p "$S"
export APP_DB_PATH=$S/repo.sqlite3 APP_UPLOAD_DIR=$S/files APP_BACKUP_DIR=$S/backups APP_DEMO_AUTH=1 PORT=8766 \
  APP_BASE_URL=https://repo.example.test APP_ENV_FILE=$S/no.env \
  PUCV_ADMIN_EMAILS=admin@mail.pucv.cl PUCV_INCENTIVA_ADMINS=prof@mail.pucv.cl \
  SMTP_HOST=127.0.0.1 SMTP_PORT=8768 SMTP_SECURITY=none SMTP_FROM=avisos@pucv.cl
B=http://localhost:8766
J=(-H "Content-Type: application/json")
check() { if echo "$2" | grep -q -- "$3"; then echo "OK   $1"; else echo "FAIL $1 -> $(echo "$2" | head -c 400)"; fi; }
nocheck() { if echo "$2" | grep -q -- "$3"; then echo "FAIL $1 -> $(echo "$2" | head -c 400)"; else echo "OK   $1"; fi; }
login() { curl -s -c "$S/$1.jar" "${J[@]}" -d "{\"email\":\"$1@mail.pucv.cl\"}" $B/auth/demo -o /dev/null; }
req() { local who=$1; shift; curl -s -b "$S/$who.jar" "${J[@]}" -w ' [%{http_code}]\n' "$@"; }
val() { python3 -c "import sys,json;d=json.loads(sys.stdin.read().rsplit(' [',1)[0]);print(eval(sys.argv[1]))" "$1"; }

# Tiny local SMTP sink (stdlib socketserver, works on Python 3.12+) to verify teacher notice when a team edits its delivery.
python3 - "$S/mail.log" <<'EOF' &
import socketserver, sys
log = sys.argv[1]
class FakeSMTP(socketserver.StreamRequestHandler):
    def handle(self):
        w = lambda line: self.wfile.write((line + "\r\n").encode())
        w("220 fake"); rcpt, data = [], None
        while True:
            line = self.rfile.readline().decode(errors="replace")
            if not line: return
            cmd = line.strip().upper()
            if data is not None:
                if line.rstrip("\r\n") == ".":
                    open(log, "a", encoding="utf-8").write(f"TO:{','.join(rcpt)}\n{''.join(data)}\n---\n")
                    data, rcpt = None, []; w("250 ok"); continue
                data.append(line); continue
            if cmd.startswith(("EHLO", "HELO")): w("250 fake")
            elif cmd.startswith("RCPT"): rcpt.append(line.split(":", 1)[1].strip().strip("<>")); w("250 ok")
            elif cmd == "DATA": data = []; w("354 go")
            elif cmd == "QUIT": w("221 bye"); return
            else: w("250 ok")
socketserver.ThreadingTCPServer.allow_reuse_address = True
srv = socketserver.ThreadingTCPServer(("127.0.0.1", 8768), FakeSMTP)
srv.serve_forever()
EOF
SMTP_PID=$!

cd "$APP"
python3 "$APP/server.py" > "$S/server.log" 2>&1 & PID=$!
trap 'kill $PID $SMTP_PID 2>/dev/null' EXIT
sleep 1.2

for u in admin prof ana luis bea ofa; do login $u; done
CBIO=$(req prof -d '{"project_id":"incentiva","section":"Bioanálisis","days":7}' $B/api/admin/join-codes | val "d['code']")
COFT=$(req prof -d '{"project_id":"incentiva","section":"Oftalmología","days":7}' $B/api/admin/join-codes | val "d['code']")
for u in ana luis bea; do req $u -d "{\"code\":\"$CBIO\"}" $B/api/join > /dev/null; done
req ofa -d "{\"code\":\"$COFT\"}" $B/api/join > /dev/null

# 1. Drafts: save without sending; teammate listed with PUCV email resumes from another computer.
draft_res=$(req ana -d '{"project_id":"incentiva","data":{"team_name":"Equipo Río","section":"Bioanálisis","members":"Ana Demo ana@mail.pucv.cl\nLuis Demo luis@mail.pucv.cl","title":"Borrador inicial","summary":"Avance 1"}}' $B/api/submission-drafts)
check "guardar borrador sin enviar" "$draft_res" 'Borrador guardado.*\[200\]'
check "borrador no entra a revisión docente" "$(req prof $B/api/admin/pending | val "len(d['submissions'])")" "^0$"
check "integrante anotado con correo PUCV ve el borrador en otro computador" "$(req luis "$B/api/submission-drafts?project=incentiva")" '"title": "Borrador inicial".*"own": false'
check "persona fuera del equipo no ve el borrador" "$(req bea "$B/api/submission-drafts?project=incentiva")" '"draft": null'
req luis -d '{"project_id":"incentiva","data":{"team_name":"Equipo Río","section":"Bioanálisis","members":"Ana Demo ana@mail.pucv.cl\nLuis Demo luis@mail.pucv.cl","title":"Borrador retomado por Luis","summary":"Avance 2"}}' $B/api/submission-drafts > /dev/null
check "quien inició el borrador ve el avance guardado por su compañero" "$(req ana "$B/api/submission-drafts?project=incentiva")" '"title": "Borrador retomado por Luis"'

# Send final delivery to review
ficha_b64=$(printf 'Ficha inicial en texto' | base64 | tr -d '\n')
base='"project_id":"incentiva","section":"Bioanálisis","team_name":"Equipo Río","members":"Ana Demo ana@mail.pucv.cl\nLuis Demo luis@mail.pucv.cl","video_url":"https://youtu.be/dQw4w9WgXcQ","evidence_url":"https://example.org/evidencia","video_length_confirmed":true,"consent_confirmed":true,"project_fields":{"challenge":"Seguimiento","research_question":"¿Cómo reducir el rechazo preanalítico?","evidence":"Fuente 1; Fuente 2; Fuente 3","community":"Postas rurales","solution":"Flujo trazable","indicator":"% rechazo","limitations":"Conectividad"}'
sub_res=$(req ana -d "{$base,\"title\":\"Entrega v1\",\"summary\":\"Resumen v1\",\"evidence_file_base64\":\"$ficha_b64\",\"evidence_filename\":\"ficha.txt\"}" $B/api/submissions)
check "enviar entrega a revisión" "$sub_res" '\[201\]'
SID=$(echo "$sub_res" | val "d['id']")
check "al enviar se marca el borrador como enviado" "$(req luis "$B/api/submission-drafts?project=incentiva")" '"draft": null'

# 2. Edit already-sent delivery: teammate can edit, previous version stays backed up, teacher gets notice.
check "integrante del equipo ve la entrega con permiso de edición" "$(req luis "$B/api/my-submissions?project=incentiva")" '"title": "Entrega v1".*"can_edit": true'
check "integrante carga datos para editar" "$(req luis $B/api/submissions/$SID/edit | val "(d['title'],d['evidence_filename'])")" "('Entrega v1', 'ficha.txt')"
check "otro equipo no puede editar la entrega" "$(req bea $B/api/submissions/$SID/edit)" '\[403\]'
check "otro equipo no puede guardar cambios" "$(req bea -d "{$base,\"title\":\"Intruso\",\"summary\":\"X\"}" $B/api/submissions/$SID/update)" '\[403\]'

 > "$S/mail.log"
edit_res=$(req luis -d "{$base,\"title\":\"Entrega v2 corregida\",\"summary\":\"Resumen v2\",\"video_url\":\"https://youtu.be/9bZkp7q19f0\"}" $B/api/submissions/$SID/update)
check "equipo edita su entrega sin pedirlo a la docente" "$edit_res" 'Cambios guardados. La versión anterior quedó respaldada.*\[200\]'
check "título y enlace actualizados en la entrega" "$(req ana $B/api/submissions/$SID/edit | val "(d['title'],d['video_url'],d['evidence_filename'])")" "('Entrega v2 corregida', 'https://youtu.be/9bZkp7q19f0', 'ficha.txt')"
check "versión anterior respaldada en submission_versions" "$(sqlite3 "$S/repo.sqlite3" "select count(*) from submission_versions where submission_id=$SID and snapshot like '%Entrega v1%'")" "^1$"
check "auditoría registra entrega_editada" "$(sqlite3 "$S/repo.sqlite3" "select count(*) from audit_events where event_type='entrega_editada' and entity_id=$SID")" "^1$"
for _ in $(seq 1 40); do grep -q "TO:" "$S/mail.log" 2>/dev/null && break; sleep 0.1; done
check "aviso por correo a la docente al editar entrega" "$(python3 -c "import email,quopri,pathlib;raw=pathlib.Path('$S/mail.log').read_text();print(quopri.decodestring(raw.encode()).decode('utf-8','ignore'))")" "actualizó «Entrega v2 corregida»"

# Publish and edit again: catalog card also updates and a 2nd version snapshot is stored.
req prof -d "{\"kind\":\"submission\",\"id\":$SID,\"decision\":\"publish\"}" $B/api/admin/review > /dev/null
edit_pub=$(req ana -d "{$base,\"title\":\"Entrega v3 publicada\",\"summary\":\"Resumen v3\"}" $B/api/submissions/$SID/update)
check "editar entrega ya publicada actualiza la ficha publicada" "$edit_pub" 'ficha publicada ya muestra los cambios.*\[200\]'
check "catálogo muestra el nuevo título tras editar" "$(req bea "$B/api/resources?project=incentiva")" '"title": "Entrega v3 publicada"'
check "dos versiones anteriores guardadas" "$(sqlite3 "$S/repo.sqlite3" "select count(*) from submission_versions where submission_id=$SID")" "^2$"

# 3 & 4. Surveys per paralelo, protection when answered, and 7 selectable cases for Oftalmología & Bioanálisis.
sv_oft=$(req prof -d '{"project_id":"incentiva","section":"Oftalmología","kind":"kpsi","moment":"entrada","title":"KPSI Oftalmología"}' $B/api/admin/surveys)
check "crear encuesta KPSI para Oftalmología" "$sv_oft" '\[201\]'
OFT_CODE=$(echo "$sv_oft" | val "d['code']")
OFT_ID=$(req prof $B/api/admin/surveys | val "[x['id'] for x in d if x['code']=='$OFT_CODE'][0]")
check "Oftalmología incluye sus 7 casos seleccionables" "$(req ofa $B/api/surveys/$OFT_CODE | val "(len([i for i in d['items'] if i.get('choice')]), len([i for i in d['items'] if not i.get('choice')]))")" "^(7, 7)$"
check "Oftalmología trae Salsipuedes y Nueva Esperanza" "$(req ofa $B/api/surveys/$OFT_CODE)" 'Salsipuedes.*Nueva Esperanza'
check "estudiante de Bioanálisis no ve la encuesta de Oftalmología" "$(req ana "$B/api/my-surveys?project=incentiva" | val "len(d)")" "^0$"
check "estudiante de Bioanálisis no puede abrir la encuesta de Oftalmología" "$(req ana $B/api/surveys/$OFT_CODE)" '\[404\]'

# Create Bioanálisis survey initially without cases (simulating the live survey before adding the 7 cases), then add the 7 Bioanálisis cases.
sv_bio=$(req prof -d '{"project_id":"incentiva","kind":"kpsi","moment":"entrada","title":"KPSI inicial"}' $B/api/admin/surveys)
BIO_CODE=$(echo "$sv_bio" | val "d['code']")
BIO_ID=$(req prof $B/api/admin/surveys | val "[x['id'] for x in d if x['code']=='$BIO_CODE'][0]")
upd_bio=$(req prof -d "{\"id\":$BIO_ID,\"title\":\"KPSI Bioanálisis\",\"section\":\"Bioanálisis\",\"hours\":96,\"use_section_cases\":true}" $B/api/admin/surveys/update)
check "actualizar título, plazo, paralelo y agregar los 7 casos de Bioanálisis (sin respuestas)" "$upd_bio" 'Encuesta actualizada.*\[200\]'
check "Bioanálisis tiene sus 7 casos seleccionables (Río Claro a Laguna Verde)" "$(req ana $B/api/surveys/$BIO_CODE)" 'Río Claro.*Laguna Verde'
check "Bioanálisis tiene 7 casos seleccionables y 7 enunciados KPSI" "$(req ana $B/api/surveys/$BIO_CODE | val "(len([i for i in d['items'] if i.get('choice')]), len([i for i in d['items'] if not i.get('choice')]))")" "^(7, 7)$"
check "estudiante de Oftalmología no ve la encuesta de Bioanálisis" "$(req ofa "$B/api/my-surveys?project=incentiva" | val "[x['code'] for x in d]")" "^\\['$OFT_CODE'\\]$"

# Answering requires picking exactly 1 of the 7 cases plus rating the 7 statements.
check "rechaza respuesta si no selecciona ningún caso del paralelo" "$(req ana -d '{"values":[3,3,3,3,3,3,3,0,0,0,0,0,0,0]}' $B/api/surveys/$BIO_CODE/answer)" 'Marca el caso de tu equipo.*\[400\]'
check "rechaza respuesta si marca más de un caso" "$(req ana -d '{"values":[3,3,3,3,3,3,3,1,1,0,0,0,0,0]}' $B/api/surveys/$BIO_CODE/answer)" '\[400\]'
ans_ok=$(req ana -d '{"values":[3,4,3,4,3,4,4,0,0,1,0,0,0,0],"comment":"Caso 3 San Benito"}' $B/api/surveys/$BIO_CODE/answer)
check "acepta respuesta con 1 caso seleccionado y los enunciados evaluados" "$ans_ok" '\[201\]'
res_bio=$(req prof $B/api/admin/surveys/$BIO_ID/results)
check "resultados muestran el caso seleccionado y promedios KPSI" "$res_bio" 'San Benito.*"count": 1'

# Protection once a survey has answers: cannot delete or change statements, but can change title, section or deadline.
check "encuesta con respuestas nunca se puede borrar" "$(req prof -d '{}' $B/api/admin/surveys/$BIO_ID/delete)" 'ya tiene respuestas: no se puede eliminar.*\[409\]'
check "encuesta con respuestas no permite cambiar sus preguntas" "$(req prof -d "{\"id\":$BIO_ID,\"items\":\"# Otra\\nPregunta distinta\"}" $B/api/admin/surveys/update)" 'no los enunciados.*\[409\]'
check "encuesta con respuestas sí permite cambiar título y plazo" "$(req prof -d "{\"id\":$BIO_ID,\"title\":\"KPSI Bioanálisis (plazo extendido)\",\"hours\":120}" $B/api/admin/surveys/update)" 'Encuesta actualizada.*\[200\]'

# Unanswered survey can be deleted.
sv_tmp=$(req prof -d '{"project_id":"incentiva","kind":"percepcion","moment":"cierre","title":"Borrador encuesta"}' $B/api/admin/surveys)
TMP_ID=$(req prof $B/api/admin/surveys | val "[x['id'] for x in d if x['title']=='Borrador encuesta'][0]")
check "encuesta sin respuestas sí se puede eliminar" "$(req prof -d '{}' $B/api/admin/surveys/$TMP_ID/delete)" 'Encuesta eliminada.*\[200\]'

# Automatic migration on startup (init_db): an unanswered Bioanálisis KPSI survey gets its 7 selectable cases automatically.
sqlite3 "$S/repo.sqlite3" "INSERT INTO surveys(project_id,code,kind,moment,title,items,scale,created_by,created_at,closes_at,cohort,section) VALUES('incentiva','MIGBIO','kpsi','entrada','KPSI Bioanálisis previo','[{\"dimension\":\"Investigación\",\"text\":\"Formulo una pregunta.\"}]','[\"1\",\"2\",\"3\",\"4\"]',1,1,9999999999,'2026-2','');"
python3 -c "import sys;sys.path.insert(0,'$APP');import server;server.init_db()"
check "migración automática asigna paralelo y los 7 casos de Bioanálisis a su encuesta sin respuestas" "$(req ana $B/api/surveys/MIGBIO | val "(d['section'], len([i for i in d['items'] if i.get('choice')]))")" "('Bioanálisis', 7)"

