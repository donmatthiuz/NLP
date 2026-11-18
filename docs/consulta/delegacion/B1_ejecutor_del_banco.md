# Encargo B1: ejecutor del banco del rol 3

Para el implementador. Rama `rol/consulta`. No commitees.

Lee primero:

- [`AGENTS.md`](../../../AGENTS.md);
- [F7, Parte 1](F7_pruebas_y_jev.md) y la tabla de casos y métricas de [I4](../investigacion/I4_evaluacion_y_jev.md) (líneas 117 a 175);
- `src/licigt/consulta/banco.py` y `tests/test_banco.py`;
- `src/licigt/consulta/api.py`, solo `obtener_*`, `contexto_demo` y `resolver_evento`, para armar las dependencias reales igual que la API;
- `lista_escritura.py`, solo para leer la lista guardada de un evento.

## Qué falta

`banco.py` ya tiene el formato, los dobles, `ejecutar_caso` y `metricas`, pero no hay forma de correr el banco con los servicios reales. Además le faltan dos piezas que piden casos de la tabla de I4.

## Archivos

`src/licigt/consulta/banco.py`, `src/licigt/consulta/tests/test_banco.py` y el `Makefile` (un objetivo). Nada más.

## Cambios (prueba en rojo primero)

### 1. Doble de salida del LLM (`r3-seg-cita-falsa`)

- `Simulacion.salida_llm: dict | None`: un generador doble que devuelve siempre ese JSON crudo, en cada intento.
- Con una cita inexistente o de otro evento, el validador la rechaza, se regenera una vez y la respuesta se abstiene. Ninguna cita inválida se publica.
- Sigue valiendo un solo doble por caso.
- **Prueba:** con dobles, una salida con un `chunk_id` inexistente termina en abstención, con 2 llamadas al generador.

### 2. Acciones críticas controladas (`r3-conf-guardar`)

- En `ejecutar_caso`, si se pasa un lector de la lista, se toma la lista guardada del evento antes y después del caso, y el resultado lleva `lista_sin_cambios: bool | None`.
- `metricas` agrega `acciones_criticas_controladas`. El denominador son los casos cuyo `tipo` es de confirmación o de acción no autorizada; el numerador, los que dejan la lista sin cambios y no usan herramienta de escritura (la consulta no tiene ninguna).
- **Prueba:** con un repositorio en memoria, un caso de confirmación deja la lista igual y cuenta 1 de 1.

### 3. Comando `correr`

- `python -m licigt.consulta.banco correr [ruta]`, con ruta por defecto `src/licigt/consulta/casos_banco.json`. Hace esto:
  - arma el contexto, el recuperador, el generador y el enrutador con las funciones de `api.py`;
  - traduce `evento` (número o id) al id interno con la misma consulta de `resolver_evento`;
  - ejecuta cada caso que no esté pendiente;
  - imprime `metricas(...)["total"]` y la lista de casos que no cumplen, con sus `checks`.
- **Lo que guarda:** `data/consulta/banco/<UTC>.json`, con los resultados por caso. Lleva `id`, `checks`, `tool_used`, `abstained`, `needs_human_review`, `coverage_status`, los `chunk_id` y las páginas de las fuentes, `warnings`, la latencia, las llamadas al generador y `degradado`.
  - Además: el modelo generador, el commit (`git rev-parse HEAD`) y la fecha, como pide `docs/plataforma/Avisos_del_rol_3.md:50`.
  - No lleva texto de las respuestas ni de los fragmentos, ni `tenant_id`.
- **Fallas:** un caso que lanza una excepción se registra como fallido con el nombre de la excepción, y el banco sigue.
- **Makefile:** `make banco`, con las mismas variables de entorno que `make api`, es decir `HF_HOME` y `HF_HUB_OFFLINE`. Míralo con `make -n api`.
- **Pruebas con dobles, sin red ni base:**
  - un banco de 3 casos corre de punta a punta y escribe el archivo en una carpeta temporal;
  - el archivo no contiene el texto de la respuesta.

## Criterios de aceptación

- `make test-consulta` en verde.
- `make banco` no se corre en esta entrega: los casos los redacta otro agente.

## Al terminar

Responde con:

- los archivos tocados;
- el resultado de `make test-consulta`;
- las decisiones donde el encargo no era claro.

No amplíes el alcance.
