# Plan del rol 2: recuperación y RAG

**Estado al 15 de noviembre de 2026.** Este plan cubre las [responsabilidades del rol 2](../roles/Asignacion_de_roles.md#rol-2--recuperación-y-rag) y sigue la sección [10. Recuperación y RAG](../anteproyecto/Anteproyecto.md#10-recuperación-y-rag) del anteproyecto. El código irá en [`src/licigt/recuperacion`](../../src/licigt/recuperacion/README.md).

> **Avance (18 de noviembre):** hecho con evidencia: F0 a F5 y los casos de F6 (`src/licigt/recuperacion/tests`, `casos_desarrollo.json`, tabla de [Recuperacion.md](Recuperacion.md)); R2C agregó dispositivo y dtype configurables, `resolver_evento`, `obtener_fragmentos` y `warnings` en `cobertura_incompleta`, con pruebas en `tests/test_cierre.py`. El umbral, la latencia CPU y GPU y Hit@5 con el corpus R6 se midieron en R2C (ver Recuperacion.md).
>
> **Avance anterior:** F0–F5 están implementadas y F6 tiene sus casos de desarrollo. Lo que funciona y lo que queda pendiente está en [Recuperacion.md](Recuperacion.md).

## Lo que se revisó del paquete de entrada

Se revisó [`empresa_demo.zip`](../../entregables/recuperacion/empresa_demo.zip) y se comparó con los PDF originales que contiene.

- Contiene 6 PDF de 5 eventos (399, 222, 363, 327 y 368) y 1003 fragmentos, de los cuales 890 son de texto y 113 de tabla. Los fragmentos tienen en promedio 56 palabras y como máximo 429. La segmentación ya sigue las secciones del documento.
- **Conflicto real para evaluar:** en las bases del evento 222, la recepción de ofertas es el 31 de julio de 2023 (2.2.6). La modificación número 1 la cambia al 6 de octubre de 2023. La página 3 de la modificación es un escaneo legible: indica que se modifican el subnumeral 2.2 *Cronograma* y la literal e) del subnumeral 2.7 *Listado de documentos de la plica*. Se puede usar como uno de los dos casos de comparación temporal.
- **Calidad que afecta a la búsqueda:**
  - En los fragmentos de tabla, `tabla_markdown` viene nulo casi siempre, y el texto conserva la disposición en columnas con las celdas partidas.
  - En algunos fragmentos, `seccion` contiene el pie de página (`Extensión: 99175`) en lugar del numeral.
  - Ambos puntos se reportan al rol 1; no se corrigen en el rol 2.
- Las páginas 3 y 4 de la modificación no tienen fragmentos porque requieren OCR, que es un pendiente del rol 1. Mientras tanto, la búsqueda debe mostrar la alerta de cobertura del inventario (`status = requiere_revision`).

## Fases

### F0. Entorno — 0.5 días
Evidencia: `docker-compose.yml`, `make db-up`; `requirements.txt` sin `FlagEmbedding` (el reranker corre con `CrossEncoder`).

- [x] Levantar `pgvector/pgvector:pg17` con `docker compose` (archivo `docker-compose.yml` en la raíz, compartido con el rol 4).
- [x] Crear un entorno de Python para los modelos. En NixOS se puede usar `uv venv -p 3.12` (con `nix-shell -p uv`). No se ha comprobado que `torch` y `sentence-transformers` funcionen con Python 3.14, que es el Python del sistema.
- [x] Definir las dependencias en `src/licigt/recuperacion/requirements.txt`: `psycopg[binary]`, `pgvector`, `sentence-transformers` y `FlagEmbedding`, si hace falta para el reranker.

### F1. Esquema e importación — 1 día
Evidencia: `schema.sql` e `indice.py` (`importar`). Diferencia con lo planeado: una sola tabla `fragmentos` con columna `variante` y una columna de vector por variante, en vez de dos tablas.

- [x] Crear `schema.sql` con estas tablas:
  - `documentos`, a partir de `inventario.json`.
  - `fragmentos_mejorada`, con los chunks del ZIP sin cambios en sus identificadores, una columna `tsv tsvector GENERATED ... to_tsvector('spanish', seccion || ' ' || texto)` y una columna `emb vector(1024)`.
  - `fragmentos_base`, con la ventana de 120 tokens y `emb vector(384)`. Las dos variantes van en tablas separadas porque sus vectores tienen dimensiones distintas.
  - Campos exactos con índice B-tree para `numero_evento` y `codigos_producto_igss` (`text[]`, índice GIN).
- [x] Crear los índices: GIN sobre `tsv`, y HNSW `vector_cosine_ops` con `m=16` y `ef_construction=64`.
- [x] Definir la seguridad por fila: `ENABLE ROW LEVEL SECURITY` con una política `tenant_id = current_setting('app.tenant_id')` y un rol de aplicación sin `BYPASSRLS`. El valor de `app.tenant_id` lo fija el contexto de acceso del rol 4.
- [x] Escribir `importar.py`, que lea el ZIP, valide el SHA-256 de `chunks.jsonl` contra el inventario e inserte o actualice los registros de forma idempotente.

### F2. Línea base — 1 día
Evidencia: `ventanas_base` y `test_ventanas_base_no_se_truncan` en `tests/test_busqueda.py`.

- [x] Volver a segmentar desde `manifiestos/<doc_id>.json` (texto por página) en ventanas de 120 tokens con solapamiento de 20, medidas con el tokenizer de `paraphrase-multilingual-MiniLM-L12-v2`. Las ventanas conservan `doc_id`, páginas y versión, y no combinan documentos. Una prueba debe comprobar que ninguna ventana supera 126 tokens con los tokens especiales incluidos.
- [x] Calcular embeddings de 384 dimensiones y recuperar el top-5 por coseno con el filtro `tenant_id`/`evento_id` en el `WHERE`.

### F3. Versión mejorada — 2 días
Evidencia: `busqueda.buscar`; resultados en [Recuperacion.md](Recuperacion.md). La parte léxica usa `plainto_tsquery` con OR entre términos, no `websearch_to_tsquery`.

- [x] Calcular embeddings de `BAAI/bge-m3` (1024 dimensiones) sobre los fragmentos actuales.
- [x] Recuperar 20 candidatos semánticos y 20 léxicos (`websearch_to_tsquery('spanish', …)` con `ts_rank_cd`), con prioridad para las coincidencias exactas de número de evento, código IGSS y numeral.
- [x] Fusionar con RRF (k=60) y pesos de 0.6 para semántica y 0.4 para léxica.
- [x] Aplicar `BAAI/bge-reranker-v2-m3` a los 20 mejores y devolver hasta 5 fragmentos.
- [x] Eliminar redundancias entre fragmentos solapados del mismo documento, sin descartar el fragmento de otra versión o documento.

### F4. Suficiencia y conflictos — 1 día
Evidencia: `busqueda.suficiente` y `_alertas`; umbral calibrado en R2C (ver Recuperacion.md); `test_222_conflicto_y_cobertura`.

- [x] Definir un umbral de abstención con el puntaje del reranker, calibrado con el subconjunto de desarrollo. El puntaje no se trata como probabilidad.
- [x] Generar una alerta `posible_conflicto` cuando el resultado incluya un fragmento de un documento cuyo evento tenga una `modificacion` o `aclaracion` que toque el mismo numeral. En ese caso se devuelven ambos fragmentos y no se decide cuál está vigente.
- [x] Generar una alerta `cobertura_incompleta` cuando el documento tenga `paginas_no_indexadas` o el estado `requiere_revision`.

### F5. Contrato con el rol 3 — 0.5 días
Evidencia: `buscar`, `comparar_versiones`, `__main__.py`; R2C añadió `resolver_evento` y `obtener_fragmentos` (`tests/test_cierre.py`).

- [x] Implementar `buscar(contexto, evento_id, pregunta, variante="base"|"mejorada", k=5)`, que devuelve:
  - Los fragmentos con `chunk_id`, `doc_id`, `tipo_documento`, `version_ingesta`, páginas, `seccion`, `texto`, `url_origen` y los puntajes (semántico, léxico, RRF y reranker).
  - `alertas`.
  - `suficiente: bool`.
- [x] Implementar `comparar_versiones(contexto, evento_id, pregunta, k=2)`, que devuelve los fragmentos pareados de las bases y de sus modificaciones.
- [x] Ofrecer una CLI con la forma `python -m licigt.recuperacion buscar --evento ... "pregunta"` para hacer demos.

### F6. Evaluación con el rol 4 — 1 día
Evidencia: `evaluar.py` y `casos_desarrollo.json` (27 casos). Falta que guarde el commit en la salida y el banco común del rol 4.

- [ ] Escribir `evaluar.py`, que mida Hit@5 y MRR@5 por variante sobre el banco de al menos 20 casos, cada uno con sus `chunk_id` relevantes, y guarde los resultados y la configuración (modelos, parámetros y commit).
- [x] Incluir casos mínimos:
  - Recepción de ofertas del evento 222 (conflicto).
  - Código IGSS 432 en el evento 399 (coincidencia exacta).
  - Una pregunta sin evidencia (abstención).
  - Una consulta con otra empresa, que debe devolver vacío.

## Pruebas

- La prueba existente [`test_entrega.py`](../../src/licigt/recuperacion/tests/test_entrega.py) sigue validando el paquete de entrada.
- Pruebas nuevas:
  - Aislamiento: con otra empresa o con otro evento, la búsqueda devuelve 0 filas, incluida la verificación con RLS.
  - Ninguna ventana de la línea base se trunca.
  - La fusión RRF da el orden esperado en un caso pequeño.
  - El evento 222 genera la alerta de conflicto y la de cobertura.

## Dependencias y decisiones pendientes

- **Rol 1:** OCR de las páginas 3 y 4, `tabla_markdown` y el campo `seccion` de los pies de página. Hay que reimportar cuando cambie el ZIP; la importación idempotente lo permite.
- **Rol 3:** confirmar el contrato de F5.
- **Rol 4:** contexto de acceso (`tenant_id`, rol), dónde corre Postgres (Docker local, Cloud SQL o un bucket para artefactos) y el banco de casos.
- **Recursos:** `bge-m3` y el reranker ocupan unos 2 GB cada uno y en CPU son lentos. Con 1003 fragmentos el costo es aceptable, pero hay que medir la latencia P95 (meta del proyecto: 15 s en total).
