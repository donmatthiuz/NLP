# Encargo C8: últimos hallazgos bajos de F4 (séptima pasada del adversario)

Para el implementador. Rama `rol/consulta`. No commitees.

Lee primero:

- [`AGENTS.md`](../../../AGENTS.md);
- [C7](C7_reglas_cerradas_F4.md);
- `src/licigt/consulta/validacion.py`, con sus pruebas.

## Origen

La séptima pasada no encontró hallazgos de severidad alta ni media. Las 30 afirmaciones honestas nuevas publican, el barrido da 932 de 932 y no hay regresiones. Quedan cuatro hallazgos bajos; los scripts `c7_*.py` están en el scratchpad del gestor.

## Archivos

Solo `validacion.py` y `test_validacion.py`. Si cambia el mensaje de regeneración, también `orquestador.py` y `test_orquestador.py`.

## Correcciones (prueba en rojo primero, en cada una)

- **H1 (sin inyección, latente):** un carácter cuyo NFKC empieza con un espacio seguido de una marca combinante (`´`, `˙`, `¨`, `¯`, `¸`, `˘`, `˚`, `˛`, `˜`, `˝`, `‾`, `￣`, `΄`) cuenta como signo en `_continua` y `_signo`, no como espacio.
  - **Prueba:** con el fragmento `Q 1{sep}500,000.00` y esos separadores, la cita parcial da `cita_no_literal` y el literal parcial, `dato_no_literal`.
- **H2 (sin inyección):** la regla de vigencia por la evidencia (A3 de C7) escala cuando la respuesta cita cualquier documento cuyo tipo no esté en `TIPOS_QUE_ESCALAN` (anexo, especificaciones, convocatoria, normativa, bases), no solo `bases`.
  - **Prueba:** `B001` copiado con `tipo_documento` `anexo` y `especificaciones`, con la modificación en la evidencia, escala.
- **H3 (requiere inyección):** `UNIDAD_ANTES` admite `(` o `,` entre la moneda y el marcador.
  - **Prueba:** `Q ({1})`, `Q. ({1})` y `Q, {1}` dan `unidad_fuera_de_literal`.
- **H4 (requiere inyección):** una palabra formada solo por `I` y `O`, con al menos dos `O` o con un signo `.`, `,` interno ("IOO", "IO.OOO", "IO,OOO"), o la palabra suelta "ll", da `dato_fuera_de_literal`.
  - **Pruebas:**
    - siguen publicando "SI", "ISO", "OS", "III" y los 30 casos de `c7_falsos.py`;
    - "ZOO", "SOO" y "BOO" quedan como riesgo declarado; no se añaden más letras.

## Criterios de aceptación

- `make test-consulta` en verde.
- `c7_falsos.py`, `c6_falsos.py` y `c5_falsos.py` publican todos sus casos.
- `c6_barrido.py` da 932 de 932.
- `c7_cierre.py` rechaza o escala H1 a H4.

## Al terminar

Responde con:

- los archivos tocados;
- el resumen de `make test-consulta`;
- cada hallazgo con su prueba;
- la salida resumida de los scripts.

No amplíes el alcance.
