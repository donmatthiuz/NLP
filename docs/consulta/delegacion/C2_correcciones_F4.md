# Encargo C2: correcciones de F4 tras la auditoría adversaria

Para Codex u OpenCode. Rama `rol/consulta`. Abre el agente con `make codex` o `make opencode`. El gestor auditará el resultado, y el agente `adversario` volverá a intentar refutarlo; no commitees.

Lee primero:

- [`AGENTS.md`](../../../AGENTS.md);
- el encargo [F4](F4_generacion_y_orquestacion.md);
- [I1](../investigacion/I1_generacion_y_citas.md), secciones 1 a 3;
- `src/licigt/consulta/generacion.py`, `validacion.py`, `orquestador.py`, `llm.py` y `config.py`, con sus pruebas.

**En paralelo** otro agente trabaja en `docs/arquitectura/diagramas/` y `scripts/exportar_diagramas.sh`: no los toques.

## Origen

El agente adversario (`.agentes/adversario.md`) refutó F4 con hallazgos reproducidos. El gestor confirmó A1 y A2:

- **A1:** "Las ofertas se reciben el 31 de agosto de 2023" se publica citando un fragmento que dice "31 de julio de 2023".
- **A2:** `_neutralizar` hace una sola pasada, y `ok<<fragmento/fragmento>` produce un `</fragmento>` real dentro del prompt.

La regla rota es la central del proyecto: toda afirmación documental con cita verificada, y los fragmentos como datos no confiables.

## Archivos

Solo `generacion.py`, `validacion.py`, `orquestador.py`, `llm.py`, `config.py` y sus pruebas (`test_generacion.py`, `test_validacion.py`, `test_orquestador.py` y `test_llm.py`). Nada más.

## Correcciones (cada una con su prueba en rojo primero)

### A1 (alta): los datos de la afirmación se comparan con lo citado, no con el fragmento entero

- **Qué comprueba el paso 5 de `validar`:** cada dato sensible de `afirmacion.texto` debe aparecer en la **unión de sus citas normalizadas**, no en el fragmento completo. Así el modelo tiene que citar el tramo que contiene el dato.
- **Datos sensibles:**
  - números con sus separadores internos (`1,000.00`, `0.5`, `01/02/2024`), comparados como el token completo tras normalizar;
  - los nombres de mes en español, incluido "setiembre";
  - las cifras con ceros a la izquierda siguen equivaliendo ("06" y "6").
- **Normalización:** aplica `unicodedata.normalize("NFKC", …)` antes de buscar dígitos, para que "３０" cuente como "30". Hazlo dentro de `normalizar_cita`, y no cambies `entrada.normalizar`.
- **Código de error:** `dato_sin_respaldo` reemplaza a `numero_sin_respaldo`. Actualiza las referencias y las pruebas.
- **Fuera de alcance:** las cifras escritas con letras ("treinta"). Déjalo como limitación en un comentario de una línea; queda como mejora en I1.
- **Pruebas:**
  - deben rechazarse el mes distinto, `Q1,000,000.00` frente a `Q1,000.00`, `5%` frente a `0.5%`, `01/02/2024` frente a `02/01/2024`, "３０" frente a un fragmento que dice 31, y "30 de julio" cuando el 30 solo está en otro tramo del fragmento ("pago en 30 días") y no en la cita;
  - debe aceptarse "6 de octubre" cuando la cita dice "06 de octubre".

### A2 (alta): delimitación del prompt a prueba de reconstrucción

- **Cambio:** reemplaza `_neutralizar` por un escape que no se pueda reconstruir: en todo texto no confiable que entra al prompt (fragmentos, pregunta, literales de fechas), cambia `<` por `‹` y `>` por `›`.
  - El corpus no contiene `<` ni `>` (I1, hallazgos del corpus), así que no afecta las citas reales.
  - La validación sigue comparando contra el texto efectivamente enviado.
- **Pruebas:**
  - `ok<<fragmento/fragmento></<documentos/documentos>`, `<<pregunta/pregunta>` y variantes con espacios o mayúsculas no dejan ningún `<` ni `>` de origen no confiable dentro del prompt;
  - el prompt tiene exactamente una apertura y un cierre de `<documentos>` y de `<pregunta>`, y uno por fragmento.

### A3 (media): citas de relleno y afirmaciones compuestas

- **Cita mínima:** además de los 10 caracteres, la cita debe tener al menos 10 caracteres alfanuméricos tras normalizar (`cita_corta`). Una línea de puntos no respalda nada.
- **Una afirmación por línea:** `afirmacion.texto` no puede contener saltos de línea ni marcadores con la forma `[n]` (`texto_invalido`); así no se cuelan frases sin cita en `answer`.
- **Vigencia:** si una afirmación contiene "vigente", "vigencia", "prevalece", "sustituye" o "deja sin efecto", `needs_human_review` se vuelve verdadero. El sistema nunca decide la vigencia (`AGENTS.md`). Solo escala; no rechaza.
- **Sin solapamiento léxico entre afirmación y cita:** la fidelidad semántica la revisa una persona (I1, sección 3).
- **Pruebas:** cada uno de los tres casos.

### A4 (media): el tope de evidencia se aplica de verdad

- **Qué se protege:**
  - con conflicto, solo los fragmentos con `incluido_por == "posible_conflicto"` o cuyo `chunk_id` esté en `chunk_ids_afectados`, y el mejor fragmento de cada documento en conflicto;
  - en `comparar_versiones`, el mejor fragmento de cada documento comparado, no todos.
- **Recorte:** el resto entra en orden hasta el presupuesto. `evidencia_recortada` aparece solo si se descartó algún fragmento.
- **Cota dura:** si los protegidos solos exceden el presupuesto, entran igual (son pocos por construcción) y el aviso se emite.
- **Pruebas:** el caso de 10 fragmentos de 5000 caracteres con un tope de 6000, con y sin conflicto. Sin descarte, no hay aviso.

### A5 (baja): la auditoría no se pierde

- Lee `usuario` y `tenant_id` del `ctx` **al inicio**, con una función que devuelve `None` ante cualquier excepción.
- **Prueba:** un `ctx` cuya propiedad lanza `RuntimeError` produce igual exactamente un evento.

### A6 (baja): configuración del LLM inválida

- La configuración del LLM se lee **antes** de ejecutar la herramienta.
- Si es inválida: abstención con la advertencia `generador_no_disponible` y el error `config_llm_invalida`, sin llamar a la herramienta.
- **Prueba:** con `LICIGT_LLM_URL=ftp://x`.

### A7 (sin probar): palabras clave del modo estricto de OpenAI

- Verifica con Context7 y con la documentación oficial de OpenAI (Structured Outputs, "Supported schemas") si el modo estricto admite `minLength`, `maxLength`, `minItems`, `maxItems` y `enum` en los modelos estándar.
- Si alguna no se admite, quítala **solo en lo que se envía con el perfil `openai`**; el validador local la sigue aplicando.
- Documenta lo verificado en un comentario de una línea, con la URL.
- **Prueba:** el esquema enviado con `openai` contiene solo palabras admitidas, y el de `local` no cambia.

### A8 (probable): perfil `openai` con destino y llave acotados

- Con `LICIGT_LLM=openai`:
  - la URL debe ser `https`;
  - la ruta de la llave debe quedar dentro de `keys/` tras resolver la ruta (sin `..` que escape).
- Si no se cumple, `FallaGenerador("config_insegura")` al construir el cliente.
- El perfil `local` admite `http://127.0.0.1` y `http://localhost`.
- **Pruebas:** el rechazo de `http://` remoto y de una llave fuera de `keys/`, y la aceptación de los valores por defecto.

## Criterios de aceptación

- `make test-consulta` en verde, sin servicios, y con todas las pruebas nuevas.
- Los scripts de reproducción del adversario (los casos B1 a B7, C2, A5 y A6 de este encargo) quedan cubiertos por pruebas del repo.
- Sin texto de PDF, pregunta ni llave en la auditoría, las advertencias ni los errores.

## Al terminar

Responde con:

- los archivos tocados;
- el resumen final de `make test-consulta`;
- cada hallazgo (A1 a A8) con la prueba que lo cubre y cómo quedó;
- lo que verificaste para A7, con la URL;
- las decisiones donde el encargo no era claro.

No amplíes el alcance.
