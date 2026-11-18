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
