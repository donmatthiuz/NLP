# Ingesta y documentos — rol 1

**Integrante:** ______________________________

Este módulo implementa el tramo **registro → extracción por página → control de calidad → limpieza → segmentación → metadatos y versión** del [diagrama](../../../docs/arquitectura/arquitectura.jpeg). El índice vectorial y léxico corresponde al rol 2.

## Origen de los datos

El analista puede cargar PDF de [GUATECOMPRAS](https://www.guatecompras.gt/) con su NOG y URL de origen. También existe una **extensión opcional fuera del MVP** que descubre documentos desde la ficha pública de un NOG o desde un paquete JSON del [portal oficial OCDS](https://ocds.guatecompras.gt/), descarga los PDF y los pasa por este mismo pipeline. La autenticación de quien inicia la carga debe proporcionarla la API del rol 4.

## Requisitos

* Python 3.11 o posterior.
* `poppler-utils` (`pdfinfo`, `pdftotext` y, para OCR, `pdftoppm`).
* OCR opcional: Tesseract con datos del idioma español (`spa`). Una página sin texto suficiente queda marcada `incompleta` si no hay OCR utilizable.
* MinIO opcional: `pip install -r src/licigt/ingesta/requirements.txt`. Sin variables de MinIO se usa un almacén local de desarrollo.

## Ejecución

Desde la raíz del repositorio:

```bash
PYTHONPATH=src python -m licigt.ingesta documento.pdf \
  --nog 12345678 --document-key bases --tipo-documento bases \
  --titulo "Bases de licitación" --entidad "Entidad convocante" \
  --fecha-publicacion 2026-11-14 \
  --url-origen "https://www.guatecompras.gt/" \
  --data-dir data/ingesta
```

`document-key` identifica el documento lógico dentro del NOG: por ejemplo `bases`, `anexo_01` o `aclaracion_02`. Al cargar el mismo archivo se devuelve el manifiesto existente; un archivo distinto con la misma clave genera una versión nueva. `--visibilidad privada --tenant-id EMPRESA` restringe el ámbito del registro a esa empresa. La API deberá derivar `tenant-id` de la sesión, nunca de un dato libre enviado por el usuario.

### Descarga automática por NOG

```bash
PYTHONPATH=src python -m licigt.ingesta.automatic --nog 12362662 --data-dir data/ingesta
```

El conector consulta `https://www.guatecompras.gt/concursos/consultaConcurso.aspx?nog=<NOG>`, busca enlaces a bases, anexos, aclaraciones y otros PDF del concurso y descarga únicamente archivos HTTPS del dominio `guatecompras.gt`. Si la ficha no informa título, entidad o fecha de publicación, añádelos con `--titulo`, `--entidad` y `--fecha-publicacion AAAA-MM-DD`. No se inventa una fecha faltante. La respuesta muestra los documentos ingeridos y los enlaces omitidos con su motivo.

Si tienes un paquete OCDS JSON exportado del portal oficial, puedes usarlo para descubrir metadatos y enlaces de `tender.documents`:

```bash
PYTHONPATH=src python -m licigt.ingesta.automatic --nog 12362662 \
  --ocds-json paquete.json --data-dir data/ingesta
```

El paquete debe contener una liberación del NOG solicitado y los enlaces públicos a los PDF. Esta opción evita depender del HTML de la ficha, pero la descarga de cada PDF sigue requiriendo acceso al portal. El publicador OCDS registra concursos desde 2020; para NOG anteriores se conserva la carga manual. Se limita cada ficha a 5 MB, cada PDF a 50 MB y cada NOG a 30 enlaces. El conector no usa sesión, no supera captchas ni elude controles de acceso. Si el portal devuelve HTTP 403 o 429, informa el bloqueo y detiene la descarga; se puede usar la carga manual de PDF autorizado.

### Descarga con verificación humana en Firefox

Si GUATECOMPRAS presenta un desafío de Cloudflare, inicia la interfaz local con Firefox instalado:

```bash
PYTHONPATH=src venv/bin/python -m licigt.ingesta.local_browser --data-dir data/ingesta --port 8765
```

Se abre `http://127.0.0.1:8765/` en una ventana de Firefox controlada por Selenium. Escribe el NOG, abre la ficha del concurso en la pestaña nueva y **resuelve tú el desafío**. Regresa a la pestaña local y pulsa **Descargar e ingerir PDF**. El programa utiliza esa misma sesión de Firefox para descargar los documentos; guarda los originales y los manifiestos en `data/ingesta`. Si la ficha no contiene título, entidad o fecha legibles, rellena esos campos antes de pulsar Descargar. El servidor escucha solo en `127.0.0.1` y guarda la sesión del navegador en un perfil temporal; al terminar con `Ctrl+C`, se cierra Firefox y se elimina ese perfil.

Este flujo requiere el navegador visible y acceso a internet desde esa máquina. La verificación la realiza una persona en el sitio oficial; el programa no resuelve desafíos automáticamente. Algunos enlaces del portal pueden no ser PDF directos o pueden depender de una sesión adicional; aparecen en la lista de omitidos para revisión.

Para MinIO, configurar `LICIGT_MINIO_ENDPOINT`, `LICIGT_MINIO_BUCKET`, `LICIGT_MINIO_ACCESS_KEY`, `LICIGT_MINIO_SECRET_KEY` y opcionalmente `LICIGT_MINIO_SECURE=true`. El bucket debe existir y tener versionado habilitado. Cada documento se escribe con una clave única, sin sobrescribir originales; el administrador puede añadir Object Lock si requiere impedir también su eliminación.

## Entrega al rol 2

El comando devuelve `doc_id`, versión, estado, número de páginas, fragmentos y ubicación del original. El manifiesto completo se guarda en `data/ingesta/manifiestos/<doc_id>.json`; el registro local de desarrollo está en `data/ingesta/ingesta.sqlite3`. Cada fragmento contiene `chunk_id`, `doc_id`, `nog`, `tenant_id`, `visibilidad`, `version`, páginas, sección, tipo y `texto`. El rol 2 **solo debe indexar fragmentos con `indexable=true`**. Las páginas con calidad `incompleta` se excluyen y las frases que parecen instrucciones dirigidas al modelo se marcan para revisión.

La segmentación conserva párrafos o tablas pequeños; unidades largas se dividen en ventanas de 600 palabras con 90 de solapamiento (aproximación a 800 y 120 tokens del anteproyecto), siempre dentro de una sola página. Las tablas reconocidas incluyen una representación `tabla_markdown` adicional; `texto` conserva la extracción para verificar citas. La detección de tablas e instrucciones maliciosas es heurística y requiere revisión sobre PDF reales. El manifiesto no interpreta cuál versión prevalece legalmente.

## Pruebas

```bash
PYTHONPATH=src python -m unittest discover -s src/licigt/ingesta/tests -v
```

Ver [responsabilidades e integración](../../../docs/roles/Asignacion_de_roles.md#rol-1--ingesta-y-documentos).
