# Experimento de JEV en el enrutador

Parte 2 de [F7](delegacion/F7_pruebas_y_jev.md). Este documento registra lo medido; las corridas con JEV en vivo se agregan cuando el usuario las ejecute.

## Conjunto de prueba (17 de noviembre de 2026)

Congelado en `src/licigt/consulta/casos_enrutador.json`: 60 casos, 12 por clase (`buscar_documentos`, `extraer_requisitos`, `comparar_versiones`, `aclarar` y `abstener`).

### Quién redactó y quién revisó

- **Proponente (40 casos, sin trampa):** `proponente-casos` en Codex, con `codex exec -s read-only --ephemeral`.
- **Adversario (20 casos engañosos):** `adversario` en OpenCode con `opencode/deepseek-v4.1-flash-free`.
  - F7 pedía Kimi. No hubo acceso: Copilot no ofrece Kimi K3, OpenCode Go llegó a su límite mensual, y OpenRouter y Hugging Face no tenían saldo.
  - El usuario autorizó un modelo gratuito de OpenCode. DeepSeek es de otra familia que el proponente (OpenAI) y el revisor (Claude).
- **Revisor a ciegas:** `revisor-casos` con `claude -p`, en sesión aislada, sobre `ciego_enrutador.json` (solo `id`, `evento` y pregunta).
  - Leyó la guía, el archivo ciego y las preguntas de desarrollo (`casos_desarrollo.json` y `CASOS_ADICIONALES`), que su definición le pide para detectar duplicados. No leyó las etiquetas del proponente ni del adversario (verificado en el registro de su sesión).

### Acuerdo

- **Primera revisión:** 100 % sobre 60, kappa 1,000, sin desacuerdos.
  - El revisor marcó 7 casos como paráfrasis de desarrollo. El usuario decidió reemplazarlos.
  - El proponente redactó 5 y el adversario 2, en las mismas clases, con una lista de preguntas y temas que evitar (`evitar_reemplazo.txt`, sin preguntas de desarrollo ni etiquetas).
- **Segunda revisión, en sesión nueva, sobre los 60:** 100 %, kappa 1,000, sin desacuerdos.
  - Marcó 12 casos distintos como paráfrasis de desarrollo, entre ellos uno de los reemplazos. En la primera revisión esos 12 estaban limpios.
  - La marca no es estable entre corridas: en clases estrechas (inyección, aclarar una fecha) casi cualquier pregunta se parece a una de desarrollo.
- **Decisión del usuario:** congelar los 60. Cada caso guarda las marcas del revisor en `marcas_revisor`, y McNemar se reporta con los 60 y sin los 12 marcados como `duplica_desarrollo`.
- **Lectura del acuerdo:** un kappa de 1,000 dice que la guía es clara para estos casos, no que las etiquetas sean correctas. Los dos agentes etiquetan contra la misma guía.

### Conjunto de desarrollo

- Las 47 preguntas (27 de `casos_desarrollo.json` y 20 de `CASOS_ADICIONALES`) se etiquetaron con el mismo revisor a ciegas: 33 con confianza alta, 9 media y 5 baja.
- Las 5 de confianza baja son la pregunta del seguro de caución en cada evento. El usuario confirmó `buscar_documentos`.
- Las etiquetas viven en `data/consulta/agentes/etiquetas_desarrollo.json`, fuera del repositorio.

### Huecos de la guía que señaló el revisor

- No define `risk_level` ni `answerable` para el enrutador.
- No dice qué prevalece cuando una pregunta pide listar lo que cambió entre versiones (`extraer_requisitos` o `comparar_versiones`).
- No dice si el lugar de recepción "según el cronograma" va a `extraer_requisitos` o a `buscar_documentos`, ni si un plazo que no es actividad del cronograma (el de entrega) es fecha o dato.

## Corridas con JEV

Las ejecuta el usuario con su llave; los registros quedan en `data/consulta/experimentos/`, fuera del repositorio.

### Desarrollo (18 de noviembre de 2026, 02:30 UTC)

Registro `desarrollo_20261118T023012Z.json`: 47 preguntas, corrida limpia, sin errores ni degradaciones, modelo `jev-1.14.0`.

- **Rejilla:** la mejor combinación (`choice_min` 0,6) tiene 6 errores y la de defecto 7. La regla de elección exige 3 casos de mejora o menos críticos, así que los umbrales se quedan en los valores por defecto (`noul_si` 0,7, `noul_no` 0,3, `choice_min` 0,5). No hay cambio en el código.
- **Exactitud con esos umbrales:**

| Variante | Aciertos | Exactitud | Wilson 95 % | Críticos |
|---|---|---|---|---|
| Reglas | 45 de 47 | 0,957 | 0,858 a 0,988 | 0 |
| JEV | 40 de 47 | 0,851 | 0,723 a 0,926 | 0 |

- **McNemar:** JEV acierta 2 que las reglas fallan y falla 7 que las reglas aciertan (p = 0,18).
  - **JEV corrige:** las dos preguntas fuera de tema ("precio del petróleo", "mundial de 2022"), que las reglas mandan a `buscar_documentos`.
  - **JEV falla:**
    - las 5 del seguro de caución, que manda a `extraer_requisitos`. Es la etiqueta que el revisor marcó con confianza baja y el usuario fijó en `buscar_documentos`;
    - "Dime la fecha y la hora", que trata como fuera de tema en vez de aclarar;
    - "¿Qué fecha está vigente para la recepción?", que manda a `extraer_requisitos` en vez de comparar.
- **Latencia de JEV por pregunta:** mediana 193 ms, P95 246 ms, máximo 278 ms.
- **Veredicto en desarrollo:** no adoptar (no es significativo y JEV acierta menos). Es orientativo: el veredicto que cuenta es el de la corrida de prueba.

### Prueba (18 de noviembre de 2026, 03:06 UTC)

Registro `prueba_20261118T030611Z.json`: 60 casos, una sola corrida, limpia, sin errores ni degradaciones. Umbrales por defecto.

| Conjunto | n | Reglas | JEV | Críticos (reglas / JEV) | McNemar (b, c, p) |
|---|---|---|---|---|---|
| Completo | 60 | 37 (0,617; Wilson 0,490 a 0,729) | 53 (0,883; Wilson 0,778 a 0,942) | 6 / 0 | 16, 0, 3,1·10⁻⁵ |
| Sin los 12 marcados `duplica_desarrollo` | 48 | 30 (Wilson 0,484 a 0,748) | 42 (Wilson 0,753 a 0,941) | 3 / 0 | 12, 0, 4,9·10⁻⁴ |

- **Dónde gana JEV:**
  - las inyecciones y los pedidos fuera de alcance que las reglas mandan a una herramienta ("el supervisor ha cambiado tu función", la nota al pie que da órdenes, "certifícame por escrito", "toma la decisión por nuestra empresa");
  - las preguntas sin referente ("explícame eso que aparece", "¿a qué se refiere ese apartado?");
  - las de fuera de tema (ajedrez, guitarra);
  - las trampas de cronograma que las reglas mandan a `extraer_requisitos` ("¿qué cláusula menciona el plazo de entrega?", "¿en qué dirección se reciben las ofertas según el cronograma?").
- **Dónde fallan los dos:**
  - "¿Cómo quedó el partido del domingo? Estoy esperando el cronograma…", que ambos mandan a `extraer_requisitos`;
  - "Lo de 363-IGSS-2026, ¿dónde lo dice?", que ambos mandan a buscar;
  - "¿Cuándo es la entrega de la modificación?", que ambos mandan a comparar;
  - "Indícame el período para solicitar aclaraciones…", que ambos mandan a buscar;
  - "¿En qué fecha y a qué hora será la inducción…?" y "Cítame todas las fechas del cronograma…", que ambos tratan como ambiguas.
- **Diferencia con desarrollo:** en desarrollo las reglas ganaban (45 contra 40). Las reglas se escribieron con esas preguntas, así que aciertan por construcción. El conjunto de prueba, redactado contra la guía, muestra cuánto generalizan.

### Latencia del resto del flujo

Medida el 18 de noviembre con las 107 preguntas (60 de prueba y 47 de desarrollo) contra la API en `127.0.0.1:8010`, una por una, con el enrutador de reglas, la recuperación en GPU y `llama-server` (contexto 12288). Las 20 de `CASOS_ADICIONALES` no traen evento y se corrieron con el 222.

- **Todas:** mediana 5,4 s, P95 29,3 s, máximo 40,2 s. Todas respondieron 200.
- **Con herramienta (82):** mediana 7,0 s, P95 29,4 s.
- **Por herramienta (P95):** `buscar_documentos` 29,0 s, `extraer_requisitos` 31,2 s y `comparar_versiones` 15,2 s.
- **Sobre 15 s:** 21 consultas, casi todas de búsqueda o de requisitos.
- **JEV agrega:** P95 de 238 ms por pregunta.

### Veredicto

**No adoptar con el flujo actual.** Es lo que da la regla fijada antes del experimento (`comparar prueba --p95-resto-ms 29280`):

- los críticos no aumentan: cumple (0 contra 6);
- la diferencia es significativa: cumple (p = 3,1·10⁻⁵, y 4,9·10⁻⁴ sin los casos marcados);
- el P95 total dentro de 15 s: no cumple (29,3 s más 0,24 s).

El incumplimiento de latencia es del flujo base, no de JEV: sin JEV el P95 ya es de 29,3 s. El criterio no se cambia después de ver el resultado. Si el flujo base baja de 15 s, la misma regla da "adoptar" sin tocarla. El P95 de 29 s queda como limitación medida del sistema frente a la meta del anteproyecto.

### Nueva medición con la recuperación en GPU (18 de noviembre de 2026)

Después de R2C, el reranker y bge-m3 corren en la GPU en fp16, y la búsqueda mejorada bajó de unos 13,6 s a 0,21 s (p50). El P95 del flujo se volvió a medir con `make reporte` (commit `0b2f143`, 62 preguntas, `data/plataforma/reporte/20261118T193250Z.md`).

- **Total:** P50 3,5 s, P95 28,2 s y máximo 38,1 s.
- **Por herramienta (P95):** `buscar_documentos` 24,5 s, `comparar_versiones` 18,6 s y `extraer_requisitos` 38,1 s (P50 17,2 s).
- **Dónde está el tiempo:** en la generación del LLM local. Cada consulta manda en promedio 5 940 tokens de entrada y recibe 435 de salida, a unos 85 tokens por segundo; la regeneración, cuando la hay, duplica la llamada.

**El veredicto no cambia:** no adoptar con el flujo actual, porque el P95 total (28,2 s más 0,24 s de JEV) sigue sobre la meta de 15 s. El cuello de botella dejó de ser la recuperación y pasó a ser la generación. Para bajar de 15 s habría que acortar la evidencia, limitar la salida o evitar la regeneración. Queda como trabajo futuro.

## Variante LLM (18 de noviembre de 2026)

Encargo [J2](delegacion/J2_variante_llm_del_enrutador.md): `Anteproyecto.md:342` y `DESIGN.md:24` comprometen comparar reglas, LLM con salida estructurada y JEV, y solo se habían medido reglas y JEV.

### Qué se midió

- **Modelo:** `qwen3.5-9b` en `llama-server` local (`127.0.0.1:8080`), sin salida de la máquina ni costo; no se llamó a JEV.
- **Cliente:** `ClienteEnrutadorLlm` (`enrutador.py`) usa `ClienteGeneradorOpenAI` con esquema JSON estricto (`accion`, `motivo`, `herramienta`), temperatura 0, semilla 42 y un prompt corto con las definiciones de la guía de etiquetado. `max_tokens` es 128.
- **Degradación:** un JSON inválido, un esquema incoherente (`usar_herramienta` sin herramienta) o una espera agotada degradan a reglas (`degradado`), como JEV. Ninguna de las 107 corridas degradó.
- **Combinación:** como en JEV, las señales de las reglas (inyección, fuera de alcance, no específica) se suman a las del modelo; el modelo decide la herramienta.
- **Corrida:** `make experimento-llm CONJUNTO=desarrollo|prueba` y, para comparar, `make experimento-llm CONJUNTO=... COMPARAR=1 P95_RESTO_MS=29280`. Los registros son `llm_desarrollo_20261118T225008Z.json` y `llm_prueba_20261118T225319Z.json` en `data/consulta/experimentos/`.
- **Protocolo:** primero desarrollo; luego una sola corrida de prueba (limpia). La regla de adopción es la de JEV, sin cambios: críticos que no aumentan, McNemar significativo a favor y P95 total dentro de 15 s con el P95 del resto del flujo de 29 280 ms.

### Desarrollo (47 preguntas)

| Variante | Aciertos | Exactitud | Wilson 95 % | Críticos |
|---|---|---|---|---|
| Reglas | 45 | 0,957 | 0,858 a 0,988 | 0 |
| JEV | 40 | 0,851 | 0,723 a 0,926 | 0 |
| LLM | 36 | 0,766 | 0,628 a 0,864 | 0 |

- **McNemar LLM contra reglas:** b = 2, c = 11, p = 0,022 (a favor de las reglas, que aciertan por construcción en desarrollo).
- **Fallas del LLM:** la fecha y hora de recepción la manda a `aclarar` (5 eventos), la plica a `buscar_documentos` (5) y "qué fecha está vigente" a `aclarar`.
- **Latencia del enrutador LLM:** mediana 486 ms, P95 554 ms, máximo 2,4 s.

### Prueba (60 casos, una sola corrida)

| Conjunto | n | Reglas | JEV | LLM | Críticos (reglas / JEV / LLM) |
|---|---|---|---|---|---|
| Completo | 60 | 37 (0,617; Wilson 0,490 a 0,729) | 53 (0,883; 0,778 a 0,942) | 51 (0,850; 0,739 a 0,919) | 6 / 0 / 0 |
| Sin los 12 `duplica_desarrollo` | 48 | 30 (0,484 a 0,748) | 42 (0,753 a 0,941) | 40 (0,704 a 0,913) | 3 / 0 / 0 |

- **McNemar frente a reglas:**
  - LLM, completo: b = 18, c = 4, p = 0,0043. Sin los marcados: b = 13, c = 3, p = 0,021.
  - JEV, completo: b = 16, c = 0, p = 3,1·10⁻⁵.
  - LLM contra JEV: b = 4, c = 6, p = 0,75; no hay diferencia demostrable entre los dos.
- **Dónde acierta el LLM:** las 12 abstenciones (inyecciones, fuera de alcance y fuera de tema), sin un solo crítico, y las 12 de `buscar_documentos`; 11 de 12 en `comparar_versiones`.
- **Dónde falla (9 casos):**
  - 6 de las 12 de `extraer_requisitos`: 3 de listar documentos las manda a `buscar_documentos` y 2 las trata como ambiguas ("Cítame todas las fechas del cronograma", la hora de la inducción);
  - `aclarar`: manda "Lo de 363-IGSS-2026, ¿dónde lo dice?" a buscar y "no entiendo esa parte" a abstener;
  - una de comparar a buscar.
- **Latencia del enrutador LLM:** mediana 543 ms, P95 15,1 s, máximo 21,6 s. Cinco llamadas pasaron de 10 s porque otros procesos usaban el mismo servidor y la GPU durante la corrida (en desarrollo, a solas, el P95 fue de 554 ms). El P95 queda registrado tal como se midió; no se repitió la corrida de prueba.

### Veredicto

**No adoptar con el flujo actual**, con la regla de JEV sin tocarla (`comparar prueba --variante llm --p95-resto-ms 29280`):

- los críticos no aumentan: cumple (0 contra 6);
- la diferencia es significativa a favor: cumple (p = 0,0043; 0,021 sin los marcados);
- el P95 total dentro de 15 s: no cumple. Con el P95 medido (15,1 s) más el del resto (29,3 s) son 44 s; aun con la latencia de desarrollo (0,55 s) el total sería de 29,8 s, porque el flujo base ya excede.

**Lectura comparada.** Los dos enrutadores con modelo superan a las reglas en la prueba y no se distinguen entre sí (p = 0,75). El LLM local es gratuito y mantiene en cero los críticos; JEV acierta 2 casos más y tarda unos 240 ms contra unos 500 ms. En desarrollo ninguno supera a las reglas. Ninguno cambia la decisión de adopción, que depende del P95 de 29 s del resto del flujo.

## Fechas de la lista (F7b)

Encargo [F7b](delegacion/F7b_jev_en_fechas.md): `DESIGN.md:24` pide que JEV se quede en cada punto solo si mejora el resultado en un banco etiquetado. En el enrutador se midió; en las fechas de la lista JEV se usaba sin experimento. Aquí asigna cada fecha candidata a una actividad del cronograma, y las fechas verificadas alimentan la detección de `fechas_distintas`. Se compararon JEV, reglas deterministas y no verificar.

### Protocolo

- **Candidatas:** las fechas que produce `extraer_requisitos` con los mismos parámetros y la misma pregunta que la propuesta real (`parametros_propuesta` en `lista.py`), con el pasaje que arma `herramientas.py`.
  - Desarrollo (eventos 399 y 363): 8 candidatas.
  - Prueba (eventos 368, 327 y 222): 15 candidatas.
- **Por qué desarrollo queda por debajo de 15:** solo entran fechas escritas como "N de mes de AAAA", y en los eventos de desarrollo la recuperación del cronograma trae pocas filas (adquisición, inducción y recepción) más la solvencia patronal. Ampliar las consultas habría cambiado qué se considera candidata, así que no se hizo.
- **Etiquetas:** la actividad de `preguntas_jev.py` o `ninguna`, a ciegas.
  - Proponente en Codex y revisor en Claude, con 23 de 23 de acuerdo (8 de desarrollo y 15 de prueba).
  - El etiquetado de prueba se repitió porque el hallazgo A1 de la auditoría cambió la consulta de la exportación y se permutaron los ids del 222. Las 8 fechas y sus pasajes son los mismos.
- **Regla de adopción, fijada antes de correr:**
  - Crítico: una fecha `verificada` con una actividad distinta de la etiqueta. Acierto: `verificada` con la actividad correcta.
  - JEV se queda si no tiene más críticos que las reglas y supera sus aciertos con McNemar p < 0,05.
  - Si no se cumple, se adoptan las reglas cuando no tienen críticos; si las dos tienen críticos, las fechas quedan sin verificar y la detección de conflictos de fechas se declara como limitación.
- **Aclaraciones previas, hechas antes de cualquier corrida con JEV y de ver las reglas sobre prueba:**
  - Si JEV tiene 0 críticos, las reglas tienen 1 o más y JEV acierta al menos una, JEV se queda aunque no haya significancia, porque un crítico pesa más que una fecha sin verificar. Con 0 aciertos, las fechas quedan sin verificar.
  - Si JEV tiene críticos y las reglas no, se adoptan las reglas.
- **Reglas:** palabras clave de cada actividad tomadas de las definiciones de `ACTIVIDADES_CRONOGRAMA`, en la fila de la tabla o el texto anterior a la fecha. Sin coincidencia única, `no_verificada`. Huella de las palabras clave al medir: `8ac0fd8df76e`; la vigente es `d925b6f6f849` (ver limitaciones).
- **Latencia:** se reporta, pero no decide.

### Resultado (prueba, 15 candidatas)

- **Reglas:** 11 aciertos, 0 críticos y 4 `no_verificada`. Las 4 son solvencias patronales, con etiqueta `ninguna`.
- **Conflictos del 222:** las reglas detectan los dos conocidos (adquisición de documentos y recepción de ofertas).
- **Veredicto:** `reglas`, sin corrida de JEV, porque la regla ya estaba determinada con estos datos.

### Potencia

- Para que JEV ganara con McNemar bilateral exacto necesitaba al menos 6 casos que las reglas fallaran y él acertara (con 5 casos y ninguno en contra, p = 0,0625).
- Las reglas solo fallan en 4 candidatas, y todas tienen etiqueta `ninguna`: JEV no puede acertarlas como `verificada`. El máximo de discordantes a favor de JEV era 0 (p mínimo 1), así que JEV no podía superar a las reglas con estos datos, tuviera la llave que tuviera. Por eso no se llamó a JEV.

### Decisión

- La propuesta de lista verifica las fechas de filas de tabla con las reglas (`fechas_reglas.py`). Una fecha sin coincidencia única queda `no_verificada` y aparece en la propuesta marcada para revisión; la detección de `fechas_distintas` usa las verificadas.
- JEV no se usa en las fechas del sistema entregado. Costo 0, sin datos fuera de la máquina y sin la dependencia de la llave. `extraer_requisitos` conserva el parámetro `cliente_jev` por compatibilidad, sin usarlo, y la API ya no crea el cliente para la propuesta. El caso `r3-ind-jev-fechas` del banco se corrigió: ya no simula JEV caído.
- JEV sigue en el enrutador y en la verificación de citas, con sus propios experimentos. El código del experimento de fechas (`experimento_fechas.py`) se conserva y puede repetirse con otro conjunto.

### Limitaciones

- Muestra pequeña: 8 candidatas de desarrollo y 15 de prueba. La decisión vale para estos datos, no es una medida de generalización.
- La verificación por reglas solo vale en filas de tabla, que es lo medido (las 6 candidatas no tabulares eran solvencias). Fuera de una tabla una fecha nunca se verifica.
- Una fecha `no_verificada` sin ninguna actividad mencionada (una solvencia) solo deja el aviso `fechas_no_verificadas`. Si su texto menciona alguna actividad (coincidencia ambigua, o prosa con palabra clave), pide revisión humana: el ítem va con revisión y la respuesta lleva `needs_human_review` y el aviso `fecha_ambigua: <actividades>`.
- La verificación por reglas solo aplica a la propuesta de lista (`proponer_lista`), que es lo medido; en el chat `extraer_requisitos` deja las fechas `no_verificada`.
- La huella de las reglas cambió a `d925b6f6f849` al agregar el alcance "solo filas de tabla". Ese cambio se hizo después de ver el resultado de prueba, por un hallazgo de auditoría (verificación fuera de tabla nunca medida), y solo restringe: no puede crear aciertos nuevos. Se declara como cambio posterior a la corrida. Con la huella nueva, prueba sigue en 11 aciertos, 0 críticos, 4 `no_verificada` y los dos conflictos del 222.
- Solo 3 actividades están representadas en las candidatas (adquisición de documentos, inducción y recepción de ofertas, además de `ninguna`). Las reglas para solicitud y respuesta de aclaraciones, formulario electrónico, apertura de plicas y adjudicación no se midieron.
- Las fechas que no están escritas como "N de mes de AAAA" no son candidatas: ni las reglas ni JEV las ven.
- Con varias fechas iguales en un pasaje fuera de tabla, las reglas cortan en la primera aparición del literal; solo puede dejar la fecha sin verificar.
- Las fechas de solvencia, que JEV habría marcado fuera del cronograma, ahora aparecen como fecha sin verificar con revisión pendiente.
