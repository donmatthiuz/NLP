# Plan del rol 2: recuperación y RAG

**Estado al 15 de noviembre de 2026.** Este plan cubre las [responsabilidades del rol 2](../roles/Asignacion_de_roles.md#rol-2--recuperación-y-rag) y sigue la sección [10. Recuperación y RAG](../anteproyecto/Anteproyecto.md#10-recuperación-y-rag) del anteproyecto. El código irá en [`src/licigt/recuperacion`](../../src/licigt/recuperacion/README.md).

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
- [ ] Levantar `pgvector/pgvector:pg17` con `docker compose` (archivo `docker-compose.yml` en la raíz, compartido con el rol 4).
- [ ] Crear un entorno de Python para los modelos. En NixOS se puede usar `uv venv -p 3.12` (con `nix-shell -p uv`). No se ha comprobado que `torch` y `sentence-transformers` funcionen con Python 3.14, que es el Python del sistema.
- [ ] Definir las dependencias en `src/licigt/recuperacion/requirements.txt`: `psycopg[binary]`, `pgvector`, `sentence-transformers` y `FlagEmbedding`, si hace falta para el reranker.

### F1. Esquema e importación — 1 día
- [ ] Crear `schema.sql` con estas tablas:
  - `documentos`, a partir de `inventario.json`.
  - `fragmentos_mejorada`, con los chunks del ZIP sin cambios en sus identificadores, una columna `tsv tsvector GENERATED ... to_tsvector('spanish', seccion || ' ' || texto)` y una columna `emb vector(1024)`.
  - `fragmentos_base`, con la ventana de 120 tokens y `emb vector(384)`. Las dos variantes van en tablas separadas porque sus vectores tienen dimensiones distintas.
  - Campos exactos con índice B-tree para `numero_evento` y `codigos_producto_igss` (`text[]`, índice GIN).
- [ ] Crear los índices: GIN sobre `tsv`, y HNSW `vector_cosine_ops` con `m=16` y `ef_construction=64`.
- [ ] Definir la seguridad por fila: `ENABLE ROW LEVEL SECURITY` con una política `tenant_id = current_setting('app.tenant_id')` y un rol de aplicación sin `BYPASSRLS`. El valor de `app.tenant_id` lo fija el contexto de acceso del rol 4.
- [ ] Escribir `importar.py`, que lea el ZIP, valide el SHA-256 de `chunks.jsonl` contra el inventario e inserte o actualice los registros de forma idempotente.

### F2. Línea base — 1 día
- [ ] Volver a segmentar desde `manifiestos/<doc_id>.json` (texto por página) en ventanas de 120 tokens con solapamiento de 20, medidas con el tokenizer de `paraphrase-multilingual-MiniLM-L12-v2`. Las ventanas conservan `doc_id`, páginas y versión, y no combinan documentos. Una prueba debe comprobar que ninguna ventana supera 126 tokens con los tokens especiales incluidos.
- [ ] Calcular embeddings de 384 dimensiones y recuperar el top-5 por coseno con el filtro `tenant_id`/`evento_id` en el `WHERE`.

### F3. Versión mejorada — 2 días
- [ ] Calcular embeddings de `BAAI/bge-m3` (1024 dimensiones) sobre los fragmentos actuales.
- [ ] Recuperar 20 candidatos semánticos y 20 léxicos (`websearch_to_tsquery('spanish', …)` con `ts_rank_cd`), con prioridad para las coincidencias exactas de número de evento, código IGSS y numeral.
- [ ] Fusionar con RRF (k=60) y pesos de 0.6 para semántica y 0.4 para léxica.
- [ ] Aplicar `BAAI/bge-reranker-v2-m3` a los 20 mejores y devolver hasta 5 fragmentos.
- [ ] Eliminar redundancias entre fragmentos solapados del mismo documento, sin descartar el fragmento de otra versión o documento.

### F4. Suficiencia y conflictos — 1 día
- [ ] Definir un umbral de abstención con el puntaje del reranker, calibrado con el subconjunto de desarrollo. El puntaje no se trata como probabilidad.
- [ ] Generar una alerta `posible_conflicto` cuando el resultado incluya un fragmento de un documento cuyo evento tenga una `modificacion` o `aclaracion` que toque el mismo numeral. En ese caso se devuelven ambos fragmentos y no se decide cuál está vigente.
- [ ] Generar una alerta `cobertura_incompleta` cuando el documento tenga `paginas_no_indexadas` o el estado `requiere_revision`.

### F5. Contrato con el rol 3 — 0.5 días
- [ ] Implementar `buscar(contexto, evento_id, pregunta, variante="base"|"mejorada", k=5)`, que devuelve:
  - Los fragmentos con `chunk_id`, `doc_id`, `tipo_documento`, `version_ingesta`, páginas, `seccion`, `texto`, `url_origen` y los puntajes (semántico, léxico, RRF y reranker).
  - `alertas`.
  - `suficiente: bool`.
- [ ] Implementar `comparar_versiones(contexto, evento_id, seccion)`, que devuelve los fragmentos pareados de las bases y de sus modificaciones.
- [ ] Ofrecer una CLI con la forma `python -m licigt.recuperacion buscar --evento ... "pregunta"` para hacer demos.

### F6. Evaluación con el rol 4 — 1 día
- [ ] Escribir `evaluar.py`, que mida Hit@5 y MRR@5 por variante sobre el banco de al menos 20 casos, cada uno con sus `chunk_id` relevantes, y guarde los resultados y la configuración (modelos, parámetros y commit).
- [ ] Incluir casos mínimos:
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
