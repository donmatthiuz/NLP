# I7. Extracción de tablas a dos columnas en las bases del IGSS

Investigación con experimentos medidos; no se cambió código del repositorio. Contexto: [`Avisos_del_rol_3.md`](../../ingesta/Avisos_del_rol_3.md) (sección mezclada en el cronograma) y [`Corpus_IGSS.md`](../../ingesta/Corpus_IGSS.md). Documentación de la biblioteca propuesta: [pdfplumber](https://github.com/jsvine/pdfplumber) (consultada con Context7, `/jsvine/pdfplumber`).

## Resumen

- La extracción actual es `pdftotext -layout` de todo el documento, separado por `\f`. Conserva la posición horizontal con espacios y por eso intercala las columnas línea por línea.
- Las tablas del IGSS tienen reglas (bordes dibujados). `pdfplumber` detecta su geometría; asignar cada palabra a una celda por sus coordenadas, y no usar `extract_tables`, reconstruye cada fila sin duplicar ni perder texto.
- Medido en 6 PDF (5 eventos): 0 dígitos perdidos y 0 dígitos añadidos; 6 de 6 filas del cronograma 2.2 del 222 con título y texto contiguos y unidos (hoy 0 de 6), tanto en las bases como en la modificación 1.
- Costo: unos 1.9 s por PDF de 36 páginas (hoy 0.06 s); es una ingesta única por documento.
- Efecto en ids: cambian los `chunk_id` posteriores a la primera página con tabla reescrita (desde el 37 en las bases del 222; en la modificación 1 desde el 1). Los 12 ids concretos citados en el repo se migran con una tabla de equivalencias (sección de migración).
- Recomendación: estrategia C selectiva con formato de filas `| numeral | título | texto |`, con salvaguarda de multiconjunto de palabras y regreso al texto actual si no coincide.

## Método

- Bibliotecas instaladas con `pip install --user` fuera del repositorio: `pdfplumber` 0.11.10 (MIT) y `pymupdf` 2.1 (AGPL, solo para comparar). `pdftotext` es el Poppler del sistema.
- PDF originales leídos de `entregables/recuperacion/empresa_demo.zip` (copiados al scratchpad, ZIP intacto): 222 bases (35 p.), 222 modificación 1 (4 p.), 327, 399, 368 y 363 (36 a 37 p.).
- Scripts y salidas en el scratchpad de la sesión: `.../scratchpad/i7/` (`strat.py` con las estrategias, `measure2.py` con las métricas, `medidas2.json` con los resultados).
- Todas las estrategias alimentan el `make_chunks` real del repositorio (`pipeline.py`), con `max_words` y solapamiento por defecto, así que lo que se mide es el efecto verdadero en fragmentos, secciones y `chunk_id`. Comprobación de base: `make_chunks` sobre la extracción actual reproduce los 179 de 179 fragmentos de las bases del 222 y los 13 de la modificación 1 del `chunks.jsonl` entregado (los 3 restantes son de OCR, que aquí no se reprodujo).
- Verdad independiente para las filas: seis filas del cronograma 2.2 (2.2.1, 2.2.2, 2.2.3, 2.2.5, 2.2.6 y 2.2.7) leídas a mano del PDF, con numeral, título y texto completos. "Fila unida" exige, dentro de un mismo fragmento, numeral, título y texto en ese orden y casi pegados (regex con a lo sumo 4 y 12 caracteres no alfabéticos entre ellos). "Celdas contiguas" cuenta si el título y el texto aparecen completos como subcadena de la página (12 celdas).
- Dígitos: multiconjunto de secuencias `\d+` por página contra la extracción actual; se informa lo perdido y lo añadido.

## Cómo se extrae hoy

- `src/licigt/ingesta/pdf.py`, `extract_pages`: `pdfinfo` para contar páginas (límite 300) y un solo `pdftotext -layout -enc UTF-8` del documento completo; el texto se parte por `\f` y debe coincidir con el número de páginas.
- Por página: `normalize_text` (NFC, quita caracteres de control y espacios finales). Si la página tiene menos de 30 caracteres y hay Tesseract con idioma `spa`, se rasteriza con `pdftoppm` a 200 dpi y se hace OCR (`method = "ocr"`); si no, `quality = "incompleta"` y la página no se segmenta.
- `extract_hidden_text` compara `pdftohtml -xml` con y sin `-hidden` para el texto oculto (no depende del diseño).
- `pipeline.py`: `_without_repeated_margins` quita encabezados y pies repetidos; `_units` corta por líneas en blanco y por líneas que cumplen `HEADING` (numeral más 3 a 120 caracteres), y marca como `tabla` los bloques con al menos dos líneas con espacios dobles; `make_chunks` une unidades de texto de la misma sección hasta 600 palabras y numera `<doc_id>:<índice>` por posición.
- Por qué se rompe: en `-layout` las columnas quedan en la misma línea de texto y `_units` trabaja línea a línea. `HEADING` toma como sección una línea como `2.2.1      hasta el día 31 de julio de 2023.` (numeral de la columna izquierda más el texto de la derecha), y la fila siguiente queda bajo el numeral equivocado.

## Hallazgos sobre las páginas pedidas

- Bases p. 1 (carátula) y p. 15 (literales a, b, c con sangría francesa) no son tablas: son una columna de cuerpo con el numeral o literal colgando a la izquierda. Es el mismo diseño de "numeral | texto" de casi todas las páginas (p. 4, 11), y por eso un detector de columnas sin reglas se equivoca (ver B). Sirven de control: las estrategias no deben alterarlas.
- Bases p. 8 y p. 9 y modificación p. 1 son la tabla real de tres columnas (numeral, descripción, fecha), con bordes dibujados. La fila 2.2.8 continúa en la p. 9.
- En el 222 la tabla con reglas aparece en las p. 8-9 (cronograma), 24 (cuadro de calificación), 28, 31 (producto y distribución) y 33-34. Otras páginas con tablas: p. 35 de 327, 399, 368 y 363 (parámetros del formulario electrónico) y p. 29 de los eventos 2026.
- La modificación 1 tiene la tabla con reglas truncadas al pie de la página: el último renglón del cronograma trae rectángulos por línea de texto. Es el caso difícil.

## Estrategias comparadas

- A. Actual: `pdftotext -layout`.
- B. Palabras con coordenadas (`PyMuPDF get_text("words")`) y detección de la frontera vertical (gutter) sin reglas: columna libre de palabras en al menos 3 líneas consecutivas, ancho mínimo 9 pt y posición entre 30 % y 70 % del ancho; luego se lee columna por columna y se corta en filas por huecos verticales.
- C0. `pdfplumber extract_tables` (celdas del extractor) con la fila reconstruida como "celdas izquierdas: celda derecha".
- C. Geometría de `pdfplumber find_tables` (bbox, bordes de la primera columna y bordes verticales repetidos) y asignación de cada palabra de `extract_words` a su celda por centro. El texto fuera de las tablas se toma con `pdftotext -layout` recortado (`-x -y -W -H`), idéntico al actual. Variantes:
  - C todas: toda tabla de 2 o más columnas.
  - C selectivo: solo "tablas de descripción" (columna 0 con numeral o literal y celda final con mediana de 60 o más caracteres). Deja como están los cuadros de cantidades.
  - Formatos de fila: `1l` ("celdas izquierdas: texto"), `2l` (título y texto en líneas distintas), `pipe` (`| numeral | título | texto |`).
  - Salvaguarda: el multiconjunto de palabras del bloque reconstruido debe ser igual al de `pdftotext -layout` en esa región; si no, se usa el texto actual de la región.
  - Las tablas anidadas se descartan por contención de bbox (sin esto el texto salía duplicado en la p. 35 de cuatro eventos).
- D. `pdftotext` sin `-layout` (D1) y con `-raw` (D2).
- PyMuPDF `find_tables().extract()` también se probó en la p. 8 y en la modificación: mezcla palabras sin espacios (`recepcióndeOFERTAS`) y duplica texto en la última fila; se descartó. Además PyMuPDF es AGPL.

## Tabla comparativa medida

Cronograma 2.2 del evento 222 (6 filas verificadas a mano). "Chunks" es el total de fragmentos del documento tras `make_chunks`. "Primer id distinto" es el primer índice (desde 0) cuyo texto difiere del actual.

| Estrategia | Bases 222: filas unidas | Bases 222: celdas contiguas | Bases 222: chunks | Mod. 1: filas unidas | Mod. 1: chunks | Dígitos perdidos / añadidos (6 PDF) | Primer id distinto (bases 222 / mod. 1) | Tiempo bases 222 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A actual | 0/6 | 1/12 | 179 | 0/6 | 13 | 0 / 0 | n/a | 0.05 s |
| B palabras y gutter | 4/6 | 11/12 | 153 | 0/6 | 3 | 0 / 0 | 0 / 0 | 0.6 s |
| C0 `extract_tables` | 6/6 | 12/12 | 158 | 0/6 (cae al texto actual) | 13 | 0 / 0 | 37 / 1 | 1.8 s |
| C selectivo `1l` | 6/6 | 12/12 | 154 | 6/6 | 4 | 0 / 0 | 37 / 1 | 1.9 s |
| C selectivo `2l` | 6/6 | 12/12 | 176 | 6/6 | 11 | 0 / 0 | 37 / 1 | 1.9 s |
| C selectivo `pipe` (recomendada) | 6/6 | 12/12 | 153 | 6/6 | 3 | 0 / 0 | 37 / 1 | 1.8 s |
| C todas las tablas `1l` | 6/6 | 12/12 | 152 | 6/6 | 4 | 0 / 0 | 37 / 1 | 1.9 s |
| D1 `pdftotext` sin layout | 0/6 | 11/12 | 100 | 0/6 | 2 | 4 / 2 | 0 / 0 | 0.05 s |
| D2 `pdftotext -raw` | 6/6 | 12/12 | 182 | 6/6 | 6 | 0 / 0 | 0 / 0 | 0.05 s |

Hallazgos por estrategia:

- A: de las 12 celdas del cronograma solo una queda contigua. Ninguna fila queda unida.
- B: acierta las filas 2.2.3 a 2.2.7 y falla 2.2.1 y 2.2.2, porque entre ambas no hay hueco vertical (el numeral queda centrado en la fila). En la modificación falla por completo la unión y mezcla el encabezado con los renglones. Con un umbral de gutter menor, o sin el filtro de posición, rompe los listados con sangría francesa (p. 15), porque la columna del literal parece una tabla; con ese filtro la p. 15 y la p. 1 salen bien, pero queda sin respaldo en tablas de otro ancho. Cada fila queda como una línea larga y se pierde la estructura de párrafos (153 chunks frente a 179 con todos los textos distintos salvo 15).
- C0: funciona en las bases (6/6), pero en la modificación 1 el último renglón duplica texto ("Hasta diez (10) días hábiles..." dos veces) y la salvaguarda lo rechaza; cae al texto actual, o sea 0/6 en la página más importante de la demostración. Por eso se pasó a asignar palabras a celdas.
- C selectivo: 0 dígitos perdidos ni añadidos en los 6 PDF, 0 tablas rechazadas por la salvaguarda en el formato final y 6/6 en ambas páginas. Solo 5 tablas por documento se reescriben (cronograma, p. 9, parámetros) y el resto queda como hoy.
- C todas: reescribe también cuadros de cantidades (p. 31). Allí el resultado empeora, por ejemplo `No. 1 No. DE PEDIDO 31/2023 UNIDAD SOLICITANTE Unidad de Consulta Externa de ... : CANTIDADES ... 400`, que mezcla encabezado y primera fila. Por eso el selectivo.
- D1: no es utilizable: parte el texto por palabras (`122-2016` queda como `1222016`; 4 dígitos "perdidos" son en realidad fusiones) y reduce los chunks a la mitad.
- D2: da 6/6 en el cronograma, pero cambia el espaciado de toda la página: ninguno de los textos de las demás páginas coincide con el actual (solo 16 de 179 se conservan, frente a 143 con C selectivo), así que cambiarían los 179 ids y se pierde la sangría que `HEADING` usa.

## Ejemplos reales antes y después

Bases 222, p. 8 (el ejemplo del encargo), antes:

```
              Fecha y hora para inducción a                 El día 19 de julio de 2023, a las 10:00 horas.
              interesados en ofertar el OBJETO              La inducción se impartirá de forma virtual, por lo que
              de     los  DOCUMENTOS        DE              los interesados deberán enviar un correo
```

Después (C selectivo `pipe`):

```
| 2.2.2 | Fecha y hora para inducción a interesados en ofertar el OBJETO de los DOCUMENTOS DE LICITACIÓN. | El día 19 de julio de 2023, a las 10:00 horas. La inducción se impartirá de forma virtual, por lo que los interesados deberán enviar un correo electrónico a la dirección deptoabastosigss@gmail.com a efecto de que se les envíe la invitación correspondiente. |
```

Sección de los fragmentos del cronograma, antes y después:

- Antes, `:00041`: sección `2.2.1                                                 hasta el día 31 de julio de 2023.`.
- Antes, `:00047`: sección `2.2.5                                                 La preparación del FORMULARIO ELECTRÓNICO`, con el texto de la recepción de ofertas debajo.
- Antes, modificación 1: los fragmentos `:00009` y `:00012` quedan en las secciones `2.2.5 Período para la preparación del ...` y `2.2.8 Plazo para adjudicar.`, con la solvencia patronal bajo 2.2.8.
- Después: un solo fragmento por tabla, con sección `2.2 CRONOGRAMA DE ACTIVIDADES`, que contiene encabezado, las 7 filas y las fechas (en la modificación 1, una sola unidad de 217 palabras que incluye `| 2.2.1 | ... | ... hasta el día 06 de octubre de 2023. |`). La fecha "06 de octubre de 2023" queda en la misma fila que "Lugar, dirección, fecha y hora para la recepción de OFERTAS.".
- Con el formato `1l` o `2l`, `HEADING` hace de las filas cortas (por ejemplo 2.2.7) una sección nueva y parte el cronograma. El formato `pipe`, al empezar por `|`, no cumple `HEADING` y evita ese efecto; es una razón concreta para preferirlo.
- La fila 2.2.8 (bases, p. 9) pasa a `| 2.2.8 | Plazo para adjudicar. | Hasta diez (10) días hábiles ... |`; antes quedaba en 5 líneas intercaladas.

## Recomendación

- Adoptar la estrategia C selectivo con formato `pipe`, implementada en `pdf.py` como una función aparte que `extract_pages` llama por página solo si `find_tables` detecta una tabla que pase el filtro de "tabla de descripción". Las páginas sin tabla de ese tipo quedan con el mismo texto de hoy (en el 222 solo cambian las p. 8, 28, 33, 34 y la p. 9 con la corrección del borde exterior; en la modificación, la p. 1).
- Respaldo de la decisión:
  - Es el único con las 12 celdas contiguas y 6 de 6 filas unidas en las dos páginas del demo, con 0 dígitos alterados en los 6 PDF.
  - Las tablas son de bordes dibujados: detectar la tabla por geometría es lo que usa la propia biblioteca (`find_tables`, estrategia `lines`, Context7: [documentación](https://github.com/jsvine/pdfplumber)); la detección por proyección de texto (B) falla justo donde el numeral se centra en la fila.
  - Una salvaguarda objetiva (multiconjunto de palabras contra el texto actual de la misma región) evita publicar una reconstrucción que pierda o duplique texto, y cae al comportamiento actual en vez de fallar. Esa salvaguarda es la que habría detectado el duplicado de la modificación.
  - El formato `pipe` deja cada celda como subcadena contigua y literal: el validador de citas del rol 3 comprueba citas literales, y la cita de la fecha deja de partirse.
  - Permite llenar `tabla_markdown` con celdas reales (hoy vacío en estas tablas, ver Avisos).
- Cambios de código que implicaría (para un encargo posterior, no hechos aquí):
  - `pdf.py`: agregar la reconstrucción y la salvaguarda; `pdfplumber` entra como dependencia (MIT, pura Python, sin GPU; arrastra `pdfminer.six`, `pypdfium2` y Pillow). `shell.nix` y el entorno de instalación deben incluirla.
  - `pipeline.py`: `_units` debe tratar un bloque de líneas que empiezan por `|` como unidad `tabla` que conserve la sección vigente (hoy lo clasificaría como texto) y, si excede `max_words`, cortar por filas y no por palabras.
  - `reextraer.py` llama a `extract_pages(use_ocr=True)`; recibe el cambio sin tocarlo.
- Límites conocidos: tablas con bordes truncados al borde de página requirieron usar el borde del bbox como frontera exterior; las tablas con celdas combinadas (parámetros del formulario, p. 35) pasan la salvaguarda, pero la lectura de filas con varias líneas por celda no se validó celda por celda (solo por multiconjunto de palabras). Páginas escaneadas con tablas no pasan por este camino (OCR) y siguen como hoy.

## Impacto en los chunk_id

- Los ids son posicionales (`<doc_id>:<índice>`): cambiar el número de fragmentos de una página desplaza todos los siguientes. En las bases del 222 el primer fragmento distinto es el 37 (de 179 se conservan idénticos 37 ids; 143 textos reaparecen con otro número); en la modificación 1 es el 1, porque sus 2 primeras páginas son la tabla.
- Referencias concretas en el repositorio (12 ids únicos, hallados con `grep` de `<32 hex>:<5 dígitos>`):
  - 222 bases: `:00001`, `:00040`, `:00041`, `:00047`, `:00063`, `:00078`, `:00081`, `:00118`.
  - 222 modificación 1: `:00009`, `:00012`, `:00013`, `:00015`.
- Dónde aparecen:
  - Pruebas: `src/licigt/consulta/tests/test_requisitos.py` (7), `test_generacion.py` (2), `test_ejemplos_web.py` (1, `:00015`).
  - Ejemplos web: `web/src/ejemplos/lista.json` (8), `cobertura_parcial.json` (3), `respuesta.json` (2), `comparacion.json` (2) y `web/src/estado.test.ts`; `abstencion.json` cita el `doc_id`.
  - Documentos: `F3b_extraer_requisitos.md`, `F4_generacion_y_orquestacion.md`, `C3_correcciones_F4_segunda.md`, `C4_datos_literales_F4.md`, `I1_generacion_y_citas.md`, `docs/ingesta/delegacion/R1_ingesta.md`, `R2_corpus.md`, `Corpus_IGSS.md`, `docs/recuperacion/Avisos_del_rol_1.md`.
  - Rol 2: `src/licigt/recuperacion/casos_desarrollo.json` no cita `chunk_id`; define la relevancia por tipo de documento y página, así que no se rompe. `indice.py` y `busqueda.py` leen los ids del ZIP, no los fijan. `lista_sql.py` y la lista guardada usan ids de `chunks.jsonl`.
- Tabla de equivalencias medida (texto, página y sección de cada id antes y con C selectivo; `=` indica texto idéntico con otro número):

| Id actual | Página | Sección actual | Con la nueva extracción |
| --- | --- | --- | --- |
| 222:`00001` | 1 | Sin sección | `:00001` (idéntico) |
| 222:`00040` | 8 | `2.2 CRONOGRAMA DE ACTIVIDADES` | `:00040` (cambia: tabla completa unida, sección `2.2`) |
| 222:`00041` | 8 | `2.2.1 hasta el día 31 de julio...` | se funde en `:00040`; ya no existe como fragmento propio |
| 222:`00047` | 8 | `2.2.5 La preparación...` | se funde en `:00040` |
| 222:`00063` | 13 | `2.7 LISTADO...` | `:00055` (=) |
| 222:`00078` | 16 | `2.8 REQUISITOS FUNDAMENTALES` | `:00070` (=) |
| 222:`00081` | 18 | `2.9 REQUISITOS NO FUNDAMENTALES` | `:00073` (=) |
| 222:`00118` | 27 | `2.23.2 SEGURO DE CAUCIÓN...` | `:00110` (=) |
| mod. 1 `:00009` y `:00012` | 1 | `2.2.5` y `2.2.8` | se funden en el fragmento de la tabla (`:00002`) |
| mod. 1 `:00013` | 2 | `2.2.8 Plazo para adjudicar.` | `:00003` (la tabla continúa en p. 2) |
| mod. 1 `:00015` | 3 (OCR) | sección derivada del OCR | se agrega por `reextraer` con la base `max(índice)+1`, es decir desde `:00004`; no se pudo reproducir aquí por falta de Tesseract y debe volver a verificarse |

- Migración propuesta (`script de equivalencias`, a crear en un encargo posterior):
  - Para cada id citado, buscar en el corpus nuevo el fragmento de misma página con igual texto normalizado; si no existe, el de mayor solapamiento de palabras y marcarlo "cambia".
  - Los ids de fixtures que cambian de texto (los de las p. 8 de las bases y p. 1-2 de la modificación) deben regenerarse con el texto nuevo, porque hoy las pruebas contienen el texto intercalado. Las que se mantienen idénticas solo cambian de número.
  - Las pruebas del rol 3 usan dobles y no dependen del ZIP, así que lo que falla es solo el realismo de los fixtures y la coincidencia con la verdad documental, no la lógica. `test_ejemplos_web.py` sí exige el id `:00015`.

## Versión de ingesta y regeneración

- No subir `version_ingesta`. Ese número cuenta revisiones del mismo `document_key` con otro SHA-256 (`SELECT MAX(version_ingesta)+1` en `IngestionService`, `UNIQUE(sha256)`) y lo usan `comparar_versiones` y la lista de verificación; el documento original no cambió. Subirlo falsearía "hay una versión nueva del documento".
- Sí registrar el método: agregar al manifiesto y al inventario un campo aditivo `extraccion` (por ejemplo `{"metodo": "pdftotext-layout+tablas", "version": 2}`), sin cambiar `chunk_id` ni los campos de `Fragmento`. Opción por defecto: no tocar el contrato con el rol 2; el campo es opcional.
- Regenerar el paquete con `make corpus` / `licigt.ingesta.reproducir`: `corpus_igss.json` fija `doc_id`, `version_ingesta` e `ingested_at` y no cambia. Conviene usar `python -m licigt.ingesta.reproducir --desde-zip entregables/recuperacion/empresa_demo.zip --salida ...` (sin red; `make corpus CONFIRMAR=1` descarga de igssgt.org). Para la modificación 1 hace falta Tesseract 4.1.1 con `spa` para reproducir las páginas 3 y 4 por OCR.
- Reproducibilidad: `ReproducibilidadTests.test_el_paquete_reconstruido_es_identico_al_actual` reconstruye desde los originales del ZIP vigente y lo compara con él. Fallará mientras el ZIP guardado tenga la extracción vieja, y vuelve a pasar cuando se commitee el ZIP regenerado con el código nuevo. `test_reconstruye_el_paquete_con_los_mismos_ids` usa dobles (`PAGINAS` fijos) y no cambia. La extracción nueva es determinista (geometría, sin aleatoriedad ni hora), así que dos corridas dan el mismo `chunks.jsonl`; hay que añadir una prueba con una tabla sintética de reglas conocidas y fijar la versión de `pdfplumber` en el entorno.
- Rol 2:
  - Reimportar con `make importar` (idempotente). Los `chunk_id` previos no se conservan: no basta con agregar. Si conserva índices vivos, limpiar o recrear los de los 6 documentos.
  - Sus casos por página (`casos_desarrollo.json`) siguen siendo válidos, porque cada tabla se mantiene en su página. Hay que recalcular las métricas de recuperación (la sección de varios fragmentos cambia) y la prueba `test_entrega` que espera `paginas_no_indexadas` de la modificación (ya señalada en `Avisos_del_rol_1.md`).
  - Conviene avisarle en `docs/recuperacion/Avisos_del_rol_3.md` con la opción por defecto "reimportar tras el ZIP regenerado".
- Con cualquiera de las opciones se pierde la equivalencia con los ids de la demo grabada: hay que repetir la demo (el paso 3 compara una fecha del cronograma) tras regenerar.

## Decisiones para el visto bueno del usuario

- 1. Estrategia de extracción.
  - Opción recomendada: C selectivo `pipe` (geometría de `pdfplumber` más asignación de palabras, salvaguarda por multiconjunto, regreso al texto actual).
  - Alternativas: mantener la extracción actual y mitigar con el `Aviso` vigente (sección como pista, respaldo JEV 0.7); solo `pdftotext -raw` (cambia todos los ids y el espaciado).
- 2. Dependencia nueva.
  - Opción recomendada: aceptar `pdfplumber` (MIT; `pdfminer.six`, `pypdfium2` y Pillow) en el entorno y en `shell.nix`.
  - Alternativa: PyMuPDF, descartada por licencia AGPL y por los textos sin espacios medidos.
- 3. Alcance.
  - Opción recomendada: solo tablas de descripción (numeral o literal en la columna 0 y texto largo); los cuadros de cantidades quedan como hoy.
  - Alternativa: todas las tablas; empeora el cuadro de distribución (p. 31).
- 4. Versionado.
  - Opción recomendada: no subir `version_ingesta`; agregar el campo opcional `extraccion` en manifiesto e inventario.
  - Alternativa: nueva `version_ingesta` (no recomendada, confunde la comparación de versiones).
- 5. Momento de la migración de ids.
  - Opción recomendada: implementar, regenerar el ZIP con `reproducir --desde-zip`, migrar fixtures y ejemplos web con el script de equivalencias, avisar al rol 2 y repetir la demo; en ese orden y en una sola entrega.
  - Alternativa: posponer hasta después de la entrega y declarar la limitación en el informe (las citas literales del cronograma seguirían partidas).
- 6. Formato de fila.
  - Opción recomendada: `| numeral | título | texto |` (evita que `HEADING` parta el cronograma y llena `tabla_markdown`).
  - Alternativa: `numeral título: texto` (más cercano al pedido original, pero rompe la sección en las filas cortas).
