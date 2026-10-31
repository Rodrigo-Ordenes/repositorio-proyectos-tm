# Repositorio de proyectos PUCV

Aplicación web única para mantener Incentiva e Innova bajo un solo dominio, con dos espacios diferenciados. Incluye catálogo con filtros, fichas con video insertado, entregas estructuradas, foro con pregunta guía y respuestas del equipo autor, preguntas de control, coevaluación entre pares, tiquetes de salida y encuestas KPSI/percepción con QR, vitrina de solo lectura, indicadores para los informes, herramientas de datos personales, respaldos y base SQLite. Solo usa Python estándar.

## Código de emergencia (SOS)

Por si falla Google, el correo o un código durante una clase o una grabación. `python3 server.py codigo-sos tu-correo` muestra el código **una sola vez** y guarda solo su hash en `data/sos.txt` (fuera de git). En Render, pega la línea que imprime en la variable secreta `PUCV_SOS`. Se entra en «Tengo un código de ingreso» con ese correo y ese código, siempre como administración; cada uso queda en el registro del servidor y los intentos fallidos se limitan igual que los demás códigos. Generar uno nuevo invalida el anterior.

## Funciones para la docente y los equipos

- **Ficha de evidencia automática:** cada entrega genera su Ficha de Evidencia (Incentiva) o matriz diagnóstica (Innova) en `/ficha/<id>`, lista para imprimir o guardar en PDF. Subir la plantilla Word pasa a ser opcional.
- **Comparación de alternativas (Incentiva):** hasta 3 ideas puntuadas de 1 a 3 en los 7 criterios de la postulación, con la elegida marcada; aparece en la ficha y en la revisión.
- **Modelo 3D (Innova):** el equipo sube un STL y la ficha lo muestra en un visor que se gira con el mouse o las flechas.
- **Preguntas previas:** además del tiquete de salida, preguntas antes de la sesión (aula invertida). La docente categoriza cada respuesta y el panel calcula la duda dominante y las palabras frecuentes; el CSV incluye las categorías.
- **Seguimiento por equipo:** por paralelo, quién está ligado a una entrega, el estado de cada equipo y quién falta.
- **Informe final:** `/informe/<proyecto>` con indicadores, entregas, KPSI entrada/salida, preguntas de control, coevaluación y dudas frecuentes, con gráficos y tabla de datos; se imprime en PDF.
- **Modo proyección:** `/proyeccion/<proyecto>` muestra los trabajos publicados uno tras otro, por paralelo, con temporizador de 5 minutos y un QR para coevaluar en vivo.
- **Cohortes:** cada semestre es una cohorte (`APP_COHORT`, por defecto 2026-2). Abrir una nueva no borra nada: lo anterior queda archivado y filtrable, y los indicadores se calculan por cohorte.

## Comandos de consola

| Comando | Para qué |
|---|---|
| `python3 server.py` | Iniciar el sitio |
| `python3 server.py diagnostico` | Revisar la configuración antes de publicar (sale con error si falta algo crítico) |
| `python3 server.py codigo correo@pucv.cl [incentiva\|innova] [días]` | Código personal de ingreso sin Google ni correo |
| `python3 server.py codigo-sos tu-correo` | Código de emergencia (SOS) de administración: no vence, acepta cualquier dominio y nunca queda en el repositorio |
| `python3 server.py borradores-desafios` | Reponer desafíos que falten como borradores (no duplica; el arranque ya crea los seis) |
| `python3 server.py respaldo [archivo.zip]` / `verificar-respaldo archivo` | Respaldo completo y su verificación |
| `python3 server.py actualizar-casos [carpeta]` | Regenerar `seeds/casos_innova.json` desde los .docx del curso |

## Materiales para las sesiones

- `materiales/kit-incentiva.pdf` y `kit-innova.pdf`: storyboard de 6 bloques para dibujar, especificaciones, guía de grabación con celular, uso ético de IA y lista previa a la entrega. En el sitio están en `/kit`.
- `materiales/ficha-evidencia-incentiva.docx` y `matriz-diagnostica-innova.docx`: plantillas en Word para los equipos.
- `materiales/consentimiento.pdf`: autorización de imagen y voz.
- `GUIA_DOCENTE.md` (cómo usar el panel), `ANUNCIOS_AULA_VIRTUAL.md` (mensajes listos para copiar) y la página `/ayuda` del sitio.

El sitio sirve estos cinco archivos en `/materiales/…` (no tienen datos personales); el resto de la carpeta no es accesible.

## Qué ofrece a cada rol

| Rol | Puede |
|---|---|
| Estudiante | Entrar con Google, código personal o código del curso; ver casos y desafíos; entregar el video y la ficha del equipo; comentar y responder en el foro; responder preguntas de control; coevaluar fichas de otros equipos; responder tiquetes y encuestas sin vincular el contenido con su nombre. |
| Persona de otro curso (si `PUCV_OPEN_PROJECTS` incluye la asignatura) | Ver en modo lector los trabajos que sus equipos autorizaron para la vitrina. |
| Docente de una asignatura | Todo lo anterior más: subir, editar y retirar materiales; códigos de acceso; revisar entregas y comentarios; preguntas de control y pregunta guía por ficha; tiquetes de salida con QR y CSV; encuestas con comparación entrada/salida; resultados de coevaluación; indicadores para el informe. |
| Administración global | Todo, más el equipo docente por asignatura, solicitudes de datos personales (descargar o eliminar), cierre de cohorte y respaldos. |

## Publicar en internet

Paso a paso completo en [MANUAL_DESPLIEGUE.md](MANUAL_DESPLIEGUE.md). Resumen:

[![Desplegar en Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/Rodrigo-Ordenes/repositorio-proyectos-tm)

1. Pulsa el botón e inicia sesión en Render con tu cuenta de GitHub. Render lee `render.yaml`: plan Starter con un disco de 1 GB para la base y los archivos (tiene costo mensual; ver `COSTOS_Y_DESPLIEGUE.md`).
2. Completa las variables marcadas como secretas. Lo mínimo es `APP_BASE_URL` (la dirección `https://….onrender.com` que asigna Render) y `PUCV_ADMIN_EMAILS`.
3. Cuando termine el despliegue, abre la consola del servicio (*Shell*) y ejecuta:
   - `python3 server.py diagnostico` para revisar la configuración;
   - entra con tu código SOS (variable `PUCV_SOS`) o genera uno con `python3 server.py codigo tu-correo@pucv.cl`;
   - Los seis desafíos de Incentiva aparecen automáticamente como borradores para revisión docente.
4. Para entrar con Google, sigue «Activar Google en 15 minutos» más abajo.

## Probar localmente

Requiere Python 3.10 o superior. No usa paquetes externos.

```sh
APP_DEMO_AUTH=1 PUCV_ADMIN_EMAILS=docente@mail.pucv.cl python3 server.py
```

Abre `http://localhost:8000` e ingresa con `docente@mail.pucv.cl` para revisar el panel docente y los dos cursos. La demostración permite revisar los recorridos y persistencia, pero acepta una dirección escrita y **no verifica su buzón ni identidad**. Está limitada al equipo local y no sirve como autenticación real; nunca activar `APP_DEMO_AUTH=1` en el sitio publicado.

### Probar las funcionalidades a mano

Con el modo demostración, entra desde «Modo de demostración local» con el correo de `PUCV_ADMIN_EMAILS` (docente) o con cualquier otro `@mail.pucv.cl` (estudiante). Para probar los códigos como los usará el curso:

```sh
python3 server.py codigo estudiante@mail.pucv.cl incentiva 30   # código personal: entra con «Tengo un código de ingreso»
```

Las invitaciones de curso se crean desde «Acceso de estudiantes» en el panel docente; copia el enlace para probar y elige el paralelo.

### Pruebas automáticas

```sh
bash pruebas/ejecutar.sh            # todas las suites (225 verificaciones)
bash pruebas/ejecutar.sh seguridad  # una sola suite
```

Cada suite levanta el servidor en el puerto 8766 con una base temporal que se borra al terminar: no toca tus datos. Necesita `python3`, `curl` y `sqlite3`. Las suites son `acceso`, `entregas_y_materiales`, `foro_tiquetes_vitrina`, `encuestas_indicadores_datos`, `seguridad` y `paginas_publicas`. GitHub Actions las ejecuta en cada cambio que se sube (`.github/workflows/pruebas.yml`).

## Acceso: tres vías, ninguna depende de TI PUCV

| Vía | Qué se necesita | Cuándo usarla |
|---|---|---|
| **Continuar con Google PUCV** (recomendada) | Un cliente OAuth creado por el equipo en su propio proyecto de Google Cloud (gratis, ~15 min). Variables `GOOGLE_CLIENT_ID` y `GOOGLE_CLIENT_SECRET`. | Ingreso diario. Verifica que la cuenta sea Google Workspace de `mail.pucv.cl`/`pucv.cl` (claim `hd`) y trae el nombre real. |
| **Código del curso + correo** (principal sin Google) | Nada externo. La docente crea en el panel un código por semestre o fase, con paralelo, vigencia y lista opcional de correos del curso. | Ingreso de todo el paralelo con un solo código. No verifica el buzón; con lista, solo entran los correos del curso. Las cuentas docentes no pueden usarlo. |
| **Código de ingreso personal** | Nada externo. La docente los genera en el panel (pega correos → descarga CSV) o por consola: `python3 server.py codigo correo@pucv.cl [incentiva\|innova] [días]`. | Respaldo si Google falla o la universidad bloquea la app; primer ingreso de la administración. |
| **Enlace por correo** (opcional) | Remitente SMTP (Gmail con contraseña de aplicación, Brevo, etc.). | Si se quiere ofrecer además del ingreso con Google. |

Además, el **enlace de invitación del curso** (panel docente → «Acceso de estudiantes») permite que estudiantes con Google PUCV entren directamente a su asignatura. La docente define paralelo, vigencia y máximo de usos, copia el enlace y lo pega en Aula Virtual o un correo; lo puede desactivar. También puede mostrar el código en clase. Las personas que no puedan entrar con Google reciben un código personal. Comparte invitaciones solo en canales privados del curso.

### Activar Google en 15 minutos

1. Con cualquier cuenta Google del equipo, abrir <https://console.cloud.google.com/>, crear un proyecto (p. ej. «repositorio-tm»).
2. *APIs y servicios → Pantalla de consentimiento de OAuth*: tipo **Externo**, nombre de la app, correo de soporte. Alcances: solo `openid`, `email`, `profile` (no requieren verificación de Google). Luego **Publicar app** (pasar de «Prueba» a «En producción»; en «Prueba» solo entran 100 usuarios agregados a mano).
3. *Credenciales → Crear credenciales → ID de cliente de OAuth → Aplicación web*. URI de redireccionamiento autorizado: `https://TU-SITIO/auth/google/callback` (y `http://localhost:8000/auth/google/callback` para probar en local).
4. Copiar el ID y el secreto a las variables `GOOGLE_CLIENT_ID` y `GOOGLE_CLIENT_SECRET` del hosting y reiniciar.
5. Probar con una cuenta `@mail.pucv.cl`. Si aparece «Acceso bloqueado: la organización no permite esta app», la administración de Google de la PUCV restringe apps de terceros: seguir con códigos personales y, en paralelo, pedir que se autorice el ID de cliente.

Una cuenta Gmail personal es rechazada aunque se intente; también una cuenta personal creada con una dirección PUCV (no tiene `hd`).

### Enlace por correo

El enlace es de un solo uso. Se acepta únicamente el dominio `@mail.pucv.cl` o `@pucv.cl`; el servidor limita las solicitudes, guarda solo el hash del token y lo invalida después del primer uso o a los 15 minutos. La verificación comprueba que la persona controla el buzón, no que actualmente esté matriculada o contratada por la PUCV. Si se requiere esa distinción, habría que mantener una lista de acceso o conectar una fuente institucional más adelante.

Para activar el envío se necesita un remitente SMTP con TLS y un dominio HTTPS del sitio. No se requiere registrar una aplicación OAuth ni pedir a TI que habilite el inicio de sesión. La persona que administra el sitio controla las credenciales del remitente.

Variables necesarias en el hosting:

```text
APP_BASE_URL=https://TU-DOMINIO
HOST=0.0.0.0
SMTP_HOST=servidor-smtp-del-proveedor
SMTP_PORT=587
SMTP_SECURITY=starttls
SMTP_USER=usuario-del-remitente
SMTP_PASSWORD=secreto-del-remitente
SMTP_FROM=Repositorio PUCV <repositorio@dominio-remitente.cl>
PUCV_EMAIL_DOMAINS=mail.pucv.cl,pucv.cl
APP_DB_PATH=/var/data/repository.sqlite3
APP_UPLOAD_DIR=/var/data/submissions_files
PUCV_ADMIN_EMAILS=correo.docente@mail.pucv.cl
PUCV_INCENTIVA_ADMINS=correo.responsable.incentiva@mail.pucv.cl
PUCV_INNOVA_ADMINS=correo.responsable.innova@mail.pucv.cl
PUCV_INCENTIVA_SECTIONS=Bioanálisis,Oftalmología
PUCV_OPEN_PROJECTS=innova
PUCV_INCENTIVA_DEADLINE=2026-11-30
PUCV_INNOVA_DEADLINE=2026-11-23
PUCV_INNOVA_SECTIONS=
APP_BACKUP_DIR=/var/data/backups
GOOGLE_CLIENT_ID=xxxx.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=secreto-del-cliente
TRUST_PROXY=1
APP_DEMO_AUTH=0
```

`PUCV_OPEN_PROJECTS` (opcional) abre la vitrina de solo lectura de esas asignaturas a cualquier cuenta PUCV; solo muestra trabajos cuyo equipo marcó la autorización de vitrina. Las fechas `*_DEADLINE` alimentan el indicador «equipos que entregaron a tiempo» (las de arriba son ejemplos: usar las del calendario real).

`SMTP_*` es opcional si se usa Google. Si está configurado, además del enlace de ingreso el sitio avisa por correo cuando se aprueba un acceso y cuando una entrega se publica o se devuelve (con el comentario de la docente). `TRUST_PROXY=1` solo detrás de un proxy que fije `X-Forwarded-For` (Render lo hace); se usa para limitar intentos por IP.

También se admite `SMTP_SECURITY=ssl` (normalmente puerto 465). No usar SMTP sin cifrado. Guardar secretos en la configuración privada del hosting y nunca en el código.

## Roles y separación docente

- `student`: solicita acceso a una asignatura o se une con el código de curso que entrega la docente y entrega el trabajo de su equipo.
- `editor`: responsable docente de una o ambas asignaturas; revisa únicamente los accesos, comentarios y entregas del proyecto que tiene asignado.
- `admin`: administración técnica global.

Los códigos de curso habilitan acceso inmediato a quien ya verificó una cuenta PUCV; para mayor cierre, la docente puede aprobar solicitudes persona por persona. La administración global asigna docentes por asignatura desde el panel («Equipo docente»), con efecto inmediato. También se pueden fijar en el servidor con `PUCV_INCENTIVA_ADMINS` y `PUCV_INNOVA_ADMINS` (listas de correos separados por coma); en ese caso la persona debe volver a iniciar sesión. `PUCV_ADMIN_EMAILS` queda reservado a la administración global. La revisión docente está acotada en el servidor por proyecto, no solo escondida en la interfaz.

## Base de datos

La base se crea en `data/repository.sqlite3`; se puede cambiar con `APP_DB_PATH`. El esquema está en `server.py` e incluye proyectos, recursos, usuarios, sesiones, tokens de acceso, membresías por asignatura, entregas, comentarios y registro de moderación. Usa relaciones, restricciones de estado, índices, claves foráneas y WAL. El panel docente permite subir recursos privados por asignatura (PDF/DOCX/PPTX/XLSX/ODT/TXT, máximo 8 MB). Un equipo puede registrar una entrega final por asignatura; una persona representante comparte el enlace al único video MP4 (máx. 5 min) y adjunta la ficha o enlaza una carpeta compartida. Videos no se suben al servidor. Configura `APP_DB_PATH` y `APP_UPLOAD_DIR` en el disco persistente. Los listados filtran el proyecto en el servidor.

Cada entrega registra paralelo (si la asignatura tiene paralelos), integrantes y los campos estructurados de su asignatura (`PROJECT_FIELDS` en `server.py`, la única definición: la interfaz la recibe de `/api/me`). Los materiales se editan o retiran desde el panel; retirar oculta el material sin borrarlo.

SQLite simplifica el despliegue para un programa académico de un curso. Almacenar videos en un servicio externo aprobado, no dentro de SQLite. Migrar a PostgreSQL si el hosting necesita varias instancias o sube la concurrencia.

### Respaldos y restauración

- **Automático:** cada 24 horas (`APP_BACKUP_HOURS`) el servidor guarda una copia consistente de la base en `APP_BACKUP_DIR` (por defecto `backups/` junto a la base) y conserva las últimas 14 (`APP_BACKUP_KEEP`). Los archivos subidos no se duplican cada día: nunca se modifican, solo se agregan.
- **Copia fuera del hosting:** panel docente → «Respaldos» → *Descargar respaldo completo (.zip)*, con la base y todos los archivos. Solo la administración global (`PUCV_ADMIN_EMAILS`) lo ve, porque contiene ambas asignaturas. Descargarlo una vez por semana y guardarlo en la unidad compartida del proyecto.
- **Consola:** `python3 server.py respaldo [archivo.zip]` crea el respaldo completo y `python3 server.py verificar-respaldo archivo.zip` comprueba la integridad, cuenta los registros y revisa que estén todos los archivos.
- **Restaurar:** detener el servicio, verificar el .zip, copiar `repository.sqlite3` a `APP_DB_PATH` (borrando antes los `-wal` y `-shm` antiguos) y el contenido de `submissions_files/` a `APP_UPLOAD_DIR`, y volver a iniciar. Para restaurar solo la base desde una copia diaria se reemplaza el archivo de la misma forma.

## Datos personales

- `/privacidad` y `/consentimiento` (autorización de imagen y voz, imprimible) se abren sin iniciar sesión. Ambos textos son versión preliminar que debe validar la docente.
- Tiquetes de salida y encuestas guardan el contenido sin correo o nombre. La participación se registra en una tabla separada para limitar duplicados; no se promete anonimato certificado.
- Panel → «Datos personales»: descargar en JSON todo lo que hay de una persona (derecho de acceso) o eliminarlo (anonimiza la cuenta, borra comentarios, coevaluaciones y entregas no publicadas, y quita su nombre de los trabajos publicados de su equipo).
- **Cierre de cohorte** (al terminar el semestre): guarda antes un respaldo completo en el servidor, anonimiza las cuentas de estudiantes, borra entregas no publicadas y nombres de integrantes, y deja en el catálogo solo los trabajos autorizados para la vitrina. Los respaldos anteriores contienen datos y no se eliminan automáticamente.

## Despliegue sin datos personales

La carpeta del proyecto tiene material del curso con datos personales (respuestas KPSI, formularios de postulación). El sitio no los necesita: los casos clínicos simulados viajan en `seeds/casos_innova.json`, y `.gitignore` excluye esas carpetas, las planillas, las bases y los respaldos. Para publicar, subir el repositorio a GitHub (Render despliega desde ahí) y comprobar con `git status` que no aparezca ningún archivo del curso. Si cambian los casos: `python3 server.py actualizar-casos "Innova en el aula 2S 2026"`.

## Diseño

Los tokens de color se verifican con los cálculos WCAG 2.2 y APCA; todavía se debe auditar cada vista real para afirmar conformidad completa. Incluye modo oscuro automático o manual (botón ◐), `prefers-contrast` y temas de alto contraste de Windows. El detalle, la investigación y las herramientas para volver a medir están en [PALETA_ACCESIBLE.md](PALETA_ACCESIBLE.md).

La paleta usa marfil cálido y verde bosque como base, un acento de hoja para Incentiva y ciruela para Innova (elegido para que ambos se distingan también con daltonismo). Los títulos serif y las líneas finas dan un tono editorial relacionado con salud y territorio sin imitar el logotipo oficial. En pantalla grande las dos entradas aparecen juntas; en celular se apilan. El buscador y las tarjetas pertenecen a un solo proyecto por vez.

## Despliegue

El servidor incluido facilita una primera publicación en un solo hosting. Para producción, usar HTTPS, configuración de secretos, límite de frecuencia de correo y revisión del remitente para evitar abuso. Antes de abrir el acceso al curso, validar el aviso de privacidad (`/privacidad`, versión preliminar) y la autorización de imagen y voz (`/consentimiento`), y definir quiénes moderan.

## Documentación

- [**Manual de despliegue**: publicar, primer ingreso con SOS, cuentas, mantenimiento y tecnologías](MANUAL_DESPLIEGUE.md)
- [Plan de mejoras, estado del arte del acceso y tareas priorizadas](PLAN_DE_MEJORAS.md)
- [Estudio de usabilidad, decisiones de producto y tareas](ESTUDIO_DE_USABILIDAD.md)
- [Protocolo de validación de usabilidad con estudiantes y docente](PROTOCOLO_VALIDACION_USABILIDAD.md)
- [Paleta accesible: estado del arte, medición y resultados](PALETA_ACCESIBLE.md)
- [Guía para la docente](GUIA_DOCENTE.md) y [anuncios para el Aula Virtual](ANUNCIOS_AULA_VIRTUAL.md)
- [Guía del video único por equipo](GUIA_VIDEO_PROTOTIPO.md)
- [Alternativas de dominio, hosting y correo](COSTOS_Y_DESPLIEGUE.md)
