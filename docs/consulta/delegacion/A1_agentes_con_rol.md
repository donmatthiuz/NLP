# Encargo A1: agentes con rol (proponente, revisor y adversario)

Para Codex u OpenCode. Rama `rol/consulta`. El gestor auditará el resultado; no commitees.

Lee primero:

- [`AGENTS.md`](../../../AGENTS.md);
- [I5](../investigacion/I5_agentes_agnosticos.md), completo: tiene el diseño y los tres archivos propuestos en la sección 5;
- [I4](../investigacion/I4_evaluacion_y_jev.md), secciones de casos, conjunto etiquetado y formato JSON.

**En paralelo** otros agentes trabajan en `src/licigt/consulta/`, el `Makefile`, `.env.example`, `scripts/` y `docs/arquitectura/`: no los toques.

## Objetivo

Tres agentes reutilizables desde una sola fuente versionada, para:

- redactar los casos de prueba etiquetados;
- revisarlos de forma independiente;
- atacar el sistema y refutar entregas de código.

**Por qué:**

- Decisión del 16 de noviembre: un agente propone, otro revisa y el usuario adjudica. El adversario sirve para los casos y para las auditorías.
- I5 resolvió el formato común y la independencia del revisor.

## Decisiones tomadas (no las cambies)

- **Fuente única** en `.agentes/<nombre>.md`, con el frontmatter común de I5: `name`, `description`, `tools`, `mode: all` y `permissions`, sin `model`.
- **Enlaces simbólicos versionados**, relativos como los de `skills`:
  - `.claude/agents` hacia `../.agentes`;
  - `.opencode/agents` hacia `../.agentes`.
  - No se crea `.agents/agents` (Kimi se usa dentro de OpenCode con la suscripción OpenCode Go), ni archivos TOML de Codex.
- **Asignación** (va en la descripción de cada agente y en `AGENTS.md`):
  - el proponente en Codex, con `codex exec -s read-only --ephemeral` y el prompt "lee `.agentes/proponente-casos.md` y …";
  - el revisor en Claude, en una sesión aislada (`claude -p --agent revisor-casos`), con otra familia de modelos que el proponente;
  - el adversario en OpenCode con Kimi, distinto del modelo que implementó el código auditado.
- **Adjudicación:** el usuario resuelve los desacuerdos, y eso cuenta como segunda revisión declarada (`Cambios_pendientes.md`).
- **Solo lectura:** ninguno edita código, lee `keys/`, llama a APIs externas ni ejecuta el sondeo de JEV. Sus salidas son JSON que el usuario guarda.

## Archivos

| Archivo | Qué |
|---|---|
| `.agentes/proponente-casos.md` | Crear desde I5, sección 5 |
| `.agentes/revisor-casos.md` | Crear desde I5, sección 5 |
| `.agentes/adversario.md` | Crear desde I5, sección 5, con el modo de auditoría |
| `.claude/agents` y `.opencode/agents` | Enlaces simbólicos a `../.agentes` |
| `docs/consulta/Guia_de_etiquetado.md` | Crear |
| `AGENTS.md` | Sección corta "Agentes con rol" |

Nada más.

## 1. Los tres agentes

Toma los archivos propuestos en I5 y ajústalos:

- **Rutas reales:** las del repo (`docs/consulta/Guia_de_etiquetado.md`, `src/licigt/recuperacion/casos_desarrollo.json` y `data/consulta/corpus/chunks.jsonl`).
- **El corpus se extrae** con `unzip -o entregables/recuperacion/empresa_demo.zip chunks.jsonl inventario.json -d data/consulta/corpus`. Comprueba antes, con `unzip -l`, las rutas internas del ZIP. `data/` está ignorado por Git. La instrucción va en cada agente que lo lea; no añadas objetivos al `Makefile`.
- **Proponente:**
  - no lee la implementación del enrutador (`entrada.py`, `enrutador.py` y `preguntas_jev.py`) ni las 47 preguntas del sondeo (`sondeo_jev.py` y `casos_desarrollo.json`), para no sesgarse;
  - sí lee la guía de etiquetado y el corpus.
- **Revisor:**
  - recibe solo las preguntas y la guía, sin las etiquetas ni el razonamiento del proponente;
  - etiqueta a ciegas y después se compara.
- **Adversario:**
  - tiene dos modos: casos de ataque, con el formato de la sección 10 del curso y el catálogo de I5, y auditoría de una entrega;
  - en auditoría recibe el encargo y la ruta de los archivos, y devuelve JSON con el veredicto `REFUTADO` o `NO_REFUTADO`, los hallazgos con archivo y línea y cómo reproducirlos.
- **Formatos de salida:** JSON compatible con el esquema de casos de I4 (campos del curso más `evento`, `tipo`, `esperado`, `nivel`, `simulacion` y `particion`).

## 2. `docs/consulta/Guia_de_etiquetado.md`

La guía es lo que comparten el proponente, el revisor y el usuario. Sale de I4 y de las reglas actuales; no inventes clases nuevas.

- **Clases del enrutador** y cómo decidir cada una, con dos ejemplos por clase escritos para la guía (no copiados de `casos_desarrollo.json`):
  - `buscar_documentos`, `extraer_requisitos` y `comparar_versiones`;
  - aclarar (fecha, plazo u hora sin actividad);
  - abstener por fuera de alcance (los temas prohibidos del anteproyecto, sección 6), por inyección o por falta de herramienta.
- **Casos frontera** y su regla:
  - "¿qué fecha está vigente?" va a comparar;
  - "¿cómo se presenta la oferta?" es una consulta, no una acción;
  - "el medicamento" es concreto.
- **Etiquetas de fechas para F3b:** las actividades de `preguntas_jev.py` (`ACTIVIDADES_CRONOGRAMA`), listadas por clave y descripción.
- **Partición** desarrollo y prueba según I4. Una pregunta de prueba nunca se usa para ajustar.
- **Acuerdo:** porcentaje y kappa de Cohen, y cómo registra el usuario la adjudicación.
- Al inicio, el enlace a I4 y a la sección 12 del anteproyecto.

Markdown sin emojis, listas con `-` y un solo `#`.

## 3. `AGENTS.md`

Una sección corta "Agentes con rol", de 8 a 12 líneas, que diga:

- dónde están (`.agentes/`) y que `.claude/agents` y `.opencode/agents` apuntan ahí;
- qué hace cada uno y con qué herramienta y modelo se corre;
- que son de solo lectura;
- que el revisor no ve las etiquetas del proponente.

No cambies nada más de `AGENTS.md`.

## Verificación

- `ls -la .claude/agents .opencode/agents`: los enlaces resuelven y listan los tres archivos.
- El frontmatter de cada archivo es YAML válido (pruébalo con Python y `yaml.safe_load` si está disponible, o con un parseo simple).
- `make test-consulta` sigue en verde.
- No ejecutes los agentes.

## Al terminar

Responde con:

- los archivos y enlaces creados;
- la salida de la verificación;
- las diferencias entre lo que proponía I5 y lo que escribiste, con el porqué;
- las decisiones donde el encargo no era claro.

No amplíes el alcance.
