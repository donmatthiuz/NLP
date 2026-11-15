# Recuperación y RAG: implementación

**Estado al 15 de noviembre de 2026.** Este documento describe lo que ya funciona del [plan del rol 2](Plan_rol_2.md). El uso y el contrato para el rol 3 están en el [README del módulo](../../src/licigt/recuperacion/README.md).

## Índices

| Variante | Fragmentos | Modelo | Índice |
|---|---|---|---|
| Línea base | 1054 ventanas de 120 tokens con solape de 20, una página por ventana y medidas con el tokenizer de MiniLM. Ninguna se trunca, y una prueba lo verifica. | `paraphrase-multilingual-MiniLM-L12-v2` (384) | HNSW con coseno, `m=16`, `ef_construction=64` |
| Mejorada | Los 1003 fragmentos por sección de la ingesta | `BAAI/bge-m3` (1024) | HNSW con coseno, y además un `tsvector` en español (GIN) |

Las dos variantes comparten la tabla `fragmentos`, distinguidas por la columna `variante`. Cada una usa su propia columna de vector y su propio índice parcial. Los códigos IGSS se guardan aparte en el campo exacto `codigos` (`text[]`, GIN).

## Búsqueda

1. **Acceso:** se aplica `WHERE tenant_id AND evento_id` y, en la misma transacción, `SET LOCAL ROLE licigt_app` con `app.tenant_id`. Así la seguridad por fila bloquea a otra empresa aunque falte el `WHERE`, y hay una prueba que lo comprueba.
2. **Línea base:** devuelve el top-5 por coseno.
3. **Mejorada:**
   - Toma 20 candidatos semánticos y 20 léxicos. En la parte léxica, los términos se combinan con OR y el puntaje sube un punto cuando coincide un código IGSS o un numeral.
   - Fusiona con RRF (k=60, pesos 0.6 y 0.4).
   - Pasa el resultado por `bge-reranker-v2-m3` y quita redundancias: dos fragmentos se consideran redundantes si son del mismo documento, en páginas solapadas, y comparten más del 80 % de las palabras. Un fragmento de otra versión nunca se descarta.
4. **Alertas:**
   - `cobertura_incompleta`: el documento tiene páginas no indexadas o un estado distinto de `completo`.
   - `posible_conflicto`: un resultado de las bases cae bajo un numeral que una modificación o aclaración dice cambiar (por ejemplo, "Se modifica el subnumeral 2.2"). En ese caso se añade también el fragmento de la modificación y no se decide cuál está vigente.
5. **Suficiencia:** `suficiente = puntaje top ≥ umbral`. El umbral provisional es 0.45 de coseno para la base y 0.10 del reranker para la mejorada.

## Resultados en desarrollo

Para medir se usaron [27 casos](../../src/licigt/recuperacion/casos_desarrollo.json): 5 temas en cada uno de los 5 eventos, más 2 preguntas sin evidencia. Un fragmento cuenta como relevante si coincide el tipo de documento y la página. El comando es `python -m licigt.recuperacion.evaluar`, con la GPU local.

| Variante | Hit@5 | MRR@5 | Abstención correcta | Abstención indebida | Latencia p95 |
|---|---|---|---|---|---|
| Línea base | 0.56 | 0.36 | 2/2 | 0/25 | 0.01 s |
| Mejorada | **1.00** | **0.90** | 2/2 | 0/25 | 0.73 s |

**Límites:**
- Los casos se armaron a partir de las páginas de sección del índice y nadie los ha revisado.
- Los mismos casos sirvieron para ajustar los umbrales, así que estos números no son la evaluación final. Esa evaluación usa el banco del rol 4 y debe incluir un evento reservado.

## Evento 222: conflicto real

- Las bases (p. 8, 2.2.6) fijan la recepción de ofertas el 31 de julio de 2023, y la Modificación 1 (p. 1) la cambia al 6 de octubre de 2023.
- La búsqueda devuelve las dos cláusulas con las alertas `posible_conflicto` (numerales 2.2 y 2.7) y `cobertura_incompleta` (páginas 3 y 4 sin OCR).
- `comparar_versiones()` devuelve los mejores fragmentos de cada documento para que se contrasten.

## Pendientes

- [ ] Calibrar los umbrales con el banco del rol 4 y un evento reservado.
- [ ] Rol 1:
  - Sin OCR de las páginas 3 y 4 de la modificación, esa evidencia falta.
  - `tabla_markdown` viene vacío.
  - En algunos fragmentos `seccion` contiene el pie de página (`Extensión: 99175`), lo que impide detectar conflictos en esos casos.
  - Cuando cambie el ZIP hay que volver a ejecutar `importar`, que no duplica datos.
- [ ] Rol 4: dónde se despliega Postgres y la integración del `Contexto` con la sesión autenticada.
- [ ] Rol 3: confirmar el contrato de `buscar` y `comparar_versiones`.
