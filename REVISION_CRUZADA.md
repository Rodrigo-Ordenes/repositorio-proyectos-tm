# Revisión cruzada de la versión de Claudia

**Revisión del código y materiales:** 31 de octubre de 2026. Se contrastaron la versión actual con el respaldo del 30 de octubre, la propuesta de repositorio audiovisual, los documentos de curso y las notas compartidas en esta conversación. Se revisaron solo la estructura de los formularios estudiantiles; no se copiaron ni expusieron respuestas nominales de planillas.

## Conclusión

La dirección general funciona: un mismo sitio separa Metodología de la Investigación e Innova en el Aula en rutas, permisos, recursos y entregas distintas. La versión de Claudia añade flujos docentes útiles, materiales editables, coevaluación, preguntas de control, respaldos y una identidad visual más sobria. Conviene conservarlos.

La revisión también encontró tres ajustes que mejoran la fidelidad a lo pedido: no exigir permiso de imagen/voz para poder entregar, no llamar anónimas a respuestas cuyo registro de participación conserva la identidad por separado y distinguir a los equipos por paralelo. Se aplicaron cambios en el formulario, la privacidad y la base de datos. La tabla y materiales describen un solo video final por equipo; los seis bloques son una pauta interna del guion.

## Contraste por rol

### Como estudiante

- La portada presenta dos proyectos distintos bajo un enlace común y cada catálogo mantiene su identidad.
- El formulario permite un video y una ficha; ahora Incentiva también solicita pregunta de investigación, fuentes, comunidad, solución, indicador y limitación, en consonancia con su ficha de evidencia.
- La entrega ya no condiciona la nota a mostrar cara o voz: se propone representar con prototipo, dibujos, manos, narración o subtítulos. La declaración obligatoria se limita a permisos de recursos e identificación segura.
- Los casos de Innova quedan rotulados como ficticios y con datos simulados. Un enlace de YouTube no listado no equivale a un acceso restringido; la guía ahora lo dice y recomienda Drive limitado a cuentas PUCV cuando esté disponible.
- La diferencia de paralelo forma parte de la unicidad del equipo. Esto permite que ambos cursos usen, por ejemplo, “Equipo 4” sin bloquearse.

### Como docente

- Hay revisión de acceso, asignación de responsables por proyecto, publicación/retorno de entregas y administración de recursos.
- Los seis desafíos de Incentiva se cargan como borradores para revisión docente. Los cinco casos de Innova se alimentan de los cinco DOCX fuente y se mantienen editables en el repositorio.
- El código de clase da acceso inmediato a una persona que ya verificó una cuenta PUCV; al compartirlo, reemplaza la aprobación individual. Es configurable con vigencia, máximo de usos y paralelo. Para acceso más cerrado, la otra opción es aprobar solicitudes una por una.
- La rúbrica de coevaluación, el KPSI de Incentiva y la encuesta de percepción siguen siendo propuestas; los documentos fuente no acreditan que sean instrumentos validados. No se deben usar para atribuir causalidad o para investigación formal sin revisión de la docente y, si corresponde, sus resguardos éticos.
- El cierre de cohorte conserva respaldos anteriores con datos; anonimizar la base activa no elimina automáticamente esas copias. La guía docente ahora exige definir conservación y guardar el respaldo de forma controlada.

### Como equipo informático

- SQLite, relaciones por proyecto, control de acceso del lado del servidor, códigos de un uso, protección CSRF, revisión de archivos y respaldos son una base simple para un curso en un único servidor.
- Se corrigió la clave única de entregas para incluir paralelo; una prueba de regresión comprueba nombres de equipo repetidos en paralelos distintos.
- Google exige configurar un OAuth propio y puede ser bloqueado por la organización. Los códigos individuales y el enlace de correo son alternativas. Un dominio de correo PUCV identifica control del buzón, pero no confirma matrícula vigente.
- El sitio almacena enlaces externos para videos, no los MP4. Su disponibilidad, acceso y conservación dependen de la plataforma elegida por el equipo.
- No hay evidencia de que la app se haya desplegado en un dominio con OAuth, remitente de correo, responsable de datos y política de retención definidos. El diagnóstico local no sustituye esa preparación operativa.

## Cruce con los documentos

| Fuente | Lo que pide o aporta | Tratamiento en la plataforma |
|---|---|---|
| `Propuesta_apoyo_audiovisual_repositorio_TM.pdf` | Un repositorio común; dos proyectos, productos y públicos diferenciados; apoyo audiovisual; un video-prototipo de hasta cinco minutos para Incentiva y cápsula/prototipo/matriz para Innova. | Rutas separadas bajo una entrada común. Una entrega final por equipo, y seis bloques de guion dentro de la misma pieza. |
| Programa de Metodología de la Investigación | Pregunta, hipótesis, objetivos, diseños, variables, evidencia crítica y análisis de resultados. | Se agregaron pregunta, fuentes y solución a la ficha del sistema; la plantilla Word conserva la ficha ampliada para presentar hipótesis, objetivos y metodología. |
| Formulario del proyecto Incentiva y notas de clase | Desafíos sociosanitarios simulados, contexto territorial, personas afectadas, investigación, innovación y evaluación de resultado. | Seis desafíos de muestra siguen ocultos hasta que la docente los revise. Los equipos deben contrastar los datos ficticios con evidencia real citada. |
| Propuesta Innova, planificación, cinco casos clínico-moleculares, cruce RA1–RA4 y tiquetes de salida | Integrar alteración → proceso → efecto → patología → técnica y controles; prototipo 3D, comunicación entre pares y evaluación inicial/final. | Cinco casos sembrados; formulario estructurado y matriz diagnóstica; herramienta de preguntas, KPSI y tiquetes. No se declara eficacia clínica. |
| Planillas KPSI y formulario resumen | Información de aprendizaje estudiantil que puede ser sensible o identificable. | Permanecen excluidos del repositorio remoto por `.gitignore`; no se cargan como recurso ni semilla. Los instrumentos nuevos no reproducen esos registros nominales. |

## Mejoras aplicadas

1. La entrega requiere confirmar permisos de recursos y que las personas identificables autorizaron aparecer o que el equipo presentó una versión sin identificarlas. El formulario de uso futuro de imagen/voz se declara opcional.
2. Las encuestas se describen con precisión: el contenido no lleva correo o nombre, pero el sistema guarda en una tabla separada quién ya respondió. No se promete anonimato certificado.
3. Se permite el mismo nombre de equipo en paralelos distintos, manteniendo la unicidad dentro del paralelo.
4. Se añadió pregunta de investigación, mínimo de tres fuentes y descripción de solución al formulario de Incentiva.
5. Los cinco casos de Innova incluyen una advertencia visible de ficción y datos simulados.
6. Se amplió la guía y los accesos del sitio con rutas por nivel: edición sencilla, animación 2D, modelado y animación 3D, diagramas, audio, y generación visual con IA. Blender, Kdenlive, OpenToonz, Audacity y diagrams.net ofrecen alternativas gratuitas; las opciones web de IA muestran límites, marcas de agua o disponibilidad variable. Ninguna se requiere para completar la entrega.
7. La privacidad ahora se presenta como borrador para revisión docente, identifica la fecha de entrada en vigencia de la Ley 21.719 y advierte que el plazo de conservación y proveedores están por definir.
8. La paleta conserva los tonos cálidos y sobrios y las asociaciones por proyecto. El verificador numérico de tokens se ejecutó; no se conserva como validada la afirmación anterior de 290 combinaciones visuales.

## Validación reproducible

La suite de extremo a extremo se ejecuta sobre bases temporales; el número vigente de verificaciones está en `README.md`. El verificador de paleta reporta cero fallas en los pares incluidos en su catálogo. Estas comprobaciones no prueban despliegue, autorización OAuth real, correo de producción, accesibilidad completa de cada página ni revisión pedagógica de los instrumentos.

## Siguiente decisión y tareas

1. **Antes de abrir el acceso:** validar el aviso de privacidad, responsable/contacto, propósito del KPSI y encuesta, permisos de investigación, plazo de conservación y tratamiento de respaldos.
2. **Docentes:** aprobar las versiones finales de casos y desafíos, confirmar los paralelos y revisar rúbrica, KPSI de Incentiva y encuesta de percepción.
3. **Administración del sitio:** configurar OAuth, dominio HTTPS, correo, administradores por curso, almacenamiento persistente y copias fuera del hosting.
4. **Prueba con usuarios:** pedir a estudiantes que encuentren su curso, caso, guion, herramienta y entrega desde celular; pedir a cada docente que publique, devuelva y corrija material. Registrar errores sin nombres y repetir después de corregirlos.
5. **Revisar enlaces audiovisuales:** decidir el servicio de alojamiento y comprobar permisos con una cuenta de cada paralelo antes de mostrar los trabajos en aula.

## Fuentes oficiales consultadas

- Google, [OpenID Connect para Sign in with Google](https://developers.google.com/identity/openid-connect/openid-connect): verificación de `hd`, firma, emisor, audiencia y expiración.
- OpenID Foundation, [OpenID Connect Core 1.0 §3.1.3.7](https://openid.net/specs/openid-connect-core-1_0-18.html#IDTokenValidation): validación del token y excepción de validación TLS directa en el flujo de código.
- Biblioteca del Congreso Nacional, [Ley 21.719](https://www.bcn.cl/leychile/navegar?i=1209272&f=2026-12-01&p=10527471): entrada en vigencia el 1 de diciembre de 2026.
- Herramientas audiovisuales: [Canva](https://www.canva.com/video-editor/), [Clipchamp](https://clipchamp.com/en/pricing/), [Kdenlive](https://kdenlive.org/), [Audacity](https://www.audacityteam.org/faq/), [Blender](https://www.blender.org/about/license/), [OpenToonz](https://opentoonz.github.io/e/), [Tinkercad](https://www.tinkercad.com/), [Adobe Express](https://helpx.adobe.com/express/web/ai-assistant/adobe-express-ai-assistant-faq.html), [Runway](https://help.runwayml.com/hc/en-us/articles/50404627334547-Free-plan-details), [Pika](https://pika.art/pricing) y [Luma](https://lumalabs.ai/learning-hub/payments-subscriptions).
