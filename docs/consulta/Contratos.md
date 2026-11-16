# Contratos del rol 3

**Estado al 16 de noviembre de 2026.** Define con qué se conecta el módulo de consulta. El contrato con el rol 2 se verificó contra el código (`src/licigt/recuperacion/busqueda.py`, commit `5ccbc50`). El contrato con el rol 4 no existía por escrito: aquí se propone y se adopta hasta que el rol 4 diga otra cosa. Los acuerdos generales están en [Asignacion_de_roles](../roles/Asignacion_de_roles.md#acuerdos-de-integración).

## Rol 2 hacia rol 3

Lo que recibimos, tal como lo devuelve el código hoy.

### `buscar(ctx, evento_id, pregunta, variante="mejorada", k=5, conn=None)`

```json
{"evento_id": "...", "variante": "mejorada", "suficiente": true,
 "fragmentos": [{"chunk_id": "...", "doc_id": "...", "tipo_documento": "bases", "version_ingesta": 1,
                 "pagina_inicio": 8, "pagina_fin": 8, "seccion": "2.2.6 ...", "texto": "...",
                 "url_origen": "https://...", "identificador_version_oficial": null,
                 "score": 0.91, "reranker": 0.91, "semantico": 0.62, "lexico": 0.4, "rrf": 0.016,
                 "incluido_por": "posible_conflicto"}],
 "alertas": [{"tipo": "cobertura_incompleta", "doc_id": "...", "paginas_no_indexadas": [3, 4], "status": "requiere_revision"},
             {"tipo": "posible_conflicto", "doc_id": "...", "documento": "Modificación Número 1",
              "numerales_modificados": ["2.2", "2.7"], "chunk_ids_afectados": ["..."]},
             {"tipo": "evento_con_modificaciones", "doc_id": "...", "documento": "Modificación Número 1"}]}
```

- `incluido_por`, `reranker`, `semantico`, `lexico` y `rrf` solo aparecen según la variante y el origen del fragmento; son opcionales para nosotros.
- La variante `base` no tiene `reranker`, `lexico` ni `rrf`.
- Solo `mejorada` se usa en producción; `base` existe para la comparación del rol 4.

### `comparar_versiones(ctx, evento_id, pregunta, k=2, conn=None)`

```json
{"evento_id": "...", "documentos": [
  {"doc_id": "...", "tipo_documento": "bases", "identificador_version_oficial": null,
   "fragmentos": [{"chunk_id": "...", "doc_id": "...", "tipo_documento": "bases", "version_ingesta": 1,
                   "pagina_inicio": 8, "pagina_fin": 8, "seccion": "...", "texto": "...", "url_origen": "https://...",
                   "identificador_version_oficial": null, "score": 0.7}]}]}
```

### Reglas de uso (rol 3)

- `suficiente = false` obliga a abstenerse. No se llama al LLM.
- `posible_conflicto` obliga a `needs_human_review = true` y a mostrar ambas fuentes. Nunca se decide la vigencia.
- `cobertura_incompleta` fija `coverage_status = "parcial"` y añade un `warning` con las páginas no indexadas.
- `evento_con_modificaciones` añade un `warning`: existe una modificación que no apareció en los resultados.
- `buscar()` no filtra por `tipo_documento`: la herramienta `buscar_documentos` filtra sobre `fragmentos[].tipo_documento`. Si el recorte deja menos de `k` en el banco, se pide el filtro al rol 2.
- `comparar_versiones` del rol 2 no devuelve alertas ni suficiencia: la herramienta del rol 3 llama también a `buscar()` con el mismo tema para obtenerlas.
- El filtro por `tipo_documento` nunca quita la otra fuente de un `posible_conflicto`; si no queda ningún fragmento, se abstiene.
- Un tipo de alerta desconocido no rompe la lectura: se conserva y se añade un `warning`.
- Se acepta cualquier campo extra; faltar un campo obligatorio es un error de contrato y se trata como falla controlada.

### Diferencias detectadas (avisar al rol 2 o corregir su documentación)

- El README de recuperación lista dos tipos de alerta; el código emite tres (`evento_con_modificaciones`).
- `Plan_rol_2.md` describe `comparar_versiones(ctx, evento_id, seccion)`; el código recibe `pregunta` y `k`.
- El anteproyecto define `comparar_versiones(evento_id, doc_base_id, doc_cambio_id)`; el código del rol 2 no recibe ids de documento. Decisión del rol 3: los parámetros de la herramienta serán `evento_id`, `tema` (texto), y `doc_base_id` y `doc_cambio_id` opcionales. Si faltan los ids, se comparan todos los documentos del evento. Hay que reflejarlo en el anteproyecto.

## Rol 4 hacia rol 3

Existe solo el acuerdo 3 de integración (el contexto viene de la sesión autenticada) y la clase `Contexto(tenant_id, usuario)` que ya usa el rol 2. Propuesta adoptada:

- **Contexto de acceso:** objeto inmutable con `tenant_id`, `usuario` y `rol`. Lo crea el rol 4 desde la sesión. El rol 3 solo lee estos atributos y los pasa tal cual a `buscar()`. No existe ningún parámetro de herramienta, pregunta ni salida del modelo que pueda fijar el `tenant_id`.
- **Pruebas:** usan un contexto de mentira con esos tres atributos; no dependen del rol 4.
- **Auditoría:** el rol 3 emite un evento por solicitud a una función `auditar(evento)` que le inyecta el rol 4 (por defecto, no hace nada). Campos: `momento`, `usuario`, `tenant_id`, `evento_id`, `intencion`, `herramienta`, `chunk_ids`, `abstained`, `needs_human_review`, `validacion`, `latencia_ms`, `error`. No incluye texto de PDF ni la pregunta completa.
- **Límites y validación:** el rol 3 aplica los límites de herramienta (3 llamadas, 1 regeneración) y valida su propia salida. El rol 4 puede repetir esas validaciones en la API como segunda barrera.
- **Si el rol 4 propone otro formato:** se cambia el adaptador, no el núcleo.

## Rol 3 hacia el usuario

Respuesta estructurada (Pydantic):

| Campo | Tipo | Regla |
|---|---|---|
| `answer` | texto | Respuesta redactada. Si se abstiene, es el texto fijo de abstención. |
| `sources` | lista | Cada una con `doc_id`, `source`, `page`, `page_end`, `chunk_id`, `version_ingesta`, `version_oficial` y `cita`. La versión se separa en dos porque el anteproyecto pide no confundir la carga con la modificación oficial. Al menos una fuente si no hay abstención. |
| `abstained` | booleano | Verdadero cuando la evidencia no permite responder. |
| `tool_used` | texto o nulo | `buscar_documentos`, `extraer_requisitos`, `comparar_versiones` o nulo. |
| `needs_human_review` | booleano | Contradicción, ambigüedad o condición crítica. |
| `evento_id` | texto | Evento consultado. |
| `coverage_status` | texto | `parcial` o `sin_faltantes_detectados` (no certifica expediente completo). |
| `warnings` | lista de texto | Documentos ausentes, problemas de extracción, conflictos. |
| `needs_clarification` | booleano | Verdadero cuando la pregunta es ambigua y se pide aclaración en lugar de responder o abstenerse. |
| `clarification_question` | texto o nulo | La pregunta de vuelta al analista; en ese caso también es `answer` y no hay fuentes ni herramienta. |

Pedir aclaración es una tercera salida, distinta de abstenerse: en búsqueda conversacional, preguntar ante una consulta ambigua es práctica establecida (Aliannejadi y otros, SIGIR 2019; Zamani y otros, WWW 2020) y el curso la lista como acción del agente (diapositiva 267). Así no se mezcla con la métrica de abstención.

Texto fijo de abstención, según las notas de la semana 15.1 (la instrucción debe ser explícita y verificable): `No hay información suficiente en los documentos para responder`.
