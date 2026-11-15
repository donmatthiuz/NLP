# Ingesta de documentos del IGSS — rol 1

**Integrante:** ______________________________

Este módulo implementa el [flujo de ingesta del anteproyecto](../../../docs/anteproyecto/Anteproyecto.md#flujo-de-ingesta): registro de evento, validación del PDF, SHA-256, conservación del original, extracción por página, OCR opcional, control de calidad, segmentación y manifiesto para el rol 2. El NOG es una referencia externa opcional; **`evento_id` es la clave operativa**.

## Corpus y procedencia

La fuente principal es [Proveedores del IGSS](https://www.igssgt.org/proveedores/) y los PDF oficiales alojados en `igssgt.org`. El MVP usa carga manual de archivos obtenidos allí. El conector `automatic.py` permite descargar un evento específico desde la página de proveedores como extensión opcional; no rastrea todo el portal ni consulta GUATECOMPRAS.

Se verificaron y cargaron dos fuentes iniciales del anteproyecto en `data/ingesta` bajo el espacio ficticio `empresa_demo`:

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

`--fecha-documento`, `--fecha-publicacion` y `--fecha-descarga` son opcionales. Una fecha no verificada queda en `null`; la fecha de descarga no sustituye a la fecha oficial. Se aceptan `--unidad-requirente`, `--nog-referencia`, `--identificador-version-oficial` y `--relacion-documental` cuando se conocen. La API del rol 3 debe derivar `tenant_id` de la sesión autenticada; no debe aceptar una empresa elegida libremente por un cliente externo.

Un mismo PDF y `document_key` dentro de un evento se deduplican por SHA-256. Si cambia el archivo, se crea una nueva `version_ingesta` y se conserva el original previo. Esa versión técnica no implica que una aclaración sustituya legalmente las bases. Los documentos modificatorios se guardan por separado y pueden señalar su `relacion_documental`.

## Descarga opcional de un evento del IGSS

```bash
PYTHONPATH=src python -m licigt.ingesta.automatic \
  --numero-evento 399-IGSS-2026 --tenant-id empresa_demo \
  --data-dir data/ingesta
```

El conector lee la fila del evento en el portal, registra número, año, modalidad, descripción, unidad y código IGSS cuando aparecen, descarga el PDF oficial y llama al mismo pipeline. Si el portal cambia de estructura o enlaza a otra plataforma, informa el error; no inventa metadatos ni sigue redirecciones fuera de `igssgt.org`. Si se omite `--evento-id`, genera uno estable para esa empresa y evento. Para documentos adicionales del mismo expediente, usa carga manual con **el mismo** `evento_id`.

## Entrega al rol 2

El registro está en `data/ingesta/igss_ingesta.sqlite3`, los originales en `data/ingesta/originales/igss/<tenant_id>/<evento_id>/` y los manifiestos en `data/ingesta/manifiestos_igss/<doc_id>.json`. El manifiesto conserva páginas extraídas, advertencias y `cobertura`. Cada fragmento incluye `tenant_id`, `evento_id`, número y año institucional, tipo, versión, fechas diferenciadas, URL, hash, página del PDF, página impresa cuando se puede reconocer y texto. `nog_referencia` no se usa para filtrar.

El rol 2 debe indexar solo fragmentos con `indexable=true` y filtrar siempre por `tenant_id`, `evento_id` y el rol autorizado. Un archivo que parece solo convocatoria o cuyo número de evento no coincide con el declarado se marca `requiere_revision` y sus fragmentos no son indexables. Las páginas ilegibles se excluyen. El manifiesto no demuestra que el expediente esté completo: `cobertura.tipos_cargados` enumera solo los tipos efectivamente cargados.

La segmentación mejorada conserva secciones y tablas; cuando divide una tabla larga, repite su encabezado y lo registra como `encabezado_tabla`. Los encabezados y pies de página repetidos se quitan **solo de los fragmentos**, no del texto original por página. Las ventanas largas usan 600 palabras con 90 de solapamiento como aproximación a 800/120 tokens. El rol 2 debe aplicar el tokenizer real del modelo para la línea base de 120 tokens y comprobar truncamiento. Para reconstruir fragmentos tras un cambio de segmentación sin alterar el original ni `doc_id`, existe `IngestionService.reprocess(doc_id)`.

La carga compara la extracción normal de Poppler con la opción `-hidden` y registra en `security_scan` las páginas con texto oculto y las páginas con patrones de instrucciones ajenas al documento. Los fragmentos de una página sospechosa quedan fuera del índice y el documento requiere revisión. El patrón es una alerta auxiliar: **todos** los fragmentos se entregan como datos no confiables al rol 2, incluso cuando no se detectó nada. La API que exponga la carga debe resolver permisos de empresa, evento y rol antes de invocar este módulo; la CLI es una herramienta de desarrollo.

## Pruebas

```bash
PYTHONPATH=src python -m unittest discover -s src/licigt/ingesta/tests -v
```

Ver [asignación de roles](../../../docs/roles/Asignacion_de_roles.md#rol-1--ingesta-y-documentos).
