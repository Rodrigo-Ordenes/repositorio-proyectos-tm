# Estudio de usabilidad y decisiones de producto

## Propósito

Diseñar una entrada web común para dos asignaturas y proyectos independientes, con experiencia clara en celular y computador y acceso restringido por aprobación a la comunidad PUCV. El sitio debe permitir reconocer rápidamente el curso correcto, encontrar recursos, entregar el trabajo y participar en el foro de Innova.

## Lectura del problema

La propuesta audiovisual reúne ambos proyectos en una portada compartida, con un buscador, una lista de videos y un formulario único. Aunque incluye tarjetas y colores distintos para Incentiva e Innova, las listas mezcladas, el filtro “Todos” y el envío compartido dejan abierta la posibilidad de entrar al proyecto equivocado o no entender las diferencias entre productos.

Los proyectos tienen estructuras de contenido distintas:

| Incentiva en el Aula | Innova en el Aula |
|---|---|
| Metodología de la Investigación | Fundamentos de Diagnóstico Molecular |
| Desafío sociosanitario y territorial | Caso clínico-molecular |
| Video-prototipo de una solución y Ficha de Evidencia | Cápsula científica, prototipo 3D y matriz de técnica diagnóstica |
| Navegación por desafío, comunidad y tipo de solución | Navegación por alteración, efecto molecular, técnica y controles |

La plataforma puede compartir dominio, servidor y componentes visuales sin compartir los recorridos de navegación ni mezclar registros.

## Hallazgos aplicados

1. **Separar proyectos con navegación persistente.** La portada ofrece dos entradas claras. Cada clic abre una ruta propia (`/incentiva` o `/innova`), y las páginas de recursos mantienen esa pertenencia. El retorno a “Proyectos” está siempre disponible. GOV.UK recomienda no usar pestañas como navegación entre páginas; las pestañas ocultan contenido y se reservan para contenido relacionado dentro de una misma vista. [GOV.UK: Tabs](https://design-system.service.gov.uk/components/tabs/)
2. **Poner primero la tarea frecuente.** En cada espacio, la acción principal es explorar sus casos o desafíos; la entrega está visible como acción separada. Las fichas explican para qué sirve cada recurso y qué se espera del equipo.
3. **Ayudar a reconocer, no memorizar.** Nombre del proyecto, asignatura, tipo de producto y etiquetas aparecen en portada, resultados y fichas. La identidad cromática refuerza el contexto, pero el color no es el único indicador.
4. **Buscar dentro del proyecto actual.** El buscador y los filtros aplican solo al proyecto abierto. Así se mantiene el contexto mientras se encuentra una ficha y se evita que resultados de la otra colección aparezcan accidentalmente.
5. **Hacer visible el estado de las acciones.** Las entregas confirman que fueron recibidas para revisión. Los comentarios informan que están pendientes de moderación. Los errores se expresan en lenguaje directo y junto al control relacionado.
6. **Diseñar para distintos tamaños y formas de interacción.** La cuadrícula pasa a una columna en celular; los controles tienen un área cómoda; hay orden de lectura, enlace para saltar al contenido, estados de foco visibles y preferencia por reducir movimiento. WCAG 2.2 incluye reflow a 320 píxeles CSS, foco visible y tamaño mínimo de objetivos táctiles como criterios relevantes. [W3C: WCAG 2.2](https://www.w3.org/TR/WCAG22/), [W3C: Reflow](https://www.w3.org/WAI/WCAG22/Understanding/reflow.html), [W3C: Focus visible](https://www.w3.org/WAI/WCAG22/Understanding/focus-visible)
7. **Dar acceso sin exponer datos académicos.** Ingreso con Google Workspace PUCV (si el cliente externo se configura y la organización lo permite), código personal o enlace de un solo uso por correo. Identidad institucional y acceso a cada proyecto son controles separados: la docente puede aprobar la solicitud individual o emitir un código de curso limitado por vigencia/usos. Solo el correo en un dominio PUCV no demuestra matrícula actual.

## Sistema visual

La dirección visual acordada es editorial, cálida y vinculada con salud y territorio: marfil de papel para las superficies, verde bosque para Incentiva y arcilla suave para Innova. El verde también aparece en detalles de navegación y estados positivos; el acento terracota de Innova conserva una identidad propia. Los títulos serif, líneas finas y bordes discretos reducen el aspecto de plantilla. Cada asignatura repite nombre, número, curso y producto para que el color no sea la única señal. Estos tonos son una interpretación de producto y no colores oficiales del logotipo PUCV. [Normas gráficas PUCV 2023](https://pucv.cl/uuaa/site/docs/20240822/20240822181659/normas_graficas_2023.pdf)

## Acceso PUCV

La documentación de Aula Virtual PUCV identifica `@mail.pucv.cl` como correo estudiantil y usa una cuenta institucional de Google para ingresar a la plataforma. Se aceptan los dos dominios indicados por la docente: `@mail.pucv.cl` y `@pucv.cl`. [Aula Virtual PUCV: acceso de estudiantes](https://aulavirtualrecursos.pucv.cl/knowledgebase/ingresar-al-entorno-virtual-de-aprendizaje-estudiantes/), [PUCV: correo institucional estudiantil](https://www.pucv.cl/pucv/alumni/beneficios/correo-electronico-pucv)

**Acceso elegido:** Google Workspace PUCV es la opción diaria; el responsable técnico configura el cliente una sola vez y comprueba que la institución lo permita. La docente no configura Google ni TI: crea una invitación del curso, fija vigencia/usos y pega el enlace en Aula Virtual o en un correo. Al iniciar sesión, el estudiante queda agregado al curso automáticamente. Si Google no funciona, la docente puede generar códigos individuales y compartirlos de forma privada. Las invitaciones no deben publicarse en abierto.

**Límite de pertenencia:** verificar el buzón demuestra control de esa dirección, no matrícula o contrato activo. PUCV informa que el correo estudiantil puede seguir usándose después de egresar. Si “solo PUCV” significa integrantes actuales, este filtro debe complementarse con una lista autorizada o una fuente de afiliación activa. [PUCV: correo institucional estudiantil](https://www.pucv.cl/pucv/alumni/beneficios/correo-electronico-pucv)

## Decisiones de datos

La base SQLite inicial tiene entidades separadas para `projects`, `resources`, `submissions`, `comments`, `users`, `sessions`, `email_login_tokens`, `project_memberships` y un registro pequeño de acciones de moderación. Cada recurso y envío requiere un `project_id` válido. Las consultas de recursos filtran el proyecto en el servidor; no se confía en que la interfaz oculte los registros de otra colección. El panel docente permite subir documentos permitidos al directorio privado de archivos del mismo curso; las fichas se descargan solo después de validar acceso. Los videos finales viven en una plataforma/carpeta externa y se guardan como enlaces. Cada grupo puede registrar una entrega final por curso. Los comentarios nacen con estado `review` y las entregas con estado `review`. Las sesiones y enlaces mágicos guardan hashes de los tokens, no las claves originales.

SQLite con claves foráneas y WAL es una base simple y razonable para estos grupos académicos en un solo servidor de aplicación. Requiere respaldos comprobados y una sola instancia escritora; no es una garantía por sí misma de anonimato o disponibilidad. Se requieren copias de seguridad y no guardar videos dentro de la base. PostgreSQL sería el siguiente paso si el hosting obliga, se ejecutan varias instancias del servidor o la concurrencia y el volumen de publicaciones crecen.

La semilla incluye los cinco casos de Innova (HBB/variación de proteína, HBB/procesamiento de ARN, FMR1, XPC y PAH), y ejemplos de desafíos Incentiva basados en categorías de la propuesta. Los ejemplos no se presentan como trabajos publicados de estudiantes.

## Flujo principal

```text
Ingreso PUCV → elegir proyecto → explorar o filtrar recursos
                                      ├→ abrir ficha → comentar (Innova)
                                      └→ entregar trabajo → revisión docente → publicación
```

## Tareas de implementación

1. **Acceso por correo:** dominios PUCV permitidos, enlaces de un uso, expiración, límite de solicitudes y cookies seguras.
2. **Identidad visual:** portada común de marfil y verde, con identidad propia por asignatura; diseño responsive y etiquetas textuales.
3. **Experiencias separadas:** rutas propias, catálogos, búsqueda y filtros por proyecto; fichas con el flujo y producto de cada curso.
4. **Persistencia académica:** base SQLite con relaciones, estados de revisión, roles y registro de acciones.
5. **Operación docente:** aprobar personas por curso, cargar casos/guías en ese repositorio, revisar entregas y moderar comentarios.
6. **Preparación para publicar:** configurar hosting HTTPS y remitente SMTP; cargar materiales finales, consentimiento, subtítulos y privacidad.
7. **Validación con personas usuarias:** probar recorridos con estudiantes y docentes en computador, celular y teclado; priorizar correcciones a partir de errores observados.

Las tareas 1 a 5 están implementadas en el prototipo. El envío de enlaces queda operativo cuando se configuren SMTP y el dominio HTTPS; hoy no hay remitente de producción conectado. Las docentes se asignan mediante el panel de administración global; una vez asignadas, gestionan solo sus cursos. El servidor limita su revisión a las asignaturas correspondientes. El formulario admite un envío final por equipo y pide un enlace al único video y otro a la ficha compartida. Las tareas de despliegue, carga final de materiales y validación con participantes siguen pendientes de realizar en el entorno elegido.

## Evaluación de usabilidad pendiente

La primera versión implementa decisiones basadas en normas y patrones de diseño; aún no se ha observado con estudiantes o docentes. Una ronda de validación debería pedir a participantes de ambos proyectos que: (a) encuentren un caso o desafío, (b) distingan el tipo de entrega, (c) regresen a la portada, (d) envíen una entrega de prueba y (e) comenten una cápsula. Registrar tasa de éxito, tiempo por tarea, errores de proyecto y solicitudes de ayuda. Repetir con pantalla de teléfono y navegación por teclado.

## Recorrido de usabilidad (7 de noviembre de 2026)

**Método.** Recorrido cognitivo de las tareas a–e en un teléfono de 375 px, como estudiante nueva que llega con la invitación de su paralelo y entra con el código del curso. Después, los flujos de la docente: crear un código con lista, revisar, publicar, abrir el informe y la proyección. Además, auditoría automática de contraste (WCAG 2.2 AA), nombres accesibles y desborde horizontal, en tema claro y oscuro. No reemplaza la prueba con 5 estudiantes reales (pendiente #25): la hizo un agente siguiendo el protocolo.

### Corregidos (los cinco de mayor impacto)

| # | Problema | Tarea | Impacto | Corrección |
|---|---|---|---|---|
| 1 | El QR de la proyección abría el trabajo desde arriba: en el teléfono la coevaluación quedaba a casi tres pantallas. Si la estudiante no tenía sesión, después de entrar llegaba a la portada | e, sesión del 18-nov | Toda la clase, en vivo | El QR apunta a `#coevaluacion` y la ficha se desplaza ahí cuando termina de cargar. Las fichas guardan el destino durante el ingreso. Hay atajos «Comentar ↓ / Coevaluar ↓» bajo el título |
| 2 | Con la invitación, el campo de correo quedaba bajo el borde de la pantalla, detrás de la presentación | ingreso | Primer contacto de cada estudiante | Con `?unirse=` el correo recibe el foco y queda a la vista |
| 3 | Después de entrar con el código, la estudiante quedaba a mitad de la portada y no en su asignatura | ingreso, c | Desorientación inicial | Tras unirse va directo a la asignatura; tras entrar con código, la página parte arriba |
| 4 | El formulario de entrega (47 campos, 3.360 px en el teléfono) se perdía si se recargaba la página o vencía la sesión | d | Pérdida de trabajo del equipo | Borrador local por persona y asignatura (solo en ese dispositivo), con aviso y «Descartar borrador». Se borra al enviar. Los archivos hay que elegirlos de nuevo |
| 5 | Dos campos sin nombre accesible: enlace de material adicional y enunciados de la encuesta (WCAG 1.3.1 y 4.1.2) | d, docente | Lectores de pantalla | Etiqueta visible y `aria-label` |

### Pendientes documentados

- **«Desafíos» sin desafíos (tarea a).** Mientras la docente no publique los 6 borradores, la pestaña muestra solo trabajos de otros equipos y nada explica por qué. Se resuelve al publicarlos; si se retrasan, conviene un aviso en la pestaña.
- **Pestañas en el teléfono.** «Tiquetes y encuestas» ocupa tres líneas a 375 px. Funciona, pero se ve apretado.
- **Ingreso sin invitación en el teléfono.** La presentación va antes del formulario. Con invitación ya está resuelto (punto 2).
- **Cerrar sesión es un enlace GET.** Otro sitio podría cerrar la sesión de alguien (riesgo bajo, molesto). Conviene pasarlo a POST.
- **Borrador en computadores compartidos.** Queda guardado con el correo de la persona hasta enviarlo o descartarlo. En laboratorios, recordar «Descartar borrador».
- **Proyección: teclado y video.** Si se hace clic dentro del video, el reproductor captura el teclado hasta hacer clic fuera (limitación del navegador; documentada en la guía docente).

### Revisión a 375 px y en ambos temas (P1.7)

Vistas revisadas a 375 px, en claro y oscuro: ingreso con invitación; asignatura; formulario de entrega con borrador y aviso de Drive; ficha con atajos y coevaluación; panel docente completo (códigos del curso con lista, trazabilidad de ingresos, auditoría); proyección. Resultado: **0 fallas de contraste WCAG 2.2 AA, 0 campos sin nombre accesible (después de la corrección 5) y sin desborde horizontal**. La tabla de trazabilidad se desplaza dentro de su propio contenedor. El aviso de respaldo (PR #3) se revisó solo en escritorio.
