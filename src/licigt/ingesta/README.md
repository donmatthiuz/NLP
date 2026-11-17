# Ingesta de documentos del IGSS — rol 1

**Integrante:** ______________________________

Este módulo implementa el [flujo de ingesta del anteproyecto](../../../docs/anteproyecto/Anteproyecto.md#flujo-de-ingesta): registro de evento, validación del PDF, SHA-256, conservación del original, extracción por página, OCR opcional, control de calidad, segmentación y manifiesto para el rol 2. El NOG es una referencia externa opcional; **`evento_id` es la clave operativa**.

## Corpus y procedencia

La fuente principal es [Proveedores del IGSS](https://www.igssgt.org/proveedores/) y los PDF oficiales alojados en `igssgt.org`. El MVP usa carga manual de archivos obtenidos allí. El conector `automatic.py` permite descargar un evento específico desde la página de proveedores como extensión opcional; no rastrea todo el portal ni consulta GUATECOMPRAS.

Se verificaron y cargaron seis PDF de cinco eventos en `data/ingesta` bajo el espacio ficticio `empresa_demo`. Dos fuentes iniciales del anteproyecto son:

| Evento | Código IGSS | Documento oficial |
|---|---:|---|
| 399-IGSS-2026 | 432 | [Multivitamínico prenatal con flúor](https://www.igssgt.org/wp-content/uploads/2026/11/LICITACION-PUBLICA-DA-No.-399-IGSS-2026.pdf) |
| 363-IGSS-2026 | 345 | [Metimazol, tableta de 5 mg](https://www.igssgt.org/wp-content/uploads/2026/11/LICITACION-PUBLICA-DA-No.-363-IGSS-2026.pdf) |

Los hashes, identificadores, fechas y resultados de extracción figuran en el [inventario del corpus](../../../docs/ingesta/Corpus_IGSS.md).

`data/` está excluido de Git para evitar publicar originales, manifiestos o datos de trabajo por accidente. Cada empresa recibe su propia copia lógica y su propio registro.

## Dependencias

- Python 3.11 o posterior y `poppler-utils` (`pdfinfo`, `pdftotext`, `pdftohtml`; `pdftoppm` para OCR).
- OCR opcional: Tesseract con idioma `spa`. Sin OCR, una página con poco texto queda marcada `incompleta`.
- Almacenamiento local por defecto. Para MinIO: `pip install -r src/licigt/ingesta/requirements.txt` y configurar `LICIGT_MINIO_ENDPOINT`, `LICIGT_MINIO_BUCKET`, `LICIGT_MINIO_ACCESS_KEY`, `LICIGT_MINIO_SECRET_KEY` y, si aplica, `LICIGT_MINIO_SECURE`. El bucket debe existir y tener versionado habilitado.

## Carga manual

```bash
PYTHONPATH=src python -m licigt.ingesta documento.pdf \
  --tenant-id empresa_demo --evento-id evento_399 \
  --numero-evento 399-IGSS-2026 --anio 2026 \
  --modalidad "Licitación Pública DA" \
  --document-key bases_integradas --tipo-documento bases \
  --titulo "Multivitamínico prenatal con flúor" \
  --url-origen "https://www.igssgt.org/wp-content/uploads/2026/11/LICITACION-PUBLICA-DA-No.-399-IGSS-2026.pdf" \
  --codigo-igss 432 --data-dir data/ingesta
```

`--fecha-documento`, `--fecha-publicacion`, `--fecha-ficha` y `--fecha-descarga` son opcionales. Una fecha no verificada queda en `null`; la fecha de la ficha del portal y la fecha de descarga no sustituyen a la fecha oficial de publicación del PDF. Se aceptan `--unidad-requirente`, `--nog-referencia`, `--identificador-version-oficial` y `--relacion-documental` cuando se conocen. La API del rol 3 debe derivar `tenant_id` de la sesión autenticada; no debe aceptar una empresa elegida libremente por un cliente externo.

Un mismo PDF y `document_key` dentro de un evento se deduplican por SHA-256. Si cambia el archivo, se crea una nueva `version_ingesta` y se conserva el original previo. Esa versión técnica no implica que una aclaración sustituya legalmente las bases. Los documentos modificatorios se guardan por separado y pueden señalar su `relacion_documental`.

## Descargar PDF sin iniciar la ingesta

Desde la raíz del repositorio, este comando descarga los PDF oficiales de los dos eventos iniciales:

```bash
PYTHONPATH=src python -m licigt.ingesta.download \
  --numero-evento 399-IGSS-2026 \
  --numero-evento 363-IGSS-2026 \
  --data-dir data/ingesta
```

Puedes repetir `--numero-evento` para otros eventos publicados en [Proveedores del IGSS](https://www.igssgt.org/proveedores/). Los archivos quedan en `data/ingesta/descargas_igss/<numero_evento>/<sha256>.pdf`, con un JSON contiguo que registra URL, fecha, código IGSS y hash. En ese JSON, `archivo` es el nombre del PDF relativo a la ubicación del propio JSON. El comando descarga todos los enlaces PDF oficiales encontrados en la fila de cada evento, valida la cabecera PDF y el límite de 50 MB por archivo. Si el contenido cambia, conserva otra copia bajo su nuevo hash; si no cambia, indica `ya_existia`. Este paso no crea eventos, fragmentos ni índices.

Para repetir la descarga del [corpus seleccionado](../../../docs/ingesta/Seleccion_del_corpus.md), que incluye eventos de 2023 y las bases de 222 no enlazadas en su ficha:

```bash
PYTHONPATH=src python -m licigt.ingesta.download \
  --numero-evento 399-IGSS-2026 \
  --numero-evento 363-IGSS-2026 \
  --numero-evento 222-IGSS-2023 \
  --numero-evento 327-IGSS-2023 \
  --numero-evento 368-IGSS-2026 \
  --pdf-adicional '222-IGSS-2023:bases:https://www.igssgt.org/wp-content/uploads/2026/10/222-IGSS-2023.pdf' \
  --data-dir data/ingesta
```

El descargador consulta la vista del año correspondiente (`?y=2023` o `?y=2026`). En cada JSON, `fecha_ficha` conserva la fecha que muestra la fila del portal y `fecha_publicacion` queda sin dato mientras no se verifique una fecha propia del PDF; la fecha de la ficha de la modificación de 222 no se atribuye a sus bases.

## Descargar e ingerir un evento del IGSS

```bash
PYTHONPATH=src python -m licigt.ingesta.automatic \
  --numero-evento 399-IGSS-2026 --tenant-id empresa_demo \
  --tipo-documento bases --document-key bases_integradas \
  --data-dir data/ingesta
```

El conector lee la fila del evento en el portal, registra número, año, modalidad, descripción, unidad y código IGSS cuando aparecen, descarga el PDF oficial y llama al mismo pipeline. El tipo documental es obligatorio (`--tipo-documento`, `--document-key` y, para modificación, aclaración o anexo, `--relacion-documental`); si un PDF declarado como bases tiene portada de modificación, queda en revisión y sin fragmentos indexables. Si el portal cambia de estructura o enlaza a otra plataforma, informa el error; no inventa metadatos ni sigue redirecciones fuera de `igssgt.org`. Si se omite `--evento-id`, genera uno estable para esa empresa y evento. Para documentos adicionales del mismo expediente, usa carga manual con **el mismo** `evento_id`.

## Entrega al rol 2

Para reproducir la ingesta del corpus seleccionado a partir de las seis descargas verificadas y crear el paquete de intercambio:

```bash
PYTHONPATH=src python -m licigt.ingesta.prepare_corpus \
  --tenant-id empresa_demo --data-dir data/ingesta
PYTHONPATH=src python -m licigt.ingesta.handoff \
  --tenant-id empresa_demo --data-dir data/ingesta \
  --output entregables/recuperacion/empresa_demo.zip
```

El ZIP contiene `chunks.jsonl` (un fragmento indexable por línea), `inventario.json` (procedencia, SHA-256, estado, cobertura, versiones, alertas y recuentos), `originales/<doc_id>.pdf`, `manifiestos/<doc_id>.json` y los JSON de descarga en `procedencia/<doc_id>.json` cuando existen. Dentro del ZIP, todas las rutas de archivo son relativas a su raíz. El SHA-256 de `chunks.jsonl` figura en el inventario; cada original se verifica contra su hash antes de empaquetarlo. Esta entrega está en [`entregables/recuperacion`](../../../entregables/recuperacion/README.md), fuera de `data/`, para que Git pueda incluirla. El rol 2 debe importar el JSONL a PostgreSQL y generar allí `tsvector` y embeddings/`pgvector`. **El ZIP no contiene índices ni embeddings.**

El exportador lee solo documentos registrados para el `tenant_id` indicado y valida su correspondencia con los manifiestos; la CLI es de desarrollo. En producción, el rol 4 debe autorizar quién puede crear o acceder a un paquete de cada empresa. La autorización de consultas se aplica en la base y la API, no se infiere del `tenant_id` escrito en el JSONL. Para un despliegue con MinIO, los PDF pueden estar en el bucket compartido con permisos y versionado; este exportador portátil requiere originales locales.

El registro está en `data/ingesta/igss_ingesta.sqlite3`, los originales en `data/ingesta/originales/igss/<tenant_id>/<evento_id>/` y los manifiestos en `data/ingesta/manifiestos_igss/<doc_id>.json`. El manifiesto conserva páginas extraídas, advertencias y `cobertura`. Cada fragmento incluye `tenant_id`, `evento_id`, número y año institucional, tipo, versión, fechas diferenciadas, URL, hash, página del PDF, página impresa cuando se puede reconocer y texto. `nog_referencia` no se usa para filtrar.

El rol 2 debe indexar solo fragmentos con `indexable=true` y filtrar siempre por `tenant_id`, `evento_id` y el rol autorizado. El ZIP ya excluye los fragmentos `indexable=false`. Un archivo que parece solo convocatoria o cuyo número de evento no coincide con el declarado se marca `requiere_revision` y sus fragmentos no son indexables. Las páginas ilegibles no producen fragmentos. El manifiesto no demuestra que el expediente esté completo: `cobertura.tipos_cargados` enumera solo los tipos efectivamente cargados. La modificación de 222 tiene dos páginas sin texto por falta de OCR y requiere revisión.

La segmentación mejorada conserva secciones y tablas; cuando divide una tabla larga, repite su encabezado y lo registra como `encabezado_tabla`. Los encabezados y pies de página repetidos se quitan **solo de los fragmentos**, no del texto original por página. Las ventanas largas usan 600 palabras con 90 de solapamiento como aproximación a 800/120 tokens. El rol 2 debe aplicar el tokenizer real del modelo para la línea base de 120 tokens y comprobar truncamiento. Para reconstruir fragmentos tras un cambio de segmentación sin alterar el original ni `doc_id`, existe `IngestionService.reprocess(doc_id)`.

La carga compara la extracción normal de Poppler con la opción `-hidden` y registra en `security_scan` las páginas con texto oculto y las páginas con patrones de instrucciones ajenas al documento. Los fragmentos de una página sospechosa quedan fuera del índice y el documento requiere revisión. El patrón es una alerta auxiliar: **todos** los fragmentos se entregan como datos no confiables al rol 2, incluso cuando no se detectó nada. La API que exponga la carga debe resolver permisos de empresa, evento y rol antes de invocar este módulo; la CLI es una herramienta de desarrollo.

## Pruebas

```bash
PYTHONPATH=src python -m unittest discover -s src/licigt/ingesta/tests -v
```

Ver [asignación de roles](../../../docs/roles/Asignacion_de_roles.md#rol-1--ingesta-y-documentos).

Los trabajos que faltan para cerrar este módulo están en [Pendientes del rol 1](../../../docs/ingesta/Pendientes_rol_1.md).
