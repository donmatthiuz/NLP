# Encargo C19: URL y correos en el texto de una afirmación

Para el implementador. Rama `rol/consulta`. No commitees.

Lee primero:

- [`AGENTS.md`](../../../AGENTS.md);
- [C7](C7_reglas_cerradas_F4.md) (las URL y los correos en el texto se rechazan) y [C18](C18_pista_de_conflicto_y_presentaciones.md);
- `generacion.py` (prompt del sistema), `validacion.py` (lista blanca y datos literales) y `orquestador.py` (`_desajustes` y el mensaje de regeneración), con sus pruebas;
- en el scratchpad del gestor, `c18m/diag_resultados.json` (pregunta de la plica) y `c18m/plica_alias.py`, que reproduce la validación de cada intento sin el LLM.

## Medido (corpus R5, LLM real)

- **Qué hace el modelo en la plica:** responde bien. La afirmación 3 cita la solvencia patronal de la modificación (`F6`, "31 de julio de 2023") y la 4, la de las bases ("31 de mayo de 2023").
- **Por qué falla:** el texto de la afirmación 3 copia la URL `https://servicios.igssgt.org` y da `texto_invalido`, porque "/" solo vale en "y/o". El mensaje de regeneración no dice qué carácter falla, así que el segundo intento repite la URL.
- **Cómo termina:** la publicación parcial descarta esa afirmación, el conflicto queda con un solo lado y la respuesta se abstiene. Es el comportamiento seguro, pero se pierde una respuesta correcta.

## Archivos

`generacion.py`, `validacion.py` (solo si hace falta para el literal) y `orquestador.py`, con sus pruebas.

## Cambios (prueba en rojo primero)

1. **Prompt.** El prompt del sistema dice que una URL o un correo del documento va como dato literal `{n}`, copiado de la cita, o se omite. Sube `VERSION_PROMPT`.
2. **Desajuste.** En `_desajustes`, si el texto de una afirmación con `texto_invalido` contiene una URL (`http`, `https`, `www.`) o un correo, se agrega la línea "la afirmación N contiene una URL o un correo; ponla como dato {n} con su literal o quítala", sin copiar la URL.
3. **Literal.** Comprueba que una URL copiada tal cual de la cita pasa como dato literal: lista blanca, `MAX_DATO` y separadores. Si hoy no pasa, haz que pase solo cuando el literal es un tramo exacto de la cita. Las reglas de C7 no se relajan para el texto fuera de los marcadores.

**Pruebas:**

- la afirmación de la plica con la URL en el texto produce el desajuste;
- con la URL como dato `{1}`, publica;
- una URL en el texto que no está en ninguna cita sigue rechazada;
- los ataques `c4_*` a `c9_*` y `c17/` sin regresión.

## Verificación real

- La base tiene R5 y la API en 8010 está arriba. No los toques.
- Corre `c16/diag.py` con `c16/run.sh` y copia las salidas a `c19m/`.
- Reporta las 10 preguntas, sobre todo la plica y el seguro de caución, con los errores de cada intento.

## Criterios de aceptación

`make test-consulta` en verde, sin regresión en los ataques.

## Al terminar

Responde con:

- los archivos tocados;
- los resultados;
- las mediciones;
- las decisiones donde el encargo no era claro.

No amplíes el alcance.
