# Contrato de diseño de la interfaz web de LiciGT

Parte F6a del [encargo F6](../docs/consulta/delegacion/F6_interfaz_web.md). Fija la página de consulta antes de escribir código: zonas, estados, componentes, variables CSS, accesibilidad y un boceto por estado. F6b la implementa y `design-ui-finish-gate-reviewer` la valida contra este archivo en F6e. Requisitos de origen: [`DESIGN.md`](../DESIGN.md) (sección "Interfaz de usuario"), [I3](../docs/consulta/investigacion/I3_lista_e_interfaz.md) (preguntas 3, 4 y 5), [`AGENTS.md`](../AGENTS.md) ("Reglas que no se negocian") y `src/licigt/consulta/esquemas.py` (`Fuente` y `RespuestaEstructurada`).

## Carácter de la página

- Herramienta de trabajo para un analista que revisa una licitación, no una página de presentación. Una sola página, una sola columna de lectura, sin imágenes, sin ilustraciones, sin animaciones de entrada ni degradados.
- La jerarquía la dan el texto, el espaciado y los bordes. El color refuerza el estado, pero nunca es la única señal.
- Todo el texto de la interfaz está en español y en registro formal ("usted"), como las respuestas del sistema.
- CSS propio con variables (`web/src/estilos/`), sin librería de componentes ni de utilidades. Sin fuentes externas: la demo debe funcionar sin red hacia CDN.
- Ningún texto de la respuesta se interpreta como HTML ni como Markdown: `answer`, `cita`, `warnings` y `clarification_question` se pintan como texto plano (`AGENTS.md`: los fragmentos son datos no confiables).

## Zonas de la página

En orden del DOM, que es también el orden visual y el de lectura y tabulación:

1. **Aviso de modo** (`.aviso-modo`), banda angosta arriba de todo, solo cuando aplica:
   - con `VITE_MODO=ejemplos`: "Modo ejemplos: respuestas fijas, no se consulta la API.";
   - con la cabecera `X-LiciGT-Autenticacion: ninguna-demo`: "Modo demostración: sin autenticación. La empresa es fija (empresa_demo)." No muestra el `tenant_id` como dato ni como campo.
2. **Encabezado** (`header.encabezado`):
   - nombre "LiciGT" y subtítulo "Consulta de licitaciones";
   - evento activo: `evento_id` en texto (por ejemplo, "Evento 222-IGSS-2023");
   - selector de tema (Sistema, Claro, Oscuro), compacto, a la derecha.
3. **Consulta** (`form.consulta`, dentro de `main`):
   - en modo ejemplos, un selector "Ejemplo" con los cinco escenarios antes de la caja;
   - caja de pregunta con etiqueta visible "Pregunta sobre el evento", contador "N/500" y botón "Consultar".
4. **Aviso fijo** (`.aviso-fijo`): "La respuesta se basa en los documentos cargados del evento". Siempre presente, también antes de la primera consulta y durante la carga. Va justo encima del resultado, no se cierra ni se oculta y no cambia con el estado.
5. **Resultado** (`section.resultado[data-estado]`): cabecera de estado, banda de revisión humana si corresponde, texto de la respuesta, metadatos y avisos de cobertura.
6. **Fuentes** (`section.fuentes`): tarjetas de fuente, o el contraste lado a lado cuando hay conflicto.
7. **Lista de verificación** (`section.lista`): zona reservada para F6d. Ver "Lista de verificación (reservada)".
8. **Pie** (`footer`): una línea con "LiciGT, proyecto CC3103 (UVG). No presenta ofertas ni decide la vigencia de documentos."

Fuera de esta versión: el panel de documentos incorporados al evento y de información faltante (`DESIGN.md`, "Interfaz de usuario"). No hay ruta que lo entregue; mientras tanto, lo faltante solo se ve en los avisos de cobertura de cada respuesta.

## Rejilla y ancho

- Contenedor `.contenedor`: ancho completo hasta `--ancho-lectura` (60rem), centrado, con relleno lateral `--espacio-4` (16 px) y `--espacio-6` desde 40rem.
- Ancho mínimo soportado: 320 px CSS sin desplazamiento horizontal, también con zoom al 200 %. `chunk_id`, `doc_id` y URL cortan con `overflow-wrap: anywhere`.
- Puntos de corte, de móvil hacia arriba:
  - base (320 px): todo apilado; el contraste de fuentes en conflicto va una debajo de otra;
  - `40rem` (640 px): contraste en dos columnas iguales; metadatos de la tarjeta de fuente en dos columnas;
  - `64rem` (1024 px): solo aumenta el aire vertical (`--espacio-8` entre zonas). No se añade barra lateral.
- Las zonas se separan con `--espacio-6` (móvil) y `--espacio-8` (escritorio). Dentro de un panel, `--espacio-4`.

## Estados del resultado

La web decide el estado con la función pura `estadoDe(respuesta)`, con esta precedencia (encargo F6b):

| Orden | Estado | Condición | Rótulo visible (título del panel) |
|---|---|---|---|
| 1 | `aclaracion` | `needs_clarification = true` | "Se necesita una aclaración" |
| 2 | `abstencion` | `abstained = true` | "Sin información suficiente" |
| 3 | `revision` | `needs_human_review = true` | "Requiere revisión humana" |
| 4 | `respuesta` | ninguna de las anteriores | "Respuesta" |

Además de esos cuatro, la página tiene tres situaciones que no son estados de la respuesta: vacía (antes de la primera consulta), cargando y error de conexión.

### Cómo se distinguen sin depender del color

Cada estado lleva tres señales que no son color, más el color como refuerzo:

| Estado | Texto | Ícono (forma) | Borde del panel | Color |
|---|---|---|---|---|
| Respuesta | "Respuesta" | círculo con marca de verificación | solo borde izquierdo sólido de 4 px | `--estado-respuesta` |
| Abstención | "Sin información suficiente" | círculo con una barra horizontal | borde completo discontinuo (`dashed`) de 2 px | `--estado-abstencion` |
| Revisión humana | "Requiere revisión humana" | triángulo con signo de exclamación | borde completo sólido de 2 px y banda superior | `--estado-revision` |
| Aclaración | "Se necesita una aclaración" | globo de diálogo con signo de interrogación | borde completo punteado (`dotted`) de 2 px | `--estado-aclaracion` |

- Los íconos son SVG en línea de 20 px con trazo `currentColor` y `aria-hidden="true"`; el rótulo de texto es el que lee el lector de pantalla.
- El rótulo es el `h2` del panel, siempre visible, nunca solo en un `title` o en un tooltip.
- El atributo `data-estado` del panel es el único gancho de estilo: `.resultado[data-estado="revision"]`, etcétera. Sin clases por color.
- En modo de alto contraste del sistema (`forced-colors: active`) se pierden los fondos, pero quedan el texto, el ícono y el estilo del borde.

### Panel de respuesta

- Cabecera: ícono, rótulo "Respuesta".
- Texto de `answer` tal cual, con `white-space: pre-line` para conservar saltos de línea. Tamaño `--texto-lg`.
- **Datos literales:** las fechas, horas, montos y plazos salen literales de los documentos (por ejemplo, "06 de octubre de 2023, a las 11:00 horas"). La web no reformatea, no abrevia, no traduce a formato numérico ni resalta partes de `answer` por su cuenta. No parsea `answer`.
- Metadatos en una línea (`dl` en línea): "Evento: 222-IGSS-2023", "Herramienta: Búsqueda en documentos", "Cobertura: parcial" o "Cobertura: sin faltantes detectados".
- Nombres visibles de `tool_used`: `buscar_documentos` como "Búsqueda en documentos", `extraer_requisitos` como "Extracción de requisitos", `comparar_versiones` como "Comparación de versiones"; nulo como "Ninguna".
- Después, los avisos de cobertura y las fuentes.

### Panel de abstención

- Cabecera: ícono, rótulo "Sin información suficiente".
- `answer`, que es el texto fijo "No hay información suficiente en los documentos para responder".
- Debajo, siempre, en texto secundario: "Que no aparezca en los documentos cargados no prueba que no exista en el expediente." (`DESIGN.md`, "Principios").
- Metadatos y avisos de cobertura igual que en la respuesta. Una abstención con `coverage_status = "parcial"` muestra el aviso de cobertura con la misma visibilidad.
- Sin fuentes, la zona de fuentes dice "Sin fuentes: no se encontró evidencia suficiente." Si llegaran fuentes en una abstención, se muestran con el título "Fragmentos recuperados (no respaldan una respuesta)", nunca se ocultan.
- No usa el color de error: abstenerse es un resultado correcto del sistema, no una falla.

### Panel de revisión humana

- Cabecera: ícono, rótulo "Requiere revisión humana".
- **Banda de revisión** (`.banda-revision`), arriba del texto, a todo el ancho del panel, con fondo `--estado-revision-fondo`, borde inferior sólido y el texto: "Las fuentes difieren o un dato crítico es ambiguo. El sistema no decide cuál está vigente; revise los documentos originales."
- Luego `answer` tal cual, metadatos y avisos.
- Si las fuentes vienen de dos o más `doc_id` distintos, la zona de fuentes se muestra como **contraste lado a lado** (ver "Contradicciones"). Si todas son del mismo documento, como lista normal.
- La banda aparece siempre que `needs_human_review = true`, aunque el estado mostrado sea otro por la precedencia (por ejemplo, una abstención con revisión): la información nunca se esconde.

### Panel de aclaración

- Cabecera: ícono, rótulo "Se necesita una aclaración".
- Primero, en texto secundario, la pregunta original: "Su pregunta: «¿Cuál es la fecha?»".
- Luego `clarification_question` en `--texto-lg` (es igual a `answer`).
- Botón secundario "Escribir la aclaración": lleva el foco a la caja de pregunta, conservando el texto anterior para que el analista lo complete. No envía nada solo.
- Sin metadatos de herramienta (es nula) ni zona de fuentes. Los avisos se muestran si llegan.

### Situaciones que no son estados

- **Vacía:** aviso fijo y una línea de ayuda en el lugar del resultado: "Escriba una pregunta sobre los documentos del evento. Cada dato de la respuesta trae su fuente." Sin ejemplos de marketing ni ilustraciones.
- **Cargando:** el botón cambia a "Consultando…" y queda deshabilitado; el resultado anterior se retira; `section.resultado` lleva `aria-busy="true"` y el área de estado anuncia "Consultando. Puede tardar unos segundos." Sin indicadores giratorios que distraigan; si se usa uno, respeta `prefers-reduced-motion`.
- **Error de conexión o HTTP** (la API no responde, 422 o 500): panel `.error-consulta` con borde sólido `--color-error`, rótulo "No se pudo completar la consulta" y el código o motivo corto ("La API no respondió", "La pregunta no es válida (422)"). No se presenta como abstención, porque no lo es. Una falla de herramienta o del LLM llega como abstención desde la API y se muestra como abstención.

## Avisos de cobertura y advertencias

- Zona `.avisos` dentro del panel de resultado, debajo de los metadatos y antes de las fuentes. Nunca colapsada, nunca dentro de un acordeón ni de un tooltip.
- Con `coverage_status = "parcial"`, primero un aviso destacado con ícono de documento incompleto (rectángulo con esquina doblada y línea discontinua), borde izquierdo de 4 px en `--estado-revision` y el texto: "Cobertura parcial: hay páginas o documentos del evento que no están indexados. La respuesta puede estar incompleta."
- Con `coverage_status = "sin_faltantes_detectados"`, solo el metadato "Cobertura: sin faltantes detectados" y, al lado, "(no certifica que el expediente esté completo)" (`Contratos.md`, "Rol 3 hacia el usuario").
- Cada elemento de `warnings` es un ítem de una lista (`ul`). Formato: rótulo legible y, debajo, el texto original tal cual en `--fuente-mono` y `--texto-sm`, para que el analista pueda reportarlo.
- Rótulos legibles para los prefijos conocidos (lo que va antes de `:`); cualquier otro código se muestra con el rótulo "Aviso del sistema" y su texto original:

| Prefijo en `warnings` | Rótulo legible |
|---|---|
| `cobertura_incompleta` | "Cobertura incompleta" (el detalle trae el documento y las páginas no indexadas, por ejemplo las páginas 3 y 4 de la modificación 1 del 222) |
| `evento_con_modificaciones` | "El evento tiene modificaciones" |
| `candidatas_sin_verificar` | "Fechas sin verificar" |
| `alerta_desconocida` | "Alerta no reconocida" |

- La web no traduce ni reescribe el detalle: si el rol 2 o el rol 3 cambian el texto, se ve el nuevo tal cual.

## Fuentes

### Tarjeta de fuente

Una `article.fuente` por cada elemento de `sources`, en el orden recibido, numeradas "[1]", "[2]"… La numeración solo ordena la lista; la web no afirma qué frase de `answer` respalda cada fuente.

Contenido, en este orden:

- **Título:** "[n] " más el `doc_id`, en `--texto-base` y peso 600.
- **Metadatos** (`dl`, dos columnas desde 40rem):
  - "Página": "p. 8" si `page_end` es nulo o igual a `page`; "pp. 16–17" si es un rango;
  - "Versión de ingesta": "v" más `version_ingesta` (por ejemplo, "v1");
  - "Versión oficial": el texto de `version_oficial` o "No indicada" si es nulo;
  - "Fragmento": `chunk_id` en `--fuente-mono` y `--texto-sm`, seleccionable.
- **Cita literal:** `blockquote.cita` con borde izquierdo de 3 px en `--color-borde-control`, fondo `--color-superficie-2`, `lang="es"`, texto tal cual (sin recortar más allá de lo que trae el campo, sin reformatear fechas ni mayúsculas).
- **Acceso al original:**
  - si `source` empieza con `https://`: enlace "Abrir documento original" con el texto visible "(página 8)" al lado y la indicación accesible "abre en una pestaña nueva"; `target="_blank"` y `rel="noopener noreferrer"`. La URL no se modifica (no se añade `#page=`);
  - si no: el texto "Original no disponible en línea" y el `doc_id`, sin enlace.

La versión de ingesta y la oficial se rotulan por separado siempre, porque el anteproyecto pide no confundir la carga con la modificación oficial.

### Contradicciones: contraste lado a lado

Se activa cuando `needs_human_review = true` y las fuentes vienen de dos o más `doc_id` distintos.

- Encima de las columnas, el título "Fuentes en conflicto" y la frase fija: "El sistema no decide cuál está vigente."
- Una columna por `doc_id`, en el orden en que aparece por primera vez en `sources`. Cada columna tiene de cabecera el `doc_id` y su versión oficial ("Versión oficial: Modificación 1" o "No indicada"), y debajo sus tarjetas de fuente completas.
- Columnas de igual ancho, mismo estilo, mismo peso visual. Prohibido: rotular una como "vigente", "actual", "nueva", "anterior" o "corregida"; ordenarlas por fecha; atenuar una; marcar una con el color de respuesta.
- En móvil las columnas se apilan; cada una conserva su cabecera para que no se pierda de qué documento es cada cita.
- Más de dos documentos: tantas columnas como quepan con un mínimo de 18rem; si no caben, se apilan.

## Lista de verificación (reservada)

F6d llega después de F5 y se redacta con el contrato que F5 deje (`PropuestaLista`, `ItemLista` y las rutas de guardar y cambiar estado). Aquí queda fijado lo que no depende de ese contrato:

- **Posición:** `section.lista` después de las fuentes, con título `h2` "Lista de verificación". F6b no pinta un marcador de posición: la zona no existe en la página hasta F6d, para no mostrar en la demo controles que no funcionan.
- **Aviso fijo de la lista**, siempre visible arriba de la lista: "Los estados de la lista no certifican cumplimiento." (`DESIGN.md`, "Interfaz de usuario").
- **Estados del ítem**, con texto e ícono, no solo color:
  - "Pendiente": círculo vacío;
  - "Preparado": círculo lleno a la mitad;
  - "Revisado": círculo con marca de verificación.
- **Cada ítem** muestra categoría, carácter ("Fundamental", "No fundamental", "No indicado"), la cita, el documento, la página y las dos versiones, con la misma tarjeta de fuente reducida. Los ítems con revisión pendiente llevan la banda de revisión con su motivo, y los ítems en conflicto aparecen los dos, sin elegir.
- **Cambios locales:** marcar un ítem solo cambia el estado en pantalla y añade el rótulo "Sin guardar" junto al ítem. Nada se guarda al marcar.
- **Confirmación explícita:**
  - un botón aparte, "Guardar cambios (N)" o "Guardar N ítems", abre un `dialog` modal nativo con el resumen de lo que se va a guardar, una línea por ítem ("Requisito X: Pendiente a Preparado");
  - el modal tiene "Confirmar y guardar" y "Cancelar"; el foco entra en el título del modal, queda atrapado dentro y vuelve al botón de origen al cerrar; `Escape` cancela;
  - sin confirmación no hay petición de escritura.
- **Conflicto (409):** mensaje "Otro usuario cambió este ítem. Recargue la lista antes de guardar." El cambio local no se aplica.
- **Propuesta:** botón "Proponer lista"; los ítems propuestos llevan una casilla "Incluir" para descartar antes de guardar. La cita no se edita.

## Variables CSS

Archivo `web/src/estilos/variables.css`. El modo claro va en `:root`; el oscuro sigue al sistema salvo que el usuario fije el tema con `data-tema` en `html`. El selector de tema guarda la elección en `localStorage` dentro de `try`/`catch` y, si falla, sigue al sistema. Razón del selector: el proyector de la demo puede verse mejor en claro aunque el equipo esté en oscuro.

### Color

| Variable | Claro | Oscuro | Uso |
|---|---|---|---|
| `--color-fondo` | `#f7f7f5` | `#16181b` | fondo de la página |
| `--color-superficie` | `#ffffff` | `#1e2125` | paneles y tarjetas |
| `--color-superficie-2` | `#efefec` | `#262a2f` | cita, banda del aviso fijo, metadatos |
| `--color-texto` | `#1c1f23` | `#e6e7e9` | texto principal |
| `--color-texto-secundario` | `#4a5059` | `#a9afb8` | metadatos, ayudas |
| `--color-borde` | `#c9ccd1` | `#3d434b` | separadores decorativos |
| `--color-borde-control` | `#7d838c` | `#767d87` | bordes de caja, selector y cita (3:1 o más) |
| `--color-acento` | `#1d4f91` | `#8fb6ec` | botón primario, enlaces |
| `--color-acento-contraste` | `#ffffff` | `#16181b` | texto sobre el botón primario |
| `--color-foco` | `#1d4f91` | `#8fb6ec` | anillo de foco |
| `--color-error` | `#a3242b` | `#f19a9f` | error de conexión |
| `--color-error-fondo` | `#fbeeee` | `#2e1c1e` | fondo del error |
| `--estado-respuesta` | `#1e6b45` | `#7fcfa3` | rótulo, ícono y borde |
| `--estado-respuesta-fondo` | `#edf6f0` | `#17291f` | cabecera del panel |
| `--estado-abstencion` | `#4a5059` | `#b4bac3` | rótulo, ícono y borde |
| `--estado-abstencion-fondo` | `#f1f2f4` | `#23262b` | cabecera del panel |
| `--estado-revision` | `#8a4600` | `#f2b46b` | rótulo, ícono, borde, aviso de cobertura |
| `--estado-revision-fondo` | `#fdf1e1` | `#2f2214` | banda de revisión |
| `--estado-aclaracion` | `#4338a3` | `#b3abf2` | rótulo, ícono y borde |
| `--estado-aclaracion-fondo` | `#efeefb` | `#22203a` | cabecera del panel |

- `color-scheme: light` en `:root` y `color-scheme: dark` en el modo oscuro, para que los controles nativos sigan el tema.
- Patrón del modo oscuro: `@media (prefers-color-scheme: dark) { :root:not([data-tema="claro"]) { … } }` y el mismo bloque en `:root[data-tema="oscuro"]`. `body` declara `background: var(--color-fondo)` y `color: var(--color-texto)`.
- Ningún componente usa un color literal: todo sale de estas variables.

### Contraste medido (WCAG 2.1, fórmula de luminancia relativa)

Calculado sobre los valores de la tabla; F6e lo vuelve a comprobar sobre la página corriendo.

| Par | Claro | Oscuro |
|---|---|---|
| texto sobre fondo | 15.4 | 14.4 |
| texto sobre banda de revisión | 14.8 | 12.5 |
| texto secundario sobre superficie | 8.1 | 7.3 |
| texto secundario sobre superficie 2 | 7.1 | 6.5 |
| acento sobre superficie | 8.1 | 7.8 |
| texto del botón primario sobre acento | 8.1 | 8.5 |
| estado respuesta sobre su fondo | 5.9 | 8.3 |
| estado abstención sobre su fondo | 7.3 | 7.8 |
| estado revisión sobre su fondo | 6.4 | 8.5 |
| estado aclaración sobre su fondo | 7.8 | 7.5 |
| error sobre su fondo | 6.5 | 7.6 |
| borde de control sobre superficie | 3.8 | 3.9 |
| foco sobre fondo | 7.6 | 8.5 |

Todo el texto supera 4.5:1 (AA) y los bordes de controles y el foco superan 3:1 (contraste de elementos no textuales). `--color-borde` (1.6:1) solo se usa en separadores decorativos, nunca como único límite de un control.

### Tipografía

| Variable | Valor | Uso |
|---|---|---|
| `--fuente-texto` | `system-ui, -apple-system, "Segoe UI", Roboto, "Noto Sans", "Helvetica Neue", Arial, sans-serif` | todo el texto |
| `--fuente-mono` | `ui-monospace, "Cascadia Code", "SFMono-Regular", Consolas, "Liberation Mono", monospace` | `chunk_id`, códigos de aviso |
| `--texto-xs` | `0.75rem` (12 px) | no se usa para contenido; solo contadores |
| `--texto-sm` | `0.875rem` (14 px) | metadatos, códigos, ayudas |
| `--texto-base` | `1rem` (16 px) | cuerpo, citas, títulos de tarjeta |
| `--texto-lg` | `1.125rem` (18 px) | texto de `answer` y de la aclaración |
| `--texto-xl` | `1.25rem` (20 px) | rótulo del estado (`h2`) |
| `--texto-2xl` | `1.5rem` (24 px) | nombre "LiciGT" en el encabezado |
| `--interlinea-texto` | `1.55` | cuerpo y citas |
| `--interlinea-titulo` | `1.25` | títulos |
| `--peso-normal` / `--peso-fuerte` | `400` / `600` | sin otros pesos |

- Tamaños en `rem`, nunca en px fijos, para respetar el tamaño de letra del navegador.
- Longitud de línea de `answer` y de las citas: máximo `70ch`.
- Números de página y versiones con `font-variant-numeric: tabular-nums`.

### Espaciado, bordes y medidas

| Variable | Valor |
|---|---|
| `--espacio-1` | `0.25rem` (4 px) |
| `--espacio-2` | `0.5rem` (8 px) |
| `--espacio-3` | `0.75rem` (12 px) |
| `--espacio-4` | `1rem` (16 px) |
| `--espacio-6` | `1.5rem` (24 px) |
| `--espacio-8` | `2rem` (32 px) |
| `--espacio-12` | `3rem` (48 px) |
| `--radio` | `4px` (controles, citas) |
| `--radio-panel` | `6px` (paneles y tarjetas) |
| `--borde-fino` | `1px` |
| `--borde-estado` | `2px` (borde completo del panel) |
| `--borde-acento` | `4px` (borde izquierdo de respuesta y de cobertura parcial) |
| `--ancho-lectura` | `60rem` |
| `--alto-control` | `2.75rem` (44 px) |

- Sin sombras salvo una sola, `--sombra-dialogo`, para el modal de confirmación de F6d.
- Transiciones: solo color y fondo, `120ms`, y ninguna con `prefers-reduced-motion: reduce`.

## Componentes y nombres

Clases en español, con el patrón bloque y elemento (`.fuente`, `.fuente__cita`) y estado por atributo (`data-estado`, `aria-*`), no por clase de color.

| Componente | Bloque | Notas |
|---|---|---|
| Aviso de modo | `.aviso-modo` | fondo `--color-superficie-2`, texto `--texto-sm`, borde inferior |
| Encabezado | `.encabezado` | no es fijo al desplazar |
| Formulario | `.consulta` | `textarea` de 3 filas, `maxlength="500"`, contador con `aria-live="polite"` solo al pasar de 450 |
| Botón primario | `.boton` | fondo `--color-acento`, alto `--alto-control`; deshabilitado con opacidad y cursor, sin perder el texto |
| Botón secundario | `.boton.boton--secundario` | fondo transparente, borde `--color-borde-control` |
| Aviso fijo | `.aviso-fijo` | fondo `--color-superficie-2`, borde izquierdo de 4 px `--color-borde-control`, ícono de información, `--texto-sm` en peso 600 |
| Panel de resultado | `.resultado[data-estado]` | cabecera con fondo del estado, cuerpo con `--color-superficie` |
| Banda de revisión | `.banda-revision` | ver "Panel de revisión humana" |
| Avisos | `.avisos`, `.aviso-cobertura` | ver "Avisos de cobertura y advertencias" |
| Tarjeta de fuente | `.fuente` | borde `--borde-fino` `--color-borde`, radio `--radio-panel` |
| Contraste | `.contraste`, `.contraste__columna` | rejilla `repeat(auto-fit, minmax(18rem, 1fr))` |
| Error | `.error-consulta` | borde sólido `--color-error`, fondo `--color-error-fondo` |
| Lista (F6d) | `.lista`, `.item-lista`, `dialog.confirmacion` | ver "Lista de verificación (reservada)" |

Pruebas de la web (encargo F6b): solo `estadoDe` con Vitest; el resto se valida con `tsc`, el build y la compuerta de F6e contra este archivo.

## Accesibilidad

Meta: WCAG 2.1 nivel AA.

- **Idioma y estructura:** `html lang="es"`; un `h1` ("LiciGT") en el encabezado; `h2` para el rótulo del estado, "Fuentes" y "Lista de verificación"; `h3` para cada tarjeta. Regiones: `header`, `main`, `footer`; el formulario con `aria-label="Consulta"`.
- **Orden de lectura y teclado:** orden del DOM igual al visual. Tabulación: selector de tema, selector de ejemplo (si existe), caja de pregunta, "Consultar", botón de la aclaración (si existe), enlaces "Abrir documento original". Sin `tabindex` positivo. `Ctrl+Enter` o `Cmd+Enter` en la caja envía; `Enter` agrega una línea.
- **Foco visible:** `:focus-visible` con `outline: 3px solid var(--color-foco)` y `outline-offset: 2px` en todo control y enlace. Nunca `outline: none` sin reemplazo.
- **Al llegar un resultado:** el foco pasa al `h2` del panel (`tabindex="-1"`), de modo que el lector anuncia el estado ("Requiere revisión humana") antes que el texto. Un `div role="status"` aparte anuncia "Consultando…" y luego "Resultado: " más el rótulo del estado. No se pone `aria-live` sobre todo el panel, para no leer la respuesta dos veces.
- **Lectores de pantalla:**
  - los íconos llevan `aria-hidden="true"`; el estado lo dice el texto;
  - la cita va en `blockquote` y su tarjeta es un `article` con `aria-labelledby` hacia su título;
  - el enlace al original incluye la página y "abre en una pestaña nueva" en su nombre accesible;
  - en el contraste, cada columna es una `section` con `aria-labelledby` hacia su cabecera de documento;
  - el contador de caracteres se asocia a la caja con `aria-describedby`.
- **Contraste:** ver la tabla medida. El estado nunca depende solo del color (texto, ícono y borde).
- **Tamaño de objetivo:** botones y selectores con alto mínimo de 44 px; enlaces con relleno vertical suficiente para 24 px.
- **Reflujo y zoom:** sin desplazamiento horizontal a 320 px ni al 200 % de zoom; textos largos cortan con `overflow-wrap: anywhere`.
- **Movimiento:** sin animaciones de entrada; todo efecto se anula con `prefers-reduced-motion: reduce`.
- **Alto contraste del sistema:** con `forced-colors: active`, los bordes de estado usan `CanvasText` y siguen visibles; el foco usa `Highlight`.

## Bocetos por estado

Los valores entre `<>` son marcadores: F6b los toma reales de `entregables/recuperacion/empresa_demo.zip`, sin inventarlos. Las fechas y páginas del 222 vienen de I3, pregunta 4.

### Respuesta

```text
+----------------------------------------------------------------------+
| Modo ejemplos: respuestas fijas, no se consulta la API.              |
+----------------------------------------------------------------------+
| LiciGT  Consulta de licitaciones          Tema: [Sistema|Claro|Oscuro]|
| Evento 222-IGSS-2023                                                 |
+----------------------------------------------------------------------+
| Ejemplo: [ Respondible con fuentes          v ]                      |
| Pregunta sobre el evento                                             |
| [ ¿Cuál es el monto del seguro de caución?                     ]     |
|                                                       43/500 [Consultar]
|                                                                      |
| | (i) La respuesta se basa en los documentos cargados del evento     |
|                                                                      |
| #=====================================================================
| # (v) Respuesta                                     <h2>             |
| #                                                                    |
| # <answer tal cual, con los datos literales del documento>           |
| #                                                                    |
| # Evento: 222-IGSS-2023 · Herramienta: Búsqueda en documentos        |
| # Cobertura: parcial                                                 |
| # | [doc] Cobertura parcial: hay páginas o documentos del evento     |
| # |       que no están indexados. La respuesta puede estar incompleta|
| # - Cobertura incompleta                                             |
| #   cobertura_incompleta: <doc_id> páginas no indexadas 3, 4         |
| #=====================================================================
|                                                                      |
| Fuentes (1)                                                          |
| +------------------------------------------------------------------+ |
| | [1] <doc_id de las bases>                                        | |
| | Página: pp. 26–27            Versión de ingesta: v<n>            | |
| | Versión oficial: <texto>     Fragmento: <chunk_id>               | |
| | | «<cita literal del fragmento>»                                 | |
| | Abrir documento original (página 26)                             | |
| +------------------------------------------------------------------+ |
+----------------------------------------------------------------------+
| LiciGT, proyecto CC3103 (UVG). No presenta ofertas ni decide ...     |
+----------------------------------------------------------------------+
```

`#` marca el borde izquierdo sólido de 4 px del estado respuesta.

### Abstención

```text
| | (i) La respuesta se basa en los documentos cargados del evento     |
|                                                                      |
| - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -  |
| : (-) Sin información suficiente                    <h2>           : |
| :                                                                  : |
| : No hay información suficiente en los documentos para responder   : |
| :                                                                  : |
| : Que no aparezca en los documentos cargados no prueba que no      : |
| : exista en el expediente.                                         : |
| :                                                                  : |
| : Evento: 222-IGSS-2023 · Herramienta: Búsqueda en documentos      : |
| : Cobertura: parcial                                               : |
| : | [doc] Cobertura parcial: hay páginas o documentos del evento   : |
| : |       que no están indexados. La respuesta puede estar ...     : |
| : - Cobertura incompleta                                           : |
| :   cobertura_incompleta: <doc_id> páginas no indexadas 3, 4       : |
| - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -  |
|                                                                      |
| Fuentes                                                              |
| Sin fuentes: no se encontró evidencia suficiente.                    |
```

El borde discontinuo rodea todo el panel.

### Revisión humana con contradicción

```text
| | (i) La respuesta se basa en los documentos cargados del evento     |
|                                                                      |
| +==================================================================+ |
| | /!\ Requiere revisión humana                      <h2>           | |
| |##################################################################| |
| |## Las fuentes difieren o un dato crítico es ambiguo. El sistema ##| |
| |## no decide cuál está vigente; revise los documentos originales.##| |
| |##################################################################| |
| | <answer tal cual: menciona 31 de julio de 2023 en las bases y    | |
| |  06 de octubre de 2023, a las 11:00 horas, en la modificación 1> | |
| |                                                                  | |
| | Evento: 222-IGSS-2023 · Herramienta: Comparación de versiones    | |
| | Cobertura: parcial                                               | |
| | | [doc] Cobertura parcial: ...                                   | |
| | - Cobertura incompleta                                           | |
| |   cobertura_incompleta: <doc_id mod. 1> páginas no indexadas 3, 4| |
| +==================================================================+ |
|                                                                      |
| Fuentes en conflicto                                                 |
| El sistema no decide cuál está vigente.                              |
| +-------------------------------+ +-------------------------------+  |
| | <doc_id de las bases>         | | <doc_id de la modificación 1> |  |
| | Versión oficial: <texto>      | | Versión oficial: <texto>      |  |
| |-------------------------------| |-------------------------------|  |
| | [1] p. 8 · ingesta v<n>       | | [2] p. 1 · ingesta v<n>       |  |
| | Fragmento: <chunk_id>         | | Fragmento: <chunk_id>         |  |
| | | «<cita 2.2.6, 31 de julio   | | | «<cita, 06 de octubre de    |  |
| | |   de 2023 ...>»             | | |   2023, a las 11:00 ...>»   |  |
| | Abrir documento original      | | Abrir documento original      |  |
| | (página 8)                    | | (página 1)                    |  |
| +-------------------------------+ +-------------------------------+  |
```

`=` marca el borde completo sólido de 2 px; `#` la banda de revisión con su fondo. Las dos columnas tienen el mismo ancho y estilo. En menos de 40rem se apilan, cada una con su cabecera.

### Aclaración

```text
| | (i) La respuesta se basa en los documentos cargados del evento     |
|                                                                      |
| . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . .  |
| . (?) Se necesita una aclaración                    <h2>           . |
| .                                                                  . |
| . Su pregunta: «¿Cuál es la fecha?»                                . |
| .                                                                  . |
| . ¿A qué fecha o plazo se refiere? Por ejemplo: recepción de       . |
| . ofertas, apertura de plicas o adjudicación.                      . |
| .                                                                  . |
| .                                   [ Escribir la aclaración ]     . |
| . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . .  |
```

Borde punteado; sin metadatos de herramienta ni zona de fuentes. El botón lleva el foco a la caja con "¿Cuál es la fecha?" ya escrito.

### Cobertura sin faltantes (variante de cualquier estado)

```text
| # Evento: 222-IGSS-2023 · Herramienta: Extracción de requisitos      |
| # Cobertura: sin faltantes detectados (no certifica que el           |
| #            expediente esté completo)                               |
```

Sin aviso destacado; si hay `warnings`, se listan igual.

### Lista de verificación (F6d, referencia)

```text
| Lista de verificación                               <h2>             |
| | Los estados de la lista no certifican cumplimiento.                |
|                                                                      |
| ( ) Pendiente   Técnica · Fundamental        [ Pendiente  v ]        |
|     «<cita>» · <doc_id> · p. 16 · v<n> · <versión oficial>           |
| (/) Preparado   Legal · No indicado          [ Preparado  v ] Sin guardar
|     «<cita>» · <doc_id> · p. 26 · v<n> · <versión oficial>           |
|                                                                      |
|                                         [ Guardar cambios (1) ]      |
|                                                                      |
|   +-- Confirmar cambios ------------------------------------------+  |
|   | Se guardará 1 cambio:                                         |  |
|   | - <ítem>: Pendiente a Preparado                               |  |
|   | Los estados no certifican cumplimiento.                       |  |
|   |                          [ Cancelar ] [ Confirmar y guardar ] |  |
|   +---------------------------------------------------------------+  |
```

`( )`, `(/)` y `(v)` son los íconos de pendiente, preparado y revisado. El modal es el `dialog` nativo.

## Criterios para la compuerta (F6e)

`design-ui-finish-gate-reviewer` da PASS solo si, con la página corriendo en los cinco ejemplos y en los dos temas:

- el aviso fijo se ve en todos los estados y en la página vacía;
- cada estado se reconoce en escala de grises por su rótulo, su ícono y su borde;
- cada fuente muestra documento, página o rango, versión de ingesta, versión oficial (o "No indicada"), cita literal y acceso al original o su ausencia explicada;
- la comparación del 222 muestra las dos fuentes lado a lado, con igual peso, y la frase "El sistema no decide cuál está vigente.";
- la cobertura parcial y todos los `warnings` se ven sin interacción;
- la abstención muestra la frase de que la ausencia no prueba inexistencia;
- las fechas de `answer` y de las citas aparecen tal como vienen del documento;
- no hay desplazamiento horizontal a 320 px, el foco es visible en todo control y los contrastes de la tabla se cumplen;
- no hay `tenant_id` en la página ni en la petición, ni HTML interpretado desde la respuesta.
