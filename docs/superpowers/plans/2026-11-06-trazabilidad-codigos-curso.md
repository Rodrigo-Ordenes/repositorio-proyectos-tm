# Trazabilidad de códigos del curso — Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implementar este plan tarea por tarea. Cada paso usa casillas de verificación.

**Goal:** Mostrar a docentes qué correos ingresaron con cada código del curso y cuándo, conservando el rastro durante 180 días.

**Architecture:** Una tabla aditiva `audit_events` registra eventos de ingreso con código, sin clave foránea a la cuenta. La API existente de códigos incluye ingresos de los últimos 180 días solo para asignaturas gestionadas por la sesión; la interfaz muestra cada lista dentro de un `<details>` nativo.

**Tech Stack:** Python 3.12 estándar, SQLite WAL, `ThreadingHTTPServer`, JavaScript sin framework, Bash/curl/sqlite3.

**Spec:** `docs/superpowers/specs/2026-11-06-trazabilidad-codigos-curso-design.md`

## Global Constraints

- No agregar dependencias ni cambiar el stack.
- Mantener migraciones aditivas con `add_missing_columns` cuando correspondan.
- Mantener verificación de origen, CSP y cookies seguras.
- Las tablas de tiquetes y encuestas siguen `WITHOUT ROWID` y sin `user_id`.
- No registrar IP en claro ni guardar datos personales del curso en git.
- Usar nombres, mensajes y etiquetas en español de Chile.
- Una rama y un PR por tarea; no hacer push directo a `main`.

## Review Focus

- Una cuenta sin gestión de la asignatura no puede leer los ingresos por código.
- Una persona docente de otra asignatura no puede leer los ingresos de este código.
- Un correo fuera de la lista permitida y un código inválido no generan un ingreso exitoso.
- Usar un código cuando la cuenta ya tiene acceso conserva la fecha del nuevo uso exitoso.
- Los registros con más de 180 días no aparecen ni permanecen después de la siguiente escritura de auditoría.

---

### Task 1: Registrar ingresos exitosos y mostrarlos por código

**Files:**
- Modify: `server.py` — esquema, limpieza, registro de ingreso y respuesta de `/api/admin/join-codes`.
- Modify: `static/app.js` — sección expandible con correo y fecha/hora.
- Modify: `static/styles.css` — solo si la presentación requiere estilos responsivos nuevos.
- Create: `pruebas/trazabilidad_ingresos.sh` — prueba de ingreso, consulta, controles de acceso y retención.
- Modify: `pruebas/ejecutar.sh` — sumar la suite nueva al recorrido completo.
- Modify: `GUIA_DOCENTE.md` — explicar dónde se consultan los ingresos.
- Modify: `README.md` — evitar un total fijo y desactualizable de verificaciones.
- Modify: `.gitignore` — proteger los nombres de archivo del código SOS indicado en el encargo.

**Interfaces:**
- Produce `audit_events(event_type, actor_email, subject_email, project_id, entity_type, entity_id, created_at)` y registra `course_code_login` para `entity_type='join_code'`, `entity_id=<join_codes.id>`.
- `/api/admin/join-codes` incluye `entries`, arreglo de `{email, created_at}` dentro de cada código.

- [x] **Step 1: Write failing HTTP checks**

En `pruebas/trazabilidad_ingresos.sh`, crear una docente y estudiantes, crear códigos por asignatura, ingresar a uno con una cuenta permitida y verificar: su correo y fecha aparecen dentro de ese código; el correo de la persona no aparece en otro código; acceso sin rol de gestión se rechaza; una cuenta fuera de lista no se registra. Añadir una entrada artificial vencida y comprobar que la siguiente escritura de auditoría la elimina.

- [x] **Step 2: Run the focused suite and verify the expected failure**

Run: `bash pruebas/ejecutar.sh trazabilidad_ingresos`
Expected: falla la comprobación de correo/fecha porque la respuesta actual no contiene ingresos y falla la comprobación de tabla porque `audit_events` aún no existe. Evidencia inicial: 5 correctas, 3 fallidas.

- [x] **Step 3: Add the additive audit schema and retention**

Crear `audit_events` en `init_db()` con `event_type`, `actor_email`, `subject_email`, `project_id`, `entity_type`, `entity_id` y `created_at`; indexar `(entity_type, entity_id, created_at)`. No crear FK a `users`. Definir `AUDIT_RETENTION_DAYS = 180` y una función que elimina filas anteriores al plazo dentro de la misma transacción que registra un evento.

- [x] **Step 4: Record successful course-code use and return scoped entries**

Registrar solo tras validar código, lista, estado de membresía y aplicar/confirmar el acceso; guardar el correo autenticado y `int(time.time())`. Incluir `entries` de ese código en `/api/admin/join-codes` con SQL limitado por los proyectos que ya puede gestionar el usuario.

- [x] **Step 5: Render the per-code activity accessibly**

En `static/app.js`, mostrar «Ver ingresos (N)» con `<details>/<summary>` y una tabla de correo y fecha/hora formateada con `es-CL`. Estado vacío explícito. Añadir solo CSS necesario para que la tabla se adapte a móvil y mantenga foco visible.

- [x] **Step 6: Document the teacher workflow**

Actualizar `GUIA_DOCENTE.md` indicando que el panel muestra los ingresos por código de los últimos 180 días y que no muestra la lista del curso completa.

- [x] **Step 7: Run focused and full suites**

Run: `bash pruebas/ejecutar.sh mejoras`
Expected: todas las verificaciones de `mejoras` pasan.

Run: `bash pruebas/ejecutar.sh`
Expected: `0 con fallas`; total mayor que 293.

- [x] **Step 8: Review repository safety**

Run: `git diff --check`, `git status --short`, `git diff --stat`.
Expected: solo cambios de código, prueba, guía y este plan/diseño; sin datos personales, bases, respaldos ni secretos.
