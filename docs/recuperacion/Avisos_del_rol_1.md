# Avisos del rol 1 para el rol 2

**Estado al 17 de noviembre de 2026.** El paquete [`empresa_demo.zip`](../../entregables/recuperacion/empresa_demo.zip) cambió: la modificación 1 del evento 222 ahora tiene sus páginas 3 y 4 recuperadas por OCR.

## Qué hacer

- [ ] **Reimportar** con `make importar` (la importación es idempotente).
- [ ] Los `chunk_id` previos no cambian: los 1003 fragmentos anteriores son idénticos.
- [ ] Hay fragmentos nuevos en `d41480e5b0ce4c16bf18f66225ada2dc`: `:00014` a `:00016` son indexables (página 3); `:00017` a `:00020` (página 4) se excluyen como `ruido_ocr`. Total: 1006 indexables y 4 excluidos.
- [ ] **Cambio en `paginas_no_indexadas`.** Ahora son las páginas sin ningún fragmento indexable (antes, las ilegibles). Para `d41480…` es `[4]`, no `[3, 4]`. La prueba `test_entrega.test_fragmentos_sirven_para_busqueda_y_citas` espera `[3, 4]` y debe pasar a `[4]` (el rol 3 no edita código del rol 2). El aviso "Hay páginas incompletas o ilegibles" se mantiene mientras haya alguna página no indexada.
- [ ] Recalcular los casos o evaluaciones que dependan de la cobertura de esa modificación. El documento sigue en `requiere_revision`, con la advertencia "Menciona un anexo de 11 hojas que no está cargado".

Por defecto, si no hay respuesta, se asume que el rol 2 reimporta y conserva las alertas de cobertura de esa modificación.

## Actualización de R3: tablas de descripción (17 de noviembre de 2026)

El paquete [`empresa_demo.zip`](../../entregables/recuperacion/empresa_demo.zip) se regeneró con la extracción de tablas de `pdfplumber`: el cronograma 2.2 y las tablas de parámetros salen con sus filas unidas (`| numeral | título | texto |`) y no con las columnas intercaladas. Ver [`Corpus_IGSS.md`](../ingesta/Corpus_IGSS.md).

- [ ] **Reimportar** con `make importar`. Los `chunk_id` previos no se conservan: son posicionales y cambiaron. Si el índice conserva ids vivos, limpiarlos o recrearlos para los seis documentos.
- [ ] Ahora son **890 indexables y 4 excluidos** (antes 1006 y 4). Por documento: 399 con 189, 363 con 190, 222 bases con 158, 222 modificación 1 con 8 (más 4 excluidos por `ruido_ocr`), 327 con 154 y 368 con 191. En la importación se leyeron `base` 1077 y `mejorada` 890.
- [ ] Equivalencias de ids viejos a nuevos en [`equivalencias_r3.json`](../../src/licigt/ingesta/equivalencias_r3.json); `python -m licigt.ingesta.migrar_ids migrar --tabla ... archivos` los reemplaza con vista previa. Los fragmentos OCR de la modificación 1 pasan a `:00006` a `:00012`.
- [ ] Los casos por página (`casos_desarrollo.json`) siguen siendo válidos: cada tabla se mantiene en su página y no citan `chunk_id`.
- [ ] `test_entrega` y cualquier prueba que cuente fragmentos (1006, 179, 16 o 20 por documento) pueden requerir ajustar los conteos; `paginas_no_indexadas` no cambia (`[4]` para la modificación 1). Recalcular las métricas de recuperación, porque las secciones y la cantidad de fragmentos cambian.
- [ ] El inventario trae el campo opcional `extraccion` por documento; es aditivo y puede ignorarse.

Por defecto, si no hay respuesta, se asume que el rol 2 reimporta y recalcula sus métricas con el paquete nuevo.
