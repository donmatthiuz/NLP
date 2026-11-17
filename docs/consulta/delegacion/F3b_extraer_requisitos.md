# Encargo F3b: `extraer_requisitos` con fechas verificadas

Para Codex u OpenCode. Rama `rol/consulta`. Abre el agente con `make codex` o `make opencode`. El gestor auditará el resultado; no commitees.

Lee primero:

- [`AGENTS.md`](../../../AGENTS.md);
- [`Contratos.md`](../Contratos.md);
- [`JEV.md`](../JEV.md), en especial el cookbook de fechas y los puntos débiles;
- la skill `.skills/typesafe-ai/SKILL.md`;
- `src/licigt/consulta/herramientas.py`, `jev.py`, `preguntas_jev.py` y `esquemas.py`.

**Se lanza después de C1**, porque las dos tocan `herramientas.py`. En paralelo otro agente corrige los diagramas (`docs/arquitectura/`, `scripts/`): no los toques.

## Objetivo

La tercera herramienta de solo lectura. Reúne la evidencia de requisitos por categoría y la del cronograma, encuentra las fechas literales y, si hay JEV, le pide que diga a qué actividad corresponde cada una. El código normaliza, compara y decide la revisión humana. No redacta requisitos ni respuesta: eso es F4. La lista de verificación es F5.

**Por qué:**

- `Anteproyecto.md:335`: la herramienta extrae "requisitos, fechas y documentación de la oferta", con los parámetros `evento_id` y `categoria?`.
- `Anteproyecto.md:338`: la extracción de fechas se hace aquí, "con comprobaciones específicas de actividad y plazo".
- `Anteproyecto.md:326`: encontrar una fecha "no es prueba suficiente".
- `Plan_rol_3.md`, F3b, y el cookbook de fechas de JEV: el código encuentra candidatas, JEV elige y el código valida.

**Hallazgo que justifica la comparación en código:**

- La portada de las bases del 222 (`03791a3471c04c0f9cc260814564756e:00001`) dice que la recepción es el 31 de julio de 2023; la modificación 1 (`d41480e5b0ce4c16bf18f66225ada2dc:00009`) dice el 06 de octubre de 2023.
- La alerta `posible_conflicto` del rol 2 no lo marca, porque la portada no está bajo el numeral 2.2.

## Decisiones tomadas (no las cambies)

1. **Evidencia:**
   - una consulta fija de cronograma se ejecuta **siempre**, además de la categoría pedida, o de las cuatro si no se pide ninguna;
   - no se añade un parámetro de pregunta: la firma del anteproyecto no cambia;
   - las consultas fijas viven en un solo lugar.
2. **Sin `RequisitoCandidato`:** la herramienta entrega los fragmentos y las fechas; los requisitos los redacta F4 con citas.
3. **Dónde vive:**
   - la función y el campo nuevo van en `herramientas.py`, junto a las otras dos, reutilizando `_fallo` e `_interpretar` y el mismo `ResultadoHerramienta`;
   - la lógica pura de fechas (regex, normalización y modelo `FechaCandidata`) va en `requisitos.py`, que no importa `herramientas.py`, para que no haya ciclo;
   - el texto de las preguntas a JEV, sus opciones y sus umbrales van en `preguntas_jev.py`.
4. **Presupuesto:** la herramienta no consume el `Presupuesto`; cuenta como una invocación, y la descuenta quien la llama (`Anteproyecto.md:342`). Precedente: `comparar_versiones` ya hace dos búsquedas internas.
5. **Formato de fecha:** solo con el mes en español ("31 de julio de 2023"). El formato `dd/mm/aaaa` aparece 0 veces en los 1003 fragmentos del corpus: no se implementa.

## Archivos

| Archivo | Qué |
|---|---|
| `src/licigt/consulta/requisitos.py` | Crear: consultas fijas, regex de fechas, normalización y `FechaCandidata` |
| `src/licigt/consulta/herramientas.py` | Añadir `extraer_requisitos` y el campo `fechas` en `ResultadoHerramienta` |
| `src/licigt/consulta/preguntas_jev.py` | Añadir las actividades, el constructor de preguntas de fechas y el límite de candidatas |
| `src/licigt/consulta/tests/test_requisitos.py` | Crear |

No toques nada más. Las pruebas existentes de `test_herramientas.py` deben seguir en verde sin editarlas.

## 1. `requisitos.py` (sin estado, sin red)

### Consultas fijas

`CONSULTAS_POR_CATEGORIA`, con las cuatro claves de `Categoria` (`esquemas.py`), y `CONSULTA_CRONOGRAMA`. Son valores iniciales, a afinar con el banco:

- administrativa: "requisitos administrativos y documentos que debe contener la plica";
- legal: "requisitos legales, constancias, declaraciones juradas y solvencias";
- técnica: "especificaciones técnicas del medicamento, presentación y concentración";
- financiera: "requisitos financieros, garantías, fianzas y estados financieros";
- cronograma: "cronograma de actividades, fechas y plazos del evento".

### Fechas

- Una regex sobre el texto normalizado (minúsculas y sin tildes, como `entrada.normalizar`): día de 1 o 2 cifras, `de`, el mes en español (incluido "setiembre") y `de` o `del` con el año de 4 cifras.
- `encontrar_fechas(texto) -> list[tuple[str, date, int]]`: el literal tal como aparece en el texto original, la fecha y la posición. Las fechas imposibles (30 de febrero) se descartan con `datetime.date`, sin lanzar.

### `FechaCandidata`

Inmutable, con `extra="forbid"`:

- `chunk_id`, `doc_id`, `tipo_documento`, `pagina`;
- `literal`: el texto de la fecha, no el fragmento;
- `fecha: date`;
- `actividad: str | None`;
- `estado: Literal["verificada", "no_verificada", "fuera_del_cronograma"]`;
- `prob_actividad` y `prob_respaldo`: `Probabilidad | None` (de `jev.py`).

## 2. Preguntas de JEV (`preguntas_jev.py`)

- `ACTIVIDADES_CRONOGRAMA`: un diccionario de clave a descripción con las actividades del numeral 2.2 de las bases del IGSS:
  - `adquirir_documentos`, `induccion`, `solicitud_aclaraciones`, `respuesta_aclaraciones`, `formulario_electronico`, `recepcion_ofertas`, `apertura_plicas` y `adjudicacion`;
  - más `ninguna`, para las fechas que no son del cronograma, como la solvencia patronal "al 31 de mayo de 2023";
  - las descripciones salen del texto real del 222.
- `preguntas_fechas(ids) -> dict`: para cada candidata `cN`, un `Choice` `actividad_cN` con esas opciones y un `Noul` compañero `respaldo_cN`: "¿El pasaje dice expresamente esta fecha para una actividad del cronograma?".
  - Las instrucciones apuntan a `candidatas.cN` del estado. Comprueba en la skill o en la documentación viva cómo se referencian las rutas del estado.
- `MAX_CANDIDATAS_JEV = 20`, para acotar el costo y el límite de tokens. Las candidatas que sobran quedan `no_verificada`, con la advertencia `candidatas_sin_verificar: <n>`.
- Reutiliza `NOUL_SI`, `NOUL_NO` y `CHOICE_MIN`; no inventes umbrales nuevos.

## 3. `extraer_requisitos(ctx, params: ExtraerRequisitosParams, recuperador, cliente_jev: ClienteJev | None = None)` en `herramientas.py`

### 1. Evidencia

- Llama a `recuperador.buscar(ctx, params.evento_id, consulta, variante="mejorada", k=5)`:
  - con la categoría pedida y con `CONSULTA_CRONOGRAMA`;
  - o con las cuatro categorías y `CONSULTA_CRONOGRAMA` si `categoria` es nula.
- Cualquier excepción da `falla_recuperacion` y un `ValidationError` da `contrato_invalido`, con `_fallo`, igual que `comparar_versiones`.
- Junta los fragmentos sin repetir `chunk_id`, en el orden en que llegan, y las alertas sin repetir `(tipo, doc_id)`. Las alertas se interpretan con `_interpretar`.
- `abstener` es verdadero si ninguna búsqueda fue `suficiente` o si no queda ningún fragmento.

### 2. Candidatas

`encontrar_fechas` sobre cada fragmento. Cada fecha es una `FechaCandidata`, con `estado="no_verificada"` hasta que JEV diga otra cosa.

### 3. JEV, si hay `cliente_jev` y al menos una candidata

- **Una sola solicitud** con todas las candidatas (hasta el máximo). El estado es `{"candidatas": {"cN": {"seccion": ..., "pasaje": ..., "fecha": literal}}}`:
  - `pasaje` es una ventana de unos 300 caracteres alrededor de la fecha, dentro del fragmento;
  - `seccion` va porque la segmentación a veces deja el nombre de la actividad en el fragmento anterior (`…6e:00040` y `…6e:00041`);
  - solo texto de documentos públicos: nunca `ctx`, `tenant_id` ni datos del usuario.
- **Reglas en código:**
  - `ninguna` con la probabilidad del `Choice` ≥ `CHOICE_MIN`: queda `fuera_del_cronograma`;
  - otra actividad, con la probabilidad ≥ `CHOICE_MIN` y el respaldo ≥ `NOUL_SI`: queda `verificada`;
  - en otro caso, `no_verificada`, y `needs_human_review` pasa a verdadero; la confianza es la mínima entre las dos partes;
  - siempre guarda `prob_actividad` y `prob_respaldo`.
- **Si JEV falla** (`FallaJev`, `TimeoutError` o `ValidationError`): todas quedan `no_verificada`, con la advertencia `jev_no_disponible`. Una falla nunca cuenta como "no".

### 4. Sin JEV

- Todas quedan `no_verificada`, con la advertencia `fechas_no_verificadas: <n>`.
- `needs_human_review` sale solo de las alertas.

### 5. Comparación en código

- Si una misma actividad tiene fechas `verificada` distintas (en el mismo documento o entre documentos): `needs_human_review` verdadero y la advertencia `fechas_distintas: <actividad>`.
- Se conservan todas las fuentes y nunca se elige la vigente (`Anteproyecto.md:328`).

### 6. Resultado

`ResultadoHerramienta` con `herramienta="extraer_requisitos"` y el nuevo campo `fechas: list[FechaCandidata] = []`.

Las advertencias son códigos cortos sin texto del PDF. `literal` es un dato de la evidencia, no un log.

## Pruebas (primero, sin red, SDK ni Postgres)

**Datos de prueba:**

- Construye los fixtures con textos cortos copiados de `entregables/recuperacion/empresa_demo.zip` (`chunks.jsonl`): `03791a3471c04c0f9cc260814564756e:00001`, `:00040`, `:00041`, `:00047` y `:00063`, y `d41480e5b0ce4c16bf18f66225ada2dc:00009` y `:00013`.
- Recorta cada texto a lo que necesita la prueba.
- Usa un recuperador falso con la forma exacta del rol 2, como en `test_herramientas.py`, y un `ClienteJev` falso.

**Casos mínimos:**

- **Regex:**
  - "31 de julio de 2023", "06 de octubre de 2023", "1 de setiembre del 2023", "31 DE JULIO DE 2023" y "día 31 de julio de 2023";
  - "30 de febrero de 2023" se descarta;
  - "julio de 2023", sin día, no es una candidata.
- **Llamadas:**
  - sin categoría: 5 llamadas a `buscar`, con las consultas fijas, `variante="mejorada"` y `k=5`;
  - con categoría: 2 llamadas;
  - el `ctx` llega sin cambios.
- **Repetidos:** un fragmento que vuelve en dos consultas aparece una sola vez.
- **Sin JEV:** las fechas quedan `no_verificada`, con la advertencia `fechas_no_verificadas`, y no hay revisión humana si no hay alertas.
- **Caso 222 con un JEV falso:**
  - la recepción del 31 de julio (bases) y la del 06 de octubre (modificación) dan `needs_human_review` verdadero y `fechas_distintas: recepcion_ofertas`, con las dos fechas presentes;
  - la solvencia patronal queda `fuera_del_cronograma`.
- **Confianza baja** (`Choice` < 0.5 o respaldo < 0.7): `no_verificada` y revisión humana.
- **Falla de JEV:** degrada a `no_verificada` con `jev_no_disponible`.
- **Envío a JEV:**
  - una sola llamada por invocación;
  - el estado no contiene `ctx`, `tenant_id` ni ningún objeto del contexto;
  - con más de `MAX_CANDIDATAS_JEV` candidatas, las sobrantes quedan sin enviar y llevan su advertencia.
- **Errores y abstención:**
  - una excepción en la segunda búsqueda da `falla_recuperacion`;
  - un contrato inválido da `contrato_invalido`;
  - si todas las búsquedas son insuficientes, abstiene.
- **Importaciones:** importar `herramientas` y `requisitos` no carga `typesafe_sdk` ni `licigt.recuperacion` (revisa `sys.modules` en un subproceso).

## Criterios de aceptación

- `make test-consulta` en verde, sin servicios.
- Todo el texto y los umbrales de JEV solo en `preguntas_jev.py`; las consultas fijas solo en `requisitos.py`.
- Nombres en español, salvo los campos del contrato del curso.

## Al terminar

Responde con:

- los archivos tocados;
- el resumen final de `make test-consulta`;
- la forma exacta del estado y de las preguntas que se enviarían a JEV para el caso 222, con el texto recortado;
- las decisiones que tomaste donde el encargo no era claro.

No amplíes el alcance.
