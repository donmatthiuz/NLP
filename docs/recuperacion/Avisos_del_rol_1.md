# Avisos del rol 1 para el rol 2

**Estado al 17 de noviembre de 2026.** El paquete [`empresa_demo.zip`](../../entregables/recuperacion/empresa_demo.zip) cambió: la modificación 1 del evento 222 ahora tiene sus páginas 3 y 4 recuperadas por OCR.

## Qué hacer

- [ ] **Reimportar** con `make importar` (la importación es idempotente).
- [ ] Los `chunk_id` previos no cambian: los 1003 fragmentos anteriores son idénticos.
- [ ] Hay fragmentos nuevos en `d41480e5b0ce4c16bf18f66225ada2dc`: `:00014` a `:00016` son indexables (página 3); `:00017` a `:00020` (página 4) se excluyen como `ruido_ocr`. Total: 1006 indexables y 4 excluidos.
- [ ] **Cambio en `paginas_no_indexadas`.** Ahora son las páginas sin ningún fragmento indexable (antes, las ilegibles). Para `d41480…` es `[4]`, no `[3, 4]`. La prueba `test_entrega.test_fragmentos_sirven_para_busqueda_y_citas` espera `[3, 4]` y debe pasar a `[4]` (el rol 3 no edita código del rol 2). El aviso "Hay páginas incompletas o ilegibles" se mantiene mientras haya alguna página no indexada.
- [ ] Recalcular los casos o evaluaciones que dependan de la cobertura de esa modificación. El documento sigue en `requiere_revision`, con la advertencia "Menciona un anexo de 11 hojas que no está cargado".

Por defecto, si no hay respuesta, se asume que el rol 2 reimporta y conserva las alertas de cobertura de esa modificación.
