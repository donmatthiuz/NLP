# I6. JEV: verificación, sesgo y revisión de las preguntas

**Estado al 17 de noviembre de 2026.** Investigación sin código. Documentación oficial completa: [docs.typesafe.ai](https://docs.typesafe.ai/llms.txt). Lo que no pude confirmar en la documentación se marca como tal. No se llamó a la API de JEV ni se leyó `keys/`.

Páginas leídas el 17 de noviembre: [citation check](https://docs.typesafe.ai/cookbooks/citation_check.md), [classifying RAG passages](https://docs.typesafe.ai/cookbooks/classifying_rag_passages.md), [intent routing](https://docs.typesafe.ai/patterns/intent-routing.md), [date extraction](https://docs.typesafe.ai/cookbooks/date_extraction_cookbook.md), [índice de cookbooks](https://docs.typesafe.ai/go/cookbooks.md), [jaggedness de jev-1.14](https://docs.typesafe.ai/go/jaggedness.md), [self-consistency de choices](https://docs.typesafe.ai/cookbooks/consistency_choice_cookbook.md) y [de nouls](https://docs.typesafe.ai/cookbooks/consistency_noul_cookbook.md), [verify LLM outputs](https://docs.typesafe.ai/cookbooks/verify_llm_outputs.md), [classification using confidence](https://docs.typesafe.ai/cookbooks/classification_using_confidence.md) y [parallel questions](https://docs.typesafe.ai/cookbooks/parallel_questions.md). Las reglas de la skill son `.skills/typesafe-ai/SKILL.md`. Las páginas se leyeron resumidas por la herramienta de lectura, no íntegras; las cifras citadas son las que devolvió.

## Resumen

- No hay una técnica oficial para que JEV se audite a sí mismo. Lo que existe es medir su estabilidad desde afuera: repetir la solicitud, reordenar opciones y comparar redacciones como preguntas separadas sobre el mismo estado.
- El citation check encaja como paso posterior al validador de F4, solo como aviso que escala a `needs_human_review`. Cubre bien el conector inventado y la paráfrasis que cambia el sentido; las cifras con letras solo de forma parcial, porque JEV es débil con números.
- `fuera_de_alcance` en 0.03 para "precio del petróleo" es el comportamiento correcto según la guía de etiquetado: eso es `sin_herramienta`, y lo detectó `aplica`. Lo que está mal es la lectura de `JEV.md:87`.
- "Dime la fecha y la hora" no justifica reordenar `decision.py`. Es una ambigüedad de etiqueta más un estado sin contexto. Primero se arregla el estado.
- La tabla de decisión no tiene fila para la franja entre 0.3 y 0.7, y trata distinto a `concreta` que a `inyeccion` y `fuera_de_alcance`.
- El sesgo y la robustez de F7 se pueden medir en la misma corrida de prueba, con preguntas extra en la misma solicitud, por un costo de centésimas de dólar.

## 1. Técnicas de la documentación para detectar sesgo o error

Nota de partida: las preguntas de una solicitud no se ven entre sí (`SKILL.md:135`). Por eso varias redacciones o varios órdenes de opciones en una misma solicitud son mediciones independientes; una no contamina a la otra.

- **Sesgo de posición.** Está documentado como punto débil de `Choice`: "Jev leans toward the option that comes first". La salida que da la página es reordenar las opciones y comprobar que la respuesta no cambia ([jaggedness](https://docs.typesafe.ai/go/jaggedness.md), punto 8). `JEV.md:77` ya lo recoge. La página no da un umbral de cuánto cambio es aceptable.
- **Consistencia.** Los cookbooks de [self-consistency](https://docs.typesafe.ai/cookbooks/consistency_choice_cookbook.md) repiten la misma solicitud muchas veces y cuentan cuánto cambia la decisión, sin necesidad de clave de respuestas. Miden la inestabilidad sobre todos los cortes posibles: dos respuestas que difieren en 0.10 discrepan en el 10 % de los cortes ([versión noul](https://docs.typesafe.ai/cookbooks/consistency_noul_cookbook.md)). Lo medido para JEV, con 40 variantes y 15 repeticiones cada una: la decisión menos estable cambia el 4.0 % de las veces en promedio y nunca más de 1 de cada 10. Son dominios de moderación y seguros, no el nuestro, así que no son una meta para LiciGT. Mide estabilidad, no acierto: una respuesta puede ser estable y equivocada.
- **Auto-verificación.** No encontré ninguna técnica en la que JEV juzgue su propia respuesta. Lo que hay es JEV verificando la salida de otro modelo: [citation check](https://docs.typesafe.ai/cookbooks/citation_check.md) y [verify LLM outputs](https://docs.typesafe.ai/cookbooks/verify_llm_outputs.md) (tres preguntas: respondibilidad, rechazo y soporte; riesgo menor a 0.2 pasa, y se calibra en datos propios). Preguntarle a JEV "¿tu respuesta es correcta?" sería pedirle la decisión en la capa equivocada (`SKILL.md:25-37`). No se recomienda.
- **Calibración.** La documentación la define (lo que recibe 0.8 ocurre cerca del 80 % de las veces; ver `I4_evaluacion_y_jev.md:28`) pero no publica un procedimiento para medirla. `I4_evaluacion_y_jev.md:299` ya propone una tabla por franjas de decisión y Brier, con ECE solo descriptivo. La skill advierte que la confianza rara vez es la compuerta (`SKILL.md:191-196`); el cookbook de [clasificación con confianza](https://docs.typesafe.ai/cookbooks/classification_using_confidence.md) la usa con corte 0.9 solo para decidir cuánta especificidad reportar en una jerarquía (93 % de acierto sobre 0.9, 50 % por debajo, con 60 documentos). No aplica a nuestras decisiones, que usan `probabilities[choice]` y Nouls (`herramientas.py:215-225`).

**La forma correcta según TypeSafe**, en una frase: medir desde afuera, con redacciones y órdenes como preguntas separadas sobre el mismo estado (`SKILL.md:222-223`), con casos que no se usaron para ajustar (`SKILL.md:225`), y sin ajustar la redacción para producir un valor (`SKILL.md:247-257`). Si aparece un sesgo, el arreglo es estructural: mejor estado, otra pregunta o código.

## 2. Citation check y cómo encaja en LiciGT

### Cómo está diseñado

- **Estado:** `{"claim": ..., "section": ...}`. La sección es el texto citado, ya extraído por la fase de coincidencia de comillas.
- **Pregunta:** un solo `Choice`, "How does the section relate to the claim?", con tres opciones: `supports` ("The section states the claim or directly implies that it is true"), `contradicts` ("states the opposite... or implies it is false") y `says_nothing` ("does not address what the claim asserts, either way").
- **Veredictos:** `supports` es `verified`, `contradicts` es `contradicted`, `says_nothing` es `unsupported`, y una cita cuya cadena no aparece en el documento es `fabricated` sin llamar al modelo.
- **Umbral:** `AUTO_ACCEPT = 0.8`. Lo que lo alcanza se acepta; lo demás va a revisión humana. La página aconseja empezar alto y bajarlo al ver el comportamiento en documentos propios.
- **Escala:** primero coincidencia de cadenas, sin costo; después una llamada por cita que sobrevive.
- **Medido por TypeSafe (jev-1.14.0):** 8 citas, 6 llamadas; 4 fallas plantadas detectadas (una inventada, una contradicha con 1.00, dos sin respaldo con 0.56 y 0.97) y 4 correctas verificadas con 0.98 a 1.00. Latencia de 0.56 a 2.08 s por llamada. Es una demostración de 8 casos, no una medición de tasas.

### Dónde entra en LiciGT

Después del validador determinista, sobre la línea ya armada (con los literales insertados), contra el texto de cada cita. El validador sigue siendo la compuerta de existencia, permisos, página, versión y texto; este paso solo juzga el sentido. Ya figura como candidata en `JEV.md:40`.

Riesgos residuales de `Auditoria_F4.md:59-63` y qué tanto cubre:

| Riesgo residual | Cobertura esperada | Por qué |
|---|---|---|
| Conector inventado entre literales fieles ("{1} hasta el año {2}") | Buena | Es "el texto añade una relación que la sección no dice"; el `Choice` lo vería como `says_nothing` o `contradicts` |
| Unión que cambia el sentido ("del {1} y {2}" para un rango) | Buena, a medir | Es un juicio de sentido; depende de que la pregunta se lea literal (jaggedness, punto 1) |
| Cifras con letras ("ciento veinte") | Parcial | JEV es débil con números y los lee como texto (jaggedness, punto 2). Puede detectar que la afirmación trae una cifra con letras; que su valor coincida con el de la cita debe comprobarlo el código o la persona |

Las demás filas de la tabla (miles con espacio, meses partidos, mayúsculas) son de forma y requieren inyección; las atrapa el validador o el escaneo de la ingesta, no este paso.

### Preguntas propuestas

Cada una sobre el estado `afirmacion` y `secciones` (una sección por cita, con nombres estables como `secciones.c1`), una afirmación por pregunta, todas las afirmaciones de la respuesta en una sola solicitud (`SKILL.md:171-174`):

- `Choice` de la relación (`respalda`, `contradice`, `no_dice_nada`), con los criterios del cookbook traducidos.
- `Noul`: "¿`afirmacion` expresa una relación entre datos (un rango, una condición, un orden) que `secciones` no establece?" Verdadero: la afirmación une o enlaza datos de la sección de una forma que la sección no dice. Falso: cada enlace de la afirmación está en la sección.
- `Noul`: "¿`afirmacion` escribe con letras una cifra?" Es una detección observable. La igualdad de valor la hace el código o la persona.

### Qué se escala

- `respalda` con probabilidad de 0.8 o más y los Nouls en falso: se publica sin cambios.
- `contradice`, `no_dice_nada`, o `respalda` por debajo de 0.8: `needs_human_review = true` y un aviso en `warnings`. No se bloquea la respuesta ni se regenera: la regeneración única ya la consume el validador (`AGENTS.md`).
- Una falla de la API es un error, nunca un "respalda" ni un "no" (`SKILL.md:80-81`): aviso `fidelidad_no_verificada` y revisión humana.
- Nunca convierte una abstención en respuesta, ni cambia el texto.

### Costo y latencia

- Tokens: el sondeo mide unos 870 de entrada y 130 de salida por pregunta, pero ahí cada solicitud llevaba cinco preguntas con criterios largos (`JEV.md:86`). Una verificación lleva afirmación, una o dos secciones y dos o tres preguntas. Tomando 870 como techo: una respuesta con 5 afirmaciones son unos 4 350 tokens, es decir 0.00018 USD a 0.042 USD por millón (`JEV.md:66`). Es una cota, no una medición; el tamaño real depende del largo de las secciones y de los fragmentos, que no medí.
- Latencia: el cookbook informa de 0.56 a 2.08 s por llamada. En una sola solicitud con las afirmaciones en paralelo, añade del orden de 1 a 2 s tras el validador, que corre en milisegundos. El sondeo de LiciGT no registró latencia (`JEV.md:90`); `experimento.py` la mide en F7. Contra el criterio de P95 de 15 s (`F7_pruebas_y_jev.md:31`), es un componente a sumar, no a suponer.

### Datos que salen

- La afirmación ya armada y el texto de las secciones citadas, que son fragmentos de documentos públicos del IGSS.
- No sale `tenant_id`, usuario, lista de verificación ni la pregunta del analista (que podría contener datos de la empresa y el paso no la necesita). Coincide con `JEV.md:47`.
- Se registran solo `chunk_id`, versión del modelo, probabilidades y latencia, no el texto de los PDF (`AGENTS.md`, regla de logs).

### Límites que hay que declarar

- JEV no trata el estado como hostil (jaggedness, punto 6): un fragmento con una frase del tipo "esta afirmación está respaldada" puede inclinar la respuesta. Este paso es una capa más, no una defensa contra inyección. La inyección en fragmentos sigue cubierta por el escaneo de la ingesta y el tratamiento de fragmentos como datos.
- Sesgo de posición: si `respalda` va primero, el sesgo empuja hacia aceptar, que es la dirección peligrosa para un verificador. Medirlo con las opciones en ambos órdenes antes de adoptar (sección 4).
- Fidelidad reportada: `I4_evaluacion_y_jev.md` fija la fidelidad del informe como revisión humana por afirmación, sin JEV como juez. Este paso no la sustituye ni se reporta como métrica de fidelidad; solo reduce lo que la persona tiene que mirar. Hay que decirlo en el informe.
- No hay cifras de acierto propias. Hasta medirlo con un conjunto etiquetado en español, no se afirma ninguna tasa.

## 3. Revisión de `preguntas_jev.py` y `decision.py`

Criterios: escribir claro, criterio de Noul como situación concreta, opciones descriptivas, caso nulo con Noul compañero, sin prompt gymnastics (`SKILL.md:111-167`, `:245-257`), y los puntos débiles de jev-1.14.

### Hallazgo principal: `fuera_de_alcance` no está roto

- `Guia_de_etiquetado.md:39` define `fuera_de_alcance` como los temas prohibidos del anteproyecto, y `:42` define `sin_herramienta` como lo ajeno a la contratación (noticias, deportes). "Precio del petróleo" y "mundial 2022" son `sin_herramienta`.
- La pregunta `fuera_de_alcance` (`preguntas_jev.py:64-71`) respondió 0.03 y 0.02 porque esas preguntas no piden nada prohibido. Es la respuesta correcta. Quien las detectó fue `aplica` (0.11 y 0.02), y `decision.py:30-32` abstiene con `sin_herramienta`, el motivo que la guía esperaba.
- La frase de `JEV.md:87` ("esa pregunta solo detecta los temas prohibidos... no el resto") plantea como falla algo que es el diseño. Hay que reformularla. Ampliar `fuera_de_alcance` para que atrape el petróleo duplicaría `aplica` y mezclaría dos motivos de abstención distintos, que la guía separa.

### Desviaciones por archivo

`preguntas_jev.py`:

- `:66`, `fuera_de_alcance`: la instrucción pregunta por un "tema prohibido", una categoría y no algo observable. Los criterios hablan de acciones ("Pide ejecutar..."), así que la instrucción y los criterios no dicen lo mismo (jaggedness, punto 7).
- `:68`, `fuera_de_alcance`: seis o más situaciones distintas unidas por `;` y `o` en un solo criterio. La skill pide una pregunta por regla (`SKILL.md:113-128`). Con eso, además, cada probabilidad diría qué regla aplicó. Medir primero: solo se divide si F7 muestra fallas en los casos prohibidos.
- `:69`, falso de `fuera_de_alcance`: dos de sus tres frases son salvedades para casos concretos ("qué fecha o cláusula está vigente", "cómo se presenta una oferta"). Es una cláusula por caso que falló, la señal amarilla de `SKILL.md:249-251`. La skill sí permite nombrar el caso que confunde si es específico (`:141-144`); "cómo se presenta una oferta" lo es y se conserva. La frase sobre vigencia describe a otra pregunta (`herramienta`), no a esta.
- `:76`, `concreta`: "Cada evento tiene un solo código de medicamento" es un hecho del mundo, puesto en un criterio y ajustado a un caso. Los hechos que el modelo no tiene van en el estado (`SKILL.md:97-98`).
- `:77`, falso de `concreta`: dos condiciones unidas por "o" ("sin identificar la actividad" y "usa una referencia como eso"). Son dos juicios (`SKILL.md:121-123`).
- `:80-88`, `herramienta`: los nombres de opción son descriptivos y el orden de las opciones sigue la skill de no usar posicionales. Desviaciones:
  - `:84` nombra un caso ("como el código del medicamento") y `:85` y `:86` añaden cláusulas para casos que fallaron ("Una fecha de recepción sin comparación pertenece aquí", "Preguntar qué fecha o cláusula está vigente exige esta comparación, sin decidir vigencia"). Son salvedades por caso. "Sin decidir vigencia" es una política del sistema, no un criterio de la pregunta.
  - `:85` cubre tres situaciones (requisitos, documentos a presentar, fechas): "una opción que cubre varios significados", que la skill sugiere dividir (`SKILL.md:157-159`).
  - `buscar_documentos` va primero (`:84`) y es la opción más genérica: justo donde actúa el sesgo de la primera opción.
  - Una pregunta puede ser dos opciones a la vez (fechas de un requisito). La skill recomienda un Noul por afirmación cuando más de una puede ser verdadera (`SKILL.md:165-167`). No cambiar sin datos.
- `:89-96`, `aplica`: es el Noul compañero del `Choice` (`SKILL.md:148-152`), pero la instrucción de `:91` pregunta "se puede buscar", que suena a `buscar_documentos` y no pregunta lo que el compañero debe preguntar: si alguna herramienta cubre la solicitud. `:93` ("No es necesario que el estado incluya la respuesta") es una salvedad de una rareza del modelo. `:94` enumera "noticias generales, resultados deportivos", que coincide con los casos probados (mundial); es mejor la situación general ("la pregunta trata de un tema sin relación con contratación").
- `:30` y `:22`, `ACTIVIDADES_CRONOGRAMA`: incluye `ninguna` como opción de no-aplica dentro de un `Choice`, cuando la skill dice que en jev-1.14 el Noul compañero suele funcionar mejor (`SKILL.md:150-152`). El compañero existe (`respaldo_*`, `:44-51`), pero su "falso" (`:49`) junta dos situaciones con "o" y una es una negación ("deja indeterminada"), contra `SKILL.md:163-164`. `herramientas.py:218-219` toma `ninguna` sin consultar el respaldo. `adquirir_documentos` es la primera opción (`:22`) por orden cronológico del numeral 2.2, no por mérito. Sin medición de fechas todavía (el sondeo cubrió solo el enrutador, `JEV.md:82`), esto es una sospecha, no un fallo observado.
- `:41` y `:46`: la referencia por ruta a `candidatas.cN` y una pregunta por candidata siguen la skill (`SKILL.md:130-134`). Sin desviación. Es la misma idea de "seleccionar, no generar" del [cookbook de fechas](https://docs.typesafe.ai/cookbooks/date_extraction_cookbook.md); la diferencia es que el cookbook descompone en mes, día y año como `Choice` y nosotros elegimos entre candidatas que el código ya encontró.
- `:56-63`, `inyeccion`: cumple. El falso de `:61` nombra un caso específico que confunde, que la skill permite.

`enrutador.py`:

- `:80`: el estado es solo `{"pregunta": pregunta}`. La skill pide dar lo que una persona miraría y los hechos que el código ya sabe (`SKILL.md:92-96`). Una persona que lee solo "Dime la fecha y la hora" no sabe que el analista está consultando documentos de una licitación de medicamentos del IGSS. Eso explica `aplica = 0.13` sin culpar al modelo. Propuesta: un campo `contexto` en el estado con ese hecho. Es una hipótesis: la skill avisa que un campo para una pregunta puede inclinar otra (`SKILL.md:99-101`), así que se prueba en desarrollo, midiendo `inyeccion` y `fuera_de_alcance`.
- `:88-89` frente a `:90`: `inyeccion` y `fuera_de_alcance` usan `>= noul_si` (0.7) y `concreta` usa `>= noul_no` (0.3). Entre 0.3 y 0.7, una pregunta con `inyeccion` de 0.6 pasa y una con `concreta` de 0.5 se trata como concreta. Son filas implícitas que nadie decidió.

`decision.py`:

- `:30-32` antes de `:35`: es el orden de "Dime la fecha y la hora". No lo recomiendo cambiar. `Guia_de_etiquetado.md:7` fija el orden "falta de herramienta, aclaración, herramienta", y `decidir` lo sigue. Cambiarlo para corregir un caso sería ajustar el código a un caso. Lo que falta es la etiqueta: el `revisor-casos` ciego debe decidir si esa pregunta es `aclarar` o `abstener`; con el estado con contexto, `aplica` probablemente suba.
- Sin fila para la franja: `aplica` entre 0.3 y 0.7 sigue sin motivo (`:30`), y `inyeccion` o `fuera_de_alcance` entre 0.3 y 0.7 pasan. `SKILL.md:204-206` pide que la franja tenga su fila. No fijo cuál (abstener, aclarar o revisión humana) sin ver cuántos casos caen ahí: F7 ya guarda las probabilidades crudas, así que se cuenta sin volver a llamar.
- `:39-41`: si la probabilidad de la herramienta es menor que `choice_min`, el código cambia en silencio a la herramienta de las reglas. Es una fila explícita, pero sin rastro; la skill lista "code that quietly overrides answers" como señal amarilla (`SKILL.md:255`). Basta registrar el cambio en la auditoría.

Mapa a jaggedness: lectura literal, `:66` y `:91`; sesgo de posición, `:84` y `:22`; instrucciones frente a criterios, `:66-68`; contenido adversarial, la pregunta del analista es entrada no confiable y JEV no la trata como hostil, por eso la unión con las reglas de `enrutador.py:88` es correcta; estado grande, no aplica (el estado es pequeño); fechas y números, bien resuelto (JEV elige candidata, el código compara).

## 4. Medir sesgo y robustez en F7 sin prompt gymnastics

Propuesta de principio: todo lo que sigue va en la misma solicitud que ya se manda para cada caso, como preguntas adicionales sobre el mismo estado. No hay corridas extra, y la corrida de prueba sigue siendo una sola (`F7_pruebas_y_jev.md:53`). Costo: unas tres veces los 870 tokens por caso, sobre 107 casos, son unos 280 000 tokens, cerca de 0.012 USD.

- **Sesgo de posición.** Para `herramienta` (3 opciones) y, cuando se corra el experimento de fechas, `actividad`: el mismo `Choice` repetido con las opciones en orden original, invertido y rotado, cada uno como pregunta con su propio id. Los nombres de opción son los mismos; solo cambia el orden del diccionario de criterios. Hay que confirmar que la API respeta el orden de las claves del objeto; la documentación que leí no lo dice, y se revisa en la [especificación OpenAPI](https://api.typesafe.ai/openapi.json) antes de contar con ello. Se reporta: porcentaje de casos en que cambia la opción elegida; cambio medio de probabilidad de la opción que pasa a ser primera; exactitud por orden con McNemar entre órdenes.
- **Robustez de redacción.** Para cada Noul de decisión (`inyeccion`, `fuera_de_alcance`, `concreta`, `aplica`), dos o tres redacciones equivalentes como preguntas separadas sobre el mismo estado. Reglas para que no sea prompt gymnastics:
  - las redacciones las escribe alguien que no vio los resultados y se congelan con el resto de las preguntas antes de la corrida de prueba;
  - no se elige la redacción que da mejor número; la que queda en producción se decide por la prueba de la persona y por claridad, y las otras solo miden robustez;
  - la métrica es la de self-consistency: discrepancia media entre redacciones sobre todos los cortes (|p1 - p2|), más el porcentaje de casos en que la decisión con 0.7 y 0.3 cambia.
- **Repetición idéntica.** La misma solicitud tres veces en momentos distintos, para estimar ruido de corrida. Si el ruido ya explica las diferencias entre redacciones, no hay sesgo que atribuir a la redacción.
- **Casos.** Los 60 de prueba, sin usar para ajustar ni redacciones ni umbrales; los 47 de desarrollo solo para la rejilla (`F7_pruebas_y_jev.md:19-25`). Si la medición encuentra un sesgo y se cambia una pregunta, el conjunto de prueba deja de ser limpio para esa versión: se declara, y se necesita otro conjunto para validar el cambio.
- **Calibración.** Con las etiquetas adjudicadas se derivan etiquetas de cada juicio (por ejemplo, `inyeccion` verdadera si el motivo esperado es `inyeccion`). Se reporta una tabla por franjas (0 a 0.3, 0.3 a 0.7, 0.7 a 1) con la tasa real de cada franja, más Brier (`I4_evaluacion_y_jev.md:299`). Con 60 casos los intervalos serán anchos: se reportan con Wilson y no se ajustan umbrales con ellos.
- **Citation check en F7.** Un conjunto aparte de afirmaciones: unas fieles (las 30 de 30 honestas de `Auditoria_F4.md:36`) y otras con un conector inventado, una unión que cambia el sentido y una cifra con letras, escritas por el `adversario` y etiquetadas por una persona. Se mide la proporción de infieles que se escalan y la de fieles que se escalan de más, con ambos órdenes de opciones. Sin esa medición el paso no se adopta.

Hoy `F7_pruebas_y_jev.md:33-34` deja el sesgo, la consistencia y la calibración fuera y solo pide guardar las probabilidades crudas. La recomendación es incluir las preguntas extra, porque cuesta casi nada y la corrida de prueba no se puede repetir limpia.

## Recomendaciones priorizadas

1. **Corregir `JEV.md:87`** para que diga que `fuera_de_alcance` en 0.03 es correcto y que `sin_herramienta` lo detectó `aplica`. Solo texto.
2. **Probar en desarrollo un campo `contexto` en el estado** (`enrutador.py:80`) antes de tocar el orden de `decision.py`. Sin reordenar `decision.py:30-35`. Etiquetar "Dime la fecha y la hora" con el revisor ciego.
3. **Dar fila a la franja 0.3 a 0.7** en la tabla de decisión y alinear los umbrales de `concreta` con los de `inyeccion` y `fuera_de_alcance`, pero decidir la acción de la fila con el conteo de casos en franja de la corrida de F7. Registrar en la auditoría el cambio de herramienta de `decision.py:39-41`.
4. **Reescribir las preguntas** sin salvedades por caso, antes de congelar el conjunto de prueba: `fuera_de_alcance` (`:66-69`), `concreta` (`:76-77`), `herramienta` (`:84-86`), `aplica` (`:91-94`), `ninguna` y `respaldo` falso (`:30`, `:49`). Cada cambio, probado en desarrollo y no con los casos de prueba.
5. **Incluir en la corrida de prueba de F7** las variantes de orden, las redacciones equivalentes y la repetición (sección 4). Son preguntas extra en la misma solicitud.
6. **Citation check:** adoptarlo como paso opcional de aviso, tras F7 y solo si el conjunto etiquetado de la sección 4 lo respalda. Módulo propio después del validador en `orquestador.py`, con una bandera de configuración, sin cambiar el texto ni bloquear.
7. **Más adelante, si F7 lo muestra:** dividir `fuera_de_alcance` en un Noul por regla, y `herramienta` en Nouls por herramienta.

## Decisiones para el visto bueno del usuario

Cada una con su opción recomendada; si no dices nada, se aplica esa.

- **D1. Cómo tratar el caso "Dime la fecha y la hora".**
  - Recomendada: no reordenar `decision.py`; probar el campo `contexto` en desarrollo y que el revisor ciego fije la etiqueta.
  - Alternativa: poner `concreta` antes de `aplica`. Haría que ese caso aclare, pero cambia el orden que fija la guía y se ajusta a un caso.
- **D2. Qué hacer con `fuera_de_alcance`.**
  - Recomendada: no ampliarla para que atrape temas ajenos; corregir el texto de `JEV.md:87`. Dividirla por regla solo si F7 muestra fallas en los casos prohibidos.
  - Alternativa: dividirla ya en un Noul por regla.
- **D3. Franja entre 0.3 y 0.7.**
  - Recomendada: contar los casos en franja con las probabilidades de F7 y decidir después la acción (abstener, aclarar o revisión humana por juicio). Mientras tanto, igualar la comparación de `concreta` a las otras.
  - Alternativa: fijar ya "abstener" para `inyeccion` y `fuera_de_alcance`, y "aclarar" para `concreta`, a riesgo de abstenerse de más.
- **D4. Sesgo, consistencia y calibración en F7 (revisa D6 de `F7_pruebas_y_jev.md:33`).**
  - Recomendada: incluir las preguntas extra en la misma corrida de prueba y reportar sesgo de posición, robustez de redacción y calibración por franjas.
  - Alternativa: dejarlo fuera y solo guardar las probabilidades crudas, sabiendo que luego no se puede medir sin una segunda corrida.
- **D5. Citation check.**
  - Recomendada: adoptar como aviso que escala a `needs_human_review`, después de medirlo con un conjunto etiquetado; sin sustituir la revisión humana de fidelidad ni reportarse como métrica de fidelidad.
  - Alternativa: no adoptarlo y dejar los riesgos residuales como están, declarados en `Auditoria_F4.md:47-66`.
- **D6. Cifras con letras.**
  - Recomendada: usar JEV solo para detectar la cifra con letras y dejar la igualdad de valor a una persona (o a código, si se mide que un analizador converge); no confiar en JEV para comparar valores.
  - Alternativa: pedirle a JEV que compare el valor. No lo recomiendo: es el punto débil documentado.
- **D7. Reescritura de las preguntas.**
  - Recomendada: reescribir antes de congelar la prueba (prioridad 4), con desarrollo como único banco de ajuste.
  - Alternativa: congelar las actuales y reportar las desviaciones como limitación.
