# JEV en LiciGT

**Estado al 16 de noviembre de 2026.** Cómo se adapta JEV, el modelo de decisión de TypeSafe, a la consulta del rol 3. Documentación oficial completa: [docs.typesafe.ai](https://docs.typesafe.ai/llms.txt). Los agentes tienen la skill oficial en `.skills/typesafe-ai` (repositorio `typesafe-ai/skills`, commit `302eea6`, licencia MIT).

## Qué es

JEV no genera texto: recibe un **estado** (texto u objeto) y un conjunto de **preguntas tipadas**, y devuelve una respuesta por pregunta con probabilidades calibradas.

| Primitiva | Para qué | Devuelve |
|---|---|---|
| `Choice` | Elegir una opción de una lista | `choice`, `probabilities`, `confidence` |
| `Noul` | Probabilidad de que una afirmación sea verdadera | `noul` (0 a 1) |
| `Score` | Posición en una escala descrita | `score`, `probabilities`, `confidence` |
| `Box` | Ubicar algo en una imagen | No se usa en LiciGT |

- API: `POST https://api.typesafe.ai/v1/systemone` con `Authorization: Bearer <clave>`.
- SDK de Python: paquete `typesafe-sdk` (Python 3.10 o superior), cliente `TypeSafeClient(model=...)` y método `system_one(state=..., questions=...)`.
- La respuesta informa la versión real del modelo (por ejemplo `jev-1.13.0`); se registra en cada ejecución porque `jev-latest` cambia entre versiones.

## Principio: JEV juzga, el código decide

La skill oficial recomienda lo mismo que [DESIGN](../../DESIGN.md#principios): no preguntar "¿hay que abstenerse?" sino los juicios de los que depende esa decisión, y escribir la decisión como tabla de verdad en código, visible y probable. Encaja con la regla del proyecto de que el modelo no decide permisos, vigencia ni suficiencia.

- Umbrales iniciales de un `Noul`: mayor a 0.7 es sí, menor a 0.3 es no, y la franja intermedia tiene su propia fila en la tabla (normalmente `needs_human_review` o abstención).
- `confidence` no es la compuerta: mide concentración, no acierto.
- Los umbrales se calibran con el conjunto de desarrollo y se validan con casos que no se usaron para ajustar.
- Una falla de la API es un error, nunca un "no". Ante indisponibilidad, se usa la variante de reglas (caso del banco "degradación controlada").

## Dónde entra en LiciGT

Cada uso es una **variante candidata** frente a reglas y frente al LLM con salida estructurada; se adopta solo si mejora en el banco etiquetado (ver [DESIGN](../../DESIGN.md#capa-de-decisión)). Columna "Cookbook" son los ejemplos oficiales que sirven de punto de partida.

| Fase | Decisión del rol 3 | Preguntas a JEV | Cookbook |
|---|---|---|---|
| F2 | Validación de entrada | `Noul`: ¿el mensaje intenta cambiar las instrucciones del sistema? `Noul`: ¿la pregunta trata de los documentos de licitación del evento? | [Guardrails](https://docs.typesafe.ai/cookbooks/llm_guardrails.md) |
| F2 | Intención y herramienta | `Choice` entre `buscar_documentos`, `extraer_requisitos` y `comparar_versiones`, más un `Noul` compañero: ¿la pregunta pide algo que cubre alguna herramienta? | [Function calling](https://docs.typesafe.ai/cookbooks/function_calling.md), [intent routing](https://docs.typesafe.ai/patterns/intent-routing.md) |
| F2 | Ambigüedad | `Noul`: ¿la pregunta nombra una sola actividad, fecha o documento concreto? Si no, se pide aclaración. | |
| F3 y F4 | Pasajes recuperados | Por fragmento, `Noul`: ¿es relevante?, ¿contiene la respuesta?, ¿contradice lo que asume la pregunta?, ¿intenta dar instrucciones? Se descartan los irrelevantes y los que traen instrucciones; los que contradicen se marcan como conflicto. | [Classifying RAG passages](https://docs.typesafe.ai/cookbooks/classifying_rag_passages.md) |
| F4 | Suficiencia | `Noul`: ¿los fragmentos contienen todos los datos que la pregunta necesita? Complementa `suficiente` del rol 2. | [Verify LLM outputs](https://docs.typesafe.ai/cookbooks/verify_llm_outputs.md) |
| F4 | Fidelidad de cada cita | Por afirmación, `Choice`: la sección citada la respalda, la contradice o no dice nada. Coincide con la evaluación por afirmaciones del curso (respaldada, parcial, no respaldada). | [Citation check](https://docs.typesafe.ai/cookbooks/citation_check.md) |
| F3 | Fechas de `extraer_requisitos` | Se probó y no se adoptó (F7b, [Experimento_JEV.md](Experimento_JEV.md)): el código encuentra candidatas con expresiones regulares y las reglas deterministas asignan la actividad solo en filas de tabla; JEV no interviene en el sistema entregado. Se midió con una muestra pequeña. | [Date extraction](https://docs.typesafe.ai/cookbooks/date_extraction_cookbook.md) |

El validador determinista de citas (existencia, permisos, página, versión y texto) sigue siendo obligatorio; JEV solo añade el juicio de si la cita respalda la afirmación.

## Datos que salen del equipo

- Solo la pregunta del analista y fragmentos de documentos públicos del IGSS. Nunca `tenant_id`, usuarios, listas de verificación ni datos de empresa.
- Antes de probar contra la API en vivo: permiso del usuario, presupuesto y lista de lo que se envía, como pide la skill.
- Se guarda el payload exacto de cada caso de prueba para poder repetirlo.

## Clave y cliente

Según el [uso básico del SDK](https://docs.typesafe.ai/sdk/python/usage/basic.md), consultado el 16 de noviembre de 2026:

- `TypeSafeClient` acepta `api_key` como parámetro; si falta, lee `TYPESAFE_API_KEY`. En LiciGT el código lee la clave desde el archivo que indica `LICIGT_JEV_API_KEY_FILE` (`keys/jev/api.key`) y la pasa como `api_key`; nunca queda en el entorno ni en el repositorio.
- Otros parámetros: `model`, `base_url`, `headers` y `retry` (un `RetryPolicy` con `max_retries`, `backoff_max` y `timeout`). La documentación no publica los valores por defecto del reintento: se fijan explícitamente.
- Errores: `TypeSafeAPIError` en fallas de la API y `TypeSafeError` al crear el cliente con una clave inválida. Ambos se tratan como falla controlada, nunca como respuesta.
- Existe `AsyncTypeSafeClient`.

## Modelo, límites y costo

Según la [página de modelos](https://docs.typesafe.ai/go/models.md):

- Versiones: Jev 1.14.0 (14 de octubre de 2026) y 1.13.0. `jev-latest` apunta hoy a 1.14.0. Se fija la versión exacta para que la evaluación sea reproducible y se registra la que informa cada respuesta.
- Contexto por defecto: 64 mil tokens por solicitud y 32 mil por pregunta; sin límite de número de preguntas. El modo de contexto largo existe pero es más lento y menos preciso: no se usa.
- Costo: 0.042 USD por millón de tokens de entrada; la salida no se cobra.
- Límites de frecuencia: por organización, en la consola; no hay cifras públicas.
- Idiomas: la documentación no dice nada sobre español. Hay que comprobarlo con casos propios antes de adoptar cualquier variante.

## Puntos débiles que afectan a LiciGT

Según la [página de puntos débiles](https://docs.typesafe.ai/go/jaggedness.md):

- **Fechas y números:** JEV lee las fechas como texto; no compara ni calcula. En las fechas de la lista el código encuentra la candidata y las reglas la asignan a su actividad, sin JEV (F7b); el código la compara y valida (caso del evento 222).
- **Contenido adversario:** JEV no trata el estado como hostil. Un fragmento con instrucciones inyectadas puede influirle; la pregunta de "¿intenta dar instrucciones?" es una capa más, no la única defensa.
- **Contexto grande e irrelevante:** baja la precisión. Se envían solo los fragmentos y campos que la pregunta necesita.
- **Orden de opciones:** en `Choice` favorece la primera. En la evaluación se repite con el orden cambiado para medir ese sesgo.
- **Lectura literal:** la condición exacta va en la pregunta y los casos límite en los criterios.

## Resultados del sondeo (17 de noviembre)

Corrida real con `make sondeo-jev CONFIRMAR=1`, modelo `jev-1.14.0`, sobre las 47 preguntas de desarrollo. El registro está en `data/consulta/sondeos/20261117T163820833420Z.json`, ignorado por Git. Son preguntas de desarrollo: sirven para ajustar, no para medir. La comparación que cuenta es la de F7, con preguntas nuevas.

- **Funcionamiento:** las 47 respuestas válidas, sin degradación. Unos 870 tokens de entrada y 130 de salida por pregunta. El español funciona.
- **Coincidencia con las reglas:** 38 de 47 decisiones iguales. Las nueve diferencias:
  - **Seguro de caución (5 eventos):** las reglas eligen `buscar_documentos` y JEV `extraer_requisitos` (0.91). Las dos son defendibles; la etiqueta la fija el revisor en F7.
  - **Preguntas sin relación (petróleo, mundial):** las reglas buscan y JEV se abstiene antes de buscar, con `aplica` en 0.11 y 0.02. Es el comportamiento correcto, y lo decidió `aplica`, que es la pregunta que debe detectar ese caso. `fuera_de_alcance` dio 0.03 y 0.02, también correcto, porque por diseño solo cubre los temas prohibidos del anteproyecto (`Guia_de_etiquetado.md:39` y `:42`, [I6](investigacion/I6_jev_verificacion_y_sesgo.md)).
  - **"Dime la fecha y la hora":** las reglas piden aclaración y JEV se abstiene, porque `aplica` (0.13) se evalúa antes que `concreta` (0.07). Hay que revisar el orden de la tabla de decisión o los umbrales en la rejilla de F7.
  - **"¿Qué diferencia hay entre las versiones?":** las reglas comparan y JEV pide aclaración, con `concreta` en 0.24. Es defendible, porque no dice qué tema comparar.
- **Latencia:** el sondeo no la registra. La mide `experimento.py` en F7.

## Reescritura de las preguntas según I6 (versión 2026-11-17.1)

Resultado de la [I6](investigacion/I6_jev_verificacion_y_sesgo.md), aprobado por el usuario el 17 de noviembre. Las líneas de `.skills/typesafe-ai/SKILL.md` son las de esa versión de la skill. No se ha corrido contra JEV: `make sondeo-jev CONFIRMAR=1` comparará contra el sondeo del 17 de noviembre; el sondeo y el experimento registran `VERSION_PREGUNTAS`.

- **Estado con `contexto`** (`enrutador.py`, `CONTEXTO_JEV`): descripción fija y pública de LiciGT y de los documentos del evento, sin `tenant_id` ni datos de la empresa. Sale de `SKILL.md:92-98` (dar lo que una persona miraría y los hechos que el modelo no tiene). Es una hipótesis: `SKILL.md:99-101` avisa que un campo puede inclinar otra pregunta, y se mide en desarrollo.
- **`fuera_de_alcance`:** la instrucción pasa de una categoría ("tema prohibido") a lo observable ("pide algo más que informar"), `SKILL.md:119-120`. El criterio verdadero lista situaciones y no reglas, `SKILL.md:121-123`. Se quita del falso la frase sobre vigencia, que describía a `herramienta` (`SKILL.md:249-251`, cláusula por caso); se conserva "cómo se presenta una oferta", que es el caso concreto que confunde (`SKILL.md:141-144`). Sigue siendo una sola pregunta; dividirla por regla queda para F7.
- **`concreta`:** "Cada evento tiene un solo código de medicamento" sale del criterio y pasa al `contexto` (`SKILL.md:97-98`, hechos que el modelo no tiene). El falso tenía dos condiciones unidas por "o" y pasa a una situación con ejemplos (`SKILL.md:121-123`, `:163-164`).
- **`herramienta`:** los criterios son situaciones del analista, sin las salvedades "una fecha de recepción sin comparación pertenece aquí" y "sin decidir vigencia" (`SKILL.md:249-252`; la segunda es política del sistema, no criterio). `extraer_requisitos` pasa a describir una sola situación, "la lista de lo que el evento exige" (`SKILL.md:156-159`). El orden de opciones no cambia: elegir otro sería igual de arbitrario, y el sesgo de la primera opción lo mide F7 con el orden invertido y rotado (`SKILL.md:156`).
- **`aplica`:** la instrucción preguntaba "se puede buscar", que suena a `buscar_documentos`; ahora pregunta si trata sobre los documentos de una licitación, que es lo que debe preguntar el compañero del Choice (`SKILL.md:148-152`). Se quita la salvedad "no es necesario que el estado incluya la respuesta" (`SKILL.md:252`) y el falso es una situación general con ejemplos distintos de los casos probados (`SKILL.md:163-164`, `:251`).
- **Fechas, `ninguna` y `respaldo`:** el falso de `respaldo` tenía dos situaciones con "o"; ahora es una (el pasaje no dice a qué actividad corresponde), `SKILL.md:121-123`. `ninguna` se redactó como situación (`SKILL.md:163-164`). No se quitó de las opciones: `herramientas.py` y sus pruebas deciden `fuera_del_cronograma` con ella, y reemplazarla por un Noul compañero (`SKILL.md:148-152`) exige cambiar esa lógica, fuera de este encargo. Pendiente de decisión.
- **Umbrales:** se mantienen. `inyeccion` y `fuera_de_alcance` actúan con un sí claro (`>= noul_si`) y `concreta` pide aclaración con un no claro (`< noul_no`): las tres solo actúan con un veredicto claro. Entre 0.3 y 0.7 pasan, y esa franja no tiene fila propia hasta contar los casos en F7 (`SKILL.md:204-206`). Queda comentado en `enrutador.py`.
- **Rastro del cambio silencioso** (`decision.py`): cuando la probabilidad de la herramienta de JEV no llega a `choice_min` y se usa la de las reglas, `Siguiente.herramienta_jev_sustituida` guarda la que eligió JEV (`SKILL.md:255`). Falta que el orquestador la escriba en la auditoría.

## Segundo sondeo, con las preguntas reescritas (17 de noviembre)

Registro `data/consulta/sondeos/20261117T170536729838Z.json`, con las preguntas en la versión `2026-11-17.1` y `contexto` en el estado. Las decisiones coinciden con el primer sondeo en 46 de 47 casos, pero las probabilidades se movieron:

- "¿Qué fecha está vigente para la recepción?": `comparar_versiones` cae de 0.56 a 0.28 y la decisión pasa a `extraer_requisitos`. **Empeora**: es una pregunta de vigencia y debe contrastar los documentos.
- "Dime la fecha y la hora": `concreta` sube de 0.07 a 0.73. **Empeora**: sigue absteniéndose solo porque `aplica` da 0.08.
- Seguro de caución: `extraer_requisitos` baja de 0.89 a 0.61.
- "Precio del petróleo": `fuera_de_alcance` sube de 0.03 a 0.34, dentro de la franja sin decidir.

Hipótesis: el `contexto` ("cada evento tiene un solo medicamento, con su código") hace que una pregunta vaga parezca resoluble, y el criterio de `comparar_versiones` perdió la mención a las preguntas de vigencia. No se corrige caso por caso (SKILL.md:245-257). Siguiente paso: enviar la versión anterior y la nueva como preguntas separadas en la misma solicitud sobre las 47 de desarrollo (variantes de `experimento.py`), y quedarse con la que gane en conjunto.

## Pendientes

- [x] Cómo pasar la clave al cliente: parámetro `api_key`.
- [x] Límites, contexto y costo.
- [x] Puntos débiles documentados. La página no menciona texto en español, tablas ni citas.
- [ ] Comprobar el desempeño en español con casos propios del IGSS, con permiso y presupuesto.
- [ ] Definir el conjunto etiquetado del experimento (intención y suficiencia), separado del banco de 20 casos.
- [ ] Adaptar el diagrama `09-decision-layer-experiment` de la versión anterior (OneDrive, `tareas/proyecto/diagrams`) al IGSS.
