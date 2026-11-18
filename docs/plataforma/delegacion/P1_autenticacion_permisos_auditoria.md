# Encargo P1: autenticación, permisos, auditoría y segunda empresa

Para el implementador. Rama `proyecto`. No commitees.

Lee primero:

- [`AGENTS.md`](../../../AGENTS.md);
- en el anteproyecto (`docs/anteproyecto/Anteproyecto.md`):
  - `:199`: copias lógicas por empresa y filtros por `tenant_id`, `evento_id` y rol;
  - `:238`: la aplicación autentica al analista y resuelve empresa, evento y rol;
  - `:406`: pruebas de acceso cruzado, mezcla de eventos y original sin permiso;
  - `:411`: validar empresa, evento y rol antes de recuperar, abrir un PDF o modificar listas;
- [`Contratos.md`](../../consulta/Contratos.md), sección "Rol 4 hacia rol 3" (contexto y campos de auditoría);
- `src/licigt/consulta/api.py` completo;
- `src/licigt/recuperacion/busqueda.py`, solo `Contexto` y `_sesion`, y `schema.sql`, la parte de seguridad por fila;
- `src/licigt/recuperacion/indice.py`, la importación del ZIP, para crear la segunda empresa;
- el `Makefile`, los objetivos `keys-init`, `key-set` y `api`.

## Decisiones del gestor (cinco porqués; visto bueno del usuario el 18 de noviembre)

- **Por qué hace falta:** el rol 4 no tiene código. La API usa `contexto_demo()` con una empresa fija, así que no se cumple ni la entrega verificable del rol 4 ("una empresa no ve los documentos de otra") ni las pruebas de permisos del anteproyecto.
- **Autenticación:** usuario y contraseña, que dan una cookie de sesión firmada con HMAC.
  - La cookie es `HttpOnly` y `SameSite=Strict`, con expiración, y sin estado en el servidor.
  - Se descarta un token en el frontend, porque quedaría expuesto en el JavaScript.
  - Se descartan OAuth y un proveedor externo: es un MVP local.
- **Dónde viven usuarios y secreto:**
  - el secreto de firma, en `keys/plataforma/sesion.key`;
  - los usuarios, en `keys/plataforma/usuarios.json`: usuario, hash de la contraseña con `hashlib.scrypt` y sal, `tenant_id` y rol;
  - nada de esto entra al repo.
- **Roles:**
  - `analista`: consulta, propone y guarda la lista;
  - `lector`: consulta y ve la lista, pero no la guarda ni la cambia.

  El rol se comprueba en la API. El `Contexto` del rol 2 no cambia: la plataforma lleva su propia sesión con el rol y construye `Contexto(tenant_id, usuario)`.
- **Segunda empresa:** `empresa_b` (ficticia) recibe una copia lógica de **un solo evento** (363-IGSS-2026), como dice `Anteproyecto.md:199`. El 222 queda solo en `empresa_demo`.
- **Original del PDF:** un endpoint de solo lectura que sirve el original de un documento del evento, solo a la empresa dueña. Sirve a la trazabilidad de citas de la demo y a la prueba de "original sin permiso".
- **Auditoría:** un archivo JSONL por día en `data/auditoria/`, con los campos de `Contratos.md`. Nunca lleva la pregunta, texto de PDF, contraseñas ni tokens.

## Archivos

- **Nuevos:** `src/licigt/plataforma/` (por ejemplo `sesion.py`, `usuarios.py` y `auditoria.py`) y `src/licigt/plataforma/tests/`.
- **Se cambia:** `src/licigt/consulta/api.py`, que deja de ser "sin autenticación" y usa la plataforma.
- **Makefile:** solo objetivos nuevos.
- **No toques:**
  - `src/licigt/recuperacion` (otro agente trabaja ahí en paralelo);
  - `.env.example`;
  - `web/`, que va en un encargo aparte.

## Cambios (prueba en rojo primero)

### 1. Sesión y usuarios

- **Endpoints:**
  - `POST /api/sesion` recibe `{usuario, contrasena}` (`extra="forbid"`), valida con comparación en tiempo constante y responde 204 con la cookie; las credenciales malas dan 401 con un mensaje genérico;
  - `DELETE /api/sesion` cierra la sesión;
  - `GET /api/sesion` devuelve `{usuario, tenant_id, rol}` o 401.
- **El resto de `/api/*`** exige la sesión: sin cookie válida, 401.
  - `contexto_demo` desaparece de las rutas, junto con la cabecera `X-LiciGT-Autenticacion` y su middleware.
  - El contexto sale solo de la cookie verificada.
- **Rol en la escritura:** guardar y cambiar la lista exigen el rol `analista`; con otro rol, 403.
- **Makefile:**
  - `make usuarios-demo` crea, si no existe, el secreto y los usuarios `analista_demo` (empresa_demo, analista), `lector_demo` (empresa_demo, lector) y `analista_b` (empresa_b, analista);
  - las contraseñas se generan al azar y se guardan en `keys/plataforma/contrasenas_demo.txt`, sin imprimirlas;
  - `make keys-status` lo informa.
- **Pruebas** (`TestClient` y dobles, sin base de datos):
  - login correcto e incorrecto;
  - cookie alterada o vencida;
  - ruta sin sesión;
  - un `lector` que intenta guardar la lista;
  - que `tenant_id` no se pueda fijar desde el cuerpo, la consulta ni una cabecera.

### 2. Original del PDF

- **Endpoint:** `GET /api/eventos/{evento}/documentos/{doc_id}/original` devuelve el PDF si el documento es del evento y de la empresa de la sesión, consultando con la sesión por empresa del rol 2.
  - Si no, 404 sin distinguir "no existe" de "no es tuyo".
  - Lee el original del paquete o del almacén local, sin exponer rutas.
- **Pruebas:** propio, 200; de otra empresa, 404; `doc_id` de otro evento, 404; ruta con `..`, rechazada.

### 3. Auditoría

- **Qué se registra:** cada consulta, propuesta, cambio de lista y login (con éxito o no) escribe una línea en `data/auditoria/AAAA-MM-DD.jsonl`.
  - Los campos son los de `Contratos.md` para las consultas, y `momento`, `usuario`, `tenant_id`, `accion` y `resultado` para lo demás.
  - En un login fallido, el usuario se guarda con hash.
- **Prueba:** ninguna línea contiene la pregunta, el texto de la respuesta, la contraseña ni la cookie.

### 4. Segunda empresa y pruebas de permisos

- **Paquete de la segunda empresa:** `make empresa-b` arma, desde `entregables/recuperacion/empresa_demo.zip`, un paquete con solo el evento 363 y `tenant_id=empresa_b`.
  - Mismos `doc_id` y `chunk_id`, si el esquema lo permite; si la clave primaria lo impide, documenta qué cambiaste.
  - Lo deja en `data/plataforma/empresa_b.zip` y lo importa con el importador del rol 2, sin modificarlo.
- **Pruebas de integración** (`src/licigt/plataforma/tests/`, se saltan sin base, como las del rol 2):
  - **acceso cruzado:** `analista_b` pide el 222 y recibe 404; con el `evento_id` interno del 222, también 404;
  - **mezcla de eventos:** una consulta de `analista_demo` sobre el 363 solo cita fragmentos del 363 de `empresa_demo`, nunca de `empresa_b`, y viceversa;
  - **original sin permiso:** `analista_b` pide el original de un documento del 222 y recibe 404;
  - **concurrencia:** 10 consultas en paralelo de las dos empresas (con un generador doble, para no depender del LLM) nunca devuelven fragmentos de la otra empresa.

## Criterios de aceptación

- `make test-consulta` en verde, con las pruebas de la API adaptadas a la sesión, sin debilitarlas.
- Las pruebas nuevas de la plataforma, en verde.
- Las de integración pasan con `make db-up`, `make importar` y `make empresa-b`. Córrelas: Postgres está arriba.
- `make api` sigue funcionando y su texto de ayuda ya no dice "sin autenticación".

## Al terminar

Responde con:

- los archivos tocados;
- los resultados de las pruebas;
- cómo se usa: los comandos y lo que debe hacer el usuario;
- las decisiones donde el encargo no era claro.

No amplíes el alcance. Sin `keys/` en la salida: no leas ni imprimas las llaves; las generas con el `Makefile`.
