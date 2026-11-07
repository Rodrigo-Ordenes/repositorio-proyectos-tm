# Diseño: trazabilidad de códigos del curso

## Intención

Permitir que cada docente revise qué correos ingresaron con cada código del curso y en qué momento, para detectar el uso del correo de otra persona. La lista mostrará solo ingresos asociados al código seleccionado; no expondrá la lista completa del curso.

## Enfoque

Agregar un registro aditivo de eventos de auditoría y guardar cada ingreso exitoso con código del curso usando el mismo dato de correo de la cuenta autenticada. La consulta del panel docente se limita en servidor a los proyectos que puede gestionar y devuelve las entradas agrupadas por código. La interfaz las presenta en una sección desplegable por código, con correo y fecha/hora local.

Este registro comienza con los ingresos por código y se ampliará en una tarea posterior para los demás eventos administrativos. Se conservará por 180 días, con purga al iniciar el servidor, cada hora y al escribir eventos. El esquema no referencia `users` con clave foránea para que la eliminación o anonimización de la cuenta no borre el rastro antes del plazo.

## Alternativas consideradas

- Guardar el ingreso dentro de `join_codes`: descartado porque un contador no puede representar distintos correos ni fechas.
- Consultar `project_memberships`: descartado porque no identifica qué código se usó y puede contener ingresos por otros medios.
- Crear un registro de eventos aditivo compartido: elegido porque permite la vista por código ahora y la auditoría administrativa en la siguiente tarea sin migrar ni duplicar los ingresos.

## Límites y restricciones

- Mantener Python estándar, SQLite, la SPA actual y la CSP existente.
- Solo una persona autenticada con acceso de gestión a la asignatura ve los ingresos de sus códigos.
- No exponer la lista del curso ni permitir que otra asignatura consulte esos datos.
- No almacenar IP en claro; esta tarea no necesita registrar IP.
- Respetar los códigos docentes, cuentas SOS, anonimato de tiquetes/encuestas y límite por IP establecidos en el encargo.
- Interfaz en español de Chile, operable con teclado y utilizable en 375 px.

## Fuera de alcance

El panel global de auditoría y el registro de eventos SOS, administración de códigos, equipo docente, retiro de acceso y anonimización pertenecen a la tarea P0 siguiente. El ensayo de usabilidad con participantes reales se informará por separado.

## Validación

Agregar primero una prueba HTTP en `pruebas/` que demuestre la falta de trazabilidad y falle antes del cambio. Después comprobar ingreso exitoso, hora asociada, restricción por asignatura/rol, ausencia de lista completa y retención de 180 días. Correr la suite completa y comprobar que `.gitignore` mantiene fuera datos locales.
