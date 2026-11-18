# Corpus local de ingesta del IGSS

**Corte local:** 14 de noviembre de 2026. **Empresa ficticia de prueba:** `empresa_demo`. La [selección de casos](Seleccion_del_corpus.md) contiene cinco licitaciones y seis PDF oficiales, incluida una modificación del evento 222. Todos los archivos se descargaron, verificaron por SHA-256 e ingresaron al pipeline. `data/` está excluido de Git.

| Evento | Tipo | Código IGSS | `evento_id` | `doc_id` | SHA-256 | Páginas legibles / total | Fragmentos indexables | Estado |
|---|---|---:|---|---|---|---:|---:|---|
| 399-IGSS-2026 | Bases | 432 | `437a8435922652fbb78aea651114680e` | `4182413774fa4149a9a15f4ecd0ef466` | `1f9aa9fdf38e8ce7780a00f37b49a9edda4ec9ef9426a979b2962127ff740444` | 36 / 36 | 189 | Completo |
| 363-IGSS-2026 | Bases | 345 | `7008db8420d85f7c932817d7868eae8a` | `f1cb15bfe200440891134b14683dcadf` | `953eab12d975d203d1d4f27aed8e14c39581095d67ac91efbcda7a8934cb9426` | 36 / 36 | 190 | Completo |
| 222-IGSS-2023 | Bases | 10527 | `69099f7184e65924a3e0aebf0ee238de` | `03791a3471c04c0f9cc260814564756e` | `93fc4e4fa0ef1376c2d2163f092f08236986ac72f5caf828dd7869de36a3ed2f` | 35 / 35 | 159 | Completo |
| 222-IGSS-2023 | Modificación 1 | 10527 | `69099f7184e65924a3e0aebf0ee238de` | `d41480e5b0ce4c16bf18f66225ada2dc` | `4101799486c95dc6d109a10043c3907704a3fc8ff1af249f7c1dc6faa61e8434` | 4 / 4 | 9 (4 excluidos por `ruido_ocr`) | Requiere revisión |
| 327-IGSS-2023 | Bases | Sin código | `b221164ba31257b89dbd66cf548983eb` | `0818d24d643a426b966ddaeb41072a00` | `759ac61bfc2282b8012358001d66ad364447f7dc2b4435fa66d511435db57ae3` | 37 / 37 | 155 | Completo |
| 368-IGSS-2026 | Bases | 10583 | `db659f295e08533eb33d07b7b76d127a` | `70a60ca8b46c46099376a1c581734662` | `1161c9f8b49aac197857a6de891d2b9e5db2d91df71a1221bf8d6a96ffb2e8a0` | 36 / 36 | 191 | Completo |

Con el paquete R5 (17 de noviembre de 2026), los seis documentos suman **893 fragmentos indexables** y 4 excluidos (`ruido_ocr`, todos de la modificación de 222). Las fechas de las fichas del portal se conservan en `fecha_ficha`; `fecha_publicacion` queda sin dato porque no se verificó una fecha propia de publicación de cada PDF. La versión técnica de ingesta es 1 para cada `document_key`; la modificación 1 de 222 es un documento distinto, relacionado con sus bases.

## Extracción de tablas (R3)

Las tablas de descripción con bordes dibujados (cronograma 2.2 y parámetros del formulario) se extraen ahora con la geometría de `pdfplumber` y cada palabra se asigna a su celda. Cada fila sale como `| numeral | título | texto |` en una sola unidad `tabla` cuya sección es su encabezado (`2.2 CRONOGRAMA DE ACTIVIDADES`), y `tabla_markdown` queda lleno. Los cuadros de cantidades y el resto de las páginas siguen con `pdftotext -layout`. Una salvaguarda compara las palabras de la tabla con las del texto de su región y los dígitos de la página con los del texto anterior; si no coinciden se conserva el texto anterior. Medido en los seis PDF: 0 dígitos perdidos y 0 añadidos. El manifiesto y el inventario llevan el campo opcional `extraccion` (`pdftotext-layout+tablas`, versión 2); `version_ingesta` no cambió.

Efecto en los `chunk_id`: son posicionales, así que cambiaron. Los 12 ids citados en el repo se migraron con [`equivalencias_r3.json`](../../src/licigt/ingesta/equivalencias_r3.json) y `migrar_ids.py`; hay dos resueltos a mano (`03791a…:00040` es ahora el encabezado de la tabla y `d41480…:00012` se fundió en la fila 2.2.8 de `d41480…:00003`). Fragmentos por documento: 399 de 211 a 189, 363 de 210 a 190, 222 bases de 179 a 158, 222 modificación 1 de 20 a 12 (8 indexables), 327 de 178 a 154 y 368 de 212 a 191.

## Reproducibilidad

Los `doc_id`, `evento_id` y momentos de ingesta de la tabla están fijados en [`corpus_igss.json`](../../src/licigt/ingesta/corpus_igss.json), generado desde el ZIP del 14 de noviembre. `make corpus CONFIRMAR=1` baja de nuevo los seis PDF, verifica sus SHA-256 y reconstruye el paquete con los mismos ids; `reproducir --desde-zip` hace lo mismo sin red. Ver el [README de ingesta](../../src/licigt/ingesta/README.md).

## Límite de cobertura de la modificación 222

Las páginas 3 y 4 del PDF de modificación son imágenes sin texto extraíble. Con Tesseract 4.1.1 y el idioma `spa` se recuperaron por OCR (`reextraer`, ver [`corpus_igss.json`](../../src/licigt/ingesta/corpus_igss.json)): la página 3 aporta los fragmentos `d41480…:00006` a `:00008`, indexables (el `:00009` se excluye como `ruido_ocr`), y la 4 los `:00010` a `:00012`, excluidos como `ruido_ocr`. La página 4 menciona un anexo de 11 hojas que **no está incluido en este PDF de cuatro páginas**; `paginas_no_indexadas` cuenta las páginas sin ningún fragmento indexable, no solo las ilegibles: aquí es `[4]`, y se mantiene el aviso "Hay páginas incompletas o ilegibles"; el documento conserva el estado `requiere_revision` con la advertencia "Menciona un anexo de 11 hojas que no está cargado". El rol 2 no debe responder como si el cambio estuviera completo hasta localizar ese anexo.

## Entrega al rol 2

El paquete versionable está en [`entregables/recuperacion/empresa_demo.zip`](../../entregables/recuperacion/empresa_demo.zip). Contiene `chunks.jsonl`, `inventario.json`, los seis PDF originales bajo `originales/<doc_id>.pdf`, los manifiestos y sus JSON de descarga bajo `procedencia/<doc_id>.json`. La [guía de la entrega](../../entregables/recuperacion/README.md) da los comandos para extraerlo y recrearlo. El inventario incluye fuente, hash, estado, cobertura, fechas y páginas sin indexar. Todos los archivos internos se referencian por rutas relativas a la raíz del ZIP. El registro de trabajo en `data/` sigue excluido de Git.

Para crear el paquete se verifican de nuevo los SHA-256 de los originales y la correspondencia entre el registro SQLite, cada manifiesto y sus fragmentos. Los índices léxico y vectorial todavía corresponden al rol 2.
