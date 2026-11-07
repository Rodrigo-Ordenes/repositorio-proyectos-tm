# Auditoría global — Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` para implementar este plan tarea por tarea. Cada paso usa casillas de verificación.

**Goal:** Registrar acciones sensibles y permitir que solo administración global las consulte, conservando eventos por 180 días y sin IP en claro.

**Architecture:** Reutilizar `audit_events`, `record_audit_event` y la purga de 180 días. Calcular HMAC-SHA-256 de la IP con una sal aleatoria por instalación persistida en `settings`; exponer una API y una tabla de auditoría exclusivas para admin.

**Tech Stack:** Python 3.12 estándar, SQLite WAL, `ThreadingHTTPServer`, JavaScript sin framework, Bash/curl/sqlite3.

**Spec:** `docs/superpowers/specs/2026-11-06-auditoria-global-design.md`

## Global Constraints

- No agregar dependencias ni cambiar el stack.
- Migraciones aditivas; conservar retención de 180 días.
- No registrar IP en claro ni exponerla por consola.
- Mantener CSP, cookies, verificación de origen y anonimato de tiquetes/encuestas.
- Solo administración global consulta el registro consolidado.
- No subir datos, archivos SOS ni secretos; no hacer push a `main`.

## Review Focus

- El ingreso SOS válido se registra, el inválido no.
- El acceso al registro consolidado falla para estudiantes y docentes de asignatura.
- Las altas/bajas repetidas que no cambian estado no producen cambios engañosos en la auditoría.
- El hash usa la IP observada y una sal persistente, y no guarda la IP original.
- El borrado de cuenta no borra su evento de anonimización antes de los 180 días.

---

### Task 1: Registrar acciones sensibles y mostrar auditoría global

**Files:**
- Modify: `server.py` — sal de instalación, huella IP, eventos en rutas autorizadas, consulta admin y ocultar IP en consola SOS.
- Modify: `static/app.js` — panel, carga y etiquetas de eventos.
- Modify: `static/styles.css` — tabla de auditoría adaptable y con foco visible.
- Create: `pruebas/auditoria_global.sh` — cobertura de eventos, permisos, retención y hash salado.
- Modify: `pruebas/ejecutar.sh` — sumar la suite nueva.
- Modify: `GUIA_DOCENTE.md` — acceso y conservación del registro global.

**Interfaces:**
- Extender `record_audit_event(..., ip_hash='')` para persistir una huella de 64 caracteres hexadecimales.
- `audit_ip_hash(db, address) -> str` carga/crea `settings.audit_ip_salt` y calcula HMAC-SHA-256.
- `GET /api/admin/audit` devuelve eventos de los últimos 180 días solo a `role='admin'`.

- [x] **Step 1: Write failing HTTP checks**

En `pruebas/auditoria_global.sh`, generar SOS solo en la base temporal; probar SOS, ingreso por código, alta/baja de código, alta/baja docente, retiro de acceso, borrado de cuenta y cierre de cohorte. Comprobar actor/cuenta/asignatura, acceso denegado a editor, HMAC calculado con la sal de SQLite, IP original ausente y retención vigente.

- [x] **Step 2: Run the focused suite and verify expected failures**

Run: `bash pruebas/ejecutar.sh auditoria_global`
Expected: falla el endpoint protegido (404), faltan los eventos administrativos y las entradas heredadas tienen IP sin huella. Evidencia inicial: 3 correctas, 14 fallidas.

- [x] **Step 3: Persist the installation salt and hashed IP**

Crear `audit_ip_hash(db, address)` con sal aleatoria de 32 bytes en `settings` y HMAC-SHA-256. Extender `record_audit_event` con `ip_hash` y pasar una huella al registro de ingresos por código. Quitar IP remota en claro de todos los mensajes HTTP de consola.

- [x] **Step 4: Record each successful administrative change**

Registrar SOS válido, creación/desactivación efectiva de código, alta/retiro efectivo de docente, retiro de acceso, borrado de persona y cierre de cohorte. Guardar actor, cuenta afectada, asignatura y entidad disponibles; obtener todas las IP desde `self.client_ip()` y transformarlas antes de escribir.

- [x] **Step 5: Add the admin-only endpoint and panel**

Implementar `GET /api/admin/audit` con verificación explícita de rol global y eventos no vencidos ordenados por fecha descendente. Mostrar acción, fecha/hora, actor, cuenta afectada y asignatura en una tabla, sin IP original.

- [x] **Step 6: Document the global admin workflow**

Actualizar `GUIA_DOCENTE.md` para indicar que el registro consolidado vive en administración global y se conserva por 180 días.

- [x] **Step 7: Verify focused and full suites**

Run: `bash pruebas/ejecutar.sh auditoria_global`
Expected: todas las verificaciones focalizadas pasan.

Run: `bash pruebas/ejecutar.sh`
Expected: `0 con fallas`; total mayor que 304.

- [x] **Step 8: Check repository safety and commit**

Run: `git diff --check`, `git check-ignore -v data/repository.sqlite3 sos.txt MI_CODIGO_SOS.txt`, `git status --short`, `git diff --stat`.
Expected: solo archivos de código, pruebas, guía y plan/diseño; sin datos personales ni secretos.
