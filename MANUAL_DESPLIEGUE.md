# Manual de despliegue

Cómo publicar el repositorio en internet, entrar por primera vez, dejar lista la cuenta de la docente y mantenerlo funcionando. No requiere a TI PUCV. Tiempo estimado: 30 a 45 minutos la primera vez.

## Qué vas a necesitar

| Necesario | Para qué | Costo |
|---|---|---|
| Cuenta de GitHub con acceso a este repositorio | Render lee el código desde aquí | Gratis |
| Cuenta de Render (se entra con GitHub) y una tarjeta | Servidor siempre encendido con disco para la base de datos | US$7/mes (Starter) + ~US$0,25/mes (disco de 1 GB) |
| Tu archivo privado `data/MI_CODIGO_SOS.txt` | Primer ingreso y emergencias | — |
| Correos de la docente y de quienes revisan cada asignatura | Permisos del panel | — |
| *Opcional:* proyecto en Google Cloud | Botón «Continuar con Google PUCV» | Gratis |
| *Opcional:* remitente SMTP (Gmail con contraseña de aplicación o Brevo) | Enlaces de ingreso y avisos por correo | Gratis |

> **No uses el plan gratuito de Render para el curso.** Se duerme a los 15 minutos y no tiene disco persistente: cada reinicio borra la base de datos con entregas, cuentas y respuestas.

## 1. Preparar el código SOS (2 minutos, en tu computador)

El código SOS ya está generado para `rodrigo.ordenes.a@mail.pucv.cl`. Abre `data/MI_CODIGO_SOS.txt` y ten a mano:

- el **código** (`XXXX-XXXX-XXXX-XXXX`), que se escribe al entrar;
- la **línea larga** `correo|…|…`, que es el valor de la variable `PUCV_SOS` en Render. Es un hash: aunque alguien la vea, no le sirve para entrar.

Para cambiarlo (por ejemplo, si se filtró): `python3 server.py codigo-sos rodrigo.ordenes.a@mail.pucv.cl`. El código anterior deja de funcionar.

## 2. Crear el servicio en Render (10 minutos)

1. Abre el botón **Deploy to Render** del `README.md` o entra a <https://dashboard.render.com> → **New → Blueprint** y elige este repositorio. Render lee `render.yaml`: servicio web Python 3.12, plan Starter, disco de 1 GB en `/var/data`.
2. Render pide las variables marcadas como secretas. Completa al menos estas:

| Variable | Valor |
|---|---|
| `APP_BASE_URL` | Déjala vacía por ahora; la completas en el paso 3 |
| `PUCV_ADMIN_EMAILS` | `rodrigo.ordenes.a@mail.pucv.cl` (administración global; varios correos separados por coma) |
| `PUCV_SOS` | La línea larga de `data/MI_CODIGO_SOS.txt` |
| `PUCV_INCENTIVA_ADMINS` | Correo de la docente de Metodología de la Investigación |
| `PUCV_INNOVA_ADMINS` | Correo de la docente de TEM 1133 |
| `PUCV_INCENTIVA_SECTIONS` | `Bioanálisis,Oftalmología` |
| `PUCV_INCENTIVA_DEADLINE` / `PUCV_INNOVA_DEADLINE` | Fechas de entrega, formato `AAAA-MM-DD` |

Las demás (`SMTP_*`, `GOOGLE_*`, `PUCV_OPEN_PROJECTS`, `PUCV_INNOVA_SECTIONS`) pueden quedar vacías.

3. Pulsa **Apply**. Cuando termine, Render muestra la dirección `https://repositorio-proyectos-tm-xxxx.onrender.com`. Cópiala a `APP_BASE_URL` (en *Environment*) y guarda: el servicio se reinicia solo.
4. En la pestaña **Shell** del servicio ejecuta `python3 server.py diagnostico`. Todo lo crítico debe decir `OK`; los `AVISO` son opcionales (correo, Google).

Cada `git push` a `main` vuelve a desplegar el sitio. La base de datos y los archivos subidos quedan en el disco y no se pierden.

## 3. Primer ingreso y cuenta de la docente (5 minutos)

1. Abre la dirección del sitio → **Tengo un código de ingreso** → tu correo y el código SOS. Entras como administración global.
2. Si la docente no está en `PUCV_*_ADMINS`, agrégala en **Panel docente → Equipo docente** (correo y asignatura). El cambio rige de inmediato, sin reiniciar.
3. En **Códigos personales de ingreso** pega su correo y genera su código. Entrégaselo en privado. Cuando Google esté activo, podrá entrar con el botón y el código ya no hará falta.

## 4. Dar acceso a estudiantes

La forma principal es **un código por curso o por fase**, sin Google ni códigos individuales:

- **Código del curso (recomendado):** en **Acceso de estudiantes**, la docente elige asignatura y paralelo, pone un nombre (por ejemplo «Semestre 2026-2» o «Fase 1»), la vigencia y, si quiere, la **lista del curso** (correos pegados desde la nómina). Comparte el código en clase o el enlace `/?unirse=CÓDIGO` en Aula Virtual. Cada estudiante entra en «Tengo un código de ingreso» con su correo institucional y ese código, y queda inscrito en su paralelo.
  - **Con lista:** solo entran esos correos. Es lo recomendado para que nadie ajeno al curso entre aunque se filtre el código.
  - **Sin lista:** entra cualquier correo `@mail.pucv.cl` o `@pucv.cl` que conozca el código.
  - **Límite:** el sitio no puede comprobar que el correo sea de quien lo escribe (eso solo lo hace Google o el enlace por correo). Las cuentas docentes y de administración nunca entran con el código del curso.
  - **Al terminar la fase:** se pulsa «Desactivar» o se deja vencer; abrir una cohorte nueva los desactiva todos.

Alternativas:

- **Con Google** (cuando esté activo): la docente crea en **Acceso de estudiantes** una invitación con asignatura, paralelo, vigencia y máximo de usos, y pega el enlace `/?unirse=CÓDIGO` en Aula Virtual. Quien lo abre entra con Google PUCV y queda inscrito en el paralelo sin aprobación.
- **Código personal**, para casos puntuales: en **Códigos personales de ingreso** pega los correos (uno por línea), elige la asignatura y la vigencia, y descarga el CSV con el código de cada persona. Envía cada código en privado, por ejemplo por mensaje de Aula Virtual. Ese código ya da acceso a la asignatura.
- **Solicitud**: quien entra sin invitación ve «Solicitar acceso», y la docente aprueba en **Solicitudes de acceso**.

El dominio del correo no da permisos por sí solo. `@mail.pucv.cl` y `@pucv.cl` pueden entrar, pero solo ve el panel docente quien está en `PUCV_*_ADMINS` o en **Equipo docente**.

## 5. Activar Google (opcional, 15 minutos)

Sigue «Activar Google en 15 minutos» del `README.md`. Lo importante:

- crear el cliente en un proyecto propio de Google Cloud;
- usar los alcances `openid`, `email` y `profile`, que no requieren verificación de Google;
- publicar la app;
- usar como URI de redirección `https://TU-SITIO/auth/google/callback`;
- copiar `GOOGLE_CLIENT_ID` y `GOOGLE_CLIENT_SECRET` a Render.

Si aparece «la organización no permite esta app», la PUCV bloquea apps externas. En ese caso se sigue con códigos personales, que funcionan igual.

## 6. Activar correo (opcional, 10 minutos)

Lo más simple es una cuenta Gmail del equipo con verificación en dos pasos y una **contraseña de aplicación**:

| Variable | Valor |
|---|---|
| `SMTP_HOST` | `smtp.gmail.com` |
| `SMTP_PORT` | `587` |
| `SMTP_SECURITY` | `starttls` |
| `SMTP_USER` | La dirección Gmail |
| `SMTP_PASSWORD` | La contraseña de aplicación |
| `SMTP_FROM` | `Repositorio TM <esa dirección>` |

Con eso se activan el enlace de ingreso por correo y los avisos de acceso aprobado y de entrega publicada o devuelta.

## 7. Mantenerlo

- **Respaldo fuera del sitio, una vez por semana:** en el panel, pulsa «respaldo completo (.zip)» y guárdalo en un lugar del equipo. El sitio hace copias automáticas, pero quedan en el mismo disco. El panel muestra quién descargó el último respaldo y cuándo; si pasan 7 días sin descarga, aparece un aviso arriba del panel. Cada descarga queda en la auditoría.
- **Registro de auditoría:** en el panel de administración global revisa ingresos SOS y del curso, cambios de códigos y equipo docente, retiros de acceso y anonimización. Se conserva por 180 días; las IP se guardan como huellas HMAC con una sal aleatoria persistida en la base, nunca en claro.
- **Aviso si se cae:** crea un monitor gratuito en UptimeRobot (o similar) sobre `https://TU-SITIO/api/me`. Avisa por correo si deja de responder.
- **Nuevo semestre:** en el panel, **Cohortes → Abrir cohorte**. No se borra nada.
- **Actualizar:** `git push` a `main`. GitHub Actions ejecuta las suites automatizadas en cada envío; si fallan, no conviene desplegar.

## 8. Antes de una grabación o una clase

1. Abre el sitio unos minutos antes y entra con tu código SOS.
2. Corre `python3 server.py diagnostico` en la Shell de Render.
3. Ten el código SOS a mano, fuera del computador que proyecta (en el teléfono, por ejemplo).
4. Si una cuenta no entra, entra con el SOS y genera un código personal para esa persona desde el panel. Tarda menos de un minuto.
5. Después de 6 intentos fallidos con el mismo correo, el ingreso se bloquea 15 minutos. Copia el código en vez de escribirlo de memoria.

## 9. Si algo falla

| Síntoma | Causa probable | Qué hacer |
|---|---|---|
| El sitio tarda o muestra error 502 justo después de un push | Se está desplegando | Esperar 1 o 2 minutos |
| «El correo o el código no coinciden» con el SOS | `PUCV_SOS` mal copiada o con espacios | Pegar de nuevo la línea completa y reiniciar |
| «Tu correo no está en la lista de este curso» | Correo mal escrito o ausente de la nómina | Revisar el correo; si falta, crear el código de nuevo con la lista corregida |
| El video de Drive aparece como privado | El archivo no está compartido | En Drive: Compartir → «Cualquier persona con el enlace» |
| La sesión se cierra al recargar | `APP_BASE_URL` no coincide con la dirección real | Corregirla, con `https://` y sin barra final |
| Las entregas desaparecieron | Plan gratuito o sin disco | Usar Starter con disco y restaurar el último respaldo |
| No aparece el botón de Google | Faltan `GOOGLE_CLIENT_ID` o `GOOGLE_CLIENT_SECRET` | Paso 5, o seguir con códigos |

## Alternativas de hosting

| Opción | Costo | Cuándo |
|---|---|---|
| **Render Starter + disco** (recomendada) | ~US$7,25/mes | Curso real: siempre encendido y sin administrar servidores |
| **Oracle Cloud Always Free** (VM Linux) | US$0 (pide tarjeta solo para verificar) | Si no se puede pagar. Requiere instalar Python, un servicio `systemd` y Caddy para HTTPS (~1 h de trabajo técnico) |
| **Tu computador + túnel** (Cloudflare Tunnel o localhost.run) | US$0 | Solo para una demostración puntual: depende de que el computador esté encendido y la dirección puede cambiar |

## Tecnologías usadas

| Capa | Tecnología | Por qué |
|---|---|---|
| Servidor | Python 3.12, solo biblioteca estándar (`http.server` con hilos), sin dependencias externas | Nada que instalar ni actualizar, y menos riesgo de paquetes de terceros |
| Base de datos | SQLite en modo WAL con `secure_delete`; tablas anónimas `WITHOUT ROWID` | Un solo archivo, fácil de respaldar; los tiquetes y encuestas anónimos no guardan un orden que permita reidentificar |
| Interfaz | HTML, CSS y JavaScript sin frameworks (aplicación de una página) | Carga rápida, funciona en celulares y se audita completa |
| Accesibilidad | WCAG 2.2 AA, contraste APCA, simulación de daltonismo (Machado 2009), temas claro y oscuro | Verificado con `herramientas/verificar_paleta.py` y `auditoria_vistas.js` |
| Ingreso | Google OpenID Connect con PKCE; códigos personales con PBKDF2-SHA256 y límite de intentos; enlaces de un solo uso; código SOS fuera del repositorio | Varias vías independientes, ninguna depende de TI PUCV |
| Seguridad | Cookies `HttpOnly`/`SameSite`/`Secure`, CSP estricta, verificación de origen, archivos validados por contenido (PDF, Word, STL) | Protege sesiones y datos del curso |
| Gráficos y 3D | SVG generado en el navegador; visor STL propio en canvas | Sin librerías externas; cada gráfico tiene tabla de datos |
| QR | Generador propio (`qr.py`) | Funciona sin servicios externos |
| Videos | YouTube (no listado) o Google Drive, embebidos con `youtube-nocookie` | El sitio no almacena video |
| Pruebas | Suites automatizadas en `pruebas/*.sh` con `curl`, ejecutadas por GitHub Actions | Cada cambio se prueba antes de publicarse |
| Hosting | Render (Blueprint `render.yaml`) con disco persistente | Despliegue en un clic desde GitHub, con HTTPS incluido |
