# Encargo F7: casos del banco, métricas y experimento de JEV

Para Codex u OpenCode (código) y para el usuario (corridas de agentes y de JEV). Rama `rol/consulta`. Abre el agente con `make codex` o `make opencode`. El gestor auditará el resultado y el `adversario` intentará refutarlo; no commitees.

Lee primero:

- [`AGENTS.md`](../../../AGENTS.md);
- el [plan del rol 3](../Plan_rol_3.md#f7-pruebas-con-el-rol-4), sección F7;
- [I4](../investigacion/I4_evaluacion_y_jev.md), secciones 2 a 5;
- [I5](../investigacion/I5_agentes_agnosticos.md), secciones 3 y 4;
- la [guía de etiquetado](../Guia_de_etiquetado.md);
- `src/licigt/consulta/enrutador.py`, `decision.py`, `preguntas_jev.py`, `sondeo_jev.py`, `orquestador.py` y `herramientas.py`.

## Decisiones para el visto bueno del usuario

Sin evidencia suficiente en el repo o en el curso para decidirlas solo. Cada una trae su opción recomendada; si el usuario no dice nada, se aplica esa.

- **D1. Quién escribe las 60 preguntas de prueba.**
  - Recomendada: el `proponente-casos` escribe 40, 8 por clase y sin casos tentadores; el `adversario` escribe 20, 4 por clase y todos tentadores. Así se cumple "alrededor de un tercio tentadores" (`I4_evaluacion_y_jev.md:210`) y "un agente adversario aporta los casos engañosos" (`Plan_rol_3.md:100`), y las clases quedan balanceadas en 12.
  - Alternativa: el proponente escribe las 60 y el adversario solo ataques para el banco.
  - El reparto 40 y 20 no tiene respaldo, es propuesta del gestor.
- **D2. Quién etiqueta las 47 preguntas de desarrollo.** Hoy no tienen etiqueta (`I4_evaluacion_y_jev.md:204`).
  - Recomendada: el `revisor-casos` las etiqueta a ciegas y el usuario solo revisa las de `confianza: "baja"`. Es desarrollo: sirve para la rejilla de umbrales, no para el resultado.
  - Alternativa: las etiqueta el usuario.
- **D3. El LLM como tercera variante del enrutador.** `EnrutadorLlm` no tiene cliente y se degrada a reglas (`enrutador.py:104-105`). El anteproyecto se comprometió a comparar reglas con la salida estructurada del modelo (`I4_evaluacion_y_jev.md:57`).
  - Recomendada: este encargo compara reglas con reglas más JEV. Conectar el LLM al enrutador va en un encargo aparte si sobra tiempo, y se anota en `Cambios_pendientes.md`. Es la opción por defecto de I4 (`I4_evaluacion_y_jev.md:323`).
  - Alternativa: conectarlo ahora con el cliente de `llm.py`. Hace falta el servidor local en marcha para correrlo.
- **D4. El experimento de fechas de F3b.** Es una mejora (`I4_evaluacion_y_jev.md:298`).
  - Recomendada: se pospone a un F7b, después de F6, y primero va el enrutador.
  - Alternativa: incluirlo aquí. Su unidad es la candidata, con los eventos 363, 368 y 327 como prueba.
- **D5. Qué P95 entra en el criterio de adopción.** El criterio dice "P95 dentro de los 15 s" (`Plan_rol_3.md:105`), pero el experimento solo mide la etapa de decisión.
  - Recomendada: el criterio se evalúa sumando el P95 de la etapa de JEV y el P95 del resto del flujo medido en la integración; `orquestador.py:106` y `:233` ya registran la latencia total. Mientras no haya integración, el criterio de latencia se reporta como "pendiente" y se informan p50 y p95 de JEV (`I4_evaluacion_y_jev.md:257`).
- **D6. Sesgo de posición, consistencia y calibración.** Son mejoras (`I4_evaluacion_y_jev.md:300-301`).
  - Recomendada: quedan fuera de este encargo, pero la corrida guarda las probabilidades crudas para poder calcularlas después sin volver a llamar a JEV.

## Cinco porqués de las decisiones tomadas

### Formato de los casos y dónde viven

1. ¿Por qué el formato de I4? Porque usa los campos que exige el curso (`I4_evaluacion_y_jev.md:41`, `:111`) y sigue siendo compatible con `casos_desarrollo.json` del rol 2 (`I4_evaluacion_y_jev.md:68-73`).
2. ¿Por qué no esperar el formato del rol 4? Porque se le pidió y no respondió; el aviso ya trae esta opción por defecto (`docs/plataforma/Avisos_del_rol_3.md:18`, `:38-45`).
3. ¿Por qué en `src/licigt/consulta/casos_banco.json`? Porque I4 lo fija junto a los casos del rol 2, y el rol 4 los une al banco (`I4_evaluacion_y_jev.md:275`, `:311`).
4. ¿Por qué una función pura de métricas en el módulo del rol 3? Porque el reparto le da al rol 3 los dobles y las métricas, y al rol 4 el ejecutor (`I4_evaluacion_y_jev.md:276`, `:282`, `:312`).
5. ¿Por qué con dobles y sin red? Porque las pruebas del rol 3 no deben requerir red, GPU ni base de datos (`AGENTS.md`, sección "Comandos"; `I4_evaluacion_y_jev.md:114`).

No hace falta un aviso nuevo para el rol 4: los del banco y las métricas ya existen (`docs/plataforma/Avisos_del_rol_3.md:38-45`).

### Separación entre desarrollo y prueba

1. ¿Por qué las 47 del sondeo solo sirven para desarrollo? Porque ya se usaron para escribir reglas y criterios, y en ellas las reglas aciertan por construcción (`Guia_de_etiquetado.md:72`; `I4_evaluacion_y_jev.md:204`).
2. ¿Por qué 60 preguntas nuevas? Porque con 60 el intervalo de Wilson es de unos 15 puntos y McNemar detecta diferencias de unos 10 (`I4_evaluacion_y_jev.md:216-218`).
3. ¿Por qué escribirlas y congelarlas antes de correr? Porque una pregunta de prueba nunca se usa para ajustar, y se congela con el hash del commit (`Guia_de_etiquetado.md:73-74`; `I4_evaluacion_y_jev.md:245-246`).
4. ¿Por qué una sola corrida de prueba? Porque si se cambia algo después, el conjunto deja de estar limpio (`I4_evaluacion_y_jev.md:246`).
5. ¿Por qué evitar paráfrasis de desarrollo? Porque el anteproyecto lo pide (`I4_evaluacion_y_jev.md:212`), y el revisor marca `duplica_desarrollo` (`.agentes/revisor-casos.md:36`).

### Quién propone, quién revisa y quién adjudica

1. ¿Por qué otra familia de modelos para el revisor? Porque un juez prefiere sus propias salidas (`I5_agentes_agnosticos.md:143`).
2. ¿Por qué a ciegas? Porque así no se ancla en las etiquetas del proponente (`I5_agentes_agnosticos.md:145`; `Guia_de_etiquetado.md:78`).
3. ¿Por qué con ids neutros y en orden mezclado? Porque el prefijo de id revelaría el autor, y con él si el caso es tentador. Lo exige el modo ciego del revisor (`.agentes/revisor-casos.md:26`).
4. ¿Por qué adjudica el usuario? Porque cuenta como segunda revisión declarada (`Guia_de_etiquetado.md:79`; `AGENTS.md`, "Agentes con rol").
5. ¿Por qué los comandos de cada herramienta? Porque son los verificados en I5 (`I5_agentes_agnosticos.md:121-124`) y los que fija `AGENTS.md`.

### Grabar y reproducir para la rejilla de umbrales

1. ¿Por qué una rejilla? Porque el anteproyecto pide umbrales calibrados en desarrollo (`I4_evaluacion_y_jev.md:58`, `:299`).
2. ¿Por qué solo 3 valores por umbral? Para no sobreajustar (`I4_evaluacion_y_jev.md:243-244`).
3. ¿Por qué grabar las respuestas de JEV y reproducirlas? Porque los umbrales actúan sobre las probabilidades que ya devolvió JEV (`enrutador.py:87-89`; `decision.py:30`, `:39`). Con una sola llamada por pregunta se prueban las 27 combinaciones sin volver a llamar a JEV.
4. ¿Por qué pasar los umbrales como parámetro? Porque hoy son constantes de módulo importadas por nombre (`preguntas_jev.py:3-5`). Parcharlas en tres módulos sería frágil, y el parámetro con los mismos valores por defecto no cambia el comportamiento.
5. ¿Por qué vista previa por defecto y `--confirmar-envio`? Porque es el patrón del sondeo (`sondeo_jev.py:1`, `:85`, `:89`): sin autorización explícita no se envía nada a un tercero.

### Métricas del experimento y criterio de adopción

1. ¿Por qué McNemar exacto? Porque las dos variantes responden las mismas preguntas y el criterio lo fija (`Plan_rol_3.md:102-106`; `Cambios_pendientes.md`, sección 12).
2. ¿Por qué contar errores críticos aparte? Porque la regla es "primero cero errores críticos" (`I4_evaluacion_y_jev.md:244`). Para el enrutador, un error crítico es un caso que esperaba `abstener` por `inyeccion` o `fuera_de_alcance` y la variante no se abstiene.
3. ¿Por qué Wilson? Para reportar la exactitud con su intervalo y no como un número suelto (`I4_evaluacion_y_jev.md:216`).
4. ¿Por qué kappa de Cohen? Porque la guía pide porcentaje de acuerdo y kappa (`Guia_de_etiquetado.md:78`).
5. ¿Por qué medir la latencia en el cliente? Porque el sondeo no mide tiempos (`I4_evaluacion_y_jev.md:257`), y el criterio la necesita (D5).

## Parte 1: casos del rol 3 para el banco común

### Casos

- Los 23 casos de la tabla de I4 (`I4_evaluacion_y_jev.md:121-145`): 15 mínimos más los recomendados, con el formato de `I4_evaluacion_y_jev.md:75-115`.
- **Redacción:** el `proponente-casos` en modo `banco` escribe `casos_banco.json` a partir de esa tabla y completa páginas y pasajes con `data/consulta/corpus/chunks.jsonl`. Si no lo verificó, deja `expected_sources` vacío.
- **Revisión:** el `revisor-casos` en modo `evidencia` verifica páginas y pasajes, y comprueba la ausencia en los casos fabricados (r3-seg-requisito-fabricado y r3-sin-adjudicado).
- **Adjudicación:** el usuario decide los desacuerdos y anota `revisado_por`.
- **Dependencia:** `r3-conf-guardar` necesita F5 (la lista de verificación). Hasta entonces se marca `"pendiente": "F5"` y las métricas lo excluyen y lo cuentan aparte.

### Código, para Codex (Parte 1)

Archivos: `src/licigt/consulta/banco.py`, nuevo, y `src/licigt/consulta/tests/test_banco.py`, nuevo. Nada más.

- **`CasoBanco`**, en Pydantic:
  - obligatorios, los campos del curso: `id`, `question`, `expected_behavior`, `expected_sources`, `expected_pages`, `answerable` y `risk_level` (`bajo`, `medio` o `alto`);
  - opcionales: `evento`, `tipo`, `esperado`, `nivel` (`e2e`, `herramienta` o `validador`), `simulacion`, `particion`, `autor`, `revisado_por` y `pendiente`.
  - Usa `extra="forbid"` en `esperado`, para que un error de tipeo no pase.
- **`cargar_banco(ruta) -> list[CasoBanco]`.**
- **Dobles de `simulacion`:**
  - `{"jev": "caido"}`: un cliente que lanza `FallaJev`;
  - `{"recuperacion": "falla"}`: un recuperador que lanza;
  - `{"fragmento_inyectado": "..."}`: un recuperador que añade ese fragmento al resultado real del doble;
  - `{"llm_params": {...}}`: llama a la herramienta con esos parámetros, sin pasar por el enrutador.
- **`ejecutar_caso(caso, *, ctx, recuperador, generador, enrutador, cliente_jev=None)`:** aplica la simulación, llama a `consultar` y devuelve la salida (`RespuestaEstructurada`), más el evento de auditoría capturado con un `auditar` local.
  - La acción y la herramienta salen de `intencion` y `herramienta` del evento (`orquestador.py:124`, `:230`).
- **`metricas(casos, resultados) -> dict`:** función pura con las métricas deterministas de `I4_evaluacion_y_jev.md:163-175`, por caso y en total. No incluye fidelidad ni ALCE, que son humanas.
- **Pruebas, cada una primero en rojo:**
  - un caso por tipo de simulación con dobles, incluido el de JEV caído, que debe devolver salida válida y `degradado`;
  - las métricas sobre un conjunto pequeño con valores conocidos, incluida la división entre cero cuando no hay casos de una clase;
  - un caso con `pendiente` que queda fuera del total;
  - un `esperado` con una clave desconocida se rechaza.

## Parte 2: experimento de JEV en el enrutador

### Precondiciones

- La guía está commiteada (commit `8314abf`). Si se corrige un hueco, se re-etiquetan solo los casos afectados (`Guia_de_etiquetado.md:80`).
- El corpus se extrae una vez (lo hace el gestor o el usuario; `I5_agentes_agnosticos.md:179`):

```bash
mkdir -p data/consulta/agentes data/consulta/experimentos
unzip -o -q entregables/recuperacion/empresa_demo.zip chunks.jsonl inventario.json -d data/consulta/corpus
```

- `data/` está ignorado por Git (`.gitignore:3`). Ahí van las salidas crudas de los agentes y de JEV. Solo se commitean los casos finales adjudicados y el reporte.

### Código, para Codex (Parte 2)

Archivos:

- nuevos: `src/licigt/consulta/experimento.py` y `src/licigt/consulta/tests/test_experimento.py`;
- con cambio mínimo: `preguntas_jev.py`, `enrutador.py` y `decision.py` (umbrales como parámetro);
- un objetivo nuevo en el `Makefile`.

Nada más.

- **Umbrales como parámetro:**
  - `Umbrales` en `preguntas_jev.py`, en Pydantic y `frozen`, con `noul_si=0.7`, `noul_no=0.3` y `choice_min=0.5` por defecto. Las constantes actuales quedan como alias de esos valores.
  - `EnrutadorJev(..., umbrales=Umbrales())` y `decidir(..., umbrales=Umbrales())`.
  - Sin cambio de comportamiento: las pruebas existentes pasan sin tocarlas.
- **`experimento.py`**, todo sin red salvo `correr` con `confirmar=True`:
  - `exportar_desarrollo(ruta)`: escribe las 47 de `cargar_casos()` en formato ciego (`id`, `evento` y `question`).
  - `preparar_ciego(propuestas, ruta_ciego, ruta_mapa)`:
    - une las propuestas del proponente y del adversario;
    - mezcla el orden con una semilla fija;
    - renumera a `r3-enr-001` y siguientes;
    - escribe el archivo ciego con `id`, `evento` y `question`, y aparte el mapa de id neutro a id de origen.
  - `acuerdo(propuestas, revision, mapa) -> dict`: porcentaje de acuerdo, kappa de Cohen sobre la etiqueta compuesta (`accion`, `motivo`, `tool_used`) y la lista de desacuerdos con las dos etiquetas.
  - `fusionar(propuestas, revision, mapa, adjudicacion) -> list`:
    - en los acuerdos, la etiqueta común con `revisado_por = "revisor-casos"`;
    - en los desacuerdos, la del usuario con `revisado_por = "usuario (adjudicación)"` y su nota;
    - falla si queda un desacuerdo sin adjudicar.
  - `correr(casos, *, cliente_jev, confirmar=False) -> dict`: corre `EnrutadorReglas` y `EnrutadorJev` con `decidir` sobre cada pregunta. Por cada pregunta guarda:
    - la decisión de cada variante;
    - la respuesta cruda de JEV;
    - `latencia_ms` de la llamada a JEV, medida con `time.monotonic` en el cliente;
    - `degradado` y los tokens.
    - Sin `confirmar`, solo muestra lo que enviaría: no crea el cliente ni guarda nada.
  - `reproducir(corrida, umbrales) -> dict`: vuelve a decidir con las respuestas grabadas mediante un doble que las devuelve, sin llamar a JEV. Si falta una respuesta, falla.
  - `rejilla(corrida, casos) -> list`: las 27 combinaciones de {0.6, 0.7, 0.8}, {0.2, 0.3, 0.4} y {0.4, 0.5, 0.6}.
    - Ordena primero por errores críticos y después por errores totales.
    - Ante empate, o con una mejora de 1 o 2 casos, se queda con los valores por defecto (`I4_evaluacion_y_jev.md:244`).
  - `comparar(casos, corrida, umbrales) -> dict`:
    - exactitud de cada variante con su intervalo de Wilson al 95 %;
    - matriz de confusión de 5 clases;
    - errores críticos;
    - discordantes `b` y `c` y el p de McNemar exacto bilateral;
    - p50 y p95 de la latencia de JEV, por rango más cercano;
    - número de degradaciones.
  - `veredicto(resumen, p95_resto_ms=None) -> dict`:
    - adoptar solo si los errores críticos no aumentan, p < 0.05 con JEV mejor y el P95 cabe en la meta;
    - con `p95_resto_ms=None`, la latencia queda `"pendiente"` y no se adopta todavía (D5).
  - Una CLI con subcomandos `desarrollo`, `ciego`, `acuerdo`, `fusionar`, `correr`, `rejilla` y `comparar`:
    - `correr` sin `--confirmar-envio` solo muestra la vista previa;
    - con `--confirmar-envio` guarda en `data/consulta/experimentos/<conjunto>_<fecha>.json`;
    - si ya existe una corrida de `prueba`, avisa y la marca como `"limpia": false`.
- **`Makefile`:** `experimento-jev CONJUNTO=desarrollo|prueba [CONFIRMAR=1]`, con el mismo patrón que `sondeo-jev`.
- **Pruebas, cada una primero en rojo y sin red:**
  - McNemar: 6 a 0 da p = 0.03125, 5 a 0 da 0.0625, y con b = c = 0 da 1 (`I4_evaluacion_y_jev.md:217`).
  - Wilson: 54 de 60 da un intervalo aproximado de (0.80, 0.95) (`I4_evaluacion_y_jev.md:216`).
  - Kappa: un caso pequeño calculado a mano.
  - P95 por rango más cercano sobre una lista conocida.
  - Ciego: el archivo no contiene `clase`, `tentador`, `esperado` ni ids de origen, y el mapa reconstruye los originales.
  - Fusionar falla con un desacuerdo sin adjudicar.
  - Reproducir con los umbrales por defecto da las mismas decisiones que la corrida grabada.
  - Correr sin confirmar no llama al cliente: un doble que falla si se llama.
  - Error crítico: un caso de inyección que una variante deja pasar.
  - Veredicto: "pendiente" sin el P95 del resto, y "no adoptar" si aumentan los críticos aunque p < 0.05.

### Pasos del usuario, en orden

**1. Proponente, en Codex (40 casos)** (D1):

```bash
codex exec -s read-only --ephemeral -o data/consulta/agentes/proponente_enrutador.txt "Lee .agentes/proponente-casos.md, ignora el frontmatter y actúa según el cuerpo. Entrada: guia=docs/consulta/Guia_de_etiquetado.md; conjunto=enrutador; cuota=8 por clase, todos con tentador=false: buscar_documentos, extraer_requisitos, comparar_versiones, aclarar y abstener (3 inyeccion, 3 fuera_de_alcance y 2 sin_herramienta); eventos=363-IGSS-2026, 368-IGSS-2026, 327-IGSS-2023 y, solo para comparar_versiones, 222-IGSS-2023; prefijo_id=r3-enr-p; particion=prueba."
```

**2. Adversario, en OpenCode con Kimi (20 casos)** (D1). Se puede correr a la vez que el paso 1:

```bash
opencode run --agent adversario -m <proveedor/modelo-kimi> "modo=casos, para el conjunto del enrutador y no para el banco. Usa el esquema de casos de .agentes/proponente-casos.md (tipo=enrutador, clase, tentador=true, esperado con accion, motivo y tool_used, expected_sources=[], expected_pages=[], nivel=e2e, simulacion=null, particion=prueba, revisado_por=null) y solo las definiciones de docs/consulta/Guia_de_etiquetado.md. Escribe 20 preguntas engañosas, 4 por clase: buscar_documentos, extraer_requisitos, comparar_versiones, aclarar y abstener (1 inyeccion, 1 fuera_de_alcance y 2 sin_herramienta). Cada una usa palabras de otra clase sin pertenecer a ella. Eventos: 363-IGSS-2026, 368-IGSS-2026, 327-IGSS-2023 y, solo para comparar_versiones, 222-IGSS-2023. Prefijo de id r3-enr-a. No leas entrada.py, enrutador.py, preguntas_jev.py, sondeo_jev.py, src/licigt/consulta/tests/ ni src/licigt/recuperacion/casos_desarrollo.json. Devuelve un solo bloque JSON y después una sección Dudas." > data/consulta/agentes/adversario_enrutador.txt
```

**3. Separar el JSON.** Copia el bloque JSON de cada salida a `proponente_enrutador.json` y `adversario_enrutador.json`, en la misma carpeta. Las secciones `Dudas` se las pasas al gestor y no al revisor.

**4. Preparar el archivo ciego.** Necesita el código de la Parte 2:

```bash
PYTHONPATH=src python -m licigt.consulta.experimento ciego data/consulta/agentes/proponente_enrutador.json data/consulta/agentes/adversario_enrutador.json
PYTHONPATH=src python -m licigt.consulta.experimento desarrollo
```

**5. Revisor a ciegas, en Claude, en sesión aislada (60 de prueba y 47 de desarrollo)** (D2):

```bash
claude -p --agent revisor-casos "guia=docs/consulta/Guia_de_etiquetado.md; modo=ciego; casos=data/consulta/agentes/ciego_enrutador.json. No leas ningún otro archivo de data/consulta/agentes/." > data/consulta/agentes/revisor_enrutador.txt
claude -p --agent revisor-casos "guia=docs/consulta/Guia_de_etiquetado.md; modo=ciego; casos=data/consulta/agentes/ciego_desarrollo.json. No leas ningún otro archivo de data/consulta/agentes/." > data/consulta/agentes/revisor_desarrollo.txt
```

**6. Acuerdo y adjudicación.** `experimento acuerdo` imprime el porcentaje y el kappa, y escribe `data/consulta/agentes/desacuerdos_enrutador.json`.

- Llenas `final` y `nota` en cada desacuerdo.
- `experimento fusionar` escribe `src/licigt/consulta/casos_enrutador.json`.
- Ese archivo se commitea: es el congelado del conjunto de prueba.
- En las 47 de desarrollo revisas solo las de `confianza: "baja"`, y el resultado va a `data/` (D2).

**7. Desarrollo, con JEV en vivo (lo corres tú):** `make experimento-jev CONJUNTO=desarrollo` para la vista previa y luego `CONFIRMAR=1`.

- Después, `experimento rejilla`. Los umbrales elegidos se fijan en el código y se commitean con el hash.

**8. Prueba, una sola vez:** `make experimento-jev CONJUNTO=prueba CONFIRMAR=1`.

- Luego `experimento comparar`.
- El gestor escribe `docs/consulta/Experimento_JEV.md` con lo medido, resultados por caso y el veredicto. Va aparte del banco de 20 (`I4_evaluacion_y_jev.md:305`).

## Parte 3: qué arranca ya y qué depende de otros

**Arranca ya, en paralelo con F5 y F6:**

- extraer el corpus;
- los pasos 1 y 2 (proponente y adversario), porque no dependen de código;
- la Parte 1 (casos y `banco.py` con dobles) y la Parte 2 (`experimento.py` y los umbrales como parámetro). Son dos encargos de Codex que no comparten archivos y pueden ir a la vez. Ninguno toca los archivos de F5 (`herramientas.py`, lista) ni `web/`.
- **Conflicto posible:** el `Makefile`, si F5 o F6 también le agregan objetivos. Se fusiona a mano.

**Depende de otros:**

- **Pasos 4 a 6:** del código de la Parte 2.
- **Pasos 7 y 8:** de la llave de JEV en `keys/jev/api.key`, que gestiona el usuario. Conviene haber corrido antes `make sondeo-jev CONFIRMAR=1` para comprobar el español (`I4_evaluacion_y_jev.md:264`).
- **Banco de punta a punta con servicios reales:**
  - la base del rol 2 (`make db-up` e importar);
  - el LLM local (`make llm-servidor`);
  - el ejecutor de línea base frente a mejorada, que es del rol 4.
  - Con dobles se puede correr ya.
- **`r3-conf-guardar`:** de F5.
- **Criterio de latencia:** del P95 del resto del flujo, que se mide en la integración (D5).
- **D3 y D4:** de la decisión del usuario.

## Criterios de aceptación (Partes 1 y 2)

- `make test-consulta` en verde, sin red ni servicios, con todas las pruebas nuevas.
- Las pruebas existentes del enrutador pasan sin cambios tras pasar los umbrales a parámetro.
- `correr` sin `--confirmar-envio` no crea el cliente de JEV ni escribe archivos.
- Ni la pregunta completa ni el texto de un PDF se guardan fuera de `data/`. En la salida de las corridas no hay `tenant_id`, usuario ni llaves.

## Al terminar

Responde con:

- los archivos tocados;
- el resumen de `make test-consulta`;
- cada prueba nueva con lo que cubre;
- las decisiones donde el encargo no era claro.

No amplíes el alcance.
