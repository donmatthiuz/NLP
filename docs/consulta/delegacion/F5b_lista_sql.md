# Encargo F5b: la lista de verificación en Postgres

Para el implementador. Rama `rol/consulta`. No commitees.

Lee primero:

- [`AGENTS.md`](../../../AGENTS.md);
- [F5](F5_lista_de_verificacion.md);
- `src/licigt/consulta/lista.py` y `lista_escritura.py` (`RepositorioLista`, `LectorFragmentos` y `RepositorioMemoria`);
- `src/licigt/recuperacion/schema.sql`, `indice.py` (`conectar`) y `busqueda.py` (`_sesion` y `set_config('app.tenant_id', ...)`), solo de lectura;
- el aviso al rol 4 sobre las tablas de la lista, en `docs/plataforma/Avisos_del_rol_3.md`.

## Origen

F5 dejó la persistencia como interfaz con un repositorio en memoria. Este encargo implementa esa interfaz en Postgres. Por defecto, las tablas las crea el rol 3 en un SQL de su módulo, con la misma seguridad por fila que el rol 2, y el rol 4 revisa las políticas.

## Archivos

- **Nuevos:**
  - `src/licigt/consulta/lista_schema.sql`;
  - `src/licigt/consulta/lista_sql.py`;
  - `src/licigt/consulta/tests/test_lista_sql.py`.
- **El objetivo `lista-schema` del `Makefile`:** no lo edites tú; dale al gestor las líneas exactas.
- **Nada más:** no toques `lista.py`, `lista_escritura.py`, `api.py`, `web/` ni `src/licigt/recuperacion`.

## Cambios (prueba en rojo primero)

- **`lista_schema.sql`:**
  - tablas `lista_items` y `lista_cambios` con todos los campos de `ItemLista` y `CambioLista`;
  - `tenant_id` y `evento_id` en las dos tablas, e índices por `tenant_id` y `evento_id`;
  - seguridad por fila con la política `por_empresa` sobre `current_setting('app.tenant_id', true)`, igual que `schema.sql` del rol 2, para el rol `licigt_app`;
  - idempotente (`IF NOT EXISTS` y `DROP POLICY IF EXISTS`).
- **`RepositorioPostgres(conn_factory)`** implementa `RepositorioLista` completo:
  - fija `app.tenant_id` en cada transacción, como `busqueda._sesion`;
  - además filtra por `tenant_id` en el SQL, como segunda barrera;
  - `actualizar_estado` es atómico: `UPDATE ... WHERE estado = estado_anterior`, y si no cambia ninguna fila da `estado_desactualizado`; el `CambioLista` se registra en la misma transacción;
  - el SQL siempre va parametrizado.
- **`LectorFragmentosPostgres(conn_factory)`** implementa `LectorFragmentos`:
  - lee de la tabla `fragmentos` del rol 2 con la misma sesión por empresa, solo `SELECT`;
  - un `chunk_id` de otro evento o de otra empresa no se devuelve;
  - es un adaptador temporal hasta que el rol 2 entregue `obtener_fragmentos`, según el aviso del 17 de noviembre. Indícalo en un comentario de una línea.
- **Pruebas:**
  - **Sin base de datos, siempre corren:**
    - todo el SQL usa parámetros, sin f-strings con datos;
    - `lista_schema.sql` habilita RLS en las dos tablas;
    - el contrato de `RepositorioPostgres` se comprueba con un doble de conexión que registra las sentencias.
  - **De integración:**
    - solo corren si `LICIGT_DB_URL` está definida y la base responde; si no, se saltan con un mensaje explícito;
    - corren las mismas pruebas de contrato que `RepositorioMemoria` (reutiliza las de `test_lista_escritura` si se puede, parametrizadas por repositorio);
    - otra empresa no ve los ítems de la primera, aunque se salte el filtro de la aplicación;
    - la concurrencia de `estado_desactualizado`.
- **Antes de escribir código contra psycopg 3**, consulta su documentación con Context7.

## Criterios de aceptación

- `make test-consulta` en verde, con las pruebas de integración saltadas y su mensaje cuando no hay base.
- Con `make db-up`, las pruebas de integración pasan si las corre el usuario; tú no levantes servicios.

## Al terminar

Responde con:

- los archivos tocados;
- los resultados;
- las líneas del `Makefile`;
- las decisiones donde el encargo no era claro.

No amplíes el alcance.
