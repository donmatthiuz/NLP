# Contrato de diseño de la interfaz web de LiciGT

Parte F6a del [encargo F6](../docs/consulta/delegacion/F6_interfaz_web.md), con la base de componentes actualizada en W2 ([encargo W2](../docs/consulta/delegacion/W2_rediseno_con_shadcn.md)). Fija la página de consulta antes de escribir código: zonas, estados, componentes, variables CSS, accesibilidad y un boceto por estado. F6b la implementa y `design-ui-finish-gate-reviewer` la valida contra este archivo en F6e. Requisitos de origen: [`DESIGN.md`](../DESIGN.md) (sección "Interfaz de usuario"), [I3](../docs/consulta/investigacion/I3_lista_e_interfaz.md) (preguntas 3, 4 y 5), [`AGENTS.md`](../AGENTS.md) ("Reglas que no se negocian") y `src/licigt/consulta/esquemas.py` (`Fuente` y `RespuestaEstructurada`).

El [refinamiento W3](../docs/consulta/delegacion/W3_refinamiento_visual.md), aprobado el 19 de noviembre de 2026, compacta la presentación y añade un favicon local. Conserva el flujo, los datos documentales y las reglas de seguridad de este contrato. La [corrección de controles](../docs/consulta/delegacion/W3_correccion_controles.md), solicitada después por el usuario, sustituye los selectores nativos, elimina el pie y ordena la cabecera adaptable.

## Carácter de la página

- Herramienta de trabajo para un analista que revisa una licitación, no una página de presentación. Una sola página, una sola columna de lectura, sin imágenes ni ilustraciones en el contenido y sin degradados. Sin animaciones de entrada en resultados, fuentes o advertencias; la única entrada animada es la confirmación, acotada en "Lista de verificación".
- Favicon SVG local (`public/favicon.svg`, declarado en `index.html`): hoja blanca con esquina doblada y dos trazos sobre fondo grafito redondeado. Sin letras, marca institucional ni símbolo de aprobación; debe distinguirse a 16 px en las pestañas del navegador.
- La jerarquía la dan el texto, el espaciado y los bordes. El color refuerza el estado, pero nunca es la única señal.
- Todo el texto de la interfaz está en español y en registro formal ("usted"), como las respuestas del sistema.
- Componentes de shadcn/ui (Radix) y utilidades de Tailwind v4, con el tema de este archivo (ver "Base: Tailwind v4 y shadcn/ui" y "Tema"). Sin fuentes externas: la demo debe funcionar sin red hacia CDN.
- Ningún texto de la respuesta se interpreta como HTML ni como Markdown: `answer`, `cita`, `warnings` y `clarification_question` se pintan como texto plano (`AGENTS.md`: los fragmentos son datos no confiables).

## Zonas de la página

En orden del DOM, que es también el orden visual y el de lectura y tabulación:

1. **Aviso de modo**, banda angosta arriba de todo, solo cuando aplica:
   - con `VITE_MODO=ejemplos`: "Modo ejemplos: respuestas fijas, no se consulta la API.";
   - ya no hay aviso de modo demostración: la cabecera `X-LiciGT-Autenticacion` y el adaptador sin autenticación no existen; la web usa la sesión (ver "Sesión").
2. **Encabezado** (`header`):
   - nombre "LiciGT" y subtítulo "Consulta de licitaciones", con jerarquía compacta;
   - evento activo: `evento_id` en texto (por ejemplo, "Evento 222-IGSS-2023"), agrupado con el nombre;
   - con sesión iniciada, una segunda fila separada por un filete: usuario, empresa y rol en texto pequeño, junto al botón secundario "Cerrar sesión" (`DELETE /api/sesion`); datos y botón se apilan en móvil y se distribuyen a los extremos desde 40rem;
   - botón de tema de 44 px, sin rótulo visible, con icono de sol o luna; alterna Claro y Oscuro. Marca y tema comparten la primera fila; la sesión ocupa otra fila en móvil.
3. **Consulta** (`form` con `aria-label="Consulta"`, dentro de `main`, en una tarjeta):
   - título breve "Consulta"; en modo ejemplos, un selector "Ejemplo" con los cinco escenarios antes de la caja, junto al título cuando cabe, de 20rem desde 40rem y ancho completo en móvil; el ejemplo de comparación se rotula "Comparación" para que quepa a 320 px, y el resultado conserva el aviso de revisión humana;
   - caja de pregunta con etiqueta visible "Pregunta sobre el evento", contador "N/500" y botón "Consultar".
4. **Aviso fijo**: "La respuesta se basa en los documentos cargados del evento". Siempre presente, también antes de la primera consulta y durante la carga. Va justo encima del resultado, no se cierra ni se oculta y no cambia con el estado.
5. **Resultado** (`section[data-estado]`): cabecera de estado, banda de revisión humana si corresponde, texto de la respuesta, metadatos y avisos de cobertura.
6. **Fuentes** (`section` con `h2`): tarjetas de fuente, o el contraste lado a lado cuando hay conflicto.
7. **Lista de verificación** (`section` con `h2`): propuesta, guardado con confirmación y estados por ítem. Ver "Lista de verificación".
No hay pie institucional: se retira por solicitud del usuario. Los avisos documentales y de revisión permanecen en sus secciones.

El panel de documentos del evento (`section` con `h2` "Documentos del evento") va entre el encabezado y la consulta. Ver "Documentos del evento".

Antes de la primera consulta, la ayuda bajo el aviso fijo dice "La respuesta aparecerá aquí con sus fuentes". No sustituye el aviso ni cambia las explicaciones de abstención, cobertura o revisión.

## Sesión

Desde que toda ruta `/api/*` (salvo `/api/sesion`) exige cookie, la web comprueba la sesión antes de mostrar nada. Solo con `VITE_MODO=api`; en modo ejemplos no hay sesión.

- **Al cargar:** `GET /api/sesion`. Con 200 se muestra la aplicación; con 401, la pantalla de inicio de sesión; mientras tanto, "Comprobando la sesión…".
- **Pantalla de inicio de sesión** (`form` con `aria-label="Inicio de sesión"`, componente `InicioSesion`, en una tarjeta centrada): encabezado de la página, título "Iniciar sesión", mensaje de error en un `Alert` destructivo con `role="alert"` ("Usuario o contraseña no válidos", genérico, sin distinguir la causa), campos "Usuario" y "Contraseña" con `<label>` visible, y el botón "Iniciar sesión". Nada más. Ancho máximo 24 rem (`max-w-sm`), una columna, válida desde 320 px; usa solo las utilidades del tema (campos con `border-input`, foco con `--ring`), por lo que respeta el tema claro y oscuro y el contraste medido.
- **Cookie y contraseña:** la cookie es `HttpOnly`: la web ni la lee ni la guarda. La contraseña vive solo en el estado del formulario; no va a `localStorage`, `sessionStorage` ni a la URL.
- **401 a mitad de uso:** vuelve a la pantalla de inicio de sesión con el aviso "La sesión terminó. Inicie sesión de nuevo." en el `role="alert"`; la pregunta escrita sigue en el estado de `App` y reaparece al volver a entrar.
- **403 y rol `lector`:** el servidor responde 403 si un `lector` intenta proponer, guardar o cambiar estado; la lista muestra "Su rol no permite modificar la lista". Con `rol: lector` los botones "Proponer lista", "Guardar N ítems", los estados y "Guardar cambio" se muestran deshabilitados, con esa misma frase visible debajo de los botones (no solo en el atributo `disabled`).
- **Foco y detalles:** al entrar, el foco va a la caja de pregunta; al salir o al perder la sesión, al título "Iniciar sesión". Tras un intento fallido se vacía la contraseña. El error usa `--destructive` y `--destructive-fondo`. Con el lector, los estados van en un `fieldset disabled` descrito por la explicación, y con 403 no se ofrece "Recargar lista".
- **Cerrar sesión:** `DELETE /api/sesion`; vuelve al inicio de sesión y limpia la pregunta.

## Documentos del evento

Panel `section.documentos`, con `h2` "Documentos del evento", arriba de la consulta. Lo alimenta la ruta `GET /api/eventos/{evento_id}/documentos` (`DocumentoEvento`); `App` carga los documentos una sola vez y de ellos arma el mapa `doc_id` a tipo que usan las fuentes y la lista.

- **Línea de resumen**, junto al `h2` cuando cabe y debajo en móvil: "N documentos, sin información faltante" o "N documentos, M con información faltante" (en `text-estado-revision` si hay faltantes, con `data-faltantes`); "No hay documentos cargados para este evento" si no hay ninguno. Cuenta como faltante una página sin indexar, un estado distinto de "completo" o una advertencia.
- **Una tarjeta por documento** (`li` con `data-faltantes`; con borde de 2 px y fondo de revisión si le falta información), con:
  - título: etiqueta del tipo ("Bases", "Modificación", "Aclaración"), la versión oficial (si no existe, "Versión oficial no indicada" como texto secundario, sin ocupar el lugar del título) y "v" más la versión de ingesta;
  - el tipo y las versiones como `Badge` ("v1" y "Versión oficial no indicada" en la variante `suave`);
  - metadatos en `dl`: "Documento", con el `doc_id` completo en `font-mono` y `text-sm`, y "Páginas y estado"; esos dos rótulos redundantes son `sr-only`, mientras todos sus valores permanecen visibles;
  - páginas y estado: "35 páginas, todas indexadas; estado: completo" o "4 páginas, 1 sin indexar (p. 4); estado: requiere revisión";
  - si hay advertencias del documento, el rótulo "Falta información" y la lista de esas advertencias. Las páginas sin indexar y el estado no se repiten ahí: ya están en la línea anterior.
- **Carga:** "Cargando documentos…" (`aria-busy`). **Error:** "No se pudieron cargar los documentos." y el motivo, en un `Alert` destructivo con `role="alert"`; la consulta sigue disponible y las citas muestran solo el hash.
- **Modo ejemplos:** documentos fijos del 222.
- **Densidad:** cabecera y metadatos agrupados dentro de cada tarjeta; metadatos en dos columnas desde un ancho de tarjeta de 28rem (`@md:`). Identificadores completos y advertencias permanecen visibles. No se pliegan documentos ni se truncan datos para reducir altura.

## Rejilla y ancho

- Contenedor de lectura (`mx-auto max-w-lectura px-4 sm:px-6`, constante `CONTENEDOR` de `App.tsx`): ancho completo hasta 60rem, centrado, con relleno lateral de 16 px y de 24 px desde 40rem. Lo comparten el aviso de ejemplos, el encabezado y `main`.
- Ancho mínimo soportado: 320 px CSS sin desplazamiento horizontal, también con zoom al 200 %. `chunk_id`, `doc_id` y URL cortan con `overflow-wrap: anywhere`.
- Puntos de corte, de móvil hacia arriba:
  - base (320 px): todo apilado; el contraste de fuentes en conflicto va una debajo de otra;
  - `40rem` (640 px): contraste en dos columnas iguales;
  - los metadatos de documentos, fuentes e ítems no siguen la ventana sino el ancho de la tarjeta (consulta de contenedor `@container` con `@md:grid-cols-2`, 28rem): en la lista de fuentes van en dos columnas y dentro de cada columna del contraste, que es angosta, en una;
  - `64rem` (1024 px): solo aumenta el aire vertical (`--espacio-8` entre zonas). No se añade barra lateral.
- Las zonas se separan con `gap-6` (móvil) y `lg:gap-8` (escritorio). Dentro de un panel, `gap-4`.
- Las tarjetas comparten superficie, radio, espaciado y alineación de cabecera, contenido y acciones; sus variantes de revisión conservan los bordes y fondos de estado. Una tarjeta informativa no cambia al pasar el puntero como si fuera un botón.

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
- El atributo `data-estado` del panel es el único gancho de estilo: utilidades `data-[estado=revision]:border-estado-revision` en el panel y `group-data-[estado=revision]/resultado:bg-estado-revision-fondo` en la cabecera (constantes `PANEL` y `CABECERA` de `Resultado.tsx`). Sin clases por color.
- En modo de alto contraste del sistema (`forced-colors: active`) se pierden los fondos, pero quedan el texto, el ícono y el estilo del borde.

### Panel de respuesta

- Cabecera: ícono, rótulo "Respuesta".
- Texto de `answer` tal cual, con `white-space: pre-line` para conservar saltos de línea. Tamaño `--texto-lg`.
- **Datos literales:** las fechas, horas, montos y plazos salen literales de los documentos (por ejemplo, "06 de octubre de 2023, a las 11:00 horas"). La web no reformatea, no abrevia, no traduce a formato numérico ni resalta partes de `answer` por su cuenta. No parsea `answer`.
- Metadatos en una línea (`dl` en línea, separado del texto por un filete superior): "Evento: 222-IGSS-2023", "Herramienta: Búsqueda en documentos", "Cobertura: parcial" o "Cobertura: sin faltantes detectados".
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
- Con cero fuentes el motivo es neutro: "El sistema marcó esta consulta para revisión humana; revise los documentos originales." Sin ambigüedad ni vigencia.
- El rótulo en negrita "Requiere revisión humana." va en la banda solo cuando el estado mostrado es otro (abstención, aclaración); en el estado de revisión ya está en el `h2` y no se repite.
- **Banda de revisión**, arriba del texto, a todo el ancho del panel, con fondo `--estado-revision-fondo`, borde inferior sólido y el texto: "Las fuentes difieren o un dato crítico es ambiguo. El sistema no decide cuál está vigente; revise los documentos originales."
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

- **Vacía:** aviso fijo y una línea de ayuda en el lugar del resultado: "La respuesta aparecerá aquí con sus fuentes". Sin ejemplos de marketing ni ilustraciones.
- **Cargando:** el botón cambia a "Consultando…" y queda deshabilitado; el resultado anterior se retira; `section.resultado` lleva `aria-busy="true"` y el área de estado anuncia "Consultando. Puede tardar unos segundos." Sin indicadores giratorios que distraigan; si se usa uno, respeta `prefers-reduced-motion`.
- **Error de conexión o HTTP** (la API no responde, 422 o 500): `Alert` destructivo con borde sólido `--destructive`, rótulo "No se pudo completar la consulta" y el código o motivo corto ("La API no respondió", "La pregunta no es válida (422)"). No se presenta como abstención, porque no lo es. Una falla de herramienta o del LLM llega como abstención desde la API y se muestra como abstención.

## Avisos de cobertura y advertencias

- Zona de avisos dentro del panel de resultado (se oculta con `empty:hidden` si no hay nada), debajo de los metadatos y antes de las fuentes. Nunca colapsada, nunca dentro de un acordeón ni de un tooltip.
- Con `coverage_status = "parcial"`, primero un aviso destacado con ícono de documento incompleto (rectángulo con esquina doblada y línea discontinua), borde izquierdo de 4 px en `--estado-revision` y el texto: "Cobertura parcial: hay páginas o documentos del evento que no están indexados. La respuesta puede estar incompleta."
- Con `coverage_status = "sin_faltantes_detectados"`, solo el metadato "Cobertura: sin faltantes detectados" y, al lado, "(no certifica que el expediente esté completo)" (`Contratos.md`, "Rol 3 hacia el usuario").
- Cada elemento de `warnings` es un ítem de una lista (`ul`). Formato: rótulo legible y, debajo, el texto original tal cual en `font-mono` y `text-sm`, con un filete izquierdo decorativo, para que el analista pueda reportarlo.
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

Una `article` (`Card asChild`) por cada elemento de `sources`, en el orden recibido, numeradas "[1]", "[2]"… La numeración solo ordena la lista; la web no afirma qué frase de `answer` respalda cada fuente.

Contenido, en este orden:

- **Título** (`h3`): "[n] " más el tipo del documento y el `doc_id` ("[1] Bases · 03791a…"), en `text-base` y peso 600. Regla del tipo antes del hash: ver "Tipo del documento".
- **Metadatos** (agrupados con el título en una cabecera; `dl` en `text-sm`, rótulo en `text-muted-foreground` junto al valor en peso 600 cuando cabe, con salto de línea si hace falta; dos columnas si la tarjeta mide 28rem o más):
  - "Página": "p. 8 del PDF" si `page_end` es nulo o igual a `page`; "pp. 16–17 del PDF" si es un rango. Si la fuente trae `printed_page` (opcional en el backend: el número impreso en la hoja), se agrega "(impresa M)": "p. 8 del PDF (impresa 6)". La página del PDF manda siempre: es la que abre el enlace. Lo arma `textoPagina()` de `Fuentes.tsx`, que también usa el ítem de la lista;
  - "Versión de ingesta": "v" más `version_ingesta` (por ejemplo, "v1");
  - "Versión oficial": el texto de `version_oficial` o "No indicada" si es nulo;
  - "Fragmento": `chunk_id` en `font-mono` y `text-sm`, seleccionable.
- **Cita literal:** `blockquote` (clases de `CLASE_CITA` en `Fuentes.tsx`) con borde izquierdo de 3 px en `border-input`, fondo `bg-muted`, texto de 16 px sin atenuar (destaca contra los metadatos en `text-sm`), `lang="es"`, texto tal cual (sin recortar más allá de lo que trae el campo, sin reformatear fechas ni mayúsculas). Única excepción de pantalla: una cita de tabla llega como `título | texto` y la barra se lee como ": " (o un espacio tras un punto), igual en la tarjeta y en la lista; lo guardado no cambia.
- **Accesos al original**, separados de la cita por un filete superior: dos enlaces distintos, con rótulos que no se confunden:
  - "Ver copia archivada, p. N del PDF" (solo con la API, nunca en modo ejemplos): copia que sirve el sistema, `/api/eventos/{evento}/documentos/{doc_id}/original#page=N`, con `target="_blank"` y `rel="noopener"`. El `doc_id` y la página salen de la fuente (el `doc_id` se codifica en la ruta), nunca de texto del usuario. El servidor solo sirve documentos de la empresa de la sesión y responde 404 en cualquier otro caso;
  - "Publicación en igssgt.org": si `source` empieza con `https://`, enlace a la publicación externa, sin número de página y sin modificar la URL (no se añade `#page=`); `target="_blank"` y `rel="noopener noreferrer"`. Ambos llevan la indicación accesible "abre en una pestaña nueva";
  - si `source` no es https: el texto "Publicación externa no disponible" y el `doc_id`, sin enlace.
  - Estilo del primero: `font-semibold`, color `text-primary`, en `text-sm` como el segundo; los dos con `py-1` para el objetivo de 24 px.

### Tipo del documento

Cada vez que la web nombra un documento, el tipo va antes del hash: "Bases · 03791a…" o "Modificación · d41480…". Aplica al título de la tarjeta de fuente, a la cabecera de cada columna del conflicto (su nombre accesible incluye el tipo) y al origen de cada ítem de la lista. Si el mapa no tiene el documento (modo ejemplos o falla de carga), se muestra solo el hash.

La versión de ingesta y la oficial se rotulan por separado siempre, porque el anteproyecto pide no confundir la carga con la modificación oficial.

### Contradicciones: contraste lado a lado

Se activa cuando `needs_human_review = true` y las fuentes vienen de dos o más `doc_id` distintos.

- Encima de las columnas, el título "Fuentes en conflicto" y la frase fija: "El sistema no decide cuál está vigente."
- Una columna por `doc_id`, en el orden en que aparece por primera vez en `sources`. Cada columna es una `section` (`Card asChild`) con borde de 2 px en `border-input` y fondo `bg-background`, para que se lea como un contenedor de sus tarjetas; de cabecera, el documento y su versión oficial ("Versión oficial: Modificación 1" o "No indicada"), separados por un filete, y debajo sus tarjetas de fuente completas.
- Columnas de igual ancho, mismo estilo, mismo peso visual. Prohibido: rotular una como "vigente", "actual", "nueva", "anterior" o "corregida"; ordenarlas por fecha; atenuar una; marcar una con el color de respuesta.
- En móvil las columnas se apilan; cada una conserva su cabecera para que no se pierda de qué documento es cada cita.
- Más de dos documentos: tantas columnas como quepan con un mínimo de 18rem; si no caben, se apilan.

## Lista de verificación

Implementada en F6d sobre `PropuestaLista`, `ItemLista` y las rutas de proponer, guardar y cambiar estado:

- **Posición:** `section` después de las fuentes, con título `h2` "Lista de verificación" y acciones "Proponer lista" y "Guardar N ítems" agrupadas en la cabecera; en móvil se apilan sin cambiar el orden de lectura.
- **Aviso fijo de la lista** (`Alert variant="neutro"` con `IconoInfo`, como el aviso fijo de la consulta), siempre visible arriba de la lista: "Los estados de la lista no certifican cumplimiento." (`DESIGN.md`, "Interfaz de usuario").
- **Agrupada:** los ítems se agrupan por tipo, primero "Requisitos (N)" y luego "Fechas (N)", cada grupo con un `h3` y un filete inferior; dentro de cada grupo se respeta el orden recibido. Un grupo sin ítems no se muestra. La agrupación es solo de pantalla: `lista.ts` no cambia.
- **Estados del ítem**, con texto e ícono, no solo color:
  - "Pendiente": círculo vacío;
  - "Preparado": círculo lleno a la mitad;
  - "Revisado": círculo con marca de verificación.
- Las opciones de estado mantienen borde de 2 px y peso 600 tanto activas como inactivas: la selección cambia color, fondo y radio, sin desplazar el contenido.
- **Cada ítem** muestra categoría, carácter ("Fundamental", "No fundamental", "No indicado"), la cita, el documento, la página y las dos versiones, con la misma tarjeta de fuente reducida. Detalle:
  - la cita del ítem (`blockquote` con `CLASE_CITA`) es la de su fuente (`fuentes[0].cita`), con el mismo tratamiento de ` | ` que la tarjeta de fuente; en los ítems de fecha, la etiqueta de la actividad ("Recepción de ofertas") va fuera de la cita, como `Badge variant="suave"` junto a los rótulos;
  - el origen se organiza en un `dl` con "Documento" (tipo y hash completo, "Bases · 03791a…"), "Página" con el mismo texto que la tarjeta de fuente ("p. 16 del PDF", con "(impresa M)" si llega), "Versión de ingesta" y "Versión oficial". Dos columnas desde 28rem de ancho de tarjeta. Los ítems con revisión pendiente llevan la banda de revisión con su motivo, y los ítems en conflicto aparecen los dos, sin elegir.
- **Cambios locales:** marcar un ítem solo cambia el estado en pantalla y añade, al pie del ítem y tras un filete, el rótulo "Sin guardar" (`Badge variant="aviso"`), el cambio ("Pendiente a Preparado") y los botones "Guardar cambio" y "Descartar". Nada se guarda al marcar.
- **Confirmación explícita:**
  - un botón aparte, "Guardar cambios (N)" o "Guardar N ítems", abre un `dialog` modal nativo (`Confirmacion.tsx`: tarjeta con borde de 2 px en `border-foreground`, `shadow-dialogo`, velo `backdrop:bg-velo`, centrado con `m-auto` porque la preflight de Tailwind quita el margen, y `open:grid` para no pisar el `display: none` del diálogo cerrado) con el resumen de lo que se va a guardar, una línea por ítem ("Requisito X: Pendiente a Preparado");
  - el modal tiene "Confirmar y guardar" y "Cancelar"; el foco entra en el título del modal, queda atrapado dentro y vuelve al botón de origen al cerrar; `Escape` cancela;
  - al abrir, el diálogo se desplaza de 4 px a 0 durante 160 ms (`ease-out`), sin cambiar la opacidad ni retrasar su disponibilidad o el foco. Es la única excepción a la ausencia de animaciones de entrada y se anula con `prefers-reduced-motion: reduce`;
  - sin confirmación no hay petición de escritura.
- **Conflicto (409):** mensaje "Otro usuario cambió este ítem. Recargue la lista antes de guardar." El cambio local no se aplica.
- **Propuesta:** botón "Proponer lista"; los ítems propuestos llevan una casilla "Incluir" (`Checkbox` de Radix dentro de una `Label` de 44 px) para descartar antes de guardar, enlazada con `aria-describedby` a la cita de su ítem para que se anuncie con él, y el rótulo "No guardado". La cita no se edita.
- **Lista vacía:** "Proponga una lista para comenzar. Solo se guarda al confirmar". El aviso de no certificación sigue visible.

## Base: Tailwind v4 y shadcn/ui

Desde W2 ([encargo](../docs/consulta/delegacion/W2_rediseno_con_shadcn.md)) la interfaz parte de un estándar: shadcn/ui sobre primitivas de Radix y Tailwind CSS v4. Cambia la implementación; las reglas de contenido de este archivo (estados, avisos, fuentes, contraste lado a lado, lista, sesión, accesibilidad) siguen iguales.

- **Paquetes:** `tailwindcss` y `@tailwindcss/vite` 4.3.5; `shadcn` 4.23.0 (CLI y `shadcn/tailwind.css`); `tw-animate-css` 1.4.0; `radix-ui` 1.8.1; `class-variance-authority` 0.7.1; `cn` 0.5.2 (sustituye a `clsx` más `tailwind-merge`); `lucide-react` 1.75.0 (solo los íconos internos de shadcn). Se instalan con `pnpm`; los componentes se añaden con `pnpm dlx shadcn@latest add <nombre>`.
- **Configuración:**
  - `components.json`: estilo `radix-nova`, base Radix (no Base UI, que es el valor por defecto de la CLI desde julio de 2026), sin RTL, CSS en `src/estilos/tema.css`;
  - alias `@/componentes`, `@/componentes/ui`, `@/utilidades` y `@/hooks`. No se usa `src/lib`: el `.gitignore` de la raíz ignora `lib/`;
  - el alias `@` apunta a `src` en `tsconfig.json`, `tsconfig.app.json` y `vite.config.ts`.
- **Sin fuentes externas:** se quitó la fuente Geist que trae el preset; la pila es la del sistema (`--font-sans`) y la demo sigue funcionando sin red.
- **Archivo de estilo:** solo `src/estilos/tema.css`: entrada de Tailwind, variante `dark`, tokens en claro y oscuro, mapeo a utilidades (`@theme`) y capa base con las reglas de interacción. El puente de la fase A (`variables.css` y `base.css`, con el CSS por bloques) se borró en la fase B: los componentes usan solo utilidades.
- **Componentes de `src/componentes/ui/`:** son código propio, no una dependencia. Ya vienen ajustados a este contrato (ver "Reglas de interacción"); si se regenera alguno con la CLI, hay que volver a aplicar esos ajustes. Uno de ellos: el estilo `radix-nova` trae variantes `data-checked:` y `data-horizontal:`, pero `radix-ui` 1.8.1 marca el estado con `data-state="checked"` y la orientación con `data-orientation`; `checkbox`, `radio-group` y `separator` usan `data-[state=checked]:` y `data-[orientation=…]:` (sin eso, la casilla marcada no se pintaba).

## Tema

El tema vive en `src/estilos/tema.css`. El modo claro va en `:root`. El oscuro sigue al sistema salvo que el usuario fije el tema con `data-tema` en `html`, y se repite en dos bloques:

- `@media (prefers-color-scheme: dark) { :root:not([data-tema="claro"]) { … } }`;
- `:root[data-tema="oscuro"] { … }`.

La variante `dark:` de Tailwind se redefine con `@custom-variant` para seguir esa misma regla; no se usa la clase `.dark` de shadcn. El botón de tema alterna Claro y Oscuro con iconos de sol y luna. Sin una preferencia guardada, el modo inicial sigue al sistema y el icono refleja el aspecto efectivo. Su nombre accesible y título anuncian el estado actual y la siguiente acción; no lleva el texto visible "Tema". Guarda la elección en `localStorage` dentro de `try`/`catch`; si falla, mantiene la elección durante la sesión. Al pulsar fija el modo contrario y lo conserva para futuras visitas. No ofrece una opción Sistema. `index.html` aplica el tema guardado antes de pintar. Razón del control: el proyector de la demo puede verse mejor en claro aunque el equipo esté en oscuro.

### Color

Cada token del contrato anterior pasa a una variable de shadcn (o a una propia cuando shadcn no la tiene) y a una utilidad de Tailwind. Los valores no cambian.

| Token anterior | Variable de tema | Utilidad | Claro | Oscuro | Uso |
|---|---|---|---|---|---|
| `--color-fondo` | `--background` | `bg-background` | `#f7f7f5` | `#16181b` | fondo de la página |
| `--color-superficie` | `--card`, `--popover` | `bg-card` | `#ffffff` | `#1e2125` | paneles, tarjetas y controles |
| `--color-superficie-2` | `--muted`, `--secondary`, `--accent` | `bg-muted` | `#efefec` | `#262a2f` | cita, aviso fijo, etiquetas |
| `--color-texto` | `--foreground` (y sus `-foreground`) | `text-foreground` | `#1c1f23` | `#e6e7e9` | texto principal |
| `--color-texto-secundario` | `--muted-foreground` | `text-muted-foreground` | `#4a5059` | `#a9afb8` | metadatos, ayudas |
| `--color-borde` | `--border` | `border-border` | `#c9ccd1` | `#3d434b` | separadores y borde de tarjeta, decorativos |
| `--color-borde-control` | `--input` | `border-input` | `#7d838c` | `#767d87` | bordes de caja, selector, casilla y cita (3:1 o más) |
| `--color-acento` | `--primary` | `bg-primary`, `text-primary` | `#1d4f91` | `#8fb6ec` | botón primario, enlaces |
| `--color-acento-contraste` | `--primary-foreground` | `text-primary-foreground` | `#ffffff` | `#16181b` | texto sobre el botón primario |
| `--color-foco` | `--ring` | `outline-ring` | `#1d4f91` | `#8fb6ec` | anillo de foco |
| `--color-error` | `--destructive` | `text-destructive` | `#a3242b` | `#f19a9f` | error de conexión |
| `--color-error-fondo` | `--destructive-fondo` | `bg-destructive-fondo` | `#fbeeee` | `#2e1c1e` | fondo del error |
| `--estado-respuesta` | `--estado-respuesta` | `text-estado-respuesta` | `#1e6b45` | `#7fcfa3` | rótulo, ícono y borde |
| `--estado-respuesta-fondo` | `--estado-respuesta-fondo` | `bg-estado-respuesta-fondo` | `#edf6f0` | `#17291f` | cabecera del panel |
| `--estado-abstencion` | `--estado-abstencion` | `text-estado-abstencion` | `#4a5059` | `#b4bac3` | rótulo, ícono y borde |
| `--estado-abstencion-fondo` | `--estado-abstencion-fondo` | `bg-estado-abstencion-fondo` | `#f1f2f4` | `#23262b` | cabecera del panel |
| `--estado-revision` | `--estado-revision` | `text-estado-revision` | `#8a4600` | `#f2b46b` | rótulo, ícono, borde, aviso de cobertura |
| `--estado-revision-fondo` | `--estado-revision-fondo` | `bg-estado-revision-fondo` | `#fdf1e1` | `#2f2214` | banda de revisión |
| `--estado-aclaracion` | `--estado-aclaracion` | `text-estado-aclaracion` | `#4338a3` | `#b3abf2` | rótulo, ícono y borde |
| `--estado-aclaracion-fondo` | `--estado-aclaracion-fondo` | `bg-estado-aclaracion-fondo` | `#efeefb` | `#22203a` | cabecera del panel |
| (nuevo) | `--primary-hover` | `bg-primary-hover` | `#173f74` | `#adc9f1` | botón primario con el puntero encima |
| (nuevo) | `--primary-active` | `bg-primary-active` | `#12315a` | `#c8dbf6` | botón primario pulsado |
| (nuevo) | `--muted-hover` | `bg-muted-hover` | `#e7e7e3` | `#2c3036` | botón secundario, selector y casilla con el puntero encima |
| (nuevo) | `--muted-active` | `bg-muted-active` | `#d8d8d3` | `#353a41` | botón secundario pulsado |

- `--accent` de shadcn es un fondo de realce neutro (igual a `--muted`), no nuestro acento azul: el azul es `--primary`.
- Los colores de `hover` y `active` son hex explícitos, no opacidades (`bg-primary/80`) ni `color-mix`, para que su contraste se pueda medir.
- `color-scheme: light` en `:root` y `color-scheme: dark` en el modo oscuro, para que los controles nativos sigan el tema. `body` usa `bg-background text-foreground`.
- Ningún componente usa un color literal ni una utilidad de la paleta de Tailwind (`bg-blue-600`, `text-gray-500`): todo sale de estas variables.

### Contraste medido (WCAG 2.1, fórmula de luminancia relativa)

Calculado sobre los valores de la tabla; la compuerta lo vuelve a comprobar sobre la página corriendo.

| Par | Claro | Oscuro |
|---|---|---|
| texto sobre fondo | 15.4 | 14.4 |
| texto sobre banda de revisión | 14.8 | 12.5 |
| texto secundario sobre superficie | 8.1 | 7.3 |
| texto secundario sobre superficie 2 | 7.1 | 6.5 |
| acento sobre superficie | 8.1 | 7.8 |
| texto del botón primario sobre acento | 8.1 | 8.5 |
| texto del botón primario sobre `--primary-hover` | 10.5 | 10.5 |
| texto del botón primario sobre `--primary-active` | 13.0 | 12.6 |
| texto sobre `--muted-hover` | 13.3 | 10.7 |
| texto sobre `--muted-active` | 11.6 | 9.3 |
| estado respuesta sobre su fondo | 5.9 | 8.3 |
| estado abstención sobre su fondo | 7.3 | 7.8 |
| estado revisión sobre su fondo | 6.4 | 8.5 |
| estado aclaración sobre su fondo | 7.8 | 7.5 |
| error sobre su fondo | 6.5 | 7.6 |
| borde de control sobre superficie | 3.8 | 3.9 |
| borde de control sobre `--muted-hover` | 3.1 | 3.2 |
| foco sobre fondo | 7.6 | 8.5 |
| foco sobre superficie 2 | 7.1 | 6.9 |

Todo el texto supera 4.5:1 (AA) y los bordes de controles y el foco superan 3:1 (contraste de elementos no textuales). `--border` (1.6:1) solo se usa en separadores y bordes decorativos, nunca como único límite de un control. Los controles deshabilitados bajan a opacidad 0.6; WCAG los exime del mínimo y el texto que explica por qué están deshabilitados va aparte, con contraste completo.

### Tipografía

La escala de Tailwind coincide con la del contrato, así que no se redefine: solo se fijan las familias y las interlineas.

| Token anterior | Utilidad | Valor | Uso |
|---|---|---|---|
| `--fuente-texto` | `font-sans` (`--font-sans`) | `system-ui, -apple-system, "Segoe UI", Roboto, "Noto Sans", "Helvetica Neue", Arial, sans-serif` | todo el texto |
| `--fuente-mono` | `font-mono` (`--font-mono`) | `ui-monospace, "Cascadia Code", "SFMono-Regular", Consolas, "Liberation Mono", monospace` | `chunk_id`, códigos de aviso |
| `--texto-xs` | `text-xs` | `0.75rem` (12 px) | no se usa para contenido; solo contadores |
| `--texto-sm` | `text-sm` | `0.875rem` (14 px) | metadatos, códigos, ayudas, etiquetas |
| `--texto-base` | `text-base` | `1rem` (16 px) | cuerpo, citas, controles, títulos de tarjeta (`h3`) |
| `--texto-lg` | `text-lg` | `1.125rem` (18 px) | texto de `answer` y de la aclaración |
| `--texto-xl` | `text-xl` | `1.25rem` (20 px) | `h2`: rótulo del estado y títulos de sección |
| `--texto-2xl` | `text-2xl` | `1.5rem` (24 px) | `h1`: nombre "LiciGT" |
| `--interlinea-texto` | `leading-texto` | `1.55` | cuerpo y citas |
| `--interlinea-titulo` | `leading-titulo` | `1.25` | títulos, botones, etiquetas |
| `--peso-normal` / `--peso-fuerte` | `font-normal` / `font-semibold` | `400` / `600` | sin otros pesos: no se usa `font-medium` ni `font-bold` |

- Tamaños en `rem`, nunca en px fijos, para respetar el tamaño de letra del navegador. Los controles no bajan a `text-sm` en escritorio (shadcn lo hace con `md:text-sm`; aquí se quitó).
- La capa base da tamaño y peso a `h1` (2xl), `h2` (xl) y `h3` (base), porque la preflight de Tailwind los deja sin estilo.
- Longitud de línea de `answer` y de las citas: máximo `70ch` (`max-w-[70ch]`).
- Números de página y versiones con `tabular-nums` (lo pone `body`).

### Espaciado, bordes y medidas

La escala de espacio de Tailwind (`--spacing: 0.25rem`) coincide con la del contrato: `--espacio-N` es la utilidad `p-N`, `gap-N`, `m-N`.

| Token anterior | Utilidad | Valor |
|---|---|---|
| `--espacio-1` | `*-1` | `0.25rem` (4 px) |
| `--espacio-2` | `*-2` | `0.5rem` (8 px) |
| `--espacio-3` | `*-3` | `0.75rem` (12 px) |
| `--espacio-4` | `*-4` | `1rem` (16 px) |
| `--espacio-6` | `*-6` | `1.5rem` (24 px) |
| `--espacio-8` | `*-8` | `2rem` (32 px) |
| `--espacio-12` | `*-12` | `3rem` (48 px) |
| `--radio` | `rounded-lg` (`--radius`) | `4px` (controles, citas, avisos, etiquetas) |
| `--radio-panel` | `rounded-xl` (`--radius-panel`) | `6px` (paneles y tarjetas) |
| `--borde-fino` | `border` | `1px` |
| `--borde-estado` | `border-2` | `2px` (borde completo del panel) |
| `--borde-acento` | `border-l-4` | `4px` (borde izquierdo de respuesta, aviso fijo y cobertura parcial) |
| (cita) | `border-l-3` | `3px` |
| `--ancho-lectura` | `max-w-lectura` | `60rem` |
| `--alto-control` | `min-h-11` | `2.75rem` (44 px) |
| `--sombra-dialogo` | `shadow-dialogo` | `0 8px 24px rgb(0 0 0 / 0.25)` |
| (velo del modal) | `backdrop:bg-velo` (`--color-velo`) | `rgb(0 0 0 / 0.55)`, igual en claro y oscuro |

- Puntos de corte: `sm:` es `40rem` y `lg:` es `64rem`, los dos de "Rejilla y ancho". No se usan `md:`, `xl:` ni `2xl:`. La consulta de contenedor `@md:` (28rem) organiza los metadatos de documentos, fuentes e ítems.
- Sin sombras salvo `shadow-dialogo`, para el modal de confirmación. Las tarjetas de shadcn traían `ring-1`; aquí llevan borde.
- Transiciones de controles: color, fondo y color del borde (`transition-colors`), de 150 ms. Los botones no se desplazan al pulsarlos. Solo el diálogo de confirmación permite una animación de entrada de 160 ms y 4 px; no se animan resultados ni advertencias. La capa base anula transiciones y animaciones con `prefers-reduced-motion: reduce`.

## Reglas de interacción

Viven en la capa base de `tema.css` y en los componentes de `src/componentes/ui/`. Valen para todo lo que se pulsa, sea componente de shadcn o elemento nativo.

| Estado | Regla |
|---|---|
| Cursor | Mano (`pointer`) en botones habilitados, `role="button"`, `role="radio"`, `role="checkbox"`, enlaces con `href`, `select`, `summary`, casillas y radios nativos y la `label` que los envuelve. Texto (`text`) en cajas de texto. `not-allowed` en `:disabled`, `aria-disabled="true"`, `data-disabled` y en la `label` de un control deshabilitado. |
| `hover` | Primario: fondo `--primary-hover`. Secundario (`outline`), fantasma, selector y casilla: fondo `--muted-hover`. Enlace: subrayado de 2 px. Solo si el control no está deshabilitado (`hover:not-disabled:`), y Tailwind lo limita a dispositivos con puntero (`@media (hover: hover)`). |
| `focus-visible` | Contorno sólido de 3 px en `--ring` con separación de 2 px, en todo control y enlace, por la capa base. Con `forced-colors: active`, el contorno usa `Highlight`. Ningún componente usa `outline-none` ni el anillo translúcido de shadcn (`ring-ring/50`, que no llega a 3:1). Los `h2` que reciben el foco por programa (`tabindex="-1"`) lo muestran igual con teclado. |
| `active` | Primario: fondo `--primary-active`. Secundario y fantasma: fondo `--muted-active`. Sin desplazamiento del control. |
| `disabled` | Opacidad 0.6 y cursor `not-allowed`, sin `pointer-events: none` (shadcn lo trae; se quitó para que el cursor se vea). El texto del botón no cambia ni desaparece; si la causa es el rol, la explicación va en texto visible debajo. |

- **Tamaño de objetivo:** botones, cajas, selectores y opciones de estado con alto mínimo de 44 px (`min-h-11`). Casillas y radios de 20 px (`size-5`) con zona de toque ampliada por `::after`, dentro de una `label` de 44 px.
- **Texto que no desborda:** los botones permiten partir la línea (sin `whitespace-nowrap`) y crecen en alto; `doc_id`, `chunk_id` y URL cortan con `wrap-anywhere`.
- **Selector de ejemplos:** `Select` de Radix, con etiqueta visible, disparador y opciones de altura mínima de 44 px. Menú en portal con superficie del tema, opción seleccionada marcada y foco visible. Ancho y alto limitados al espacio disponible; navegación con flechas, selección con Enter y cierre con Escape. El tema usa el botón con icono descrito arriba.
- **`Alert` sin `role` fijo:** el `Alert` de shadcn pone `role="alert"` siempre; aquí se quitó, porque el aviso fijo y el de cobertura no son alertas y no deben anunciarse cada vez. Quien lo use pone `role="alert"` solo en los errores que hoy lo llevan (inicio de sesión, documentos, aviso de la lista).

## Componentes: mapa a shadcn/ui

Componentes instalados en `src/componentes/ui/`: `button`, `input`, `textarea`, `label`, `native-select`, `checkbox`, `radio-group`, `card`, `badge`, `alert` y `separator`. No se instalan:

- `tooltip`: este contrato prohíbe que el estado o un aviso vivan solo en un tooltip, y nada lo necesita;
- `dialog`: la confirmación sigue siendo el `dialog` modal nativo (foco al título, atrapado, vuelta al botón de origen, `Escape` cancela), con el aspecto de una tarjeta.

Variantes propias, que sustituyen a las de shadcn que no se usan:

- `Button`: `default` (primario), `outline` (secundario), `ghost` y `link`; tamaños `default` (`px-6`), `sm` (`px-4`, mismo alto) e `icon`.
- `Badge`: `default` (rótulo), `aviso` ("Sin guardar", "Falta información") y `suave` (actividad, "No guardado", versiones).
- `Alert`: `default`, `neutro` (avisos fijos), `revision` (cobertura parcial y conflicto 409) y `destructive` (errores).
- `Card`: acepta `asChild` para ser el `article` de una fuente, la `section` de una columna o del resultado, el `form` de la consulta o del inicio de sesión y el `li` de un documento o de un ítem.

Estado tras la fase B: todo componente usa esta tabla; los bloques CSS de la segunda columna ya no existen (se borraron con `base.css`).

| Componente nuestro | Bloque anterior | Implementación | Notas |
|---|---|---|---|
| Aviso de modo | `.aviso-modo` | utilidades (`bg-muted text-sm border-b`) | banda, no es un `Alert` |
| Encabezado | `.encabezado` | utilidades (`bg-card border-b`), `Button variant="outline" size="sm"` para "Cerrar sesión" | no es fijo al desplazar |
| Selector de tema (`Tema.tsx`) | `.tema` | `Button` con icono cambiante | dos estados, nombre accesible y persistencia en `localStorage` |
| Formulario de consulta | `.consulta` | `Card asChild` sobre `form` | agrupa ejemplo, pregunta, contador y botón |
| Selector de ejemplo | `.campo select` | `Label` + `Select` de Radix | solo en modo ejemplos; menú estilizado |
| Caja de pregunta | `.consulta textarea` | `Label` + `Textarea` (`rows={3}`, `maxLength={500}`) | contador en `text-xs`, con `aria-describedby` |
| Botón primario | `.boton` | `Button` | "Consultar", "Iniciar sesión", "Guardar…", "Confirmar y guardar" |
| Botón secundario | `.boton--secundario` | `Button variant="outline"` (`size="sm"` en la lista, el modal y el encabezado) | "Escribir la aclaración", "Proponer lista", "Cancelar", "Cerrar sesión" |
| Aviso fijo | `.aviso-fijo` | `Alert variant="neutro"` + `IconoInfo`, `text-sm font-semibold` | sin `role`; nunca se cierra |
| Panel de resultado | `.resultado[data-estado]` | `Card asChild` sobre `section` | `data-estado` sigue siendo el único gancho: `data-[estado=revision]:border-estado-revision`, etc.; cabecera con el fondo del estado por `group-data-[estado=…]/resultado:` |
| Rótulo de estado | `h2` + `IconoEstado` | `header` con utilidades (no `CardHeader`, cuyo relleno no encaja con la banda) | íconos propios de `Iconos.tsx` (las formas son parte del contrato), no de lucide |
| Banda de revisión | `.banda-revision` | utilidades (`bg-estado-revision-fondo border-b-2`) | a todo el ancho del panel; no es un `Alert`; la misma banda en el ítem de la lista |
| Metadatos | `.metadatos` (`dl`) | utilidades | se mantiene el `dl`; los dos puntos los pone `after:content-[':']` |
| Aviso de cobertura | `.aviso-cobertura` | `Alert variant="revision"` + `IconoCobertura` | sin `role` |
| Lista de `warnings` | `.avisos__lista` | utilidades | texto original en `font-mono text-sm` |
| Tarjeta de fuente | `.fuente` | `Card asChild` sobre `article`, `@container` | título en `h3` simple (no `CardTitle`, que es un `div`); cita con `CLASE_CITA` |
| Enlaces al original | `.fuente__origen a` | `a` nativo | los atributos no cambian; el rótulo agrega "del PDF" |
| Contraste lado a lado | `.contraste`, `.contraste__columna` | rejilla (`sm:grid-cols-[repeat(auto-fit,minmax(18rem,1fr))]`) + `Card asChild` sobre `section` | las dos columnas con la misma variante y el mismo peso |
| Error de consulta | `.error-consulta` | `Alert variant="destructive"` con su `h2` | la consulta sigue disponible |
| Inicio de sesión | `.sesion` | `Card asChild` sobre `form` + `Label` + `Input` + `Button`; error con `Alert variant="destructive" role="alert"` | ancho máximo 24 rem, centrado |
| Documentos del evento | `.documentos`, `.documento` | `Card asChild` sobre `li` por documento; `Badge` para tipo, versión y "Falta información" (`aviso`) | con faltantes: `border-2 border-estado-revision bg-estado-revision-fondo` |
| Grupos de la lista | (nuevo) | `h3` con filete inferior y el número de ítems | "Requisitos (N)" y "Fechas (N)" |
| Ítem de la lista | `.item-lista` | `Card asChild` sobre `li` | con revisión: borde de 2 px `estado-revision` |
| Rótulos del ítem | `.etiqueta` | `Badge` (`default`, `aviso`, `suave`) | "Sin guardar" es `aviso` |
| Casilla "Incluir" | `.incluir input` | `Label` + `Checkbox` | ver "Notas de Radix" debajo de la tabla |
| Estados del ítem | `.estados`, `.estados__opcion` | `fieldset` + `RadioGroup` + `RadioGroupItem`, cada opción en una `Label` de al menos 44 px, borde constante de 2 px y peso 600 | ícono de estado (`IconoItem`) y texto; la opción activa con `border-foreground bg-muted` (`data-activo`) |
| Avisos de la lista | `.lista__aviso` | `Alert variant="destructive"` o `"revision"` (conflicto 409), con `role="alert"` | |
| Confirmación | `dialog.confirmacion` | `dialog` nativo con clases de tarjeta (`bg-card border-2 rounded-xl shadow-dialogo backdrop:bg-velo`) + `Button` | sin `Dialog` de Radix |
| Separadores | borde del encabezado | bordes y filetes con utilidades (`border-b`, `border-t`) | `Separator` queda instalado pero sin uso: cada filete separa partes de un contenedor que ya existe |
| Pie | retirado | sin componente | corrección solicitada tras W3 |

Notas de Radix (aplicadas en la fase B):

- `Checkbox` y `RadioGroupItem` pintan un `<button>` con `role="checkbox"` o `role="radio"`, no un `<input>`. El `aria-describedby` hacia la cita se pone en el `Checkbox` y llega al botón. La prueba de `fuentes.test.ts` busca un `<button>` con `role="checkbox"` y ese mismo `aria-describedby` en la misma etiqueta, y que haya una sola casilla.
- Un `fieldset disabled` deshabilita los botones de Radix de forma nativa, pero Radix no se entera (no pone `data-disabled`). Con el rol `lector` se pasa también `disabled` al `RadioGroup` y al `Checkbox`; `sesion.test.ts` comprueba que los tres radios llevan `disabled`, que el grupo lleva `data-disabled` y que la casilla del lector va deshabilitada.
- `RadioGroup` usa foco itinerante: una sola parada de tabulación por grupo y flechas entre opciones, como un grupo de radios nativo. El grupo se nombra con `aria-labelledby` hacia la `legend` del `fieldset`.
- Una `label` que envuelve el `<button>` de Radix lo activa al pulsarla (el botón es un elemento etiquetable), así que toda la opción de 44 px es pulsable.

Clases y nombres:

- No quedan bloques CSS en español: cada componente usa utilidades de Tailwind sobre las variables del tema. Las combinaciones que se repiten viven en constantes del módulo que las usa (`CONTENEDOR` y `PRINCIPAL` en `App.tsx`, `PANEL` y `CABECERA` en `Resultado.tsx`, `CLASE_CITA` en `Fuentes.tsx`).
- El estado sigue en atributos (`data-estado`, `data-faltantes`, `data-revision`, `data-activo`, `aria-*`), nunca en clases por color.
- Texto solo para lectores de pantalla con `sr-only` (antes `.oculto-visual`).
- Se combinan clases con `cn` (paquete `cn`; `@/utilidades/cn` lo reexporta).

## Pruebas

Pruebas de la web: Vitest sobre la lógica pura (`estado`, `lista`, `cobertura`) y sobre el HTML de las fuentes, la lista, el panel y el resultado con `renderToStaticMarkup`. Las de render buscan atributos estables (`data-slot`, `data-variant`, `role`, `lang`, `aria-*`), no clases de Tailwind, salvo `font-mono` en el `doc_id`; el resto se valida con `tsc`, el build y la compuerta (`design-ui-finish-gate-reviewer`) contra este archivo, en vivo, en claro y oscuro, a 1366 y 320 px.

## Accesibilidad

Meta: WCAG 2.1 nivel AA.

- **Idioma y estructura:** `html lang="es"`; un `h1` ("LiciGT") en el encabezado; `h2` para el rótulo del estado, "Fuentes" y "Lista de verificación"; `h3` para cada tarjeta. Regiones: `header`, `main`; el formulario con `aria-label="Consulta"`.
- **Orden de lectura y teclado:** orden del DOM igual al visual. Tabulación: botón de tema, selector de ejemplo (si existe), caja de pregunta, "Consultar", botón de la aclaración (si existe), enlaces "Ver copia archivada" y "Publicación en igssgt.org" de cada fuente. Con sesión, después del botón de tema va "Cerrar sesión"; en la pantalla de inicio: "Usuario", "Contraseña" e "Iniciar sesión". Sin `tabindex` positivo. `Ctrl+Enter` o `Cmd+Enter` en la caja envía; `Enter` agrega una línea.
- **Foco visible:** `:focus-visible` con `outline: 3px solid var(--ring)` y `outline-offset: 2px` en todo control y enlace, desde la capa base de `tema.css` (ver "Reglas de interacción"). Nunca `outline: none` ni `outline-none` sin reemplazo.
- **Al llegar un resultado:** el foco pasa al `h2` del panel (`tabindex="-1"`), de modo que el lector anuncia el estado ("Requiere revisión humana") antes que el texto. Un `div role="status"` aparte anuncia "Consultando…" y luego "Resultado: " más el rótulo del estado. No se pone `aria-live` sobre todo el panel, para no leer la respuesta dos veces.
- **Lectores de pantalla:**
  - los íconos llevan `aria-hidden="true"`; el estado lo dice el texto;
  - la cita va en `blockquote` y su tarjeta es un `article` con `aria-labelledby` hacia su título;
  - el enlace al original incluye la página del PDF y "abre en una pestaña nueva" en su nombre accesible;
  - en el contraste, cada columna es una `section` con `aria-labelledby` hacia su cabecera de documento;
  - el contador de caracteres se asocia a la caja con `aria-describedby`.
- **Contraste:** ver la tabla medida. El estado nunca depende solo del color (texto, ícono y borde).
- **Tamaño de objetivo:** botones y selectores con alto mínimo de 44 px; enlaces con relleno vertical suficiente para 24 px.
- **Reflujo y zoom:** sin desplazamiento horizontal a 320 px ni al 200 % de zoom; textos largos cortan con `overflow-wrap: anywhere`.
- **Movimiento:** sin animaciones de entrada salvo el diálogo de confirmación (160 ms, desplazamiento máximo de 4 px, sin retrasar foco o interacción); todo efecto se anula con `prefers-reduced-motion: reduce`.
- **Alto contraste del sistema:** con `forced-colors: active`, los bordes de estado usan `CanvasText` y siguen visibles; el foco usa `Highlight`.

## Bocetos por estado

Los valores entre `<>` son marcadores: F6b los toma reales de `entregables/recuperacion/empresa_demo.zip`, sin inventarlos. Las fechas y páginas del 222 vienen de I3, pregunta 4.

### Respuesta

```text
+----------------------------------------------------------------------+
| Modo ejemplos: respuestas fijas, no se consulta la API.              |
+----------------------------------------------------------------------+
| LiciGT  Evento 222-IGSS-2023              [icono del tema] |
| Consulta de licitaciones                                             |
+----------------------------------------------------------------------+
| Consulta               Ejemplo: [ Respondible con fuentes       v ] |
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
| | Página: pp. 26–27 del PDF    Versión de ingesta: v<n>            | |
| | Versión oficial: <texto>     Fragmento: <chunk_id>               | |
| | | «<cita literal del fragmento>»                                 | |
| | Ver copia archivada, p. 26 del PDF · Publicación en igssgt.org   | |
| +------------------------------------------------------------------+ |
+----------------------------------------------------------------------+
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
| | Ver copia archivada · Publicación | | Ver copia archivada · Publicación |  |
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

### Lista de verificación (referencia)

```text
| Lista de verificación                 [Proponer lista] [Guardar 0 ítems] |
| | (i) Los estados de la lista no certifican cumplimiento.            |
|                                                                      |
| Requisitos (2)                                      <h3>             |
| -------------------------------------------------------------------- |
| +------------------------------------------------------------------+ |
| | [Requisito] [Técnica] [Fundamental]                              | |
| | | <cita>                                                         | |
| | Documento: Bases · <doc_id>       Página: p. 16 del PDF          | |
| | Versión de ingesta: v<n>          Versión oficial: <texto>       | |
| | Estado de «Requisito técnica»                                    | |
| | [(o) ( ) Pendiente] [( ) (/) Preparado] [( ) (v) Revisado]       | |
| | ---------------------------------------------------------------- | |
| | [Sin guardar] Pendiente a Preparado [Guardar cambio] [Descartar] | |
| +------------------------------------------------------------------+ |
| Fechas (2)                                          <h3>             |
| +==================================================================+ |
| |## Requiere revisión: <motivo> ##################################| |
| | [Fecha] [No indicado] [Recepción de ofertas]                     | |
| | | 31 de julio de 2023                                            | |
| | ...                                                              | |
| +==================================================================+ |
|                                                                      |
|   +-- Guardar el cambio de estado --------------------------------+  |
|   | Nada se guarda hasta que confirme.                            |  |
|   | | <ítem>: Pendiente a Preparado                               |  |
|   |                          [ Cancelar ] [ Confirmar y guardar ] |  |
|   +---------------------------------------------------------------+  |
```

`( )`, `(/)` y `(v)` son los íconos de pendiente, preparado y revisado; `(o)` es el radio de Radix marcado. Todas las opciones llevan borde de 2 px y texto en peso 600; la activa refuerza color y fondo. El modal es el `dialog` nativo.

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
