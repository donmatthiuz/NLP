# Ingesta y documentos — rol 1

**Integrante:** ______________________________

Aquí se implementarán la carga de PDF, el registro y hash, almacenamiento del original en MinIO, extracción por página, OCR, control de calidad, limpieza, segmentación y versionado.

**Entrada:** PDF y metadatos de licitación, fuente, fecha y empresa.

**Salida para recuperación:** fragmentos con texto, `chunk_id`, `doc_id`, NOG, página, sección, versión y visibilidad. Las páginas ilegibles deben quedar marcadas.

Ver [responsabilidades e integración](../../../docs/roles/Asignacion_de_roles.md#rol-1--ingesta-y-documentos).
