# Encargo F6f: hallazgos de la compuerta de diseño

Para el implementador. Rama `rol/consulta`. No commitees.

Lee primero:

- [`AGENTS.md`](../../../AGENTS.md);
- `web/DISENO.md` completo;
- [F6d](F6d_lista_en_la_web.md) y [C16](C16_novena_pasada_y_demo.md) (panel de documentos);
- `web/src/`, con sus pruebas de Vitest.

## Origen

La compuerta de diseño (F6e) revisó la web con la API y el LLM reales y dio HOLD por dos hallazgos mayores. Las capturas están en el scratchpad del gestor, en `r4m/` (`f6e_*.png` y `gate_*.png`).

## Archivos

- Solo `web/src/` (código, estilos y Vitest) y `web/DISENO.md`.
- No toques `src/licigt`: otros agentes trabajan ahí en paralelo.
- No cambies el contrato de la API.

## Cambios (prueba en rojo primero)

### M1 (mayor): la revisión sin fuentes no inventa un motivo

- **Problema:** con `sources` vacío, `motivoRevision` (`estado.ts`) usa la rama de "un solo documento" y dice que un dato es ambiguo o está desactualizado, y habla de vigencia.
- **Cambio:** con cero fuentes, el texto es neutro: "El sistema marcó esta consulta para revisión humana; revise los documentos originales.", sin ambigüedad ni vigencia.
- **Prueba:** un caso en `estado.test.ts`.

### M2 (mayor): cada cita dice de qué documento viene

- **Problema:** las fuentes y los ítems de la lista muestran solo el hash del documento, y el panel de documentos muestra el tipo, pero nunca el `doc_id`.
- **Cambio:**
  - sube a `App` los documentos que ya se cargan para el panel y arma un mapa `doc_id → tipo_documento`;
  - muestra el tipo antes del hash en la cabecera de cada columna del conflicto, en el título de cada tarjeta de fuente y en el origen de cada ítem de la lista (por ejemplo "Bases · 03791a…" o "Modificación · d41480…");
  - el nombre accesible de cada columna incluye el tipo;
  - en el panel, muestra el `doc_id` en monoespaciada y `--texto-sm` en cada tarjeta;
  - si el mapa no tiene el documento (modo ejemplo o falla de carga), se muestra solo el hash, como hoy.
- **Pruebas:** Vitest de Fuentes, de la lista y del panel con y sin el mapa.

### m1: rótulo repetido en la revisión

En `Resultado.tsx`, el `<strong>` "Requiere revisión humana." no se repite cuando el estado es `revision`, porque ya está en el `h2`. Se mantiene en la abstención y en la aclaración.

### m2: contrato al día

Actualiza `web/DISENO.md`:

- documenta el panel "Documentos del evento" (posición, resumen, faltantes y estados de carga y error);
- describe la lista tal como quedó implementada, sin decir "reservada" ni "fuera de esta versión";
- añade la regla de M2 (tipo antes del hash).

### m3: faltantes sin repetir

En el panel, la lista "Falta información" muestra solo las advertencias del documento (`cobertura.ts`). Las páginas sin indexar y el estado ya aparecen en la línea de resumen.

### m4: título de las bases

La tarjeta de un documento sin versión oficial se titula con su tipo, por ejemplo "Bases", y "Versión oficial no indicada" pasa a texto secundario.

### m5: la cita de la lista es la cita

- Dentro del `blockquote` de cada ítem va la cita de su fuente (`fuentes[0].cita`), con el mismo tratamiento de ` | ` que en la tarjeta de fuente.
  - Decide uno: ` | ` tal cual en los dos lugares, o `: ` en los dos.
  - Que la misma frase se vea igual en las dos vistas.
- En los ítems de fecha, la etiqueta de la actividad (la parte de `descripcion` antes de la cita) va fuera de la cita, como `.etiqueta` o como prefijo, para que no parezca texto del documento.
- Lo guardado no cambia.

### m6: tamaño de las etiquetas

`.etiqueta` usa `--texto-sm`. `--texto-xs` queda solo para los contadores, como dice `DISENO.md`.

### m7: casillas con nombre propio

Cada casilla "Incluir" de la lista se anuncia con su ítem, por ejemplo con `aria-describedby` hacia un `id` del `blockquote`.

## Verificación

- `pnpm --dir web test` (Vitest) y `pnpm --dir web build` en verde.
- `make test-consulta` en verde: `test_ejemplos_web` valida los ejemplos.
- La web está levantada en `http://127.0.0.1:5199`, en modo API y con recarga en caliente. Si tienes herramientas de navegador, comprueba:
  - una pregunta fuera de alcance (M1);
  - "¿Cuál es la fecha de recepción de ofertas?" (M2);
  - la propuesta de lista, sin guardarla;
  - todo a 1366 y a 320 px, en tema claro y oscuro, sin desplazamiento horizontal.

## Al terminar

Responde con:

- los archivos tocados;
- los resultados de las pruebas;
- las capturas, si las tomaste;
- las decisiones donde el encargo no era claro.

No amplíes el alcance.
