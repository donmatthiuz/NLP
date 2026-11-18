# Encargo C9: correcciones de la integración con el LLM real

Para el implementador. Rama `rol/consulta`. No commitees.

Lee primero:

- [`AGENTS.md`](../../../AGENTS.md);
- [C4](C4_datos_literales_F4.md) y [C7](C7_reglas_cerradas_F4.md);
- `src/licigt/consulta/validacion.py`, `generacion.py`, `orquestador.py`, `llm.py`, `config.py`, `herramientas.py` y `enrutador.py`, con sus pruebas;
- el diagnóstico en el scratchpad del gestor: `diag_resultados.json` y los scripts `diag_*.py`.

## Origen

Es la primera corrida con servicios reales: Qwen3.5-9B en llama-server, la base del rol 2 y el evento 222. Con 10 preguntas, solo 1 respondió (el código IGSS). Las causas son independientes, y el contenido que generó el modelo era correcto en todos los casos.

- **A.** El modelo escribe el dato en el texto en lugar de `{n}`, o llena `datos` cuando no hay cifra. Da `texto_invalido`.
- **B.** `max_tokens=1024` corta el JSON de las respuestas largas (`finish_reason="length"`). Da `json_invalido`.
- **D.** Las preguntas por una fecha van a `extraer_requisitos`, que no usa la pregunta del usuario. Recupera 27 fragmentos sin el dato y tarda 48 s.
- **La regeneración no sirve:** con temperatura 0 y la misma semilla el JSON sale idéntico, y el mensaje solo lista códigos genéricos.
- **`comparar_versiones` pasa la pregunta entera como tema.** El reranker la puntúa por debajo del umbral; con el tema corto sí es suficiente.

## Archivos

`validacion.py`, `generacion.py`, `orquestador.py`, `llm.py`, `config.py`, `herramientas.py` y `enrutador.py`, con sus pruebas. Nada del rol 2.

## Cambios (prueba en rojo primero, en cada uno)

### A. Marcadores puestos por el código, sin aflojar la regla

- **Sustitución antes de validar:** si el texto de la afirmación contiene **exactamente** el literal de un dato y el dato no tiene marcador, el código reemplaza esa aparición por `{n}`.
  - Se sustituye primero el literal más largo, una sola aparición por dato.
  - El literal debe estar con límites de palabra y de número en el texto, con la misma regla de `_continua`.
  - Después se valida con todas las reglas actuales, sin cambios.
- **Datos que sobran:** un dato que no aparece en el texto y no tiene marcador se descarta antes de validar, porque no se publica.
  - Lo descartado se registra en la auditoría como el número de datos descartados, sin texto.
- **Lo que no cambia:**
  - un dígito o un mes que queda en el texto sin coincidir exactamente con un literal sigue dando `dato_fuera_de_literal`;
  - la fecha "6 de octubre" escrita a mano frente al literal "06 de octubre de 2023" sigue rechazándose.
- **Prompt:**
  - añade un ejemplo de afirmación sin cifras con `datos: []`;
  - aclara que el texto puede llevar el dato copiado tal cual o el marcador;
  - sube `VERSION_PROMPT`.
- **Pruebas:** con los JSON crudos reales de `diag_resultados.json`, el lugar de entrega y la fecha por `buscar_documentos` publican; la caución publica o falla por otra regla, reportada tal cual. Siguen fallando todos los ataques de los scripts `c4_*` a `c7_*`, y `c5_falsos`, `c6_falsos` y `c7_falsos` siguen publicando.

### B. Longitud y regeneración

- `max_tokens` por defecto pasa a 3072, configurable.
- Si `finish_reason` es `length`, el error es `respuesta_cortada`, distinto de `json_invalido`.
- **Mensaje de regeneración:** el código de error más el desajuste concreto, sin texto del documento. Por ejemplo: "la afirmación 2 tiene 1 dato y 0 marcadores", o "la respuesta se cortó: usa como máximo 5 afirmaciones".
- **La regeneración cambia la semilla** (semilla + 1), para no repetir la misma salida.
- **Pruebas:**
  - con un doble que corta la primera respuesta, la regeneración pide menos afirmaciones;
  - con un doble que repite la salida, se comprueba que la segunda llamada usa otra semilla.

### D. La pregunta del usuario entra en `extraer_requisitos`

- `ExtraerRequisitosParams` gana `pregunta`, opcional, con el mismo recorte de `entrada`.
- Si viene, es la primera consulta, antes de las fijas por categoría y del cronograma.
- **Enrutador:** una pregunta sobre una sola fecha o un solo dato ("¿cuál es la fecha de...?") va a `buscar_documentos`; "requisitos", "lista" y "qué documentos" siguen yendo a `extraer_requisitos`. Ajusta los patrones de `EnrutadorReglas` con pruebas y deja intactos los casos que hoy pasan.
- **Pruebas:**
  - "¿Cuál es la fecha de recepción de ofertas?" va a `buscar_documentos`;
  - "¿Qué requisitos tiene la plica?" va a `extraer_requisitos` con la pregunta como primera consulta.

### E. Tema corto en `comparar_versiones`

- El tema que se pasa al rol 2 quita la parte de la orden de comparación: "compara / compare / diferencia entre ... las bases y la modificación / las versiones". Queda el núcleo, por ejemplo "fecha de recepción de ofertas".
- Es un recorte determinista, con una lista corta y probada.
- Si el tema queda vacío, se pide aclaración, como hoy.
- **Pruebas:** tres formulaciones de la demo.

## Verificación con servicios reales (obligatoria)

Los servicios ya están arriba: la base y `llama-server` en 127.0.0.1:8080.

- Vuelve a correr `diag_run.py` (o su equivalente) con el código nuevo y reporta la misma tabla de las 10 preguntas.
- Para Python con la base, usa el comando que arma el `Makefile`, sin leer la llave: `CMD=$(make -n api | sed ...)` y `eval`, como en los scripts de diagnóstico.

## Criterios de aceptación

- `make test-consulta` en verde.
- En la corrida real responden al menos el lugar de entrega, el código IGSS y la fecha de recepción. Las que dependen del umbral del rol 2 (NOG, inducción) quedan explicadas como tales.

## Al terminar

Responde con:

- los archivos tocados;
- los resultados;
- la tabla real antes y después;
- las decisiones donde el encargo no era claro.

No amplíes el alcance.
