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
5. **Suficiencia:** `suficiente = puntaje del primer resultado ≥ umbral`, sin más reglas. El umbral es 0.45 de coseno para la base y 0.005 del reranker para la mejorada (calibración en la sección siguiente).

## Resultados en desarrollo

**Fecha:** 18 de noviembre de 2026. **Código:** commit `cd75bbd` más los cambios de R2C sin commitear. **Corpus:** R6, ya importado.

Para medir se usaron [27 casos](../../src/licigt/recuperacion/casos_desarrollo.json): 5 temas en cada uno de los 5 eventos, más 2 preguntas sin evidencia. Un fragmento cuenta como relevante si coincide el tipo de documento y la página. El comando es `make evaluar` (que corre `python -m licigt.recuperacion.evaluar`); con `LICIGT_EVALUAR_PUNTAJES=1`, `LICIGT_EVALUAR_SALIDA=<archivo>` y `LICIGT_EVALUAR_CASOS=<archivo>` imprime los puntajes y guarda el detalle.

| Variante | Hit@5 | MRR@5 | Abstención correcta | Abstención indebida | Latencia p50 | Latencia p95 |
|---|---|---|---|---|---|---|
| Línea base | 0.56 | 0.33 | 2/2 | 0/25 | 0.01 s | 0.01 s |
| Mejorada, GPU fp16 | **1.00** | **0.90** | 2/2 | 0/25 | 0.21 s | 0.45 s (0.25 s en otra corrida) |
| Mejorada, CPU fp32 | **1.00** | **0.90** | 2/2 | 0/25 | 13.6 s | 15.6 s |

La latencia de la GPU se midió con `licigt-llm` cargado, y la variación entre corridas (p95 de 0.25 a 0.45 s) viene de que comparte la GPU con el LLM. En CPU, el reranker sobre 20 candidatos domina el tiempo.

### Umbral de suficiencia (calibración de desarrollo)

Puntaje del primer resultado de la mejorada (reranker), con GPU fp16:

- 25 casos respondibles: de 0.7957 (`399-seg`) a 0.9951 (`222-req`).
- 2 casos sin respuesta del archivo de desarrollo: 0.0000 y 0.0001.
- 4 preguntas extra sobre el 222, que no forman parte de los 27 ([`casos_calibracion.json`](../../src/licigt/recuperacion/casos_calibracion.json)): NOG 0.0209 (respondible; el primero es la portada y la p. 10 con el NOG da 0.012), inducción 0.666 (respondible), precio unitario por vial 0.0022 (sin respuesta; una medición anterior dio 0.001, deriva entre corpus o dispositivo) y "numeral 2.7 sobre el seguro de vida" 0.364 (sin respuesta).

| Umbral | Aciertos de suficiencia, 27 casos | 27 casos más NOG y precio por vial (dentro de la muestra usada para elegir el umbral, no es acierto fuera de ella) |
|---|---|---|
| 0.0001 o menos | 26/27 (una pregunta sin respuesta pasa) | 27/29 |
| 0.0002 a 0.0022 | 27/27 | 28/29 (el precio por vial pasa si el umbral es 0.0022 o menos) |
| **0.005** (elegido) | 27/27 | 29/29 |
| 0.0209 | 27/27 | 29/29 (en el límite del NOG) |
| 0.10 (anterior) | 27/27 | 28/29 (el NOG, 0.0209, queda insuficiente) |
| 0.8154 | 26/27 | 25/29 |
| 0.9594 | 21/27 | 22/29 |

Los 27 casos separan con cualquier umbral entre 0.0002 y 0.7957: la evaluación de desarrollo no discrimina el valor. Por eso la elección se apoya en las preguntas extra, que obligan a quedar entre 0.0022 (precio por vial, sin respuesta) y 0.0209 (NOG, respondible); 0.005 queda en ese tramo, lejos del ruido (menos de 0.0003 en los casos de desarrollo).

**Riesgos y casos en el límite:**
- Hay solo 3 preguntas sin respuesta con datos; el margen es chico.
- NOG (0.0209) e inducción son datos puntuales que el reranker puntúa bajo; en la medición del rol 3 sobre el corpus anterior daban 0.011 y 0.006. Con 0.005 siguen pasando, pero un umbral mayor que 0.011 las habría rechazado.
- Riesgo abierto: una pregunta sin respuesta que comparte vocabulario con el corpus ("seguro de vida", 0.364) pasa con cualquier umbral razonable. Que termine en abstención depende de la generación y la verificación de citas del rol 3; se probará en el banco común.
- No se usa ninguna regla léxica de respaldo: una prueba lo comprueba. Un identificador repetido en el texto no demuestra que haya respuesta.
- La base (coseno 0.45) separa también los 27 casos (sin respuesta hasta 0.38, respondibles desde 0.51); no se recalibró.

**Límites:**
- Es una calibración de desarrollo. La evaluación final usa el banco común del rol 4 con un evento reservado (otra fase).
- Los casos se armaron a partir de las páginas de sección del índice y nadie los ha revisado.

**Reproducir el barrido:**

```bash
HF_HOME=$PWD/models HF_HUB_OFFLINE=1 LICIGT_EVALUAR_PUNTAJES=1 make evaluar
HF_HOME=$PWD/models HF_HUB_OFFLINE=1 LICIGT_EVALUAR_PUNTAJES=1 \
  LICIGT_EVALUAR_CASOS=src/licigt/recuperacion/casos_calibracion.json make evaluar
```

Con `LICIGT_RECUPERACION_DISPOSITIVO=cpu` o `cuda` se elige el dispositivo.

## Dispositivo y precisión (R2C)

- `LICIGT_RECUPERACION_DISPOSITIVO` (`auto`, `cuda` o `cpu`; `auto` por defecto) y `LICIGT_RECUPERACION_DTYPE` (`float16` o `float32`; vacío significa `float16` en CUDA y `float32` en CPU) se aplican a MiniLM, bge-m3 y el reranker (`indice.cargar`). Usan `device=` y `model_kwargs={"dtype": ...}` (en transformers 4 la clave es `torch_dtype`; el código elige según la versión). Firmas consultadas en la documentación de sentence-transformers y transformers con Context7.
- Si CUDA no está o no hay memoria para cargar el modelo, se carga en CPU en float32 con un aviso en el registro (`licigt.recuperacion.indice`), sin abortar.
- **VRAM medida con el LLM cargado** (`licigt-llm` en Docker; RTX 5070 de 12 GiB, 8280 MiB ocupados antes de cargar nada), en fp16, con `torch.cuda.memory_allocated`:

| Modelo | VRAM de pesos |
|---|---|
| MiniLM (línea base) | 226 MiB |
| bge-m3 | 1083 MiB |
| bge-reranker-v2-m3 | 1083 MiB |
| Los tres, pico con una búsqueda de 20 candidatos | 2486 MiB asignados; `nvidia-smi` marcó 11219 MiB de 12227 MiB en total |

  Caben junto al LLM, con unos 1000 MiB de margen. Es poco: con un contexto del LLM mayor que 12288 o más procesos en la GPU, la carga caerá a CPU por el respaldo de arriba.
- Tiempo de los modelos solos (embedding de la pregunta más reranker sobre 20 fragmentos de unas 200 palabras): 0.06 s por búsqueda en GPU fp16. Es una medición parcial, sin la base.
- **Latencia de `buscar` mejorada** sobre los 27 casos, con el LLM cargado: GPU fp16 p50 0.21 s y p95 0.45 s (0.25 s en otra corrida); CPU fp32 p50 13.6 s y p95 15.6 s (tabla de resultados).
- **fp16 frente a fp32 (CPU fp32 contra GPU fp16, mismo código y corpus):**
  - Hit@5 y MRR@5 son iguales (1.00 y 0.90), y ningún caso cambia `suficiente`, tanto en los 27 casos como en las 4 preguntas extra.
  - El primer resultado de cada caso es el mismo. En 3 casos (`363-seg`, `368-seg`, `327-ent`) cambia el orden entre las posiciones 3 y 5, con puntajes bajos.
  - Con eso se cumple el criterio y `auto` (GPU fp16 si hay CUDA) queda por defecto. La diferencia máxima de puntaje en esas posiciones fue 0.10.
- **Sin memoria durante la búsqueda:** si `encode` o `predict` lanzan un error de memoria de CUDA, ese modelo se recarga en CPU una vez, se repite la llamada y sigue en CPU (`indice.ejecutar`), con un aviso en el registro.

## Interfaces para el rol 3 (R2C)

- `resolver_evento(ctx, evento)`: `evento_id` interno a partir del id o del `numero_evento`, solo de la empresa de la sesión, o `None`.
- `obtener_fragmentos(ctx, evento_id, chunk_ids)`: fragmentos con los campos de `buscar()` (con `score` 0.0, porque es lectura por id), solo del evento y de la empresa de la sesión, en el orden pedido. Un id ajeno o inexistente no se devuelve.
- `cobertura_incompleta` lleva ahora `warnings`, la lista del inventario (`documentos.inventario->'warnings'`), sin texto del PDF. El dato existe en la base; no cambió el esquema.

## Evento 222: conflicto real

- Las bases (p. 8, 2.2.6) fijan la recepción de ofertas el 31 de julio de 2023, y la Modificación 1 (p. 1) la cambia al 6 de octubre de 2023.
- La búsqueda devuelve las dos cláusulas con las alertas `posible_conflicto` (numerales 2.2 y 2.7) y `cobertura_incompleta` (página 4 sin indexar).
- `comparar_versiones()` devuelve los mejores fragmentos de cada documento para que se contrasten.

## Respuestas a los avisos del rol 3 (16/11)

- **Contrato:** `buscar()` y `comparar_versiones()` se confirman tal como están en el código. Si se renombra algún campo, se avisará antes.
- **`chunk_id`:** es estable al reimportar (detalle en el [README](../../src/licigt/recuperacion/README.md#contrato-para-el-rol-3)).
- **Documentación:** el README ya incluye `evento_con_modificaciones`, y el plan ya tiene la firma real de `comparar_versiones`.
- **`LICIGT_DB_URL`:** ya no tiene valor por defecto ni contraseña en el código. Si falta, `conectar()` falla con un mensaje claro.
- **Revisiones fijas de los modelos:** están en `REVISION` (`indice.py`) y se guardan en la salida de `evaluar.py`.
  - MiniLM: `e8f8c21`
  - bge-m3: `5617a9f`
  - bge-reranker-v2-m3: `953dc6f`
- **VRAM medida** con `torch.cuda.max_memory_allocated`, en fp32: buscar con las dos variantes, con bge-m3, el reranker y MiniLM cargados, llega a un pico de **4.85 GiB** (4.99 GiB reservados). Con fp16 debería bajar a la mitad, pero no está medido.
- **Filtro `tipo_documento`:** no se agrega por ahora. Se acepta el valor por defecto del rol 3, que filtra después de recibir los resultados.

## Pendientes

- [ ] Calibrar los umbrales con el banco común del rol 4 y un evento reservado. La calibración de desarrollo con `casos_desarrollo.json` es solo para ajustar parámetros, no es evaluación final.
- [ ] Rol 1:
  - La página 4 de la modificación 1 sigue sin indexar (la 3 ya tiene texto en el paquete R6), esa evidencia falta.
  - `tabla_markdown` viene vacío.
  - En algunos fragmentos `seccion` contiene el pie de página (`Extensión: 99175`), lo que impide detectar conflictos en esos casos.
  - Cuando cambie el ZIP hay que volver a ejecutar `importar`, que no duplica datos.
- [ ] Rol 4: dónde se despliega Postgres y la integración del `Contexto` con la sesión autenticada.
- [ ] Rol 3: confirmar el contrato de `buscar` y `comparar_versiones`.
