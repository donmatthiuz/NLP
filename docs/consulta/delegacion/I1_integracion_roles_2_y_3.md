# Encargo I1: integración del rol 2 en el rol 3 y página impresa

Rama `proyecto`. No commitees.

Lee primero:

- [`AGENTS.md`](../../../AGENTS.md);
- `src/licigt/recuperacion/busqueda.py` (`CAMPOS`, `resolver_evento` y `obtener_fragmentos`), `indice.py` (importación) y `schema.sql`;
- `src/licigt/consulta/api.py` (`resolver_evento` y `_abrir_conexion_rol2`), `lista_sql.py` (`LectorFragmentosPostgres`), `lectura.py` (`FragmentoRecuperado`), `esquemas.py` (`Fuente`) y `herramientas.py` (`fuente_desde_fragmento`), con sus pruebas;
- `src/licigt/plataforma/originales.py`, para ver cómo usa la conexión.

## Por qué (cinco porqués del gestor; plan aprobado por el usuario)

- **Adaptadores provisionales:** el rol 3 tiene adaptadores propios para resolver el evento y leer fragmentos por id. Los escribió mientras el rol 2 no los tenía, y R2C (`c7d0dcc`) ya entregó `resolver_evento` y `obtener_fragmentos` con la sesión por empresa. Mantener las dos versiones duplica la lógica de seguridad.
- **Página impresa:** el usuario abrió "p. 8" y el PDF mostraba un 7 impreso. La página física es la correcta, porque el enlace navega por ella, pero confunde. El paquete trae `pagina_impresa` (la responsabilidad 4 del rol 1 pide conservarla), y el esquema y el importador del rol 2 la descartan.

## Archivos

- `src/licigt/recuperacion`: `schema.sql`, `indice.py` y `busqueda.py`, con sus pruebas.
- `src/licigt/consulta`: `api.py`, `lista_sql.py`, `lectura.py`, `esquemas.py` y `herramientas.py`, con sus pruebas.
- **No toques `web/`:** otro agente la rediseña. La web leerá `printed_page` si viene.

## Cambios (prueba en rojo primero)

### 1. Usar las funciones del rol 2

- **`resolver_evento` de la API:** llama a `busqueda.resolver_evento(ctx, evento)`. Con `None`, da 404 `evento_no_encontrado`, igual que hoy.
- **`LectorFragmentosPostgres`:** delega en `busqueda.obtener_fragmentos`, o se reemplaza por un adaptador mínimo que la llame. Se quita el SQL duplicado.
- **No debe cambiar:**
  - la seguridad por fila;
  - las pruebas de plataforma: acceso cruzado, mezcla de eventos, original sin permiso y concurrencia;
  - las de la lista.
- `_abrir_conexion_rol2` puede quedarse para `originales` y para el listado de documentos, si siguen haciendo falta. Si no, se quita.

### 2. Página impresa de punta a punta

- **`schema.sql`:** `pagina_impresa INTEGER NULL` en `fragmentos`, con `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` para no romper una base existente.
- **El importador** la guarda desde `chunks.jsonl`. En las ventanas de la línea base, la de su página de inicio.
- **`CAMPOS`** la incluye, y `buscar`, `comparar_versiones` y `obtener_fragmentos` la devuelven.
- **`FragmentoRecuperado`:** `pagina_impresa: int | None = None`.
- **`Fuente`:** `printed_page: int | None = None`, que es un campo nuevo opcional del contrato de salida. `fuente_desde_fragmento` lo llena.
  - Documenta el campo en `docs/consulta/Contratos.md`.
  - Revisa que el validador de citas no dependa de él.
- **Reimporta:** `make importar` y luego `make empresa-b`, para que `empresa_b` siga existiendo.
- **Prueba de integración:** la fuente del 222 que cita `03791a…:00032` sale con `page=8` y `printed_page=7`.

## Criterios de aceptación

- `make test-recuperacion`, `make test-consulta` y `make test-plataforma` en verde, con Postgres.
- Una consulta real por la API con sesión, en un puerto libre, que apagas al terminar. No puedes leer contraseñas, así que hazla con `TestClient` y los usuarios de prueba de `soporte.py`, contra la base real.

## Al terminar

Responde con:

- los archivos tocados;
- las pruebas;
- qué adaptadores se quitaron;
- las decisiones donde el encargo no era claro.

No amplíes el alcance. Sin `keys/`.
