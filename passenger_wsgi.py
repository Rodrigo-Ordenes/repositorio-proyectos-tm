"""WSGI entry for cPanel «Python» apps (Phusion Passenger): runs the same App handler as `python3 server.py`.

Each request builds an App with the WSGI request instead of a socket and turns what it writes into a WSGI response,
so no route is duplicated. Background work (daily backup, audit cleanup) runs from cron:
`python3 server.py mantenimiento`.
"""
import http.client
import io
import os
import sys
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import server  # noqa: E402

server.init_db()

HOP_BY_HOP = {"connection", "keep-alive", "proxy-authenticate", "proxy-authorization", "te", "trailers", "transfer-encoding", "upgrade"}


def request_target(environ):
    # REQUEST_URI keeps the bytes the browser sent; PATH_INFO arrives decoded as latin-1, so re-encode it otherwise.
    target = environ.get("REQUEST_URI")
    if not target:
        path = urllib.parse.quote(environ.get("PATH_INFO", "/").encode("latin-1").decode("utf-8", "replace"), safe="/%:@!$&'()*+,;=-._~")
        target = environ.get("SCRIPT_NAME", "") + path + ("?" + environ["QUERY_STRING"] if environ.get("QUERY_STRING") else "")
    return target or "/"


def build_handler(environ):
    lines = [f"{key[5:].replace('_', '-').title()}: {value}" for key, value in environ.items() if key.startswith("HTTP_")]
    if environ.get("CONTENT_TYPE"): lines.append(f"Content-Type: {environ['CONTENT_TYPE']}")
    if environ.get("CONTENT_LENGTH"): lines.append(f"Content-Length: {environ['CONTENT_LENGTH']}")
    handler = server.App.__new__(server.App)
    handler.headers = http.client.parse_headers(io.BytesIO(("\r\n".join(lines) + "\r\n\r\n").encode("latin-1", "replace")))
    handler.command = environ.get("REQUEST_METHOD", "GET").upper()
    handler.path = request_target(environ)
    handler.request_version = "HTTP/1.1"
    handler.requestline = f"{handler.command} {handler.path} HTTP/1.1"
    handler.client_address = (environ.get("REMOTE_ADDR", ""), 0)
    handler.close_connection = True
    # The handler reads at most Content-Length bytes, and only after checking it against the size limit.
    handler.rfile = environ.get("wsgi.input") or io.BytesIO()
    handler.wfile = io.BytesIO()
    return handler


def application(environ, start_response):
    handler = build_handler(environ)
    method = getattr(handler, "do_" + handler.command, None)
    if method is None:
        start_response("405 Method Not Allowed", [("Content-Type", "text/plain; charset=utf-8"), ("Allow", "GET, POST")])
        return [b"Metodo no permitido"]
    method()
    raw = handler.wfile.getvalue()
    head, _, body = raw.partition(b"\r\n\r\n")
    status_line, *header_lines = head.decode("latin-1").split("\r\n")
    status = status_line.split(" ", 1)[1] if " " in status_line else "500 Internal Server Error"
    headers = [tuple(part.strip() for part in line.split(":", 1)) for line in header_lines if ":" in line]
    start_response(status, [(k, v) for k, v in headers if k.lower() not in HOP_BY_HOP])
    return [body]
