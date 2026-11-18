# Encargo P2: rol de conexión sin superusuario, rotación de la contraseña y auditoría seudonimizada

Rama `proyecto`. No commitees. Decisiones del usuario del 18 de noviembre, a partir de la revisión retrospectiva ([`Revision_retrospectiva.md`](../../consulta/Revision_retrospectiva.md)).

## Por qué

- **La conexión salta la RLS:** la API, el banco y el reporte se conectan como `licigt`, que es superusuario con BYPASSRLS (`docker-compose.yml:7`). La seguridad por fila depende entonces de que el código llame siempre a `_sesion`. `Anteproyecto.md:246` pide un rol sin privilegios para eludir las políticas.
- **El usuario va en claro:** la auditoría lo guarda así, y `Anteproyecto.md:416` pide seudonimizarlo. Además, las fallas de escritura se tragan sin aviso (`auditoria.py:30-31`).
- **La contraseña se rota** por precaución, tras el incidente de `make … PYTHON=script` (ver la revisión).

## Archivos

- `docker-compose.yml`, `src/licigt/recuperacion/schema.sql` y `lista_schema.sql` (solo roles y grants).
- `Makefile` y `scripts/keys.sh`.
- `src/licigt/plataforma/auditoria.py`, `src/licigt/plataforma/README.md` y sus pruebas.
- **No toques:**
  - `src/licigt/consulta` salvo `api.py`, solo si hace falta para la URL de la base;
  - `src/licigt/ingesta`;
  - `web/`.

## Cambios (prueba en rojo primero donde aplique)

### 1. Rol de conexión

- **Rol `licigt_api`:** `LOGIN`, `NOSUPERUSER`, `NOBYPASSRLS` y miembro de `licigt_app`. Su contraseña, en `keys/database/app.password`, la genera `make keys-init` (y `keys.sh status` la informa) sin imprimirla.
- **Creación idempotente:** con un objetivo `make db-rol-app` que corre como administrador, con la contraseña leída dentro del `Makefile` como hace `db-password-sync`.
- **`Makefile`:**
  - `WITH_DB_ADMIN` (usuario `licigt`) para `importar`, `lista-schema`, `empresa-b`, `db-password-sync` y las pruebas que crean esquema;
  - `WITH_DB` (usuario `licigt_api`) para `api`, `banco`, `reporte`, `evaluar`, `buscar` y las pruebas de integración que solo leen o escriben la lista.
  - Revisa cada objetivo y documenta la elección.
- **Grants:** `licigt_app` necesita en las tablas de la lista los permisos que use la lista (SELECT, INSERT, UPDATE…), sin más.
- **Prueba de integración:** conectado como `licigt_api`, un `SELECT` sobre `fragmentos` sin `_sesion` (sin `app.tenant_id`) devuelve 0 filas o falla, nunca filas de otra empresa. `make test-plataforma`, `make test-recuperacion` y `make test-consulta-sql` siguen en verde.

### 2. Rotación de la contraseña de administración

- **`make db-password-rotar`:** genera una contraseña nueva en `keys/database/dev.password` (con respaldo `.bak` en `keys/`, nunca impreso) y la aplica con la lógica de `db-password-sync`.
- **Córrelo una vez.** Después, comprueba que `make importar` (no hace falta correrlo completo; basta una conexión de administrador) y la API funcionan.
- **Servicios:** hay una API en 8010 lanzada por el gestor con la URL vieja. No la reinicies; el gestor la relanza.

### 3. Auditoría seudonimizada

- **`usuario`:** en todas las líneas va como `hmac:<16 hex>` con la clave de sesión, igual que el login fallido. Sin clave, un valor fijo de respaldo, como hoy.
- **`tenant_id`:** se mantiene, porque los ids de empresa son ficticios y hacen falta para auditar el acceso cruzado. Decláralo en el README.
- **Fallas de escritura:** `logging.warning` sin datos sensibles; la solicitud no falla.
- **Pruebas:** ninguna línea contiene el nombre de usuario en claro, y una falla de escritura emite el aviso.

## Criterios

- `make test-plataforma`, `make test-recuperacion`, `make test-consulta` y `make test-consulta-sql` en verde.

## Reglas

- Nunca leas, imprimas ni copies `keys/`. Solo el `Makefile` y `keys.sh` los manejan.
- No uses `make … PYTHON=…`.
- Si el clasificador bloquea algo, repórtalo sin rodeos.
