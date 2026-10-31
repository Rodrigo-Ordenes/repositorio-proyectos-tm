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
7. **Dar acceso sin exponer datos académicos.** Se envía un enlace individual al buzón declarado. El usuario confirma el acceso desde ese enlace; los listados, entregas y comentarios no se devuelven a quien no tenga una sesión activa.

## Sistema visual

El diseño mantiene un marco institucional común y usa la paleta de las Normas Gráficas PUCV 2023, en vez de colores web genéricos:

- **Azul PUCV `#29588C`** para navegación común e Incentiva.
- **Rojo PUCV `#A75154`** para la ruta Innova.
- **Dorado PUCV `#B78C30`** como acento puntual.
- **Marfil, blanco cálido y gris grafito** para superficies y lectura.

Se usan tonos atenuados de la paleta para los fondos. Las tarjetas tienen bordes finos, títulos editoriales y menos sombras; se evita decorar cada elemento con cápsulas y gradientes. Las etiquetas repiten el nombre y curso, de modo que el color nunca es el único identificador. El manual institucional define azul, rojo y dorado como los tres colores de marca y recomienda su uso principal sobre blanco. [Normas gráficas PUCV 2023](https://pucv.cl/uuaa/site/docs/20240822/20240822181659/normas_graficas_2023.pdf)

## Acceso PUCV

La documentación de Aula Virtual PUCV identifica `@mail.pucv.cl` como correo estudiantil y usa una cuenta institucional de Google para ingresar a la plataforma. Se aceptan los dos dominios indicados por la docente: `@mail.pucv.cl` y `@pucv.cl`. [Aula Virtual PUCV: acceso de estudiantes](https://aulavirtualrecursos.pucv.cl/knowledgebase/ingresar-al-entorno-virtual-de-aprendizaje-estudiantes/), [PUCV: correo institucional estudiantil](https://www.pucv.cl/pucv/alumni/beneficios/correo-electronico-pucv)

**Acceso elegido:** enlace mágico de un solo uso. La aplicación envía un mensaje a la dirección introducida; el enlace expira a los 15 minutos, se almacena como hash y se consume al confirmar acceso. Se limita a tres solicitudes por correo en 15 minutos, se usan cookies HTTP-only y el envío exige TLS. La persona administradora configura el remitente SMTP y el hosting; no se necesita una aplicación OAuth institucional.

**Límite de pertenencia:** verificar el buzón demuestra control de esa dirección, no matrícula o contrato activo. PUCV informa que el correo estudiantil puede seguir usándose después de egresar. Si “solo PUCV” significa integrantes actuales, este filtro debe complementarse con una lista autorizada o una fuente de afiliación activa. [PUCV: correo institucional estudiantil](https://www.pucv.cl/pucv/alumni/beneficios/correo-electronico-pucv)

## Decisiones de datos

La base SQLite inicial tiene entidades separadas para `projects`, `resources`, `submissions`, `comments`, `users`, `sessions`, `email_login_tokens`, `project_memberships` y un registro pequeño de acciones de moderación. Cada recurso y envío requiere un `project_id` válido. Las consultas de recursos filtran el proyecto en el servidor; no se confía en que la interfaz oculte los registros de otra colección. El panel docente permite subir documentos permitidos al directorio privado de archivos del mismo curso; las fichas se descargan solo después de validar acceso. Los videos finales viven en una plataforma/carpeta externa y se guardan como enlaces. Cada grupo puede registrar una entrega final por curso. Los comentarios nacen con estado `review` y las entregas con estado `review`. Las sesiones y enlaces mágicos guardan hashes de los tokens, no las claves originales.

SQLite con claves foráneas y WAL es una base simple y razonable para un curso con hasta decenas o pocos cientos de usuarios activos y un solo servidor de aplicación. Se requieren copias de seguridad y no guardar videos dentro de la base. PostgreSQL sería el siguiente paso si el hosting obliga, se ejecutan varias instancias del servidor o la concurrencia y el volumen de publicaciones crecen.

La semilla incluye los cinco casos de Innova (HBB/variación de proteína, HBB/procesamiento de ARN, FMR1, XPC y PAH), y ejemplos de desafíos Incentiva basados en categorías de la propuesta. Los ejemplos no se presentan como trabajos publicados de estudiantes.

## Flujo principal

```text
Ingreso PUCV → elegir proyecto → explorar o filtrar recursos
                                      ├→ abrir ficha → comentar (Innova)
                                      └→ entregar trabajo → revisión docente → publicación
```

## Tareas de implementación

1. **Acceso por correo:** dominios PUCV permitidos, enlaces de un uso, expiración, límite de solicitudes y cookies seguras.
2. **Identidad visual:** portada institucional común; azul Incentiva y rojo vino Innova; diseño responsive con etiquetas textuales.
3. **Experiencias separadas:** rutas propias, catálogos, búsqueda y filtros por proyecto; fichas con el flujo y producto de cada curso.
4. **Persistencia académica:** base SQLite con relaciones, estados de revisión, roles y registro de acciones.
5. **Operación docente:** aprobar personas por curso, cargar casos/guías en ese repositorio, revisar entregas y moderar comentarios.
6. **Preparación para publicar:** configurar hosting HTTPS y remitente SMTP; cargar materiales finales, consentimiento, subtítulos y privacidad.
7. **Validación con personas usuarias:** probar recorridos con estudiantes y docentes en computador, celular y teclado; priorizar correcciones a partir de errores observados.

Las tareas 1 a 5 están implementadas en el prototipo. El envío de enlaces queda operativo cuando se configuren SMTP y el dominio HTTPS; hoy no hay remitente de producción conectado. Las docentes se asignan mediante listas de correo por proyecto, y el servidor limita la revisión a los cursos correspondientes. El formulario admite un envío final por equipo y pide un enlace al único video y otro a la ficha compartida. Las tareas de despliegue, carga final de materiales y validación con participantes siguen pendientes de realizar en el entorno elegido.

## Evaluación de usabilidad pendiente

La primera versión implementa decisiones basadas en normas y patrones de diseño; aún no se ha observado con estudiantes o docentes. Una ronda de validación debería pedir a participantes de ambos proyectos que: (a) encuentren un caso o desafío, (b) distingan el tipo de entrega, (c) regresen a la portada, (d) envíen una entrega de prueba y (e) comenten una cápsula. Registrar tasa de éxito, tiempo por tarea, errores de proyecto y solicitudes de ayuda. Repetir con pantalla de teléfono y navegación por teclado.
