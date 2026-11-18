# Encargo W1: inicio de sesión y original del PDF en la web

Para el implementador. Rama `proyecto`. No commitees.

Lee primero:

- [`AGENTS.md`](../../../AGENTS.md);
- [`web/DISENO.md`](../../../web/DISENO.md): es el contrato visual y se respeta;
- `web/src/api.ts`, `App.tsx`, `componentes/Fuentes.tsx`, `tipos.ts` y las pruebas de Vitest;
- `src/licigt/plataforma/README.md` y, en `src/licigt/consulta/api.py`, las rutas `/api/sesion` y `/api/eventos/{evento}/documentos/{doc_id}/original` (no las edites).

## Por qué (cinco porqués del gestor; plan aprobado por el usuario el 18 de noviembre)

- Desde P1 (commit `946d228`), toda ruta `/api/*` salvo `/api/sesion` exige una cookie de sesión. La web no inicia sesión, así que todas sus llamadas dan 401 y la demo no funciona.
- La web todavía lee la cabecera `X-LiciGT-Autenticacion` del adaptador sin autenticación, que ya no existe.
- La demo del curso pide trazabilidad de citas. Cada fuente ya muestra documento y página, pero no permite abrir el original. El endpoint del original ya existe y solo sirve documentos de la empresa de la sesión.

## Archivos

- `web/src` y sus pruebas.
- `web/DISENO.md`, solo para agregar las secciones de la pantalla de sesión y del enlace al original.
- No toques el backend.

## Cambios (prueba en rojo primero, con Vitest y dobles de `fetch`)

### 1. Sesión

- **Al cargar:** `GET /api/sesion`.
  - Con 200, se muestra la aplicación con el usuario, su empresa y su rol en la cabecera, junto a un botón "Cerrar sesión" que llama a `DELETE /api/sesion`.
  - Con 401, una pantalla de inicio de sesión: usuario y contraseña con `<label>`, el botón, el mensaje de error genérico del servidor y nada más.
- **Las llamadas:** `fetch` same-origin. La cookie es `HttpOnly`, así que la web nunca la lee ni la guarda, y no guarda la contraseña en ningún almacenamiento.
- **Si una llamada a `/api` da 401 a mitad de uso:** vuelve a la pantalla de inicio de sesión y conserva la pregunta escrita.
- **Si da 403** (un `lector` que intenta proponer, guardar o cambiar la lista): un mensaje claro, "Su rol no permite modificar la lista", y no una falla genérica. Si la sesión dice `rol: lector`, los botones de proponer, guardar y cambiar estado se muestran deshabilitados con esa explicación.
- **Lo que se quita:** todo uso de la cabecera `X-LiciGT-Autenticacion` y de `sinAutenticacion`.
- **Modo ejemplos:** sin `VITE_MODO=api` sigue funcionando sin sesión, con los ejemplos.

### 2. Original del PDF en cada fuente

- **El enlace:** en cada tarjeta de fuente (`Fuentes.tsx`), "Ver original, p. N", que abre `/api/eventos/{evento}/documentos/{doc_id}/original#page=N` en una pestaña nueva, con `rel="noopener"`.
- **El `doc_id`:** sale de la fuente y no se arma con texto del usuario.
- **En modo ejemplos** el enlace no aparece.
- **Pruebas:** el enlace lleva el `doc_id` y la página de la fuente, y no aparece en modo ejemplos.

### 3. Diseño

- La pantalla de sesión y el enlace siguen las variables CSS, el tema claro y oscuro, el contraste y el ancho mínimo de 320 px de `DISENO.md`.
- Documenta las dos piezas en `DISENO.md`.

## Criterios de aceptación

- `pnpm --dir web test` y `pnpm --dir web build` en verde (usa pnpm, nunca npm ni npx).
- `make test-consulta` sin cambios, porque no tocas el backend.
- **Prueba manual, si puedes:** levanta la API con `make api LICIGT_API_PUERTO=8010` y la web con `VITE_MODO=api LICIGT_API_PUERTO=8010 pnpm --dir web dev --port 5199 --strictPort`.
  - Comprueba que sin sesión aparece el inicio de sesión.
  - No puedes leer las contraseñas de la demo, así que la prueba con sesión la hace el gestor. Basta con que lo dejes listo.

## Al terminar

Responde con:

- los archivos tocados;
- las pruebas;
- las capturas, si las tomaste;
- las decisiones donde el encargo no era claro.

No amplíes el alcance. Sin `keys/`.
