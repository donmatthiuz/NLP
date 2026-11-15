# Corpus local de ingesta del IGSS

**Corte local:** 14 de noviembre de 2026. **Empresa ficticia de prueba:** `empresa_demo`. La [selección de casos](Seleccion_del_corpus.md) contiene cinco licitaciones y seis PDF oficiales, incluida una modificación del evento 222. Todos los archivos se descargaron, verificaron por SHA-256 e ingresaron al pipeline. `data/` está excluido de Git.

| Evento | Tipo | Código IGSS | `evento_id` | `doc_id` | SHA-256 | Páginas legibles / total | Fragmentos indexables | Estado |
|---|---|---:|---|---|---|---:|---:|---|
| 399-IGSS-2026 | Bases | 432 | `437a8435922652fbb78aea651114680e` | `4182413774fa4149a9a15f4ecd0ef466` | `1f9aa9fdf38e8ce7780a00f37b49a9edda4ec9ef9426a979b2962127ff740444` | 36 / 36 | 211 | Completo |
| 363-IGSS-2026 | Bases | 345 | `7008db8420d85f7c932817d7868eae8a` | `f1cb15bfe200440891134b14683dcadf` | `953eab12d975d203d1d4f27aed8e14c39581095d67ac91efbcda7a8934cb9426` | 36 / 36 | 210 | Completo |
| 222-IGSS-2023 | Bases | 10527 | `69099f7184e65924a3e0aebf0ee238de` | `03791a3471c04c0f9cc260814564756e` | `93fc4e4fa0ef1376c2d2163f092f08236986ac72f5caf828dd7869de36a3ed2f` | 35 / 35 | 179 | Completo |
| 222-IGSS-2023 | Modificación 1 | 10527 | `69099f7184e65924a3e0aebf0ee238de` | `d41480e5b0ce4c16bf18f66225ada2dc` | `4101799486c95dc6d109a10043c3907704a3fc8ff1af249f7c1dc6faa61e8434` | 2 / 4 | 13 | Requiere revisión |
| 327-IGSS-2023 | Bases | Sin código | `b221164ba31257b89dbd66cf548983eb` | `0818d24d643a426b966ddaeb41072a00` | `759ac61bfc2282b8012358001d66ad364447f7dc2b4435fa66d511435db57ae3` | 37 / 37 | 178 | Completo |
| 368-IGSS-2026 | Bases | 10583 | `db659f295e08533eb33d07b7b76d127a` | `70a60ca8b46c46099376a1c581734662` | `1161c9f8b49aac197857a6de891d2b9e5db2d91df71a1221bf8d6a96ffb2e8a0` | 36 / 36 | 212 | Completo |

Los seis documentos suman **1003 fragmentos indexables**. Las fechas de las fichas del portal se conservan en `fecha_ficha`; `fecha_publicacion` queda sin dato porque no se verificó una fecha propia de publicación de cada PDF. La versión técnica de ingesta es 1 para cada `document_key`; la modificación 1 de 222 es un documento distinto, relacionado con sus bases.

## Límite de cobertura de la modificación 222

Las páginas 3 y 4 del PDF de modificación son imágenes sin texto extraíble en este entorno, que carece de Tesseract con idioma español. Se revisaron visualmente: la página 3 contiene una aprobación de cambios y la 4 menciona un anexo de 11 hojas que **no está incluido en este PDF de cuatro páginas**. Esas dos páginas no producen fragmentos; el rol 2 debe conservar el estado `requiere_revision` y no responder como si toda la modificación estuviera indexada. Para ampliar la cobertura hay que aplicar OCR y localizar el anexo oficial, si está disponible, antes de afirmar que se conoce el cambio completo.

## Entrega al rol 2

El paquete versionable está en [`entregables/recuperacion/empresa_demo.zip`](../../entregables/recuperacion/empresa_demo.zip). Contiene `chunks.jsonl`, `inventario.json`, los seis PDF originales bajo `originales/<doc_id>.pdf`, los manifiestos y sus JSON de descarga bajo `procedencia/<doc_id>.json`. La [guía de la entrega](../../entregables/recuperacion/README.md) da los comandos para extraerlo y recrearlo. El inventario incluye fuente, hash, estado, cobertura, fechas y páginas sin indexar. Todos los archivos internos se referencian por rutas relativas a la raíz del ZIP. El registro de trabajo en `data/` sigue excluido de Git.

Para crear el paquete se verifican de nuevo los SHA-256 de los originales y la correspondencia entre el registro SQLite, cada manifiesto y sus fragmentos. Los índices léxico y vectorial todavía corresponden al rol 2.
