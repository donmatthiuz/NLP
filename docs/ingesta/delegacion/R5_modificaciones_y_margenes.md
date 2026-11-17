# Encargo R5: secciones de las modificaciones y encabezados repetidos

Para el implementador. Rama `rol/consulta`. No commitees.

Lee primero:

- [`AGENTS.md`](../../../AGENTS.md);
- [R3](R3_tablas_dos_columnas.md) y [R4](R4_orden_en_tablas.md);
- `src/licigt/ingesta/pipeline.py`, sobre todo:
  - `HEADING`;
  - `_units`;
  - `_without_repeated_margins`;
  - `make_chunks`;
- `pdf.py`, `reproducir.py` y `migrar_ids.py`, con sus pruebas;
- en `src/licigt/recuperacion/busqueda.py`, `NUMERAL_MODIFICADO` y `_alertas`, solo para entender cómo usa el rol 2 la sección y los numerales (no lo edites).

## Decisión del usuario (17 de noviembre)

El usuario aprobó corregir en la ingesta:

- la sección de los fragmentos de las modificaciones;
- los encabezados y pies de página repetidos.

## Hallazgos (medidos con el paquete R4)

### 1. Sección equivocada en la modificación

En la modificación 1 del 222, el fragmento `d41480e5b0ce4c16bf18f66225ada2dc:00005` (página 2) lleva la sección `2.2 CRONOGRAMA DE ACTIVIDADES`, pero contiene:

> Punto 2: Se modifica la literal e) del subnumeral 2.7 LISTADO DE DOCUMENTOS QUE DEBERÁ CONTENER LA PLICA de los Documentos de Licitación, de acuerdo a lo siguiente: e) Solvencia Patronal ... al 31 de julio de 2023 ...

El rol 3 decide la revisión por el numeral de la sección. Con la sección equivocada, el cambio a la solvencia patronal (que en las bases dice "31 de mayo de 2023") se pierde en la lista. En la consulta de la plica, el fragmento de la modificación sale como si hablara del cronograma.

### 2. Encabezado repetido sin quitar

"Instituto Guatemalteco de Seguridad Social / Documentos de Licitación DA No. 222-IGSS-2023 / Departamento de Abastecimientos" queda al inicio de los fragmentos `:00001` y `:00005` de la modificación, y la lista lo propone como requisito.

- `_without_repeated_margins` exige que una línea se repita en al menos `max(3, …)` páginas.
- Una modificación de 4 páginas, con una de OCR y otra sin indexar, nunca llega a ese umbral.

## Cambios (prueba en rojo primero)

### 1. Puntos de una modificación o aclaración

- En los documentos de tipo `modificacion` o `aclaracion`, una línea que empieza por "Punto N:" (o "PUNTO N:") y nombra un numeral o subnumeral ("Se modifica la literal e) del subnumeral 2.7 LISTADO DE …") abre una unidad nueva.
- Su sección es el numeral y su nombre tal como aparecen ("2.7 LISTADO DE DOCUMENTOS QUE DEBERÁ CONTENER LA PLICA"), recortado como las demás secciones.
- El texto no cambia: no se quita ni se añade nada, solo cambia dónde se corta y qué sección lleva.
- Si la línea no nombra un numeral, no se toca.
- **Pruebas:**
  - texto sintético con "Punto 1: … subnumeral 2.2 CRONOGRAMA …" y "Punto 2: … subnumeral 2.7 LISTADO …", que da dos unidades con esas secciones;
  - con el ZIP real en memoria, el fragmento que contiene "Solvencia Patronal" en la modificación del 222 lleva una sección que empieza por "2.7".

### 2. Encabezados y pies repetidos en documentos cortos

- Ajusta el umbral para que, en un documento de 2 a 5 páginas, una línea de las 8 primeras o las 6 últimas que se repite en al menos 2 páginas cuente como margen.
  - La regla de los documentos largos no cambia.
  - Solo cuentan las páginas con texto: no la que no tiene capa de texto.
- Una línea que contiene un numeral de sección (`HEADING`) nunca se quita.
- Lo quitado sigue solo en el índice: el texto original de las páginas se conserva, como hoy.
- **Pruebas:**
  - sintética de 4 páginas con un encabezado de tres líneas en 2 páginas;
  - con el ZIP real, ningún fragmento de la modificación del 222 empieza por "Instituto Guatemalteco de Seguridad Social";
  - el número de dígitos de cada documento solo baja en los del encabezado quitado (repórtalo).

### 3. Celda de ancho completo en tablas de varias filas (décima pasada, R1)

- **El caso:** en el 222, página 33, y en el 327, página 34, la fila `f)` sale como `| f) | Fotocopia legible legalizada de los documentos | siguientes: |`. Es una celda de ancho completo partida en dos columnas por un hueco de 2,21 pt.
- **El cambio:** `_separacion_minima` (`SEPARACION_CELDAS`) se exige también, fila por fila, en las tablas de varias filas. Si en una fila el hueco entre dos columnas de texto es menor, esas celdas se funden en una, sin cambiar el orden de las palabras.
- **Prueba:** con el ZIP real, ninguna fila contiene "documentos | siguientes:", y el cronograma sigue con sus filas unidas.
- **Scripts del adversario:** `c17/r4_p33.py` y `c17/r4_fila_f.py`, en el scratchpad del gestor.

### 4. Equivalencias completas (décima pasada, R2)

R4 añadió un fragmento al 222 y otro al 327, así que los ids siguientes conservan el nombre pero apuntan a otro texto (`c17/r4_desplaza.py`).

- La tabla de equivalencias de este paquete cubre **todos** los ids cuyo texto normalizado cambia respecto del paquete actual del repo, no solo los citados en el repo.
- Agrega una prueba: cada id viejo con otro texto tiene su entrada.
- Anota en `docs/recuperacion/Avisos_del_rol_1.md` que, al reimportar, las listas guardadas que citen ids desplazados deben migrarse con esa tabla.

## Paquete candidato

- Regenera el candidato sin red con `reproducir --desde-zip` y déjalo en `<scratchpad>/r5/empresa_demo_r5.zip`.
- **No reemplaces el ZIP del repo.**
- Con `migrar_ids.py` en vista previa, informa qué ids citados en el repo cambian (pruebas, ejemplos de la web y documentos).
  - Escribe `equivalencias_r5.json` según el punto 4. Si el usuario lo aprueba, `equivalencias_r4.json` (sin commit) queda reemplazado.
  - Si cambian, aplícalo solo después de que el usuario copie el ZIP.

## Al terminar

Responde con:

- los archivos tocados;
- `make test-ingesta` (con `LICIGT_ZIP_CORPUS` apuntando al candidato) y `make test-consulta`;
- las secciones de la modificación del 222 antes y después;
- los fragmentos que pierden el encabezado;
- los ids que cambian;
- el comando `cp` para el usuario.

## Reglas

- Sin `keys/` y sin git.
- Solo `src/licigt/ingesta`.
- Nada en la raíz del repo.
