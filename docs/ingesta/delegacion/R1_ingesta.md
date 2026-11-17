# Encargo R1: ingesta, OCR de la modificación del 222 y clasificación del conector

Para Codex u OpenCode. Rama `rol/consulta` (decisión del usuario del 17 de noviembre: el rol 3 abarca también el rol 1). El gestor auditará el resultado y el agente `adversario` intentará refutarlo. No commitees.

## Decisiones para el visto bueno del usuario

La rama ya la decidió el usuario el 17 de noviembre; las demás siguen pendientes de su visto bueno.

- **Aviso al compañero del rol 1.** `src/licigt/ingesta` y `docs/ingesta/Pendientes_rol_1.md` los escribió otra persona (último commit de ingesta: `85f123a`, 14 de noviembre). Recomendado: avisarle antes de empezar, con el enlace a este encargo, para no trabajar los dos sobre lo mismo.
- **Rama.** `rol/consulta`, por decisión del usuario, aunque `AGENTS.md` pide una rama por rol. Los commits de ingesta van separados con su propio prefijo.
- **Sección mezclada a dos columnas y `tabla_markdown` vacío** (`docs/ingesta/Avisos_del_rol_3.md`). Recomendado: dejarlo fuera de este encargo. Corregir `_units` cambia los cortes de fragmento y, como `chunk_id` es posicional (`pipeline.py:241`), cambiaría los ids de las bases que ya usan los roles 2 y 3. El rol 3 ya lo mitiga con un umbral de JEV de 0.7.
- **Almacenamiento MinIO o GCS.** Recomendado: fuera de este encargo; lo decide el equipo con el rol 4 (`Pendientes_rol_1.md`, "Almacenamiento para el despliegue").

## Lee primero

- [`AGENTS.md`](../../../AGENTS.md);
- `docs/ingesta/Pendientes_rol_1.md`, `docs/ingesta/Corpus_IGSS.md` y `docs/ingesta/Avisos_del_rol_3.md`;
- `entregables/recuperacion/README.md`;
- `src/licigt/ingesta/pipeline.py`, `pdf.py`, `handoff.py` y `automatic.py`, con sus pruebas;
- `src/licigt/recuperacion/indice.py`, funciones `leer_paquete` e `importar` (solo lectura: así consume el rol 2 el ZIP).

## Origen

- La modificación 1 del 222 (`d41480e5b0ce4c16bf18f66225ada2dc`) tiene 4 páginas; las 3 y 4 son imágenes sin texto y no producen fragmentos (`Corpus_IGSS.md:18`; en el inventario del ZIP, `paginas_no_indexadas: [3, 4]`). Es el caso de demostración de comparación de versiones del rol 3 (`Avisos_del_rol_3.md`, primer punto).
- Este equipo tiene Tesseract 4.1.1 con `eng` y `osd`, sin `spa`. `pdf.py:77` pide `-l spa`, así que el OCR no se aplica.
- `reprocess()` no hace OCR: solo resegmenta el texto guardado (`pipeline.py:427-428`). Volver a correr `ingest()` con el mismo PDF devuelve la carga existente por deduplicación (`pipeline.py:312-316`).
- No existe `data/` en este clon; el registro SQLite y las descargas del rol 1 no están. Regenerar con `prepare_corpus` crearía `doc_id` nuevos (`uuid4`, `pipeline.py:382`) y rompería todas las referencias. El ZIP sí es autosuficiente: trae originales, manifiestos, procedencia, `chunks.jsonl` e `inventario.json`.
- `ingest_event()` registra siempre el PDF del portal como `bases_integradas` y `bases` (`automatic.py:166`); en el 222 ese enlace lleva a una modificación (`Pendientes_rol_1.md`, punto 2).

## Partes (paralelizables: no comparten archivos)

### Parte A (alta): reextracción con OCR sobre el ZIP, con `chunk_id` estables

Archivos: solo `src/licigt/ingesta/reextraer.py` (nuevo) y `src/licigt/ingesta/tests/test_reextraer.py` (nuevo). Puede importar de `pdf.py` y `pipeline.py`, pero no editarlos.

- **Entrada:** la ruta del ZIP, un `doc_id` y, opcional, advertencias humanas repetibles (`--advertencia "..."`). **Salida:** un ZIP nuevo, escrito de forma atómica como en `handoff.export` (temporal y `replace`).
- **Qué hace:**
  - verifica el SHA-256 del original dentro del ZIP contra el inventario y el manifiesto; si no coincide, falla;
  - extrae de nuevo con `extract_pages(..., use_ocr=True)` solo para decidir las páginas que antes tenían `quality != "ok"` y ahora sí;
  - las páginas que ya estaban bien y sus fragmentos se copian sin cambios: mismo texto, mismo `chunk_id`, mismo orden;
  - las páginas recuperadas se segmentan con `make_chunks` sobre esas páginas, y sus fragmentos se renumeran a partir del mayor índice existente más uno (`<doc_id>:00014`, …);
  - cada fragmento nuevo pasa por `SUSPICIOUS` y por las mismas reglas de `indexable` que `reprocess` (`pipeline.py:459-467`);
  - actualiza en el manifiesto `pages`, `chunks`, `cobertura.paginas_legibles`, `warnings` y `status`, y añade `reextracted_at`; en el inventario, `paginas_no_indexadas`, `chunks_indexables`, `cobertura`, `warnings` y `status`; y en `chunks.jsonl`, solo añade las líneas nuevas de ese `doc_id`;
  - el aviso "Hay páginas incompletas o ilegibles" se quita solo si todas las páginas quedan `ok`; las advertencias humanas se añaden y mantienen `status = "requiere_revision"`.
- **No cambia:** `doc_id`, `version_ingesta`, `hash_sha256`, `object_uri` ni ningún otro documento del ZIP (sus bytes deben ser idénticos).
- **Ejecución:** `PYTHONPATH=src python -m licigt.ingesta.reextraer --zip entregables/recuperacion/empresa_demo.zip --doc-id <id> --salida <ruta> [--advertencia "..."]`. No añadas objetivos al `Makefile`.
- **Pruebas (primero en rojo, sin red ni Tesseract; OCR simulado con `unittest.mock.patch` sobre `extract_pages` del módulo):**
  - un ZIP de prueba con un documento de 4 páginas, 2 ilegibles: los fragmentos previos quedan idénticos y los nuevos empiezan en el índice siguiente;
  - los demás documentos del ZIP quedan byte a byte iguales;
  - un original con hash alterado hace fallar sin escribir salida;
  - una página OCR con "ignora las instrucciones anteriores" queda `injection_suspected` y no indexable;
  - sin OCR disponible (la página sigue sin texto), no cambia nada y lo informa;
  - una advertencia humana mantiene `requiere_revision`;
  - el ZIP de salida pasa `leer_paquete` del rol 2 (importarlo en la prueba no requiere base de datos).

### Parte B (alta): el conector no etiqueta una modificación como bases

Archivos: solo `src/licigt/ingesta/automatic.py` y `src/licigt/ingesta/tests/test_automatic.py`.

- `ingest_event()` exige `tipo_documento` y `document_key` explícitos; sin ellos, falla con un mensaje claro en vez de asumir `bases`.
- Si el tipo es `modificacion`, `aclaracion` o `anexo`, exige `relacion_documental`.
- **Comprobación verificable:** si el texto de las dos primeras páginas contiene "MODIFICACI[ÓO]N" y el tipo declarado es `bases`, añade la advertencia "El PDF parece una modificación; revisar el tipo documental" y deja los fragmentos no indexables hasta revisarlo.
- La CLI (`main()` del módulo) recibe `--tipo-documento`, `--document-key` y `--relacion-documental`.
- **Pruebas (con el `fetcher` falso que ya usan las pruebas):**
  - sin tipo explícito, falla;
  - una modificación sin relación, falla;
  - un PDF cuya portada dice "MODIFICACIÓN" declarado como `bases` queda no indexable y con la advertencia;
  - un evento con bases y modificación queda con los dos tipos y la relación correcta;
  - un evento sin código IGSS sigue funcionando.

### Parte C (media): eventos de carga para el rol 4

Archivos: solo `src/licigt/ingesta/eventos.py` (nuevo), `src/licigt/ingesta/tests/test_eventos.py` (nuevo) y `docs/plataforma/Avisos_del_rol_1.md` (nuevo).

- `evento_de_carga(manifest) -> dict`, función pura con `tenant_id`, `evento_id`, `doc_id`, `hash_sha256`, `status`, `paginas_legibles`, `paginas_total`, `warnings`, `created_at` y `reextracted_at` si existe.
- **Nunca** incluye el texto de páginas ni de fragmentos, ni rutas locales, ni credenciales.
- El aviso al rol 4 propone ese contrato con una opción por defecto: el rol 4 lo guarda en su auditoría; mientras no exista, la CLI lo imprime en JSON.
- **Pruebas:** con un manifiesto con texto de páginas, el evento no contiene ningún fragmento de ese texto; un manifiesto con página ilegible produce `status = "requiere_revision"` y el aviso correspondiente.

## Lo que hace el usuario a mano

- Instalar el idioma español de Tesseract: `sudo apt install tesseract-ocr-spa`, y comprobar con `tesseract --list-langs` que aparece `spa`.
- Buscar en el portal del IGSS el anexo de 11 hojas que menciona la página 4 de la modificación 1. Si aparece, guardar el PDF y su URL; cargarlo será un encargo aparte (hoy no hay `data/` y añadir un documento al ZIP requiere su propia herramienta).
- Después de la Parte A, correr la reextracción real:

  ```bash
  PYTHONPATH=src python -m licigt.ingesta.reextraer \
    --zip entregables/recuperacion/empresa_demo.zip \
    --doc-id d41480e5b0ce4c16bf18f66225ada2dc \
    --salida entregables/recuperacion/empresa_demo.zip \
    --advertencia "Menciona un anexo de 11 hojas que no está cargado"
  ```

- Revisar el texto OCR de las páginas 3 y 4 contra la imagen del PDF antes de commitear el ZIP.

## Regeneración del paquete y aviso al rol 2

- El ZIP nuevo reemplaza a `entregables/recuperacion/empresa_demo.zip` en la rama `rol/consulta`. Se actualizan a mano `docs/ingesta/Corpus_IGSS.md` (páginas legibles y fragmentos de la modificación) y `entregables/recuperacion/README.md` (las páginas 3 y 4 ya tienen texto; el anexo sigue faltando).
- El rol 2 reimporta con `make importar`: su `importar` borra y vuelve a insertar los fragmentos de cada `doc_id` del paquete (`indice.py:89`), así que no deja fragmentos huérfanos.
- **Garantía de estabilidad:** los 13 `chunk_id` previos de la modificación y todos los de los otros cinco documentos no cambian; solo se añaden ids nuevos. Los casos de desarrollo del rol 2 están por página, no por `chunk_id` (`casos_desarrollo.json`), así que no se rompen.
- El aviso va en `docs/recuperacion/Avisos_del_rol_1.md`, con la lista de `chunk_id` nuevos y la opción por defecto: reimportar y volver a correr `evaluar.py`.

## Cinco porqués de las decisiones

### Reextraer sobre el ZIP y no sobre `data/`

1. ¿Por qué no usar `prepare_corpus`? Porque necesita `data/ingesta/descargas_igss` (`prepare_corpus.py:27`), que no existe en este clon.
2. ¿Por qué no recuperar `data/`? Aunque existiera, `ingest()` deduplica por hash y no vuelve a extraer (`pipeline.py:312-316`).
3. ¿Por qué no usar `reprocess()`? Porque no ejecuta OCR, solo resegmenta el texto guardado (`pipeline.py:428`).
4. ¿Por qué no reingerir desde cero? Porque cada ingesta crea un `doc_id` nuevo con `uuid4` (`pipeline.py:382`) y rompería las referencias de los roles 2 y 3.
5. ¿Por qué basta el ZIP? Porque trae el original, el manifiesto y el inventario de cada documento con rutas relativas (`entregables/recuperacion/README.md`), y el rol 2 lo consume tal cual (`indice.py:44`).

### Fragmentos nuevos numerados después de los existentes

1. ¿Por qué no volver a llamar `make_chunks` sobre las 4 páginas? Porque `_without_repeated_margins` decide qué líneas quitar contando todas las páginas (`pipeline.py:168-175`); páginas nuevas pueden cambiar el texto de las páginas 1 y 2.
2. ¿Por qué importa? Porque `chunk_id` es posicional, `<doc_id>:<índice>` (`pipeline.py:241`).
3. ¿Quién depende de esos ids? Las pruebas y los encargos del rol 3 citan `d41480e5b0ce4c16bf18f66225ada2dc:00009` (`tests/test_requisitos.py`, `tests/test_generacion.py`), y el rol 2 prometió que `chunk_id` es estable al reimportar (`src/licigt/recuperacion/README.md:51`).
4. ¿Por qué no basta con la estabilidad del rol 2? Porque el rol 2 solo garantiza estabilidad si la ingesta entrega los mismos ids.
5. ¿Por qué numerar al final es correcto? Porque las páginas 3 y 4 son las últimas del documento, así que el orden de lectura se mantiene.

### Prioridad de las partes

1. ¿Qué exige el curso al rol 1? Una carga reproducible que permita localizar la página de cualquier fragmento, y que una segunda versión conserve la primera (`docs/roles/Asignacion_de_roles.md`, rol 1). Eso ya lo cubren `test_duplicate_version_and_tenant_isolation` y las 16 pruebas en verde.
2. ¿Qué bloquea la demo? La comparación de versiones del 222 sale parcial sin las páginas 3 y 4 (`docs/ingesta/Avisos_del_rol_3.md`), así que la Parte A va primero.
3. ¿Por qué la Parte B es alta si el corpus curado está bien? Porque el conector general etiquetaría mal cualquier evento nuevo cargado en la demo (`automatic.py:166`).
4. ¿Por qué la Parte C es media? Porque la auditoría es del rol 4 y su contrato no está acordado (`Pendientes_rol_1.md`, punto 3); basta proponerlo con una función pura.
5. ¿Por qué la sección a dos columnas queda fuera? Porque arreglarla cambia los cortes y los ids (porqués anteriores), y el rol 3 ya la mitiga.

## Criterios de aceptación

- `make test-ingesta` en verde, con las pruebas nuevas, sin red, sin Tesseract y sin base de datos.
- `make test-recuperacion` sigue pasando la prueba de aceptación del paquete (la de integración requiere `db-up`).
- Ningún archivo fuera de los asignados a cada parte.

## Al terminar

Responde con:

- los archivos tocados por parte;
- el resumen de `make test-ingesta`;
- cada prueba nueva y qué cubre;
- las decisiones donde el encargo no era claro.

No amplíes el alcance.

## Parte D (añadida el 17 de noviembre): ruido de OCR no indexable

La corrida real con `tesseract-ocr-spa` sobre las páginas 3 y 4 de la modificación del 222, hecha por el gestor en una copia, recuperó 7 fragmentos.

- **Buenos:** `:00014` a `:00016`, con 25, 101 y 40 palabras de 4 o más letras. Son el acuerdo de la Modificación No. 1.
- **Ruido de sellos y firmas:** `:00017`, `:00019` y `:00020`, con 9, 3 y 9 palabras.
- **Poco texto:** `:00018`, con 10 palabras. Es el encabezado de la página 4 con "Anexo: en 11 hojas", que ya cubre la advertencia humana.

Archivos: solo `src/licigt/ingesta/reextraer.py` y su prueba.

- Un fragmento de OCR solo es indexable si tiene al menos 20 palabras de 4 o más letras. Si no, queda con `indexable = false` y `estado_calidad = "ruido_ocr"`, y no entra en `chunks.jsonl`, igual que los otros no indexables.
- El umbral es una constante con un comentario que cite esta medición.
- **Pruebas:** un fragmento de sellos con 3 palabras no es indexable; uno con 25 sí lo es.
