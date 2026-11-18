# Plataforma, seguridad y evaluación (rol 4)

Ver [responsabilidades e integración](../../../docs/roles/Asignacion_de_roles.md#rol-4--plataforma-seguridad-y-evaluación).

## Qué hace

- **Sesión:** `POST /api/sesion` (usuario y contraseña) da una cookie `licigt_sesion` firmada con HMAC-SHA256, `HttpOnly`, `SameSite=Strict` y con expiración. No hay estado en el servidor. `GET /api/sesion` devuelve `{usuario, tenant_id, rol}`; `DELETE /api/sesion` borra la cookie.
- **Toda la API exige sesión:** el resto de `/api/*` responde 401 sin cookie válida, antes de leer el cuerpo. La cookie solo vale si el usuario sigue en `usuarios.json` con el mismo `tenant_id` y rol.
- **Contexto:** el `tenant_id` sale solo de la cookie verificada; `Contexto(tenant_id, usuario)` del rol 2 no cambia.
- **Roles:** `analista` consulta, propone y guarda la lista; `lector` consulta y ve la lista, sin proponer, guardar ni cambiar (403).
- **Origen:** en POST, PATCH, PUT y DELETE, un `Origin` o `Referer` que no esté permitido da 403.
- **Original del PDF:** `GET /api/eventos/{evento}/documentos/{doc_id}/original`, solo si el documento es del evento y de la empresa de la sesión; si no, 404 sin distinguir la causa.
- **Auditoría:** un JSONL por día en `data/auditoria/` con login (los fallidos, con el usuario como HMAC), consultas, propuestas, cambios de lista y originales. Nunca lleva la pregunta, la respuesta, texto de PDF, contraseñas ni cookies.
- **Segunda empresa:** `empresa_b` (ficticia) tiene solo el evento 363-IGSS-2026, con `doc_id` y `chunk_id` propios porque son clave primaria.

## Comandos

```bash
make usuarios-demo     # crea, si faltan, la clave y los usuarios en keys/plataforma (no imprime contraseñas); FORZAR=1 los regenera
make empresa-b         # arma data/plataforma/empresa_b.zip y lo importa
make api               # API con sesión
make test-plataforma   # las de integración requieren make db-up, importar y empresa-b
```

## Usuarios de la demo

- `analista_demo`: empresa_demo, analista.
- `lector_demo`: empresa_demo, lector.
- `analista_b`: empresa_b, analista.

Las contraseñas están en `keys/plataforma/contrasenas_demo.txt`; ábrelo tú, no se imprimen. Nada de `keys/plataforma/` entra al repo. La contraseña se guarda con `hashlib.scrypt` (N=2^14, r=8, p=5, sal propia, máximo 2 derivaciones a la vez; un hash con parámetros anteriores se reescribe tras un login correcto).

## Variables de entorno

- `LICIGT_SESION_CLAVE_ARCHIVO`: clave de firma (por defecto `keys/plataforma/sesion.key`).
- `LICIGT_USUARIOS_ARCHIVO`: usuarios (por defecto `keys/plataforma/usuarios.json`).
- `LICIGT_CONTRASENAS_DEMO_ARCHIVO`: contraseñas de la demo (por defecto `keys/plataforma/contrasenas_demo.txt`).
- `LICIGT_SESION_HORAS`: vida de la cookie, en (0, 24]; por defecto 8. Un valor fuera de rango, `nan` o `inf` vuelve al defecto con un aviso en el log.
- `LICIGT_ORIGENES_PERMITIDOS`: orígenes separados por comas; reemplaza la lista por defecto, que es `http://127.0.0.1` y `http://localhost` con el puerto de `LICIGT_API_PUERTO` (8000) y con 5173 (Vite, `make web`).
- `LICIGT_AUDITORIA_DIR`: carpeta de la auditoría (por defecto `data/auditoria`).
- `LICIGT_PAQUETES_DIRS`: carpetas con los paquetes `<empresa>.zip` de los originales, separadas por `:` (por defecto `entregables/recuperacion` y `data/plataforma`).

## Límites declarados

- **Sin revocación al cerrar sesión:** la sesión no tiene estado en el servidor, así que `DELETE /api/sesion` solo borra la cookie del navegador; una cookie copiada sigue valiendo hasta que venza o hasta que se quite o cambie al usuario en `usuarios.json`, o se rote `sesion.key`.
- **Sin `Secure` en HTTP local:** la cookie no lleva `Secure` porque la demo corre en `http`. Debe activarse si se sirve por HTTPS.
- **Sin límite de intentos de login.**
- **Auditoría con un solo proceso:** el cerrojo que ordena las escrituras es de proceso; con varios procesos de uvicorn las líneas podrían intercalarse.
