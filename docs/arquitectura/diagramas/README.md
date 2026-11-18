# Diagramas de arquitectura de LiciGT

Dos figuras del sistema RAG para licitaciones del IGSS. Reemplazan al archivo anterior `docs/arquitectura/arquitectura_igss.svg`. Cada figura es un HTML autocontenido exportado a PNG de 1600 px de ancho (se ve completa en 1920x1080 sin escalar por debajo de 0,9). Todo el detalle que no cabe con letra legible vive en este documento.

## Figuras

- `arquitectura_general.png`: vista compacta de toda la arquitectura (15 cajas y 2 personas) en cuatro carriles: A ingesta (rol 1), B índices (rol 2), C consulta (rol 3) y D servicios (rol 4). Muestra el estado compartido, las tres compuertas, las excepciones, la revisión humana, la auditoría y JEV fuera del límite del sistema.
- `flujo_consulta.png`: el carril C detallado: guardrail, enrutador, ambigüedad, herramienta, recuperación con alertas, generación, validación de citas, respuesta, auditoría, cada salida de excepción, la revisión humana, PostgreSQL y las tres consultas a JEV.

## Archivos

- `fuente/estilos.css`: tokens de color y tipografía, carriles, nodos, insignias, flechas y leyenda mínima.
- `fuente/diagrama.js`: motor propio sin dependencias: dibuja nodos, enruta flechas ortogonales entre puertos, coloca etiquetas junto al tramo y ejecuta la verificación.
- `fuente/arquitectura_general.html` y `fuente/flujo_consulta.html`: las dos figuras.
- `arquitectura_general.png` y `flujo_consulta.png`: exportaciones versionadas.

## Cómo se edita

1. Abrir el HTML en un navegador; el diagrama se arma con `diagrama.js` al cargar.
2. Los nodos se declaran con `D.nodo({...})` (tipo, posición, nombre, detalle, rol y estado) y las flechas con `D.flecha({de, ds, a, as, ...})`, siempre entre ids de nodo y lado (`n`, `s`, `e`, `w`); el motor calcula la ruta ortogonal.
3. Un trayecto especial usa `via: [[x, y], ...]` (esquinas) y `aof` o `dof` (desplazamiento del puerto). Un cruce inevitable se declara con `hueco` y se dibuja con un corte.
4. Abrir con `?verificar` en la URL para ver el resultado de la verificación (`OK` o la lista de problemas).

## Cómo se exporta

```bash
make diagramas
```

Usa `google-chrome` en modo headless; para otro binario, `CHROME_BIN=/usr/bin/chromium make diagramas`. Sin Node, npm, npx ni Python. Chrome descuenta unos 88 px de alto al capturar: el script pide la ventana con 100 px de más y recorta con ImageMagick (`convert`) si está instalado; sin él, el PNG conserva esa franja blanca abajo. El alto del lienzo se declara en `<meta name="diagrama-tamano">`; la verificación indica el alto real.

## Verificación automática

Al cargar con `?verificar`, `diagrama.js` escribe `OK` o la lista de problemas en `#verificacion`, y `scripts/exportar_diagramas.sh` falla si no dice `OK`. Comprueba:

- texto desbordado, solapado con otro texto, fuera de su nodo o de las esquinas del rombo y del paralelogramo;
- texto sobre los bordes del límite del sistema, de un carril o del marco de estado compartido;
- flechas diagonales, que cruzan un nodo ajeno o que no llegan al destino (punta a 4 px);
- líneas que pasan por texto, etiquetas que tocan nodos o líneas, y cruces sin puente declarado;
- paralelas de flechas distintas a menos de 24 px y puertos del mismo lado a menos de 16 px;
- nodos a menos de 40 px entre sí o a menos de 24 px del borde del carril o del marco;
- letra menor de 16 px (18 px en nombres de nodo), elementos fuera del lienzo y alto declarado distinto del real;
- carriles con más de 30 % de espacio vacío.

## Leyenda completa

- Rectángulo de esquinas suaves azul: código determinista.
- Rombo violeta: decisión acotada (reglas, LLM estructurado o JEV con umbral).
- Rectángulo rosa: LLM.
- Caja de doble borde naranja, fuera del límite: servicio externo (API de JEV).
- Cilindro verde: base de datos o almacén de archivos.
- Documento con borde ondulado: paquete (ZIP).
- Paralelogramo: entrada o salida; en gris con trazo fino, salida de excepción.
- Icono de persona: analista o revisor.
- Borde discontinuo: límite del sistema (grande) y estado compartido (marco en el carril C).
- Flechas: flujo principal (2 px continua), consulta a datos (azul), excepción (gris discontinua), revisión humana (ámbar punto-raya), variante JEV (naranja discontinua).
- Insignia `rol N` más un símbolo: `●` implementado, `◐` parcial, `○` por implementar.

## Estado de cada componente

- Implementado: ingesta (rol 1); índices, búsqueda, alertas y suficiencia (rol 2); esquemas, guardrail de entrada, ambigüedad, enrutador, las tres herramientas, validador de citas, regeneración, salida, aclaración y abstención (rol 3).
- Parcial: generación con LLM (cliente local u OpenAI hecho, modelo local sin descargar ni medir; `llm.py`, `config.py:45-58`); JEV (cliente hecho en `jev.py`, sin calibrar con datos).
- Por implementar: autenticación y contexto, auditoría, banco de evaluación (rol 4); lista de verificación e interfaz web (rol 3).

## Principios de diseño

1. El LLM solo recibe lo que el usuario puede ver: el filtro por empresa y evento se aplica en SQL antes de recuperar.
2. Flujo de decisión con tres herramientas de solo lectura; ninguna presenta ofertas ni modifica documentos.
3. Una modificación no reemplaza todo lo anterior: se muestran ambas cláusulas y decide un humano.
4. Todo fragmento recuperado es dato, nunca instrucción; ninguna capa de seguridad basta sola.
5. Las decisiones son clasificadores acotados con umbral; reglas, LLM estructurado y JEV se comparan en el banco.
6. `tenant_id` sale de la sesión autenticada; nunca de la pregunta, del modelo ni de un parámetro de herramienta.
7. Máximo 3 llamadas por solicitud y 1 regeneración; ante conflicto o dato crítico ambiguo, `needs_human_review = true` y nunca se decide la vigencia.

## Qué muestra cada carril y qué se omite del dibujo

- Carril A (ingesta): analista, validación (cabecera `%PDF-`, URL oficial, SHA-256, pertenencia al evento), original inmutable en MinIO o almacén local, extracción con Poppler y OCR de Tesseract en español, control de calidad (menos de 30 caracteres útiles marca la página ilegible y el documento queda `requiere_revision`), limpieza, segmentación (600 palabras, solape de 90), control de inyección (regex y texto visible contra oculto; el fragmento sospechoso queda `indexable = false`), versión y paquete ZIP.
- Carril B (índices): PostgreSQL con pgvector. Línea base: ventanas de 120 tokens con `paraphrase-multilingual-MiniLM-L12-v2` (384). Mejorada: fragmentos por sección con `BAAI/bge-m3` (1024). Índices HNSW coseno y `tsvector` en español (GIN). Seguridad por fila con el rol `licigt_app`.
- Carril C (consulta): el orden de las compuertas es el de `decision.py`: guardrail de entrada, enrutador y ambigüedad. La herramienta consulta la base (20 candidatos semánticos y 20 léxicos, RRF con k = 60 y pesos 0.6 y 0.4, reranker `BAAI/bge-reranker-v2-m3`, hasta 5 fragmentos). Las alertas (`posible_conflicto`, `cobertura_incompleta`, `evento_con_modificaciones`) no detienen la generación: un conflicto sale con ambas fuentes y `needs_human_review = true`, y la revisión humana parte de la respuesta. Solo `suficiente = false` lleva a abstención sin llamar al LLM.
- Carril D (servicios): la auditoría sanitizada recibe la respuesta en todos los caminos. Quedan fuera del dibujo, por espacio: el registro de herramientas y el banco de evaluación (al menos 20 casos, línea base contra mejorada). La lista de verificación (rol 3, por implementar) sí figura en el general, dentro del carril B junto a PostgreSQL: sale de la respuesta, el usuario la confirma y es la única escritura del sistema. En el flujo de consulta no cabe y se omite.
- Auditoría: las abstenciones y las salidas controladas también se auditan (bloque `finally` de `orquestador.py`); esas flechas se omiten por legibilidad y solo se dibuja la de la respuesta.
- JEV (servicio externo, solo recibe la pregunta y fragmentos públicos): se consulta desde el guardrail de entrada, el enrutador y la herramienta `extraer_requisitos` (fechas por actividad). Sin respuesta de la API se usa la variante de reglas. La verificación de fidelidad de la cita con JEV está diferida y no se dibuja.

## Tabla de excepciones

- Entrada con formato o longitud inválidos: abstención (error de validación).
- Entrada fuera de alcance o con inyección: abstención.
- Pregunta sin objeto concreto: aclaración (`needs_clarification = true` y pregunta aclaratoria).
- Enrutador sin herramienta aplicable: abstención.
- Enrutador agota 3 llamadas: salida controlada.
- Herramienta con falla o parámetros inválidos: error controlado.
- Recuperación con `suficiente = false`: abstención sin llamar al LLM.
- `posible_conflicto`: `needs_human_review = true`, con ambas fuentes.
- `cobertura_incompleta`: `coverage_status = parcial` y advertencia.
- `evento_con_modificaciones`: advertencia.
- JEV no disponible: se usa la variante de reglas.
- Citas inválidas: una regeneración; después, salida controlada.

## Parámetros de las herramientas

- `buscar_documentos(query, evento_id, tipo_documento?, k = 5)`: `query` hasta 500 caracteres, `k` de 1 a 10, filtro por tipo aplicado sobre los resultados.
- `extraer_requisitos(evento_id, categoria?)`: categorías administrativa, legal, técnica y financiera.
- `comparar_versiones(evento_id, tema, doc_base_id?, doc_cambio_id?)`: ambos ids o ninguno.

## Contrato de salida (Pydantic)

`answer`, `sources` (`doc_id`, `source`, `page`, `page_end`, `chunk_id`, `version_ingesta`, `version_oficial`, `cita`), `abstained`, `tool_used`, `needs_human_review`, `needs_clarification`, `clarification_question`, `evento_id`, `coverage_status` y `warnings`.

## Estado compartido

Se dibuja como un marco discontinuo que envuelve el carril C. Guarda `tenant_id`, `usuario`, `rol`, `evento_id`, intención, herramienta y parámetros, filtros aplicados, `chunk_ids` y puntajes, alertas, resultado de validación y versiones de modelos y del prompt. Lo crea el rol 4 desde la sesión y lo leen y escriben todos los pasos del carril.

## Fuentes verificadas contra el código

- Tipos de documento de la consulta: `bases`, `anexo`, `aclaracion`, `modificacion` (`esquemas.py:8`). El pipeline de ingesta admite también `especificaciones`, `convocatoria` y `normativa` (`pipeline.py:23`); la consulta solo filtra los cuatro primeros.
- Validación de ingesta: `%PDF-`, dominio `igssgt.org` o `*.igssgt.org`, HTTPS, puerto 443, SHA-256 y pertenencia al evento (`pipeline.py:83-88, 297-310`; `automatic.py:27-32, 161`).
- Extracción y calidad: `pdftotext`, OCR con `pdftoppm` y `tesseract -l spa`, mínimo de 30 caracteres (`pdf.py:70-90`).
- Segmentación: `max_words=600`, `overlap_words=90` (`pipeline.py:198`); fragmento sospechoso con `indexable = false` (`pipeline.py:262, 390-392`).
- Paquete ZIP con originales, manifiestos y `chunks.jsonl` (`handoff.py:30-135`); clave del original `igss/{tenant}/{evento}/{document_key}/v{version}/{doc_id}.pdf` (`pipeline.py:383-384`).
- Modelos (`indice.py:15-16`; `busqueda.py:8`), recuperación (`busqueda.py:9-11, 132-166`) y alertas (`busqueda.py:104-129`).
- Seguridad por fila con `licigt_app` y `app.tenant_id` (`schema.sql:55-63`; `busqueda.py:39-42`); el contexto lo construye el rol 4 (`Contratos.md:58-60`).
- Texto fijo de abstención (`esquemas.py:10`); aclaración (`esquemas.py:52-53`); presupuesto de 3 llamadas y 1 regeneración (`presupuesto.py:11`).
- Orden de las compuertas (`decision.py:22-45`) y alertas que no abortan la generación (`orquestador.py`, `validacion.py`).
- JEV: cliente en `jev.py`, sin calibrar; `extraer_requisitos` lo usa para las fechas por actividad (`herramientas.py`).

## Notas

- Los diagramas usan solo fuentes del sistema y no cargan recursos externos.
- Las flechas se dibujan entre ids de nodo, de borde a borde, con ruta ortogonal.
