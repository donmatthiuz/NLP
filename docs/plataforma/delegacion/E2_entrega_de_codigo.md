# Encargo E2: entrega de código reproducible

Rama `proyecto`. No commitees.

## Por qué (cinco porqués del gestor; plan aprobado por el usuario)

`docs/Pendientes.md` ("Entrega de código") pide:

- un README raíz con instalación y ejecución reproducibles;
- dependencias unificadas y un entorno sin credenciales;
- scripts de benchmark automatizados.

Hoy el `README.md` raíz solo dice "# NLP" y hay tres `requirements.txt` por módulo. Quien clone el repo (el docente o un evaluador) no sabe cómo levantarlo. Los benchmarks ya existen (`make evaluar`, `make banco`, `make reporte` y `make experimento-jev`), pero no están documentados juntos.

## Archivos

- `README.md` (raíz) y `requirements.txt` (raíz, nuevo).
- `Makefile`: objetivos nuevos y textos de ayuda; nada de lógica existente.
- `.env.example`: solo comentarios o variables que falten, sin valores secretos.
- Los README de módulo, solo para enlazarlos desde el raíz si les falta algo mínimo.
- **No toques** código de `src/` ni `web/src`.

## Qué hacer

### 1. Dependencias unificadas

- **`requirements.txt` raíz:** incluye los tres de módulo con `-r` y nada más, para que haya una sola fuente por módulo.
- **`make deps`:** instala Python (`pip install -r requirements.txt`) y la web (`pnpm --dir web install`).
- **Lo que no se instala así:**
  - la versión de Python, la de Node y pnpm, que se documentan;
  - el SDK de JEV, que es opcional, va por `make deps-consulta` y se documenta así.

### 2. README raíz

En español, Markdown sin emojis, listas con `-` y un solo `#`. Contenido:

- **Qué es LiciGT,** en tres líneas, con enlaces al anteproyecto, a `DESIGN.md` y a `docs/informe/`.
- **Requisitos:**
  - Linux o WSL2;
  - Docker con GPU de NVIDIA (opcional: sin GPU todo cae a CPU, más lento);
  - Python y Node con sus versiones;
  - pnpm;
  - unos 12 GB de disco para los modelos.
- **Puesta en marcha desde un clon limpio, paso a paso con los `make` reales:**
  - `setup`, `deps`, `db-up`, `llm-descargar`, `llm-servidor`, `importar`, `empresa-b`, `usuarios-demo`, `api` y `web`;
  - qué hace cada uno y cuánto tarda aproximadamente;
  - dónde quedan las contraseñas de la demo (`keys/plataforma/contrasenas_demo.txt`, que solo lee el usuario).
- **Pruebas:** `test-ingesta`, `test-recuperacion`, `test-consulta`, `test-consulta-sql` y `test-plataforma`, con qué necesita cada una.
- **Evaluación:** `evaluar`, `banco`, `reporte BANCO_COMUN=...` y `experimento-jev`, con qué produce cada uno y dónde (`data/...`, fuera del repo).
- **Estructura del repo** por rol, con un enlace a `docs/roles/Asignacion_de_roles.md`.
- **Seguridad:** credenciales en `keys/` (nunca en el repo), `make keys-status`, y que la demo usa datos ficticios (`empresa_demo` y `empresa_b`).
- **Limitaciones conocidas:** P95 de unos 25 s frente a la meta de 15 s, el modelo local de 9B y la cobertura parcial de la modificación del 222. Enlaza `docs/informe/`.

### 3. Verificación de reproducibilidad

- Clona el repo en una carpeta del scratchpad (`git clone` local del directorio, sin red) y sigue el README hasta donde no haga falta GPU, base ni red: `make setup`, `make deps` (puede usar el caché de pip y pnpm) y las pruebas que no requieren servicios.
- Reporta cada paso que falló o que el README no explicaba, y corrígelo en el README o en el Makefile.
- No copies `keys/` ni `data/` al clon.
- Borra el clon al terminar.

## Criterios de aceptación

- El README sirve desde cero: verificado en el clon.
- `make help` muestra los objetivos nuevos.
- `make test-consulta` sigue en verde en el repo.

## Reglas

- Sin `keys/`.
- No uses `make ... PYTHON=...` para correr scripts propios.
- Usa pnpm.
