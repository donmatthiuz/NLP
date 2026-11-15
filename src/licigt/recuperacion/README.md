# Recuperación y RAG — rol 2

**Integrante:** ______________________________

Aquí se implementarán embeddings, índices de PostgreSQL y `pgvector`, búsqueda léxica y vectorial, fusión, reranking y detección de evidencia insuficiente o versiones en conflicto.

**Entrada:** [paquete de ingesta](../../../entregables/recuperacion/README.md) con `chunks.jsonl`, `inventario.json`, PDF originales, manifiestos y JSON de procedencia. El paquete versionable está en `entregables/recuperacion/empresa_demo.zip` (desde la raíz del repositorio). En consulta, recibe `evento_id` y contexto de acceso autenticado de la empresa.

Para examinar la entrega: `unzip -l entregables/recuperacion/empresa_demo.zip`. Para extraerla desde la raíz del repositorio:

```bash
mkdir -p data/recuperacion/entrada
unzip entregables/recuperacion/empresa_demo.zip -d data/recuperacion/entrada
```

Cada línea de `chunks.jsonl` trae `chunk_id`, `doc_id`, `tenant_id`, `evento_id`, tipo, versión, página, sección, texto, hash y URL. `inventario.json` identifica el original por `original_zip_path`, su SHA-256, estado y cobertura; `procedencia/<doc_id>.json` conserva el registro de descarga. Importar los fragmentos a PostgreSQL conservando esos identificadores; calcular `tsvector` y embeddings allí. No se debe asumir que `version_ingesta` indica vigencia legal: para 222 hay bases y una modificación oficial como documentos separados. Las páginas 3 y 4 de esa modificación requieren OCR o revisión y no aparecen como fragmentos.

Antes de consultar, aplicar en SQL los filtros de empresa y evento que entregue el rol 4 y respetar sus permisos de rol. El `tenant_id` dentro del paquete sirve para asociar datos; por sí solo no autoriza al usuario. La búsqueda devuelve solo fragmentos permitidos, con página, versión y puntaje para las citas del rol 3.

Para validar el paquete antes de importarlo: `python -m unittest discover -s src/licigt/recuperacion/tests -v` desde la raíz del repositorio.

**Salida para consulta:** fragmentos autorizados con puntaje, `chunk_id`, documento, página, versión y alertas de conflicto.

Ver [responsabilidades e integración](../../../docs/roles/Asignacion_de_roles.md#rol-2--recuperación-y-rag).
