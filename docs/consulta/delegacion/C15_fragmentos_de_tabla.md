# Encargo C15: el rol 3 entiende los fragmentos de tabla

Para el implementador. Rama `rol/consulta`. No commitees.

Lee primero:

- [`AGENTS.md`](../../../AGENTS.md);
- [R3](../../ingesta/delegacion/R3_tablas_dos_columnas.md);
- [C14](C14_lista_sin_llm_y_publicacion_parcial.md);
- `validacion.py` (`normalizar_cita`, `_mapa` y la comparación de literales), `generacion.py`, `lista.py` (`tramo_literal`), `requisitos.py` (`encontrar_fechas`) y `herramientas.py`, con sus pruebas;
- `diag_resultados_r3.json` y `c14/prop.py`, en el scratchpad del gestor (subcarpeta `r3/`).

## Origen

Desde R3, las tablas de descripción llegan como un fragmento de tipo `tabla`, con filas `| numeral | título | texto |` y el texto de cada celda contiguo. Medido con los servicios reales:

- **Citas:** el modelo cita las filas sin las barras, así que `cita_no_literal` aparece en el primer intento de las preguntas 3 y 9.
- **Lista:** de un fragmento de tabla, la propuesta toma el primer tramo, que es la fila de encabezado ("| DOCUMENTO | PARÁMETROS…").
- **Fechas:** en la lista sin categoría desapareció la fecha del 19 de julio (inducción).

## Archivos

`validacion.py`, `generacion.py`, `lista.py`, `requisitos.py` y `herramientas.py`, con sus pruebas. Si el contrato del ítem cambia, también `web/src` (presentación) con Vitest.

## Cambios (prueba en rojo primero)

### 1. Las barras de tabla no rompen la cita

- En `normalizar_cita` y en la comparación de literales, el separador de celda ` | ` (una barra con espacios alrededor, y la barra al inicio y al fin de una fila) se trata como un espacio, tanto en la cita como en el fragmento.
- El mapa de posiciones publica el tramo original del fragmento, con sus barras.
- Una barra dentro de una palabra o de un número no se toca.
- **Prueba:** una cita sin barras de una fila real del cronograma (`03791a34…:00041`) pasa y publica el tramo original. Siguen fallando todos los ataques de los scripts `c4_*` a `c8_*`.

### 2. El prompt explica las tablas

En la evidencia, un fragmento `tabla` lleva una línea que explica que cada fila es "numeral | título | texto" y que la cita puede copiar el texto de una celda o la fila sin barras. Sube `VERSION_PROMPT`.

### 3. Un ítem por fila en la propuesta de lista

- Para un fragmento `tabla`, cada fila con numeral o literal en la primera celda da un ítem.
  - **Cita:** el tramo contiguo `título | texto` de esa fila, que es literal del fragmento, recortado como en C14.
  - **Lo que se salta:** las filas de encabezado, sin numeral.
- En la web, ` | ` se muestra como ": " entre el título y el texto, sin cambiar la cita guardada.
- **Prueba:** el fragmento real del cronograma da un ítem por fila 2.2.1 a 2.2.7, y cada uno revalida en `lista_escritura`.

### 4. Fechas dentro de filas de tabla

- Averigua por qué la fecha "19 de julio de 2023" (fila 2.2.2, inducción) no sale en la propuesta sin categoría. Revisa `encontrar_fechas` con barras, la deduplicación y la verificación JEV, y corrígelo.
- **Prueba:** la tabla real del cronograma da sus fechas, cada una con su actividad.

## Verificación real

Los servicios ya están arriba: la base con el paquete R3 y `llama-server`. Usa el comando del `Makefile`, sin leer la llave, para correr:

- `scratchpad/r3/diag_run2_r3.py`: la tabla de las 10 preguntas;
- la propuesta de lista (`c14/prop.py`): número de ítems, cuántos revalidan y 5 ejemplos.

## Criterios de aceptación

- `make test-consulta` en verde, y Vitest y el build si se tocó la web.
- Ataques sin regresión.
- Las preguntas 3 y 9 no empeoran.

## Al terminar

Responde con:

- los archivos tocados;
- los resultados;
- las tablas reales;
- las decisiones donde el encargo no era claro.

No amplíes el alcance.
