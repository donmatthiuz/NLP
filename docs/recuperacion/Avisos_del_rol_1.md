# Avisos del rol 1 para el rol 2

**Estado al 18 de noviembre de 2026.** Las reimportaciones están hechas con el paquete R6 vigente (625 fragmentos indexables); lo que sigue abierto son las listas guardadas con ids desplazados, que la herramienta de migración no toca en PostgreSQL. El paquete [`empresa_demo.zip`](../../entregables/recuperacion/empresa_demo.zip) cambió: la modificación 1 del evento 222 ahora tiene sus páginas 3 y 4 recuperadas por OCR.

## Qué hacer

- [x] **Reimportar** con `make importar` (la importación es idempotente).
- [x] Los `chunk_id` previos no cambian: los 1003 fragmentos anteriores son idénticos.
- [x] Hay fragmentos nuevos en `d41480e5b0ce4c16bf18f66225ada2dc`: `:00014` a `:00016` son indexables (página 3); `:00017` a `:00020` (página 4) se excluyen como `ruido_ocr`. Total: 1006 indexables y 4 excluidos.
- [x] **Cambio en `paginas_no_indexadas`.** Ahora son las páginas sin ningún fragmento indexable (antes, las ilegibles). Para `d41480…` es `[4]`, no `[3, 4]`. La prueba `test_entrega.test_fragmentos_sirven_para_busqueda_y_citas` espera `[3, 4]` y debe pasar a `[4]` (el rol 3 no edita código del rol 2). El aviso "Hay páginas incompletas o ilegibles" se mantiene mientras haya alguna página no indexada.
- [x] Recalcular los casos o evaluaciones que dependan de la cobertura de esa modificación. El documento sigue en `requiere_revision`, con la advertencia "Menciona un anexo de 11 hojas que no está cargado".

Por defecto, si no hay respuesta, se asume que el rol 2 reimporta y conserva las alertas de cobertura de esa modificación.

## Actualización de R3: tablas de descripción (17 de noviembre de 2026)

El paquete [`empresa_demo.zip`](../../entregables/recuperacion/empresa_demo.zip) se regeneró con la extracción de tablas de `pdfplumber`: el cronograma 2.2 y las tablas de parámetros salen con sus filas unidas (`| numeral | título | texto |`) y no con las columnas intercaladas. Ver [`Corpus_IGSS.md`](../ingesta/Corpus_IGSS.md).

- [x] **Reimportar** con `make importar`. Los `chunk_id` previos no se conservan: son posicionales y cambiaron. Si el índice conserva ids vivos, limpiarlos o recrearlos para los seis documentos.
- [x] Ahora son **890 indexables y 4 excluidos** (antes 1006 y 4). Por documento: 399 con 189, 363 con 190, 222 bases con 158, 222 modificación 1 con 8 (más 4 excluidos por `ruido_ocr`), 327 con 154 y 368 con 191. En la importación se leyeron `base` 1077 y `mejorada` 890.
- [ ] Equivalencias de ids viejos a nuevos en [`equivalencias_r3.json`](../../src/licigt/ingesta/equivalencias_r3.json); `python -m licigt.ingesta.migrar_ids migrar --tabla ... archivos` los reemplaza con vista previa. Los fragmentos OCR de la modificación 1 pasan a `:00006` a `:00012`. Abierto: las listas guardadas en PostgreSQL no se migran con esta herramienta (revisión retrospectiva).
- [x] Los casos por página (`casos_desarrollo.json`) siguen siendo válidos: cada tabla se mantiene en su página y no citan `chunk_id`.
- [x] `test_entrega` y cualquier prueba que cuente fragmentos (1006, 179, 16 o 20 por documento) pueden requerir ajustar los conteos; `paginas_no_indexadas` no cambia (`[4]` para la modificación 1). Recalcular las métricas de recuperación, porque las secciones y la cantidad de fragmentos cambian.
- [x] El inventario trae el campo opcional `extraccion` por documento; es aditivo y puede ignorarse.

Por defecto, si no hay respuesta, se asume que el rol 2 reimporta y recalcula sus métricas con el paquete nuevo.

## Actualización de R5: modificaciones y márgenes (17 de noviembre de 2026, pendiente de que el usuario copie el ZIP)

El paquete candidato cambia solo tres cosas: la sección de los fragmentos de las modificaciones (cada "Punto N:" que nombra un numeral lleva ese numeral, p. ej. `2.7 LISTADO DE DOCUMENTOS QUE DEBERÁ CONTENER LA PLICA`), el encabezado y el pie repetidos de los documentos cortos (ya no están en el índice) y la fila `f)` de la tabla de documentos del 222 y del 327 (una sola celda: `Fotocopia legible legalizada de los documentos siguientes:`).

- [x] **Reimportar** con `make importar` cuando se publique el ZIP. Pasan de 892 a 893 fragmentos; solo cambian ids del 222 (modificación 1: `:00001` a `:00008`) y dos de otros documentos por la fila `f)` (`:00149` y `:00154`).
- [ ] Al reimportar, las listas guardadas que citen ids desplazados deben migrarse con [`equivalencias_r5.json`](../../src/licigt/ingesta/equivalencias_r5.json) (cubre todos los ids cuyo texto cambia, no solo los citados en el repo): `python -m licigt.ingesta.migrar_ids migrar --tabla ... archivos`. Las entradas en estado `revision` no se reemplazan solas y las resuelve una persona (la modificación 1, `:00001`, `:00004` y `:00005`, se partió o perdió el encabezado). Abierto: las listas guardadas en PostgreSQL no se migran con esta herramienta (revisión retrospectiva).
- [x] La alerta de conflicto por numeral (`NUMERAL_MODIFICADO`, `_alertas`) no cambia. Con la sección correcta, el fragmento de la solvencia patronal de la modificación queda bajo el numeral 2.7.

Por defecto, si no hay respuesta, se asume que el rol 2 reimporta y migra las listas con esa tabla.

## Actualización de R6: pies con número, índice y títulos (18 de noviembre de 2026, ZIP ya publicado)

El paquete pasa de 893 a 625 fragmentos indexables. El texto y las páginas no cambian, salvo:

- **Pies con número y números de página sueltos:** se quitaron ("9 Extensión: 99175"). Antes, 177 fragmentos tenían un pie como sección y 98 eran solo un pie.
- **Índice de la página 3:** sus entradas ("1. TERMINOLOGÍA"… "6. ANEXOS") forman un solo fragmento, con "Sin sección".
- **Títulos:** solo cuentan como sección los numerales de varios niveles, los números simples con texto en mayúsculas y los títulos con palabra clave que no son citas. Las líneas de lista ("8. Clasificación…") y las citas partidas ("3 del Decreto…", "Numeral 15 del…") ya no abren sección: los literales del 2.7 quedan en 2.7.
- **Fragmentos más grandes:** sin esos cortes falsos se juntan los vecinos de la misma sección. La mediana pasa de 61 a 96 tokens de bge-m3 y el máximo de 615 a 699, lejos del límite de 8192.
- **Modificación del 222:** las páginas OCR no se funden.
  - La página 4 sigue sin indexar (`paginas_no_indexadas` [4]).
  - De la página 3 solo queda indexable el párrafo de la aprobación (`d41480…:00014`).
  - El membrete, la fecha de la resolución y dos órdenes de trámite quedan como `ruido_ocr` (límite declarado en `Corpus_IGSS.md`).

- [x] **Reimportar** con `make importar` (hecho con el paquete R6, 625 fragmentos).
- [ ] **Listas guardadas:** las que citen ids desplazados se migran con [`equivalencias_r6.json`](../../src/licigt/ingesta/equivalencias_r6.json) (881 ids: 466 idénticos, 293 contenidos y 122 en revisión). Las entradas en `revision` las resuelve una persona; `d41480…:00009` no tiene equivalente. Abierto: las listas guardadas en PostgreSQL no se migran con esta herramienta (revisión retrospectiva).
- [x] **Alertas:** `NUMERAL_MODIFICADO` y `_alertas` no cambian; con las secciones correctas, más fragmentos quedan bajo su numeral real.

Por defecto, si no hay respuesta, se asume que el rol 2 reimporta y migra las listas con esa tabla.
