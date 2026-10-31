# Paleta de colores accesible

Evaluación y rediseño de los colores del repositorio. La revisión es del 31 de octubre de 2026. Los valores están en `static/styles.css`, en el bloque `:root`.

## 1. Estado del arte: qué se exige hoy

| Referencia | Qué pide | Cómo se aplicó |
|---|---|---|
| **WCAG 2.2, criterio 1.4.3** (nivel AA) | Contraste de 4,5:1 para texto normal y de 3:1 para texto grande (desde 24 px, o desde 18,7 px en negrita). | Es el mínimo para todo el texto. |
| **WCAG 2.2, criterio 1.4.6** (nivel AAA) | 7:1 para texto normal. | Se cumple en el texto principal (14:1 en modo claro y 15,9:1 en oscuro). |
| **WCAG 2.2, criterio 1.4.11** (nivel AA) | 3:1 para los componentes de interfaz: bordes de campos, controles y el indicador de foco. | Los bordes de los campos pasaron de 1,34:1 a 3,33–3,73:1. |
| **WCAG 2.2, criterios 2.4.7 y 2.4.13** | El foco debe ser visible; el 2.4.13 (nivel AAA) pide además un cambio de al menos 3:1 entre el estado con foco y sin foco. | El anillo de foco tiene 3 px y llega a 4,4–5,1:1 en modo claro y a 8–10:1 en oscuro. |
| **WCAG 2.2, criterio 1.4.1** | El color no puede ser el único medio para transmitir información. | Los estados de las entregas llevan ícono y texto, además del color. |
| **APCA** (método candidato de WCAG 3, todavía en borrador) | Contraste perceptual que depende del tamaño y del peso de la letra. Valores de referencia: Lc 90 preferido y Lc 75 mínimo para texto de lectura continua, y Lc 60 para texto grande o etiquetas. | Se usó como segundo criterio. Sirvió para detectar el texto auxiliar de 10–12 px que WCAG 2 dejaba pasar pero que se lee mal. |
| **Simulación de daltonismo** (Machado, Oliveira y Fernandes, 2009) | Modelo fisiológico de protanopia, deuteranopia y tritanopia. Las guías recomiendan variar la luminosidad, no solo el tono, y revisar en escala de grises. | Se midió en cada caso la separación entre los colores de Incentiva e Innova, y entre los de los estados. |
| **Preferencias del sistema** (`prefers-color-scheme`, `prefers-contrast`, `forced-colors`) | Respetar el modo oscuro, el pedido de más contraste y los temas de alto contraste de Windows. | Están implementadas las tres. |

No se encontró un manual de marca público de la PUCV con sus códigos de color, así que la paleta no depende de él. Conserva la identidad que ya tenía el sitio (azul para Incentiva, rojo vino para Innova, dorado como acento y fondo marfil), con los tonos ajustados hasta cumplir las normas. Si más adelante se obtienen los colores oficiales, basta con cambiar los tokens `--blue` y `--wine` y volver a correr la verificación de la sección 5.

## 2. Diagnóstico de la versión anterior

Se auditó la página renderizada: cada texto visible contra su fondo efectivo, en 11 vistas.

- **23 combinaciones de texto bajo 4,5:1.** Las peores eran el texto de ayuda gris (3,3–3,7:1), el pie de página (3,67:1), el tipo de entrega en las tarjetas (4,0:1) y la etiqueta de Innova (4,47:1).
- **Bordes de campos con 1,34–1,41:1** frente al mínimo de 3:1, en todos los formularios (89 casos solo en el panel docente).
- **Anillo de foco naranja claro de unos 1,9:1** sobre el fondo marfil.
- **Unos 40 grises distintos escritos a mano,** sin un sistema detrás. Por eso cada pantalla tenía contrastes diferentes.
- **Texto auxiliar de 10,5–11,7 px.** Pasaba WCAG 2 en algunos casos, pero APCA lo marcaba como difícil de leer.
- **Estados «publicada» y «devuelta» distinguidos solo por verde y rojo,** que se confunden con protanopia y deuteranopia.

## 3. La nueva paleta

| Token | Uso | Claro | Oscuro |
|---|---|---|---|
| `--canvas` | Fondo de página | `#f5f2eb` | `#121417` |
| `--surface` | Tarjetas y paneles | `#ffffff` | `#1b1f24` |
| `--surface-2` | Paneles internos | `#f7f5ef` | `#22272d` |
| `--ink` | Texto principal | `#1f2328` | `#eceef0` |
| `--ink-2` | Texto secundario | `#434a53` | `#d6dade` |
| `--ink-3` | Ayuda y metadatos | `#4f565e` | `#c9ced4` |
| `--control` | Bordes de campos | `#7f858c` | `#7c848d` |
| `--focus` | Anillo de foco | `#b35200` | `#ffb057` |
| `--blue` / `--blue-soft` | Incentiva | `#24507f` / `#e8eef5` | `#b8d5f6` / `#1a2a3b` |
| `--wine` / `--wine-soft` | Innova | `#8c3539` / `#f5e9e8` | `#f6c4c6` / `#3a2225` |
| `--success` / `--danger` / `--warning` | Estados | `#22603a` / `#9a2a24` / `#6b470b` | `#a3dcb3` / `#f7b4ad` / `#f5d08a` |

Además de la paleta:

- El texto auxiliar subió a 12–13 px como mínimo.
- El modo oscuro sigue al sistema y se puede fijar a mano con el botón ◐ del encabezado. La elección se recuerda en el navegador.
- Al imprimir, la página siempre sale en claro.

## 4. Resultados

**Verificación numérica de los tokens:** 54 pares de uso real, 27 por tema. Todos cumplen WCAG 2.2 AA y el umbral APCA de su uso.

**Auditoría de las páginas renderizadas** (unas 290 combinaciones de texto y fondo por tema, en 10 vistas):

| | Antes | Ahora (claro) | Ahora (oscuro) |
|---|---|---|---|
| Fallas de contraste WCAG 2.2 AA | 23 | **0** | **0** |
| Peor contraste de texto | 3,3:1 | **6,2:1** | **8,4:1** |
| Bordes de campos bajo 3:1 | 89 o más | **0** | **0** |
| Tamaño mínimo de texto | 10,5 px | 11,5 px (etiquetas en mayúsculas y negrita) | 11,5 px |

En modo oscuro quedan algunas etiquetas de 12 px con Lc 73–75, justo en el umbral APCA recomendado. Es la meta preferente de un estándar todavía en borrador, no un mínimo exigido.

**Separación de colores** (ΔE CIE76; desde 20 se distinguen con claridad):

| Par | Visión normal | Protanopia | Deuteranopia | Tritanopia |
|---|---|---|---|---|
| Incentiva / Innova (claro) | 60 | 38 | 55 | 75 |
| Incentiva / Innova (oscuro) | 32 | 21 | 28 | 42 |
| Publicada / Devuelta (claro) | 77 | **9** | 22 | 90 |

Verde y rojo se confunden con protanopia. Por eso los estados no dependen del color: llevan ícono (✓, ↺, ◷) y texto. Los dos proyectos también se identifican por su nombre y número («01 · Incentiva», «02 · Innova»), no solo por el color.

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
