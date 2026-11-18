# Encargo C17: revisión acotada en la lista y décima pasada

Para el implementador. Rama `rol/consulta`. No commitees.

Lee primero:

- [`AGENTS.md`](../../../AGENTS.md);
- [C14](C14_lista_sin_llm_y_publicacion_parcial.md) a [C16](C16_novena_pasada_y_demo.md);
- `lista.py`, `lista_escritura.py`, `herramientas.py`, `orquestador.py` y `validacion.py`, con sus pruebas;
- en `src/licigt/recuperacion/busqueda.py`, `_alertas`, para entender `numerales_modificados` y `chunk_ids_afectados` (no lo edites);
- en el scratchpad del gestor:
  - `r4m/prop.txt` y `r4m/diag_resultados.json`, que son la medición con el paquete R4;
  - `r4m/alertas.py`, que imprime las alertas de conflicto de la plica.

## Archivos

- `src/licigt/consulta` y sus pruebas.
- No toques `web/` ni `src/licigt/ingesta`: otros agentes trabajan ahí en paralelo.

## Decisión del usuario (17 de noviembre)

**Revisión en la lista: solo los afectados.** Hoy cualquier alerta `posible_conflicto` marca todos los ítems: 31 de 31 en la demo. La modificación del 222 solo cambia los numerales 2.2 y 2.7.

## Cambios (prueba en rojo primero)

### 1. Revisión acotada en la propuesta de lista

Un ítem de requisito pide revisión si se cumple al menos una de estas condiciones:

- su fragmento está en `chunk_ids_afectados` de alguna alerta `posible_conflicto`;
- su fragmento es del documento de la alerta (`doc_id` de la modificación o aclaración);
- el numeral principal de su sección está en `numerales_modificados` de la alerta;
- se cumple la regla H6 de C16: la evidencia trae un fragmento de modificación o aclaración que comparte el numeral principal.

Detalles:

- **Lo que deja de marcar:** `resultado.posible_conflicto` solo, sin ninguna de esas condiciones, ya no marca el ítem.
- **Lo que viaja:** `ResultadoHerramienta` lleva lo que haga falta de las alertas (ids afectados, documentos y numerales), sin texto.
- **Motivo:** un solo texto, sin repetir "requiere revisión humana", que ya está en la banda. Por ejemplo: "Una modificación o aclaración del evento toca esta sección; el sistema no decide cuál está vigente".
- **Fechas:** sus reglas no cambian.
- **Revalidación:** si `lista_escritura` recalcula la revisión, aplica la misma regla.

**Pruebas:**

- con alertas como las del 222 (numerales 2.2 y 2.7, afectados `:00052`), un ítem de la sección 2.8 no pide revisión; uno de 2.7 y uno del documento de la modificación sí la piden;
- una alerta sin numerales ni afectados marca solo los ítems del documento de la alerta;
- con la propuesta real (`c16/prop2.py`), el número de ítems que piden revisión baja de 31. Repórtalo.

### 2. Ítems que solo presentan una lista

- **Qué se descarta:** un tramo que termina en ":" y tiene menos de 15 palabras de contenido es una presentación, no un requisito. Por ejemplo:
  - "2.8 REQUISITOS FUNDAMENTALES Se consideran Requisitos Fundamentales los siguientes:";
  - "Fotocopia legible legalizada de los documentos: siguientes:".
- **Encabezado con una referencia:** también es basura un encabezado en mayúsculas seguido solo de una referencia entre paréntesis, como "ESPECIFICACIONES GENERALES. (Artículo 16 del REGLAMENTO).".
- **El fragmento no se pierde:** si el primer tramo de un fragmento no tabular es basura, se toma el siguiente tramo legible del mismo fragmento, con las mismas reglas de C14.

**Pruebas:**

- los ejemplos anteriores se descartan;
- el fragmento real del 2.8 da un ítem con su primer requisito;
- reporta cuántos ítems cambian con el corpus real.

### 3. La regeneración nombra los fragmentos del otro documento

- **El cambio:** cuando el error es `falta_segunda_fuente`, el mensaje de regeneración dice qué alias de la evidencia (`F7`, `F12`…) son del documento que falta citar. Las demás instrucciones siguen igual: si ese documento trata el mismo dato, cítalo; si no, abstente.
- **Origen:** en la plica, el modelo citó la solvencia patronal de las bases ("31 de mayo de 2023") sin la modificación, que en el fragmento `d41480…:00005` la cambia a "31 de julio de 2023". El validador lo rechazó bien, pero el modelo no supo qué fragmento citar.
- **Prueba:** el mensaje contiene los alias correctos y ningún texto del fragmento.

### 4. Hallazgos de la décima pasada del adversario

Los scripts están en `c17/`, en el scratchpad del gestor (`h6.py`, `h7.py`, `h2_500.py`, `h2_falsos.py` y `basura.py`). Se corren con `PYTHONPATH=src python3`, sin base.

- **A1 (media): las fechas de una sección modificada piden revisión.**
  - Un ítem de fecha cuyo fragmento comparte numeral principal con una modificación o aclaración de la evidencia, o que cumple la regla del punto 1, pide revisión con el motivo de modificación, salvo que ya tenga otro motivo.
  - La respuesta de la lista lleva `needs_human_review=True` si la evidencia trae un fragmento de `modificacion` o `aclaracion`, como hace `validacion.py`.
  - **Prueba:** caso A de `h6.py`.
- **A2 (baja): numerales que una modificación nombra en su texto.**
  - A los numerales modificados se suman los que el texto del fragmento de la modificación o aclaración nombra como "numeral X.Y" o "subnumeral X.Y", además del de su sección.
  - R5 corrige la sección en la ingesta, pero esta regla se queda como salvaguarda.
  - **Prueba:** caso B de `h6.py`.
- **A6 (baja): numeral principal de una sección mal detectada.** Para las secciones de una modificación o aclaración, el numeral principal necesita al menos dos componentes (`d.d`). "2 vial, Código IGSS…" no marca las secciones "2." de las bases.
  - **Prueba:** caso C de `h6.py`.
- **A3 (baja): una vigencia descartada con otras palabras.** En `_publicacion_parcial`, la respuesta escala (`needs_human_review=True`) si alguna afirmación descartada tiene un dato literal de fecha o menciona modificación, aclaración, cambio, "rige", "actual", "aplica" o "vigor".
  - **Prueba:** los casos de `h7.py`.
- **A4 (baja): una fuente inválida dentro de una sola afirmación.** En `validacion.py`, si construir la `Fuente` de una cita falla (por ejemplo, porque el tramo original con barras pasa de 500 caracteres), el error lleva el índice de la afirmación y de la cita (`esquema_invalido`), para que la publicación parcial pueda descartar solo esa afirmación.
  - **Prueba:** `h2_500.py` publica la afirmación válida, y `h2_falsos.py` no rechaza ninguna cita legítima por esta causa.
- **A7 (baja): falsos descartes de basura.** No es basura un tramo que empieza con un numeral o literal ("a)", "1.", "2.27.4") y contiene alguna palabra en minúscula.
  - **Prueba:** el fragmento `222:00107` da "a) Extendida a favor del INSTITUTO.". Reporta de nuevo los conteos de `basura.py`.
- **A5:** sin código. El carácter de los literales del 2.7 queda como limitación declarada en `Pendientes.md`, por decisión del gestor.

## Verificación real

- Los servicios ya están arriba: la base con el paquete R4, el LLM y la API en 8010, que no hay que tocar.
- Corre en proceso, con `c16/run.sh`:
  - `c16/diag.py`: las 10 preguntas;
  - `c16/prop2.py`: la lista.
- Copia las salidas a `c17m/` (`c17/` es del adversario), porque `diag.py` sobrescribe su JSON.
- **Reporta:** la tabla de las 10 preguntas (sobre todo la plica), y de la lista los ítems, cuántos piden revisión, la distribución del carácter y 5 ejemplos.

## Criterios de aceptación

- `make test-consulta` en verde.
- Los ataques `c4_*` a `c9_*` sin regresión.

## Al terminar

Responde con:

- los archivos tocados;
- los resultados;
- las mediciones;
- las decisiones donde el encargo no era claro.

No amplíes el alcance.
