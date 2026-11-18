# Encargo R2C: cierre del rol 2 (GPU, umbral e interfaces pedidas)

Para el implementador. Rama `proyecto`. No commitees.

Lee primero:

- [`AGENTS.md`](../../../AGENTS.md);
- [`Recuperacion.md`](../Recuperacion.md) y [`Plan_rol_2.md`](../Plan_rol_2.md);
- los pedidos abiertos de [`Avisos_del_rol_3.md`](../Avisos_del_rol_3.md) y [`Avisos_del_rol_1.md`](../Avisos_del_rol_1.md);
- `src/licigt/recuperacion/busqueda.py`, `indice.py`, `evaluar.py` y `casos_desarrollo.json`, con sus pruebas;
- en `src/licigt/consulta/api.py`, `resolver_evento` y `obtener_lector`, solo para ver qué reemplazan las funciones nuevas (no lo edites);
- `docs/consulta/investigacion/I2_llm_local.md`, sección 1 (presupuesto de VRAM).

## Decisiones del gestor (cinco porqués; visto bueno del usuario el 18 de noviembre)

- **Latencia:** el reranker corre en CPU (unos 7 s por búsqueda) porque la GPU de 12 GB la ocupa el LLM. Es una parte grande del P95 de 29,3 s (`docs/consulta/Experimento_JEV.md`). Si el P95 baja de 15 s, la regla del experimento, sin cambios, da "adoptar JEV".
- **Umbral:** `UMBRAL["mejorada"]=0.10` declara insuficientes preguntas que tienen respuesta y el fragmento correcto primero: NOG con 0,011, inducción con 0,006. La pregunta sin respuesta da 0,001.
- **Interfaces:** el rol 3 suple `resolver_evento` y `obtener_fragmentos` con adaptadores propios. El sitio correcto es el rol 2, con la sesión por empresa.

## Archivos

- `src/licigt/recuperacion` y sus pruebas.
- `.env.example`, solo variables nuevas.
- `docs/recuperacion/Recuperacion.md`.
- **No toques:** `src/licigt/consulta`, `src/licigt/plataforma` ni el `Makefile`; otro agente trabaja ahí en paralelo.

## Cambios (prueba en rojo primero)

### 1. Dispositivo y precisión

- `LICIGT_RECUPERACION_DISPOSITIVO` (`cuda`, `cpu` o `auto`, por defecto `auto`) y `LICIGT_RECUPERACION_DTYPE` (`float16` o `float32`; `float16` por defecto solo en CUDA) se aplican a `bge-m3` y al reranker, con la API actual de sentence-transformers. **Consulta la firma con Context7** antes de escribirla.
- **Si CUDA no tiene memoria para cargar, o no está:** se cae a CPU con un aviso en el registro, sin abortar.
- **Mide y anota en `Recuperacion.md`, con el LLM cargado en la GPU** (`docker ps` muestra `licigt-llm`; no lo apagues):
  - la VRAM de cada modelo en fp16;
  - el tiempo de `buscar` mejorada (p50 y p95 sobre los 27 casos de desarrollo) en CPU y en GPU.
- Si no cabe junto al LLM, repórtalo con los números y deja CPU como valor por defecto.

### 2. Umbral de suficiencia

- Calibra `UMBRAL["mejorada"]` con `casos_desarrollo.json` y el corpus actual (R6, ya importado): el valor que maximiza el acierto de suficiencia (respondibles con `suficiente=true` y sin respuesta con `false`).
- Reporta la tabla de umbrales probados.
- Si con el reranker solo no se separan los casos, evalúa un respaldo simple y documentado: por ejemplo, exigir el umbral del reranker **o** que el primer resultado tenga coincidencia léxica exacta de un identificador de la pregunta. No inventes más de una regla.
- Declara en `Recuperacion.md` que es una calibración de desarrollo: la evaluación final usa el banco común con un evento reservado (otra fase).

### 3. Interfaces pedidas

- `resolver_evento(ctx, evento)` devuelve el `evento_id` interno, buscando por id o por `numero_evento`, con la sesión por empresa, o `None`.
- `obtener_fragmentos(ctx, evento_id, chunk_ids)` devuelve los fragmentos con los mismos campos que `buscar()`, solo los del evento y de la empresa de la sesión. Un id ajeno no se devuelve.
- Agrega `warnings` (la lista del inventario, sin texto del PDF) a la alerta `cobertura_incompleta`, si el dato existe en la base. Si no existe, repórtalo y no cambies el esquema sin necesidad.
- **Pruebas:** unitarias con dobles, y de integración que se saltan sin base (como las actuales).

### 4. Documentación

- Corrige las tres diferencias de `Avisos_del_rol_3.md` (README de recuperación y `Plan_rol_2.md`).
- Marca en `Plan_rol_2.md` lo que ya está hecho, con su evidencia.
- Corre `python -m licigt.recuperacion.evaluar` con el corpus R6 y actualiza la tabla de resultados de desarrollo de `Recuperacion.md` (Hit@5 y MRR@5 de las dos variantes), con la fecha y el commit.

## Criterios de aceptación

- `make test-recuperacion` en verde, incluidas las de integración: Postgres está arriba y el corpus R6, importado.
- `make test-consulta` sin regresión.

## Al terminar

Responde con:

- los archivos tocados;
- las pruebas;
- las mediciones de VRAM, latencia y umbral;
- Hit@5 y MRR@5 con R6;
- las decisiones donde el encargo no era claro.

No amplíes el alcance. Sin `keys/`.
