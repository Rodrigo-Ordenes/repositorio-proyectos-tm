"""Same requests through the stdlib server (HTTP) and through passenger_wsgi.application; prints one line per check."""
import io, json, os, sys, urllib.request, urllib.error
sys.path.insert(0, os.getcwd())
B = sys.argv[1]
import passenger_wsgi

def http(method, path, body=None, headers=None):
    req = urllib.request.Request(B + path, data=body, method=method, headers=headers or {})
    opener = urllib.request.build_opener(type("N", (urllib.request.HTTPRedirectHandler,), {"redirect_request": lambda *a, **k: None}))
    try:
        with opener.open(req, timeout=10) as r: return r.status, dict(r.headers), r.read()
    except urllib.error.HTTPError as e: return e.code, dict(e.headers), e.read()

def wsgi(method, path, body=None, headers=None, remote="203.0.113.7"):
    raw_path, _, query = path.partition("?")
    env = {"REQUEST_METHOD": method, "PATH_INFO": raw_path, "QUERY_STRING": query, "REQUEST_URI": path, "SCRIPT_NAME": "",
           "SERVER_NAME": "localhost", "SERVER_PORT": "8766", "SERVER_PROTOCOL": "HTTP/1.1", "REMOTE_ADDR": remote,
           "wsgi.input": io.BytesIO(body or b""), "wsgi.errors": sys.stderr, "wsgi.url_scheme": "http", "HTTP_HOST": "localhost:8766"}
    for k, v in (headers or {}).items():
        if k.lower() == "content-type": env["CONTENT_TYPE"] = v
        else: env["HTTP_" + k.upper().replace("-", "_")] = v
    if body is not None: env["CONTENT_LENGTH"] = str(len(body))
    out = {}
    def start(status, hdrs, exc_info=None): out["status"], out["headers"] = status, hdrs
    data = b"".join(passenger_wsgi.application(env, start))
    hdrs = {}
    for k, v in out["headers"]: hdrs[k] = hdrs[k] + "\n" + v if k in hdrs else v
    return int(out["status"].split()[0]), hdrs, data

def line(ok, label, detail=""): print(("OK   " if ok else "FAIL ") + label + ("" if ok else " -> " + str(detail)[:200]))
J = {"Content-Type": "application/json"}
for path in ("/", "/static/app.js", "/static/styles.css", "/api/me", "/privacidad", "/incentiva", "/no-existe"):
    a, b = http("GET", path), wsgi("GET", path)
    line(a[0] == b[0], f"{path}: mismo código ({a[0]})", f"{a[0]} vs {b[0]}")
    line(a[2] == b[2], f"{path}: mismo cuerpo", f"{len(a[2])} vs {len(b[2])}")
    line(a[1].get("Content-Type") == b[1].get("Content-Type"), f"{path}: mismo Content-Type")
    line(a[1].get("Content-Security-Policy") == b[1].get("Content-Security-Policy"), f"{path}: misma CSP")
_, h, _ = wsgi("GET", "/")
line(not any(k.lower() in ("connection", "transfer-encoding", "keep-alive") for k in h), "sin cabeceras hop-by-hop (WSGI las prohíbe)")
# Sign-in, cookie and session through WSGI only
st, h, body = wsgi("POST", "/auth/demo", json.dumps({"email": "ana@mail.pucv.cl"}).encode(), J)
cookie = h.get("Set-Cookie", "")
line(st in (200, 302) and "pucv_session=" in cookie and "HttpOnly" in cookie, "ingreso por WSGI entrega la cookie de sesión", (st, cookie))
st, _, body = wsgi("GET", "/api/me", headers={"Cookie": cookie.split(";")[0]})
line(b'"email": "ana@mail.pucv.cl"' in body, "la sesión creada por WSGI se reconoce", body[:120])
st, h, _ = wsgi("GET", "/auth/logout", headers={"Cookie": cookie.split(";")[0]})
line(st == 302 and h.get("Location") == "/", "redirección por WSGI", (st, h.get("Location")))
# Cross-site POST is still blocked, and the body limit is enforced before reading
st, _, body = wsgi("POST", "/auth/demo", b"{}", {**J, "Origin": "https://evil.example"})
line(st == 403, "POST de otro sitio bloqueado por WSGI", st)
class Huge(io.RawIOBase):
    read_bytes = 0
    def readable(self): return True
    def readinto(self, b): Huge.read_bytes += len(b); b[:] = b"x" * len(b); return len(b)
env_body = Huge()
env = {"REQUEST_METHOD": "POST", "PATH_INFO": "/api/comments", "QUERY_STRING": "", "REQUEST_URI": "/api/comments", "SCRIPT_NAME": "",
       "SERVER_NAME": "localhost", "SERVER_PORT": "8766", "SERVER_PROTOCOL": "HTTP/1.1", "REMOTE_ADDR": "203.0.113.7",
       "wsgi.input": env_body, "wsgi.errors": sys.stderr, "wsgi.url_scheme": "http", "HTTP_HOST": "localhost:8766",
       "CONTENT_TYPE": "application/json", "CONTENT_LENGTH": str(50 * 1024 * 1024)}
res = {}
b"".join(passenger_wsgi.application(env, lambda s, h, e=None: res.setdefault("s", s)))
line(res["s"].startswith("413") and Huge.read_bytes == 0, "cuerpo gigante rechazado sin leerlo", (res, Huge.read_bytes))
# The client IP comes from REMOTE_ADDR, not from a header the client controls
import server
h = passenger_wsgi.build_handler({"REQUEST_METHOD": "GET", "PATH_INFO": "/", "QUERY_STRING": "", "REMOTE_ADDR": "198.51.100.9",
                                  "HTTP_X_FORWARDED_FOR": "1.2.3.4", "wsgi.input": io.BytesIO()})
line(h.client_ip() == "198.51.100.9", "IP del cliente desde REMOTE_ADDR", h.client_ip())
# Non-ASCII paths survive the WSGI latin-1 round trip
st, _, _ = wsgi("GET", "/api/admin/projection?project=incentiva&section=Oftalmolog%C3%ADa")
line(st in (401, 403), "ruta con tilde codificada llega intacta", st)
