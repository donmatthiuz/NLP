# Encargo F2: validación de entrada, ambigüedad, enrutador y JEV

Para Codex u OpenCode. Rama `rol/consulta`. Lee primero [`AGENTS.md`](../../../AGENTS.md), [`Contratos.md`](../Contratos.md), [`JEV.md`](../JEV.md) y la skill `.skills/typesafe-ai/SKILL.md`. Abre el agente con `make codex` o `make opencode` para tener Context7. El gestor auditará el resultado; no commitees.

**En paralelo** otro agente hace el encargo F3a en `lectura.py`, `herramientas.py` y sus pruebas, y otro hace diagramas en `docs/arquitectura/`, `scripts/` y `Makefile`. No toques esos archivos.

## Objetivo

La primera compuerta del flujo de consulta: decidir, antes de recuperar, si la pregunta se rechaza, se aclara o va a una de las tres herramientas. Dos variantes intercambiables, **reglas** (línea base) y **JEV** (API real), más el punto de conexión para un LLM que se elegirá después.

**Por qué:** las instrucciones del curso piden validación estructurada de entradas, mitigación de inyección, procedimiento ante preguntas fuera de dominio y un flujo de decisión con enrutamiento condicional (secciones 5.6 y 5.8), y casos de ambigüedad y de selección de herramienta en el banco (sección 8). Ver `Plan_rol_3.md`, F2.

## Principio de diseño

"JEV juzga, el código decide" (skill `typesafe-ai` y `DESIGN.md`). Las preguntas devuelven juicios; la decisión es una tabla de verdad en código, con un resultado para cada combinación. Las reglas producen los mismos juicios que JEV, así que la tabla es la misma para las dos variantes.

## Archivos

Solo dentro de `src/licigt/consulta/`:

| Archivo | Acción |
|---|---|
| `esquemas.py` | Modificar: aclaración en la respuesta (ver abajo) |
| `config.py` | Crear: lectura del entorno |
| `entrada.py` | Crear: juicios de entrada por reglas |
| `enrutador.py` | Crear: interfaz, variante de reglas, variante JEV, variante LLM sin cliente |
| `preguntas_jev.py` | Crear: toda la redacción de preguntas, opciones, criterios y umbrales de JEV, en un solo lugar |
| `jev.py` | Crear: cliente de JEV, limitador de frecuencia y errores |
| `presupuesto.py` | Crear: límite de 3 llamadas y 1 regeneración por solicitud |
| `decision.py` | Crear: tabla de decisión |
| `sondeo_jev.py` | Crear: prueba manual contra la API real |
| `requirements.txt` | Añadir `typesafe-sdk` |
| `tests/test_*.py` | Pruebas nuevas, y ampliar `test_esquemas.py` |

Prohibido tocar: `lectura.py`, `herramientas.py`, `tests/test_lectura.py`, `tests/test_herramientas.py`, `README.md`, `__init__.py`, `Makefile`, `scripts/` y cualquier archivo fuera de `src/licigt/consulta/`.

## 1. Aclaración en el contrato (`esquemas.py`)

Pedir aclaración es una tercera salida, distinta de abstenerse (decisión del 16 de noviembre; ver `Contratos.md`).

- `RespuestaEstructurada` gana `needs_clarification: StrictBool = False` y `clarification_question: TextoNoVacio | None = None`.
- Reglas del validador:
  - Si `needs_clarification`: `abstained` es falso, `clarification_question` existe, `answer` es igual a `clarification_question`, `tool_used` es nulo y `sources` puede estar vacía.
  - Si no hay aclaración, `clarification_question` es nulo.
  - La regla actual "sin abstención requiere al menos una fuente" pasa a ser "sin abstención y sin aclaración".
- Constantes junto a `TEXTO_ABSTENCION`:
  - `TEXTO_ACLARACION_FECHA = "¿A qué fecha o plazo se refiere? Por ejemplo: recepción de ofertas, apertura de plicas o adjudicación."`
  - `TEXTO_ACLARACION = "¿Puede indicar a qué actividad o documento del evento se refiere?"`
- No rompas las 22 pruebas existentes; añade las nuevas.

## 2. Juicios de entrada por reglas (`entrada.py`)

Devuelve un modelo inmutable `JuiciosEntrada` con:

- `longitud_valida: bool`: reutiliza `TextoRecortado` de `esquemas.py` con un `TypeAdapter`; no dupliques el 500.
- `inyeccion: bool`: patrones en español e inglés de intento de cambiar instrucciones o extraer el prompt ("ignora tus instrucciones", "olvida lo anterior", "revela tu prompt", "actúa como", "eres ahora", "ignore previous instructions", "system prompt", etc.). Es una señal auxiliar, no la única defensa: las pruebas no afirman que bloquea todo.
- `fuera_de_alcance: bool`: **lista de temas prohibidos**, no de palabras permitidas. Solo lo que el anteproyecto declara fuera de alcance:
  - presentar, enviar o subir ofertas o trámites;
  - navegar a sitios o enlaces externos;
  - modificar, editar o borrar documentos;
  - certificar cumplimiento o decidir si la empresa debe participar;
  - recomendaciones clínicas (dosis para pacientes, tratamientos, diagnósticos, equivalencias terapéuticas).
  
  Preguntar qué fecha o cláusula "está vigente" **no** es fuera de alcance: va a `comparar_versiones` y termina en revisión humana.
- `especifica: bool`: falso cuando la pregunta pide "la fecha", "el plazo" o "la hora" sin nombrar una actividad (recepción, apertura, adjudicación, presentación, entrega, aclaraciones, consultas, publicación, firma, pago, inicio, garantía, vigencia del contrato…). No uses "el medicamento": cada evento del corpus tiene un solo código (`docs/ingesta/Corpus_IGSS.md`), así que no es ambiguo.

Las listas de patrones van como constantes al inicio del archivo.

## 3. Enrutador (`enrutador.py`)

- `Clasificacion` (inmutable):
  - `herramienta: NombreHerramienta | None`;
  - `variante: Literal["reglas", "jev", "llm"]`;
  - `degradado: bool`: verdadero si se pidió JEV o LLM y se usaron las reglas por falla;
  - `prob_herramienta: float | None` y `prob_aplica: float | None`: solo JEV;
  - `modelo: str | None`: versión de JEV que respondió.
- `Enrutador` es un `Protocol` con `clasificar(pregunta: str) -> tuple[JuiciosEntrada, Clasificacion]`.
- **`EnrutadorReglas`**, por prioridad:
  1. `comparar_versiones`: cambió, cambio, modific-, diferencia, versión, antes y después, vigente.
  2. `extraer_requisitos`: requisito, documentos que se deben presentar, lista, fecha, plazo, hora, cronograma, cuándo. Las fechas van aquí, no a buscar (`Anteproyecto.md`, sección 11).
  3. `buscar_documentos` en cualquier otro caso.
- **`EnrutadorJev`**: una sola solicitud a JEV con todas las preguntas (patrón de abanico especulativo de la skill), cuyo estado es solo `{"pregunta": texto}`:
  - `Noul` de inyección;
  - `Noul` de tema prohibido;
  - `Noul` de pregunta concreta;
  - `Choice` de herramienta;
  - `Noul` compañero: ¿la pregunta se responde con los documentos de una licitación?
  
  La longitud siempre la validan las reglas. Si JEV falla, usa `EnrutadorReglas` y marca `degradado=True`.
- **`EnrutadorLlm`**: recibe un `ClienteLlm` (un `Protocol` con un método que devuelve un dict validado). No hay cliente real todavía: el LLM se elegirá después. Solo debe funcionar con un doble en pruebas. Si no se inyecta cliente, degrada a reglas.
- Selección por `LICIGT_ENRUTADOR` (`reglas` por defecto, `jev` o `llm`), leída en `config.py`.

## 4. Preguntas de JEV (`preguntas_jev.py`)

Un solo lugar para auditar y editar redacción, opciones, criterios y umbrales, como pide la skill:

- Redacción en español, una sola idea por pregunta, opciones con nombres descriptivos, criterios del `false` como situación concreta, y el caso límite nombrado en los criterios.
- Opciones del `Choice`:
  - `buscar_documentos`: consultar un dato o pasaje concreto de los documentos;
  - `extraer_requisitos`: listar requisitos, documentos a presentar o fechas del cronograma;
  - `comparar_versiones`: saber qué cambió entre las bases y una modificación o aclaración.
- Umbrales: `NOUL_SI = 0.7`, `NOUL_NO = 0.3` y `CHOICE_MIN = 0.5`. Son valores iniciales (`JEV.md`); se calibran después con datos que no se usaron para ajustar.
- Antes de escribirlas, lee en la documentación viva las páginas de `Choice` y `Noul` y la de puntos débiles (enlaces en la skill y en `JEV.md`).

## 5. Tabla de decisión (`decision.py`)

`decidir(juicios, clasificacion) -> Siguiente`, donde `Siguiente` (inmutable) tiene:

- `accion: Literal["abstener", "aclarar", "usar_herramienta"]`;
- `motivo: Literal["longitud_invalida", "inyeccion", "fuera_de_alcance", "sin_herramienta", "no_especifica", "ok"]`;
- `herramienta: NombreHerramienta | None`;
- `pregunta_aclaratoria: str | None`.

| Orden | Condición | Salida |
|---|---|---|
| 1 | Longitud inválida | abstener, `longitud_invalida` |
| 2 | Inyección (reglas sí, o `Noul` ≥ 0.7) | abstener, `inyeccion` |
| 3 | Tema prohibido (reglas sí, o `Noul` ≥ 0.7) | abstener, `fuera_de_alcance` |
| 4 | Con JEV, `Noul` compañero < 0.3 | abstener, `sin_herramienta` |
| 5 | Sin herramienta (`None`) | abstener, `sin_herramienta` |
| 6 | No específica (reglas no, o `Noul` de concreta < 0.3) | aclarar con `TEXTO_ACLARACION_FECHA` si menciona fecha, plazo u hora; si no, `TEXTO_ACLARACION` |
| 7 | Con JEV y probabilidad de la herramienta < 0.5 | usar la herramienta que eligen las reglas |
| 8 | En otro caso | usar_herramienta, `ok` |

- Franjas intermedias (de 0.3 a 0.7): no bloquean ni aclaran; siguen a la fila siguiente. Lo que no está claro lo resuelve después la suficiencia de la recuperación.
- Cada fila tiene al menos una prueba.

## 6. Cliente de JEV (`jev.py`) y configuración (`config.py`)

- `ClienteJev` es un `Protocol` con `preguntar(estado, preguntas) -> RespuestaJev` (respuestas, versión del modelo, `request_id` y uso de tokens).
- `ClienteJevSdk`:
  - importa `typesafe_sdk` dentro del constructor, no a nivel de módulo, para que las pruebas corran sin el SDK;
  - lee la clave del archivo de `LICIGT_JEV_API_KEY_FILE` y la pasa como `api_key`; nunca la imprime ni la registra;
  - fija el modelo con `LICIGT_JEV_MODELO`, por defecto la versión exacta vigente. Verifica el nombre exacto en la [especificación OpenAPI](https://api.typesafe.ai/openapi.json) o en la documentación del SDK; no uses `jev-latest`;
  - usa un `RetryPolicy` explícito (por ejemplo 2 reintentos y 5 segundos), con valores en `config.py`.
- Errores: `TypeSafeAPIError`, `TypeSafeError`, tiempo agotado o respuesta incompleta se convierten en `FallaJev(codigo)`, sin el texto de la pregunta. Nunca se interpretan como respuesta.
- **Límites simulados:** los límites reales de frecuencia están en la consola de TypeSafe y no son públicos.
  - `LimitadorFrecuencia` de cubeta de fichas, con reloj inyectable para las pruebas, configurable con `LICIGT_JEV_MAX_SOLICITUDES_SEG` (por defecto 5).
  - Si no hay ficha, espera hasta un máximo configurable y después lanza `FallaJev("limite_frecuencia")`.
  - Queda listo para poner los valores reales cuando se conozcan.
- `config.py` lee el entorno una vez, con valores por defecto y validación: enrutador, modelo, archivo de clave, reintentos, tiempo de espera y frecuencia.

## 7. Presupuesto por solicitud (`presupuesto.py`)

- `Presupuesto(max_llamadas=3, max_regeneraciones=1)` con `usar_llamada()` y `usar_regeneracion()`, que lanzan `LimiteAgotado(tipo)` al pasarse.
- Hoy no hay herramientas ni generación reales: se prueba solo. F3 y F4 lo usarán. Es la "simulación" del límite, lista para conectarse.

## 8. Sondeo manual contra la API real (`sondeo_jev.py`)

El usuario aprobó el uso de su clave y presupuesto. Aun así, el envío exige un paso explícito:

- `PYTHONPATH=src python -m licigt.consulta.sondeo_jev --confirmar-envio` (requiere `typesafe-sdk` instalado). Sin el flag, solo imprime qué se enviaría.
- Casos fijos:
  - las 27 preguntas de `src/licigt/recuperacion/casos_desarrollo.json`;
  - al menos 5 ataques de inyección (español e inglés);
  - 5 temas prohibidos;
  - 5 preguntas ambiguas;
  - 5 preguntas de comparación.
- Solo se envía el texto de la pregunta: nada de PDF, `tenant_id` ni usuarios.
- Imprime una tabla con la decisión de reglas frente a JEV por caso, el modelo que respondió y los tokens usados. Guarda los payloads exactos y las respuestas en `data/consulta/sondeos/<fecha>.json`; `data/` ya está ignorado por Git.

## Pruebas (escribirlas primero, sin red ni SDK)

- Las 27 preguntas reales de `casos_desarrollo.json` pasan la entrada sin abstención ni aclaración por reglas. Las dos sin evidencia también pasan aquí: las frena después la recuperación.
- "¿Cuál es la fecha y hora de recepción de ofertas?" va a `extraer_requisitos`; "¿Qué cambió en el cronograma con la modificación 1?", a `comparar_versiones`; "¿Qué documentos debe contener la plica?", a `extraer_requisitos`; una pregunta de dato puntual, a `buscar_documentos`.
- "¿Cuál es la fecha?" pide aclaración con `TEXTO_ACLARACION_FECHA`.
- Ataques de inyección y temas prohibidos se abstienen; "¿qué fecha está vigente para la recepción?" no se abstiene.
- Cada fila de la tabla de decisión, incluidas las franjas intermedias, con un `ClienteJev` falso.
- Una falla de JEV degrada a reglas con `degradado=True`.
- El limitador con reloj falso: permite N por segundo, espera y falla al exceder.
- `Presupuesto`: la cuarta llamada y la segunda regeneración lanzan `LimiteAgotado`.
- `esquemas.py`: las nuevas reglas de aclaración.
- Ningún módulo importa `licigt.recuperacion` ni `typesafe_sdk` al importarse. Pruébalo revisando `sys.modules`.

## Criterios de aceptación

- `make test-consulta` en verde, sin red, sin SDK y sin Postgres.
- Todo el texto de las preguntas a JEV y sus umbrales viven solo en `preguntas_jev.py`; las listas de reglas, solo en `entrada.py` y `enrutador.py`.
- Nombres en español, salvo los campos del contrato del curso.

## Al terminar

Responde con:

- los archivos creados o modificados;
- la salida literal de `make test-consulta`;
- el nombre exacto del modelo fijado y de dónde lo sacaste;
- las decisiones que tomaste donde el encargo no era claro.

No ejecutes el sondeo con `--confirmar-envio`; lo corre el usuario.
