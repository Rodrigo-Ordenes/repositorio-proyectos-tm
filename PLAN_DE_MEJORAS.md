# Plan de mejoras · Repositorio Incentiva + Innova

Revisión del 30 de octubre de 2026, actualizada el 31 de octubre con las tareas P1, P2 y P3 implementadas (secciones 3.1 a 3.3). Se basa en el código (`server.py`, `static/app.js`), la documentación del repositorio y los materiales del curso: la propuesta audiovisual, los formularios de postulación, los casos clínicos 1 a 5, la guía ABP, los tiquetes de salida, el KPSI y el cruce de resultados de aprendizaje.

## 1. Resumen

- **El acceso era el bloqueo principal.** La versión anterior solo dejaba entrar mediante un enlace por correo, así que sin un remitente SMTP configurado nadie podía ingresar. **Ya están implementadas tres vías, y ninguna depende de TI PUCV:** Continuar con Google PUCV, un código personal de ingreso y el enlace por correo (este último sigue siendo opcional). A eso se suma un **código del curso** que evita aprobar a cada estudiante a mano. Todo se probó de punta a punta (sección 3).
- **El calendario está muy ajustado.** Incentiva parte el lunes 2 de noviembre. La propuesta fija el repositorio operativo para el 13 de noviembre. Innova publica cápsulas el 23 de noviembre y ambos proyectos cierran el 11 de diciembre. Por eso las tareas P0 deben quedar listas esta semana.
- Se corrigieron **5 errores** que afectaban flujos reales (sección 4).
- Las **3 brechas** detectadas entre lo que piden los proyectos y lo que hacía el sitio ya están cubiertas (secciones 3.2 y 3.3):
  1. La apertura a otros cursos y cohortes: hay una vitrina de solo lectura, que se activa cuando la docente lo decida.
  2. Los tiquetes de salida y las preguntas de control.
  3. La coevaluación entre pares.
- **Lo que no se puede hacer desde el código** y queda para el equipo:
  - desplegar y crear el cliente de Google (P0 1 a 5);
  - cargar los desafíos de Incentiva (#7);
  - validar los textos legales, la rúbrica de coevaluación y la encuesta de percepción (sección 7);
  - aplicar el protocolo de usabilidad con personas (#25).

---

## 2. Estado del arte: cómo dar acceso sin depender de terceros

### 2.1 Opciones evaluadas

| Opción | Dependencia | Verifica identidad PUCV | Costo | Puesta en marcha | Veredicto |
|---|---|---|---|---|---|
| Enlace mágico por correo (lo que existía) | Un remitente SMTP. Los correos pueden caer en spam o ser consumidos por los escáneres de enlaces del correo; la página de confirmación con POST ya mitiga esto último. | Control del buzón | Gratis con Brevo o Gmail | Requiere cuenta SMTP y validar el remitente | Útil como **opción secundaria** |
| **Sign in with Google (OIDC)** | Una cuenta Google cualquiera del equipo, para crear el cliente OAuth | **Sí**: claim `hd` = dominio Workspace y `email_verified` | Gratis | 15 min | **Principal** |
| Microsoft Entra ID | No aplica: PUCV usa Google Workspace para `@mail.pucv.cl` | — | — | — | Descartado |
| SSO institucional (SAML/CAS) | TI PUCV | Sí, y además matrícula | — | Semanas | Fuera de alcance |
| Código personal emitido por la docente | Ninguna | Solo si la docente asocia cada código a un correo de su lista | Gratis | Inmediata | **Respaldo** |
| Código de clase (patrón Google Classroom / Kahoot) | Ninguna | No: sirve para *unirse a un curso*, no para identificarse | Gratis | Inmediata | **Complemento** de Google o del código personal |
| Passkeys / WebAuthn | Ninguna | Requiere un primer registro verificado | Gratis | Implementación compleja | Futuro |
| Contraseñas propias | Ninguna | No | Gratis | Media | Descartado: resetear contraseñas vuelve a depender del correo |

**Patrón elegido:** la identidad la da *Google Workspace PUCV*, la pertenencia al curso la da un *código del curso* y el respaldo es un *código personal*. Es el mismo modelo de Google Classroom (cuenta institucional más código de clase) y no requiere integración con TI.

### 2.2 Detalles técnicos de lo implementado

- **Google:** flujo *Authorization Code* con **PKCE**, `state` atado a una cookie HttpOnly y `nonce`. El intercambio del código se hace desde el servidor contra `oauth2.googleapis.com` por TLS verificado. Según OpenID Connect Core §3.1.3.7, eso permite validar el token sin verificar la firma, así que no hace falta instalar librerías: el servidor sigue usando solo Python estándar. Se validan `iss`, `aud`, `exp`, `nonce`, `email_verified` y que **`hd` sea `mail.pucv.cl` o `pucv.cl`**. Esto rechaza cuentas Gmail y también cuentas personales de Google creadas con una dirección PUCV.
- **Riesgo conocido:** la administración Google de la PUCV podría bloquear las apps de terceros no configuradas. Lo habitual es que permitan las que solo piden datos básicos de inicio de sesión, que es este caso. Hay que probarlo con una cuenta `@mail.pucv.cl` el primer día. Si está bloqueado, se usan los códigos personales mientras se pide autorizar el ID de cliente.
- **Códigos personales:** 8 caracteres sin letras o números ambiguos (alfabeto de 31 símbolos, unos 40 bits). Se guardan con PBKDF2-SHA256 de 120 000 iteraciones y se limitan a 6 intentos fallidos por correo y 30 por IP cada 15 minutos. Se pueden reutilizar mientras estén vigentes (por defecto 30 días, máximo 180), y emitir uno nuevo anula el anterior. Si a una persona se le retira el acceso, también se anulan sus códigos de esa asignatura.
- **Código del curso:** tiene etiqueta (paralelo o sesión), vigencia, máximo de usos opcional y se puede desactivar. Admite 8 intentos fallidos por persona cada 15 minutos. No reactiva a alguien cuyo acceso fue retirado.
- **Enlace por correo:** ahora también tiene un límite por IP (10 cada 15 minutos). Antes una sola persona podía hacer llegar correos a cientos de buzones PUCV.

### 2.3 La cuenta Google del proyecto (YouTube y Drive)

La propuesta pregunta si se debe usar una cuenta o un dominio institucional para YouTube, Google y el logo. Para que ningún teléfono ni contraseña dependa de una sola persona:

1. **No compartir una contraseña.** Crear el canal de YouTube como **cuenta de marca** y agregar como **propietarias** a dos personas o más (docente y ayudante), cada una con su propia cuenta. Si alguien se va, se le quita el rol y nada se pierde.
2. Si hace falta una cuenta Gmail del proyecto (por ejemplo, dueña de la carpeta Drive o remitente SMTP):
   - activar la **verificación en 2 pasos con una app autenticadora** (TOTP) y no con SMS a un teléfono personal;
   - generar los **10 códigos de respaldo** e imprimirlos o guardarlos en el gestor de contraseñas del equipo (por ejemplo, una organización gratuita de Bitwarden) junto con la semilla TOTP;
   - registrar una **llave de acceso (passkey)** en el dispositivo de cada responsable;
   - usar como correo de recuperación el correo institucional de la docente.

   Así, cualquier responsable entra con un código y sin pedir nada a nadie.
3. **Videos:** subirlos a YouTube como **no listados** y con subtítulos. **Fichas y archivos:** una carpeta Drive del proyecto con permisos de edición para el equipo docente.

---

## 3. Qué se implementó hoy

| Área | Cambio | Archivo |
|---|---|---|
| Acceso | Botón «Continuar con Google PUCV» (aparece solo si `GOOGLE_CLIENT_ID` y `GOOGLE_CLIENT_SECRET` están configurados) | `server.py` (`google_start`, `google_callback`), `app.js` (`login`) |
| Acceso | «Tengo un código de ingreso» en el login. Si no hay Google ni SMTP, este formulario aparece abierto. | `server.py` (`login_with_access_code`) |
| Acceso | Consola: `python3 server.py codigo correo@pucv.cl innova 30` imprime un código. Sirve para que la administración entre la primera vez desde la consola de Render, sin correo. | `server.py` (`cli_issue_code`) |
| Docencia | Panel «Acceso de estudiantes»: crear y desactivar códigos del curso con su uso, y generar códigos personales pegando correos (los que no son PUCV se omiten; se descarga un CSV) | `app.js` (`accessCodesPanel`) |
| Docencia | Lista «Integrantes con acceso» con botón **Retirar acceso**. La documentación anunciaba la revocación, pero no existía. | `server.py` (`/api/admin/members`, `kind=membership`) |
| Docencia | Al devolver una entrega se puede dejar un **comentario para el equipo**. La tarjeta muestra la declaración de IA. | `server.py`, `app.js` |
| Estudiantes | En «Entregar trabajo» aparece «Tus entregas», con su estado (en revisión, publicada o devuelta) y el comentario docente | `/api/my-submissions` |
| Estudiantes | «¿Tienes el código del curso?» en la portada: acceso inmediato | `/api/join` |

**Pruebas realizadas** (base temporal, servidor real, sin datos del curso):

- código correcto en minúsculas y sin guion;
- código erróneo y bloqueo por intentos (429);
- código del curso con máximo de 1 uso;
- un estudiante no puede crear códigos;
- entrega devuelta con nota y reenvío con el mismo equipo;
- retiro de acceso que invalida el código;
- Google con un token simulado: cuenta válida, Gmail personal, cuenta sin `hd`, `nonce`, `aud` o `state` alterados y correo no verificado.

También se revisaron la pantalla de ingreso y el panel docente en el navegador.

Los archivos originales quedaron respaldados en `_respaldo_2026-10-30/`.

### 3.1 Tareas P1 implementadas (31 de octubre)

| # | Cambio | Dónde |
|---|---|---|
| 8 | **Paralelo e integrantes.** El código del curso puede registrar un paralelo (Bioanálisis u Oftalmología; la lista se cambia con `PUCV_INCENTIVA_SECTIONS` y `PUCV_INNOVA_SECTIONS`). La entrega pide paralelo (ya viene elegido si la persona entró con un código de paralelo) e integrantes, uno por línea. La lista de integrantes con acceso muestra el paralelo, el catálogo tiene un filtro por paralelo y la ficha publicada da crédito al equipo. | `server.py` (`PROJECT_SECTIONS`, `/api/join`, `/api/submissions`), `app.js` (`showDelivery`, `showResources`) |
| 9 | **Campos estructurados.** Innova sigue la cadena de la guía ABP: alteración, proceso molecular (lista), efecto en ADN/ARN/proteína, cambio celular y clínica, técnica, controles y limitaciones. Incentiva sigue el storyboard: tipo de desafío (los 6 de la propuesta), personas afectadas, indicador y limitación. El servidor valida los campos obligatorios y las opciones. La docente los ve al revisar, y al publicar se convierten en una ficha ordenada y en etiquetas que se pueden buscar (proceso, técnica, tipo de desafío, paralelo). La tarjeta muestra «IA declarada». | `PROJECT_FIELDS` en `server.py` (una sola definición, la interfaz la recibe de `/api/me`) |
| 10 | **Storyboard unificado** con los tiempos de la propuesta (0:45 · 0:40 · 0:50 · 1:30 · 0:40 · 0:35) y su versión para Innova. | `STORYBOARD` en `app.js`, `GUIA_VIDEO_PROTOTIPO.md` |
| 11 | **Respaldos.** Copia diaria automática de la base (se guardan 14) y descarga de un respaldo completo (base y archivos) desde el panel, solo para la administración global. Por consola: `python3 server.py respaldo` y `python3 server.py verificar-respaldo archivo`. Se hizo un **simulacro de restauración**: se borraron la base y los archivos, se restauraron desde el .zip descargado y el sitio volvió a servir la entrega publicada y el archivo del caso. | `create_backup`, `create_full_archive`, `cli_verify_backup` |
| 12 | **Editar y retirar materiales.** Panel «Materiales del repositorio»: corregir título, tipo, descripción y palabras clave, reemplazar el archivo, retirar del catálogo y volver a publicar (retirar no borra). Las ediciones de los casos semilla ya no se pierden al reiniciar el servidor. Cada docente solo edita su asignatura. | `/api/admin/resources`, `/api/admin/resources/update` |
| 13 | **Aviso de privacidad y autorización de imagen y voz.** `/privacidad` y `/consentimiento` se pueden abrir sin iniciar sesión y están enlazadas desde el pie, el ingreso y el formulario de entrega. La autorización se imprime o guarda como PDF, con opciones separadas: evaluación, repositorio del curso, futuras cohortes y difusión. **Ambos textos son una versión preliminar que la docente debe validar** (ver decisión 4). | `privacyPage`, `consentPage` en `app.js` |

Pendiente de P1: **#7, publicar los desafíos de Incentiva.** Es contenido de la docente; ahora se cargan desde el panel con el tipo «Desafío · …» y se corrigen después sin crear duplicados.

**Pruebas:** 40 verificaciones automáticas de estos flujos, entre ellas permisos por asignatura y rol, validación de cada campo, migración sobre una copia de la base actual y el simulacro de restauración. Además se repitieron las pruebas de acceso del día anterior, sin regresiones, y se revisaron en el navegador el catálogo, la ficha, el formulario y el panel.

### 3.2 Tareas P2 implementadas

| # | Cambio |
|---|---|
| 14 | **Video insertado en la ficha.** Enlaces de YouTube (watch, youtu.be, shorts) se reproducen con `youtube-nocookie.com` y subtítulos activados; los de Google Drive, con su vista previa. La entrega tiene la casilla «El video tiene subtítulos», y la ficha muestra el aviso correspondiente y la etiqueta «Subtitulado». |
| 15 | **Foro con pregunta guía y equipo autor destacado,** en ambas asignaturas. Cada ficha tiene su pregunta guía (editable). Hay hilos de respuestas y las respuestas del equipo autor y de la docente aparecen primero, con su insignia. Cuentan como equipo autor quien envió la entrega y las personas cuyo correo PUCV se escribió junto a su nombre en «Integrantes». Lo que escribe la docente se publica sin revisión. |
| 16 | **Preguntas de control:** hasta 3 por ficha, escritas en un formato simple (la opción correcta lleva *). Solo cuenta el primer intento. Al responder se ven las respuestas correctas y la explicación, y la docente ve el porcentaje de acierto y la distribución de opciones. |
| 17 | **Vitrina de solo lectura,** que se activa con `PUCV_OPEN_PROJECTS`. Muestra a cualquier cuenta PUCV solo los trabajos cuyo equipo marcó la autorización de vitrina; quien entra como lectora no puede comentar, responder ni descargar fichas. **Queda apagada** hasta que la docente decida (decisión 1). |
| 18 | **Tiquetes de salida** con las 3 preguntas estándar de `Tiquetes de Salida.docx`, editables. El QR se genera en el propio servidor y se probó decodificándolo con el lector de macOS. Las respuestas son **anónimas por diseño** y una por persona. El CSV sale listo para agruparlas en Excel (con protección contra fórmulas), y el enlace al audio de retroalimentación lo ven las y los estudiantes. Quien escanea el QR sin haber iniciado sesión vuelve al tiquete después de entrar. |
| 19 | **Coevaluación entre pares** con 5 criterios y 4 niveles por asignatura. No hay una rúbrica docente en los archivos, así que se armó con los criterios de la postulación de Incentiva (pertinencia territorial, fundamento, factibilidad, ética, comunicación) y los RA1–RA4 de Innova. **La docente debe revisarla** (en `PEER_RUBRIC`, `server.py`). El equipo ve promedios y comentarios sin nombres; la docente ve todo y lo descarga en CSV. Nadie puede evaluar el trabajo de su propio equipo. |

### 3.3 Tareas P3 y P0 implementadas

| # | Cambio |
|---|---|
| 6 | **Despliegue sin datos personales.** Los 5 casos simulados pasaron a `seeds/casos_innova.json` (se regeneran con `python3 server.py actualizar-casos`), y `.gitignore` excluye las carpetas del curso, las planillas, las bases y los respaldos. El sitio funciona sin la carpeta «Innova en el aula 2S 2026». |
| 20 | **Indicadores para el informe** por asignatura, en el panel y en CSV. Incluyen participación, equipos con entrega (también por paralelo y a tiempo si se configura `PUCV_*_DEADLINE`), subtítulos, declaración de IA, vitrina, actividad del foro y respuestas del equipo autor, preguntas de control, coevaluación, tiquetes y encuestas. |
| 21 | **KPSI de entrada y salida** con los 17 enunciados del KPSI de TEM 1133 y su escala 1–4. Los resultados de salida muestran, por enunciado, el promedio de entrada, el cambio y el porcentaje en los niveles altos. Son anónimos y se responden con QR. Para Incentiva no había KPSI en los archivos, así que se propone una plantilla que hay que revisar. |
| 22 | **Encuesta de percepción** (escala de acuerdo 1–5, con comentario abierto). **La plantilla es provisional:** los ítems del instrumento de Bravo Cofré et al. (2024) no están en la carpeta. Hay que reemplazarlos por los del artículo antes de aplicarla. |
| 23 | **Equipo docente desde el panel.** La administración asigna o quita docentes por asignatura y el cambio rige de inmediato, sin reiniciar. Las variables de entorno siguen funcionando. |
| 24 | **Datos personales (Ley 21.719).** Se puede descargar en JSON todo lo que hay de una persona o eliminarlo, con doble confirmación. El **cierre de cohorte** respalda, anonimiza a las y los estudiantes, borra entregas no publicadas y nombres de integrantes, y solo deja visibles los trabajos con autorización de vitrina. El aviso de privacidad ya lo describe. |
| 25 | **Protocolo de validación de usabilidad** listo para aplicar: 9 tareas de estudiantes, 5 de la docente, planilla de registro y cuestionario SUS ([PROTOCOLO_VALIDACION_USABILIDAD.md](PROTOCOLO_VALIDACION_USABILIDAD.md)). Falta aplicarlo con personas reales. |

**Pruebas P2 y P3:** 62 y 47 verificaciones automáticas, más las 40 de P1 y las de acceso, todas aprobadas:
- permisos por rol;
- anonimato de tiquetes y encuestas;
- que no se filtren las respuestas correctas;
- que nadie se autoevalúe;
- vitrina sin trabajos no autorizados;
- borrado y cierre de cohorte.

En el navegador se revisó el recorrido completo, también en el ancho de un celular. El reproductor de YouTube carga sin bloqueos de seguridad, pero el panel de prueba no muestra contenido externo, así que la reproducción **hay que confirmarla en un navegador normal** una vez desplegado.

### 3.4 Revisión de seguridad, accesibilidad y materiales para las sesiones

**Seguridad.** Una revisión independiente del código encontró 6 defectos. Todos están corregidos y tienen prueba de regresión:

1. **Escalada de privilegios:** una docente de una asignatura podía generarse un código para el correo de la administración y entrar con ese rol. Ahora no se emiten códigos para cuentas docentes ni para personas de otra asignatura.
2. **Acceso retirado:** una persona a la que se le retiró el acceso podía volver a entrar pidiendo acceso de nuevo. Ahora el retiro se recuerda; rechazar una solicitud no bloquea el código del curso.
3. **Fichas de evidencia y comentarios de trabajos retirados** se podían descargar o leer. Ahora siguen el estado del catálogo.
4. **Anonimato:** las respuestas de tiquetes y encuestas se podían cruzar con la persona por el orden interno de la base. Las tablas ahora no guardan ese orden (`WITHOUT ROWID`), las bases existentes se migran solas y lo borrado se sobrescribe en disco (`secure_delete`).
5. **Límite por IP:** se podía saltar falsificando `X-Forwarded-For`.
6. **Datos mal formados:** cortaban la conexión. Ahora responden un error claro.

Además: protección contra envíos desde otros sitios (cabecera `Origin`), límite de 20 comentarios por hora, protección del CSV contra fórmulas con tabulación, y el rol de administración se pierde de inmediato al quitarlo de la configuración.

**Paleta accesible.** La auditoría encontró 23 textos y 89 o más bordes de campos bajo el mínimo WCAG. Se rediseñó con tokens y se verificó en unas 290 combinaciones por tema: **0 fallas WCAG 2.2 AA en modo claro y oscuro**. Hay modo oscuro, soporte de alto contraste y tamaños mínimos legibles. Los estados de las entregas ya no dependen solo del color. Detalle en [PALETA_ACCESIBLE.md](PALETA_ACCESIBLE.md).

**Producto:**
- Materiales escritos sin archivo adjunto, para desafíos y casos, y borradores ocultos. Los **6 desafíos de Incentiva** están redactados como expedientes simulados: uno por tipo, pensados para Bioanálisis y Oftalmología, con personas y cifras marcadas como ficticias. Se cargan como borradores con `python3 server.py borradores-desafios`.
- **Kit de producción imprimible** en `/kit` y en PDF.
- **Plantillas Word:** Ficha de Evidencia de Incentiva y matriz diagnóstica de Innova.
- **Página de ayuda** en `/ayuda`.
- **Avisos por correo** cuando se aprueba un acceso o se revisa una entrega (si hay remitente configurado).
- **Comando `diagnostico`** para revisar la configuración del hosting, y verificación de salud en Render.

**Para las sesiones:**
- Presentación de 12 diapositivas para la sesión del 2 de noviembre (kit, storyboard, herramientas, IA, repositorio y evaluación), con notas para quien presenta.
- [GUIA_DOCENTE.md](GUIA_DOCENTE.md).
- [ANUNCIOS_AULA_VIRTUAL.md](ANUNCIOS_AULA_VIRTUAL.md).

**Verificación:**
- 210 verificaciones automáticas en 5 suites, todas aprobadas: acceso, P1, P2, P3, seguridad y páginas públicas.
- Auditoría de contraste en el navegador.
- Revisión en celular de 320 px y con teclado.
- Prueba de que un `git add` no incluye ningún archivo con datos personales.

#7 queda resuelto como borradores: falta que la docente los revise y publique.

## 4. Errores corregidos

1. **Recargar `/admin` devolvía un 404 en JSON.** El servidor no servía esa ruta.
2. **Una entrega «Devuelta» bloqueaba para siempre al equipo.** El índice único de equipo no consideraba el estado y el reenvío fallaba con «ya registró su entrega». Ahora la restricción solo aplica a entregas no rechazadas, y la migración es automática.
3. **Después de enviar con éxito una entrega o un comentario aparecía un error en pantalla.** `event.currentTarget` es `null` después de un `await`.
4. En las fichas de Incentiva, la sección «Preguntas y comentarios» quedaba en «Cargando…» para siempre. Ahora solo aparece en Innova.
5. El enlace por correo no tenía límite por IP. Ahora lo tiene.

---

## 5. Análisis por áreas

### Pedagogía · Innova (TEM 1133)
- Los RA1 a RA4 y la guía ABP definen una cadena explícita: **alteración, proceso molecular, efecto en ADN, ARN o proteína, cambio celular, patología, técnica y controles**. Hoy el formulario de entrega la reduce a un solo campo libre. **Mejora:** campos estructurados para cada eslabón, que además alimentan filtros por gen, tipo de alteración y técnica.
- El KPSI y su cruce muestran que el curso entiende la teoría pero no logra «imaginar» los procesos, y que tiene dudas sobre los tipos de PCR, la extracción y los controles. **Mejora:** 2 o 3 preguntas de control por cápsula (aula invertida con quiz previo: DME 0,56 frente a 0,26 sin quiz, Hew y Lo 2018), enfocadas en esas dudas.
- **Tiquetes de salida:** el documento ya define 3 preguntas estándar, su aplicación por QR, la agrupación de respuestas y la retroalimentación por audio. El repositorio puede alojarlos:
  - un formulario por sesión con QR;
  - un CSV para agruparlas;
  - un enlace al audio de retroalimentación.

  Así ningún dato pasa por Google Forms.
- **Foro:** la propuesta pide una pregunta guía por cápsula y que el equipo autor responda de forma destacada. Hoy el foro es plano y sin respuestas.

### Pedagogía · Incentiva (Metodología de la Investigación)
- Son 80 estudiantes en **2 paralelos** (Bioanálisis y Oftalmología) y unos 16 equipos. El sitio no registra paralelo ni integrantes. **Mejora:** agregar paralelo e integrantes a la entrega y usar un código del curso por paralelo, que ya es posible con la etiqueta.
- **Storyboard de 6 bloques:** la propuesta lo usa con tiempos de 0:45, 0:40, 0:50, 1:30, 0:40 y 0:35, mientras la app y la guía usan 6 bloques con otros tiempos. Conviene **unificar** la guía impresa, la app y `GUIA_VIDEO_PROTOTIPO.md` con una sola fuente.
- **Caja sorpresa:** no tiene desafíos cargados porque la semilla de Incentiva se borró. La docente debe publicarlos desde el panel con el tipo «Desafío …». Los tipos de desafío de la propuesta son acceso rural, personas mayores, comunidad escolar, discapacidad, seguimiento y detección temprana.
- **Coevaluación entre pares** con la misma rúbrica docente (Pereira Varela et al., 2014): está en la propuesta y no está en el sitio.

### Producto y UX
- Hoy la docente debe aprobar a cada estudiante uno por uno. El código del curso elimina ese cuello de botella.
- Faltan la edición y el retiro de materiales publicados: un error de tipeo obliga a crear otro material.
- Los videos se abren solo como enlace externo. **Mejora:** insertar YouTube *no listado* (`youtube-nocookie.com`) agregando `frame-src` a la CSP.
- Falta un indicador de «IA declarada» y de «foro abierto» en las tarjetas, como muestran los mockups de la propuesta.

### Técnica y seguridad
- La arquitectura (Python sin dependencias, SQLite en modo WAL, un servidor) es adecuada para unas 120 personas.
- Los roles docentes se configuran por variables de entorno, así que cambiar a una docente obliga a reiniciar. **Mejora:** gestionar los roles desde el panel de administración.
- **Respaldos:** no existe un mecanismo. **Mejora:** usar `sqlite3 .backup` diario y una descarga desde el panel solo para administración.
- Los archivos se envían en base64 dentro de JSON (unos 11 MB en memoria por archivo de 8 MB). Es aceptable para esta escala.
- Defensa adicional contra CSRF: verificar el encabezado `Origin` en los POST. Hoy depende solo de `SameSite=Lax`, que es correcto, pero conviene sumar una segunda capa.

### Datos y privacidad
- La **Ley 21.719 entra en vigencia alrededor de diciembre de 2026**, justo al cierre de los proyectos. Hace falta definir:
  - plazos de conservación de entregas y cuentas;
  - un aviso de privacidad;
  - la forma de pedir que se borren los datos.
- **Esta carpeta mezcla el código con datos personales.** Contiene las respuestas KPSI con nombres y correos de estudiantes, y el formulario de postulación con el RUT y el teléfono de la docente. Si se sube tal cual a GitHub o Render, esos datos viajan a terceros. **Mejora:** separar la aplicación en su propia carpeta o repositorio y que el servidor lea los casos desde una ruta configurable.
- Consentimiento de imagen y voz: hoy es solo una casilla. La propuesta pide además un formulario descargable.

### Evaluación del proyecto (informes)
La propuesta lista indicadores que «la plataforma entrega sin esfuerzo»: entregas a tiempo, subtítulos y declaración de IA, actividad del foro y resultados de las preguntas de control. **Mejora:** un botón «Exportar indicadores (CSV)» por asignatura para los informes Incentiva e Innova.

---

## 6. Tareas priorizadas

**P0: esta semana, antes del 2 de noviembre (acceso funcionando)**

| # | Tarea | Responsable | Tiempo |
|---|---|---|---|
| 1 | Desplegar en Render (Starter + disco). Se puede usar la URL `*.onrender.com` con HTTPS gratis; **no hace falta comprar un dominio** para partir. | Ayudante | 1 h |
| 2 | Crear el cliente OAuth en Google Cloud (pasos en `README.md`), cargar las variables y publicar la app | Ayudante | 15 min |
| 3 | Probar el ingreso con 2 cuentas `@mail.pucv.cl` reales. Si la PUCV lo bloquea, activar el plan B: códigos personales desde la lista del curso. | Ayudante y docente | 15 min |
| 4 | Generar un código del curso por paralelo de Incentiva y proyectarlo en la sesión del 2 de noviembre | Docente | 5 min |
| 5 | Primer acceso de la administración con `python3 server.py codigo correo@pucv.cl` desde la consola de Render | Ayudante | 5 min |
| 6 | ✅ Sacar de la carpeta de despliegue los archivos con datos personales (KPSI, formularios): resuelto con `seeds/` y `.gitignore`; solo falta revisar `git status` al subir | Ayudante | 5 min |

**P1: antes del 13 de noviembre (repositorio operativo)**

| # | Tarea | Área |
|---|---|---|
| 7 | ◐ Publicar los desafíos de Incentiva (6 tipos) para la caja sorpresa: los 6 borradores están listos; falta que la docente los revise y publique | Contenido |
| 8 | ✅ Agregar paralelo e integrantes a la entrega, y filtro por paralelo | Producto |
| 9 | ✅ Campos estructurados de Innova: alteración, proceso, efecto, técnica, controles y limitaciones | Pedagogía |
| 10 | ✅ Unificar el storyboard de 6 bloques (app, guía y kit impreso) | Contenido |
| 11 | ✅ Respaldo diario de SQLite y prueba de restauración | Operación |
| 12 | ✅ Editar y retirar materiales publicados | Producto |
| 13 | ✅ Aviso de privacidad y formulario de consentimiento descargable | Datos |

**P2: antes del 23 de noviembre (publicación Innova)**

| # | Tarea | Área |
|---|---|---|
| 14 | ✅ Video de YouTube insertado en la ficha, con aviso de subtítulos | Producto |
| 15 | ✅ Foro con pregunta guía por cápsula y **respuesta del equipo autor destacada** | Pedagogía |
| 16 | ✅ 2 o 3 preguntas de control por cápsula, con resultados agregados para la docente | Pedagogía |
| 17 | ✅ **Vitrina pública o «modo lector»**: las cápsulas publicadas y con consentimiento se pueden ver con cualquier cuenta PUCV (u otra configurable), sin poder entregar | Producto |
| 18 | ✅ Tiquetes de salida por sesión (QR, 3 preguntas estándar, CSV para agrupar respuestas) | Pedagogía |
| 19 | ✅ Pauta de coevaluación entre pares con la rúbrica docente | Pedagogía |

**P3: cierre e informes (hasta el 11 de diciembre) y siguiente cohorte**

| # | Tarea | Área |
|---|---|---|
| 20 | ✅ Exportar indicadores por asignatura (CSV) para los informes | Evaluación |
| 21 | ✅ KPSI de entrada y salida dentro del repositorio, con comparación agregada y anónima | Evaluación |
| 22 | ✅ Encuesta de percepción basada en Bravo Cofré et al. (2024) | Evaluación |
| 23 | ✅ Roles docentes gestionados desde el panel, sin variables de entorno | Técnica |
| 24 | ✅ Política de conservación y borrado (Ley 21.719); archivar la cohorte 2026 | Datos |
| 25 | ◐ Validación de usabilidad con 5 estudiantes por proyecto (tareas a–e de `ESTUDIO_DE_USABILIDAD.md`) | UX |

## 7. Decisiones pendientes para la docente

1. ¿El repositorio de Innova queda visible para **toda la comunidad PUCV** o solo para cursos invitados? Esto define la tarea 17.
2. ¿Los códigos personales se entregan en clase (papel) o por mensaje del Aula Virtual?
3. ¿Quién es la segunda propietaria del canal de YouTube y de la carpeta Drive?
4. ¿Hasta cuándo se conservan las entregas y las cuentas después del 11 de diciembre? El aviso de privacidad propone «el semestre siguiente, luego eliminar o anonimizar, salvo lo que el equipo autor autorice». Hay que confirmarlo o cambiarlo en `privacyPage` (`static/app.js`).
5. ¿Los paralelos de Innova se separan? Hoy solo Incentiva tiene paralelos (`PUCV_INNOVA_SECTIONS` vacío).
6. ¿El kit impreso ya usa los tiempos de la propuesta? La app y la guía quedaron con 0:45 · 0:40 · 0:50 · 1:30 · 0:40 · 0:35.
7. **Rúbrica de coevaluación:** ¿sirven los 5 criterios propuestos o se reemplazan por la rúbrica docente oficial? (`PEER_RUBRIC` en `server.py`).
8. **Encuesta de percepción:** conseguir los ítems del instrumento de Bravo Cofré et al. (2024) para reemplazar la plantilla provisional.
9. **KPSI de Incentiva:** ¿se usa la plantilla propuesta o la docente tiene uno propio?
10. Fechas límite de entrega para el indicador «a tiempo» (`PUCV_INCENTIVA_DEADLINE`, `PUCV_INNOVA_DEADLINE`).
