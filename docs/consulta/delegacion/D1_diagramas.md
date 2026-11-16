# Encargo D1: diagramas de arquitectura en HTML

Para Codex u OpenCode. Rama `rol/consulta`. Lee primero [`AGENTS.md`](../../../AGENTS.md), [`DESIGN.md`](../../../DESIGN.md), [`Contratos.md`](../Contratos.md) y [`JEV.md`](../JEV.md). El gestor revisará el resultado contra este encargo y contra el código; no commitees.

## Objetivo

Dos diagramas profesionales, escritos como HTML autocontenido y exportados a PNG, que reemplacen al diagrama actual `docs/arquitectura/arquitectura_igss.svg`:

1. **General** (`arquitectura_general`): flujo de ingesta y flujo de consulta en una sola figura.
2. **Flujo de consulta** (`flujo_consulta`): el detalle del rol 3, con cada compuerta y cada salida de excepción.

**Por qué:** la sección 6 de las instrucciones del curso exige que el diagrama muestre entradas, salidas, estado compartido, herramientas, índices, compuertas de decisión, puntos de validación, tratamiento de excepciones y control de acceso. Pesa 15 puntos de la rúbrica. El diagrama actual no muestra el estado compartido, ni los guardrails de salida, ni JEV, y usa nombres viejos.

**Fuera de alcance:** los otros siete diagramas de la versión anterior (ingesta detallada, recuperación, generación, tres E2E y experimento de JEV) se harán en la fase que los use. No uses como referencia la versión anterior de OneDrive: está deprecada y contradice el repositorio.

## Archivos

Crear:

- `docs/arquitectura/diagramas/README.md`: qué es cada diagrama, cómo se edita y cómo se exporta.
- `docs/arquitectura/diagramas/fuente/estilos.css`: estilos compartidos (paleta, tipografía, tipos de nodo, flechas, leyenda).
- `docs/arquitectura/diagramas/fuente/arquitectura_general.html`.
- `docs/arquitectura/diagramas/fuente/flujo_consulta.html`.
- `docs/arquitectura/diagramas/arquitectura_general.png` y `docs/arquitectura/diagramas/flujo_consulta.png` (exportados, versionados).
- `scripts/exportar_diagramas.sh`: exporta cada HTML de `fuente/` a PNG con Chrome sin interfaz.
- Objetivo `diagramas` en el `Makefile` que llama al script.

Eliminar `docs/arquitectura/arquitectura_igss.svg` solo cuando el PNG general exista. No tocar `docs/anteproyecto/`, `DESIGN.md` ni el código de `src/`: las referencias las actualiza el gestor.

## Reglas técnicas

- HTML autocontenido: sin CDN, sin JavaScript de terceros, sin fuentes externas. Pila de fuentes del sistema (`Inter, "Segoe UI", Roboto, Helvetica, Arial, sans-serif`). Nodos con HTML y CSS; flechas con SVG en línea. Puede haber JavaScript propio mínimo solo si hace falta para dibujar las flechas; mejor sin él.
- Lienzo fijo declarado en el propio HTML con `<meta name="diagrama-tamano" content="ANCHOxALTO">` (por ejemplo `1800x1100`). El script lo lee para fijar el tamaño de la ventana.
- Exportación con `google-chrome --headless=new --hide-scrollbars --force-device-scale-factor=2 --window-size=... --screenshot=...`. El binario se puede cambiar con `CHROME_BIN`. Si no existe, el script falla con un mensaje claro. Sin Node, sin npm, sin npx, sin Python extra.
- Texto en español, sin emojis, legible al 100 % (mínimo 12 px en el lienzo). Fondo blanco, alto contraste.
- Consulta con Context7 lo que necesites de CSS o SVG; no inventes atributos.

## Diseño visual

- Título y subtítulo arriba; leyenda y principios abajo o a la derecha.
- Carriles (bandas con título) para separar flujos y almacenamiento.
- Tipos de nodo con color y forma distintos, y la misma leyenda en ambos diagramas:
  - código determinista;
  - decisión acotada (reglas, LLM estructurado o JEV, con umbral);
  - LLM local (generación de texto);
  - servicio externo (API de JEV);
  - datos y almacenamiento;
  - humano (analista o revisión);
  - salida al usuario;
  - estado compartido (borde discontinuo).
- Etiqueta pequeña de responsable en cada nodo: `rol 1`, `rol 2`, `rol 3` o `rol 4`.
- Etiqueta de estado: `implementado` o `por implementar`, según la tabla de estado de abajo. Debe ser honesta: un diagrama de defensa no puede presentar como hecho lo que no existe.
- Flechas: flujo principal, consulta a datos, rama de excepción (discontinua) y rama a revisión humana, cada una con su estilo y en la leyenda.
- Numeración de pasos para que se pueda narrar en la presentación.

## Notación y componentes (obligatorio)

Un diagrama de arquitectura no es un tablero de notas. Cada elemento usa la forma estándar de su tipo (notación de diagramas de flujo ISO 5807 y convenciones del modelo C4):

| Elemento | Forma |
|---|---|
| Base de datos (PostgreSQL, índices) | Cilindro |
| Almacén de archivos (originales PDF) | Cilindro o pila de documentos, nunca un rectángulo |
| Documento o paquete (PDF, ZIP) | Forma de documento (borde inferior ondulado) |
| Proceso de código | Rectángulo de esquinas suaves |
| Decisión o compuerta | Rombo con las ramas etiquetadas (sí, no, falla) |
| Entrada o salida al usuario | Paralelogramo |
| Persona (analista, revisor) | Icono de persona dibujado en SVG |
| Servicio externo (API de JEV) | Caja con borde doble o nube, fuera del límite del sistema |
| LLM | Rectángulo con color propio |
| Estado compartido | Caja de borde discontinuo |
| Límite del sistema | Rectángulo grande discontinuo que encierra lo que es LiciGT |

Reglas de texto:

- Cada nodo lleva un nombre corto (máximo 5 palabras) y, como mucho, una línea secundaria de 8 palabras. Nada de párrafos dentro de los nodos.
- Los detalles (modelos, parámetros, cifras) van en una tabla lateral o en notas numeradas al pie que el nodo referencia con su número, no dentro del nodo.
- Las etiquetas de rol y de estado son insignias pequeñas (pastillas), no texto corrido.
- Las flechas llevan etiqueta solo cuando es una condición o un dato que viaja.
- Alinear a una cuadrícula, espaciado uniforme, flechas ortogonales sin cruzar nodos.

## Contenido del diagrama general

Cada dato de abajo sale del código o de los documentos citados; respétalo. Si algo del código no coincide, gana el código y lo reportas.

### Carril A: ingesta (rol 1, `src/licigt/ingesta`)

1. Analista registra el evento y carga cada PDF con su tipo (`bases`, `anexo`, `aclaracion`, `modificacion`) y URL de origen del Portal de Proveedores del IGSS.
2. Validación: cabecera `%PDF-`, URL de dominio oficial, tamaño, SHA-256 y pertenencia al evento (`pipeline.py`, `automatic.py`).
3. Original inmutable en "MinIO o almacén local" (el proveedor no está decidido; `storage.py`).
4. Extracción por página con Poppler (`pdftotext`) y OCR con Tesseract en español (`pdftoppm`) cuando la página no tiene texto (`pdf.py`).
5. Control de calidad: página con menos de 30 caracteres útiles se marca ilegible; el documento queda `requiere_revision` y sus páginas no indexadas se informan (`pdf.py`, `pipeline.py`).
6. Limpieza que conserva numerales, fechas y códigos.
7. Segmentación por sección, hasta 600 palabras con solape de 90 (`pipeline.py`).
8. Control de inyección: expresiones regulares y comparación de texto visible contra texto oculto (`pdftohtml -hidden`). El fragmento sospechoso queda `indexable = false` y no se exporta (`pipeline.py`, `pdf.py`, `handoff.py`).
9. Metadatos y versión: `doc_id`, `evento_id`, `tipo_documento`, `version_ingesta`, páginas y sección, sin borrar versiones anteriores. Paquete ZIP para el rol 2.

### Carril B: índices (rol 2, `src/licigt/recuperacion`)

- PostgreSQL con pgvector. Línea base: ventanas de 120 tokens, `paraphrase-multilingual-MiniLM-L12-v2` (384). Mejorada: fragmentos por sección, `BAAI/bge-m3` (1024). Índices HNSW coseno y `tsvector` en español (GIN). Seguridad por fila por empresa con el rol `licigt_app` (`schema.sql`, `indice.py`).

### Carril C: consulta

1. Analista autenticado: el contexto (empresa, usuario, rol) lo crea el rol 4 desde la sesión; nunca de la pregunta.
2. Guardrail de entrada (rol 3): formato y longitud con Pydantic, alcance e indicios de inyección (reglas; JEV como variante). Falla: abstención.
3. Ambigüedad: si la pregunta no nombra una actividad, fecha o documento concreto, se pide aclaración.
4. Enrutador de intención (flujo de decisión, no agente autónomo): elige una de tres herramientas de solo lectura, `buscar_documentos`, `extraer_requisitos` o `comparar_versiones`. Máximo 3 llamadas por solicitud. Parámetros validados (`k` de 1 a 10, `query` hasta 500 caracteres).
5. Recuperación autorizada (rol 2): filtro por empresa y evento en SQL, más seguridad por fila. 20 candidatos semánticos y 20 léxicos (`ts_rank_cd`), fusión RRF (k = 60, pesos 0.6 y 0.4), reranker `BAAI/bge-reranker-v2-m3`, hasta 5 fragmentos sin redundancia (`busqueda.py`).
6. Alertas y suficiencia (rol 2): `posible_conflicto`, `cobertura_incompleta`, `evento_con_modificaciones` y `suficiente` por umbral del reranker. `suficiente = false` lleva a abstención sin llamar al LLM.
7. Generación (rol 3): LLM local con prompt que separa instrucciones, evidencia (tratada como datos) y pregunta; salida estructurada con citas.
8. Guardrail de salida (rol 3): validador determinista de esquema y citas (`chunk_id` existente y autorizado, página, versión, texto citado). JEV como variante para juzgar si la cita respalda la afirmación. Una sola regeneración; si vuelve a fallar, salida controlada.
9. Salidas: respuesta con fuentes; abstención con el texto fijo "No hay información suficiente en los documentos para responder"; revisión humana (`needs_human_review`) ante conflicto o dato crítico ambiguo, mostrando ambas fuentes sin decidir la vigencia.

### Estado compartido (nodo visible, conectado a todo el carril C)

`tenant_id`, `usuario`, `rol`, `evento_id`, intención, herramienta y parámetros, filtros aplicados, `chunk_ids` y puntajes, alertas, resultado de validación, versiones de modelos y del prompt.

### Almacenamiento y servicios (columna o carril propio)

- PostgreSQL con pgvector: documentos, fragmentos, versiones, seguridad por fila.
- Originales: MinIO o almacén local.
- Registro de herramientas: esquemas y límites.
- Auditoría sanitizada (rol 4): tarea, filtros, `chunk_ids`, citas y errores, sin texto de PDF ni datos personales.
- Banco de evaluación (rol 4): al menos 20 casos, línea base frente a mejorada.
- API de JEV (servicio externo): solo recibe la pregunta y fragmentos públicos.

### Principios (texto al pie)

1. El LLM solo recibe lo que el usuario puede ver: el filtro por empresa y evento se aplica en SQL antes de recuperar.
2. Flujo de decisión con tres herramientas de solo lectura; ninguna presenta ofertas ni modifica documentos.
3. Una modificación no reemplaza todo lo anterior: se muestran ambas cláusulas y decide un humano.
4. Todo fragmento recuperado es dato, nunca instrucción; ninguna capa de seguridad es suficiente por sí sola.
5. Las decisiones son clasificadores acotados con umbral; reglas, LLM estructurado y JEV se comparan en el banco.

## Contenido del diagrama de flujo de consulta

El mismo carril C con más detalle, y cada excepción como rama visible hacia su salida:

| Punto | Condición | Salida |
|---|---|---|
| Entrada | Formato o longitud inválidos | Abstención (error de validación) |
| Entrada | Fuera de alcance o inyección | Abstención |
| Ambigüedad | Pregunta sin objeto concreto | Pedir aclaración |
| Enrutador | Ninguna herramienta aplica | Abstención |
| Enrutador | Se agotan 3 llamadas | Salida controlada |
| Herramienta | Falla o parámetros inválidos | Error controlado |
| Recuperación | `suficiente = false` | Abstención sin llamar al LLM |
| Alertas | `posible_conflicto` | `needs_human_review = true`, ambas fuentes |
| Alertas | `cobertura_incompleta` | `coverage_status = parcial` y advertencia |
| Alertas | `evento_con_modificaciones` | Advertencia |
| JEV | API no disponible | Se usa la variante de reglas |
| Validación | Citas inválidas | Una regeneración; luego salida controlada |

Incluir los parámetros de cada herramienta:

- `buscar_documentos(query, evento_id, tipo_documento?, k = 5)`, con `k` de 1 a 10 y el filtro por tipo aplicado sobre los resultados.
- `extraer_requisitos(evento_id, categoria?)`, con categorías administrativa, legal, técnica y financiera.
- `comparar_versiones(evento_id, tema, doc_base_id?, doc_cambio_id?)`, con ambos ids o ninguno.

Y el contrato de salida: `answer`, `sources` (`doc_id`, `source`, `page`, `page_end`, `chunk_id`, `version_ingesta`, `version_oficial`, `cita`), `abstained`, `tool_used`, `needs_human_review`, `evento_id`, `coverage_status`, `warnings`.

## Estado para las etiquetas

| Componente | Estado |
|---|---|
| Ingesta (rol 1) | implementado |
| Índices y búsqueda, alertas, suficiencia (rol 2) | implementado |
| Esquemas de salida y parámetros (rol 3) | implementado |
| Guardrail de entrada, ambigüedad, enrutador, herramientas, generación, validador de citas (rol 3) | por implementar |
| JEV en cualquier punto | por implementar |
| Autenticación, contexto, auditoría, banco de evaluación (rol 4) | por implementar |

## Verificación

- `make diagramas` genera los dos PNG sin errores.
- Abre cada PNG y comprueba que no haya texto cortado, nodos encimados ni flechas que crucen texto.
- Busca en tus archivos y confirma que no aparecen: `GUATECOMPRAS`, `NOG`, `Docling`, `BM25`, `search_documents`, `extract_requirements`, `compare_versions`, `agente autónomo`.

## Corrección 1 (auditoría del gestor sobre la primera entrega)

La primera entrega no cumple. Defectos vistos en los PNG:

- **Texto encimado o cortado:** las insignias `rol N` y `IMPLEMENTADO` tapan títulos y líneas ("Control de inyección", "falso", "PDF", "pregunta", "reranker", "aplica", "inválidos", "sin llamar al LLM", "esquema y citas", "Respuesta / controlada"). El título del carril D queda debajo del nodo de JEV.
- **Formas incorrectas:** todo es rectángulo. PostgreSQL y Originales deben ser cilindros, el analista un icono de persona, las compuertas rombos, JEV un servicio externo fuera del límite del sistema (ver "Notación y componentes").
- **Flechas sin destino:** en el general, las ramas de excepción (abstención, sin herramienta, llamadas agotadas, insuficiente) terminan en el aire; hay una línea vertical que sube desde los paneles inferiores y otra que entra al carril B sin llegar a ningún nodo. La salida de ingesta no llega al cilindro de PostgreSQL.
- **Información oculta o faltante:** el estado compartido del general queda tapado por la leyenda y no está conectado al carril C. Faltan como nodos: la fuente autorizada (Portal de Proveedores del IGSS), las salidas de abstención, aclaración y revisión humana, y la conexión del guardrail de salida con la salida final. La leyenda está cortada abajo.
- **JEV mal ubicado:** en el flujo de consulta aparece como un paso fijo entre alertas y generación. No es un paso: es una variante que se consulta desde tres compuertas (guardrail de entrada, enrutador y guardrail de salida) con flechas discontinuas hacia el servicio externo, y una rama "API no disponible → reglas".
- **Dato a verificar:** el panel de fuentes dice que `pipeline.py` admite más tipos de documento (especificaciones, convocatoria, normativa). Si el código lo confirma, cítalo con línea; el diagrama debe mostrar solo los tipos que usa la consulta (`bases`, `anexo`, `aclaracion`, `modificacion`, según `esquemas.py`).

### Verificación automática de maquetación (obligatoria)

Antes de entregar, añade al script de exportación una comprobación que falle si hay defectos:

1. Cada HTML incluye un pequeño script propio que, al cargar con el parámetro `?verificar`, mide con `getBoundingClientRect` todos los nodos, insignias, títulos de carril y paneles, y detecta: elementos que se solapan entre sí, texto desbordado (`scrollWidth > clientWidth` o `scrollHeight > clientHeight`) y elementos que salen del lienzo. Escribe el resultado en un elemento con `id="verificacion"` (`OK` o la lista de problemas con el id de cada elemento).
2. El script de exportación carga cada HTML con `?verificar` usando `google-chrome --headless=new --dump-dom`, busca ese elemento y termina con error si no dice `OK`.
3. Las flechas se dibujan entre ids de nodos (de borde a borde), no con coordenadas sueltas, para que ninguna termine en el vacío.

Después de exportar, abre y mira cada PNG completo. No entregues si `make diagramas` falla.

## Al terminar

Responde con los archivos creados o eliminados, la salida de `make diagramas`, cualquier dato del encargo que no coincidiera con el código y las decisiones de diseño que tomaste. No amplíes el alcance.
