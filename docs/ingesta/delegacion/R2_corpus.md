# Encargo R2: corpus reproducible con los mismos ids

Para el implementador. Rama `rol/consulta`. No commitees.

Lee primero:

- [`AGENTS.md`](../../../AGENTS.md);
- [R1](R1_ingesta.md);
- `docs/ingesta/Corpus_IGSS.md` y `docs/ingesta/Seleccion_del_corpus.md`;
- `src/licigt/ingesta/pipeline.py`, `prepare_corpus.py`, `download.py`, `handoff.py`, `reextraer.py` y `automatic.py`, con sus pruebas;
- `entregables/recuperacion/README.md`.

## Origen y decisiones del usuario (17 de noviembre)

- **Qué exige la entrega:** las instrucciones del curso no fijan un número de documentos. El entregable 2 sí exige "pipelines de ingesta reproducibles", y el anteproyecto pide de 3 a 5 licitaciones, que ya tenemos (5 eventos, 6 PDF). **No se amplía el corpus.**
- **Por qué hoy no se puede reproducir:**
  - `prepare_corpus.py` fija los 6 PDF por su SHA-256, pero `pipeline.py:382` crea cada `doc_id` con `uuid4`, así que una nueva corrida cambia todos los `doc_id` y `chunk_id`;
  - `data/` no está en el repo.
  - Los roles 2 y 3, los casos de prueba y los ejemplos de la web citan los ids actuales (`03791a3471c04c0f9cc260814564756e`, `d41480e5b0ce4c16bf18f66225ada2dc`, etc.).
- **Autoridad:** el rol 3 absorbe el rol 1 con autoridad total, así que este encargo puede modificar `pipeline.py` y el resto de `src/licigt/ingesta`.

## Archivos

- **Nuevos:**
  - `src/licigt/ingesta/corpus_igss.json`, la especificación del corpus;
  - `src/licigt/ingesta/reproducir.py`;
  - `src/licigt/ingesta/tests/test_reproducir.py`.
- **Modificados:**
  - `pipeline.py`: `doc_id` y el momento de ingesta inyectables, y la corrección de `reprocess`;
  - `prepare_corpus.py`: lee la especificación en lugar de `SELECTION`;
  - sus pruebas;
  - `src/licigt/ingesta/README.md` y `docs/ingesta/Corpus_IGSS.md`;
  - el objetivo `corpus` del `Makefile`.
- **No se toca:** `src/licigt/recuperacion`, `src/licigt/consulta`, `web/` ni `entregables/recuperacion/empresa_demo.zip`. La regeneración real del ZIP la corre el usuario.

## Cambios (prueba en rojo primero, en cada uno)

### 1. Especificación del corpus

`corpus_igss.json` se genera una sola vez desde el ZIP actual, a partir de su inventario y sus manifiestos, y se commitea. Lleva una entrada por documento con:

- `numero_evento`, `evento_id`, `tenant_id`, `document_key`, `tipo_documento`, `version_oficial` y `relacion_documental`;
- `url_origen` (la de procedencia), `sha256`, `doc_id`, `version_ingesta` e `ingested_at`;
- `paginas_ocr` y las advertencias humanas, si las hay.

Se incluye la función que la genera, con su prueba.

### 2. `doc_id` e `ingested_at` inyectables en el pipeline

- `IngestionService.ingest` acepta un `doc_id` y un `ingested_at` opcionales. Si faltan, usa `uuid4` y la hora actual, como hoy.
- Un `doc_id` repetido con otro SHA-256 da error.
- **Prueba:** con valores fijos, dos corridas sobre el mismo PDF producen manifiestos y fragmentos idénticos.

### 3. `reproducir.py` y `make corpus`

Dos fuentes de PDF:

- `--desde-zip <ruta>` toma los originales que trae el ZIP, sin red;
- `--descargar` baja cada `url_origen` del portal del IGSS y respeta las reglas de `download.py`: solo `igssgt.org` y sin seguir redirecciones fuera de ese dominio.

En las dos fuentes:

- verifica el SHA-256 de cada PDF contra la especificación; si no coincide, falla sin escribir nada;
- ingiere en el orden de la especificación, con el `doc_id` y el `ingested_at` fijados, en un `data_dir` temporal;
- aplica la reextracción OCR de R1-A a los documentos con `paginas_ocr`, si `tesseract --list-langs` incluye `spa`; si no, lo avisa y deja las páginas como ilegibles, igual que el ZIP actual;
- exporta el ZIP con `handoff.export` a la ruta de `--salida`.

`make corpus` corre `reproducir.py --descargar --salida entregables/recuperacion/empresa_demo.zip` solo con `CONFIRMAR=1`. Sin `CONFIRMAR=1`, solo muestra lo que haría.

### 4. Prueba de reproducibilidad, sin red

Se reconstruye desde los originales del ZIP actual (`--desde-zip`, con la salida en un temporal) y se compara con el paquete actual:

- cada línea de `chunks.jsonl` es idéntica en `chunk_id`, texto, página, sección, metadatos e `indexable`;
- inventario y manifiestos son idénticos, salvo los campos de tiempo de la exportación, que la prueba enumera de forma explícita.

**Si algo difiere, la prueba lo reporta y no se ajusta a mano para que pase.** Una diferencia indica que el pipeline cambió desde que se armó el ZIP. Se informa al gestor con el detalle, y la decisión la toma el usuario.

### 5. `reprocess` respeta la advertencia de "parece modificación"

- Hoy, tras `reprocess()`, los fragmentos de un documento marcado así vuelven a ser indexables (lo reportó R1-B).
- **Corrección:** si el manifiesto trae esa advertencia, `reprocess` deja los fragmentos no indexables.
- **Prueba:** la que falta.

## Criterios de aceptación

- `make test-ingesta` en verde y `make test-consulta` sin cambios.
- La prueba del punto 4 pasa con el ZIP actual, o queda reportada la diferencia exacta.
- `make corpus` sin `CONFIRMAR=1` no descarga nada.
- Sin datos personales ni rutas absolutas en la especificación ni en el ZIP.

## Al terminar

Responde con:

- los archivos tocados;
- los resultados de `make test-ingesta` y `make test-consulta`;
- el resultado de la prueba de reproducibilidad, con el detalle si algo difiere;
- las líneas del objetivo `corpus` del `Makefile` (si no lo editaste);
- las decisiones donde el encargo no era claro.

No amplíes el alcance.
