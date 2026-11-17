# Entrega de ingesta para Recuperación y RAG

[`empresa_demo.zip`](empresa_demo.zip) es el corpus de prueba listo para incluir en Git para el rol 2: seis PDF oficiales del IGSS correspondientes a cinco eventos, con 1006 fragmentos indexables. `empresa_demo` es una empresa ficticia. La carpeta `data/` contiene el registro de trabajo local y sigue excluida de Git; el ZIP es el entregable que se comparte en el repositorio.

Dentro del ZIP, todas las rutas de archivos son **relativas a la raíz del ZIP**:

| Ruta | Uso |
|---|---|
| `chunks.jsonl` | Fragmentos que el rol 2 importa e indexa en PostgreSQL. |
| `inventario.json` | Relaciona `doc_id`, evento, versión, SHA-256, cobertura, estado y rutas internas. |
| `originales/<doc_id>.pdf` | PDF exacto para verificar citas y páginas. |
| `manifiestos/<doc_id>.json` | Extracción por página, fragmentos y alertas; `object_uri` apunta al PDF dentro del ZIP. |
| `procedencia/<doc_id>.json` | Metadatos de la descarga oficial; `original_zip_path` apunta al PDF dentro del ZIP. |

Los fragmentos de `chunks.jsonl` no contienen rutas de archivos locales. Conservan `url_origen` como enlace HTTPS al PDF oficial para mostrar la fuente; esa URL no es una ruta del equipo que generó el paquete.

Para extraerlo desde la raíz del repositorio:

```bash
mkdir -p data/recuperacion/entrada
unzip entregables/recuperacion/empresa_demo.zip -d data/recuperacion/entrada
```

El ZIP se regenera desde las descargas y el registro local con:

```bash
PYTHONPATH=src python -m licigt.ingesta.prepare_corpus --tenant-id empresa_demo --data-dir data/ingesta
PYTHONPATH=src python -m licigt.ingesta.handoff --tenant-id empresa_demo --data-dir data/ingesta --output entregables/recuperacion/empresa_demo.zip
```

La prueba de aceptación abre el ZIP en una carpeta temporal, comprueba hashes y rutas relativas, coteja cada fragmento con su manifiesto y ejecuta una búsqueda de ejemplo con filtros de empresa y evento:

```bash
python -m unittest discover -s src/licigt/recuperacion/tests -v
```

La modificación del evento 222 tiene las páginas 3 y 4 legibles por OCR (Tesseract 4.1.1, `spa`): 16 fragmentos indexables y 4 excluidos como `ruido_ocr`; la página 4 solo dejó ruido, así que el inventario la lista en `paginas_no_indexadas` (`[4]`). El PDF menciona un anexo de 11 hojas que no forma parte del archivo entregado, por lo que el documento sigue en `requiere_revision`. Consultar el [inventario del corpus](../../docs/ingesta/Corpus_IGSS.md) antes de evaluar respuestas sobre esa modificación.
