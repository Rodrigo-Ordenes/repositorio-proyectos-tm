#!/usr/bin/env python3
"""Single-host app for two PUCV learning projects with SQLite and email links."""
from __future__ import annotations

import hashlib
import base64
import binascii
import csv
import hmac
import io
import html
import sys
import json
import os
import re
import secrets
import smtplib
import ssl
import sqlite3
import tempfile
import threading
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from xml.etree import ElementTree
from email.message import EmailMessage
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import qr

ROOT = Path(__file__).resolve().parent


def load_env_file(path: Path):
    """KEY=value lines shared by the hosting app and its cron jobs, kept outside the repository; the real environment wins."""
    if not path.is_file(): return
    if path.stat().st_mode & 0o077:
        print(f"Aviso: {path} debe tener permisos 600 (contiene secretos).", file=sys.stderr, flush=True)
    for line in path.read_text(encoding="utf-8").splitlines():
        key, sep, value = line.strip().partition("=")
        if not sep or key.startswith("#") or not re.fullmatch(r"[A-Z][A-Z0-9_]*", key.strip()): continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"": value = value[1:-1]
        os.environ.setdefault(key.strip(), value)


load_env_file(Path(os.environ.get("APP_ENV_FILE", ROOT.parent / "repositorio-datos" / "config.env")))
DATA_DIR = ROOT / "data"
DB_PATH = Path(os.environ.get("APP_DB_PATH", DATA_DIR / "repository.sqlite3"))
UPLOAD_DIR = Path(os.environ.get("APP_UPLOAD_DIR", DATA_DIR / "submissions_files"))
PORT = int(os.environ.get("PORT", "8000"))
BASE_URL = os.environ.get("APP_BASE_URL", f"http://localhost:{PORT}").rstrip("/")
ALLOWED_EMAIL_DOMAINS = {d.strip().lower() for d in os.environ.get(
    "PUCV_EMAIL_DOMAINS", "mail.pucv.cl,pucv.cl"
).split(",") if d.strip()}
ADMIN_EMAILS = {email.strip().lower() for email in os.environ.get("PUCV_ADMIN_EMAILS", "").split(",") if email.strip()}
# Emergency ("SOS") sign-in: "correo|sal|hash" from the PUCV_SOS variable or a private file next to the database.
# It never lives in the repository; `python3 server.py codigo-sos correo` creates it.
SOS_FILE = DB_PATH.parent / "sos.txt"


def load_sos():
    raw = os.environ.get("PUCV_SOS", "").strip()
    if not raw and SOS_FILE.exists():
        raw = SOS_FILE.read_text().strip()
    parts = raw.split("|")
    if len(parts) != 3 or "@" not in parts[0] or not re.fullmatch(r"[0-9a-f]{32}", parts[1]) or not re.fullmatch(r"[0-9a-f]{64}", parts[2]):
        return None
    return {"email": parts[0].strip().lower(), "salt": parts[1], "hash": parts[2]}


SOS = load_sos()
if SOS: ADMIN_EMAILS.add(SOS["email"])
PROJECT_ADMIN_EMAILS = {
    "incentiva": {email.strip().lower() for email in os.environ.get("PUCV_INCENTIVA_ADMINS", "").split(",") if email.strip()},
    "innova": {email.strip().lower() for email in os.environ.get("PUCV_INNOVA_ADMINS", "").split(",") if email.strip()},
}
SMTP_HOST = os.environ.get("SMTP_HOST", "")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
SMTP_FROM = os.environ.get("SMTP_FROM", "")
SMTP_SECURITY = os.environ.get("SMTP_SECURITY", "starttls").lower()
DEMO_AUTH = os.environ.get("APP_DEMO_AUTH", "0") == "1"
# Google sign-in uses an OAuth client the course team creates in its own Google Cloud project.
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "").strip()
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "").strip()
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
TRUST_PROXY = os.environ.get("TRUST_PROXY", "0") == "1"
SESSION_SECONDS = 60 * 60 * 12
MAGIC_LINK_SECONDS = 15 * 60
OAUTH_STATE_SECONDS = 10 * 60
CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"

PROJECTS = {
    "incentiva": {
        "name": "Incentiva en el Aula",
        "course": "Metodología de la Investigación",
        "short": "Innovación en salud aplicada al territorio",
        "accent": "forest",
        "kind": "Video-prototipo + Ficha de Evidencia",
        "description": "Diseña una respuesta fundamentada a un desafío sociosanitario real.",
    },
    "innova": {
        "name": "Innova en el Aula",
        "course": "Fundamentos de Diagnóstico Molecular",
        "short": "Casos, prototipos y diagnóstico molecular",
        "accent": "plum",
        "kind": "Cápsula + prototipo 3D + matriz diagnóstica",
        "description": "Explica cómo una alteración molecular se relaciona con un caso y su diagnóstico.",
    },
}
# Course sections (paralelos); each list can be replaced with PUCV_INCENTIVA_SECTIONS / PUCV_INNOVA_SECTIONS.
PROJECT_SECTIONS = {project: [s.strip()[:60] for s in os.environ.get(f"PUCV_{project.upper()}_SECTIONS", default).split(",") if s.strip()]
                    for project, default in (("incentiva", "Bioanálisis,Oftalmología"), ("innova", ""))}
# Structured delivery fields follow each course guide; they shape the published record and its catalog tags.
PROJECT_FIELDS = {
    "innova": [
        {"key": "alteration", "label": "Alteración: gen y variante", "required": True, "placeholder": "Ej.: HBB, variante puntual que cambia un aminoácido"},
        {"key": "process", "label": "Proceso molecular afectado", "required": True, "choices": [
            "Replicación y reparación del ADN", "Transcripción", "Procesamiento del ARN", "Traducción",
            "Regulación epigenética", "Estructura y función de proteínas", "Otro"]},
        {"key": "effect", "label": "Efecto en ADN, ARN o proteína", "required": True, "placeholder": "Qué cambia en la molécula y cómo lo sabemos"},
        {"key": "phenotype", "label": "Cambio celular y manifestación clínica", "required": True, "placeholder": "Cómo ese efecto explica lo que se observa en el caso"},
        {"key": "technique", "label": "Técnica diagnóstica propuesta y por qué", "required": True, "placeholder": "Ej.: PCR, RT-qPCR, secuenciación, Southern blot, ensayo funcional…"},
        {"key": "controls", "label": "Controles y cómo interpretar el resultado", "required": True, "placeholder": "Control positivo, negativo, de extracción o de carga; qué indicaría cada resultado"},
        {"key": "limitations", "label": "Limitaciones de la propuesta", "required": False, "placeholder": "Qué no puede responder la técnica o el prototipo"},
    ],
    "incentiva": [
        {"key": "challenge", "label": "Tipo de desafío", "required": True, "choices": [
            "Acceso rural", "Personas mayores", "Comunidad escolar", "Discapacidad", "Seguimiento", "Detección temprana", "Otro"]},
        {"key": "research_question", "label": "Pregunta de investigación", "required": True, "placeholder": "¿Qué problema, población y resultado quieren investigar?"},
        {"key": "evidence", "label": "Evidencia científica (mínimo 3 fuentes)", "required": True, "placeholder": "Una por línea: autor/año, hallazgo relevante y enlace o referencia APA 7. Prioricen fuentes oficiales, revisiones y estudios de Chile o Latinoamérica."},
        {"key": "community", "label": "Personas o comunidad afectada", "required": True, "placeholder": "A quién afecta el problema y qué muestra la evidencia"},
        {"key": "solution", "label": "Solución y cómo funcionaría", "required": True, "placeholder": "Qué propone el equipo, cómo se usaría y qué recurso disponible aprovecharía"},
        {"key": "indicator", "label": "Resultado esperado e indicador", "required": True, "placeholder": "Qué cambiaría y cómo lo medirían"},
        {"key": "limitations", "label": "Limitación o condición necesaria", "required": True, "placeholder": "Qué se necesita para implementarla o qué no resuelve"},
    ],
}
# Projects whose consented student work any signed-in PUCV account can read (vitrina / modo lector), e.g. "innova".
OPEN_PROJECTS = [p.strip() for p in os.environ.get("PUCV_OPEN_PROJECTS", "").split(",") if p.strip() in PROJECTS]
GUIDE_QUESTIONS = {
    "innova": "¿Qué evidencia conecta el hallazgo del caso con la alteración molecular y qué control ayudaría a confiar en el resultado?",
    "incentiva": "¿Qué evidencia muestra que la solución responde a una necesidad real de la comunidad y qué indicador usarían para comprobarlo?",
}
# The three standard exit-ticket questions from «Tiquetes de Salida» (synthesis, metacognition, risk and innovation).
EXIT_TICKET_QUESTIONS = {
    project: [f"¿Cuál es la idea o concepto más importante que te llevas de esta sesión para resolver {goal}?",
              "¿En qué conceptos o procedimientos abordados hoy te gustaría profundizar para fortalecer tu formación en la carrera?",
              "¿Qué innovación metodológica de las abordadas hoy considerarías aplicar en tus propias prácticas y qué riesgos implicaría?"]
    for project, goal in (("innova", "el caso clínico"), ("incentiva", "el desafío de tu equipo"))
}
# Peer-review rubric: Incentiva uses the criteria of its project form, Innova its learning outcomes (RA1–RA4).
PEER_LEVELS = ["Insuficiente", "En desarrollo", "Logrado", "Destacado"]
PEER_RUBRIC = {
    "incentiva": [
        {"key": "territory", "label": "Pertinencia territorial", "hint": "El problema y la comunidad afectada están bien delimitados."},
        {"key": "evidence", "label": "Fundamento científico", "hint": "La solución se apoya en evidencia citada y bien interpretada."},
        {"key": "feasibility", "label": "Utilidad, factibilidad y sostenibilidad", "hint": "Se entiende cómo funcionaría y qué se necesita para mantenerla."},
        {"key": "ethics", "label": "Accesibilidad y ética", "hint": "Considera a quién deja fuera, el consentimiento y los datos."},
        {"key": "communication", "label": "Comunicación del video", "hint": "Claro, en máximo 5 minutos, con subtítulos y una simulación comprensible."},
    ],
    "innova": [
        {"key": "flow", "label": "Alteración y flujo molecular (RA1)", "hint": "Explica qué cambia en el ADN, ARN o proteína."},
        {"key": "disease", "label": "Relación con la patología (RA2)", "hint": "Conecta el efecto molecular con el cambio celular y el cuadro clínico."},
        {"key": "technique", "label": "Técnica y controles (RA3)", "hint": "Justifica la técnica, sus controles y cómo interpretar el resultado."},
        {"key": "peer", "label": "Explicación para un par", "hint": "Lo entendería un estudiante de otro curso."},
        {"key": "rigor", "label": "Rigor y uso ético de la IA (RA4)", "hint": "La IA está declarada y el contenido es correcto."},
    ],
}
KPSI_SCALE = ["No lo sé / nunca lo he escuchado", "Lo he oído, pero tengo dudas", "Lo entiendo, pero no podría explicarlo",
              "Lo domino y puedo explicarlo o aplicarlo"]
AGREEMENT_SCALE = ["Muy en desacuerdo", "En desacuerdo", "Ni de acuerdo ni en desacuerdo", "De acuerdo", "Muy de acuerdo"]
# Items as edited in the panel: «# Dimensión» lines start a group, every other line is an item.
SURVEY_TEMPLATES = {
    "kpsi": {"innova": """# Conceptual (cátedra)
Comprendo los conceptos fundamentales del Diagnóstico Molecular y su rol en la salud humana.
Explico el Dogma Central de la Biología Molecular y las excepciones o variaciones del flujo de información.
Describo la estructura, función y niveles de organización de los ácidos nucleicos (ADN/ARN), cromosomas y genomas.
Analizo los mecanismos moleculares de replicación, recombinación y reparación del ADN.
Distingo las etapas de transcripción, procesamiento y maduración de los transcritos de ARN.
Explico la traducción de mARN, las características del Código Genético y las modificaciones co- y post-traduccionales.
Identifico los principios de regulación de la expresión génica en organismos eucariontes y procariontes.
Comprendo los conceptos fundamentales y los mecanismos moleculares de la Epigenética.
Manejo los principios teóricos para la extracción, purificación y cuantificación de ácidos nucleicos.
Explico el fundamento teórico de la síntesis de ADN complementario (cDNA) y la técnica de RT-PCR.
# Procedimental (laboratorio)
Aplico los pasos para la extracción de ADN genómico desde células humanas según protocolo.
Ejecuto las fases del protocolo para la extracción de ARN desde células humanas.
Utilizo espectrofotometría para la cuantificación y evaluación de pureza e integridad de ácidos nucleicos.
Diferencio las condiciones operativas y reactivos críticos necesarios para el montaje de reacciones moleculares.
# Actitudinal (bioseguridad y ética)
Cumplo rigurosamente las normas de bioseguridad, uso de EPP y manejo adecuado de equipamiento e insumos en el laboratorio.
Demuestro meticulosidad y rigor en la técnica para prevenir contaminación por nucleasas y minimizar la variación analítica.
Trabajo de manera colaborativa, responsable y respetuosa en las actividades de laboratorio y talleres grupales.""",
             # No KPSI for Incentiva exists in the course files; these items follow its project form and must be reviewed.
             "incentiva": """# Investigación
Formulo una pregunta de investigación a partir de un problema sociosanitario del territorio.
Busco y selecciono evidencia científica pertinente para fundamentar una propuesta.
Distingo los tipos de estudio y qué puede responder cada uno.
Identifico los resguardos éticos que requiere una propuesta con personas o comunidades.
# Innovación
Diseño una solución acotada y factible para una necesidad de salud de una comunidad.
Defino un indicador para evaluar si una propuesta produce el resultado esperado.
Comunico una propuesta en un video breve, claro y accesible."""},
    # Provisional: replace with the items of the validated instrument of Bravo Cofré et al. (2024) once the course has it.
    "percepcion": {project: """# Contenido
Los videos o cápsulas fueron coherentes con los objetivos de la asignatura.
La duración de los videos (máximo 5 minutos) fue adecuada para el contenido.
Crear el video en equipo me ayudó a comprender mejor los contenidos.
Ver los trabajos de otros equipos me ayudó a aprender.
# Recursos y participación
Las guías y herramientas del repositorio facilitaron la producción del video.
El foro, las preguntas de control y la coevaluación me ayudaron a mejorar mi trabajo.
El uso declarado de IA fue un apoyo y no reemplazó el trabajo del equipo.
# Valoración general
Recomendaría esta metodología para otras asignaturas.""" for project in PROJECTS},
}
# Course cases are simulated (no patient data); their text ships in seeds/ so deploying never needs the course folder.
CASES_DIR = Path(os.environ.get("APP_CASES_DIR", ROOT / "Innova en el aula 2S 2026"))
SEED_CASES = ROOT / "seeds" / "casos_innova.json"
INNOVA_CASES = [
    ("innova", "hbb-variante-proteina", "HBB: de la variante al cambio funcional", "Caso clínico-molecular", "Caso de anemia con alteración de HBB. El equipo conecta la variante con la proteína, el fenotipo y una estrategia diagnóstica.", ["HBB", "Variación genética", "Proteína"], "Caso_Clinico_1_*.docx"),
    ("innova", "hbb-procesamiento-arn", "HBB: cuando cambia el procesamiento del ARN", "Caso clínico-molecular", "Caso de anemia microcítica con ferritina conservada. Analiza procesamiento del ARN y cómo distinguir causas moleculares.", ["HBB", "ARN", "Procesamiento"], "Caso_Clinico_2_*.docx"),
    ("innova", "fmr1-regulacion-epigenetica", "FMR1: el gen está presente, su expresión cambia", "Caso clínico-molecular", "El estudio encuentra un aumento de repeticiones CGG y cambios de metilación. Relaciona regulación, expresión y fenotipo.", ["FMR1", "Epigenética", "Expresión génica"], "Caso_Clinico_3_*.docx"),
    ("innova", "xpc-reparacion-adn", "XPC: cuando el daño permanece en el ADN", "Caso clínico-molecular", "Compara la reparación del daño inducido por radiación UV en células control y del paciente.", ["XPC", "Reparación del ADN", "Daño UV"], "Caso_Clinico_4_*.docx"),
    ("innova", "pah-estructura-funcion", "PAH: proteína presente, función alterada", "Caso clínico-molecular", "La enzima se sintetiza, pero una variante cambia su función. Integra estructura, actividad y consecuencias metabólicas.", ["PAH", "Estructura-función", "Enzimología"], "Caso_Clinico_5_*.docx"),
]
# Criteria the Incentiva project form uses to choose among alternative solutions (scored 1 to 3).
ALTERNATIVE_CRITERIA = ["Pertinencia territorial", "Utilidad", "Accesibilidad", "Factibilidad", "Ética", "Fundamento científico", "Sostenibilidad"]
# Flipped-classroom questions answered before a session (Innova's plan: arrive with the doubt already identified).
PRE_SESSION_QUESTIONS = {
    "innova": ["¿Qué parte del caso o del mecanismo molecular todavía no entiendes?",
               "¿Qué técnica crees que serviría para confirmar el diagnóstico y por qué?",
               "Escribe una pregunta que quieras resolver en la sesión."],
    "incentiva": ["¿Qué parte del desafío o de la comunidad todavía no tienes clara?",
                  "¿Qué evidencia crees que necesita tu equipo y dónde la buscarías?",
                  "Escribe una pregunta que quieras resolver en la sesión."],
}
DEFAULT_COHORT = os.environ.get("APP_COHORT", "2026-2").strip() or "2026-2"
STOPWORDS = set("""a al algo ante antes como con contra cual cuando de del desde donde durante el ella ellas ellos en entre era es esa ese eso esta este esto estos fue ha hay la las le les lo los mas me mi mis muy ni no nos o otra otro para pero poco por porque que quien se sea ser si sin sobre su sus tambien te tiene todo tu un una uno unos y ya yo hoy creo sesion
cual cuales como mas menos mucho puede pueden seria serian hacer hace tener tengo""".split())
UPLOAD_SUFFIXES = (".pdf", ".docx", ".pptx", ".xlsx", ".odt", ".txt")
BACKUP_DIR = Path(os.environ.get("APP_BACKUP_DIR", DB_PATH.parent / "backups"))
AUDIT_RETENTION_DAYS = 180
BACKUP_REMINDER_DAYS = 7
BACKUP_KEEP = max(1, int(os.environ.get("APP_BACKUP_KEEP", "14")))
BACKUP_HOURS = int(os.environ.get("APP_BACKUP_HOURS", "24"))


def connect():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB_PATH, timeout=10)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    # Erased personal data is overwritten on disk instead of lingering in free pages.
    db.execute("PRAGMA secure_delete = ON")
    db.execute("PRAGMA busy_timeout = 5000")
    return db


def extract_docx_text(path: Path) -> str:
    """Extract readable paragraphs and table rows from the supplied case files."""
    if not path.exists():
        return ""
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    with zipfile.ZipFile(path) as archive:
        root = ElementTree.fromstring(archive.read("word/document.xml"))
    body = root.find("w:body", ns)
    blocks = []
    for item in body:
        if item.tag.endswith("}p"):
            text = "".join(node.text or "" for node in item.findall(".//w:t", ns)).strip()
            if text: blocks.append(text)
        elif item.tag.endswith("}tbl"):
            for row in item.findall("w:tr", ns):
                cells = []
                for cell in row.findall("w:tc", ns):
                    cell_text = " ".join("".join(node.text or "" for node in p.findall(".//w:t", ns)).strip()
                                          for p in cell.findall("w:p", ns)).strip()
                    if cell_text: cells.append(cell_text)
                if cells: blocks.append(" | ".join(cells))
    return "\n\n".join(blocks)


def case_text(pattern) -> str:
    case_file = next(CASES_DIR.glob(pattern), None) if CASES_DIR.is_dir() else None
    return extract_docx_text(case_file) if case_file else ""


# Response content and participation are stored separately. This prevents direct joins in routine reports,
# but does not prove anonymity against a privileged database operator or timing/backup analysis.
ANONYMOUS_TABLES = {
    "exit_ticket_answers": """CREATE TABLE exit_ticket_answers (
      id TEXT PRIMARY KEY, ticket_id INTEGER NOT NULL REFERENCES exit_tickets(id) ON DELETE CASCADE,
      answers TEXT NOT NULL, answered_on TEXT NOT NULL) WITHOUT ROWID""",
    "exit_ticket_respondents": """CREATE TABLE exit_ticket_respondents (
      ticket_id INTEGER NOT NULL REFERENCES exit_tickets(id) ON DELETE CASCADE,
      user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE, PRIMARY KEY(ticket_id, user_id)) WITHOUT ROWID""",
    "survey_answers": """CREATE TABLE survey_answers (
      id TEXT PRIMARY KEY, survey_id INTEGER NOT NULL REFERENCES surveys(id) ON DELETE CASCADE,
      answer_values TEXT NOT NULL, comment TEXT NOT NULL DEFAULT '', answered_on TEXT NOT NULL) WITHOUT ROWID""",
    "survey_respondents": """CREATE TABLE survey_respondents (
      survey_id INTEGER NOT NULL REFERENCES surveys(id) ON DELETE CASCADE,
      user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE, PRIMARY KEY(survey_id, user_id)) WITHOUT ROWID""",
}


def ensure_anonymous_tables(db) -> bool:
    """Create the anonymous tables, rebuilding older rowid versions; returns True when old pages must be vacuumed."""
    rebuilt = False
    for name, ddl in ANONYMOUS_TABLES.items():
        row = db.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone()
        if row and "WITHOUT ROWID" in row[0].upper(): continue
        if not row:
            db.execute(ddl); continue
        columns = ",".join(r[1] for r in db.execute(f"PRAGMA table_info({name})"))
        db.execute(f"ALTER TABLE {name} RENAME TO {name}_old")
        db.execute(ddl)
        # Orphans (rows whose ticket, survey or account no longer exists) carry no information and would break the copy.
        parent = "ticket_id IN (SELECT id FROM exit_tickets)" if name.startswith("exit") else "survey_id IN (SELECT id FROM surveys)"
        people = " AND user_id IN (SELECT id FROM users)" if name.endswith("respondents") else ""
        db.execute(f"INSERT INTO {name}({columns}) SELECT {columns} FROM {name}_old WHERE {parent}{people}")
        db.execute(f"DROP TABLE {name}_old")
        rebuilt = True
    return rebuilt


def init_db():
    db_connection = connect()
    db_connection.execute("PRAGMA journal_mode = WAL")
    with db_connection as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
          id INTEGER PRIMARY KEY,
          provider_subject TEXT UNIQUE,
          email TEXT NOT NULL UNIQUE,
          display_name TEXT NOT NULL,
          role TEXT NOT NULL DEFAULT 'student' CHECK(role IN ('student','editor','admin')),
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS sessions (
          token_hash TEXT PRIMARY KEY,
          user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
          expires_at INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS email_login_tokens (
          id INTEGER PRIMARY KEY,
          email TEXT NOT NULL,
          token_hash TEXT NOT NULL UNIQUE,
          requested_at INTEGER NOT NULL,
          expires_at INTEGER NOT NULL,
          used_at INTEGER
        );
        CREATE TABLE IF NOT EXISTS projects (
          id TEXT PRIMARY KEY,
          name TEXT NOT NULL,
          course TEXT NOT NULL,
          description TEXT NOT NULL,
          accent TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS project_memberships (
          id INTEGER PRIMARY KEY,
          user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
          project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
          status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','active','denied')),
          requested_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          reviewed_at TEXT,
          reviewed_by INTEGER REFERENCES users(id),
          UNIQUE(user_id, project_id)
        );
        CREATE TABLE IF NOT EXISTS resources (
          id INTEGER PRIMARY KEY,
          project_id TEXT NOT NULL REFERENCES projects(id),
          slug TEXT NOT NULL,
          title TEXT NOT NULL,
          category TEXT NOT NULL,
          summary TEXT NOT NULL,
          content TEXT NOT NULL DEFAULT '',
          tags TEXT NOT NULL DEFAULT '[]',
          media_url TEXT,
          source_submission_id INTEGER,
          file_storage_key TEXT NOT NULL DEFAULT '',
          file_filename TEXT NOT NULL DEFAULT '',
          status TEXT NOT NULL DEFAULT 'published' CHECK(status IN ('draft','review','published')),
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          UNIQUE(project_id, slug)
        );
        CREATE TABLE IF NOT EXISTS comments (
          id INTEGER PRIMARY KEY,
          resource_id INTEGER NOT NULL REFERENCES resources(id) ON DELETE CASCADE,
          user_id INTEGER NOT NULL REFERENCES users(id),
          body TEXT NOT NULL CHECK(length(body) BETWEEN 1 AND 1200),
          status TEXT NOT NULL DEFAULT 'published' CHECK(status IN ('review','published','hidden')),
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS moderation_events (
          id INTEGER PRIMARY KEY,
          actor_user_id INTEGER NOT NULL REFERENCES users(id),
          entity_type TEXT NOT NULL CHECK(entity_type IN ('submission','comment')),
          entity_id INTEGER NOT NULL,
          action TEXT NOT NULL CHECK(action IN ('publish','reject','hide')),
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS submissions (
          id INTEGER PRIMARY KEY,
          project_id TEXT NOT NULL REFERENCES projects(id),
          user_id INTEGER NOT NULL REFERENCES users(id),
          team_name TEXT NOT NULL DEFAULT '',
          title TEXT NOT NULL,
          summary TEXT NOT NULL,
          video_url TEXT,
          evidence_url TEXT,
          evidence_storage_key TEXT NOT NULL DEFAULT '',
          evidence_filename TEXT NOT NULL DEFAULT '',
          project_fields TEXT NOT NULL DEFAULT '{}',
          ai_declaration TEXT NOT NULL DEFAULT '',
          consent_confirmed INTEGER NOT NULL DEFAULT 0 CHECK(consent_confirmed IN (0,1)),
          status TEXT NOT NULL DEFAULT 'review' CHECK(status IN ('review','approved','published','rejected')),
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS resources_project_status ON resources(project_id, status);
        CREATE INDEX IF NOT EXISTS comments_resource_status ON comments(resource_id, status);
        CREATE INDEX IF NOT EXISTS sessions_expiry ON sessions(expires_at);
        CREATE INDEX IF NOT EXISTS email_tokens_rate_limit ON email_login_tokens(email, requested_at);
        CREATE INDEX IF NOT EXISTS memberships_project_status ON project_memberships(project_id, status);
        CREATE TABLE IF NOT EXISTS oauth_states (
          state_hash TEXT PRIMARY KEY,
          code_verifier TEXT NOT NULL,
          nonce TEXT NOT NULL,
          created_at INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS join_codes (
          id INTEGER PRIMARY KEY,
          code TEXT NOT NULL UNIQUE,
          project_id TEXT NOT NULL REFERENCES projects(id),
          label TEXT NOT NULL DEFAULT '',
          created_by INTEGER REFERENCES users(id),
          created_at INTEGER NOT NULL,
          expires_at INTEGER NOT NULL,
          max_uses INTEGER,
          uses INTEGER NOT NULL DEFAULT 0,
          active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1))
        );
        CREATE TABLE IF NOT EXISTS access_codes (
          id INTEGER PRIMARY KEY,
          email TEXT NOT NULL,
          code_hash TEXT NOT NULL,
          salt TEXT NOT NULL,
          project_id TEXT REFERENCES projects(id),
          created_by INTEGER REFERENCES users(id),
          created_at INTEGER NOT NULL,
          expires_at INTEGER NOT NULL,
          revoked_at INTEGER,
          last_used_at INTEGER
        );
        CREATE TABLE IF NOT EXISTS rate_events (
          bucket TEXT NOT NULL,
          created_at INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS exit_tickets (
          id INTEGER PRIMARY KEY,
          project_id TEXT NOT NULL REFERENCES projects(id),
          code TEXT NOT NULL UNIQUE,
          title TEXT NOT NULL,
          questions TEXT NOT NULL,
          created_by INTEGER REFERENCES users(id),
          created_at INTEGER NOT NULL,
          closes_at INTEGER NOT NULL,
          feedback_url TEXT NOT NULL DEFAULT '',
          active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1))
        );
        CREATE TABLE IF NOT EXISTS quiz_attempts (
          resource_id INTEGER NOT NULL REFERENCES resources(id) ON DELETE CASCADE,
          user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
          answers TEXT NOT NULL,
          score INTEGER NOT NULL,
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          PRIMARY KEY(resource_id, user_id)
        );
        CREATE TABLE IF NOT EXISTS peer_reviews (
          id INTEGER PRIMARY KEY,
          resource_id INTEGER NOT NULL REFERENCES resources(id) ON DELETE CASCADE,
          reviewer_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
          scores TEXT NOT NULL,
          strength TEXT NOT NULL DEFAULT '',
          suggestion TEXT NOT NULL DEFAULT '',
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          UNIQUE(resource_id, reviewer_id)
        );
        -- Course editors assigned from the panel; PUCV_*_ADMINS in the environment keep working alongside.
        CREATE TABLE IF NOT EXISTS staff_roles (
          email TEXT NOT NULL,
          project_id TEXT NOT NULL REFERENCES projects(id),
          created_by INTEGER REFERENCES users(id),
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          PRIMARY KEY(email, project_id)
        );
        CREATE TABLE IF NOT EXISTS surveys (
          id INTEGER PRIMARY KEY,
          project_id TEXT NOT NULL REFERENCES projects(id),
          code TEXT NOT NULL UNIQUE,
          kind TEXT NOT NULL CHECK(kind IN ('kpsi','percepcion')),
          moment TEXT NOT NULL CHECK(moment IN ('entrada','salida','cierre')),
          title TEXT NOT NULL,
          items TEXT NOT NULL,
          scale TEXT NOT NULL,
          created_by INTEGER REFERENCES users(id),
          created_at INTEGER NOT NULL,
          closes_at INTEGER NOT NULL,
          active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1))
        );
        CREATE TABLE IF NOT EXISTS settings (
          key TEXT PRIMARY KEY,
          value TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS audit_events (
          id INTEGER PRIMARY KEY,
          event_type TEXT NOT NULL,
          actor_email TEXT NOT NULL DEFAULT '',
          subject_email TEXT NOT NULL DEFAULT '',
          project_id TEXT NOT NULL DEFAULT '',
          entity_type TEXT NOT NULL DEFAULT '',
          entity_id INTEGER,
          ip_hash TEXT NOT NULL DEFAULT '',
          created_at INTEGER NOT NULL
        );
        -- Teacher-assigned categories for exit-ticket answers (keyed by the answer's random id, never by person).
        CREATE TABLE IF NOT EXISTS exit_ticket_tags (
          answer_id TEXT NOT NULL,
          question INTEGER NOT NULL,
          tag TEXT NOT NULL,
          PRIMARY KEY(answer_id, question)
        ) WITHOUT ROWID;
        CREATE INDEX IF NOT EXISTS access_codes_email ON access_codes(email, revoked_at, expires_at);
        CREATE INDEX IF NOT EXISTS rate_events_bucket ON rate_events(bucket, created_at);
        CREATE INDEX IF NOT EXISTS audit_events_entity ON audit_events(entity_type, entity_id, created_at);
        CREATE INDEX IF NOT EXISTS audit_events_created_at ON audit_events(created_at);
        """)
        rebuilt = ensure_anonymous_tables(db)
        add_missing_columns(db, "submissions", (
            ("team_name", "TEXT NOT NULL DEFAULT ''"), ("evidence_storage_key", "TEXT NOT NULL DEFAULT ''"),
            ("evidence_filename", "TEXT NOT NULL DEFAULT ''"), ("review_note", "TEXT NOT NULL DEFAULT ''"), ("reviewed_at", "TEXT"),
            ("section", "TEXT NOT NULL DEFAULT ''"), ("members", "TEXT NOT NULL DEFAULT '[]'"),
            ("member_emails", "TEXT NOT NULL DEFAULT '[]'"), ("has_subtitles", "INTEGER NOT NULL DEFAULT 0"),
            ("showcase_consent", "INTEGER NOT NULL DEFAULT 0")))
        add_missing_columns(db, "comments", (("parent_id", "INTEGER"), ("badge", "TEXT NOT NULL DEFAULT ''")))
        add_missing_columns(db, "submissions", (("cohort", "TEXT NOT NULL DEFAULT ''"), ("alternatives", "TEXT NOT NULL DEFAULT '{}'"),
                                                ("model_storage_key", "TEXT NOT NULL DEFAULT ''"), ("model_filename", "TEXT NOT NULL DEFAULT ''")))
        add_missing_columns(db, "exit_tickets", (("kind", "TEXT NOT NULL DEFAULT 'salida'"), ("cohort", "TEXT NOT NULL DEFAULT ''")))
        for table in ("surveys", "project_memberships", "join_codes"):
            add_missing_columns(db, table, (("cohort", "TEXT NOT NULL DEFAULT ''"),))
        # Rows created before cohorts existed belong to the first cohort.
        first = cohorts(db)[0]["name"]
        for table in ("submissions", "exit_tickets", "surveys", "project_memberships", "join_codes"):
            db.execute(f"UPDATE {table} SET cohort=? WHERE cohort=''", (first,))
        # A returned (rejected) delivery must not block the team from sending its corrected version.
        db.execute("DROP INDEX IF EXISTS submissions_one_final_per_team")
        # Teams in separate course sections, or in another cohort, may use the same label (for example, "Grupo 1").
        db.execute("DROP INDEX IF EXISTS submissions_one_open_per_team")
        add_missing_columns(db, "resources", (
            ("source_submission_id", "INTEGER"), ("file_storage_key", "TEXT NOT NULL DEFAULT ''"),
            ("file_filename", "TEXT NOT NULL DEFAULT ''"), ("edited_at", "TEXT"),
            ("guide_question", "TEXT NOT NULL DEFAULT ''"), ("quiz", "TEXT NOT NULL DEFAULT '[]'")))
        add_missing_columns(db, "join_codes", (("section", "TEXT NOT NULL DEFAULT ''"), ("roster", "TEXT NOT NULL DEFAULT ''")))
        add_missing_columns(db, "submissions", (("cohort", "TEXT NOT NULL DEFAULT ''"),))
        db.execute("""CREATE UNIQUE INDEX IF NOT EXISTS submissions_open_team_per_cohort ON submissions(project_id, cohort, lower(trim(section)),
          lower(trim(team_name))) WHERE team_name <> '' AND status <> 'rejected'""")
        add_missing_columns(db, "project_memberships", (("section", "TEXT NOT NULL DEFAULT ''"), ("revoked", "INTEGER NOT NULL DEFAULT 0")))
        for slug, p in PROJECTS.items():
            db.execute("""INSERT INTO projects(id,name,course,description,accent)
              VALUES(?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name,
              course=excluded.course,description=excluded.description,accent=excluded.accent""",
              (slug, p["name"], p["course"], p["description"], p["accent"]))

        cases = json.loads(SEED_CASES.read_text(encoding="utf-8")) if SEED_CASES.exists() else {}
        for project, slug, title, category, summary, tags, case_pattern in INNOVA_CASES:
            content = cases.get(slug) or case_text(case_pattern)
            db.execute("""INSERT INTO resources(project_id,slug,title,category,summary,content,tags)
              VALUES(?,?,?,?,?,?,?) ON CONFLICT(project_id,slug) DO UPDATE SET
              title=excluded.title,category=excluded.category,summary=excluded.summary,
              content=CASE WHEN excluded.content<>'' THEN excluded.content ELSE resources.content END,
              tags=excluded.tags WHERE resources.edited_at IS NULL""",
              (project, slug, title, category, summary, content, json.dumps(tags, ensure_ascii=False)))
        # Seed teacher-reviewed challenge drafts on first launch, with no CLI step required.
        # INSERT OR IGNORE preserves any edits, publication status, or removal made in the dashboard.
        challenge_seed = ROOT / "seeds" / "desafios_incentiva.json"
        if challenge_seed.exists():
            for challenge in json.loads(challenge_seed.read_text(encoding="utf-8")):
                db.execute("""INSERT OR IGNORE INTO resources(project_id,slug,title,category,summary,content,tags,status)
                  VALUES('incentiva',?,?,?,?,?,?,'draft')""",
                  (challenge["slug"], challenge["title"], f"Desafío · {challenge['type']}", challenge["summary"],
                   challenge["content"], json.dumps(challenge["tags"], ensure_ascii=False)))
        db.execute("DELETE FROM resources WHERE project_id='incentiva' AND slug IN ('desafio-acceso-rural','desafio-personas-mayores')")
        purge_audit_events(db)
    if rebuilt:
        # Old rowid pages could still hold the insertion order until the file is rewritten.
        db_connection.execute("VACUUM")
    db_connection.close()


def add_missing_columns(db, table, columns):
    existing = {row[1] for row in db.execute(f"PRAGMA table_info({table})")}
    for column, definition in columns:
        if column not in existing: db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def record_audit_event(db, event_type, actor_email="", subject_email="", project_id="", entity_type="", entity_id=None, now=None, ip_hash=""):
    """Store a bounded-retention audit event without tying it to a deletable user row."""
    created_at = int(time.time() if now is None else now)
    purge_audit_events(db, created_at)
    db.execute("""INSERT INTO audit_events(event_type,actor_email,subject_email,project_id,entity_type,entity_id,ip_hash,created_at)
      VALUES(?,?,?,?,?,?,?,?)""", (event_type, actor_email, subject_email, project_id, entity_type, entity_id, ip_hash, created_at))


def audit_ip_hash(db, address):
    """HMAC the client address with a random installation salt stored outside the repository."""
    row = db.execute("SELECT value FROM settings WHERE key='audit_ip_salt'").fetchone()
    if not row:
        db.execute("INSERT OR IGNORE INTO settings(key,value) VALUES('audit_ip_salt',?)", (secrets.token_hex(32),))
        row = db.execute("SELECT value FROM settings WHERE key='audit_ip_salt'").fetchone()
    return hmac.new(bytes.fromhex(row["value"]), str(address or "").encode("utf-8"), hashlib.sha256).hexdigest()


def purge_audit_events(db, now=None):
    now = int(time.time() if now is None else now)
    db.execute("DELETE FROM audit_events WHERE created_at < ?", (now - AUDIT_RETENTION_DAYS * 86400,))


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class UploadError(ValueError):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def decode_upload(file_b64, filename, noun="El archivo"):
    """Return (bytes, safe filename) for an attached course document, or raise UploadError with a user-facing message."""
    if not isinstance(file_b64, str) or len(file_b64) > 11_184_812:
        raise UploadError(f"{noun} debe pesar como máximo 8 MB.", 413)
    try: data = base64.b64decode(file_b64, validate=True)
    except (binascii.Error, ValueError): raise UploadError("No pudimos leer el archivo adjunto.")
    if len(data) > 8 * 1024 * 1024: raise UploadError(f"{noun} debe pesar como máximo 8 MB.", 413)
    name = Path(str(filename or "archivo")[:180].replace("\\", "/")).name
    suffix = Path(name).suffix.lower()
    if suffix not in UPLOAD_SUFFIXES: raise UploadError("Adjunta PDF, DOCX, PPTX, XLSX, ODT o TXT.")
    if suffix == ".pdf" and not data.startswith(b"%PDF-"): raise UploadError("El archivo no parece ser un PDF válido.")
    if suffix in (".docx", ".pptx", ".xlsx", ".odt") and not data.startswith(b"PK\x03\x04"): raise UploadError("El documento Office/ODT no parece válido.")
    if suffix == ".txt":
        try: data.decode("utf-8")
        except UnicodeDecodeError: raise UploadError("El archivo TXT debe estar en UTF-8.")
    return data, name


def clean_tags(raw):
    tags = [t.strip() for t in raw.split(",")] if isinstance(raw, str) else raw if isinstance(raw, list) else []
    return [str(t)[:50] for t in tags if str(t).strip()][:8]


def clean_project_fields(project, raw):
    """Validate a delivery's structured fields against the course guide; returns (fields, error message)."""
    if not isinstance(raw, dict): return None, "Los campos del proyecto no tienen el formato esperado."
    fields = {}
    for spec in PROJECT_FIELDS[project]:
        value = str(raw.get(spec["key"]) or "").strip()[:1500]
        if value and spec.get("choices") and value not in spec["choices"]: return None, f"Elige una opción válida en «{spec['label']}»."
        if spec["required"] and not value: return None, f"Completa «{spec['label']}»."
        if value: fields[spec["key"]] = value
    return fields, ""


def labeled_fields(project, fields):
    """(label, value) pairs in guide order; deliveries sent before the structured form kept one free-text 'details' field."""
    specs = PROJECT_FIELDS.get(project, []) + [{"key": "details", "label": "Detalle de la propuesta"}]
    return [{"label": spec["label"], "value": str(fields[spec["key"]])} for spec in specs if fields.get(spec["key"])]


def clean_members(raw):
    """Team member names and, position by position, the PUCV address written next to each one ('' when none);
    those accounts act as the authoring team."""
    items = raw if isinstance(raw, list) else re.split(r"[\n;]+", str(raw or ""))
    if len(items) == 1 and "@" not in str(items[0]): items = str(items[0]).split(",")
    members, emails = [], []
    for item in items:
        text = str(item)
        found = re.search(r"[^\s<>,;()]+@[^\s<>,;()]+", text)
        email = institutional_email(found.group(0)) if found else ""
        if found: text = text.replace(found.group(0), " ")
        name = " ".join(text.replace("<", " ").replace(">", " ").replace("()", " ").strip(" ,-").split())[:100]
        name = name or (name_from_email(found.group(0)) if found else "")
        if name and name.lower() not in (m.lower() for m in members) and (not email or email not in emails):
            members.append(name); emails.append(email)
    return members[:12], emails[:12]


def video_embed_url(url) -> str:
    """Embeddable player for YouTube (privacy-enhanced domain, captions on) or a Google Drive file; '' for anything else."""
    parsed = urllib.parse.urlparse(str(url or ""))
    if parsed.scheme != "https": return ""
    host = (parsed.hostname or "").lower().removeprefix("www.").removeprefix("m.")
    video_id = ""
    if host == "youtu.be":
        video_id = parsed.path.strip("/").split("/")[0]
    elif host in ("youtube.com", "youtube-nocookie.com"):
        if parsed.path == "/watch": video_id = urllib.parse.parse_qs(parsed.query).get("v", [""])[0]
        elif parsed.path.startswith(("/embed/", "/shorts/", "/live/")): video_id = parsed.path.split("/")[2]
    if re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id):
        return f"https://www.youtube-nocookie.com/embed/{video_id}?rel=0&cc_load_policy=1"
    drive = re.fullmatch(r"/file/d/([A-Za-z0-9_-]{10,})(?:/(?:view|preview|edit))?/?", parsed.path) if host == "drive.google.com" else None
    return f"https://drive.google.com/file/d/{drive.group(1)}/preview" if drive else ""


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs): return None


def drive_sharing_status(url) -> str:
    """'public', 'private', 'missing' or 'unknown' for a Drive file, asked anonymously as a classmate would see it."""
    parsed = urllib.parse.urlparse(str(url or ""))
    found = re.fullmatch(r"/file/d/([A-Za-z0-9_-]{10,})(?:/(?:view|preview|edit))?/?", parsed.path)
    if (parsed.hostname or "").lower() != "drive.google.com" or not found: return "unknown"
    request = urllib.request.Request(f"https://drive.google.com/file/d/{found.group(1)}/view", headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.build_opener(_NoRedirect).open(request, timeout=6) as response:
            return classify_drive_response(response.status)
    except urllib.error.HTTPError as error:
        return classify_drive_response(error.code, error.headers.get("Location", ""))
    except (urllib.error.URLError, TimeoutError, OSError):
        return "unknown"


def classify_drive_response(status, location="") -> str:
    """Anonymous Drive answers measured on 30 real links (Nov 2026): 200 viewable, 401 sign-in required, 404 gone."""
    if status == 200: return "public"
    if status in (401, 403): return "private"
    if status in (301, 302, 303, 307) and urllib.parse.urlparse(location).hostname == "accounts.google.com": return "private"
    if status == 404: return "missing"
    return "unknown"


def parse_quiz(text):
    """Control questions written as blocks separated by a blank line: the question, then one option per line, the correct
    one marked with '*', and optionally a line starting with 'Explicación:'. Returns (questions, error message)."""
    questions = []
    for block in [b for b in re.split(r"\n\s*\n", str(text or "").strip()) if b.strip()][:4]:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        prompt, options, correct, explanation = lines[0][:300], [], None, ""
        for line in lines[1:]:
            if line.lower().startswith("explicación:") or line.lower().startswith("explicacion:"):
                explanation = line.split(":", 1)[1].strip()[:500]
            elif line.startswith("*"):
                correct = len(options); options.append(line[1:].strip()[:200])
            else:
                options.append(line.lstrip("-").strip()[:200])
        if not 2 <= len(options) <= 5 or correct is None:
            return None, f"Revisa la pregunta «{prompt[:60]}»: necesita de 2 a 5 opciones y una marcada con *."
        questions.append({"prompt": prompt, "options": options, "correct": correct, "explanation": explanation})
    if len(questions) > 3: return None, "Usa como máximo 3 preguntas de control."
    return questions, ""


def quiz_text(questions):
    return "\n\n".join("\n".join([q["prompt"]] + [("* " if i == q["correct"] else "") + o for i, o in enumerate(q["options"])]
                                 + ([f"Explicación: {q['explanation']}"] if q.get("explanation") else [])) for q in questions)


def resource_authors(db, resource_id):
    """(submitter id, PUCV addresses listed as members) of the team that authored a published delivery, or None."""
    row = db.execute("""SELECT s.user_id,s.member_emails FROM resources r JOIN submissions s ON s.id=r.source_submission_id
      WHERE r.id=?""", (resource_id,)).fetchone()
    return (row["user_id"], json.loads(row["member_emails"] or "[]")) if row else None


def is_author(authors, user) -> bool:
    return bool(authors) and (authors[0] == user["id"] or user["email"] in authors[1])


def peer_summary(rubric, score_sets):
    averages = []
    for criterion in rubric:
        values = [s[criterion["key"]] for s in score_sets if isinstance(s.get(criterion["key"]), int)]
        averages.append({"key": criterion["key"], "label": criterion["label"], "average": round(sum(values) / len(values), 2) if values else None})
    known = [a["average"] for a in averages if a["average"] is not None]
    return {"count": len(score_sets), "averages": averages, "overall": round(sum(known) / len(known), 2) if known else None}


def parse_survey_items(text):
    items, dimension = [], ""
    for line in str(text or "").splitlines():
        line = line.strip()
        if line.startswith("#"): dimension = line.lstrip("#").strip()[:120]
        elif line: items.append({"dimension": dimension, "text": line[:300]})
    return items[:40]


def survey_results(items, scale, rows):
    """Per-item mean, distribution and share at the top two levels; rows are lists of 1-based levels."""
    results = []
    for index, item in enumerate(items):
        values = [r[index] for r in rows if index < len(r) and isinstance(r[index], int)]
        results.append({**item, "count": len(values), "mean": round(sum(values) / len(values), 2) if values else None,
                        "top_share": round(sum(v >= len(scale) - 1 for v in values) / len(values), 2) if values else None,
                        "distribution": [values.count(level) for level in range(1, len(scale) + 1)]})
    return results


MIN_SHARE_N = 5


def level_shares(distribution, min_n=MIN_SHARE_N):
    """Whole percentages per level that add up to 100 (largest remainder, ties to the lower level).
    With fewer than min_n answers the shares are withheld: they could reveal individual answers."""
    n = sum(distribution)
    if n < min_n: return {"n": n, "percent": None}
    raw = [100 * count / n for count in distribution]
    percent = [int(x) for x in raw]
    for index in sorted(range(len(raw)), key=lambda i: (-(raw[i] - percent[i]), i))[:100 - sum(percent)]:
        percent[index] += 1
    return {"n": n, "percent": percent}


def project_indicators(db, project, cohort=None):
    """Figures the proposal promises for the Incentiva and Innova reports, computed from what the platform already records.
    Everything is limited to one cohort: by its column where the record has one, by its time window otherwise."""
    cohort = cohort or current_cohort(db)
    since, until = cohort_window(db, cohort)
    one = lambda sql, *args: db.execute(sql, args).fetchone()[0]
    deadline = os.environ.get(f"PUCV_{project.upper()}_DEADLINE", "").strip()
    subs = "FROM submissions WHERE project_id=? AND cohort=?"
    open_subs = subs + " AND status<>'rejected'"
    teams = one("SELECT COUNT(DISTINCT lower(trim(section))||'/'||lower(trim(team_name))) " + open_subs, project, cohort)
    pct = lambda part, whole: f"{round(100 * part / whole)}%" if whole else "—"
    subtitled = one("SELECT COUNT(*) " + open_subs + " AND has_subtitles=1", project, cohort)
    with_ai = one("SELECT COUNT(*) " + open_subs + " AND trim(ai_declaration)<>''", project, cohort)
    rows = [
        ("Participación", "Estudiantes con acceso", one("SELECT COUNT(*) FROM project_memberships WHERE project_id=? AND status='active' AND cohort=?", project, cohort)),
        ("Entregas", "Equipos con entrega", teams),
        ("Entregas", "Entregas publicadas", one("SELECT COUNT(*) " + subs + " AND status='published'", project, cohort)),
        ("Entregas", "Entregas en revisión", one("SELECT COUNT(*) " + subs + " AND status='review'", project, cohort)),
        ("Entregas", "Entregas devueltas para corregir", one("SELECT COUNT(*) " + subs + " AND status='rejected'", project, cohort)),
    ]
    for section in PROJECT_SECTIONS[project]:
        rows.append(("Entregas", f"Equipos con entrega · {section}", one("SELECT COUNT(DISTINCT lower(trim(team_name))) " + open_subs + " AND section=?", project, cohort, section)))
    if deadline:
        on_time = one("SELECT COUNT(DISTINCT lower(trim(section))||'/'||lower(trim(team_name))) " + open_subs + " AND date(created_at)<=date(?)", project, cohort, deadline)
        rows.append(("Entregas", f"Equipos que entregaron hasta el {deadline}", f"{on_time} ({pct(on_time, teams)})"))
    total = one("SELECT COUNT(*) " + open_subs, project, cohort)
    with_alternatives = one("SELECT COUNT(*) " + open_subs + " AND alternatives LIKE '%\"items\"%'", project, cohort)
    published_comments = "FROM comments c JOIN resources r ON r.id=c.resource_id WHERE r.project_id=? AND c.status='published' AND c.created_at>=? AND c.created_at<?"
    quiz_rows = db.execute("""SELECT q.score,r.quiz FROM quiz_attempts q JOIN resources r ON r.id=q.resource_id
      WHERE r.project_id=? AND q.created_at>=? AND q.created_at<?""", (project, since, until)).fetchall()
    quiz_share = sum(r["score"] / max(1, len(json.loads(r["quiz"]))) for r in quiz_rows) / len(quiz_rows) if quiz_rows else None
    peer = [json.loads(r[0]) for r in db.execute("""SELECT p.scores FROM peer_reviews p JOIN resources r ON r.id=p.resource_id
      WHERE r.project_id=? AND p.created_at>=? AND p.created_at<?""", (project, since, until))]
    peer_overall = peer_summary(PEER_RUBRIC[project], peer)["overall"] if peer else None
    rows += [
        ("Calidad y uso ético", "Videos con subtítulos declarados", f"{subtitled} de {total} ({pct(subtitled, total)})"),
        ("Calidad y uso ético", "Entregas con declaración de IA", f"{with_ai} de {total} ({pct(with_ai, total)})"),
        ("Calidad y uso ético", "Equipos que autorizan la vitrina", one("SELECT COUNT(*) " + open_subs + " AND showcase_consent=1", project, cohort)),
    ]
    if project == "incentiva":
        rows.append(("Calidad y uso ético", "Entregas que comparan alternativas", f"{with_alternatives} de {total} ({pct(with_alternatives, total)})"))
    else:
        rows.append(("Calidad y uso ético", "Entregas con modelo 3D", one("SELECT COUNT(*) " + open_subs + " AND model_storage_key<>''", project, cohort)))
    rows += [
        ("Foro", "Comentarios publicados", one("SELECT COUNT(*) " + published_comments, project, since, until)),
        ("Foro", "Respuestas del equipo autor", one("SELECT COUNT(*) " + published_comments + " AND c.badge='equipo'", project, since, until)),
        ("Foro", "Fichas con respuesta del equipo autor", one("SELECT COUNT(DISTINCT c.resource_id) " + published_comments + " AND c.badge='equipo'", project, since, until)),
        ("Preguntas de control", "Personas que respondieron (intentos)", len(quiz_rows)),
        ("Preguntas de control", "Promedio de respuestas correctas", f"{round(100 * quiz_share)}%" if quiz_share is not None else "—"),
        ("Coevaluación", "Evaluaciones entre pares", len(peer)),
        ("Coevaluación", "Promedio general (1 a 4)", peer_overall if peer_overall is not None else "—"),
        ("Tiquetes", "Tiquetes de salida aplicados", one("SELECT COUNT(*) FROM exit_tickets WHERE project_id=? AND cohort=? AND kind='salida'", project, cohort)),
        ("Tiquetes", "Preguntas previas aplicadas", one("SELECT COUNT(*) FROM exit_tickets WHERE project_id=? AND cohort=? AND kind='previa'", project, cohort)),
        ("Tiquetes", "Respuestas recibidas", one("SELECT COUNT(*) FROM exit_ticket_answers a JOIN exit_tickets t ON t.id=a.ticket_id WHERE t.project_id=? AND t.cohort=?", project, cohort)),
        ("Encuestas", "Encuestas aplicadas (KPSI y percepción)", one("SELECT COUNT(*) FROM surveys WHERE project_id=? AND cohort=?", project, cohort)),
        ("Encuestas", "Respuestas recibidas", one("SELECT COUNT(*) FROM survey_answers a JOIN surveys s ON s.id=a.survey_id WHERE s.project_id=? AND s.cohort=?", project, cohort)),
    ]
    return [{"group": g, "label": label, "value": value} for g, label, value in rows]


def project_report(db, project, cohort):
    """Data behind the printable end-of-project report: indicators plus the series the charts draw."""
    since, until = cohort_window(db, cohort)
    statuses = {r["status"]: r["n"] for r in db.execute("SELECT status,COUNT(*) n FROM submissions WHERE project_id=? AND cohort=? GROUP BY status", (project, cohort))}
    by_section = [{"section": r["section"] or "Sin paralelo", "teams": r["n"]} for r in db.execute(
        """SELECT section,COUNT(DISTINCT lower(trim(team_name))) n FROM submissions WHERE project_id=? AND cohort=? AND status<>'rejected'
           GROUP BY section ORDER BY section""", (project, cohort))]
    kpsi = []
    exit_survey = db.execute("SELECT * FROM surveys WHERE project_id=? AND cohort=? AND kind='kpsi' AND moment='salida' ORDER BY id DESC LIMIT 1", (project, cohort)).fetchone()
    entry_survey = db.execute("SELECT * FROM surveys WHERE project_id=? AND cohort=? AND kind='kpsi' AND moment='entrada' ORDER BY id DESC LIMIT 1", (project, cohort)).fetchone()
    if exit_survey and entry_survey:
        rows_for = lambda sid: [json.loads(r[0]) for r in db.execute("SELECT answer_values FROM survey_answers WHERE survey_id=?", (sid,))]
        before = {r["text"]: r for r in survey_results(json.loads(entry_survey["items"]), json.loads(entry_survey["scale"]), rows_for(entry_survey["id"]))}
        for r in survey_results(json.loads(exit_survey["items"]), json.loads(exit_survey["scale"]), rows_for(exit_survey["id"])):
            b = before.get(r["text"])
            kpsi.append({"text": r["text"], "dimension": r["dimension"], "before": b["mean"] if b else None, "after": r["mean"],
                         "before_levels": level_shares(b["distribution"]) if b else {"n": 0, "percent": None},
                         "after_levels": level_shares(r["distribution"])})
    perception = None
    survey = db.execute("SELECT * FROM surveys WHERE project_id=? AND cohort=? AND kind='percepcion' ORDER BY id DESC LIMIT 1", (project, cohort)).fetchone()
    if survey:
        answers = [json.loads(r[0]) for r in db.execute("SELECT answer_values FROM survey_answers WHERE survey_id=?", (survey["id"],))]
        perception = {"title": survey["title"], "scale": json.loads(survey["scale"]),
                      "items": [{"text": r["text"], "dimension": r["dimension"], "levels": level_shares(r["distribution"])}
                                for r in survey_results(json.loads(survey["items"]), json.loads(survey["scale"]), answers)]}
    quiz = []
    for resource in db.execute("SELECT id,title,quiz FROM resources WHERE project_id=? AND quiz<>'[]'", (project,)).fetchall():
        attempts = [json.loads(a[0]) for a in db.execute("SELECT answers FROM quiz_attempts WHERE resource_id=? AND created_at>=? AND created_at<?", (resource["id"], since, until))]
        if attempts:
            stats = quiz_stats(json.loads(resource["quiz"]), attempts)
            shares = [q["correct_share"] for q in stats["questions"] if q["correct_share"] is not None]
            quiz.append({"title": resource["title"], "respondents": stats["respondents"], "correct_share": round(sum(shares) / len(shares), 2) if shares else None})
    peer = [json.loads(r[0]) for r in db.execute("""SELECT p.scores FROM peer_reviews p JOIN resources r ON r.id=p.resource_id
      WHERE r.project_id=? AND p.created_at>=? AND p.created_at<?""", (project, since, until))]
    tags = db.execute("""SELECT g.tag,COUNT(*) n FROM exit_ticket_tags g JOIN exit_ticket_answers a ON a.id=g.answer_id
      JOIN exit_tickets t ON t.id=a.ticket_id WHERE t.project_id=? AND t.cohort=? GROUP BY g.tag ORDER BY n DESC LIMIT 8""", (project, cohort)).fetchall()
    return {"project": project, "name": PROJECTS[project]["name"], "cohort": cohort, "indicators": project_indicators(db, project, cohort),
            "statuses": statuses, "by_section": by_section, "kpsi": kpsi, "kpsi_scale": KPSI_SCALE, "perception": perception, "quiz": quiz,
            "peer": peer_summary(PEER_RUBRIC[project], peer) if peer else None, "doubts": [dict(r) for r in tags]}


def anonymize_user(db, user_id):
    """Remove a person's identity and personal contributions; response content stays without a direct user key."""
    user = db.execute("SELECT id,email,display_name FROM users WHERE id=?", (user_id,)).fetchone()
    if not user: return None
    files = []
    for row in db.execute("SELECT id,status,evidence_storage_key,model_storage_key FROM submissions WHERE user_id=? AND status<>'published'", (user_id,)).fetchall():
        files += [k for k in (row["evidence_storage_key"], row["model_storage_key"]) if k]
        db.execute("DELETE FROM submissions WHERE id=?", (row["id"],))
    # Published team work stays (the team authorised it); only this person's name and address are taken out.
    for row in db.execute("SELECT id,members,member_emails FROM submissions WHERE user_id=? OR member_emails LIKE ?",
                          (user_id, f'%"{user["email"]}"%')).fetchall():
        members, emails = json.loads(row["members"] or "[]"), json.loads(row["member_emails"] or "[]")
        emails += [""] * (len(members) - len(emails))
        kept = [(m, e) for m, e in zip(members, emails) if e != user["email"] and m.lower() != user["display_name"].lower()]
        db.execute("UPDATE submissions SET members=?,member_emails=? WHERE id=?",
                   (json.dumps([m for m, _ in kept], ensure_ascii=False), json.dumps([e for _, e in kept]), row["id"]))
    db.execute("DELETE FROM comments WHERE parent_id IN (SELECT id FROM comments WHERE user_id=?)", (user_id,))
    for table, column in (("sessions", "user_id"), ("project_memberships", "user_id"), ("comments", "user_id"), ("peer_reviews", "reviewer_id"),
                          ("quiz_attempts", "user_id"), ("exit_ticket_respondents", "user_id"), ("survey_respondents", "user_id")):
        db.execute(f"DELETE FROM {table} WHERE {column}=?", (user_id,))
    db.execute("DELETE FROM access_codes WHERE email=?", (user["email"],))
    db.execute("DELETE FROM email_login_tokens WHERE email=?", (user["email"],))
    db.execute("DELETE FROM staff_roles WHERE email=?", (user["email"],))
    db.execute("UPDATE users SET email=?,display_name='Persona eliminada',provider_subject=NULL,role='student' WHERE id=?",
               (f"eliminada-{user_id}@anonimo.invalid", user_id))
    return files


def person_export(db, email):
    """Everything stored about one address (right of access), as plain JSON."""
    user = db.execute("SELECT id,email,display_name,role,created_at FROM users WHERE email=?", (email,)).fetchone()
    if not user: return None
    rows = lambda sql: [dict(r) for r in db.execute(sql, (user["id"],))]
    return {"cuenta": dict(user),
            "asignaturas": rows("SELECT project_id,status,section,requested_at,reviewed_at FROM project_memberships WHERE user_id=?"),
            "entregas": rows("SELECT project_id,team_name,section,members,title,summary,video_url,evidence_url,evidence_filename,project_fields,ai_declaration,status,review_note,created_at FROM submissions WHERE user_id=?"),
            "comentarios": rows("SELECT c.body,c.status,c.created_at,r.title recurso FROM comments c JOIN resources r ON r.id=c.resource_id WHERE c.user_id=?"),
            "coevaluaciones": rows("SELECT r.title recurso,p.scores,p.strength,p.suggestion,p.updated_at FROM peer_reviews p JOIN resources r ON r.id=p.resource_id WHERE p.reviewer_id=?"),
            "preguntas_de_control": rows("SELECT r.title recurso,q.answers,q.score,q.created_at FROM quiz_attempts q JOIN resources r ON r.id=q.resource_id WHERE q.user_id=?"),
            "nota": "El contenido de las respuestas no incluye el correo o nombre; el registro separado de participación sí se liga a la cuenta para limitar duplicados."}


def cohorts(db):
    """Cohorts in order; each starts when it is opened and ends when the next one starts. The last one is current."""
    row = db.execute("SELECT value FROM settings WHERE key='cohorts'").fetchone()
    if row: return json.loads(row[0])
    items = [{"name": DEFAULT_COHORT, "started_at": "1970-01-01 00:00:00"}]
    db.execute("INSERT OR IGNORE INTO settings(key,value) VALUES('cohorts',?)", (json.dumps(items),))
    return items


def current_cohort(db) -> str:
    return cohorts(db)[-1]["name"]


def cohort_window(db, name):
    """(start, end) timestamps of a cohort, for records that have no cohort column (comments, answers, reviews)."""
    items = cohorts(db)
    names = [c["name"] for c in items]
    i = names.index(name) if name in names else len(items) - 1
    return items[i]["started_at"], items[i + 1]["started_at"] if i + 1 < len(items) else "9999-12-31"


def clean_alternatives(raw):
    """Alternative solutions scored 1–3 on each criterion of the Incentiva form; returns (dict, error)."""
    if not raw: return {}, ""
    if not isinstance(raw, dict) or not isinstance(raw.get("items"), list): return None, "Las alternativas no tienen el formato esperado."
    items = []
    for entry in raw["items"][:3]:
        if not isinstance(entry, dict): return None, "Las alternativas no tienen el formato esperado."
        name = str(entry.get("name", "")).strip()[:160]
        scores = entry.get("scores")
        if not name: continue
        if not isinstance(scores, list) or len(scores) != len(ALTERNATIVE_CRITERIA) or not all(isinstance(v, int) and 1 <= v <= 3 for v in scores):
            return None, f"Puntúa de 1 a 3 cada criterio de la alternativa «{name[:40]}»."
        items.append({"name": name, "scores": scores, "total": sum(scores)})
    if not items: return {}, ""
    try: chosen = int(raw.get("chosen", 0))
    except (TypeError, ValueError): chosen = 0
    return {"criteria": ALTERNATIVE_CRITERIA, "items": items, "chosen": chosen if 0 <= chosen < len(items) else 0}, ""


def valid_stl(data: bytes) -> bool:
    """Binary STL: 80-byte header, triangle count, 50 bytes per triangle. ASCII STL: 'solid … facet … endsolid'."""
    if len(data) >= 84 and 84 + 50 * int.from_bytes(data[80:84], "little") == len(data): return True
    head = data[:1024].lstrip().lower()
    return head.startswith(b"solid") and b"facet" in data[:200000].lower()


def keyword_counts(texts, limit=8):
    counts = {}
    for text in texts:
        words = set(re.findall(r"[a-záéíóúñü0-9]{4,}", unicodedata.normalize("NFC", str(text).lower())))
        for word in words:
            plain = unicodedata.normalize("NFKD", word).encode("ascii", "ignore").decode()
            if plain not in STOPWORDS: counts[word] = counts.get(word, 0) + 1
    return [{"word": w, "count": c} for w, c in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:limit] if c > 1]


def staff_emails(db):
    emails = set(ADMIN_EMAILS) | {e for group in PROJECT_ADMIN_EMAILS.values() for e in group}
    return emails | {r["email"] for r in db.execute("SELECT email FROM staff_roles")}


def close_cohort(db):
    """End of a cohort: anonymize every student, drop unpublished work and keep in the catalog only student work whose
    team authorised the showcase for future cohorts; the rest is retired (hidden), not deleted."""
    staff = staff_emails(db)
    students = [r["id"] for r in db.execute("SELECT id,email FROM users WHERE email NOT LIKE '%@anonimo.invalid'") if r["email"] not in staff]
    db.execute("""UPDATE resources SET status='draft',edited_at=CURRENT_TIMESTAMP
      WHERE source_submission_id IN (SELECT id FROM submissions WHERE showcase_consent=0)""")
    # Evidence of work that will not stay visible is not needed for future cohorts.
    files = [k for r in db.execute("SELECT evidence_storage_key,model_storage_key FROM submissions WHERE showcase_consent=0") for k in r if k]
    db.execute("UPDATE submissions SET evidence_storage_key='',evidence_filename='',model_storage_key='',model_filename='' WHERE showcase_consent=0")
    for user_id in students: files += anonymize_user(db, user_id)
    # Member names were typed by the team and cannot always be matched to an account, so they all go.
    db.execute("UPDATE submissions SET members='[]',member_emails='[]'")
    db.execute("UPDATE join_codes SET active=0")
    db.execute("UPDATE exit_tickets SET active=0")
    db.execute("UPDATE surveys SET active=0")
    db.execute("DELETE FROM rate_events")
    return len(students), files


def quiz_stats(questions, attempts):
    """Aggregate results per control question: respondents, share correct and how often each option was chosen."""
    stats = []
    for index, question in enumerate(questions):
        chosen = [a[index] for a in attempts if index < len(a) and isinstance(a[index], int)]
        stats.append({"prompt": question["prompt"], "correct_share": round(sum(c == question["correct"] for c in chosen) / len(chosen), 2) if chosen else None,
                      "options": [{"text": option, "count": chosen.count(i), "correct": i == question["correct"]} for i, option in enumerate(question["options"])]})
    return {"respondents": len(attempts), "questions": stats}


def snapshot_database(target: Path):
    """Consistent copy of the live database (the SQLite backup API also captures pages still in the WAL)."""
    source, copy = connect(), sqlite3.connect(target)
    try:
        source.backup(copy)
    finally:
        copy.close()
        source.close()


def create_backup() -> Path:
    """Daily database snapshot next to the data; uploaded files are append-only and go in the full archive instead."""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    target = BACKUP_DIR / f"respaldo-{time.strftime('%Y%m%d-%H%M%S')}.sqlite3"
    partial = target.with_suffix(".partial")
    snapshot_database(partial)
    partial.replace(target)
    for old in sorted(BACKUP_DIR.glob("respaldo-*.sqlite3"))[:-BACKUP_KEEP]:
        old.unlink(missing_ok=True)
    return target


def create_full_archive(target: Path) -> Path:
    """Zip with the database snapshot and every uploaded file, to keep a copy outside the hosting disk."""
    target.parent.mkdir(parents=True, exist_ok=True)
    snapshot = target.with_suffix(".sqlite3.tmp")
    snapshot_database(snapshot)
    try:
        with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.write(snapshot, "repository.sqlite3")
            if UPLOAD_DIR.is_dir():
                for file in sorted(UPLOAD_DIR.iterdir()):
                    if file.is_file() and re.fullmatch(r"[a-f0-9]{40}", file.name):
                        archive.write(file, "submissions_files/" + file.name)
    finally:
        snapshot.unlink(missing_ok=True)
    return target


def backup_loop():
    # Checking hourly instead of sleeping a full day keeps the schedule across the frequent restarts of a hosted service.
    while True:
        try:
            latest = max((p.stat().st_mtime for p in BACKUP_DIR.glob("respaldo-*.sqlite3")), default=0)
            if time.time() - latest >= BACKUP_HOURS * 3600:
                print(f"Respaldo automático: {create_backup()}", flush=True)
        except Exception as error:
            print(f"Respaldo automático falló: {error}", file=sys.stderr, flush=True)
        time.sleep(3600)


def audit_cleanup_loop():
    """Remove expired audit events hourly, even when no new event is written."""
    while True:
        try:
            with connect() as db: purge_audit_events(db)
            notify_pending_digest()
        except Exception as error:
            print(f"No se pudo depurar el registro de auditoría: {error}", flush=True)
        time.sleep(3600)


def institutional_email(value) -> str:
    """Return the normalized address when it has a valid shape and an allowed PUCV domain, else ''."""
    email = str(value or "").strip().lower()
    if len(email) > 254 or email.count("@") != 1: return ""
    local_part, domain = email.split("@", 1)
    if domain not in ALLOWED_EMAIL_DOMAINS: return ""
    if not re.fullmatch(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]{1,64}@[A-Za-z0-9.-]{1,253}", email): return ""
    if local_part.startswith(".") or local_part.endswith(".") or ".." in local_part: return ""
    return email


def name_from_email(email: str) -> str:
    local = email.split("@", 1)[0].replace(".", " ").replace("_", " ").replace("-", " ")
    return " ".join(part.capitalize() for part in local.split()) or "Comunidad PUCV"


def new_code(length=8) -> str:
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(length))


def normalize_code(value) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(value or "").upper())[:32]


def join_code_usable(row, now=None) -> bool:
    now = now or int(time.time())
    return bool(row and row["active"] and row["expires_at"] > now and (row["max_uses"] is None or row["uses"] < row["max_uses"]))


def roster_emails(raw) -> list:
    """Institutional addresses from a pasted class list (one per line, commas or semicolons), deduplicated."""
    found = []
    for item in re.split(r"[\s,;]+", str(raw or "")):
        email = institutional_email(item.strip("<>()\"'"))
        if email and email not in found: found.append(email)
    return found


def apply_join_code(db, user_id, row):
    """Activate the membership a course code grants, record its paralelo and count the use."""
    db.execute("""INSERT INTO project_memberships(user_id,project_id,status,reviewed_at,reviewed_by,section,cohort)
      VALUES(?,?,'active',CURRENT_TIMESTAMP,?,?,?) ON CONFLICT(user_id,project_id) DO UPDATE SET
      status='active',reviewed_at=CURRENT_TIMESTAMP,reviewed_by=excluded.reviewed_by,cohort=excluded.cohort,
      section=CASE WHEN excluded.section<>'' THEN excluded.section ELSE project_memberships.section END""",
      (user_id, row["project_id"], row["created_by"], row["section"], current_cohort(db)))
    db.execute("UPDATE join_codes SET uses=uses+1 WHERE id=?", (row["id"],))


def is_staff_email(db, email) -> bool:
    """Teaching and admin accounts never enter with a shared course code: whoever knows it could type their address."""
    if email in ADMIN_EMAILS or any(email in emails for emails in PROJECT_ADMIN_EMAILS.values()): return True
    if db.execute("SELECT 1 FROM staff_roles WHERE email=?", (email,)).fetchone(): return True
    return bool(db.execute("SELECT 1 FROM users WHERE email=? AND role IN ('admin','editor')", (email,)).fetchone())


def format_code(code: str) -> str:
    return "-".join(code[i:i + 4] for i in range(0, len(code), 4))


def code_digest(code: str, salt: str) -> str:
    # Personal codes are short, so they are stretched like passwords and also rate limited.
    return hashlib.pbkdf2_hmac("sha256", code.encode(), bytes.fromhex(salt), 120_000).hex()


def is_rate_limited(db, bucket: str, limit: int, window: int) -> bool:
    now = int(time.time())
    db.execute("DELETE FROM rate_events WHERE created_at<?", (now - 24 * 60 * 60,))
    return db.execute("SELECT COUNT(*) FROM rate_events WHERE bucket=? AND created_at>?", (bucket, now - window)).fetchone()[0] >= limit


def record_rate_event(db, bucket: str):
    db.execute("INSERT INTO rate_events(bucket,created_at) VALUES(?,?)", (bucket, int(time.time())))


def issue_access_codes(db, emails, project, created_by, days):
    """Create personal sign-in codes; previous active codes for the same address are revoked."""
    now = int(time.time())
    issued = []
    for email in emails:
        code = new_code()
        salt = secrets.token_hex(16)
        db.execute("UPDATE access_codes SET revoked_at=? WHERE email=? AND revoked_at IS NULL", (now, email))
        db.execute("""INSERT INTO access_codes(email,code_hash,salt,project_id,created_by,created_at,expires_at)
          VALUES(?,?,?,?,?,?,?)""", (email, code_digest(code, salt), salt, project, created_by, now, now + days * 86400))
        issued.append({"email": email, "code": format_code(code)})
    return issued


def email_ready() -> bool:
    # Unencrypted SMTP only to this same machine (a local relay or the test suite's fake server).
    secure = SMTP_SECURITY in ("ssl", "starttls") or (SMTP_SECURITY == "none" and SMTP_HOST in ("127.0.0.1", "localhost"))
    return bool(SMTP_HOST and SMTP_FROM and BASE_URL.startswith("https://") and secure)


def send_email(to, subject, body):
    message = EmailMessage()
    message["Subject"], message["From"], message["To"] = subject, SMTP_FROM, to
    message.set_content(body)
    if SMTP_SECURITY == "ssl":
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=12, context=ssl.create_default_context()) as smtp:
            if SMTP_USER: smtp.login(SMTP_USER, SMTP_PASSWORD)
            smtp.send_message(message)
    else:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=12) as smtp:
            smtp.ehlo()
            if SMTP_SECURITY == "starttls": smtp.starttls(context=ssl.create_default_context()); smtp.ehlo()
            if SMTP_USER: smtp.login(SMTP_USER, SMTP_PASSWORD)
            smtp.send_message(message)


def smtp_check():
    """Connect and authenticate without sending anything, for `diagnostico`."""
    try:
        smtp = (smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=12, context=ssl.create_default_context()) if SMTP_SECURITY == "ssl"
                else smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=12))
        with smtp:
            smtp.ehlo()
            if SMTP_SECURITY == "starttls": smtp.starttls(context=ssl.create_default_context()); smtp.ehlo()
            if SMTP_USER: smtp.login(SMTP_USER, SMTP_PASSWORD)
        return True, f"{SMTP_HOST}:{SMTP_PORT}"
    except Exception as error:
        return False, f"{type(error).__name__}: {error}"


def notify_later(recipients, subject, body):
    """Best-effort course notices: sent in the background only when a sender is configured, never blocking a review."""
    recipients = sorted({r for r in recipients if r and not r.endswith("@anonimo.invalid")})
    if not email_ready() or not recipients: return
    def run():
        for to in recipients:
            try: send_email(to, subject, body)
            except Exception as error: print(f"Aviso por correo a {to} falló: {error}", file=sys.stderr, flush=True)
    threading.Thread(target=run, daemon=True).start()


NOTICE_EVERY = 3600


def project_teachers(db, project):
    """Who is notified about a subject: its teachers (configured or assigned in the panel) and the global admins."""
    assigned = {r["email"] for r in db.execute("SELECT email FROM staff_roles WHERE project_id=?", (project,))}
    return sorted(PROJECT_ADMIN_EMAILS.get(project, set()) | assigned | ADMIN_EMAILS)


def pending_counts(db, projects):
    if not projects: return {"submissions": 0, "comments": 0, "access_requests": 0, "total": 0}
    marks = ",".join("?" for _ in projects)
    counts = {
        "submissions": db.execute(f"SELECT COUNT(*) FROM submissions WHERE status='review' AND project_id IN ({marks})", projects).fetchone()[0],
        "comments": db.execute(f"""SELECT COUNT(*) FROM comments c JOIN resources r ON r.id=c.resource_id
                                   WHERE c.status='review' AND r.project_id IN ({marks})""", projects).fetchone()[0],
        "access_requests": db.execute(f"SELECT COUNT(*) FROM project_memberships WHERE status='pending' AND project_id IN ({marks})", projects).fetchone()[0]}
    return {**counts, "total": sum(counts.values())}


def teacher_projects(db, email):
    if email in ADMIN_EMAILS: return list(PROJECTS)
    assigned = {r["project_id"] for r in db.execute("SELECT project_id FROM staff_roles WHERE email=?", (email,))}
    return [p for p, emails in PROJECT_ADMIN_EMAILS.items() if email in emails or p in assigned]


def notify_teachers(db, project, force=False):
    """At most one e-mail per teacher per hour: only the pending count and the panel link, never students' data."""
    if not email_ready(): return
    now = int(time.time())
    for email in project_teachers(db, project):
        if db.execute("SELECT 1 FROM settings WHERE key=?", (f"notify_off:{email}",)).fetchone(): continue
        last = db.execute("SELECT value FROM settings WHERE key=?", (f"notify_last:{email}",)).fetchone()
        if last and now - int(last["value"]) < NOTICE_EVERY: continue
        projects = teacher_projects(db, email)
        counts = pending_counts(db, projects)
        if not counts["total"]: continue
        if not force and last:
            # The hourly digest only writes when something arrived after the previous notice.
            since = int(last["value"]); marks = ",".join("?" for _ in projects)
            newer = db.execute(f"""SELECT 1 FROM submissions WHERE status='review' AND project_id IN ({marks}) AND created_at>datetime(?,'unixepoch')
                                  UNION SELECT 1 FROM project_memberships WHERE status='pending' AND project_id IN ({marks}) AND requested_at>datetime(?,'unixepoch')""",
                               (*projects, since, *projects, since)).fetchone()
            if not newer: continue
        db.execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (f"notify_last:{email}", str(now)))
        total = counts["total"]
        body = (f"Hay {total} {'pendiente' if total == 1 else 'pendientes'} de revisión en el Repositorio de proyectos de Tecnología Médica:\n"
                f"- Entregas: {counts['submissions']}\n- Solicitudes de acceso: {counts['access_requests']}\n- Comentarios: {counts['comments']}\n\n"
                f"Revísalos en {BASE_URL}/admin\n\nRecibes como máximo un aviso por hora. Puedes desactivarlos en el panel docente.")
        notify_later([email], f"Repositorio TM: {total} {'pendiente' if total == 1 else 'pendientes'} de revisión", body)


def notify_pending_digest():
    """Hourly (cron or background loop): tell teachers about what arrived since their last notice."""
    if not email_ready(): return
    with connect() as db:
        for project in PROJECTS: notify_teachers(db, project)


def google_ready() -> bool:
    return bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET and (BASE_URL.startswith("https://") or BASE_URL.startswith("http://localhost")))


def jwt_payload(token: str) -> dict:
    part = token.split(".")[1]
    return json.loads(base64.urlsafe_b64decode(part + "=" * (-len(part) % 4)))


class App(BaseHTTPRequestHandler):
    server_version = "RepositorioPUCV/0.1"

    def log_message(self, fmt, *args):
        # Magic-link tokens and Google authorization codes are in these URLs; never log those request lines.
        if self.path.startswith(("/auth/verify?", "/auth/google/callback?")):
            return
        sys.stderr.write(f"{self.log_date_time_string()} {fmt % args}\n")

    def client_ip(self):
        if TRUST_PROXY and self.headers.get("X-Forwarded-For"):
            # The client can prepend anything to X-Forwarded-For; the last entry is the one Render's proxy added.
            return self.headers["X-Forwarded-For"].split(",")[-1].strip()[:64]
        return self.client_address[0]

    def send_bytes(self, data: bytes, content_type="text/html; charset=utf-8", status=200, headers=None):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-src https://www.youtube-nocookie.com https://drive.google.com; frame-ancestors 'none'; base-uri 'self'; form-action 'self'")
        self.send_header("Cache-Control", "no-store")
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)

    def json(self, obj, status=200, headers=None):
        self.send_bytes(json.dumps(obj, ensure_ascii=False).encode(), "application/json; charset=utf-8", status, headers)

    def cookies(self):
        c = SimpleCookie()
        c.load(self.headers.get("Cookie", ""))
        return c

    def cookie_header(self, name, value, max_age, http_only=True):
        # Secure only when the browser reached the configured https address; the same instance can also be opened
        # over plain http on the local network (classroom demo), where a Secure cookie would never be stored.
        on_https_host = BASE_URL.startswith("https://") and self.headers.get("Host", "") == urllib.parse.urlparse(BASE_URL).netloc
        secure = "; Secure" if on_https_host else ""
        http = "; HttpOnly" if http_only else ""
        return f"{name}={value}; Path=/; SameSite=Lax; Max-Age={max_age}{http}{secure}"

    def current_user(self):
        c = self.cookies()
        if "pucv_session" not in c:
            return None
        hashed = token_hash(c["pucv_session"].value)
        with connect() as db:
            row = db.execute("""SELECT u.id,u.email,u.display_name,u.role FROM sessions s
              JOIN users u ON u.id=s.user_id WHERE s.token_hash=? AND s.expires_at>?""",
              (hashed, int(time.time()))).fetchone()
        if not row: return None
        user = dict(row)
        if user["role"] == "admin" and user["email"] not in ADMIN_EMAILS: user["role"] = "student"
        managed = self.managed_projects(user)
        if user["role"] == "student" and managed: user["role"] = "editor"
        elif user["role"] == "editor" and not managed: user["role"] = "student"
        return user

    def active_projects(self, user):
        if user["role"] == "admin":
            return list(PROJECTS)
        managed = self.managed_projects(user)
        with connect() as db:
            rows = db.execute("SELECT project_id FROM project_memberships WHERE user_id=? AND status='active' ORDER BY project_id",
                              (user["id"],)).fetchall()
        return sorted(set([row["project_id"] for row in rows] + managed))

    def managed_projects(self, user):
        if user["role"] == "admin": return list(PROJECTS)
        email = user.get("email", "").lower()
        with connect() as db:
            assigned = {r["project_id"] for r in db.execute("SELECT project_id FROM staff_roles WHERE email=?", (email,))}
        return [project for project, emails in PROJECT_ADMIN_EMAILS.items() if email in emails or project in assigned]

    def has_project_access(self, user, project):
        if project not in PROJECTS: return False
        if user and user["role"] == "admin": return True
        if not user: return False
        if project in self.managed_projects(user): return True
        with connect() as db:
            row = db.execute("SELECT 1 FROM project_memberships WHERE user_id=? AND project_id=? AND status='active'",
                             (user["id"], project)).fetchone()
        return bool(row)

    def member_resource(self, user, resource_id):
        """A published resource of a course the user belongs to (course editors also reach retired ones), else None."""
        with connect() as db:
            row = db.execute("SELECT * FROM resources WHERE id=?", (resource_id,)).fetchone()
        if not row or not self.has_project_access(user, row["project_id"]): return None
        if row["status"] != "published" and row["project_id"] not in self.managed_projects(user): return None
        return dict(row)

    def can_view_submission(self, user, row):
        """Course editors, the submitter, members listed by address, or course members once the work is published."""
        if row["project_id"] in self.managed_projects(user) or row["user_id"] == user["id"]: return True
        if user["email"] in json.loads(row["member_emails"] or "[]"): return True
        if not self.has_project_access(user, row["project_id"]): return False
        with connect() as db:
            return bool(db.execute("SELECT 1 FROM resources WHERE source_submission_id=? AND status='published'", (row["id"],)).fetchone())

    def reader_projects(self, user):
        return [p for p in OPEN_PROJECTS if not self.has_project_access(user, p)] if user else []

    def send_csv(self, filename, header, rows):
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(header)
        # Prefixing formula-like cells keeps spreadsheet apps from executing text typed by students.
        writer.writerows([["'" + str(v) if str(v)[:1] in ("=", "+", "-", "@", "\t", "\r") else v for v in row] for row in rows])
        # The BOM makes Excel open the file as UTF-8 so accents survive.
        self.send_bytes(("﻿" + buffer.getvalue()).encode(), "text/csv; charset=utf-8",
                        headers={"Content-Disposition": f"attachment; filename={filename}"})

    def require_user(self):
        user = self.current_user()
        if not user:
            self.json({"error": "Inicia sesión con tu cuenta PUCV para continuar."}, 401)
            return None
        return user

    def do_GET(self):
        self.guarded(self.route_get)

    def do_POST(self):
        self.guarded(self.route_post)

    def guarded(self, handler):
        # Malformed input (huge ids, 1e400, non-UTF-8 bodies, wrong JSON types) answers 400 instead of dropping the connection.
        try:
            handler()
        except (OverflowError, UnicodeDecodeError, TypeError, ValueError, AttributeError) as error:
            self.log_error("Solicitud inválida en %s: %r", urllib.parse.urlparse(self.path).path, error)
            try: self.json({"error": "Solicitud inválida."}, 400)
            except Exception: pass

    def route_get(self):
        path = urllib.parse.urlparse(self.path).path
        if path == "/auth/verify":
            return self.verify_page()
        if path == "/auth/logout":
            return self.logout()
        if path == "/auth/google":
            return self.google_start()
        if path == "/auth/google/callback":
            return self.google_callback()
        if path == "/api/me":
            user = self.current_user()
            email_ready = self.email_transport_ready()
            active, pending, sections = [], [], {}
            if user:
                active = self.active_projects(user)
                with connect() as db:
                    rows = db.execute("SELECT project_id,status,section FROM project_memberships WHERE user_id=?", (user["id"],)).fetchall()
                if user["role"] != "admin":
                    pending = [r["project_id"] for r in rows if r["status"] == "pending"]
                sections = {r["project_id"]: r["section"] for r in rows if r["status"] == "active" and r["section"]}
                pending = [project for project in pending if project not in self.managed_projects(user)]
            managed = self.managed_projects(user) if user else []
            config = {p: {"sections": PROJECT_SECTIONS[p], "fields": PROJECT_FIELDS[p], "open": p in OPEN_PROJECTS,
                          "guide_question": GUIDE_QUESTIONS[p], "ticket_questions": EXIT_TICKET_QUESTIONS[p],
                          "survey_templates": {kind: SURVEY_TEMPLATES[kind][p] for kind in SURVEY_TEMPLATES},
                          "pre_questions": PRE_SESSION_QUESTIONS[p], "alternative_criteria": ALTERNATIVE_CRITERIA if p == "incentiva" else []} for p in PROJECTS}
            with connect() as db: cohort_now = current_cohort(db)
            return self.json({"user": user, "demo": DEMO_AUTH, "email_ready": email_ready, "google_ready": google_ready(),
                              "active_projects": active, "pending_projects": pending,"managed_projects":managed,
                              "my_sections": sections, "project_config": config, "reader_projects": self.reader_projects(user), "cohort": cohort_now})
        if path == "/api/video-check":
            user = self.require_user()
            if not user: return
            url = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query).get("url", [""])[0][:500]
            with connect() as db:
                if is_rate_limited(db, f"video-check:{user['id']}", 30, 15 * 60): return self.json({"status": "unknown"})
                record_rate_event(db, f"video-check:{user['id']}")
            return self.json({"status": drive_sharing_status(url)})
        if path == "/api/my-submissions":
            user = self.require_user()
            if not user: return
            project = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query).get("project", [""])[0]
            if not self.has_project_access(user, project): return self.json({"error":"No tienes acceso a esta asignatura."},403)
            with connect() as db:
                rows = db.execute("""SELECT id,team_name,section,title,status,review_note,created_at,reviewed_at FROM submissions
                  WHERE project_id=? AND user_id=? ORDER BY id DESC""", (project, user["id"])).fetchall()
            return self.json([dict(r) for r in rows])
        if path == "/api/admin/join-codes":
            user = self.require_user()
            if not user: return
            managed = self.managed_projects(user)
            if not managed: return self.json({"error": "No tienes permiso para gestionar códigos."}, 403)
            placeholders = ",".join("?" for _ in managed)
            with connect() as db:
                rows = db.execute("SELECT id,code,project_id,label,section,expires_at,max_uses,uses,active,roster FROM join_codes WHERE project_id IN ("
                                  + placeholders + ") ORDER BY id DESC LIMIT 50", managed).fetchall()
            now = int(time.time())
            entries = {}
            if rows:
                code_ids = [r["id"] for r in rows]
                id_slots = ",".join("?" for _ in code_ids)
                with connect() as db:
                    activity = db.execute(f"""SELECT entity_id,subject_email,created_at FROM audit_events
                      WHERE event_type='course_code_login' AND entity_type='join_code' AND project_id IN ({placeholders})
                      AND entity_id IN ({id_slots}) AND created_at>=? ORDER BY created_at DESC""",
                      (*managed, *code_ids, now - AUDIT_RETENTION_DAYS * 86400)).fetchall()
                for event in activity:
                    entries.setdefault(event["entity_id"], []).append({"email": event["subject_email"], "created_at": event["created_at"]})
            return self.json([{**{k: r[k] for k in r.keys() if k != "roster"}, "code": format_code(r["code"]), "valid": join_code_usable(r, now),
                               "roster_size": len(r["roster"].split()), "entries": entries.get(r["id"], [])} for r in rows])
        if path == "/api/admin/members":
            user = self.require_user()
            if not user: return
            managed = self.managed_projects(user)
            if not managed: return self.json({"error": "No tienes permiso para ver integrantes."}, 403)
            placeholders = ",".join("?" for _ in managed)
            with connect() as db:
                rows = db.execute("""SELECT m.id,m.project_id,m.section,m.reviewed_at,u.display_name,u.email FROM project_memberships m
                  JOIN users u ON u.id=m.user_id WHERE m.status='active' AND m.project_id IN (""" + placeholders + ") ORDER BY m.project_id,u.email",
                  managed).fetchall()
            return self.json([dict(r) for r in rows])
        if path == "/api/admin/resources":
            user = self.require_user()
            if not user: return
            managed = self.managed_projects(user)
            if not managed: return self.json({"error": "No tienes permiso para gestionar materiales."}, 403)
            placeholders = ",".join("?" for _ in managed)
            with connect() as db:
                rows = db.execute("""SELECT id,project_id,slug,title,category,summary,content,tags,status,file_filename,source_submission_id,edited_at,
                  guide_question,quiz,CASE WHEN file_storage_key<>'' THEN 1 ELSE 0 END has_file FROM resources WHERE project_id IN (""" + placeholders + """)
                  ORDER BY project_id,status DESC,id DESC""", managed).fetchall()
                attempts = {}
                for a in db.execute("SELECT resource_id,answers FROM quiz_attempts"):
                    attempts.setdefault(a["resource_id"], []).append(json.loads(a["answers"]))
            result = []
            for r in rows:
                questions = json.loads(r["quiz"] or "[]")
                item = {**dict(r), "tags": json.loads(r["tags"]), "quiz": quiz_text(questions),
                        "default_guide_question": GUIDE_QUESTIONS[r["project_id"]]}
                if questions: item["quiz_stats"] = quiz_stats(questions, attempts.get(r["id"], []))
                result.append(item)
            return self.json(result)
        if path == "/api/admin/backups":
            user = self.require_user()
            if not user: return
            if user["role"] != "admin": return self.json({"error": "Solo la administración global gestiona respaldos."}, 403)
            files = sorted(BACKUP_DIR.glob("respaldo-*.sqlite3"), reverse=True) if BACKUP_DIR.is_dir() else []
            with connect() as db:
                row = db.execute("SELECT value FROM settings WHERE key='last_full_backup_download'").fetchone()
            last = json.loads(row["value"]) if row else None
            days = (int(time.time()) - int(last["at"])) // 86400 if last else None
            return self.json({"enabled": BACKUP_HOURS > 0, "every_hours": BACKUP_HOURS, "keep": BACKUP_KEEP,
                              "last_download": last, "days_since_download": days,
                              "download_overdue": days is None or days >= BACKUP_REMINDER_DAYS, "reminder_days": BACKUP_REMINDER_DAYS,
                              "backups": [{"name": f.name, "size": f.stat().st_size, "created_at": int(f.stat().st_mtime)} for f in files[:BACKUP_KEEP]]})
        if path == "/api/admin/audit":
            user = self.require_user()
            if not user: return
            if user["role"] != "admin": return self.json({"error": "Solo la administración global puede consultar la auditoría."}, 403)
            now = int(time.time())
            query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            try: offset = max(0, int(query.get("offset", ["0"])[0]))
            except (TypeError, ValueError): offset = 0
            with connect() as db:
                purge_audit_events(db, now)
                rows = db.execute("""SELECT event_type,actor_email,subject_email,project_id,entity_type,entity_id,ip_hash,created_at
                  FROM audit_events WHERE created_at>=? ORDER BY created_at DESC,id DESC LIMIT 500 OFFSET ?""",
                  (now - AUDIT_RETENTION_DAYS * 86400, offset)).fetchall()
            return self.json([dict(row) for row in rows])
        if path == "/api/admin/backup":
            user = self.require_user()
            if not user: return
            # The archive holds both courses and every account, so course editors cannot download it.
            if user["role"] != "admin": return self.json({"error": "Solo la administración global descarga respaldos."}, 403)
            # Only the full archive leaves the hosting; the reminder counts days since someone took one off-site.
            with connect() as db:
                db.execute("INSERT INTO settings(key,value) VALUES('last_full_backup_download',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                           (json.dumps({"at": int(time.time()), "by": user["email"]}),))
                record_audit_event(db, "full_backup_downloaded", user["email"], ip_hash=audit_ip_hash(db, self.client_ip()))
            return self.send_archive()
        if path == "/api/admin/tickets":
            user = self.require_user()
            if not user: return
            managed = self.managed_projects(user)
            if not managed: return self.json({"error": "No tienes permiso para gestionar tiquetes."}, 403)
            placeholders = ",".join("?" for _ in managed)
            with connect() as db:
                rows = db.execute("""SELECT t.id,t.project_id,t.code,t.title,t.closes_at,t.feedback_url,t.active,t.created_at,t.kind,t.cohort,
                  (SELECT COUNT(*) FROM exit_ticket_answers a WHERE a.ticket_id=t.id) answers
                  FROM exit_tickets t WHERE t.project_id IN (""" + placeholders + ") ORDER BY t.id DESC LIMIT 60", managed).fetchall()
            return self.json([{**dict(r), "url": f"{BASE_URL}/tiquete/{r['code']}", "open": bool(r["active"] and r["closes_at"] > time.time())} for r in rows])
        ticket_admin = re.fullmatch(r"/api/admin/tickets/(\d+)/(responses|responses\.csv|qr\.svg)", path)
        if ticket_admin:
            user = self.require_user()
            if not user: return
            with connect() as db:
                ticket = db.execute("SELECT * FROM exit_tickets WHERE id=?", (int(ticket_admin.group(1)),)).fetchone()
                if not ticket or ticket["project_id"] not in self.managed_projects(user): return self.json({"error": "No tienes permiso para este tiquete."}, 403)
                rows = db.execute("SELECT id,answers FROM exit_ticket_answers WHERE ticket_id=? ORDER BY answered_on,id", (ticket["id"],)).fetchall()
                tag_rows = db.execute("""SELECT g.answer_id,g.question,g.tag FROM exit_ticket_tags g JOIN exit_ticket_answers a ON a.id=g.answer_id
                  WHERE a.ticket_id=?""", (ticket["id"],)).fetchall()
            answers = [json.loads(r["answers"]) for r in rows]
            tags = {}
            for t in tag_rows: tags.setdefault(t["answer_id"], {})[str(t["question"])] = t["tag"]
            questions = json.loads(ticket["questions"])
            if ticket_admin.group(2) == "qr.svg":
                return self.send_bytes(qr.svg(f"{BASE_URL}/tiquete/{ticket['code']}").encode(), "image/svg+xml")
            if ticket_admin.group(2) == "responses":
                summary = []
                for q in range(len(questions)):
                    counts = {}
                    for r in rows:
                        tag = tags.get(r["id"], {}).get(str(q))
                        if tag: counts[tag] = counts.get(tag, 0) + 1
                    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
                    summary.append({"tags": [{"tag": t, "count": c} for t, c in ranked], "dominant": ranked[0][0] if ranked else None,
                                    "keywords": keyword_counts(a[q] for a in answers if q < len(a))})
                return self.json({"title": ticket["title"], "kind": ticket["kind"], "questions": questions, "summary": summary,
                                  "answers": [{"id": r["id"], "answers": a, "tags": tags.get(r["id"], {})} for r, a in zip(rows, answers)]})
            return self.send_csv(f"tiquete-{ticket['code']}.csv", ["respuesta"] + questions + [f"categoría {i + 1}" for i in range(len(questions))],
                                 [[i + 1] + [a[j] if j < len(a) else "" for j in range(len(questions))]
                                  + [tags.get(r["id"], {}).get(str(j), "") for j in range(len(questions))] for i, (r, a) in enumerate(zip(rows, answers))])
        ticket_path = re.fullmatch(r"/api/tickets/([A-Za-z0-9-]{4,12})", path)
        if ticket_path:
            user = self.require_user()
            if not user: return
            with connect() as db:
                ticket = db.execute("SELECT * FROM exit_tickets WHERE code=?", (normalize_code(ticket_path.group(1)),)).fetchone()
                if not ticket or not self.has_project_access(user, ticket["project_id"]):
                    return self.json({"error": "Este tiquete no existe o no pertenece a tus asignaturas."}, 404)
                answered = bool(db.execute("SELECT 1 FROM exit_ticket_respondents WHERE ticket_id=? AND user_id=?", (ticket["id"], user["id"])).fetchone())
            return self.json({"code": ticket["code"], "project_id": ticket["project_id"], "title": ticket["title"], "kind": ticket["kind"],
                              "questions": json.loads(ticket["questions"]), "answered": answered, "feedback_url": ticket["feedback_url"],
                              "open": bool(ticket["active"] and ticket["closes_at"] > time.time()), "closes_at": ticket["closes_at"]})
        if path == "/api/my-tickets":
            user = self.require_user()
            if not user: return
            project = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query).get("project", [""])[0]
            if not self.has_project_access(user, project): return self.json({"error": "No tienes acceso a esta asignatura."}, 403)
            with connect() as db:
                rows = db.execute("""SELECT t.code,t.title,t.closes_at,t.active,t.feedback_url,t.kind,
                  EXISTS(SELECT 1 FROM exit_ticket_respondents r WHERE r.ticket_id=t.id AND r.user_id=?) answered
                  FROM exit_tickets t WHERE t.project_id=? ORDER BY t.id DESC LIMIT 30""", (user["id"], project)).fetchall()
            return self.json([{**dict(r), "answered": bool(r["answered"]), "open": bool(r["active"] and r["closes_at"] > time.time())} for r in rows])
        quiz_path = re.fullmatch(r"/api/quiz/(\d+)", path)
        if quiz_path:
            user = self.require_user()
            if not user: return
            resource = self.member_resource(user, int(quiz_path.group(1)))
            if not resource: return self.json({"error": "Recurso no disponible."}, 404)
            questions = json.loads(resource["quiz"] or "[]")
            with connect() as db:
                attempt = db.execute("SELECT answers,score FROM quiz_attempts WHERE resource_id=? AND user_id=?", (resource["id"], user["id"])).fetchone()
            result = {"questions": [{"prompt": q["prompt"], "options": q["options"]} for q in questions], "attempt": None}
            if attempt:
                # Correct answers and explanations are revealed only after the first (and only counted) attempt.
                result["attempt"] = {"answers": json.loads(attempt["answers"]), "score": attempt["score"],
                                     "correct": [q["correct"] for q in questions], "explanations": [q.get("explanation", "") for q in questions]}
            return self.json(result)
        peer_path = re.fullmatch(r"/api/peer/(\d+)", path)
        if peer_path:
            user = self.require_user()
            if not user: return
            resource = self.member_resource(user, int(peer_path.group(1)))
            if not resource or not resource["source_submission_id"]: return self.json({"error": "Esta ficha no tiene coevaluación."}, 404)
            project = resource["project_id"]
            with connect() as db:
                author = is_author(resource_authors(db, resource["id"]), user)
                mine = db.execute("SELECT scores,strength,suggestion FROM peer_reviews WHERE resource_id=? AND reviewer_id=?",
                                  (resource["id"], user["id"])).fetchone()
                reviews = db.execute("SELECT scores,strength,suggestion FROM peer_reviews WHERE resource_id=? ORDER BY id",
                                     (resource["id"],)).fetchall() if author or project in self.managed_projects(user) else []
            result = {"rubric": PEER_RUBRIC[project], "levels": PEER_LEVELS, "is_author": author, "can_review": not author,
                      "mine": {**dict(mine), "scores": json.loads(mine["scores"])} if mine else None}
            if author or project in self.managed_projects(user):
                # The authoring team sees averages and comments without reviewer names.
                result["summary"] = peer_summary(PEER_RUBRIC[project], [json.loads(r["scores"]) for r in reviews])
                result["comments"] = [{"strength": r["strength"], "suggestion": r["suggestion"]} for r in reviews if r["strength"] or r["suggestion"]]
            return self.json(result)
        if path in ("/api/admin/peer-summary", "/api/admin/peer-reviews.csv"):
            user = self.require_user()
            if not user: return
            managed = self.managed_projects(user)
            if not managed: return self.json({"error": "No tienes permiso para ver la coevaluación."}, 403)
            placeholders = ",".join("?" for _ in managed)
            with connect() as db:
                rows = db.execute("""SELECT r.id resource_id,r.project_id,r.title,s.team_name,s.section,p.scores,p.strength,p.suggestion,
                  p.updated_at,u.display_name,u.email FROM peer_reviews p JOIN resources r ON r.id=p.resource_id
                  JOIN submissions s ON s.id=r.source_submission_id JOIN users u ON u.id=p.reviewer_id
                  WHERE r.project_id IN (""" + placeholders + ") ORDER BY r.project_id,r.title,p.id", managed).fetchall()
            if path.endswith(".csv"):
                keys = [(p, c["key"], c["label"]) for p in managed for c in PEER_RUBRIC[p]]
                return self.send_csv("coevaluacion.csv",
                    ["asignatura", "ficha", "equipo", "paralelo", "evaluador", "correo"] + [f"{PROJECTS[p]['name']}: {label}" for p, _, label in keys]
                    + ["fortaleza", "sugerencia", "fecha"],
                    [[PROJECTS[r["project_id"]]["name"], r["title"], r["team_name"], r["section"], r["display_name"], r["email"]]
                     + [json.loads(r["scores"]).get(k, "") if p == r["project_id"] else "" for p, k, _ in keys]
                     + [r["strength"], r["suggestion"], r["updated_at"]] for r in rows])
            grouped = {}
            for r in rows:
                grouped.setdefault(r["resource_id"], {"resource_id": r["resource_id"], "project_id": r["project_id"], "title": r["title"],
                                                      "team_name": r["team_name"], "section": r["section"], "scores": []})["scores"].append(json.loads(r["scores"]))
            return self.json([{**{k: v for k, v in g.items() if k != "scores"}, **peer_summary(PEER_RUBRIC[g["project_id"]], g["scores"])}
                              for g in grouped.values()])
        if path in ("/api/admin/indicators", "/api/admin/indicators.csv"):
            user = self.require_user()
            if not user: return
            query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            project = query.get("project", [""])[0]
            if project not in self.managed_projects(user): return self.json({"error": "No tienes permiso para esta asignatura."}, 403)
            with connect() as db:
                rows = project_indicators(db, project, query.get("cohort", [""])[0] or None)
            if path.endswith(".csv"):
                return self.send_csv(f"indicadores-{project}-{time.strftime('%Y%m%d')}.csv", ["dimensión", "indicador", "valor"],
                                     [[r["group"], r["label"], r["value"]] for r in rows])
            return self.json(rows)
        if path in ("/api/admin/cohorts", "/api/admin/report", "/api/admin/tracking", "/api/admin/projection", "/api/admin/qr.svg"):
            user = self.require_user()
            if not user: return
            managed = self.managed_projects(user)
            if not managed: return self.json({"error": "No tienes permiso para el panel docente."}, 403)
            query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            arg = lambda name: query.get(name, [""])[0]
            if path == "/api/admin/qr.svg":
                # QR for a page of this site (a work shown on the projector), never for an outside address.
                target = arg("path")
                if not re.fullmatch(r"/(incentiva|innova)/recurso/[A-Za-z0-9-]{1,120}", target): return self.json({"error": "Ruta inválida."}, 400)
                # Shown on the projector to rate that work: open it straight at the peer review.
                return self.send_bytes(qr.svg(BASE_URL + target + "#coevaluacion").encode(), "image/svg+xml")
            with connect() as db:
                if path == "/api/admin/cohorts":
                    items = cohorts(db)
                    for c in items:
                        c["submissions"] = db.execute("SELECT COUNT(*) FROM submissions WHERE cohort=?", (c["name"],)).fetchone()[0]
                        c["members"] = db.execute("SELECT COUNT(*) FROM project_memberships WHERE cohort=? AND status='active'", (c["name"],)).fetchone()[0]
                    return self.json({"current": items[-1]["name"], "cohorts": items})
                project = arg("project")
                if project not in managed: return self.json({"error": "No tienes permiso para esta asignatura."}, 403)
                cohort = arg("cohort") or current_cohort(db)
                if path == "/api/admin/report":
                    return self.json(project_report(db, project, cohort))
                if path == "/api/admin/projection":
                    section = arg("section")
                    rows = db.execute("""SELECT r.id,r.slug,r.title,r.media_url,s.team_name,s.section FROM resources r
                      JOIN submissions s ON s.id=r.source_submission_id WHERE r.project_id=? AND r.status='published' AND s.cohort=?
                      AND (?='' OR s.section=?) ORDER BY s.section,lower(s.team_name)""", (project, cohort, section, section)).fetchall()
                    return self.json([{**dict(r), "embed_url": video_embed_url(r["media_url"]), "path": f"/{project}/recurso/{r['slug']}"} for r in rows])
                # Tracking: who in the cohort is linked to a delivery (as submitter or listed by address) and its state.
                members = db.execute("""SELECT u.id,u.display_name,u.email,m.section FROM project_memberships m JOIN users u ON u.id=m.user_id
                  WHERE m.project_id=? AND m.status='active' AND m.cohort=? ORDER BY m.section,u.display_name""", (project, cohort)).fetchall()
                subs = db.execute("""SELECT id,user_id,team_name,section,status,member_emails,created_at FROM submissions
                  WHERE project_id=? AND cohort=? ORDER BY id""", (project, cohort)).fetchall()
                rank = {"published": 3, "review": 2, "approved": 2, "rejected": 1}
                people = []
                for m in members:
                    linked = [s for s in subs if s["user_id"] == m["id"] or m["email"] in json.loads(s["member_emails"] or "[]")]
                    best = max(linked, key=lambda s: (rank.get(s["status"], 0), s["id"]), default=None)
                    people.append({"name": m["display_name"], "email": m["email"], "section": m["section"],
                                   "team": best["team_name"] if best else "", "status": best["status"] if best else ""})
                teams = {}
                for s in subs:
                    key = (s["section"], s["team_name"].strip().lower())
                    if key not in teams or rank.get(s["status"], 0) >= rank.get(teams[key]["status"], 0):
                        teams[key] = {"team": s["team_name"], "section": s["section"], "status": s["status"], "created_at": s["created_at"]}
                sections = sorted({p["section"] for p in people} | {t["section"] for t in teams.values()})
                summary = [{"section": sec or "Sin paralelo", "members": sum(p["section"] == sec for p in people),
                            "linked": sum(p["section"] == sec and bool(p["status"]) for p in people),
                            "teams": sum(t["section"] == sec for t in teams.values()),
                            "published": sum(t["section"] == sec and t["status"] == "published" for t in teams.values()),
                            "returned": sum(t["section"] == sec and t["status"] == "rejected" for t in teams.values())} for sec in sections]
                return self.json({"cohort": cohort, "summary": summary, "people": people, "teams": sorted(teams.values(), key=lambda t: (t["section"], t["team"].lower()))})
        if path == "/api/admin/staff":
            user = self.require_user()
            if not user: return
            # Each subject's teachers manage their own co-teachers; only global admins see every subject and the admin list.
            managed = self.managed_projects(user)
            if not managed: return self.json({"error": "No tienes permiso para gestionar el equipo docente."}, 403)
            with connect() as db:
                assigned = [dict(r) for r in db.execute("SELECT email,project_id,created_at FROM staff_roles ORDER BY project_id,email") if r["project_id"] in managed]
            configured = [{"email": e, "project_id": p} for p, emails in PROJECT_ADMIN_EMAILS.items() if p in managed for e in sorted(emails)]
            return self.json({"assigned": assigned, "configured": configured, "admins": sorted(ADMIN_EMAILS) if user["role"] == "admin" else []})
        if path == "/api/admin/surveys":
            user = self.require_user()
            if not user: return
            managed = self.managed_projects(user)
            if not managed: return self.json({"error": "No tienes permiso para gestionar encuestas."}, 403)
            placeholders = ",".join("?" for _ in managed)
            with connect() as db:
                rows = db.execute("""SELECT s.id,s.project_id,s.code,s.kind,s.moment,s.title,s.closes_at,s.active,
                  (SELECT COUNT(*) FROM survey_answers a WHERE a.survey_id=s.id) answers
                  FROM surveys s WHERE s.project_id IN (""" + placeholders + ") ORDER BY s.id DESC LIMIT 60", managed).fetchall()
            return self.json([{**dict(r), "url": f"{BASE_URL}/encuesta/{r['code']}", "open": bool(r["active"] and r["closes_at"] > time.time())} for r in rows])
        survey_admin = re.fullmatch(r"/api/admin/surveys/(\d+)/(results|responses\.csv|qr\.svg)", path)
        if survey_admin:
            user = self.require_user()
            if not user: return
            with connect() as db:
                survey = db.execute("SELECT * FROM surveys WHERE id=?", (int(survey_admin.group(1)),)).fetchone()
                if not survey or survey["project_id"] not in self.managed_projects(user): return self.json({"error": "No tienes permiso para esta encuesta."}, 403)
                answers = db.execute("SELECT answer_values,comment FROM survey_answers WHERE survey_id=? ORDER BY answered_on,id", (survey["id"],)).fetchall()
                # An exit (salida/cierre) survey is compared with the latest entry survey of the same kind in the course.
                baseline = None if survey["moment"] == "entrada" else db.execute("""SELECT * FROM surveys WHERE project_id=? AND kind=? AND moment='entrada'
                  AND id<>? ORDER BY id DESC LIMIT 1""", (survey["project_id"], survey["kind"], survey["id"])).fetchone()
                baseline_rows = [json.loads(r[0]) for r in db.execute("SELECT answer_values FROM survey_answers WHERE survey_id=?", (baseline["id"],))] if baseline else []
            items, scale = json.loads(survey["items"]), json.loads(survey["scale"])
            values = [json.loads(a["answer_values"]) for a in answers]
            if survey_admin.group(2) == "qr.svg":
                return self.send_bytes(qr.svg(f"{BASE_URL}/encuesta/{survey['code']}").encode(), "image/svg+xml")
            if survey_admin.group(2) == "responses.csv":
                return self.send_csv(f"encuesta-{survey['code']}.csv", ["respuesta"] + [i["text"] for i in items] + ["comentario"],
                                     [[n + 1] + v + [a["comment"]] for n, (v, a) in enumerate(zip(values, answers))])
            results = survey_results(items, scale, values)
            if baseline:
                before = {r["text"]: r for r in survey_results(json.loads(baseline["items"]), json.loads(baseline["scale"]), baseline_rows)}
                for r in results:
                    previous = before.get(r["text"])
                    r["baseline_mean"] = previous["mean"] if previous else None
                    r["delta"] = round(r["mean"] - previous["mean"], 2) if previous and r["mean"] is not None and previous["mean"] is not None else None
            return self.json({"title": survey["title"], "kind": survey["kind"], "moment": survey["moment"], "scale": scale, "respondents": len(values),
                              "baseline": {"title": baseline["title"], "respondents": len(baseline_rows)} if baseline else None,
                              "items": results, "comments": [a["comment"] for a in answers if a["comment"]]})
        survey_path = re.fullmatch(r"/api/surveys/([A-Za-z0-9-]{4,12})", path)
        if survey_path:
            user = self.require_user()
            if not user: return
            with connect() as db:
                survey = db.execute("SELECT * FROM surveys WHERE code=?", (normalize_code(survey_path.group(1)),)).fetchone()
                if not survey or not self.has_project_access(user, survey["project_id"]):
                    return self.json({"error": "Esta encuesta no existe o no pertenece a tus asignaturas."}, 404)
                answered = bool(db.execute("SELECT 1 FROM survey_respondents WHERE survey_id=? AND user_id=?", (survey["id"], user["id"])).fetchone())
            return self.json({"code": survey["code"], "project_id": survey["project_id"], "title": survey["title"], "kind": survey["kind"],
                              "items": json.loads(survey["items"]), "scale": json.loads(survey["scale"]), "answered": answered,
                              "open": bool(survey["active"] and survey["closes_at"] > time.time())})
        if path == "/api/my-surveys":
            user = self.require_user()
            if not user: return
            project = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query).get("project", [""])[0]
            if not self.has_project_access(user, project): return self.json({"error": "No tienes acceso a esta asignatura."}, 403)
            with connect() as db:
                rows = db.execute("""SELECT s.code,s.title,s.kind,s.closes_at,s.active,
                  EXISTS(SELECT 1 FROM survey_respondents r WHERE r.survey_id=s.id AND r.user_id=?) answered
                  FROM surveys s WHERE s.project_id=? ORDER BY s.id DESC LIMIT 30""", (user["id"], project)).fetchall()
            return self.json([{**dict(r), "answered": bool(r["answered"]), "open": bool(r["active"] and r["closes_at"] > time.time())} for r in rows])
        if path == "/api/admin/person":
            user = self.require_user()
            if not user: return
            if user["role"] != "admin": return self.json({"error": "Solo la administración global atiende solicitudes de datos."}, 403)
            email = str(urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query).get("email", [""])[0]).strip().lower()
            with connect() as db:
                data = person_export(db, email)
            if not data: return self.json({"error": "No hay una cuenta con ese correo."}, 404)
            body = json.dumps(data, ensure_ascii=False, indent=2).encode()
            return self.send_bytes(body, "application/json; charset=utf-8", headers={"Content-Disposition": f"attachment; filename=datos-{email.split('@')[0]}.json"})
        if path == "/api/projects":
            user = self.require_user()
            if not user: return
            return self.json({key:PROJECTS[key] for key in self.active_projects(user)})
        material_path = re.fullmatch(r"/api/projects/(incentiva|innova)/resources/([^/]+)/file", path)
        if material_path:
            user=self.require_user()
            if not user: return
            project,slug=material_path.groups()
            if not self.has_project_access(user,project): return self.json({"error":"No tienes acceso a esta asignatura."},403)
            with connect() as db:
                row=db.execute("SELECT status,file_storage_key,file_filename FROM resources WHERE project_id=? AND slug=?",(project,slug)).fetchone()
            if not row or not row["file_storage_key"] or (row["status"]!="published" and project not in self.managed_projects(user)):
                return self.json({"error":"Archivo no disponible."},404)
            key=row["file_storage_key"]
            if not re.fullmatch(r"[a-f0-9]{40}",key): return self.json({"error":"Archivo no encontrado."},404)
            file_path=UPLOAD_DIR/key
            if not file_path.is_file(): return self.json({"error":"El archivo ya no está disponible."},404)
            filename=urllib.parse.quote(row["file_filename"] or "material",safe="")
            return self.send_bytes(file_path.read_bytes(),"application/octet-stream",headers={"Content-Disposition":f"attachment; filename*=UTF-8''{filename}"})
        if path == "/api/admin/pending-counts":
            user = self.require_user()
            if not user: return
            managed = self.managed_projects(user)
            if not managed: return self.json({"error": "No tienes permiso para moderar."}, 403)
            with connect() as db:
                counts = pending_counts(db, managed)
                off = db.execute("SELECT 1 FROM settings WHERE key=?", (f"notify_off:{user['email'].lower()}",)).fetchone()
            return self.json({**counts, "email_enabled": not off, "email_ready": self.email_transport_ready()})
        if path == "/api/admin/pending":
            user = self.require_user()
            if not user: return
            managed = self.managed_projects(user)
            if not managed: return self.json({"error": "No tienes permiso para moderar."}, 403)
            placeholders = ",".join("?" for _ in managed)
            with connect() as db:
                submissions = db.execute("""SELECT s.id,s.project_id,s.team_name,s.section,s.members,s.title,s.summary,s.video_url,s.evidence_url,
                  s.alternatives,CASE WHEN s.model_storage_key<>'' THEN 1 ELSE 0 END has_model,
                  s.project_fields,s.ai_declaration,s.consent_confirmed,s.evidence_storage_key,s.evidence_filename,s.created_at,u.display_name,u.email FROM submissions s
                  JOIN users u ON u.id=s.user_id WHERE s.status='review' AND s.project_id IN ("""+placeholders+") ORDER BY s.id DESC", managed).fetchall()
                comments = db.execute("""SELECT c.id,c.body,c.badge,c.parent_id,c.created_at,r.title resource_title,r.project_id,u.display_name,u.email
                  FROM comments c JOIN resources r ON r.id=c.resource_id JOIN users u ON u.id=c.user_id
                  WHERE c.status='review' AND r.project_id IN ("""+placeholders+") ORDER BY c.id DESC", managed).fetchall()
                requests = db.execute("""SELECT m.id,m.project_id,m.requested_at,u.display_name,u.email
                  FROM project_memberships m JOIN users u ON u.id=m.user_id
                  WHERE m.status='pending' AND m.project_id IN ("""+placeholders+") ORDER BY m.id", managed).fetchall()
            submissions = [{**dict(r), "members": json.loads(r["members"] or "[]"), "alternatives": json.loads(r["alternatives"] or "{}"),
                            "fields": labeled_fields(r["project_id"], json.loads(r["project_fields"] or "{}"))} for r in submissions]
            return self.json({"submissions":submissions,"comments":[dict(r) for r in comments],
                              "access_requests":[dict(r) for r in requests]})
        if path == "/api/resources":
            if not self.require_user(): return
            query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            project = query.get("project", [""])[0]
            user = self.current_user()
            member = self.has_project_access(user, project)
            # Readers of an open project see only student work whose team agreed to the wider showcase.
            if not member and project not in self.reader_projects(user):
                return self.json({"error": "No tienes acceso a esta asignatura."}, 403)
            with connect() as db:
                rows = db.execute("""SELECT r.id,r.project_id,r.slug,r.title,r.category,r.summary,r.content,r.tags,r.media_url,r.source_submission_id,
                  r.file_filename,CASE WHEN r.file_storage_key<>'' THEN 1 ELSE 0 END has_file,r.guide_question,r.quiz,
                  COALESCE(s.team_name,'') team_name,COALESCE(s.section,'') section,COALESCE(s.members,'[]') members,
                  COALESCE(s.project_fields,'{}') project_fields,COALESCE(s.ai_declaration,'') ai_declaration,
                  COALESCE(s.has_subtitles,0) has_subtitles,COALESCE(s.showcase_consent,0) showcase_consent,
                  COALESCE(s.cohort,'') cohort,CASE WHEN COALESCE(s.model_storage_key,'')<>'' THEN 1 ELSE 0 END has_model,
                  COALESCE(s.alternatives,'{}') alternatives,CASE WHEN COALESCE(s.evidence_storage_key,'')<>'' THEN 1 ELSE 0 END has_evidence,
                  (SELECT COUNT(*) FROM comments c WHERE c.resource_id=r.id AND c.status='published') comment_count
                  FROM resources r LEFT JOIN submissions s ON s.id=r.source_submission_id
                  WHERE r.project_id=? AND r.status='published' ORDER BY r.id""", (project,)).fetchall()
            result = []
            for row in rows:
                item = dict(row)
                if not member and not item["showcase_consent"]: continue
                item["tags"], item["members"] = json.loads(item["tags"]), json.loads(item["members"])
                item["fields"] = labeled_fields(project, json.loads(item.pop("project_fields")))
                item["alternatives"] = json.loads(item["alternatives"] or "{}")
                item["quiz_count"] = len(json.loads(item.pop("quiz") or "[]"))
                item["guide_question"] = item["guide_question"] or GUIDE_QUESTIONS[project]
                item["embed_url"] = video_embed_url(item["media_url"])
                if not member: item.update(has_file=0, file_filename="", quiz_count=0, comment_count=0, has_model=0, has_evidence=0)
                result.append(item)
            return self.json(result)
        submission_file = re.fullmatch(r"/api/submissions/(\d+)/(evidence|model|ficha)", path)
        if submission_file:
            user = self.require_user()
            if not user: return
            with connect() as db:
                row = db.execute("SELECT * FROM submissions WHERE id=?", (int(submission_file.group(1)),)).fetchone()
            if not row: return self.json({"error":"Entrega no encontrada."},404)
            if not self.can_view_submission(user, row): return self.json({"error":"No tienes acceso a esta entrega."},403)
            kind = submission_file.group(2)
            if kind == "ficha":
                # The evidence sheet is generated from what the team entered, so nobody has to write it twice.
                alternatives = json.loads(row["alternatives"] or "{}")
                return self.json({"id": row["id"], "project_id": row["project_id"], "project_name": PROJECTS[row["project_id"]]["name"],
                                  "course": PROJECTS[row["project_id"]]["course"], "cohort": row["cohort"], "team_name": row["team_name"],
                                  "section": row["section"], "members": json.loads(row["members"] or "[]"), "title": row["title"],
                                  "summary": row["summary"], "fields": labeled_fields(row["project_id"], json.loads(row["project_fields"] or "{}")),
                                  "alternatives": alternatives, "video_url": row["video_url"], "evidence_url": row["evidence_url"],
                                  "evidence_filename": row["evidence_filename"], "model_filename": row["model_filename"],
                                  "ai_declaration": row["ai_declaration"], "has_subtitles": bool(row["has_subtitles"]),
                                  "status": row["status"], "created_at": row["created_at"]})
            key, filename = (row["evidence_storage_key"], row["evidence_filename"] or "ficha") if kind == "evidence" else (row["model_storage_key"], row["model_filename"] or "modelo.stl")
            if not re.fullmatch(r"[a-f0-9]{40}", key or ""): return self.json({"error":"Archivo no encontrado."},404)
            file_path = UPLOAD_DIR / key
            if not file_path.is_file(): return self.json({"error":"El archivo ya no está disponible."},404)
            name = urllib.parse.quote(filename, safe="")
            disposition = "inline" if kind == "model" else "attachment"
            return self.send_bytes(file_path.read_bytes(), "model/stl" if kind == "model" else "application/octet-stream", headers={
                "Content-Disposition": f"{disposition}; filename*=UTF-8''{name}", "X-Content-Type-Options":"nosniff"})
        comment_path = re.fullmatch(r"/api/projects/(incentiva|innova)/resources/([^/]+)/comments", path)
        if comment_path:
            user = self.require_user()
            if not user: return
            project, slug = comment_path.groups()
            if not self.has_project_access(user, project): return self.json({"error":"No tienes acceso a esta asignatura."},403)
            with connect() as db:
                rows = db.execute("""SELECT c.id,c.parent_id,c.badge,c.body,c.created_at,u.display_name FROM comments c
                  JOIN resources r ON r.id=c.resource_id JOIN users u ON u.id=c.user_id
                  WHERE r.project_id=? AND r.slug=? AND c.status='published' AND (r.status='published' OR ?) ORDER BY c.id LIMIT 200""",
                  (project, slug, project in self.managed_projects(user))).fetchall()
            return self.json([dict(r) for r in rows])
        downloadable = re.fullmatch(r"/materiales/(kit-incentiva\.pdf|kit-innova\.pdf|consentimiento\.pdf|ficha-evidencia-incentiva\.docx|matriz-diagnostica-innova\.docx)", path)
        if downloadable:
            # Public course templates (no personal data); everything else in the folder stays unreachable.
            file = ROOT / "materiales" / downloadable.group(1)
            if not file.is_file(): return self.json({"error": "No encontrado."}, 404)
            kind = "application/pdf" if file.suffix == ".pdf" else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            return self.send_bytes(file.read_bytes(), kind, headers={"Content-Disposition": f"attachment; filename={file.name}"})
        if path.startswith("/static/"):
            name = path.rsplit("/", 1)[-1]
            allowed = {"styles.css", "app.js", "theme.js"}
            if name not in allowed: return self.json({"error": "No encontrado."}, 404)
            file = ROOT / "static" / name
            kind = "text/css; charset=utf-8" if name.endswith(".css") else "text/javascript; charset=utf-8"
            return self.send_bytes(file.read_bytes(), kind)
        # The shell contains no course data; all project records are behind the authenticated API.
        if path in ("/", "/login", "/admin", "/privacidad", "/consentimiento", "/ayuda") or re.fullmatch(r"/(tiquete|encuesta)/[A-Za-z0-9-]{4,12}", path) or re.fullmatch(r"/kit(/incentiva|/innova)?", path) or re.fullmatch(r"/(ficha/\d+|proyeccion/(incentiva|innova)|informe/(incentiva|innova))", path) or path == "/incentiva" or path.startswith("/incentiva/") or path == "/innova" or path.startswith("/innova/"):
            return self.send_bytes((ROOT / "index.html").read_bytes())
        return self.json({"error": "No encontrado."}, 404)

    def route_post(self):
        path = urllib.parse.urlparse(self.path).path
        # Second layer against cross-site requests besides SameSite=Lax: browsers send Origin on POST, and it must
        # match the host the page was served from (works behind Render's proxy and on localhost or 127.0.0.1 alike).
        origin = self.headers.get("Origin")
        if origin is not None and urllib.parse.urlparse(origin).netloc != self.headers.get("Host", ""):
            return self.json({"error": "Solicitud bloqueada: no proviene de este sitio."}, 403)
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            return self.json({"error":"Solicitud inválida."},400)
        limit = (24 if path == "/api/submissions" else 12) * 1024 * 1024 if path in ("/api/submissions","/api/admin/resources","/api/admin/resources/update") else 100_000
        if content_length < 0 or content_length > limit:
            return self.json({"error":"La solicitud supera el tamaño permitido."},413)
        length = content_length
        raw = self.rfile.read(length)
        if self.headers.get("Content-Type", "").startswith("application/x-www-form-urlencoded"):
            payload = {key: values[0] for key, values in urllib.parse.parse_qs(raw.decode("utf-8", "replace")).items()}
        else:
            try:
                payload = json.loads(raw or b"{}")
            except json.JSONDecodeError:
                return self.json({"error": "Solicitud inválida."}, 400)
        if not isinstance(payload, dict):
            return self.json({"error": "Solicitud inválida."}, 400)
        if path == "/auth/request-link":
            return self.request_login_link(payload)
        if path == "/auth/verify":
            token = str(payload.get("token", ""))
            if not token or len(token) > 120:
                return self.redirect("/login?error=expired")
            now = int(time.time())
            with connect() as db:
                row = db.execute("SELECT id,email FROM email_login_tokens WHERE token_hash=? AND expires_at>? AND used_at IS NULL",
                                 (token_hash(token), now)).fetchone()
                if not row: return self.redirect("/login?error=expired")
                changed = db.execute("UPDATE email_login_tokens SET used_at=? WHERE id=? AND used_at IS NULL", (now, row["id"]))
                if not changed.rowcount: return self.redirect("/login?error=expired")
            email = row["email"]
            return self.create_session(email, name_from_email(email), provider_subject="email:" + email)
        if path == "/auth/code":
            return self.login_with_access_code(payload)
        if path == "/api/join":
            user = self.require_user()
            if not user: return
            code = normalize_code(payload.get("code", ""))
            failure = {"error": "El código no es válido o ya venció. Pídelo nuevamente a la docente."}
            with connect() as db:
                bucket = f"join:{user['id']}"
                if is_rate_limited(db, bucket, 8, 15 * 60):
                    return self.json({"error": "Demasiados intentos. Espera unos minutos e inténtalo de nuevo."}, 429)
                row = db.execute("SELECT * FROM join_codes WHERE code=?", (code,)).fetchone() if code else None
                if not join_code_usable(row) or (row["roster"] and user["email"].lower() not in row["roster"].split()):
                    record_rate_event(db, bucket)
                    return self.json(failure, 400)
                project = row["project_id"]
                if self.has_project_access(user, project):
                    if row["section"]:
                        db.execute("UPDATE project_memberships SET section=? WHERE user_id=? AND project_id=? AND status='active' AND section=''",
                                   (row["section"], user["id"], project))
                    record_audit_event(db, "course_code_login", user["email"], user["email"], project, "join_code", row["id"],
                                       ip_hash=audit_ip_hash(db, self.client_ip()))
                    return self.json({"ok": True, "project_id": project, "message": "Ya tenías acceso a esta asignatura."})
                member = db.execute("SELECT revoked FROM project_memberships WHERE user_id=? AND project_id=?", (user["id"], project)).fetchone()
                if member and member["revoked"]:
                    return self.json({"error": "Tu acceso a esta asignatura fue retirado. Contacta a la docente."}, 403)
                # A code created for one paralelo also records it, so deliveries and the catalog can be filtered by section.
                apply_join_code(db, user["id"], row)
                record_audit_event(db, "course_code_login", user["email"], user["email"], project, "join_code", row["id"],
                                   ip_hash=audit_ip_hash(db, self.client_ip()))
            return self.json({"ok": True, "project_id": project, "message": f"Listo: ya tienes acceso a {PROJECTS[project]['name']}."})
        if path == "/api/admin/join-codes":
            user = self.require_user()
            if not user: return
            project = str(payload.get("project_id", ""))
            if project not in self.managed_projects(user): return self.json({"error": "No tienes permiso para esta asignatura."}, 403)
            label = str(payload.get("label", "")).strip()[:80]
            section = str(payload.get("section", "")).strip()
            if section and section not in PROJECT_SECTIONS[project]: return self.json({"error": "Elige un paralelo válido."}, 400)
            try:
                days = max(1, min(int(payload.get("days") or 14), 180))
                max_uses = int(payload["max_uses"]) if str(payload.get("max_uses", "")).strip() else None
            except (TypeError, ValueError):
                return self.json({"error": "Revisa la duración y el número de usos."}, 400)
            if max_uses is not None and not 1 <= max_uses <= 1000: return self.json({"error": "El máximo de usos debe estar entre 1 y 1000."}, 400)
            roster = roster_emails(payload.get("roster", ""))
            if str(payload.get("roster", "")).strip() and not roster:
                return self.json({"error": "La lista no tiene correos institucionales válidos."}, 400)
            if len(roster) > 1000: return self.json({"error": "La lista admite hasta 1000 correos."}, 400)
            now = int(time.time())
            with connect() as db:
                for _ in range(5):
                    code = new_code()
                    try:
                        created = db.execute("""INSERT INTO join_codes(code,project_id,label,section,created_by,created_at,expires_at,max_uses,cohort,roster)
                          VALUES(?,?,?,?,?,?,?,?,?,?)""", (code, project, label, section, user["id"], now, now + days * 86400, max_uses, current_cohort(db),
                                                         "\n".join(roster)))
                        record_audit_event(db, "course_code_created", user["email"], project_id=project,
                                           entity_type="join_code", entity_id=created.lastrowid,
                                           ip_hash=audit_ip_hash(db, self.client_ip()))
                        break
                    except sqlite3.IntegrityError:
                        continue
            return self.json({"ok": True, "code": format_code(code), "roster_size": len(roster)}, 201)
        if path == "/api/admin/join-codes/disable":
            user = self.require_user()
            if not user: return
            try: code_id = int(payload.get("id", 0))
            except (TypeError, ValueError): return self.json({"error": "Identificador inválido."}, 400)
            with connect() as db:
                row = db.execute("SELECT project_id,active FROM join_codes WHERE id=?", (code_id,)).fetchone()
                if not row or row["project_id"] not in self.managed_projects(user): return self.json({"error": "No tienes permiso para este código."}, 403)
                changed = db.execute("UPDATE join_codes SET active=0 WHERE id=? AND active=1", (code_id,))
                if changed.rowcount:
                    record_audit_event(db, "course_code_disabled", user["email"], project_id=row["project_id"],
                                       entity_type="join_code", entity_id=code_id, ip_hash=audit_ip_hash(db, self.client_ip()))
            return self.json({"ok": True})
        if path == "/api/admin/access-codes":
            user = self.require_user()
            if not user: return
            project = str(payload.get("project_id", ""))
            if project not in self.managed_projects(user): return self.json({"error": "No tienes permiso para esta asignatura."}, 403)
            raw = re.split(r"[\s,;]+", str(payload.get("emails", ""))[:20000])
            emails, invalid = [], []
            for item in raw:
                if not item: continue
                email = institutional_email(item)
                if email and email not in emails: emails.append(email)
                elif not email: invalid.append(item[:80])
            if not emails: return self.json({"error": "Pega al menos un correo @mail.pucv.cl o @pucv.cl."}, 400)
            if len(emails) > 300: return self.json({"error": "Genera como máximo 300 códigos por vez."}, 400)
            try: days = max(1, min(int(payload.get("days") or 30), 180))
            except (TypeError, ValueError, OverflowError): return self.json({"error": "Revisa la duración."}, 400)
            with connect() as db:
                refused = []
                if user["role"] != "admin":
                    # A code signs in as that account, so a course editor must not obtain one for staff or for people
                    # who also belong to a course the editor does not manage.
                    staff, managed = staff_emails(db), set(self.managed_projects(user))
                    for email in emails:
                        other = db.execute("""SELECT 1 FROM project_memberships m JOIN users u ON u.id=m.user_id
                          WHERE u.email=? AND m.status='active' AND m.project_id NOT IN (""" + ",".join("?" for _ in managed) + ")",
                          (email, *managed)).fetchone()
                        if email in staff or other: refused.append(email)
                    emails = [e for e in emails if e not in refused]
                issued = issue_access_codes(db, emails, project, user["id"], days) if emails else []
            return self.json({"ok": True, "codes": issued, "invalid": invalid[:50], "refused": refused, "days": days}, 201)
        if path == "/auth/demo":
            if not DEMO_AUTH:
                return self.json({"error": "El acceso de demostración está desactivado."}, 403)
            email = str(payload.get("email", "")).strip().lower()
            domain = email.rsplit("@", 1)[-1] if "@" in email else ""
            if domain not in ALLOWED_EMAIL_DOMAINS:
                return self.json({"error": "Usa un correo institucional PUCV permitido."}, 403)
            name = str(payload.get("name", "Invitado de demostración"))[:100]
            return self.create_session(email, name, provider_subject="demo:" + email)
        if path == "/api/admin/resources":
            user=self.require_user()
            if not user: return
            project=str(payload.get("project_id",""))
            if project not in self.managed_projects(user): return self.json({"error":"No tienes permiso para cargar materiales en esta asignatura."},403)
            title=str(payload.get("title","")).strip()[:180]
            category=str(payload.get("category","")).strip()[:100]
            summary=str(payload.get("summary","")).strip()[:2000]
            file_b64=payload.get("file_base64","")
            content=str(payload.get("content","")).strip()[:20000]
            status="draft" if payload.get("status")=="draft" else "published"
            # A material is a file, a written text (e.g. a challenge dossier), or both.
            if not title or not category or not summary or not (file_b64 or content):
                return self.json({"error":"Completa título, tipo y descripción, y agrega un texto o un archivo."},400)
            storage_key,filename="",""
            if file_b64:
                try: file_bytes,filename=decode_upload(file_b64,payload.get("filename","material"))
                except UploadError as error: return self.json({"error":str(error)},error.status)
                storage_key=secrets.token_hex(20)
                UPLOAD_DIR.mkdir(parents=True,exist_ok=True)
                (UPLOAD_DIR/storage_key).write_bytes(file_bytes)
            normalized=unicodedata.normalize("NFKD",title.lower()).encode("ascii","ignore").decode()
            base_slug=re.sub(r"[^a-z0-9]+","-",normalized).strip("-")[:90] or "material"
            tags=clean_tags(payload.get("tags",""))
            try:
                with connect() as db:
                    slug=base_slug;suffix_num=2
                    while db.execute("SELECT 1 FROM resources WHERE project_id=? AND slug=?",(project,slug)).fetchone():
                        slug=f"{base_slug}-{suffix_num}";suffix_num+=1
                    db.execute("""INSERT INTO resources(project_id,slug,title,category,summary,content,tags,status,file_storage_key,file_filename,edited_at)
                      VALUES(?,?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)""",
                      (project,slug,title,category,summary,content,json.dumps(tags,ensure_ascii=False),status,storage_key,filename))
            except Exception:
                if storage_key: (UPLOAD_DIR/storage_key).unlink(missing_ok=True)
                raise
            return self.json({"ok":True,"message":"Borrador guardado: publícalo desde «Materiales del repositorio»." if status=="draft" else "Material agregado al repositorio de la asignatura."},201)
        if path == "/api/admin/resources/update":
            user=self.require_user()
            if not user: return
            try: resource_id=int(payload.get("id",0))
            except (TypeError,ValueError): return self.json({"error":"Identificador inválido."},400)
            title=str(payload.get("title","")).strip()[:180]
            category=str(payload.get("category","")).strip()[:100]
            summary=str(payload.get("summary","")).strip()[:2000]
            status=str(payload.get("status","published"))
            if not title or not category or not summary: return self.json({"error":"Completa título, tipo y descripción."},400)
            # Retiring keeps the record and its comments; 'draft' hides it from the catalog and can be reverted.
            if status not in ("published","draft"): return self.json({"error":"Estado inválido."},400)
            guide_question=str(payload.get("guide_question","")).strip()[:400]
            quiz,quiz_error=parse_quiz(payload.get("quiz",""))
            if quiz_error: return self.json({"error":quiz_error},400)
            new_key,new_name="",""
            if payload.get("file_base64"):
                try: file_bytes,new_name=decode_upload(payload["file_base64"],payload.get("filename","material"))
                except UploadError as error: return self.json({"error":str(error)},error.status)
                new_key=secrets.token_hex(20)
            with connect() as db:
                row=db.execute("SELECT project_id,file_storage_key FROM resources WHERE id=?",(resource_id,)).fetchone()
                if not row or row["project_id"] not in self.managed_projects(user): return self.json({"error":"No tienes permiso para editar este material."},403)
                if new_key:
                    UPLOAD_DIR.mkdir(parents=True,exist_ok=True)
                    (UPLOAD_DIR/new_key).write_bytes(file_bytes)
                old_quiz=db.execute("SELECT quiz FROM resources WHERE id=?",(resource_id,)).fetchone()["quiz"]
                # Changing the questions invalidates earlier answers, which no longer match the options.
                if json.loads(old_quiz or "[]")!=quiz: db.execute("DELETE FROM quiz_attempts WHERE resource_id=?",(resource_id,))
                db.execute("UPDATE resources SET guide_question=?,quiz=? WHERE id=?",(guide_question,json.dumps(quiz,ensure_ascii=False),resource_id))
                if "content" in payload: db.execute("UPDATE resources SET content=? WHERE id=?",(str(payload.get("content","")).strip()[:20000],resource_id))
                db.execute("""UPDATE resources SET title=?,category=?,summary=?,tags=?,status=?,edited_at=CURRENT_TIMESTAMP,
                  file_storage_key=CASE WHEN ?<>'' THEN ? ELSE file_storage_key END,file_filename=CASE WHEN ?<>'' THEN ? ELSE file_filename END
                  WHERE id=?""",(title,category,summary,json.dumps(clean_tags(payload.get("tags","")),ensure_ascii=False),status,
                                 new_key,new_key,new_name,new_name,resource_id))
            old_key=row["file_storage_key"]
            if new_key and re.fullmatch(r"[a-f0-9]{40}",old_key or ""): (UPLOAD_DIR/old_key).unlink(missing_ok=True)
            return self.json({"ok":True,"message":"Material retirado del catálogo." if status=="draft" else "Material actualizado."})
        if path == "/api/access-requests":
            user = self.require_user()
            if not user: return
            project = str(payload.get("project_id", ""))
            if project not in PROJECTS: return self.json({"error":"Proyecto inválido."},400)
            if self.has_project_access(user, project):
                return self.json({"ok":True,"message":"Ya tienes acceso a este proyecto."})
            with connect() as db:
                if db.execute("SELECT 1 FROM project_memberships WHERE user_id=? AND project_id=? AND revoked=1", (user["id"], project)).fetchone():
                    return self.json({"error": "Tu acceso a esta asignatura fue retirado. Contacta a la docente."}, 403)
                db.execute("""INSERT INTO project_memberships(user_id,project_id,status,cohort) VALUES(?,?,'pending',?)
                  ON CONFLICT(user_id,project_id) DO UPDATE SET cohort=excluded.cohort,
                  status=CASE WHEN project_memberships.status='active' THEN 'active' ELSE 'pending' END,
                  requested_at=CASE WHEN project_memberships.status='active' THEN project_memberships.requested_at ELSE CURRENT_TIMESTAMP END,
                  reviewed_at=NULL,reviewed_by=NULL""",(user["id"],project,current_cohort(db)))
                notify_teachers(db, project, force=True)
            return self.json({"ok":True,"message":"Solicitud enviada. La docente debe aprobar el acceso."},201)
        if path == "/api/comments":
            user = self.require_user()
            if not user: return
            project = str(payload.get("project_id", ""))
            if project not in PROJECTS: return self.json({"error": "Proyecto inválido."}, 400)
            if not self.has_project_access(user, project): return self.json({"error":"No tienes acceso a esta asignatura."},403)
            slug = str(payload.get("slug", ""))[:120]
            body = str(payload.get("body", "")).strip()
            if not body or len(body) > 1200:
                return self.json({"error": "El comentario debe tener entre 1 y 1200 caracteres."}, 400)
            teacher = project in self.managed_projects(user)
            with connect() as db:
                bucket = f"comment:{user['id']}"
                if not teacher and is_rate_limited(db, bucket, 20, 60 * 60):
                    return self.json({"error": "Enviaste muchos comentarios en la última hora. Espera un poco antes de seguir."}, 429)
                record_rate_event(db, bucket)
                resource = db.execute("SELECT id FROM resources WHERE project_id=? AND slug=? AND status='published'", (project,slug)).fetchone()
                if not resource: return self.json({"error": "Recurso no encontrado."}, 404)
                parent_id = None
                if payload.get("parent_id"):
                    try: parent_id = int(payload["parent_id"])
                    except (TypeError, ValueError): return self.json({"error": "Respuesta inválida."}, 400)
                    # Threads have one level: replies always hang from a top-level comment of the same resource.
                    parent = db.execute("SELECT id,parent_id FROM comments WHERE id=? AND resource_id=? AND status='published'", (parent_id, resource["id"])).fetchone()
                    if not parent: return self.json({"error": "El comentario que respondes ya no está disponible."}, 404)
                    parent_id = parent["parent_id"] or parent["id"]
                badge = "docente" if teacher else ("equipo" if is_author(resource_authors(db, resource["id"]), user) else "")
                status = "published" if teacher else "review"
                db.execute("INSERT INTO comments(resource_id,user_id,body,status,parent_id,badge) VALUES(?,?,?,?,?,?)",
                           (resource["id"], user["id"], body, status, parent_id, badge))
            message = "Comentario publicado." if teacher else "Comentario recibido. Quedará visible después de la revisión."
            return self.json({"ok": True, "status": status, "message": message}, 201)
        if path == "/api/submissions":
            user = self.require_user()
            if not user: return
            project = str(payload.get("project_id", ""))
            if project not in PROJECTS: return self.json({"error": "Proyecto inválido."}, 400)
            if not self.has_project_access(user, project): return self.json({"error":"No tienes acceso a esta asignatura."},403)
            title = str(payload.get("title", "")).strip()[:180]
            team_name = str(payload.get("team_name", "")).strip()[:160]
            summary = str(payload.get("summary", "")).strip()[:5000]
            if not title or not team_name or not summary: return self.json({"error": "Completa equipo, título y resumen."}, 400)
            section = str(payload.get("section", "")).strip()
            if PROJECT_SECTIONS[project] and section not in PROJECT_SECTIONS[project]: return self.json({"error": "Indica el paralelo del equipo."}, 400)
            if not PROJECT_SECTIONS[project]: section = ""
            members, member_emails = clean_members(payload.get("members", ""))
            if not members: return self.json({"error": "Indica quiénes integran el equipo (un nombre por línea)."}, 400)
            project_fields, fields_error = clean_project_fields(project, payload.get("project_fields", {}))
            if fields_error: return self.json({"error": fields_error}, 400)
            alternatives, alternatives_error = clean_alternatives(payload.get("alternatives") if project == "incentiva" else None)
            if alternatives_error: return self.json({"error": alternatives_error}, 400)
            video_url = str(payload.get("video_url", "")).strip()[:1000]
            evidence_url = str(payload.get("evidence_url", "")).strip()[:1000]
            upload_key = ""
            upload_filename = ""
            upload_bytes = b""
            file_b64 = payload.get("evidence_file_base64", "")
            if file_b64:
                try: upload_bytes, upload_filename = decode_upload(file_b64, payload.get("evidence_filename", "ficha"), "La ficha")
                except UploadError as error: return self.json({"error": str(error)}, error.status)
                upload_key=secrets.token_hex(20)
            model_key, model_name, model_bytes = "", "", b""
            if project == "innova" and payload.get("model_file_base64"):
                model_b64 = payload["model_file_base64"]
                if not isinstance(model_b64, str) or len(model_b64) > 11_184_812: return self.json({"error": "El modelo 3D debe pesar como máximo 8 MB."}, 413)
                try: model_bytes = base64.b64decode(model_b64, validate=True)
                except (binascii.Error, ValueError): return self.json({"error": "No pudimos leer el modelo 3D."}, 400)
                model_name = Path(str(payload.get("model_filename", "modelo.stl"))[:180].replace("\\", "/")).name
                if not model_name.lower().endswith(".stl") or not valid_stl(model_bytes): return self.json({"error": "El modelo 3D debe ser un archivo STL válido."}, 400)
                model_key = secrets.token_hex(20)
            # The evidence sheet is generated from the form; a separate file or folder is optional.
            if not video_url: return self.json({"error": "Incluye el enlace al único video final."}, 400)
            for url in (video_url, evidence_url):
                if url:
                    parsed_url = urllib.parse.urlparse(url)
                    if parsed_url.scheme != "https" or not parsed_url.netloc or parsed_url.username or parsed_url.password:
                        return self.json({"error": "Los enlaces deben comenzar con https://"}, 400)
            # This records a content-rights/safe-media declaration, not consent to future or public use.
            consent = int(bool(payload.get("consent_confirmed")))
            if not consent: return self.json({"error": "Confirma que las imágenes, voces y recursos identificables tienen autorización o que el video evita identificarlos."}, 400)
            if not payload.get("video_length_confirmed"):
                return self.json({"error":"Confirma que el enlace corresponde al video final único de máximo cinco minutos."},400)
            with connect() as db:
                cohort = current_cohort(db)
                existing=db.execute("""SELECT 1 FROM submissions WHERE project_id=? AND cohort=? AND lower(trim(section))=lower(trim(?))
                  AND lower(trim(team_name))=lower(trim(?)) AND status<>'rejected'""", (project,cohort,section,team_name)).fetchone()
                if existing: return self.json({"error":"Este equipo ya registró su entrega final. Contacten a la docente para reemplazarla si corresponde."},409)
                UPLOAD_DIR.mkdir(parents=True,exist_ok=True)
                if upload_key: (UPLOAD_DIR/upload_key).write_bytes(upload_bytes)
                if model_key: (UPLOAD_DIR/model_key).write_bytes(model_bytes)
                try:
                    cur = db.execute("""INSERT INTO submissions(project_id,user_id,team_name,section,members,member_emails,title,summary,video_url,evidence_url,
                      evidence_storage_key,evidence_filename,project_fields,ai_declaration,consent_confirmed,has_subtitles,showcase_consent,
                      cohort,alternatives,model_storage_key,model_filename)
                      VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                      (project, user["id"], team_name, section, json.dumps(members, ensure_ascii=False), json.dumps(member_emails), title, summary,
                       video_url, evidence_url, upload_key,upload_filename,json.dumps(project_fields, ensure_ascii=False),
                       str(payload.get("ai_declaration", ""))[:2000],consent,int(bool(payload.get("has_subtitles"))),int(bool(payload.get("showcase_consent"))),
                       cohort, json.dumps(alternatives, ensure_ascii=False), model_key, model_name))
                except sqlite3.IntegrityError:
                    for key in (upload_key, model_key):
                        if key: (UPLOAD_DIR/key).unlink(missing_ok=True)
                    return self.json({"error":"Este equipo ya registró una entrega final."},409)
                notify_teachers(db, project, force=True)
            return self.json({"ok": True, "id": cur.lastrowid, "message": "Entrega recibida para revisión. Ya puedes descargar la ficha de evidencia generada."}, 201)
        if path == "/api/admin/tickets":
            user = self.require_user()
            if not user: return
            project = str(payload.get("project_id", ""))
            if project not in self.managed_projects(user): return self.json({"error": "No tienes permiso para esta asignatura."}, 403)
            title = str(payload.get("title", "")).strip()[:120]
            if str(payload.get("questions_text", "")).strip():
                # Questions pasted from Word or an e-mail: one per line; numbering and bullets are removed.
                pasted = [re.sub(r"^\s*(?:\d+[.)]|[-–•*])\s*", "", line).strip() for line in str(payload["questions_text"]).splitlines()]
                pasted = [q for q in pasted if q]
                if len(pasted) > 5: return self.json({"error": f"Pegaste {len(pasted)} preguntas: el máximo es 5 preguntas por tiquete."}, 400)
                if any(len(q) > 400 for q in pasted): return self.json({"error": "Cada pregunta puede tener hasta 400 caracteres."}, 400)
                raw_questions = pasted
            else:
                raw_questions = payload.get("questions") if isinstance(payload.get("questions"), list) else []
            questions = [str(q).strip()[:400] for q in raw_questions if str(q).strip()][:5]
            if not title: return self.json({"error": "Ponle un nombre a la sesión (por ejemplo, «Fase 1 · sesión 3»)."}, 400)
            kind = "previa" if payload.get("kind") == "previa" else "salida"
            if not questions: questions = PRE_SESSION_QUESTIONS[project] if kind == "previa" else EXIT_TICKET_QUESTIONS[project]
            try: hours = max(1, min(int(payload.get("hours") or 24), 24 * 14))
            except (TypeError, ValueError): return self.json({"error": "Revisa la duración."}, 400)
            now = int(time.time())
            with connect() as db:
                for _ in range(5):
                    code = new_code(6)
                    try:
                        db.execute("""INSERT INTO exit_tickets(project_id,code,title,questions,created_by,created_at,closes_at,kind,cohort)
                          VALUES(?,?,?,?,?,?,?,?,?)""", (project, code, title, json.dumps(questions, ensure_ascii=False), user["id"], now,
                                                         now + hours * 3600, kind, current_cohort(db)))
                        break
                    except sqlite3.IntegrityError:
                        continue
            return self.json({"ok": True, "code": code, "url": f"{BASE_URL}/tiquete/{code}"}, 201)
        ticket_tag = re.fullmatch(r"/api/admin/tickets/(\d+)/tag", path)
        if ticket_tag:
            user = self.require_user()
            if not user: return
            answer_id = str(payload.get("answer_id", ""))
            tag = " ".join(str(payload.get("tag", "")).split())[:60]
            with connect() as db:
                ticket = db.execute("SELECT project_id,questions FROM exit_tickets WHERE id=?", (int(ticket_tag.group(1)),)).fetchone()
                if not ticket or ticket["project_id"] not in self.managed_projects(user): return self.json({"error": "No tienes permiso para este tiquete."}, 403)
                question = int(payload.get("question", -1))
                if not 0 <= question < len(json.loads(ticket["questions"])): return self.json({"error": "Pregunta inválida."}, 400)
                if not db.execute("SELECT 1 FROM exit_ticket_answers WHERE id=? AND ticket_id=?", (answer_id, int(ticket_tag.group(1)))).fetchone():
                    return self.json({"error": "Respuesta no encontrada."}, 404)
                if tag: db.execute("INSERT INTO exit_ticket_tags(answer_id,question,tag) VALUES(?,?,?) ON CONFLICT(answer_id,question) DO UPDATE SET tag=excluded.tag", (answer_id, question, tag))
                else: db.execute("DELETE FROM exit_ticket_tags WHERE answer_id=? AND question=?", (answer_id, question))
            return self.json({"ok": True})
        if path == "/api/admin/cohorts":
            user = self.require_user()
            if not user: return
            if user["role"] != "admin": return self.json({"error": "Solo la administración global abre cohortes."}, 403)
            name = " ".join(str(payload.get("name", "")).split())[:20]
            if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 ._-]{1,19}", name): return self.json({"error": "Usa un nombre corto, por ejemplo «2027-1»."}, 400)
            with connect() as db:
                items = cohorts(db)
                if name in [c["name"] for c in items]: return self.json({"error": "Esa cohorte ya existe."}, 409)
                items.append({"name": name, "started_at": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())})
                db.execute("UPDATE settings SET value=? WHERE key='cohorts'", (json.dumps(items),))
                # Course codes belong to the cohort that was taught with them.
                db.execute("UPDATE join_codes SET active=0 WHERE active=1")
            return self.json({"ok": True, "message": f"Cohorte {name} abierta. Lo anterior queda archivado y visible; crea los nuevos códigos del curso."}, 201)
        if path == "/api/admin/tickets/update":
            user = self.require_user()
            if not user: return
            try: ticket_id = int(payload.get("id", 0))
            except (TypeError, ValueError): return self.json({"error": "Identificador inválido."}, 400)
            feedback_url = str(payload.get("feedback_url", "")).strip()[:1000]
            if feedback_url and urllib.parse.urlparse(feedback_url).scheme != "https": return self.json({"error": "El enlace de retroalimentación debe comenzar con https://"}, 400)
            with connect() as db:
                row = db.execute("SELECT project_id FROM exit_tickets WHERE id=?", (ticket_id,)).fetchone()
                if not row or row["project_id"] not in self.managed_projects(user): return self.json({"error": "No tienes permiso para este tiquete."}, 403)
                db.execute("UPDATE exit_tickets SET feedback_url=?,active=? WHERE id=?", (feedback_url, int(bool(payload.get("active", True))), ticket_id))
            return self.json({"ok": True})
        ticket_answer = re.fullmatch(r"/api/tickets/([A-Za-z0-9-]{4,12})/answer", path)
        if ticket_answer:
            user = self.require_user()
            if not user: return
            with connect() as db:
                ticket = db.execute("SELECT * FROM exit_tickets WHERE code=?", (normalize_code(ticket_answer.group(1)),)).fetchone()
                if not ticket or not self.has_project_access(user, ticket["project_id"]): return self.json({"error": "Este tiquete no existe."}, 404)
                if not ticket["active"] or ticket["closes_at"] <= time.time(): return self.json({"error": "Este tiquete ya cerró."}, 409)
                questions = json.loads(ticket["questions"])
                raw_answers = payload.get("answers") if isinstance(payload.get("answers"), list) else []
                answers = [str(a).strip()[:1500] for a in raw_answers][:len(questions)]
                if len(answers) < len(questions) or not all(answers): return self.json({"error": "Responde las tres preguntas; basta una o dos frases."}, 400)
                try:
                    db.execute("INSERT INTO exit_ticket_respondents(ticket_id,user_id) VALUES(?,?)", (ticket["id"], user["id"]))
                except sqlite3.IntegrityError:
                    return self.json({"error": "Ya respondiste este tiquete. ¡Gracias!"}, 409)
                db.execute("INSERT INTO exit_ticket_answers(id,ticket_id,answers,answered_on) VALUES(?,?,?,date('now'))",
                           (secrets.token_hex(12), ticket["id"], json.dumps(answers, ensure_ascii=False)))
            return self.json({"ok": True, "message": "Respuesta recibida sin nombre ni correo en el contenido. ¡Gracias!"}, 201)
        quiz_answer = re.fullmatch(r"/api/quiz/(\d+)", path)
        if quiz_answer:
            user = self.require_user()
            if not user: return
            resource = self.member_resource(user, int(quiz_answer.group(1)))
            if not resource: return self.json({"error": "Recurso no disponible."}, 404)
            questions = json.loads(resource["quiz"] or "[]")
            if not questions: return self.json({"error": "Esta ficha no tiene preguntas de control."}, 404)
            answers = payload.get("answers")
            if not isinstance(answers, list) or len(answers) != len(questions) or not all(isinstance(a, int) and 0 <= a < len(q["options"]) for a, q in zip(answers, questions)):
                return self.json({"error": "Responde todas las preguntas."}, 400)
            score = sum(a == q["correct"] for a, q in zip(answers, questions))
            with connect() as db:
                # Only the first attempt counts for the course statistics; later attempts just show the feedback again.
                db.execute("INSERT OR IGNORE INTO quiz_attempts(resource_id,user_id,answers,score) VALUES(?,?,?,?)",
                           (resource["id"], user["id"], json.dumps(answers), score))
            return self.json({"ok": True, "score": score, "total": len(questions), "correct": [q["correct"] for q in questions],
                              "explanations": [q.get("explanation", "") for q in questions]})
        peer_post = re.fullmatch(r"/api/peer/(\d+)", path)
        if peer_post:
            user = self.require_user()
            if not user: return
            resource = self.member_resource(user, int(peer_post.group(1)))
            if not resource or not resource["source_submission_id"]: return self.json({"error": "Esta ficha no tiene coevaluación."}, 404)
            rubric = PEER_RUBRIC[resource["project_id"]]
            raw_scores = payload.get("scores") if isinstance(payload.get("scores"), dict) else {}
            scores = {}
            for criterion in rubric:
                try: value = int(raw_scores.get(criterion["key"], 0))
                except (TypeError, ValueError): value = 0
                if not 1 <= value <= len(PEER_LEVELS): return self.json({"error": f"Elige un nivel en «{criterion['label']}»."}, 400)
                scores[criterion["key"]] = value
            strength = str(payload.get("strength", "")).strip()[:1000]
            suggestion = str(payload.get("suggestion", "")).strip()[:1000]
            if not strength or not suggestion: return self.json({"error": "Escribe una fortaleza y una sugerencia concreta para el equipo."}, 400)
            with connect() as db:
                if is_author(resource_authors(db, resource["id"]), user): return self.json({"error": "No puedes coevaluar el trabajo de tu propio equipo."}, 403)
                db.execute("""INSERT INTO peer_reviews(resource_id,reviewer_id,scores,strength,suggestion) VALUES(?,?,?,?,?)
                  ON CONFLICT(resource_id,reviewer_id) DO UPDATE SET scores=excluded.scores,strength=excluded.strength,
                  suggestion=excluded.suggestion,updated_at=CURRENT_TIMESTAMP""", (resource["id"], user["id"], json.dumps(scores), strength, suggestion))
            return self.json({"ok": True, "message": "Coevaluación guardada. El equipo la verá sin tu nombre."})
        if path == "/api/admin/notifications":
            user = self.require_user()
            if not user: return
            if not self.managed_projects(user): return self.json({"error": "No tienes permiso para el panel docente."}, 403)
            key = f"notify_off:{user['email'].lower()}"
            with connect() as db:
                if payload.get("enabled") is False: db.execute("INSERT OR IGNORE INTO settings(key,value) VALUES(?, '1')", (key,))
                else: db.execute("DELETE FROM settings WHERE key=?", (key,))
            return self.json({"ok": True, "email_enabled": payload.get("enabled") is not False,
                              "message": "Avisos por correo activados." if payload.get("enabled") is not False else "Avisos por correo desactivados."})
        if path == "/api/admin/test-email":
            user = self.require_user()
            if not user: return
            if not self.managed_projects(user): return self.json({"error": "No tienes permiso para el panel docente."}, 403)
            if not email_ready(): return self.json({"error": "El correo saliente no está configurado (SMTP_* y una dirección https)."}, 503)
            with connect() as db:
                bucket = f"test-email:{user['id']}"
                if is_rate_limited(db, bucket, 3, 3600): return self.json({"error": "Ya enviaste 3 correos de prueba en la última hora."}, 429)
                record_rate_event(db, bucket)
                record_audit_event(db, "test_email_sent", user["email"], user["email"], ip_hash=audit_ip_hash(db, self.client_ip()))
            try:
                send_email(user["email"], "Repositorio TM: correo de prueba",
                           f"Si lees esto, los avisos del repositorio llegan a {user['email']}.\n\n{BASE_URL}/admin")
            except Exception as error:
                print(f"Correo de prueba a {user['email']} falló: {error}", file=sys.stderr, flush=True)
                return self.json({"error": "El servidor de correo rechazó el envío. Revisa SMTP_* en la configuración."}, 502)
            return self.json({"ok": True, "message": f"Correo de prueba enviado a {user['email']}. Revisa también la carpeta de spam."})
        if path == "/api/admin/staff":
            user = self.require_user()
            if not user: return
            email, project = institutional_email(payload.get("email")), str(payload.get("project_id", ""))
            if not email or project not in PROJECTS: return self.json({"error": "Indica un correo PUCV y la asignatura."}, 400)
            if project not in self.managed_projects(user): return self.json({"error": "Solo gestionas el equipo docente de tus asignaturas."}, 403)
            with connect() as db:
                if payload.get("action") == "remove":
                    teachers = PROJECT_ADMIN_EMAILS[project] | {r["email"] for r in db.execute("SELECT email FROM staff_roles WHERE project_id=?", (project,))}
                    if email == user["email"].lower() and email in teachers and not teachers - {email}:
                        return self.json({"error": "Eres la última docente de la asignatura: agrega a otra persona antes de retirarte."}, 409)
                    changed = db.execute("DELETE FROM staff_roles WHERE email=? AND project_id=?", (email, project))
                    if changed.rowcount:
                        record_audit_event(db, "staff_removed", user["email"], email, project, "staff_role",
                                           ip_hash=audit_ip_hash(db, self.client_ip()))
                    return self.json({"ok": True, "message": "Rol docente retirado."})
                changed = db.execute("INSERT OR IGNORE INTO staff_roles(email,project_id,created_by) VALUES(?,?,?)", (email, project, user["id"]))
                if changed.rowcount:
                    record_audit_event(db, "staff_added", user["email"], email, project, "staff_role",
                                       ip_hash=audit_ip_hash(db, self.client_ip()))
            return self.json({"ok": True, "message": f"{email} ahora gestiona {PROJECTS[project]['name']}. El cambio rige de inmediato."}, 201)
        if path == "/api/admin/surveys":
            user = self.require_user()
            if not user: return
            project, kind, moment = str(payload.get("project_id", "")), str(payload.get("kind", "")), str(payload.get("moment", ""))
            if project not in self.managed_projects(user): return self.json({"error": "No tienes permiso para esta asignatura."}, 403)
            if kind not in SURVEY_TEMPLATES or moment not in ("entrada", "salida", "cierre"): return self.json({"error": "Elige el tipo y el momento de la encuesta."}, 400)
            title = str(payload.get("title", "")).strip()[:120] or f"{'KPSI' if kind == 'kpsi' else 'Percepción'} · {moment}"
            items = parse_survey_items(payload.get("items") or SURVEY_TEMPLATES[kind][project])
            if not items: return self.json({"error": "Escribe al menos un enunciado."}, 400)
            try: hours = max(1, min(int(payload.get("hours") or 72), 24 * 30))
            except (TypeError, ValueError): return self.json({"error": "Revisa la duración."}, 400)
            scale = KPSI_SCALE if kind == "kpsi" else AGREEMENT_SCALE
            now = int(time.time())
            with connect() as db:
                for _ in range(5):
                    code = new_code(6)
                    try:
                        db.execute("""INSERT INTO surveys(project_id,code,kind,moment,title,items,scale,created_by,created_at,closes_at,cohort)
                          VALUES(?,?,?,?,?,?,?,?,?,?,?)""", (project, code, kind, moment, title, json.dumps(items, ensure_ascii=False),
                                                         json.dumps(scale, ensure_ascii=False), user["id"], now, now + hours * 3600, current_cohort(db)))
                        break
                    except sqlite3.IntegrityError:
                        continue
            return self.json({"ok": True, "code": code, "url": f"{BASE_URL}/encuesta/{code}"}, 201)
        if path == "/api/admin/surveys/update":
            user = self.require_user()
            if not user: return
            try: survey_id = int(payload.get("id", 0))
            except (TypeError, ValueError): return self.json({"error": "Identificador inválido."}, 400)
            with connect() as db:
                row = db.execute("SELECT project_id FROM surveys WHERE id=?", (survey_id,)).fetchone()
                if not row or row["project_id"] not in self.managed_projects(user): return self.json({"error": "No tienes permiso para esta encuesta."}, 403)
                db.execute("UPDATE surveys SET active=? WHERE id=?", (int(bool(payload.get("active"))), survey_id))
            return self.json({"ok": True})
        survey_answer = re.fullmatch(r"/api/surveys/([A-Za-z0-9-]{4,12})/answer", path)
        if survey_answer:
            user = self.require_user()
            if not user: return
            with connect() as db:
                survey = db.execute("SELECT * FROM surveys WHERE code=?", (normalize_code(survey_answer.group(1)),)).fetchone()
                if not survey or not self.has_project_access(user, survey["project_id"]): return self.json({"error": "Esta encuesta no existe."}, 404)
                if not survey["active"] or survey["closes_at"] <= time.time(): return self.json({"error": "Esta encuesta ya cerró."}, 409)
                items, scale = json.loads(survey["items"]), json.loads(survey["scale"])
                values = payload.get("values")
                if not isinstance(values, list) or len(values) != len(items) or not all(isinstance(v, int) and 1 <= v <= len(scale) for v in values):
                    return self.json({"error": "Marca una opción en cada enunciado."}, 400)
                try:
                    db.execute("INSERT INTO survey_respondents(survey_id,user_id) VALUES(?,?)", (survey["id"], user["id"]))
                except sqlite3.IntegrityError:
                    return self.json({"error": "Ya respondiste esta encuesta. ¡Gracias!"}, 409)
                db.execute("INSERT INTO survey_answers(id,survey_id,answer_values,comment,answered_on) VALUES(?,?,?,?,date('now'))",
                           (secrets.token_hex(12), survey["id"], json.dumps(values), str(payload.get("comment", "")).strip()[:1500]))
            return self.json({"ok": True, "message": "Respuesta recibida sin nombre ni correo en el contenido. ¡Gracias!"}, 201)
        if path in ("/api/admin/person/delete", "/api/admin/cohort/close"):
            user = self.require_user()
            if not user: return
            if user["role"] != "admin": return self.json({"error": "Solo la administración global puede borrar datos."}, 403)
            with connect() as db:
                if path.endswith("/delete"):
                    email = institutional_email(payload.get("email"))
                    if not email or str(payload.get("confirm", "")).strip().lower() != email:
                        return self.json({"error": "Escribe el correo dos veces para confirmar."}, 400)
                    if email == user["email"]: return self.json({"error": "No puedes borrar tu propia cuenta desde aquí."}, 400)
                    row = db.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()
                    if not row: return self.json({"error": "No hay una cuenta con ese correo."}, 404)
                    files = anonymize_user(db, row["id"])
                    record_audit_event(db, "person_anonymized", user["email"], email, entity_type="user",
                                       ip_hash=audit_ip_hash(db, self.client_ip()))
                    message = "Datos de la persona eliminados. El contenido de sus respuestas no conserva nombre o correo; los trabajos publicados del equipo quedan sin su nombre."
                else:
                    if str(payload.get("confirm", "")).strip() != "CERRAR COHORTE":
                        return self.json({"error": "Escribe CERRAR COHORTE para confirmar."}, 400)
                    # A full archive is written first so the closure can be undone from the backup if it was a mistake.
                    archive = create_full_archive(BACKUP_DIR / f"antes-del-cierre-{time.strftime('%Y%m%d-%H%M%S')}.zip")
                    count, files = close_cohort(db)
                    record_audit_event(db, "cohort_anonymized", user["email"], entity_type="cohort",
                                       ip_hash=audit_ip_hash(db, self.client_ip()))
                    message = f"Cohorte cerrada: {count} cuentas anonimizadas. Respaldo previo: {archive.name}."
            for key in files:
                if re.fullmatch(r"[a-f0-9]{40}", key or ""): (UPLOAD_DIR / key).unlink(missing_ok=True)
            return self.json({"ok": True, "message": message})
        if path == "/api/admin/review":
            user = self.require_user()
            if not user: return
            if not self.managed_projects(user): return self.json({"error": "No tienes permiso para moderar."}, 403)
            kind, decision = str(payload.get("kind", "")), str(payload.get("decision", ""))
            try:
                item_id = int(payload.get("id", 0))
            except (TypeError, ValueError):
                return self.json({"error":"Identificador inválido."},400)
            if item_id < 1: return self.json({"error":"Identificador inválido."},400)
            if kind == "access_request" and decision in ("approve", "reject"):
                status="active" if decision=="approve" else "denied"
                with connect() as db:
                    req=db.execute("SELECT project_id FROM project_memberships WHERE id=? AND status='pending'",(item_id,)).fetchone()
                    if not req or req["project_id"] not in self.managed_projects(user): return self.json({"error":"No tienes permiso para revisar esta asignatura."},403)
                    cur=db.execute("""UPDATE project_memberships SET status=?,reviewed_at=CURRENT_TIMESTAMP,reviewed_by=?
                      WHERE id=? AND status='pending'""",(status,user["id"],item_id))
                    if not cur.rowcount: return self.json({"error":"La solicitud ya fue revisada o no existe."},404)
                    if status=="active":
                        who=db.execute("SELECT u.email FROM project_memberships m JOIN users u ON u.id=m.user_id WHERE m.id=?",(item_id,)).fetchone()
                        notify_later([who["email"]],f"Ya tienes acceso a {PROJECTS[req['project_id']]['name']}",
                                     f"La docente aprobó tu acceso. Entra aquí:\n{BASE_URL}/{req['project_id']}\n")
                return self.json({"ok":True})
            if kind == "membership" and decision == "revoke":
                with connect() as db:
                    member=db.execute("""SELECT m.project_id,u.email FROM project_memberships m JOIN users u ON u.id=m.user_id
                      WHERE m.id=? AND m.status='active'""",(item_id,)).fetchone()
                    if not member or member["project_id"] not in self.managed_projects(user): return self.json({"error":"No tienes permiso para revisar esta asignatura."},403)
                    db.execute("UPDATE project_memberships SET status='denied',revoked=1,reviewed_at=CURRENT_TIMESTAMP,reviewed_by=? WHERE id=?",(user["id"],item_id))
                    # Otherwise a still-valid personal code would re-grant the course at the next sign-in.
                    db.execute("UPDATE access_codes SET revoked_at=? WHERE email=? AND project_id=? AND revoked_at IS NULL",
                               (int(time.time()),member["email"],member["project_id"]))
                    record_audit_event(db, "membership_revoked", user["email"], member["email"], member["project_id"],
                                       "membership", item_id, ip_hash=audit_ip_hash(db, self.client_ip()))
                return self.json({"ok":True})
            if kind == "comment" and decision in ("publish", "hide"):
                status = "published" if decision == "publish" else "hidden"
                with connect() as db:
                    item=db.execute("SELECT r.project_id FROM comments c JOIN resources r ON r.id=c.resource_id WHERE c.id=?",(item_id,)).fetchone()
                    if not item or item["project_id"] not in self.managed_projects(user): return self.json({"error":"No tienes permiso para revisar esta asignatura."},403)
                    cur=db.execute("UPDATE comments SET status=? WHERE id=? AND status='review'",(status,item_id))
                    if not cur.rowcount: return self.json({"error":"El comentario ya fue revisado o no existe."},404)
                    db.execute("INSERT INTO moderation_events(actor_user_id,entity_type,entity_id,action) VALUES(?,?,?,?)",
                               (user["id"],"comment",item_id,decision))
                return self.json({"ok":True})
            if kind == "submission" and decision in ("publish", "reject"):
                with connect() as db:
                    row=db.execute("SELECT * FROM submissions WHERE id=? AND status='review'",(item_id,)).fetchone()
                    if not row: return self.json({"error":"La entrega ya fue revisada o no existe."},404)
                    if row["project_id"] not in self.managed_projects(user): return self.json({"error":"No tienes permiso para revisar esta asignatura."},403)
                    if decision == "publish":
                        words=unicodedata.normalize("NFKD",row["title"].lower()).encode("ascii","ignore").decode()
                        base_slug=re.sub(r"[^a-z0-9]+","-",words).strip("-")[:90] or f"entrega-{item_id}"
                        slug=base_slug; suffix=2
                        while db.execute("SELECT 1 FROM resources WHERE project_id=? AND slug=?",(row["project_id"],slug)).fetchone():
                            slug=f"{base_slug}-{suffix}"; suffix+=1
                        fields=json.loads(row["project_fields"] or "{}")
                        # Plain-text copy keeps the record readable and searchable; the detail page shows the structured fields.
                        lines=[f"{f['label']}: {f['value']}" for f in labeled_fields(row["project_id"],fields)]
                        if row["ai_declaration"]: lines.append("Declaración de IA: "+row["ai_declaration"])
                        content="\n\n".join(lines)
                        category="Cápsula educativa" if row["project_id"]=="innova" else "Video-prototipo"
                        tag_keys=("process","technique") if row["project_id"]=="innova" else ("challenge",)
                        tags=[str(fields[k])[:50] for k in tag_keys if fields.get(k)]+([row["section"]] if row["section"] else [])
                        db.execute("""INSERT INTO resources(project_id,slug,title,category,summary,content,tags,media_url,status,source_submission_id)
                          VALUES(?,?,?,?,?,?,?,?, 'published',?)""",
                          (row["project_id"],slug,row["title"],category,row["summary"],content,json.dumps(tags,ensure_ascii=False),row["video_url"],item_id))
                        status="published"
                    else: status="rejected"
                    note=str(payload.get("note","")).strip()[:2000]
                    db.execute("UPDATE submissions SET status=?,review_note=?,reviewed_at=CURRENT_TIMESTAMP WHERE id=?",(status,note,item_id))
                    submitter=db.execute("SELECT email FROM users WHERE id=?",(row["user_id"],)).fetchone()["email"]
                    team_emails=[submitter]+json.loads(row["member_emails"] or "[]")
                    link=f"{BASE_URL}/{row['project_id']}"
                    if status=="published":
                        notify_later(team_emails,f"Su entrega «{row['title']}» fue publicada",
                                     f"La entrega del equipo {row['team_name']} ya está en el repositorio de {PROJECTS[row['project_id']]['name']}.\n\n"
                                     f"Respondan las preguntas del foro como equipo autor:\n{link}\n")
                    else:
                        notify_later(team_emails,f"Su entrega «{row['title']}» fue devuelta para corregir",
                                     f"La docente devolvió la entrega del equipo {row['team_name']}.\n\n"+(f"Comentario:\n{note}\n\n" if note else "")
                                     +f"Corrijan y vuelvan a enviarla con el mismo nombre de equipo:\n{link}\n")
                    db.execute("INSERT INTO moderation_events(actor_user_id,entity_type,entity_id,action) VALUES(?,?,?,?)",
                               (user["id"],"submission",item_id,decision))
                return self.json({"ok":True})
            return self.json({"error":"Decisión de moderación inválida."},400)
        return self.json({"error": "No encontrado."}, 404)

    def redirect(self, location, cookie=None, extra_cookies=()):
        self.send_response(302)
        self.send_header("Location", location)
        self.send_header("Cache-Control", "no-store")
        for value in ([cookie] if cookie else []) + list(extra_cookies): self.send_header("Set-Cookie", value)
        self.end_headers()

    def send_archive(self):
        target = BACKUP_DIR / f".descarga-{secrets.token_hex(8)}.zip"
        try:
            create_full_archive(target)
            self.send_response(200)
            self.send_header("Content-Type", "application/zip")
            self.send_header("Content-Length", str(target.stat().st_size))
            self.send_header("Content-Disposition", f"attachment; filename=respaldo-completo-{time.strftime('%Y%m%d-%H%M')}.zip")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            with target.open("rb") as archive:
                while chunk := archive.read(1024 * 1024):
                    self.wfile.write(chunk)
        finally:
            target.unlink(missing_ok=True)

    def google_start(self):
        if not google_ready():
            return self.redirect("/login?error=google_off")
        state, verifier, nonce = secrets.token_urlsafe(32), secrets.token_urlsafe(48), secrets.token_urlsafe(24)
        now = int(time.time())
        with connect() as db:
            db.execute("DELETE FROM oauth_states WHERE created_at<?", (now - OAUTH_STATE_SECONDS,))
            db.execute("INSERT INTO oauth_states(state_hash,code_verifier,nonce,created_at) VALUES(?,?,?,?)",
                       (token_hash(state), verifier, nonce, now))
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
        params = {"client_id": GOOGLE_CLIENT_ID, "redirect_uri": BASE_URL + "/auth/google/callback", "response_type": "code",
                  "scope": "openid email profile", "state": state, "nonce": nonce, "code_challenge": challenge,
                  "code_challenge_method": "S256", "prompt": "select_account"}
        # The hd parameter only preselects accounts; the hd claim is enforced again after the token exchange.
        if len(ALLOWED_EMAIL_DOMAINS) == 1: params["hd"] = next(iter(ALLOWED_EMAIL_DOMAINS))
        return self.redirect(GOOGLE_AUTH_URL + "?" + urllib.parse.urlencode(params),
                             self.cookie_header("pucv_oauth", state, OAUTH_STATE_SECONDS))

    def google_callback(self):
        query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        state, code = query.get("state", [""])[0], query.get("code", [""])[0]
        clear_state = self.cookie_header("pucv_oauth", "", 0)
        cookie_state = self.cookies().get("pucv_oauth")
        if not state or not code or not cookie_state or not hmac.compare_digest(cookie_state.value, state):
            return self.redirect("/login?error=auth", extra_cookies=[clear_state])
        with connect() as db:
            row = db.execute("SELECT code_verifier,nonce,created_at FROM oauth_states WHERE state_hash=?", (token_hash(state),)).fetchone()
            db.execute("DELETE FROM oauth_states WHERE state_hash=?", (token_hash(state),))
        if not row or row["created_at"] < int(time.time()) - OAUTH_STATE_SECONDS:
            return self.redirect("/login?error=auth", extra_cookies=[clear_state])
        body = urllib.parse.urlencode({"code": code, "client_id": GOOGLE_CLIENT_ID, "client_secret": GOOGLE_CLIENT_SECRET,
                                       "redirect_uri": BASE_URL + "/auth/google/callback", "grant_type": "authorization_code",
                                       "code_verifier": row["code_verifier"]}).encode()
        request = urllib.request.Request(GOOGLE_TOKEN_URL, data=body, headers={"Content-Type": "application/x-www-form-urlencoded"})
        try:
            with urllib.request.urlopen(request, timeout=10, context=ssl.create_default_context()) as response:
                claims = jwt_payload(json.loads(response.read())["id_token"])
        except Exception:
            return self.redirect("/login?error=auth", extra_cookies=[clear_state])
        # The ID token comes straight from Google's token endpoint over verified TLS, so its claims are checked
        # without a separate signature verification (OpenID Connect Core, section 3.1.3.7).
        email = institutional_email(claims.get("email"))
        valid = (claims.get("iss") in ("https://accounts.google.com", "accounts.google.com") and claims.get("aud") == GOOGLE_CLIENT_ID
                 and int(claims.get("exp", 0)) > time.time() and hmac.compare_digest(str(claims.get("nonce", "")), row["nonce"])
                 and claims.get("email_verified") in (True, "true"))
        if not valid:
            return self.redirect("/login?error=auth", extra_cookies=[clear_state])
        # hd is present only for Google Workspace accounts; it blocks personal Google accounts that merely use a PUCV address.
        if not email or str(claims.get("hd", "")).lower() not in ALLOWED_EMAIL_DOMAINS:
            return self.redirect("/login?error=domain", extra_cookies=[clear_state])
        name = str(claims.get("name") or "").strip()[:100] or name_from_email(email)
        return self.create_session(email, name, provider_subject="google:" + str(claims.get("sub", email)), extra_cookies=[clear_state])

    def login_with_access_code(self, payload):
        raw_email = str(payload.get("email") or "").strip().lower()
        email = institutional_email(raw_email) or (raw_email if SOS and raw_email == SOS["email"] else "")
        code = normalize_code(payload.get("code", ""))
        failure = {"error": "El correo o el código no coinciden, o el código venció. Pide uno nuevo a la docente."}
        now = int(time.time())
        with connect() as db:
            if SOS and email == SOS["email"] and code and not is_rate_limited(db, f"code-email:{email}", 6, 15 * 60) \
                    and hmac.compare_digest(code_digest(code, SOS["salt"]), SOS["hash"]):
                print(f"Ingreso con código SOS: {email}", file=sys.stderr, flush=True)
                sos_login = True
            else:
                sos_login = False
        if sos_login:
            response = self.create_session(email, name_from_email(email), provider_subject="sos:" + email)
            with connect() as db:
                record_audit_event(db, "sos_login", email, email, entity_type="sos",
                                   ip_hash=audit_ip_hash(db, self.client_ip()))
            return response
        with connect() as db:
            buckets = (f"code-ip:{self.client_ip()}", f"code-email:{email}")
            if is_rate_limited(db, buckets[0], 120, 15 * 60) or (email and is_rate_limited(db, buckets[1], 6, 15 * 60)):
                return self.json({"error": "Demasiados intentos. Espera 15 minutos e inténtalo de nuevo."}, 429)
            rows = db.execute("SELECT id,code_hash,salt,project_id,created_by FROM access_codes WHERE email=? AND revoked_at IS NULL AND expires_at>?",
                              (email, now)).fetchall() if email and code else []
            match = next((r for r in rows if hmac.compare_digest(code_digest(code, r["salt"]), r["code_hash"])), None)
            course = None
            if not match and email and code and not (SOS and email == SOS["email"]):
                # Course (or phase) code shared in class: the address only needs the institutional format.
                course = db.execute("SELECT * FROM join_codes WHERE code=?", (code,)).fetchone()
                if not join_code_usable(course, now): course = None
                elif course["roster"] and email not in course["roster"].split():
                    for bucket in buckets: record_rate_event(db, bucket)
                    return self.json({"error": "Tu correo no está en la lista de este curso. Revisa que esté bien escrito o pide ayuda a la docente."}, 403)
                elif is_staff_email(db, email):
                    return self.json({"error": "Las cuentas docentes no entran con el código del curso. Usa Google o tu código personal."}, 403)
                elif db.execute("""SELECT 1 FROM project_memberships m JOIN users u ON u.id=m.user_id
                                   WHERE u.email=? AND m.project_id=? AND m.revoked=1""", (email, course["project_id"])).fetchone():
                    return self.json({"error": "Tu acceso a esta asignatura fue retirado. Contacta a la docente."}, 403)
            if not match and not course:
                for bucket in buckets: record_rate_event(db, bucket)
                return self.json(failure, 400)
            if match: db.execute("UPDATE access_codes SET last_used_at=? WHERE id=?", (now, match["id"]))
        if course:
            return self.create_session(email, name_from_email(email), provider_subject="curso:" + email, join_row=course)
        return self.create_session(email, name_from_email(email), provider_subject="code:" + email,
                                   grant_project=match["project_id"], granted_by=match["created_by"])

    def email_transport_ready(self):
        return email_ready()

    def request_login_link(self, payload):
        if not self.email_transport_ready():
            return self.json({"error": "El acceso por correo necesita HTTPS y un remitente SMTP configurado."}, 503)
        email = institutional_email(payload.get("email"))
        generic = {"ok": True, "message": "Si el correo pertenece a los dominios admitidos, recibirás un enlace de acceso."}
        if not email:
            return self.json(generic, 202)
        now = int(time.time())
        raw_token = secrets.token_urlsafe(36)
        with connect() as db:
            # Per-address limits alone still let one client send links to many different inboxes.
            ip_bucket = f"link-ip:{self.client_ip()}"
            if is_rate_limited(db, ip_bucket, 10, 15 * 60):
                return self.json(generic, 202)
            record_rate_event(db, ip_bucket)
            db.execute("DELETE FROM email_login_tokens WHERE expires_at<?", (now - 24 * 60 * 60,))
            count = db.execute("SELECT COUNT(*) FROM email_login_tokens WHERE email=? AND requested_at>?",
                               (email, now - 15 * 60)).fetchone()[0]
            if count >= 3:
                return self.json(generic, 202)
            db.execute("UPDATE email_login_tokens SET used_at=? WHERE email=? AND used_at IS NULL", (now, email))
            db.execute("INSERT INTO email_login_tokens(email,token_hash,requested_at,expires_at) VALUES(?,?,?,?)",
                       (email, token_hash(raw_token), now, now + MAGIC_LINK_SECONDS))
        verify_url = BASE_URL + "/auth/verify?token=" + urllib.parse.quote(raw_token)
        try:
            send_email(email, "Tu enlace de acceso al Repositorio PUCV",
                       "Solicitaste entrar al Repositorio de proyectos de Tecnología Médica PUCV.\n\n"
                       f"Abre este enlace de un solo uso (vence en 15 minutos):\n{verify_url}\n\n"
                       "Si no solicitaste el acceso, ignora este correo.")
        except Exception:
            with connect() as db:
                db.execute("UPDATE email_login_tokens SET used_at=? WHERE token_hash=?", (int(time.time()), token_hash(raw_token)))
            return self.json({"error": "No se pudo enviar el correo. Revisa la configuración del remitente."}, 503)
        return self.json(generic, 202)

    def verify_page(self):
        query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        token = query.get("token", [""])[0]
        if not token or len(token) > 120:
            return self.redirect("/login?error=expired")
        with connect() as db:
            row = db.execute("SELECT 1 FROM email_login_tokens WHERE token_hash=? AND expires_at>? AND used_at IS NULL",
                             (token_hash(token), int(time.time()))).fetchone()
        if not row: return self.redirect("/login?error=expired")
        safe_token = html.escape(token, quote=True)
        page = f"""<!doctype html><html lang='es'><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
          <title>Confirmar acceso · Repositorio PUCV</title><link rel='stylesheet' href='/static/styles.css'>
          <body><main class='verify-page'><section class='verify-card'><div class='brand-mark'>TM</div><div class='eyebrow'>Tecnología Médica · PUCV</div>
          <h1>Confirma tu acceso</h1><p>El enlace es válido por un solo uso. Al continuar, se abrirá el repositorio privado.</p>
          <form method='post' action='/auth/verify'><input type='hidden' name='token' value='{safe_token}'><button class='button' type='submit'>Entrar al repositorio →</button></form>
          <p class='helper'>Si no solicitaste este correo, puedes cerrar esta página.</p></section></main></body></html>"""
        return self.send_bytes(page.encode())

    def create_session(self, email, name, provider_subject, extra_cookies=(), grant_project=None, granted_by=None, join_row=None):
        with connect() as db:
            is_project_admin=any(email.lower() in emails for emails in PROJECT_ADMIN_EMAILS.values())
            role="admin" if email.lower() in ADMIN_EMAILS else ("editor" if is_project_admin else "student")
            # Keep the real name obtained from Google when the same person later signs in with a code or link.
            db.execute("""INSERT INTO users(provider_subject,email,display_name,role)
              VALUES(?,?,?,?) ON CONFLICT(email) DO UPDATE SET
              display_name=CASE WHEN users.provider_subject LIKE 'google:%' AND excluded.provider_subject NOT LIKE 'google:%'
                THEN users.display_name ELSE excluded.display_name END,
              provider_subject=CASE WHEN users.provider_subject LIKE 'google:%' AND excluded.provider_subject NOT LIKE 'google:%'
                THEN users.provider_subject ELSE excluded.provider_subject END,
              role=excluded.role""",
              (provider_subject, email, name, role))
            user = db.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()
            if grant_project in PROJECTS:
                db.execute("""INSERT INTO project_memberships(user_id,project_id,status,reviewed_at,reviewed_by,cohort)
                  VALUES(?,?,'active',CURRENT_TIMESTAMP,?,?) ON CONFLICT(user_id,project_id) DO UPDATE SET
                  status='active',revoked=0,reviewed_at=CURRENT_TIMESTAMP,reviewed_by=excluded.reviewed_by,cohort=excluded.cohort""",
                  (user["id"], grant_project, granted_by, current_cohort(db)))
            if join_row: apply_join_code(db, user["id"], join_row)
            raw = secrets.token_urlsafe(36)
            db.execute("INSERT INTO sessions(token_hash,user_id,expires_at) VALUES(?,?,?)",
                       (token_hash(raw), user["id"], int(time.time()) + SESSION_SECONDS))
            db.execute("DELETE FROM sessions WHERE expires_at<=?", (int(time.time()),))
        return self.redirect("/", self.cookie_header("pucv_session", raw, SESSION_SECONDS), extra_cookies)

    def logout(self):
        c = self.cookies()
        if "pucv_session" in c:
            with connect() as db:
                db.execute("DELETE FROM sessions WHERE token_hash=?", (token_hash(c["pucv_session"].value),))
        return self.redirect("/", self.cookie_header("pucv_session", "", 0))


def cli_issue_code(args):
    """`python3 server.py codigo correo@pucv.cl [incentiva|innova] [días]`: sign-in code without email or Google."""
    email = institutional_email(args[0] if args else "")
    project = args[1] if len(args) > 1 and args[1] in PROJECTS else None
    days = int(args[2]) if len(args) > 2 and args[2].isdigit() else 30
    if not email:
        sys.exit("Uso: python3 server.py codigo correo@pucv.cl [incentiva|innova] [días]  (dominios: " + ", ".join(sorted(ALLOWED_EMAIL_DOMAINS)) + ")")
    init_db()
    with connect() as db:
        issued = issue_access_codes(db, [email], project, None, max(1, min(days, 180)))[0]
    print(f"Código de ingreso para {email}: {issued['code']} (válido {days} días{', da acceso a ' + project if project else ''}).")
    print(f"Entra en {BASE_URL}/login → «Tengo un código de ingreso».")


def cli_issue_sos(args):
    """`python3 server.py codigo-sos correo`: permanent emergency admin code, stored outside the repository."""
    email = str(args[0] if args else "").strip().lower()
    if email.count("@") != 1 or len(email) > 254:
        sys.exit("Uso: python3 server.py codigo-sos tu-correo@dominio  (cualquier dominio; ese correo queda como administración)")
    alphabet = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
    raw = "".join(secrets.choice(alphabet) for _ in range(16))
    code = "-".join(raw[i:i + 4] for i in range(0, 16, 4))
    salt = secrets.token_hex(16)
    line = f"{email}|{salt}|{code_digest(normalize_code(code), salt)}"
    SOS_FILE.parent.mkdir(parents=True, exist_ok=True)
    SOS_FILE.write_text(line + "\n"); os.chmod(SOS_FILE, 0o600)
    print(f"Código SOS para {email}: {code}")
    print("Guárdalo en tu gestor de contraseñas: no se vuelve a mostrar y no vence. Generar otro invalida este.")
    print(f"Quedó activo en {SOS_FILE} (reinicia el servidor).")
    print(f"Para Render, crea la variable secreta PUCV_SOS con este valor (es un hash, no el código):\n{line}")


def cli_backup(args):
    """`python3 server.py respaldo [archivo.zip]`: full archive (database and uploaded files) for an off-site copy."""
    init_db()
    target = Path(args[0]) if args else BACKUP_DIR / f"respaldo-completo-{time.strftime('%Y%m%d-%H%M%S')}.zip"
    print(f"Respaldo completo creado: {create_full_archive(target)}")


def cli_maintenance(args):
    """`python3 server.py mantenimiento`: hourly cron job where no background threads run (cPanel/Passenger)."""
    init_db()
    with connect() as db: purge_audit_events(db)
    print("Auditoría depurada.")
    notify_pending_digest()
    latest = max((p.stat().st_mtime for p in BACKUP_DIR.glob("respaldo-*.sqlite3")), default=0) if BACKUP_DIR.is_dir() else 0
    if BACKUP_HOURS > 0 and time.time() - latest >= BACKUP_HOURS * 3600:
        print(f"Respaldo de la base: {create_backup()}")
    else:
        print("Respaldo al día.")


def cli_verify_backup(args):
    """`python3 server.py verificar-respaldo archivo.zip|.sqlite3`: restore into a temporary copy and check it opens and is complete."""
    if not args or not Path(args[0]).is_file():
        sys.exit("Uso: python3 server.py verificar-respaldo archivo.zip|archivo.sqlite3")
    source = Path(args[0])
    with tempfile.TemporaryDirectory() as work:
        database, files = Path(work) / "repository.sqlite3", set()
        if zipfile.is_zipfile(source):
            with zipfile.ZipFile(source) as archive:
                database.write_bytes(archive.read("repository.sqlite3"))
                files = {Path(n).name for n in archive.namelist() if n.startswith("submissions_files/")}
        else:
            database.write_bytes(source.read_bytes())
        db = sqlite3.connect(database)
        integrity = db.execute("PRAGMA integrity_check").fetchone()[0]
        counts = {table: db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                  for table in ("users", "project_memberships", "resources", "submissions", "comments")}
        keys = {r[0] for r in db.execute("SELECT file_storage_key FROM resources WHERE file_storage_key<>'' UNION SELECT evidence_storage_key FROM submissions WHERE evidence_storage_key<>''")}
        db.close()
    print(f"Integridad: {integrity}")
    print("Registros: " + ", ".join(f"{k}={v}" for k, v in counts.items()))
    if zipfile.is_zipfile(source):
        missing = keys - files
        print(f"Archivos adjuntos: {len(keys) - len(missing)} de {len(keys)} incluidos" + (f"; faltan {len(missing)}" if missing else ""))
    else:
        print(f"Archivos adjuntos referenciados: {len(keys)} (este respaldo diario no los incluye; están en {UPLOAD_DIR})")
    sys.exit(0 if integrity == "ok" else 1)


def cli_update_cases(args):
    """`python3 server.py actualizar-casos [carpeta]`: refresh seeds/casos_innova.json from the course .docx cases."""
    global CASES_DIR
    if args: CASES_DIR = Path(args[0])
    cases = {slug: case_text(pattern) for _, slug, *_rest, pattern in INNOVA_CASES}
    missing = [slug for slug, text in cases.items() if not text]
    if missing: sys.exit(f"No encontré estos casos en {CASES_DIR}: {', '.join(missing)}")
    SEED_CASES.parent.mkdir(parents=True, exist_ok=True)
    SEED_CASES.write_text(json.dumps(cases, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(cases)} casos guardados en {SEED_CASES.relative_to(ROOT)}")


def cli_challenge_drafts(args):
    """`python3 server.py borradores-desafios`: load the six Incentiva challenge drafts as hidden drafts (existing ones are kept)."""
    init_db()
    drafts = json.loads((ROOT / "seeds" / "desafios_incentiva.json").read_text(encoding="utf-8"))
    added = 0
    with connect() as db:
        for d in drafts:
            cur = db.execute("""INSERT OR IGNORE INTO resources(project_id,slug,title,category,summary,content,tags,status,edited_at)
              VALUES('incentiva',?,?,?,?,?,?,'draft',CURRENT_TIMESTAMP)""",
              (d["slug"], d["title"], f"Desafío · {d['type']}", d["summary"], d["content"], json.dumps(d["tags"], ensure_ascii=False)))
            added += cur.rowcount
    print(f"{added} borradores de desafíos agregados (ocultos). Revísalos y publícalos en Panel → Materiales del repositorio.")


def cli_diagnose(args):
    """`python3 server.py diagnostico`: check the hosting configuration before opening the site to the course."""
    import shutil
    results = []
    def check(ok, label, fix="", critical=True):
        results.append((ok, critical, label, fix))
    check(sys.version_info >= (3, 10), f"Python {sys.version.split()[0]} (se necesita 3.10 o superior)", "Usar Python 3.10+.")
    check(BASE_URL.startswith("https://"), f"APP_BASE_URL = {BASE_URL}", "Definir APP_BASE_URL con la dirección https del sitio.")
    check(not DEMO_AUTH, "Acceso de demostración desactivado", "Poner APP_DEMO_AUTH=0: la demostración acepta cualquier correo sin verificarlo.")
    check(bool(ADMIN_EMAILS), f"Administración global: {', '.join(sorted(ADMIN_EMAILS)) or 'ninguna'}", "Definir PUCV_ADMIN_EMAILS.")
    check(google_ready() or email_ready(), "Al menos una vía de ingreso automática (Google o enlace por correo)",
          "Configurar GOOGLE_CLIENT_ID/SECRET (recomendado). Mientras tanto, entregar códigos personales.", critical=False)
    check(google_ready(), "Ingreso con Google configurado", "Ver README → «Activar Google en 15 minutos».", critical=False)
    check(email_ready(), "Correo saliente configurado (enlaces y avisos)", "Opcional: SMTP_HOST, SMTP_FROM y credenciales.", critical=False)
    if email_ready():
        smtp_ok, smtp_detail = smtp_check()
        check(smtp_ok, f"Conexión con el servidor de correo ({smtp_detail})", "Revisa SMTP_HOST, SMTP_PORT, SMTP_SECURITY, usuario y contraseña. Luego prueba «Enviar correo de prueba» en el panel.", critical=False)
    for label, path in (("Base de datos", DB_PATH.parent), ("Archivos subidos", UPLOAD_DIR), ("Respaldos", BACKUP_DIR)):
        try:
            path.mkdir(parents=True, exist_ok=True); probe = path / ".prueba-escritura"; probe.write_text("ok"); probe.unlink(); ok = True
        except OSError: ok = False
        check(ok, f"{label} escribible en {path}", f"Dar permisos de escritura o cambiar la ruta de {label.lower()}.")
    on_render = bool(os.environ.get("RENDER"))
    check(not on_render or str(DB_PATH).startswith("/var/data"), f"Base en disco persistente ({DB_PATH})",
          "En Render, APP_DB_PATH debe estar en /var/data o se pierde en cada despliegue.")
    free = shutil.disk_usage(DB_PATH.parent).free / 1024 ** 3
    check(free > 0.2, f"Espacio libre: {free:.1f} GB", "Ampliar el disco: quedan menos de 200 MB.", critical=False)
    check(BACKUP_HOURS > 0, f"Respaldo automático cada {BACKUP_HOURS} h", "APP_BACKUP_HOURS=24 para activarlo.", critical=False)
    check(SEED_CASES.exists(), "Casos de Innova en seeds/casos_innova.json", "Ejecutar python3 server.py actualizar-casos.")
    check(SOS is not None, "Código de emergencia (SOS) configurado",
          "python3 server.py codigo-sos tu-correo y copiar la línea que imprime a la variable PUCV_SOS.", critical=False)
    for project in PROJECTS:
        deadline = os.environ.get(f"PUCV_{project.upper()}_DEADLINE", "")
        if deadline:
            check(bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", deadline)), f"Plazo de {project}: {deadline}", "Usar el formato AAAA-MM-DD.")
    check(not TRUST_PROXY or on_render or os.environ.get("TRUST_PROXY_CONFIRMED") == "1", "TRUST_PROXY solo detrás de un proxy",
          "Sin proxy delante, TRUST_PROXY=1 permite falsificar la IP.", critical=False)
    print("Diagnóstico del repositorio\n")
    for ok, critical, label, fix in results:
        print(f"{'OK  ' if ok else ('FALTA' if critical else 'AVISO')} {label}" + ("" if ok else f"\n      → {fix}"))
    failed = [r for r in results if not r[0] and r[1]]
    print(f"\n{'Listo para publicar.' if not failed else f'{len(failed)} punto(s) crítico(s) por resolver.'}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    commands = {"diagnostico": cli_diagnose, "borradores-desafios": cli_challenge_drafts, "codigo": cli_issue_code, "codigo-sos": cli_issue_sos, "respaldo": cli_backup, "mantenimiento": cli_maintenance, "verificar-respaldo": cli_verify_backup,
                "actualizar-casos": cli_update_cases}
    if len(sys.argv) > 1 and sys.argv[1] in commands:
        commands[sys.argv[1]](sys.argv[2:])
        sys.exit(0)
    init_db()
    threading.Thread(target=audit_cleanup_loop, daemon=True).start()
    if BACKUP_HOURS > 0:
        threading.Thread(target=backup_loop, daemon=True).start()
    print(f"Repositorio PUCV listo en {BASE_URL} (demo={'sí' if DEMO_AUTH else 'no'})")
    ThreadingHTTPServer((os.environ.get("HOST", "127.0.0.1"), PORT), App).serve_forever()
