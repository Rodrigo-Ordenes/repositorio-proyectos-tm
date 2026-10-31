# Paleta de colores accesible

Evaluación de contraste de tokens y propuesta visual del repositorio. Revisión del 31 de octubre de 2026. Los valores están en `static/styles.css`, bloque `:root`. El resultado numérico de tokens no sustituye una auditoría completa de cada vista y estado.

## 1. Estado del arte: qué se exige hoy

| Referencia | Qué pide | Cómo se aplicó |
|---|---|---|
| **WCAG 2.2, criterio 1.4.3** (nivel AA) | Contraste de 4,5:1 para texto normal y de 3:1 para texto grande (desde 24 px, o desde 18,7 px en negrita). | Se usa como objetivo de diseño para texto normal; debe verificarse cada combinación que aparezca en las vistas reales. |
| **WCAG 2.2, criterio 1.4.6** (nivel AAA) | 7:1 para texto normal. | Se cumple en el texto principal (14:1 en modo claro y 15,9:1 en oscuro). |
| **WCAG 2.2, criterio 1.4.11** (nivel AA) | 3:1 para los componentes de interfaz: bordes de campos, controles y el indicador de foco. | Los bordes de los campos pasaron de 1,34:1 a 3,33–3,73:1. |
| **WCAG 2.2, criterios 2.4.7 y 2.4.13** | El foco debe ser visible. El 2.4.13 (nivel AAA) incluye condiciones geométricas y de contraste adicionales, que no quedan probadas por medir solo el color del anillo. | El anillo está definido en CSS y se midió su contraste con los fondos principales; el cumplimiento íntegro de 2.4.13 queda pendiente de probar en cada control y tema. |
| **WCAG 2.2, criterio 1.4.1** | El color no puede ser el único medio para transmitir información. | Los estados de las entregas llevan ícono y texto, además del color. |
| **APCA** (método candidato de WCAG 3, todavía en borrador) | Contraste perceptual que depende del tamaño y del peso de la letra. Valores de referencia: Lc 90 preferido y Lc 75 mínimo para texto de lectura continua, y Lc 60 para texto grande o etiquetas. | Se usó como segundo criterio experimental para revisar el texto auxiliar; no reemplaza los requisitos WCAG ni una prueba con usuarios. |
| **Simulación de daltonismo** (Machado, Oliveira y Fernandes, 2009) | Modelo fisiológico de protanopia, deuteranopia y tritanopia. Las guías recomiendan variar la luminosidad, no solo el tono, y revisar en escala de grises. | Se revisó la separación entre los acentos y entre estados. La prueba detecta combinaciones que requieren texto o iconografía además del color; no certifica usabilidad cromática. |
| **Preferencias del sistema** (`prefers-color-scheme`, `prefers-contrast`, `forced-colors`) | Respetar el modo oscuro, el pedido de más contraste y los temas de alto contraste de Windows. | Están implementadas las tres. |

La interfaz usa marfil cálido y verde hoja como base. Incentiva se marca con verde bosque; Innova con arcilla suave, que hace contraste con la identidad general y evoca trabajo de laboratorio. Nombre, número y texto acompañan siempre los acentos para que el color no cargue solo con la distinción. No son valores corporativos ni sustituyen el logotipo PUCV. El verde y la arcilla son decisiones de interfaz para los cursos, no colores oficiales de marca. [Normas gráficas PUCV 2023](https://pucv.cl/uuaa/site/docs/20240822/20240822181659/normas_graficas_2023.pdf).

## 2. Diagnóstico de la versión anterior

La documentación anterior reportaba una auditoría renderizada en 11 vistas, pero no hay un registro reproducible de páginas, estados, capturas ni resultados por vista en la carpeta. Se conserva como antecedente del trabajo de Claudia, no como certificación verificada.

- **23 combinaciones de texto bajo 4,5:1.** Las peores eran el texto de ayuda gris (3,3–3,7:1), el pie de página (3,67:1), el tipo de entrega en las tarjetas (4,0:1) y la etiqueta de Innova (4,47:1).
- **Bordes de campos con 1,34–1,41:1** frente al mínimo de 3:1, en todos los formularios (89 casos solo en el panel docente).
- **Anillo de foco naranja claro de unos 1,9:1** sobre el fondo marfil.
- **Unos 40 grises distintos escritos a mano,** sin un sistema detrás. Por eso cada pantalla tenía contrastes diferentes.
- **Texto auxiliar de 10,5–11,7 px.** Pasaba WCAG 2 en algunos casos, pero APCA lo marcaba como difícil de leer.
- **Estados «publicada» y «devuelta» distinguidos solo por verde y rojo,** que se confunden con protanopia y deuteranopia.

## 3. La nueva paleta

| Token | Uso | Claro | Oscuro |
|---|---|---|---|
| `--canvas` | Fondo marfil de página | `#f3f0e5` | `#141a16` |
| `--surface` | Tarjetas y paneles | `#fffef9` | `#1d241f` |
| `--surface-2` | Paneles internos | `#f5f2e9` | `#242b25` |
| `--ink` | Texto principal | `#252b25` | `#f0f1e9` |
| `--ink-2` | Texto secundario | `#3d473f` | `#dae0d9` |
| `--ink-3` | Ayuda y metadatos | `#4a554c` | `#c4cec4` |
| `--control` | Bordes de campos | `#697469` | `#89968b` |
| `--focus` | Anillo de foco | `#92551e` | `#e0ad6a` |
| `--forest` / `--forest-soft` | Incentiva · verde hoja | `#315d42` / `#e6ede3` | `#c4dac1` / `#26342a` |
| `--clay` / `--clay-soft` | Innova · arcilla | `#8b4c38` / `#f1e7df` | `#efc9b8` / `#392a25` |
| `--success` / `--danger` / `--warning` | Estados | `#2d603d` / `#933c32` / `#6c531b` | `#add5ad` / `#f0b4a9` / `#e6cd8c` |

Además de la paleta:

- El texto auxiliar subió a 12–13 px como mínimo.
- El modo oscuro sigue al sistema y se puede fijar a mano con el botón ◐ del encabezado. La elección se recuerda en el navegador.
- Al imprimir, la página siempre sale en claro.

## 4. Resultados

**Verificación numérica de los tokens:** 54 pares de uso, 27 por tema. El script local calculó cero fallas en ese conjunto bajo sus umbrales. Es una comprobación de tokens, no una declaración de conformidad de toda la aplicación.

**Verificación ejecutada en esta revisión:** `python3 herramientas/verificar_paleta.py` reportó cero fallas en los pares de tokens incluidos en `herramientas/paleta.json` (modo claro y oscuro). Este chequeo sí es reproducible. No demuestra por sí solo que cada página, estado, control, video incrustado o texto dinámico cumpla WCAG.

La auditoría de página `herramientas/auditoria_contraste.js` se debe ejecutar en el navegador sobre las vistas reales de estudiante, docente, privacidad y formularios, en ambos temas. El archivo registra solo la página que está abierta; no automatiza las diez vistas mencionadas por la documentación previa. El resultado por vista queda pendiente.

**Separación de colores** (ΔE CIE76; desde 20 se distinguen con claridad):

| Par | Visión normal | Protanopia | Deuteranopia | Tritanopia |
|---|---|---|---|---|
| Incentiva / Innova (claro) | 49 | 5 | 18 | 58 |
| Incentiva / Innova (oscuro) | 23 | 3 | 6 | 29 |
| Publicada / Devuelta (claro) | 77 | **9** | 22 | 90 |

Algunos tonos de proyecto pueden acercarse bajo simulaciones de deficiencia cromática, sobre todo protanopia. Por eso las asignaturas también se identifican con su nombre y número («01 · Incentiva», «02 · Innova»), y los estados llevan ícono (✓, ↺, ◷) y texto además del color.

## 5. Cómo verificarla de nuevo

Al cambiar un color, hay que volver a medir. Los scripts usados son:

- **`herramientas/verificar_paleta.py`** (lee `herramientas/paleta.json`): calcula WCAG, APCA y la simulación de daltonismo de cada par de tokens.
- **`herramientas/auditoria_contraste.js`** (se pega en la consola del navegador): recorre cada texto visible y su fondo real.

Las herramientas manuales equivalentes son el selector de color de Chrome DevTools (muestra la razón WCAG y la línea AA/AAA) y cualquier simulador de daltonismo basado en Machado (2009).

## Fuentes

- W3C. [Understanding SC 2.4.13 Focus Appearance (WCAG 2.2)](https://www.w3.org/WAI/WCAG22/Understanding/focus-appearance), y [What's New in WCAG 2.2](https://www.w3.org/WAI/standards-guidelines/wcag/new-in-22/).
- TetraLogical. [What's new in WCAG 2.2](https://tetralogical.com/blog/2023/10/05/whats-new-wcag-2.2).
- Disability World. [1.4.11 Non-text Contrast](https://www.disabilityworld.org/toolkit/standards/wcag/1-4-11-non-text-contrast/).
- Myndex. [APCA introduction](https://github.com/Myndex/apca-introduction), y University of Bath. [The times they are a-changin' (for how we measure colour contrast)](https://blogs.bath.ac.uk/digital-content-and-development/2024/11/08/the-times-they-are-a-changin-for-how-we-measure-colour-contrast/).
- Machado, G. M., Oliveira, M. M. y Fernandes, L. (2009). A physiologically-based model for simulation of color vision deficiency. *IEEE Transactions on Visualization and Computer Graphics, 15*(6), 1291–1298. Implementaciones: [colorspace (R)](https://colorspace.R-Forge.R-project.org/articles/color_vision_deficiency.html) y [colour (Python)](https://colour.readthedocs.io/en/v0.4.1/_modules/colour/blindness/machado2009.html).
