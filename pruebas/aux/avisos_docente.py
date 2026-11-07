"""Teacher notices: pending counter (always) and hourly e-mail digest (with SMTP), checked against a fake SMTP server."""
import io, json, os, socketserver, sys, threading, time
sys.path.insert(0, os.getcwd())
received = []

class FakeSMTP(socketserver.StreamRequestHandler):
    def handle(self):
        w = lambda line: self.wfile.write((line + "\r\n").encode())
        w("220 fake"); rcpt, data = [], None
        while True:
            line = self.rfile.readline().decode(errors="replace")
            if not line: return
            cmd = line.strip().upper()
            if data is not None:
                if line.rstrip("\r\n") == ".": received.append({"to": rcpt, "data": "".join(data)}); data, rcpt = None, []; w("250 ok"); continue
                data.append(line); continue
            if cmd.startswith(("EHLO", "HELO")): w("250 fake")
            elif cmd.startswith("RCPT"): rcpt.append(line.split(":", 1)[1].strip().strip("<>")); w("250 ok")
            elif cmd == "DATA": data = []; w("354 go")
            elif cmd == "QUIT": w("221 bye"); return
            else: w("250 ok")

srv = socketserver.ThreadingTCPServer(("127.0.0.1", 0), FakeSMTP); srv.daemon_threads = True
threading.Thread(target=srv.serve_forever, daemon=True).start()
os.environ.update({"SMTP_HOST": "127.0.0.1", "SMTP_PORT": str(srv.server_address[1]), "SMTP_SECURITY": "none",
                   "SMTP_FROM": "Avisos <avisos@example.test>", "APP_BASE_URL": "https://repo.example.test"})
import passenger_wsgi, server

def call(method, path, body=None, cookie=""):
    raw = json.dumps(body).encode() if body is not None else b""
    env = {"REQUEST_METHOD": method, "PATH_INFO": path.split("?")[0], "QUERY_STRING": path.partition("?")[2], "REQUEST_URI": path,
           "REMOTE_ADDR": "203.0.113.9", "HTTP_HOST": "repo.example.test", "HTTP_COOKIE": cookie, "CONTENT_TYPE": "application/json",
           "CONTENT_LENGTH": str(len(raw)), "wsgi.input": io.BytesIO(raw)}
    out = {}
    body = b"".join(passenger_wsgi.application(env, lambda s, h, e=None: out.update(status=int(s.split()[0]), headers=h)))
    return out["status"], dict(out["headers"]), body.decode()

def login(email):
    _, h, _ = call("POST", "/auth/demo", {"email": email})
    return h["Set-Cookie"].split(";")[0]

def wait_mail(n, timeout=5):
    end = time.time() + timeout
    while len(received) < n and time.time() < end: time.sleep(0.05)
    return len(received)

def settle(quiet=0.5, timeout=5):
    """Wait until no e-mail has arrived for `quiet` seconds: notices are sent from background threads."""
    end, last, seen = time.time() + timeout, time.time(), len(received)
    while time.time() < end:
        time.sleep(0.05)
        if len(received) != seen: seen, last = len(received), time.time()
        elif time.time() - last >= quiet: return

def wait_for(predicate, timeout=5):
    end = time.time() + timeout
    while time.time() < end:
        if predicate(): return True
        time.sleep(0.05)
    return predicate()

def line(ok, label, detail=""): print(("OK   " if ok else "FAIL ") + label + ("" if ok else " -> " + str(detail)[:250]))

prof, est, otro = login("prof@mail.pucv.cl"), login("ana@mail.pucv.cl"), login("beto@mail.pucv.cl")
st, _, b = call("GET", "/api/admin/pending-counts", cookie=prof)
line(st == 200 and '"total": 0' in b, "contador sin pendientes", (st, b))
line(call("GET", "/api/admin/pending-counts", cookie=est)[0] == 403, "un estudiante no ve el contador")
# Access request → pending counter and one e-mail to the subject's teachers (and the global admin)
call("POST", "/api/access-requests", {"project_id": "incentiva"}, est)
st, _, b = call("GET", "/api/admin/pending-counts", cookie=prof)
line('"access_requests": 1' in b and '"total": 1' in b, "la solicitud aparece en el contador", b)
line(wait_mail(1) >= 1, "la solicitud envía un correo", received)
to = sorted({t for m in received for t in m["to"]})
line("prof@mail.pucv.cl" in to, "el aviso llega a la docente de la asignatura", to)
line("inn@mail.pucv.cl" not in to, "no llega a la docente de otra asignatura", to)
mail = received[0]["data"] if received else ""
line("1 pendiente" in mail and "https://repo.example.test/admin" in mail, "el correo trae el conteo y el enlace al panel", mail[-400:])
line("ana@mail.pucv.cl" not in mail and "Ana" not in mail, "el correo no incluye datos de la estudiante", mail[-400:])
# A second event within the hour does not send another e-mail to the same teacher
settle(); before = len(received)
call("POST", "/api/access-requests", {"project_id": "incentiva"}, otro)
time.sleep(0.6)
line(len([m for m in received[before:] if "prof@mail.pucv.cl" in m["to"]]) == 0, "como máximo un correo por hora por docente")
# The hourly cron sends the digest once the hour has passed, with the updated total
settle()
with server.connect() as db: db.execute("UPDATE settings SET value=CAST(value AS INTEGER)-3700 WHERE key LIKE 'notify_last:%'")
before = len(received)
server.notify_pending_digest()
wait_for(lambda: any("prof@mail.pucv.cl" in m["to"] for m in received[before:]))
digest = [m for m in received[before:] if "prof@mail.pucv.cl" in m["to"]]
line(digest and "2 pendientes" in digest[0]["data"], "el cron envía el resumen con el total actualizado", digest)
settle(); before = len(received); server.notify_pending_digest(); settle()
line(len(received) == before, "el cron no repite el aviso sin novedades")
# Opt-out
st, _, _ = call("POST", "/api/admin/notifications", {"enabled": False}, prof)
line(st == 200 and '"email_enabled": false' in call("GET", "/api/admin/pending-counts", cookie=prof)[2], "la docente desactiva los avisos por correo")
with server.connect() as db: db.execute("UPDATE settings SET value=CAST(value AS INTEGER)-3700 WHERE key LIKE 'notify_last:%'")
before = len(received); call("POST", "/api/access-requests", {"project_id": "incentiva"}, login("caro@mail.pucv.cl")); time.sleep(0.6)
line(not [m for m in received[before:] if "prof@mail.pucv.cl" in m["to"]], "desactivados, no le llegan")
# Test e-mail button: to herself, rate limited, audited
before = len(received)
st, _, b = call("POST", "/api/admin/test-email", {}, prof)
line(st == 200 and wait_mail(before + 1) > before and received[-1]["to"] == ["prof@mail.pucv.cl"], "correo de prueba a mi dirección", (st, b))
codes = [call("POST", "/api/admin/test-email", {}, prof)[0] for _ in range(4)]
line(429 in codes, "el correo de prueba tiene límite de intentos", codes)
line(call("POST", "/api/admin/test-email", {}, est)[0] == 403, "un estudiante no puede enviar correos de prueba")
admin = login("admin@mail.pucv.cl")
line('"event_type": "test_email_sent"' in call("GET", "/api/admin/audit", cookie=admin)[2], "el correo de prueba queda en la auditoría")
ok, detail = server.smtp_check()
line(ok, "el diagnóstico conecta con el servidor de correo", detail)
srv.shutdown()
