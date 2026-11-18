# Encargo F4: generación con citas, validador y orquestación

Para Codex u OpenCode. Rama `rol/consulta`. Abre el agente con `make codex` o `make opencode`. El gestor auditará el resultado; no commitees.

Lee primero:

- [`AGENTS.md`](../../../AGENTS.md), [`DESIGN.md`](../../../DESIGN.md) (LLM generador) y [`Contratos.md`](../Contratos.md) (rol 4 y salida);
- [I1](../investigacion/I1_generacion_y_citas.md), completo: es el diseño de este encargo;
- [I2](../investigacion/I2_llm_local.md), secciones 3 y 4;
- `src/licigt/consulta/esquemas.py`, `lectura.py`, `herramientas.py`, `entrada.py`, `enrutador.py`, `decision.py`, `presupuesto.py`, `config.py` y `jev.py` (para imitar su estilo de configuración y de fallas).

**En paralelo** otros agentes trabajan en:

- `herramientas.py`, `tests/test_herramientas.py`, el `Makefile`, `.env.example` y el README de consulta (C1);
- `docs/arquitectura/` y `scripts/` (diagramas).

No toques esos archivos.

## Objetivo

Cerrar el flujo de una consulta de punta a punta, sin servicios en las pruebas:

1. pregunta;
2. enrutador y decisión (F2);
3. herramienta (F3);
4. prompt aumentado y LLM;
5. validador determinista de citas, con una regeneración;
6. `RespuestaEstructurada` y auditoría.

El modelo concreto no se ejecuta en este encargo. Queda un cliente agnóstico con la API compatible con OpenAI y un interruptor entre lo local y OpenAI.

## Decisiones tomadas (no las cambies)

Salen de I1 y de las decisiones del 16 de noviembre; cada punto tiene su respaldo en I1.

- **Prompt:**
  - el mensaje de sistema lleva las reglas;
  - el mensaje de usuario lleva `<documentos>`, con cada `<fragmento id="F1" tipo version_oficial pagina seccion>` y su texto tal cual, y al final `<pregunta>`;
  - se conserva el orden de la herramienta y se neutralizan las etiquetas falsas dentro del texto (I1, sección 1).
- **Citas:**
  - el modelo devuelve `SalidaModelo` (`abstener`, `afirmaciones[]` con `texto` y `citas[]` de `{fragmento: Fn, cita}`, y `revision_humana`);
  - los alias van como `enum` en el esquema;
  - el código traduce el alias a `chunk_id` y arma la `Fuente` con `fuente_desde_fragmento`;
  - `answer` lo compone el código con marcadores `[n]` (I1, sección 2).
- **Validador puro:** los 7 pasos de I1, sección 3, en ese orden y con esos códigos de error. La cita es exacta tras normalizar, no aproximada, con un mínimo de 10 caracteres.
- **Regeneración:** una, con la salida anterior y los errores por código, sin texto del PDF. Si falla otra vez, o si se agota el presupuesto, abstención con `TEXTO_ABSTENCION` y la advertencia `citas_no_validas` (I1, sección 4).
- **`needs_human_review`:** es el O lógico de la herramienta y de `revision_humana`; el modelo solo puede subirlo (I1, sección 5).
- **JEV de fidelidad:** no entra.
- **Falla del generador** (servicio caído o tiempo agotado): `abstained=true`, la advertencia `generador_no_disponible` y el código en el `error` de la auditoría.
- **Auditoría:**
  - un evento por solicitud, siempre, en un `finally`, con los campos de `Contratos.md` (rol 4);
  - además, como campos opcionales, `chunk_ids_citados`, `modelo_generador` y `version_prompt`;
  - nunca la pregunta, texto de fragmentos, citas ni la salida del modelo;
  - una excepción de `auditar` no cambia la respuesta.
- **Tope de evidencia:** sin tope de fragmentos mientras quepan en un presupuesto de caracteres configurable (36000 por defecto). Si no caben, se conservan los primeros en el orden de la herramienta y siempre los del conflicto, con la advertencia `evidencia_recortada`.
- **Sin clase `EstadoConsulta`:** el estado se pasa explícito entre funciones (I1, sección 7).

## Archivos

| Archivo | Qué |
|---|---|
| `src/licigt/consulta/generacion.py` | Crear: `SalidaModelo`, `construir_prompt`, `esquema_salida(alias)`, `VERSION_PROMPT` y el Protocol `ClienteGenerador` |
| `src/licigt/consulta/validacion.py` | Crear: `normalizar_cita` y `validar(...)` puro, con errores por código |
| `src/licigt/consulta/orquestador.py` | Crear: `consultar(...)` |
| `src/licigt/consulta/llm.py` | Crear: `ClienteGeneradorOpenAI` y `FallaGenerador` |
| `src/licigt/consulta/config.py` | Ampliar con la configuración del LLM, sin romper lo de JEV |
| `src/licigt/consulta/requirements.txt` | Añadir `openai` (versión mínima, sin fijar la exacta) |
| `src/licigt/consulta/tests/test_generacion.py`, `test_validacion.py`, `test_orquestador.py` y `test_llm.py` | Crear |

Nada más.

## 1. Cliente del LLM (`llm.py`) y configuración

**`ClienteGenerador`** (en `generacion.py`): `generar(mensajes: list[dict], esquema: dict) -> str`. Devuelve el texto crudo; el parseo estricto es nuestro.

**`ClienteGeneradorOpenAI`:**

- usa el SDK `openai` con `base_url` y lo importa dentro del constructor, como `jev.py`, para que las pruebas corran sin el SDK;
- consulta con Context7 la firma actual de `chat.completions.create`, `response_format` con `json_schema` y `strict`, `seed`, `timeout` y las excepciones (`APITimeoutError`, `APIConnectionError`, `APIStatusError`).

**Interruptor `LICIGT_LLM`, `local` por defecto u `openai`, con perfiles:**

- **`local`:**
  - URL `http://127.0.0.1:8080/v1`, modelo `qwen3.5-9b` (alias que fijará el servidor) y sin llave; el SDK exige una cadena, así que se pasa una constante no secreta;
  - envía `chat_template_kwargs: {"enable_thinking": false}` por el cuerpo extra.
- **`openai`:**
  - URL `https://api.openai.com/v1`, modelo `gpt-4.1-mini` y llave leída del archivo `LICIGT_LLM_API_KEY_FILE` (por defecto `keys/llm/openai.key`), igual que JEV;
  - comprueba en la documentación de OpenAI que el modelo acepta `temperature` y `seed`, porque los modelos con razonamiento (familia GPT-5) no aceptan temperatura. Si `gpt-4.1-mini` no está disponible, propón otro sin razonamiento y repórtalo; no lo cambies en silencio.
- **Variables que sobreescriben cualquier perfil:** `LICIGT_LLM_URL`, `LICIGT_LLM_MODELO`, `LICIGT_LLM_API_KEY_FILE`, `LICIGT_LLM_TIEMPO_ESPERA` (20 s), `LICIGT_LLM_MAX_TOKENS` (1024), `LICIGT_LLM_SEMILLA` (42) y `LICIGT_LLM_MAX_CARACTERES_EVIDENCIA` (36000). La temperatura es siempre 0.

**Salida estructurada:**

- `response_format={"type": "json_schema", "json_schema": {"name": "salida_licigt", "schema": esquema, "strict": True}}`;
- si el modo estricto de OpenAI no admite alguna palabra clave del esquema de Pydantic, quítala solo en lo que se envía (el validador local la sigue aplicando) y documenta cuál;
- el esquema también va como texto en el prompt.

**Errores:**

- `FallaGenerador(codigo)` con `tiempo_agotado`, `servicio_no_disponible`, `respuesta_vacia`, `clave_no_disponible`, `sdk_no_disponible` y `api`;
- nunca se propaga el texto del error remoto ni se registra la llave.

**Metadatos:** expone el modelo y el perfil para la auditoría (`modelo_generador`).

**Datos que salen:**

- con el perfil `openai` solo salen la pregunta y los fragmentos;
- `construir_prompt` nunca recibe `ctx`, así que no puede incluir `tenant_id` ni `usuario`. Pruébalo.

## 2. `consultar` (`orquestador.py`)

```python
consultar(ctx, evento_id, pregunta, *, enrutador, recuperador, generador,
          cliente_jev=None, auditar=lambda evento: None) -> RespuestaEstructurada
```

Sigue los 9 pasos de I1, sección 7:

- un `Presupuesto` por solicitud;
- `decidir` de F2;
- aclarar o abstener sin herramienta ni LLM;
- `usar_llamada()` y los parámetros validados;
- la herramienta (`extraer_requisitos` recibe `cliente_jev`);
- si la herramienta abstiene, se responde sin LLM;
- el prompt, `generar`, `validar` y una regeneración;
- la respuesta;
- `auditar` en un `finally`.

El `evento_id` llega por parámetro, nunca de la pregunta.

**Si sale `comparar_versiones`:** la evidencia es la unión sin repetir `chunk_id` de los fragmentos de `documentos` y los de `buscar`, agrupados por documento: primero las bases, luego aclaraciones y modificaciones.

**Si sale `extraer_requisitos`:** añade al prompt, después de `<documentos>`, un bloque `<fechas>` con las `FechaCandidata` (alias del fragmento, literal, actividad y estado), para que el modelo las use con su cita. Las fechas `no_verificada` se marcan así; el modelo no las presenta como confirmadas.

## 3. Pruebas (primero, sin red, SDK, GPU ni Postgres)

Las de I1, sección 9, completas, más estas:

- **`test_llm.py`:**
  - perfiles `local` y `openai` y sobreescritura por variables;
  - temperatura 0, semilla y `response_format` en la llamada (con un SDK falso inyectado);
  - las seis fallas mapeadas a su código, sin el texto remoto;
  - si falta la llave con `openai`, `clave_no_disponible`;
  - `local` no lee ninguna llave.
- **Envío:** con el perfil `openai`, lo enviado no contiene `tenant_id`, `usuario` ni el `repr` del contexto.
- **Recorte de evidencia:** con una evidencia que pasa el presupuesto, se conservan los fragmentos del conflicto y aparece la advertencia.
- **Caso 222 de punta a punta**, con dobles:
  - la recepción da `needs_human_review` verdadero, `coverage_status` parcial y dos fuentes;
  - una salida del modelo que cita "30 de julio" se rechaza y regenera.
- **Importaciones:** importar cualquier módulo nuevo no carga `openai`, `typesafe_sdk` ni `licigt.recuperacion` (revisa `sys.modules` en un subproceso).

Los fixtures de texto se recortan de `entregables/recuperacion/empresa_demo.zip` (`chunks.jsonl`), incluido `d41480e5b0ce4c16bf18f66225ada2dc:00009`, que está a dos columnas.

## Criterios de aceptación

- `make test-consulta` en verde, sin servicios.
- Ninguna ruta lanza una excepción hacia afuera: toda salida es una `RespuestaEstructurada` válida.
- Sin texto de PDF, pregunta ni llave en la auditoría, las advertencias ni los errores.
- Nombres en español, salvo los campos del contrato del curso y los parámetros de la API.

## Al terminar

Responde con:

- los archivos tocados;
- el resumen final de `make test-consulta`;
- el prompt completo generado para el caso 222, con los textos recortados;
- el JSON Schema enviado en cada perfil, indicando qué palabras clave quitaste para OpenAI;
- qué verificaste en la documentación de OpenAI sobre el modelo;
- las decisiones donde el encargo no era claro.

No amplíes el alcance.
