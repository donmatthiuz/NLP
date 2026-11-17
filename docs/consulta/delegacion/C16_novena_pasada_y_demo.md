# Encargo C16: novena pasada (H2 a H7) y hallazgos de la demo

Para el implementador. Rama `rol/consulta`. No commitees.

Lee primero:

- [`AGENTS.md`](../../../AGENTS.md);
- [C14](C14_lista_sin_llm_y_publicacion_parcial.md) y [C15](C15_fragmentos_de_tabla.md);
- [`Demo_222.md`](../Demo_222.md), sección de hallazgos;
- `validacion.py`, `lista.py`, `herramientas.py`, `orquestador.py` y `api.py`, con sus pruebas;
- en `web/src`, la lista y el resultado;
- en el scratchpad del gestor, los scripts `c9_*.py` (con `c9_corpus.py` para el corpus nuevo, y `c9_ataques.py`, `c9_lista.py`, `c9_lista2.py`, `c9_cortes.py` y `c9_falsos.py`).

## Archivos

Los anteriores con sus pruebas, y `web/src` con Vitest. No toques `src/licigt/ingesta`: otro agente corrige ahí el H1 en paralelo.

## Cambios (prueba en rojo primero)

### H2 (media): citas que cruzan filas de tabla

Una cita cuyo tramo original abarca el final de una fila y el inicio de la siguiente (contiene un fin de fila `|` y un salto de línea seguido de `|`) da `cita_cruza_filas`. Las citas dentro de una sola fila, con o sin barras, siguen publicando.

**Prueba:** el caso S1 de `c9_ataques.py`.

### H3 (media): ítems de fila que se cortan antes del dato

- Para una fila de tabla, la cita del ítem es `título | texto` completo hasta 500 caracteres. Solo se recorta si pasa de ese tope, y nunca justo antes de un número ni dentro de un dato.
- `FIN_ORACION` no toma como fin de oración un ordinal ("7ª.", "1º.") ni una abreviatura antes de un número ("No.").

**Pruebas:**

- el ítem de la fila 2.2.6 del cronograma real contiene "31 de julio de 2023";
- ningún ítem del corpus termina justo antes de un número (`c9_cortes.py`).

### H4 (media): fechas repetidas dentro de una tabla

- Cada fecha candidata da su propio ítem.
- La huella incluye la fila (o la posición) y la cita es el tramo contiguo de la fila desde el título hasta la fecha.

**Prueba:** sin JEV, el número de ítems de fecha de `:00041` es igual al de `encontrar_fechas`, y cada uno cita su fila.

### H5 (media): pasaje de JEV en tablas

El contexto posterior de una candidata en una fila de tabla termina en el fin de esa fila.

**Prueba:** con un JEV espía, ningún pasaje contiene el numeral de otra fila.

### H6 (baja): revisión por modificación en la lista

- Un ítem requiere revisión si la evidencia trae un fragmento de `modificacion` o `aclaracion` cuya sección comparte el numeral principal con la del ítem. Por ejemplo, "2.2" para las filas 2.2.x, o "2.7" para sus literales.
- Se mantiene la regla de alerta `posible_conflicto`.
- Ya no se marca **todo** por `resultado.needs_human_review`, que es lo que en la demo marcó 39 de 41 ítems.

**Pruebas:** H6 de `c9_lista2.py`, y que los ítems de secciones no modificadas no pidan revisión.

### H7 (baja): vigencia en una afirmación descartada

En `_publicacion_parcial`, si una afirmación descartada coincide con `VIGENCIA`, la respuesta lleva `needs_human_review=True`.

**Prueba:** el caso 4c de `c9_ataques.py`.

### Demo: ítems basura y carácter

**Ítems basura.** No se propone un ítem si:

- tiene menos de 4 palabras de contenido;
- es solo un encabezado (numeral más un título en mayúsculas sin verbo, como "4. ESPECIFICACIONES TÉCNICAS" o "CANTIDAD TOTAL");
- es un resto de frase (empieza en minúscula y tiene menos de 40 caracteres, como "correspondiente.").

Reporta cuántos se descartan con el corpus real.

**Carácter.** Revisa por qué 39 de 41 salen `no_indicado`. `caracter_de_seccion` debe reconocer las secciones de las tablas (por ejemplo "2.7 LISTADO DE DOCUMENTOS…", "2.8 REQUISITOS FUNDAMENTALES" y "2.9 …"), tomando el encabezado vigente de la tabla. Reporta la distribución antes y después.

### Demo: `evento_id` en las rutas de la lista

La propuesta, el listado y los ítems guardados devuelven el valor que pidió la ruta (`222-IGSS-2023`), como la consulta desde C12. El repositorio sigue usando el id interno.

### Demo: panel de cobertura del evento

**`GET /api/eventos/{evento_id}/documentos`** (DESIGN.md, Interfaz: "se muestran los documentos incorporados al evento y qué información falta"):

- devuelve, por documento, tipo, versión oficial, páginas totales, páginas no indexadas, estado y las advertencias del inventario (por ejemplo, el anexo de 11 hojas);
- lo lee de la tabla `documentos` del rol 2 con la sesión por empresa, solo `SELECT`, como `resolver_evento`;
- sin texto de los PDF.

**En la web,** un panel "Documentos del evento" bajo el encabezado, con lo que falta destacado.

**Pruebas:** la ruta con un doble de conexión, y Vitest del panel.

## Verificación real

Los servicios ya están arriba: la base, el LLM y la API vieja en 8010, que no hay que tocar.

- Corre `diag_run2.py` (la versión de `r3/`) y la propuesta de lista con el comando del `Makefile`, en proceso, sin leer la llave.
- Reporta las 10 preguntas y la lista: ítems, cuántos piden revisión, distribución del carácter y 5 ejemplos.

## Criterios de aceptación

- `make test-consulta`, Vitest y el build en verde.
- Los ataques `c9_*` sin regresión.
- `c9_falsos` publica sus casos.

## Al terminar

Responde con:

- los archivos tocados;
- los resultados;
- las mediciones;
- las decisiones donde el encargo no era claro.

No amplíes el alcance.
