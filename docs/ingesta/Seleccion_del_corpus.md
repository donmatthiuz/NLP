# Selección propuesta para el banco de evaluación

**Revisión:** 14 de noviembre de 2026. La [sección de evaluación del anteproyecto](../anteproyecto/Anteproyecto.md#12-evaluación) propone 3 a 5 licitaciones de medicamentos y al menos 20 casos. Esta selección busca cubrir los casos documentales con pocos expedientes; la suite de seguridad y las preguntas sin respuesta se diseñan por separado.

| Prioridad | Evento y fuente oficial | Archivos | Aporte al banco |
|---|---|---|---|
| Ya descargado | [399-IGSS-2026](https://www.igssgt.org/wp-content/uploads/2026/11/LICITACION-PUBLICA-DA-No.-399-IGSS-2026.pdf), multivitamínico prenatal, código 432 | Bases integradas, 36 páginas | Requisitos, cronograma, anexos, preguntas directas y compuestas. |
| Ya descargado | [363-IGSS-2026](https://www.igssgt.org/wp-content/uploads/2026/11/LICITACION-PUBLICA-DA-No.-363-IGSS-2026.pdf), metimazol, código 345 | Bases integradas, 36 páginas | Identificadores exactos y comprobación de que no se mezclan respuestas de eventos similares. |
| Descargado | [222-IGSS-2023: bases](https://www.igssgt.org/wp-content/uploads/2026/10/222-IGSS-2023.pdf) y [modificación 1](https://www.igssgt.org/wp-content/uploads/2026/10/LICITACION-DA-No.-222-IGSS-2023-IGSS.pdf), omalizumab, código 10527 | Bases, 35 páginas; modificación, 4 páginas | Dos casos temporales auténticos: recepción de ofertas del 31 de julio al 6 de octubre de 2023; solvencia patronal con pago operado desde el 31 de mayo al 31 de julio de 2023. También ejercita cronograma en tabla y citas a ambos documentos. |
| Descargado | [327-IGSS-2023](https://www.igssgt.org/wp-content/uploads/2026/10/LICITACION-PUBLICA-DA-No.-327-IGSS-2023-IGSS.pdf), lenalidomida, **sin código IGSS** | Bases integradas, 37 páginas | Comprobar que el sistema no invente un código, consultas sobre presentación y nombre comercial, y condiciones especiales y anexos del expediente. |
| Descargado como quinto evento | [368-IGSS-2026](https://www.igssgt.org/wp-content/uploads/2026/11/LICITACION-PUBLICA-DA-No.-368-IGSS-2026.pdf), amfotericina B, código 10583 | Bases integradas, 36 páginas | Conjunto de prueba separado con concentración, presentación y volumen de un inyectable. Su estructura se parece a la de las dos bases iniciales. |

**Núcleo recomendado:** cuatro licitaciones y cinco PDF. Con el quinto evento serían cinco licitaciones y seis PDF. Los PDF de 2023 son históricos: sus fechas sirven para evaluación de versiones, no para preparar una oferta actual.

## Evidencia y límites

- Los enlaces de 222 y 327 corresponden a archivos oficiales actuales de `igssgt.org`; se comprobó que responden como PDF y se revisó su texto con Poppler. La [fila del portal de 2023](https://www.igssgt.org/proveedores/?y=2023) enlaza la modificación de 222; las bases se localizaron aparte en el mismo dominio. Los enlaces antiguos indexados bajo `/2023/` devolvieron HTTP 404 durante esta revisión.
- La modificación de 222 identifica el mismo número de evento y declara los cambios en los numerales 2.2 y 2.7. Debe cargarse como `modificacion`, vinculada a las bases, y conservar la versión oficial separada de `version_ingesta`.
- Los dos PDF iniciales comparten plantilla. El par de 222 agrega comparación temporal y una presentación distinta; 327 añade un caso sin código IGSS. El quinto evento aporta diversidad técnica, aunque no una plantilla nueva.
- Las preguntas sin respuesta se obtienen formulando preguntas sobre información ausente en el corpus; no requieren un PDF incompleto. Las pruebas de inyección, acceso cruzado y citas falsas usan la suite adversaria separada que define el anteproyecto.
- Esta selección no confirma que se haya reunido todo el historial de anexos, aclaraciones o modificaciones de cada evento. Antes de fijar los 20 casos deben registrarse los documentos efectivamente disponibles y sus faltantes.

**Estado local:** los seis PDF de los cinco eventos están en `data/ingesta/descargas_igss/` y ya se procesaron con la ingesta; ver el [inventario de archivos y hashes](Corpus_IGSS.md). El [paquete para el rol 2](../../entregables/recuperacion/README.md) contiene originales, manifiestos y fragmentos preparados.

El descargador por lote consulta la página del año correspondiente. Para 222 se usó `--pdf-adicional` con las bases oficiales, porque la fila del portal de 2023 enlaza solo la modificación.
