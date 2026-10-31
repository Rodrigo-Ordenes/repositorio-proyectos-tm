# Plan de mejoras · Repositorio Incentiva + Innova

Revisión del 30 de octubre de 2026, actualizada el 31 de octubre. Este documento conserva hallazgos y decisiones de iteraciones previas; cuando una descripción histórica contradiga el estado actual, prevalecen la sección 3.4 y [REVISION_CRUZADA.md](REVISION_CRUZADA.md). Se basa en el código (`server.py`, `static/app.js`), la documentación del repositorio y los materiales del curso: la propuesta audiovisual, los formularios de postulación, los casos clínicos 1 a 5, la guía ABP, los tiquetes de salida, el KPSI y el cruce de resultados de aprendizaje.

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
3. **Videos:** compartirlos desde Drive con acceso limitado a cuentas PUCV. Un enlace de YouTube «no listado» lo puede ver cualquiera que lo reciba; solo usarlo si la docente aprueba ese nivel de exposición y el material no contiene información sensible. **Fichas y archivos:** una carpeta Drive del proyecto con permisos de edición para el equipo docente.

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
| 13 | **Aviso de privacidad y autorización de imagen y voz.** `/privacidad` y `/consentimiento` se pueden abrir sin iniciar sesión y están enlazadas desde el pie, el ingreso y el formulario de entrega. La autorización opcional de imagen/voz se imprime como PDF y separa repositorio, futuras cohortes y difusión. La entrega y evaluación no dependen de mostrar rostros o voces identificables. El aviso de privacidad y el formulario son borradores para validación docente. | `privacyPage`, `consentPage` en `app.js` |

Pendiente de P1: **#7, publicar los desafíos de Incentiva.** Es contenido de la docente; ahora se cargan desde el panel con el tipo «Desafío · …» y se corrigen después sin crear duplicados.

**Pruebas:** 40 verificaciones automáticas de estos flujos, entre ellas permisos por asignatura y rol, validación de cada campo, migración sobre una copia de la base actual y el simulacro de restauración. Además se repitieron las pruebas de acceso del día anterior, sin regresiones, y se revisaron en el navegador el catálogo, la ficha, el formulario y el panel.

### 3.2 Tareas P2 implementadas

| # | Cambio |
|---|---|
| 14 | **Video insertado en la ficha.** Enlaces de YouTube (watch, youtu.be, shorts) se reproducen con `youtube-nocookie.com` y subtítulos activados; los de Google Drive, con su vista previa. La entrega tiene la casilla «El video tiene subtítulos», y la ficha muestra el aviso correspondiente y la etiqueta «Subtitulado». |
| 15 | **Foro con pregunta guía y equipo autor destacado,** en ambas asignaturas. Cada ficha tiene su pregunta guía (editable). Hay hilos de respuestas y las respuestas del equipo autor y de la docente aparecen primero, con su insignia. Cuentan como equipo autor quien envió la entrega y las personas cuyo correo PUCV se escribió junto a su nombre en «Integrantes». Lo que escribe la docente se publica sin revisión. |
| 16 | **Preguntas de control:** hasta 3 por ficha, escritas en un formato simple (la opción correcta lleva *). Solo cuenta el primer intento. Al responder se ven las respuestas correctas y la explicación, y la docente ve el porcentaje de acierto y la distribución de opciones. |
| 17 | **Vitrina de solo lectura,** que se activa con `PUCV_OPEN_PROJECTS`. Muestra a cualquier cuenta PUCV solo los trabajos cuyo equipo marcó la autorización de vitrina; quien entra como lectora no puede comentar, responder ni descargar fichas. **Queda apagada** hasta que la docente decida (decisión 1). |
| 18 | **Tiquetes de salida** con las 3 preguntas estándar de `Tiquetes de Salida.docx`, editables. El QR se genera en el propio servidor y se probó decodificándolo con el lector de macOS. El contenido de respuestas no incluye nombre o correo; el sistema conserva por separado quién ya respondió para limitar duplicados. No describir como anonimato certificado para investigación. El CSV sale listo para agruparlas en Excel (con protección contra fórmulas), y el enlace al audio de retroalimentación lo ven las y los estudiantes. Quien escanea el QR sin haber iniciado sesión vuelve al tiquete después de entrar. |
| 19 | **Coevaluación entre pares** con 5 criterios y 4 niveles por asignatura. No hay una rúbrica docente en los archivos, así que se armó con los criterios de la postulación de Incentiva (pertinencia territorial, fundamento, factibilidad, ética, comunicación) y los RA1–RA4 de Innova. **La docente debe revisarla** (en `PEER_RUBRIC`, `server.py`). El equipo ve promedios y comentarios sin nombres; la docente ve todo y lo descarga en CSV. Nadie puede evaluar el trabajo de su propio equipo. |

### 3.3 Tareas P3 y P0 implementadas

| # | Cambio |
|---|---|
| 6 | **Despliegue sin datos personales.** Los 5 casos simulados pasaron a `seeds/casos_innova.json` (se regeneran con `python3 server.py actualizar-casos`), y `.gitignore` excluye las carpetas del curso, las planillas, las bases y los respaldos. El sitio funciona sin la carpeta «Innova en el aula 2S 2026». |
| 20 | **Indicadores para el informe** por asignatura, en el panel y en CSV. Incluyen participación, equipos con entrega (también por paralelo y a tiempo si se configura `PUCV_*_DEADLINE`), subtítulos, declaración de IA, vitrina, actividad del foro y respuestas del equipo autor, preguntas de control, coevaluación, tiquetes y encuestas. |
| 21 | **KPSI de entrada y salida** con los 17 enunciados del KPSI de TEM 1133 y su escala 1–4. Los resultados de salida muestran, por enunciado, el promedio de entrada, el cambio y el porcentaje en los niveles altos. El contenido no lleva nombre o correo, pero la participación queda en un registro aparte para evitar duplicados. Para Incentiva no había KPSI en los archivos, así que se propone una plantilla que hay que revisar. |
| 22 | **Encuesta de percepción** (escala de acuerdo 1–5, con comentario abierto). **La plantilla es provisional:** los ítems del instrumento de Bravo Cofré et al. (2024) no están en la carpeta. Hay que reemplazarlos por los del artículo antes de aplicarla. |
| 23 | **Equipo docente desde el panel.** La administración asigna o quita docentes por asignatura y el cambio rige de inmediato, sin reiniciar. Las variables de entorno siguen funcionando. |
| 24 | **Gestión de datos.** Hay exportación y eliminación individual y cierre de cohorte. La Ley 21.719 entra en vigencia el 1 de diciembre de 2026; el aviso actual es un borrador operativo, no una validación jurídica. El cierre respalda datos antes de anonimizar la base activa; las copias previas deben gestionarse aparte. |
| 25 | **Protocolo de validación de usabilidad** listo para aplicar: 9 tareas de estudiantes, 5 de la docente, planilla de registro y cuestionario SUS ([PROTOCOLO_VALIDACION_USABILIDAD.md](PROTOCOLO_VALIDACION_USABILIDAD.md)). Falta aplicarlo con personas reales. |

**Pruebas P2 y P3:** las suites automatizadas cubren:
- permisos por rol;
- separación entre respuestas y registro de participación de tiquetes y encuestas;
- que no se filtren las respuestas correctas;
- que nadie se autoevalúe;
- vitrina sin trabajos no autorizados;
- borrado y cierre de cohorte.

La revisión actual se documenta en [REVISION_CRUZADA.md](REVISION_CRUZADA.md). La reproducción externa, OAuth, correo y permisos de los videos aún requieren una prueba con el dominio y las cuentas reales antes de abrirlo.

### 3.4 Revisión de seguridad, accesibilidad y materiales para las sesiones

**Seguridad.** Una revisión independiente del código encontró 6 defectos. Todos están corregidos y tienen prueba de regresión:

1. **Escalada de privilegios:** una docente de una asignatura podía generarse un código para el correo de la administración y entrar con ese rol. Ahora no se emiten códigos para cuentas docentes ni para personas de otra asignatura.
2. **Acceso retirado:** una persona a la que se le retiró el acceso podía volver a entrar pidiendo acceso de nuevo. Ahora el retiro se recuerda; rechazar una solicitud no bloquea el código del curso.
3. **Fichas de evidencia y comentarios de trabajos retirados** se podían descargar o leer. Ahora siguen el estado del catálogo.
4. **Separación de identidad y respuesta:** los resultados no contienen nombre o correo, y el indicador de participación vive en otra tabla para evitar duplicados. `WITHOUT ROWID` y `secure_delete` no garantizan anonimato ni borrado irrecuperable de copias, WAL o almacenamiento; la UI y la guía ya no hacen esa promesa.
5. **Límite por IP:** se podía saltar falsificando `X-Forwarded-For`.
6. **Datos mal formados:** cortaban la conexión. Ahora responden un error claro.

Además: protección contra envíos desde otros sitios (cabecera `Origin`), límite de 20 comentarios por hora, protección del CSV contra fórmulas con tabulación, y el rol de administración se pierde de inmediato al quitarlo de la configuración.

**Paleta y contraste.** Se ordenaron los colores en tokens y se comprobó el contraste de 54 pares de tokens en ambos temas, sin fallas en ese conjunto. Esto no equivale a certificar todas las pantallas: la verificación por vistas reales y estados sigue pendiente. Hay modo oscuro, preferencias de alto contraste y texto de estado además de color. Detalle en [PALETA_ACCESIBLE.md](PALETA_ACCESIBLE.md).

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
- 225 verificaciones automatizadas en 6 suites, todas aprobadas en la última corrida: acceso, entregas/materiales, foro/tiquetes/vitrina, encuestas/indicadores/datos, seguridad y páginas públicas.
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
- Los RA1 a RA4 y la guía ABP definen una cadena explícita: **alteración, proceso molecular, efecto en ADN, ARN o proteína, cambio celular, patología, técnica y controles**. La entrega actual usa campos estructurados para articular el caso y el razonamiento; revisar si la rúbrica docente requiere separar más etapas.
- El KPSI y su cruce muestran que el curso entiende la teoría pero no logra «imaginar» los procesos, y que tiene dudas sobre los tipos de PCR, la extracción y los controles. **Mejora:** 2 o 3 preguntas de control por cápsula (aula invertida con quiz previo: DME 0,56 frente a 0,26 sin quiz, Hew y Lo 2018), enfocadas en esas dudas.
- **Tiquetes de salida:** el documento ya define 3 preguntas estándar, su aplicación por QR, la agrupación de respuestas y la retroalimentación por audio. El repositorio puede alojarlos:
  - un formulario por sesión con QR;
  - un CSV para agruparlas;
  - un enlace al audio de retroalimentación.

  Así ningún dato pasa por Google Forms.
- **Foro:** la propuesta pide una pregunta guía por cápsula y que el equipo autor responda de forma destacada. La versión actual incluye hilo y respuesta del equipo autor; revisar su uso con docentes y estudiantes.

### Pedagogía · Incentiva (Metodología de la Investigación)
- Son cerca de 80 estudiantes en **2 paralelos** (Bioanálisis y Oftalmología) y unos 16 equipos, según los antecedentes compartidos. La entrega y los filtros ya contemplan paralelo; confirmar matrícula y configuración final antes de abrir la cohorte.
- **Storyboard de 6 bloques:** es una pauta para estructurar un único video final de hasta 5 minutos por equipo. La versión actual sincroniza sus seis apartados en la app, guía y kit imprimible; revisar contenido y tiempos con la profesora.
- **Caja sorpresa:** hay seis borradores de desafío listos para revisión docente y publicación. Los tipos de desafío de la propuesta son acceso rural, personas mayores, comunidad escolar, discapacidad, seguimiento y detección temprana.
- **Coevaluación entre pares:** se incorporó una pauta provisional basada en los criterios disponibles. La docente debe contrastarla con la rúbrica oficial antes de usarla para calificar.

### Producto y UX
- Hoy la docente debe aprobar a cada estudiante uno por uno. El código del curso elimina ese cuello de botella.
- Faltan la edición y el retiro de materiales publicados: un error de tipeo obliga a crear otro material.
- Los videos admitidos se muestran como vista previa cuando el proveedor y sus permisos lo permiten. YouTube no listado no restringe el acceso a quien tenga el enlace; para materiales de curso, preferir Drive restringido a cuentas autorizadas.
- Falta un indicador de «IA declarada» y de «foro abierto» en las tarjetas, como muestran los mockups de la propuesta.

### Técnica y seguridad
- La arquitectura (Python sin dependencias, SQLite en modo WAL, un servidor) es adecuada para unas 120 personas.
- Los roles docentes se configuran por variables de entorno, así que cambiar a una docente obliga a reiniciar. **Mejora:** gestionar los roles desde el panel de administración.
- **Respaldos:** existen copias de seguridad operativas; confirmar en el despliegue su frecuencia, ubicación y restauración. Las copias pueden contener datos personales y no se eliminan al cerrar una cohorte.
- Los archivos se envían en base64 dentro de JSON (unos 11 MB en memoria por archivo de 8 MB). Es aceptable para esta escala.
- Defensa adicional contra solicitudes de otros sitios: los POST verifican el encabezado `Origin`, además de la política de cookies.

### Datos y privacidad
- La **Ley 21.719 entra en vigencia el 1 de diciembre de 2026**, después de la fecha de esta revisión. Antes de iniciar recolección, docentes y responsables deben validar el aviso y definir:
  - plazos de conservación de entregas y cuentas;
  - un aviso de privacidad;
  - la forma de pedir que se borren los datos.
- **Datos de origen:** la carpeta de curso contiene documentos que pueden incluir información personal. `.gitignore` evita agregar las carpetas del curso, planillas, bases y respaldos al repositorio, pero se debe revisar cualquier despliegue y material adjunto antes de subirlo a un servicio externo.
- Imagen y voz: la entrega no exige identificarse en cámara. La declaración de derechos de uso del material se separa de una autorización opcional para difundirlo; confirmar el formulario descargable con las docentes.

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
| 21 | ✅ KPSI de entrada y salida dentro del repositorio, con comparación agregada; la identidad se guarda por separado para evitar duplicados y no se promete anonimato certificado | Evaluación |
| 22 | ◐ Encuesta de percepción provisional; confirmar el instrumento y sus ítems con la docente antes de aplicarla | Evaluación |
| 23 | ✅ Roles docentes gestionados desde el panel, sin variables de entorno | Técnica |
| 24 | ◐ Funciones de acceso, eliminación y cierre de cohorte listas; política de conservación y aviso requieren validación docente antes de recolectar datos. Ley 21.719 entra en vigencia el 1 de diciembre de 2026. | Datos |
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


## Revisión cruzada posterior

La revisión por roles, el cruce con las fuentes del curso, las mejoras aplicadas y las validaciones pendientes están en [REVISION_CRUZADA.md](REVISION_CRUZADA.md). La suite más reciente pasó 225 verificaciones; las limitaciones de privacidad, proveedores externos y accesibilidad por vista se describen allí.
