# Encargo R2: ampliar el corpus con un evento reservado sin tocar los ids actuales

Para Codex u OpenCode. Rama `rol/consulta`. El gestor auditará el resultado y el agente `adversario` intentará refutarlo. No commitees.

## Decisiones para el visto bueno del usuario

- **Cuántos eventos se agregan.** Recomendado: **dos licitaciones de medicamentos de noviembre de 2026** que nadie haya usado: una **reservada** para la evaluación final y otra de **plantilla distinta** para diversificar. Se amplía de 5 a 7 eventos y de 6 a 8 PDF, y el cambio se anota en `Cambios_pendientes.md`, porque el anteproyecto dice "entre tres y cinco" (`Anteproyecto.md:177`, `:362`).
  - Alternativa A: mantener los 5 eventos y declarar como limitación que no hay evento reservado.
  - Alternativa B: agregar las 10 licitaciones de medicamentos de noviembre de 2026. Da más diversidad, pero cada evento nuevo cuesta revisión de casos, y ningún documento lo exige.
- **Qué eventos.** Recomendado:
  - `389-IGSS-2026` (formoterol, código 509): el archivo se llama `DOCUMENTOS-DE-LICITACION`, distinto de la plantilla `LICITACION-PUBLICA` de los demás. Queda pendiente confirmar que la plantilla es distinta al abrirlo.
  - `516-IGSS-2026` (metotrexato, código 669) como evento reservado.
  - Antes de fijarlos, el usuario los abre y descarta los que sean solo convocatoria sin bases (`Anteproyecto.md:181`). Por ejemplo, `374-IGSS-2026` está enlazado como `convocatoria-DA-374-2026-IGSS.pdf`.
- **Quién toca el evento reservado.** Recomendado:
  - no entra en `casos_desarrollo.json` del rol 2, ni en el sondeo de JEV, ni en las preguntas de desarrollo de F7;
  - solo lo usa el banco final del rol 4;
  - se anota en `Avisos_del_rol_1.md` para los roles 2 y 4.
- **Segundo par auténtico de versiones.** Recomendado: no buscarlo en este encargo. El portal no muestra modificaciones ni aclaraciones en las filas revisadas, y el 222 ya aporta los dos casos temporales (`Seleccion_del_corpus.md:10`).

## Lee primero

- [`AGENTS.md`](../../../AGENTS.md);
- `docs/ingesta/Seleccion_del_corpus.md`, `docs/ingesta/Corpus_IGSS.md` y `docs/ingesta/delegacion/R1_ingesta.md`;
- `entregables/recuperacion/README.md`;
- `src/licigt/ingesta/download.py`, `prepare_corpus.py`, `pipeline.py` y `handoff.py`, con sus pruebas;
- `src/licigt/recuperacion/indice.py` (`leer_paquete` e `importar`), solo para lectura.

## Origen

**Qué pidió el usuario:** "hay que hacer el script de documentos; descargó 6 documentos, eso está mal, deberían ser más".

**Por qué hay 6 PDF.** No es un fallo del script: es la selección.

- `download_selected` baja **todos** los PDF que enlaza cada fila del portal para los eventos indicados (`download.py:59`, que usa `event.pdf_urls`).
- Cada fila del portal enlaza **un solo PDF**. Lo comprobé el 17 de noviembre en `proveedores/?y=2026` y `?y=2023`: ninguna de las filas revisadas tiene modificación, aclaración ni anexo adicional.
- De ahí salen los 6 PDF:
  - 5 eventos seleccionados (`Seleccion_del_corpus.md:13`, "cinco licitaciones y seis PDF");
  - más las bases del 222, que se añadieron a mano con `--pdf-adicional`, porque la fila de 2023 enlaza solo la modificación (`Seleccion_del_corpus.md:25`).
- `prepare_corpus.py:13-20` fija esos 6 PDF por SHA-256.

**Qué exige la evidencia:**

- **Instrucciones del curso** (`docs/presentaciones/Proyecto Final CC3103_ Sistema NLP_RAG Agéntico Empresarial-1.pdf`, secciones 5.2, 5.3 y 8): no fijan un número de documentos. Piden fuentes documentadas, una ingesta reproducible y al menos 20 casos, incluidos 2 sin respuesta y 2 de vigencia.
- **Anteproyecto:**
  - "entre tres y cinco licitaciones con documentación suficiente" (`Anteproyecto.md:177`, `:362`);
  - "el número de casos corresponde a preguntas o tareas de evaluación, no al número de licitaciones" (`Anteproyecto.md:150`);
  - "cuando el tamaño lo permita, se reservará un evento distinto para evaluación" (`Anteproyecto.md:382`);
  - un riesgo alto: "resultados poco representativos por corpus pequeño y similar", con la mitigación de diversificar y hacer una evaluación reservada por evento (`Anteproyecto.md:431`).
- **El evento reservado ya no existe:**
  - `Seleccion_del_corpus.md:11` proponía `368-IGSS-2026` como "conjunto de prueba separado";
  - pero el rol 2 ajustó sus umbrales con 27 casos, 5 de ellos del 368 (`Recuperacion.md:29`; `casos_desarrollo.json:149-209`);
  - y el mismo rol 2 pide calibrar "con el banco del rol 4 y un evento reservado" (`Recuperacion.md:38`, `:61`; `Pendientes.md:74`).
- **Plantillas parecidas:** 399, 363 y 368 comparten plantilla (`Seleccion_del_corpus.md:22`), y el anteproyecto pide diversidad de formatos (`Anteproyecto.md:362`).

Conclusión: el número de PDF por evento está completo según lo que publica el portal. Lo que falta es **un evento que nadie haya visto**, para que la evaluación final sea honesta, y algo de diversidad de plantilla. El anexo de 11 hojas del 222 no está en la fila del portal; buscarlo es tarea manual de R1.

## Archivos

- **Nuevos:** `src/licigt/ingesta/ampliar.py` y `src/licigt/ingesta/tests/test_ampliar.py`.
- **Modificados:** `docs/ingesta/Seleccion_del_corpus.md` y `docs/ingesta/Corpus_IGSS.md`, solo después de la corrida real.
- No toques:
  - `automatic.py` ni `test_automatic.py` (son de R1, Parte B);
  - `reextraer.py` (R1, Parte A);
  - `prepare_corpus.py`, que queda como registro histórico de la carga del 14 de noviembre;
  - `entregables/recuperacion/` a mano;
  - el `Makefile`.
- **Orden con R1:** R2 corre después de que R1-A haya escrito su ZIP con el OCR. El ZIP de entrada de R2 es el de salida de R1-A, así no se pisan. Si `reextraer.py` deja una función reutilizable para reescribir el ZIP de forma atómica, úsala; si no, sigue el patrón de `handoff.export`.

## Cambios (prueba en rojo primero, en cada uno)

### 1. `ampliar.py`: añadir documentos a un ZIP existente sin reescribir los que ya están

- **Entrada:**
  - el ZIP;
  - el `tenant_id`, que debe coincidir con el `tenant_id` del inventario;
  - una o más descargas preparadas por `download.py`, cada una con su PDF y su JSON;
  - por cada descarga, `tipo_documento`, `document_key` y, si aplica, `relacion_documental`.
- **Salida:** un ZIP nuevo, escrito de forma atómica (temporal y después `replace`).
- **Qué hace:**
  - verifica el SHA-256 de cada PDF contra su JSON y su nombre de archivo, como `prepare_corpus.py:28-29`;
  - si ese SHA-256 ya está en el inventario del ZIP, falla sin escribir nada: no hay duplicados;
  - ingiere cada documento nuevo con `IngestionService` en un directorio temporal y calcula el `evento_id` con `event_id_for` (determinista);
  - escribe el ZIP de salida:
    - copia **byte a byte** todas las entradas existentes, salvo `chunks.jsonl` e `inventario.json`;
    - añade `originales/`, `manifiestos/` y `procedencia/` de cada documento nuevo;
    - agrega al final de `chunks.jsonl` las líneas nuevas, sin reordenar las existentes;
    - actualiza `inventario.json`: `documents`, `chunks_indexables`, `generated_at` y `sha256_chunks_jsonl`.
- **Lo que nunca cambia:** el `doc_id`, el `chunk_id` y los bytes de los documentos que ya estaban. En particular `03791a3471c04c0f9cc260814564756e` y `d41480e5b0ce4c16bf18f66225ada2dc`, que usan las pruebas y encargos de los roles 2 y 3.
- **Ejecución:**

```bash
PYTHONPATH=src python -m licigt.ingesta.ampliar --zip <entrada> --tenant-id empresa_demo --documento <pdf>:<tipo>:<document_key>[:<relacion>] --salida <ruta>
```

- **Pruebas** (primero en rojo, sin red ni Tesseract; con un ZIP de prueba de 2 documentos armado en la prueba y PDF mínimos generados en memoria o fijados en la prueba):
  - después de ampliar, cada entrada previa es byte a byte igual y cada `chunk_id` previo sigue en su misma posición dentro de `chunks.jsonl`;
  - el documento nuevo aparece en el inventario con su `evento_id` determinista, y `sha256_chunks_jsonl` coincide;
  - un PDF cuyo hash ya está en el ZIP hace fallar sin escribir salida;
  - un hash que no coincide con el JSON de la descarga hace fallar sin escribir salida;
  - un `tenant_id` distinto del inventario hace fallar;
  - un `tipo_documento` de modificación sin `relacion_documental` hace fallar;
  - el ZIP de salida pasa `leer_paquete` del rol 2, sin base de datos.

### 2. Corrida real (la hace el usuario; el implementador solo deja los comandos en el README del paquete)

1. El usuario abre los PDF de los eventos aprobados en el portal y confirma que son bases completas, no una convocatoria (`Anteproyecto.md:181`).
2. `PYTHONPATH=src python -m licigt.ingesta.download --numero-evento 389-IGSS-2026 --numero-evento 516-IGSS-2026` usa la red y lo corre el usuario.
3. `ampliar` sobre el ZIP de salida de R1-A.
4. Revisión manual de una muestra de fragmentos de cada documento nuevo contra su página.
5. Se reemplaza `entregables/recuperacion/empresa_demo.zip`, y se actualizan `Corpus_IGSS.md` (filas nuevas, total de fragmentos), `Seleccion_del_corpus.md` (los eventos nuevos, el reservado marcado como tal y el 368 marcado como usado en desarrollo) y el README del paquete.

### 3. Avisos (al final, a mano)

- **`docs/recuperacion/Avisos_del_rol_1.md`:**
  - reimportar con `make importar`: `importar` borra y reinserta por `doc_id` (`indice.py:89`), así que los fragmentos existentes no cambian;
  - el evento reservado no entra en `casos_desarrollo.json`.
- **`docs/plataforma/Avisos_del_rol_1.md`:** cuál es el evento reservado del banco final.
- **`docs/anteproyecto/Cambios_pendientes.md`:**
  - la sección 12 pasa de 5 a 7 licitaciones;
  - el motivo: el 368 se usó en desarrollo y hacía falta un evento reservado (`Anteproyecto.md:382`).

## Criterios de aceptación

- `make test-ingesta` en verde, sin red.
- Ningún `doc_id` ni `chunk_id` existente cambia, y las pruebas lo verifican.
- `make test-consulta` y las pruebas sin base de datos del rol 2 siguen en verde con el ZIP nuevo.
- Sin credenciales ni texto completo de PDF en registros ni avisos.

## Al terminar

Responde con:

- los archivos tocados;
- el resumen de `make test-ingesta`;
- cada prueba del punto 1;
- los comandos de la corrida real;
- las decisiones donde el encargo no era claro.

No amplíes el alcance.
