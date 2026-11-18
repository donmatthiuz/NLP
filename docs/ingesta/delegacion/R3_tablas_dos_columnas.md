# Encargo R3: tablas de descripción con pdfplumber

Para el implementador. Rama `rol/consulta`. No commitees.

Lee primero:

- [`AGENTS.md`](../../../AGENTS.md);
- la investigación [I7](../../consulta/investigacion/I7_extraccion_dos_columnas.md), completa, con sus scripts en el scratchpad del gestor (`i7/strat.py`, `i7/measure2.py` y `i7/medidas2.json`);
- [R2](R2_corpus.md);
- `src/licigt/ingesta/pdf.py`, `pipeline.py`, `reextraer.py` y `reproducir.py`, con sus pruebas.

## Decisiones del usuario (17 de noviembre)

El usuario aprobó las seis decisiones de I7:

1. **Estrategia:** se toma la geometría de la tabla con `pdfplumber` y cada palabra se asigna a su celda. Una salvaguarda compara el multiconjunto de palabras con el texto actual de la región; si no coincide, se queda el texto actual.
2. **Dependencia:** se agrega `pdfplumber` (MIT) al `requirements.txt` de ingesta y a `shell.nix` si existe. No se usa PyMuPDF.
3. **Alcance:** solo tablas de descripción, con un numeral o literal en la columna 0 y texto largo. Los cuadros de cantidades quedan como hoy.
4. **Versionado:** no se sube `version_ingesta`. Se agrega el campo opcional `extraccion`, con el método y su versión, en el manifiesto y en el inventario.
5. **Migración:** toda en una sola entrega.
6. **Formato de fila:** `| numeral | título | texto |`. Así `HEADING` no parte el cronograma, y `tabla_markdown` queda lleno.

## Parte A: extracción y paquete candidato

### Código (prueba en rojo primero)

- **`pdf.py`:** extrae las tablas de descripción según I7 y deja intacto lo demás de la página (texto fuera de la tabla, OCR y avisos).
- **`pipeline.py`** (`_units` y la sección): una tabla de descripción forma una unidad, cuya sección es su encabezado ("2.2 CRONOGRAMA DE ACTIVIDADES"). Cada fila conserva su numeral.
- **Pruebas con PDF sintéticos** (genéralos en la prueba, por ejemplo con reportlab si está disponible, o usa un PDF pequeño de fixture):
  - una tabla de tres columnas sale con sus filas unidas;
  - la salvaguarda devuelve el texto actual si una palabra no coincide;
  - un cuadro de cantidades no cambia;
  - no se pierde ni se añade ningún dígito.

### Paquete candidato

- Genera el ZIP candidato **sin red** con `reproducir --desde-zip entregables/recuperacion/empresa_demo.zip`, con la salida en `<scratchpad>/r3/empresa_demo_r3.zip`.
- Usa OCR, porque Tesseract 4.1.1 con `spa` está instalado.
- **No reemplaces el ZIP del repo:** lo confirma el usuario.
- **Comprobaciones del candidato:**
  - en el cronograma 2.2 del 222 (bases y modificación 1) las 6 filas quedan unidas;
  - el conteo de dígitos coincide documento por documento;
  - la prueba de reproducibilidad pasa contra el candidato (`LICIGT_ZIP_CORPUS`).

### Tabla de equivalencias de ids

- Escribe `src/licigt/ingesta/equivalencias_r3.json`, que relaciona cada `chunk_id` viejo citado en el repo con el nuevo cuyo texto contiene la misma cita.
  - Si no hay uno único, se marca para revisión manual.
- Escribe el script `src/licigt/ingesta/migrar_ids.py`, que reemplaza los ids viejos por los nuevos en una lista de archivos, con vista previa sin `--aplicar`.
  - **Pruebas:** su prueba usa un archivo temporal.

### Al terminar la parte A

Responde con:

- los archivos tocados;
- `make test-ingesta` y `make test-consulta`;
- la tabla del cronograma antes y después, con un ejemplo real;
- los ids que cambian;
- la ruta del candidato y el comando `cp` para el usuario.

## Parte B: migración (después de que el usuario reemplace el ZIP)

- Aplica `migrar_ids.py` a las pruebas del rol 3 (`test_requisitos`, `test_generacion`, `test_ejemplos_web` y las demás que citen ids), a los ejemplos de la web (`web/src/ejemplos/*.json` y `estado.test.ts`) y a los documentos que citen ids concretos (`Demo_222.md` y los encargos vigentes).
- Revisa a mano cada id marcado para revisión.
- Ajusta los textos de prueba que citaban el texto intercalado. Ahora la cita debe ser el texto contiguo.
- Escribe `docs/recuperacion/Avisos_del_rol_1.md` con la nota de reimportar (`make importar`, ids nuevos, casos por página sin cambios).
- Actualiza `Corpus_IGSS.md`, `entregables/recuperacion/README.md` y `Auditoria_F4.md` (riesgo H3).
- **Verificación:**
  - `make test-ingesta`, `make test-consulta`, `pnpm --dir web build` y Vitest en verde;
  - reimporta con `make importar`;
  - corre `diag_run2.py` y la propuesta de lista con los servicios reales, y reporta la tabla de las 10 preguntas y la calidad de los ítems antes y después.

## Reglas

- Sin `keys/`. Sin git.
- Los servicios ya están arriba: la base y `llama-server`. Para Python con la base, usa el comando que arma el `Makefile`, sin leer la llave.
- Nada en la raíz del repo.
