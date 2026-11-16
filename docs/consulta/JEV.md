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
| F3 | Fechas de `extraer_requisitos` | El código encuentra candidatas con expresiones regulares; JEV elige cuál corresponde a cada actividad del cronograma; el código normaliza y valida la fecha. | [Date extraction](https://docs.typesafe.ai/cookbooks/date_extraction_cookbook.md) |

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

- **Fechas y números:** JEV lee las fechas como texto; no compara ni calcula. Coincide con el plan: JEV elige la fecha candidata y el código la compara y valida (caso del evento 222).
- **Contenido adversario:** JEV no trata el estado como hostil. Un fragmento con instrucciones inyectadas puede influirle; la pregunta de "¿intenta dar instrucciones?" es una capa más, no la única defensa.
- **Contexto grande e irrelevante:** baja la precisión. Se envían solo los fragmentos y campos que la pregunta necesita.
- **Orden de opciones:** en `Choice` favorece la primera. En la evaluación se repite con el orden cambiado para medir ese sesgo.
- **Lectura literal:** la condición exacta va en la pregunta y los casos límite en los criterios.

## Pendientes

- [x] Cómo pasar la clave al cliente: parámetro `api_key`.
- [x] Límites, contexto y costo.
- [x] Puntos débiles documentados. La página no menciona texto en español, tablas ni citas.
- [ ] Comprobar el desempeño en español con casos propios del IGSS, con permiso y presupuesto.
- [ ] Definir el conjunto etiquetado del experimento (intención y suficiencia), separado del banco de 20 casos.
- [ ] Adaptar el diagrama `09-decision-layer-experiment` de la versión anterior (OneDrive, `tareas/proyecto/diagrams`) al IGSS.
