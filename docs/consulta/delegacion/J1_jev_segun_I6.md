# Encargo J1: JEV según la investigación I6

Para el implementador. Rama `rol/consulta`. No commitees.

Lee primero:

- [`AGENTS.md`](../../../AGENTS.md);
- la skill `typesafe-ai` (`.skills/typesafe-ai/SKILL.md`);
- [`JEV.md`](../JEV.md);
- [I6](../investigacion/I6_jev_verificacion_y_sesgo.md), completa;
- la parte que te toque, con sus pruebas.

## Decisiones del usuario (17 de noviembre)

El usuario aprobó las recomendaciones D1 a D7 de I6:

- reescribir las preguntas según la skill antes de congelar la prueba, ajustando solo con las 47 preguntas de desarrollo;
- probar un campo `contexto` en el estado, sin reordenar `decision.py`;
- contar en F7 cuántos casos caen en la franja de 0.3 a 0.7 antes de darle su propia fila;
- medir sesgo, consistencia y calibración en la misma corrida de prueba de F7;
- citation check como aviso que escala a `needs_human_review`, que se adopta solo si un conjunto etiquetado lo respalda;
- en las cifras escritas con letras, JEV solo detecta la cifra.

## Partes (en paralelo, sin compartir archivos)

### Parte A: preguntas y estado del enrutador

- **Archivos:**
  - `preguntas_jev.py` y `enrutador.py`;
  - `decision.py`, solo para dejar rastro del cambio silencioso a la herramienta de las reglas (I6, punto 7);
  - sus pruebas.
- **Preguntas:** reescribir las de `preguntas_jev.py` corrigiendo cada desviación que señala I6 (pregunta 3), con nombre de opción, línea y regla de la skill:
  - criterios escritos como situaciones concretas, sin salvedades por caso ni listas de reglas;
  - la opción `ninguna` reemplazada por un Noul que la acompaña;
  - la mezcla de situaciones de `:49` separada;
  - la instrucción de `aplica` corregida.
- **Estado:** añadir `contexto` al estado de JEV. Debe ser una descripción fija y pública del sistema y del evento (qué es LiciGT y qué documentos contiene el evento), sin `tenant_id` ni datos de la empresa.
- **Comparaciones de umbral:** `concreta` usa `>=` sobre `noul_no`, mientras inyección y fuera de alcance usan `>=` sobre `noul_si`. Alinearlas o justificar la diferencia en un comentario.
- **Versión de las preguntas:** cada cambio sube la versión (constante `VERSION_PREGUNTAS`) para que el sondeo y el experimento la registren.
- **Sin red:** no se llama a JEV. Las pruebas con dobles deben seguir pasando y comprobar el nuevo estado.
- **Al final:** escribe en `docs/consulta/JEV.md` una sección corta con lo que cambió y por qué, citando la línea de la skill de la que sale cada cambio. El usuario correrá `make sondeo-jev CONFIRMAR=1` para comparar contra el sondeo del 17 de noviembre.

### Parte B: sesgo, consistencia y calibración en F7

- **Archivos:** `experimento.py` y `tests/test_experimento.py`.
- **Variantes en la misma solicitud de la corrida de prueba:**
  - el orden de las opciones del Choice (original, invertido y rotado);
  - 2 o 3 redacciones equivalentes, congeladas antes de la corrida en un archivo versionado;
  - una repetición idéntica.
- **Métricas:**
  - el cambio de opción por variante;
  - la discrepancia |p1 - p2|;
  - la calibración por franjas, con Brier e intervalos de Wilson;
  - el número de casos en la franja de 0.3 a 0.7.
- **Orden de las opciones:** comprueba en el OpenAPI o en la documentación de TypeSafe si la API respeta el orden de las claves de `criteria`. Si no se puede verificar, déjalo anotado en un comentario y en el informe.
- **Sin red;** las pruebas usan respuestas grabadas.

### Parte C: citation check posterior al validador

- **Archivos:**
  - `citas_jev.py` (nuevo) y `tests/test_citas_jev.py`;
  - en `orquestador.py`, solo la llamada después de `validar` y la suma del aviso.
- **Diseño:** el del cookbook (I6, pregunta 2):
  - un Choice con `supports`, `contradicts` y `says_nothing` sobre `{claim, section}` por cada afirmación publicada;
  - `AUTO_ACCEPT` de 0.8;
  - todo lo que no se acepte agrega el aviso `cita_sin_respaldo_jev: <n>` y pone `needs_human_review = true`;
  - nunca cambia el texto, no regenera ni bloquea la respuesta.
- **Interruptor:** `LICIGT_CITAS_JEV=0|1`, apagado por defecto mientras no se mida. Con JEV caído, se agrega el aviso `citas_jev_no_disponible` y no se escala.
- **Qué sale hacia JEV:** solo la afirmación armada y el texto de la sección pública citada; nunca `tenant_id`, el usuario ni la pregunta. Una prueba lo comprueba sobre el payload.
- **Auditoría:** registra el modelo y los códigos de la verificación, sin texto.
- **Conjunto de medición:** en `src/licigt/consulta/casos_citas.json`, el formato para afirmaciones fieles e infieles etiquetadas, más 6 ejemplos sacados del 222 (3 fieles y 3 infieles). El adversario redacta el resto en F7.

## Criterios de aceptación

- `make test-consulta` en verde, sin red.
- Ninguna parte llama a JEV ni lee `keys/`.

## Al terminar

Responde con:

- los archivos tocados;
- los resultados;
- en la parte A, la lista de cambios a las preguntas con la línea de la skill que los respalda;
- las decisiones donde el encargo no era claro.

No amplíes el alcance.
