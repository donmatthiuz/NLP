# Encargo F6d: la lista de verificación en la API y la web

Para el implementador. Rama `rol/consulta`. No commitees.

Lee primero:

- [`AGENTS.md`](../../../AGENTS.md);
- [F6](F6_interfaz_web.md), sección F6d;
- [F5](F5_lista_de_verificacion.md);
- `web/DISENO.md`, sección de la lista;
- `src/licigt/consulta/api.py`, `lista.py` y `lista_escritura.py`;
- `web/src/`.

## Origen

F5 dejó la lógica de la lista: propuesta determinista, guardado con `Confirmacion(confirmado=True)` y repositorio. Este encargo la expone en la API y en la web, con el diseño ya aprobado en `web/DISENO.md`.

## Archivos

- **API:** `src/licigt/consulta/api.py` y `tests/test_api.py`.
- **Web:** `web/src/` y las pruebas de Vitest.
- **Ejemplos:** la lista de ejemplo en `web/src/ejemplos/`, validada en `tests/test_ejemplos_web.py`.
- **Nada más:** no toques `lista.py`, `lista_escritura.py`, `validacion.py` ni `lista_sql.py`, que es de otro agente en paralelo.

## Cambios (prueba en rojo primero)

### API (FastAPI)

**Rutas**, con el `tenant_id` siempre del contexto de demostración y nunca del cuerpo:

- `POST /api/eventos/{evento_id}/lista/propuesta`: llama a `proponer_lista` y no escribe nada;
- `GET /api/eventos/{evento_id}/lista`: llama a `listar`;
- `POST /api/eventos/{evento_id}/lista`: guarda; el cuerpo lleva los ítems y `confirmado: true`;
- `PATCH /api/eventos/{evento_id}/lista/{item_id}`: cambia el estado con `estado_anterior`, `estado_nuevo` y `confirmado: true`.

**Errores:**

- sin `confirmado: true`, 422, y no se escribe nada;
- `estado_desactualizado`, 409;
- `item_no_encontrado`, 404;
- una cita que no pasa la revalidación, 422 con su código, sin texto del documento.

**Dependencias:**

- **Repositorio:** `obtener_repositorio()` devuelve un `RepositorioMemoria` único por proceso. Con `LICIGT_LISTA=postgres`, importa de forma diferida `licigt.consulta.lista_sql.RepositorioPostgres`; ese módulo lo escribe otro agente en paralelo, así que en las pruebas se sustituye.
- **Lector de fragmentos:** `obtener_lector()` sigue la misma lógica, con `LectorFragmentosPostgres`.

**Pruebas:** cada ruta y cada error, con `dependency_overrides` y sin red ni base de datos. Además:

- un `tenant_id` en el cuerpo da 422;
- la propuesta no escribe nada.

### Web

Sección "Lista de verificación" según `web/DISENO.md`:

- **Proponer:** un botón "Proponer lista" muestra los ítems con su cita, página y versión, su categoría, si es fundamental y si requiere revisión, más el aviso fijo "Los estados de la lista no certifican cumplimiento.".
- **Guardar:** un botón aparte abre un `<dialog>` nativo con el resumen de lo que se va a guardar. Solo "Confirmar" envía `confirmado: true`.
- **Cambiar estado:** pendiente, preparado y revisado, con ícono y texto. Los cambios locales se marcan "Sin guardar", y cada cambio se confirma con su propio diálogo.
- **Conflicto 409:** el mensaje del diseño, más la opción de recargar.
- **Modo ejemplos:** usa una propuesta de ejemplo con datos reales del 222, validada contra `PropuestaLista` en `test_ejemplos_web.py`.
- **Seguridad:** sin `dangerouslySetInnerHTML`; ningún `tenant_id`.
- **Vitest:** el reductor de estado de la lista; el guardado no se envía sin confirmar; el 409 muestra el mensaje.

## Criterios de aceptación

- `make test-consulta` en verde.
- `pnpm --dir web build` y `pnpm --dir web exec vitest run` en verde.
- Capturas en el scratchpad del gestor (`web_lista_*.png`) de la propuesta, el diálogo de confirmación, los estados y el 409, a 1000 px y a 320 px.

## Al terminar

Responde con:

- los archivos tocados;
- los resultados;
- las rutas de las capturas;
- las decisiones donde el encargo no era claro.

No amplíes el alcance.
