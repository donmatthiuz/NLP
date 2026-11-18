# Pendientes del rol 1: ingesta de documentos

**Estado al 18 de noviembre de 2026** (puntos 1, 2 y 4 actualizados con las rondas R1 a R5 y C20; la revisión completa queda para la revisión retrospectiva de `docs/Pendientes.md`). Este documento registra el trabajo que falta para completar la ingesta prevista en el [anteproyecto](../anteproyecto/Anteproyecto.md#flujo-de-ingesta) y las [responsabilidades del rol 1](../roles/Asignacion_de_roles.md#rol-1--ingesta-y-documentos). La elección del almacenamiento de despliegue corresponde al equipo; aquí se documentan MinIO y la alternativa Google Cloud Storage (GCS).

## Lo que ya funciona

- Se descargaron e ingirieron seis PDF oficiales de cinco eventos del IGSS. El [inventario](Corpus_IGSS.md) registra origen, SHA-256, `doc_id`, estado y páginas.
- La ingesta valida PDF y procedencia, guarda originales sin sobrescribir, extrae y segmenta texto, conserva metadatos por página y señala páginas de calidad insuficiente e instrucciones sospechosas.
- El [paquete para el rol 2](../../entregables/recuperacion/README.md) contiene PDF, manifiestos y 1003 fragmentos indexables con rutas internas relativas. Su prueba de aceptación verifica integridad, referencias y una consulta de ejemplo.
- Existe un adaptador de MinIO en [`storage.py`](../../src/licigt/ingesta/storage.py). No se ha verificado contra una instancia de despliegue.

## Pendientes propios del rol 1

### 1. Completar la evidencia del evento 222 — prioridad alta

- [x] Instalar o habilitar Tesseract con el idioma `spa` y extraer de nuevo las páginas 3 y 4 de la modificación 1. Hecho en R1: la página 3 aporta `:00006` a `:00008` y la 4 queda como `ruido_ocr` ([Corpus_IGSS](Corpus_IGSS.md), "Límite de cobertura"). La página 3 contiene una aprobación de cambios; actualmente no genera fragmentos.
- [x] Añadir una operación de **reextracción del PDF original** (hecho en R1: `reextraer.py`) que preserve `doc_id`, `version_ingesta` y SHA-256 y actualice páginas, alertas y fragmentos. [`reprocess()`](../../src/licigt/ingesta/pipeline.py) solo vuelve a segmentar el texto previamente guardado: no ejecuta OCR. Repetir `ingest()` con el mismo PDF devuelve la carga existente por deduplicación.
- [x] Buscar el anexo oficial de 11 hojas (no se encontró; la cobertura incompleta queda explícita en el paquete y en el panel de documentos de la web) mencionado en la página 4 y cargarlo como documento relacionado si se encuentra. Si no aparece, mantener explícita la cobertura incompleta; OCR por sí solo no demuestra que el expediente esté completo.
- [x] Revisar el texto OCR contra las imágenes de las páginas, volver a generar el ZIP y ejecutar las pruebas de ingesta y de entrega (R1; el ZIP vigente es el de R5).

**Hecho cuando:** el inventario refleja qué páginas son legibles y qué anexos se cargaron; cada nuevo fragmento cita el PDF y la página correctos. Si el anexo falta, el paquete conserva la advertencia para que el sistema se abstenga cuando la pregunta dependa de él.

### 2. Corregir la clasificación del conector automático — prioridad alta

- [x] Evitar que [`ingest_event()`](../../src/licigt/ingesta/automatic.py) registre siempre el primer PDF enlazado como `bases_integradas` y `bases`. En el evento 222, el enlace de la ficha lleva a una modificación.
- [x] Exigir un tipo documental explícito (R1: `automatic.py` falla sin `tipo_documento` y exige `relacion_documental` en modificaciones, aclaraciones y anexos; aviso al rol 4 en `docs/plataforma/Avisos_del_rol_1.md`) o una clasificación verificable antes de ingerir cada enlace. Conservar por separado bases, anexos, aclaraciones y modificaciones, y registrar su relación sin confundir modificación oficial con `version_ingesta`.
- [x] Probar al menos un evento con bases y modificación y uno sin código IGSS (`test_automatic.py`: `test_evento_con_bases_y_modificacion` y los casos de tipo y relación; el 327 del corpus no tiene código IGSS). La carga curada del corpus ya tiene esos tipos correctos; el pendiente afecta al conector general.

**Hecho cuando:** el conector no puede etiquetar automáticamente una modificación como bases y el manifiesto muestra el tipo y relación documental correctos.

### 3. Entregar eventos de calidad al rol 4 — prioridad media

- [ ] Acordar con el rol 4 un registro estructurado de carga: `tenant_id`, `evento_id`, `doc_id`, SHA-256, estado, páginas legibles, advertencias y fecha. Evitar guardar credenciales o texto completo del PDF en la auditoría.
- [ ] Hacer que la capa de aplicación resuelva empresa, evento y permisos desde la sesión autenticada antes de llamar a ingesta. La CLI actual recibe `--tenant-id` y sirve para desarrollo.
- [ ] Probar un fallo de carga y una página ilegible para confirmar que el rol 4 recibe el estado y puede mostrarlo al analista.

**Hecho cuando:** la aplicación registra éxitos y fallos de ingesta y el rol 4 puede consultar las alertas sin leer el manifiesto manualmente.

### 4. Revisar calidad y estrategia de segmentación con el rol 2 — prioridad media

- [ ] Muestrear en los PDF reales citas de requisitos, fechas, códigos IGSS y tablas; comparar cada fragmento con la página original. La prueba actual comprueba consistencia del paquete, pero no evalúa exhaustivamente si la extracción entendió cada tabla.
- [x] Acordar con el rol 2 la línea base de ventanas de 120 tokens y el tokenizer del modelo. Medido el 18 de noviembre con los tokenizadores de las revisiones fijadas: en los 893 fragmentos, p50 de 61 tokens, p95 de 410 y máximo de 615; `bge-m3` y `bge-reranker-v2-m3` aceptan 8192, así que nada se trunca. La línea base usa ventanas de 120 tokens a propósito (`ventanas_base`). Los fragmentos actuales usan hasta 600 palabras con solapamiento de 90 como aproximación para la versión mejorada; se debe comprobar que el modelo de embeddings no trunque pasajes silenciosamente.

**Hecho cuando:** se documentan ejemplos revisados y ambas estrategias de segmentación tienen tamaño medido con el tokenizer elegido.

## Almacenamiento para el despliegue: decisión pendiente con el rol 4

El trabajo local usa [`LocalOriginalStore`](../../src/licigt/ingesta/storage.py). El anteproyecto propone MinIO para conservar los PDF originales. **Google Cloud Storage también puede cumplir esa función**: ofrece objetos en buckets, control de acceso y [versionado por generación](https://docs.cloud.google.com/storage/docs/object-versioning). PostgreSQL y los índices del rol 2 siguen siendo componentes separados.

| Alternativa | Trabajo necesario |
|---|---|
| MinIO | El rol 4 prepara endpoint, bucket privado, versionado y credenciales. El rol 1 prueba el adaptador existente con carga, lectura, hash y segunda versión sin sobrescritura. |
| Google Cloud Storage | El rol 4 prepara un bucket privado, permisos IAM y credenciales de aplicación. El rol 1 añade un adaptador `GCSOriginalStore` con el mismo contrato `put(source, key)`, registra el identificador de generación y prueba carga, lectura, hash y no sobrescritura. |

Si se elige GCS, el plan técnico es:

1. Usar la [biblioteca oficial de Python](https://docs.cloud.google.com/storage/docs/uploading-objects) y [Application Default Credentials](https://docs.cloud.google.com/storage/docs/authentication), sin claves en el repositorio.
2. Mantener la clave lógica actual `igss/<tenant_id>/<evento_id>/<document_key>/vN/<doc_id>.pdf`. Crear el objeto con una condición de generación para evitar sobrescrituras y conservar la generación devuelta como referencia de la versión exacta.
3. Aplicar permisos mínimos de lectura y escritura sobre el bucket; el acceso del usuario final al PDF debe pasar por la aplicación y sus permisos de empresa. Ver [roles IAM de Cloud Storage](https://docs.cloud.google.com/storage/docs/access-control/iam-roles).
4. Actualizar el exportador portátil: hoy requiere originales locales. En despliegue, el rol 1 puede descargar temporalmente el objeto autorizado para construir el ZIP, o el equipo puede dar al rol 2 acceso controlado al bucket. El ZIP versionado actual sigue sirviendo para desarrollo.
5. Si GCS reemplaza a MinIO en el sistema final, actualizar el anteproyecto y el diagrama de arquitectura para que nombren el proveedor realmente usado.

El adaptador MinIO actual usa la API de MinIO. GCS ofrece [interoperabilidad con algunas herramientas S3 mediante XML API y claves HMAC](https://docs.cloud.google.com/storage/docs/interoperability), pero **no se ha comprobado que este adaptador funcione con GCS**. La implementación propuesta usa el cliente nativo de Google Cloud Storage.

**Hecho cuando:** el equipo elige una alternativa, los originales se cargan y recuperan en una instancia real con el mismo SHA-256, no se sobrescriben, los permisos funcionan y la arquitectura escrita coincide con el despliegue.

## Dependencias de otros roles

- **Rol 2:** importa `chunks.jsonl` y construye `tsvector`, embeddings e índices `pgvector`; valida búsqueda y citas sobre los fragmentos entregados.
- **Rol 4:** prepara autenticación, permisos por empresa, auditoría e infraestructura compartida. La ingesta debe integrarse con esos controles, no decidir permisos a partir de un `tenant_id` enviado por el usuario.

## Comprobación del entregable actual

Desde la raíz del repositorio:

```bash
PYTHONPATH=src python -m unittest discover -s src/licigt/ingesta/tests -v
python -m unittest discover -s src/licigt/recuperacion/tests -v
```
