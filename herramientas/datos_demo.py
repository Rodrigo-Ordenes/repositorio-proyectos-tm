"""Fill a demo instance with fictional data for both courses, through the site's own API.

Start a throwaway server with demo sign-in enabled and an empty database, then run:
    python3 herramientas/datos_demo.py http://127.0.0.1:8100
Everything created here (people, teams, answers) is invented. Never point it at the real course database.
"""
import json
import struct
import sys
import urllib.request
from http.cookiejar import CookieJar

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8100").rstrip("/")
VIDEO = "https://www.youtube.com/watch?v=aqz-KE-bpKQ"  # Big Buck Bunny, Blender Foundation (CC BY 3.0): neutral sample footage


class Session:
    def __init__(self, email):
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))
        self.call("POST", "/auth/demo", {"email": email})

    def call(self, method, path, body=None):
        request = urllib.request.Request(BASE + path, method=method, data=json.dumps(body).encode() if body is not None else None,
                                         headers={"Content-Type": "application/json"})
        try:
            with self.opener.open(request) as response:
                text = response.read().decode()
        except urllib.error.HTTPError as error:
            text = error.read().decode()
            if error.code >= 400 and error.code != 409: raise SystemExit(f"{method} {path} → {error.code}: {text[:200]}")
        try: return json.loads(text)
        except ValueError: return {}


def stl_helix(turns=3, steps=36):
    """A small DNA-like double helix of cubes as a binary STL (the shape of a 3D prototype upload)."""
    import math
    triangles = []
    def cube(cx, cy, cz, r):
        v = [(cx + dx * r, cy + dy * r, cz + dz * r) for dx in (-1, 1) for dy in (-1, 1) for dz in (-1, 1)]
        faces = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
        for a, b, c, d in faces:
            triangles.extend([(v[a], v[b], v[c]), (v[a], v[c], v[d])])
    for i in range(turns * steps):
        angle, z = 2 * math.pi * i / steps, i * 0.6
        for phase in (0, math.pi):
            cube(10 * math.cos(angle + phase), 10 * math.sin(angle + phase), z, 1.2)
        if i % 4 == 0:
            for t in range(1, 6):
                f = t / 6
                cube(10 * math.cos(angle) * (1 - 2 * f), 10 * math.sin(angle) * (1 - 2 * f), z, 0.6)
    data = bytearray(b"modelo de ejemplo".ljust(80, b" ")) + struct.pack("<I", len(triangles))
    for tri in triangles:
        data += struct.pack("<3f", 0, 0, 0) + b"".join(struct.pack("<3f", *p) for p in tri) + b"\0\0"
    import base64
    return base64.b64encode(bytes(data)).decode()


def main():
    admin = Session("docente@mail.pucv.cl")
    codes = {}
    for project, section in (("incentiva", "Bioanálisis"), ("incentiva", "Oftalmología"), ("innova", "")):
        r = admin.call("POST", "/api/admin/join-codes", {"project_id": project, "section": section, "label": "Demostración", "days": 30})
        codes[(project, section)] = r["code"]
    # Publish the six Incentiva challenge drafts.
    for m in admin.call("GET", "/api/admin/resources"):
        if m["status"] == "draft" and m["category"].startswith("Desafío"):
            admin.call("POST", "/api/admin/resources/update", {"id": m["id"], "title": m["title"], "category": m["category"], "summary": m["summary"],
                                                               "content": m["content"], "tags": ", ".join(m["tags"]), "status": "published"})
    people = {}
    for email, project, section in (("ana.demo@mail.pucv.cl", "incentiva", "Bioanálisis"), ("luis.demo@mail.pucv.cl", "incentiva", "Bioanálisis"),
                                    ("sofia.demo@mail.pucv.cl", "incentiva", "Oftalmología"), ("tomas.demo@mail.pucv.cl", "incentiva", "Oftalmología"),
                                    ("camila.demo@mail.pucv.cl", "innova", ""), ("diego.demo@mail.pucv.cl", "innova", ""),
                                    ("valentina.demo@mail.pucv.cl", "innova", ""), ("martin.demo@mail.pucv.cl", "innova", "")):
        people[email] = Session(email)
        people[email].call("POST", "/api/join", {"code": codes[(project, section)]})
    alternatives = {"items": [{"name": "Tamizaje con retinógrafo itinerante", "scores": [3, 3, 3, 2, 3, 3, 2]},
                              {"name": "Traslado programado al hospital", "scores": [2, 2, 1, 2, 3, 2, 1]}], "chosen": 0}
    base = {"video_url": VIDEO, "video_length_confirmed": True, "consent_confirmed": True, "has_subtitles": True}
    deliveries = [
        ("sofia.demo@mail.pucv.cl", {"project_id": "incentiva", "section": "Oftalmología", "team_name": "Equipo Retina", "title": "Retina al día en la posta rural",
          "summary": "Un circuito de tamizaje con retinógrafo no midriático que visita la posta una vez al mes y envía las imágenes por telemedicina.",
          "members": "Sofía Demo sofia.demo@mail.pucv.cl\nTomás Demo tomas.demo@mail.pucv.cl", "showcase_consent": True,
          "ai_declaration": "Usamos Canva para los títulos y subtítulos automáticos de Clipchamp, revisados por el equipo.", "alternatives": alternatives,
          "project_fields": {"challenge": "Acceso rural", "research_question": "¿Aumenta la cobertura de fondo de ojo un tamizaje itinerante en personas con diabetes de zonas rurales?",
                             "evidence": "Fuente 1 (revisión sistemática de telemedicina oftalmológica)\nFuente 2 (guía clínica MINSAL)\nFuente 3 (estudio chileno de cobertura)",
                             "community": "420 personas con diabetes inscritas en una posta rural (expediente ficticio).",
                             "solution": "Agenda en horario no laboral, traslado del equipo y lectura remota de las imágenes.",
                             "indicator": "Porcentaje con fondo de ojo vigente a 6 meses.", "limitations": "Depende de la conectividad para enviar imágenes."}}, "publish"),
        ("ana.demo@mail.pucv.cl", {"project_id": "incentiva", "section": "Bioanálisis", "team_name": "Equipo Resultados", "title": "Resultados que llegan",
          "summary": "Avisos por voz y una tarjeta impresa para que las personas mayores sepan cuándo y cómo retirar sus resultados alterados.",
          "members": "Ana Demo ana.demo@mail.pucv.cl\nLuis Demo luis.demo@mail.pucv.cl", "ai_declaration": "Sin uso de IA.",
          "project_fields": {"challenge": "Personas mayores", "research_question": "¿Mejora la tasa de control posterior un aviso telefónico a personas mayores con resultados alterados?",
                             "evidence": "Fuente 1\nFuente 2\nFuente 3", "community": "Personas mayores que viven solas (expediente ficticio).",
                             "solution": "Llamado del agente comunitario y tarjeta con la fecha de control.", "indicator": "Controles realizados en 30 días.",
                             "limitations": "Requiere tiempo del agente comunitario."}}, "review"),
        ("camila.demo@mail.pucv.cl", {"project_id": "innova", "team_name": "Equipo FMR1", "title": "Cuando el gen está, pero no se expresa",
          "summary": "Cápsula sobre la expansión de repeticiones CGG en FMR1, su metilación y cómo confirmarla en el laboratorio.",
          "members": "Camila Demo camila.demo@mail.pucv.cl\nDiego Demo diego.demo@mail.pucv.cl", "showcase_consent": True,
          "ai_declaration": "Adobe Express para una animación de la metilación, revisada por el equipo.",
          "model_file_base64": stl_helix(), "model_filename": "doble-helice.stl",
          "project_fields": {"alteration": "FMR1, expansión de repeticiones CGG", "process": "Regulación epigenética",
                             "effect": "Metilación de la región reguladora y silenciamiento del gen.", "phenotype": "Disminución de FMRP y alteraciones del neurodesarrollo.",
                             "technique": "PCR de repeticiones y Southern blot para estimar el tamaño y la metilación.",
                             "controls": "Control normal, premutación y mutación completa conocidos.", "limitations": "La PCR puede no amplificar expansiones muy grandes."}}, "publish"),
        ("valentina.demo@mail.pucv.cl", {"project_id": "innova", "team_name": "Equipo XPC", "title": "El daño que no se repara",
          "summary": "Cápsula sobre la reparación por escisión de nucleótidos y su falla en el caso XPC.",
          "members": "Valentina Demo valentina.demo@mail.pucv.cl\nMartín Demo martin.demo@mail.pucv.cl", "ai_declaration": "Sin uso de IA.",
          "project_fields": {"alteration": "XPC, variante con pérdida de función", "process": "Replicación y reparación del ADN",
                             "effect": "No se reconoce el daño por radiación UV.", "phenotype": "Fotosensibilidad y riesgo de cáncer de piel.",
                             "technique": "Ensayo funcional de reparación y secuenciación de XPC.", "controls": "Células control irradiadas y sin irradiar."}}, "reject"),
    ]
    for email, body, decision in deliveries:
        people[email].call("POST", "/api/submissions", {**base, **body})
    pending = admin.call("GET", "/api/admin/pending")["submissions"]
    for email, body, decision in deliveries:
        sub = next((s for s in pending if s["title"] == body["title"]), None)
        if sub and decision != "review":
            admin.call("POST", "/api/admin/review", {"kind": "submission", "id": sub["id"], "decision": decision,
                                                     "note": "Falta explicar los controles del ensayo." if decision == "reject" else ""})
    catalog = {p: admin.call("GET", f"/api/resources?project={p}") for p in ("incentiva", "innova")}
    retina = next(r for r in catalog["incentiva"] if r["title"].startswith("Retina"))
    fmr1 = next(r for r in catalog["innova"] if r["title"].startswith("Cuando el gen"))
    case = next(r for r in catalog["innova"] if r["slug"] == "hbb-variante-proteina")
    # Forum thread with the authoring team's highlighted answer.
    people["ana.demo@mail.pucv.cl"].call("POST", "/api/comments", {"project_id": "incentiva", "slug": retina["slug"], "body": "¿Cómo financiarían el traslado del equipo?"})
    for c in admin.call("GET", "/api/admin/pending")["comments"]:
        admin.call("POST", "/api/admin/review", {"kind": "comment", "id": c["id"], "decision": "publish"})
    first = admin.call("GET", f"/api/projects/incentiva/resources/{retina['slug']}/comments")[0]
    people["tomas.demo@mail.pucv.cl"].call("POST", "/api/comments", {"project_id": "incentiva", "slug": retina["slug"], "parent_id": first["id"],
                                                                     "body": "Con el convenio comunal de traslado que ya existe para operativos."})
    for c in admin.call("GET", "/api/admin/pending")["comments"]:
        admin.call("POST", "/api/admin/review", {"kind": "comment", "id": c["id"], "decision": "publish"})
    # Control questions on a case and on a student capsule, with answers.
    quiz = "¿Qué cambia primero en el caso?\n* La secuencia del gen\nLa dieta\nExplicación: la variante está en el ADN.\n\n¿Qué confirma el diagnóstico?\nUna radiografía\n* Un estudio molecular"
    for r in (case, fmr1):
        admin.call("POST", "/api/admin/resources/update", {"id": r["id"], "title": r["title"], "category": r["category"], "summary": r["summary"],
                                                           "tags": ", ".join(r["tags"]), "status": "published", "quiz": quiz})
    for email, answers in (("diego.demo@mail.pucv.cl", [0, 1]), ("valentina.demo@mail.pucv.cl", [0, 0]), ("martin.demo@mail.pucv.cl", [1, 1])):
        people[email].call("POST", f"/api/quiz/{case['id']}", {"answers": answers})
    # Peer reviews.
    for email, scores in (("ana.demo@mail.pucv.cl", [4, 3, 3, 3, 4]), ("luis.demo@mail.pucv.cl", [3, 3, 4, 3, 3])):
        keys = ["territory", "evidence", "feasibility", "ethics", "communication"]
        people[email].call("POST", f"/api/peer/{retina['id']}", {"scores": dict(zip(keys, scores)), "strength": "La simulación del flujo es muy clara.",
                                                                 "suggestion": "Agregar cuánto costaría mantenerlo un año."})
    for email in ("valentina.demo@mail.pucv.cl", "martin.demo@mail.pucv.cl"):
        people[email].call("POST", f"/api/peer/{fmr1['id']}", {"scores": {"flow": 4, "disease": 3, "technique": 4, "peer": 3, "rigor": 4},
                                                               "strength": "El modelo 3D ayuda mucho.", "suggestion": "Explicar mejor el Southern blot."})
    # Exit ticket and pre-session questions, with answers and categories.
    for project, kind, title, replies in (
            ("innova", "previa", "Antes de la sesión del 9 de noviembre", [["No entiendo la metilación", "PCR", "¿Cómo se lee un Southern?"],
                                                                            ["La metilación del promotor", "Southern blot", "¿Qué control uso?"],
                                                                            ["Los controles de la PCR", "RT-qPCR", "¿Por qué no basta la PCR?"]]),
            ("incentiva", "salida", "Sesión del 2 de noviembre", [["El storyboard ordena el video", "Indicadores", "Simular con maqueta; riesgo: tiempo"],
                                                                   ["Partir del problema", "Buscar evidencia", "Role-play; riesgo: que parezca actuado"]])):
        t = admin.call("POST", "/api/admin/tickets", {"project_id": project, "title": title, "kind": kind})
        members = [e for e, s in people.items() if any(e == k for k in people)]
        senders = [e for e in people if (project == "innova") == (e.split(".")[0] in ("camila", "diego", "valentina", "martin"))]
        for email, answer in zip(senders, replies):
            people[email].call("POST", f"/api/tickets/{t['code']}/answer", {"answers": answer})
    tickets = admin.call("GET", "/api/admin/tickets")
    pre = next(t for t in tickets if t["kind"] == "previa")
    responses = admin.call("GET", f"/api/admin/tickets/{pre['id']}/responses")
    for answer, tag in zip(responses["answers"], ["Metilación", "Metilación", "Controles"]):
        admin.call("POST", f"/api/admin/tickets/{pre['id']}/tag", {"answer_id": answer["id"], "question": 0, "tag": tag})
    # KPSI entry and exit surveys for Innova.
    for moment, rows in (("entrada", [[1, 2, 1, 1, 2, 1, 1, 1, 2, 1, 1, 1, 2, 1, 2, 2, 3], [2, 2, 1, 2, 1, 1, 2, 1, 1, 1, 1, 2, 1, 1, 2, 3, 3]]),
                         ("salida", [[3, 3, 3, 2, 3, 3, 3, 3, 3, 3, 2, 3, 3, 3, 3, 4, 4], [3, 4, 3, 3, 3, 3, 3, 3, 3, 2, 3, 3, 3, 3, 3, 4, 4]])):
        sv = admin.call("POST", "/api/admin/surveys", {"project_id": "innova", "kind": "kpsi", "moment": moment, "title": f"KPSI de {moment}"})
        for email, values in zip(("diego.demo@mail.pucv.cl", "martin.demo@mail.pucv.cl"), rows):
            people[email].call("POST", f"/api/surveys/{sv['code']}/answer", {"values": values})
    print("Datos de demostración cargados.")
    for (project, section), code in codes.items():
        print(f"  Código del curso {project}{' · ' + section if section else ''}: {code}")


if __name__ == "__main__":
    main()
