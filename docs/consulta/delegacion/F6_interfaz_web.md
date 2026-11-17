# Encargo F6: interfaz web y demo con el evento 222

Para Codex u OpenCode, más los agentes de diseño de `.agentes/`. Rama `rol/consulta`. El gestor auditará cada parte; no commitees.

Lee primero:

- [`AGENTS.md`](../../../AGENTS.md), sobre todo "Reglas que no se negocian" y "Agentes con rol";
- [`DESIGN.md`](../../../DESIGN.md), secciones "Stack" e "Interfaz de usuario";
- [I3](../investigacion/I3_lista_e_interfaz.md), preguntas 3, 4 y 5: es el diseño de este encargo;
- [`Contratos.md`](../Contratos.md), "Rol 4 hacia rol 3" y "Rol 3 hacia el usuario";
- `src/licigt/consulta/esquemas.py` (`Fuente` y `RespuestaEstructurada`, con la aclaración) y `orquestador.consultar`.

## Decisiones para el visto bueno del usuario

Lo que sigue no tiene respaldo directo en el repositorio ni en el curso. Cada punto trae la opción recomendada; si el usuario no dice otra cosa, se aplica esa.

1. **El adaptador de consulta se hace ya, no al cerrar F5.**
   - El plan dice que el adaptador va solo si el rol 4 no entrega la API al cerrar F5 (`Plan_rol_3.md:92`).
   - Pero la ruta de consulta no depende de F5, y sin ella la web no se puede probar de punta a punta con el LLM y la búsqueda reales.
   - **Recomendado:** escribir ahora solo la ruta de consulta (parte F6c), marcada como reemplazable. Las rutas de la lista esperan al contrato de F5 (parte F6d).
2. **Dónde va el adaptador:** **recomendado** `src/licigt/consulta/api.py`, el valor por defecto de I3 (pregunta 1 para el usuario). No se toca `src/licigt/plataforma`.
3. **Carpeta del frontend:** **recomendado** `web/` en la raíz, con una línea nueva en la sección "Estructura" de `AGENTS.md` (I3, pregunta 2 para el usuario).
4. **Sin CLI propia.** I3 recomendaba primero una CLI, pero el usuario eligió la web desde el inicio (`Plan_rol_3.md:89`).
   - **Recomendado:** sin CLI; la demo va por la web.
   - Si la web falla el día de la demo, el respaldo es `make buscar` más la API con `curl`. No se escribe código extra para eso.
5. **Sin librería de componentes ni de estilos.** **Recomendado:** CSS propio con variables, para que el diseño lo fijen los agentes de diseño y no una librería. Ni Tailwind, ni MUI, ni shadcn.
6. **Pruebas de la web:** **recomendado**:
   - `tsc` sin emitir y `vite build`;
   - pruebas con Vitest solo de la función pura que decide qué panel mostrar;
   - sin pruebas de componentes con DOM.

## Origen

- **Curso:** pide una demo en vivo, no una interfaz web (I3, pregunta 3).
- **Anteproyecto:** promete una interfaz en español, con acceso al original y la lista editable (`Anteproyecto.md:146`, `:222` y `:328`).
- **Asignación:** al rol 3 le toca "mostrar"; al rol 4, la API y la autenticación (I3, pregunta 5).
- **Decisión del 16 de noviembre:** web desde el inicio, con React, Vite y TypeScript y pnpm, sobre FastAPI (`Plan_rol_3.md:89`).

## Versiones verificadas (17 de noviembre de 2026)

Consultadas con `pnpm view`, `pip index versions` y Context7 (`/vitejs/vite/v8.3.5`, `/websites/fastapi_tiangolo`):

| Paquete | Versión | Nota |
|---|---|---|
| `vite` | 8.3.8 | requiere Node `^20.19.0 \|\| >=22.12.0`; la máquina tiene Node 22.17.0 |
| `create-vite` | 9.3.4 | plantilla `react-ts` |
| `react` y `react-dom` | 19.3.1 | |
| `@vitejs/plugin-react` | 6.3.0 | |
| `typescript` | 7.0.2 | si la plantilla trae otra versión, se queda la de la plantilla |
| `vitest` | 5.1.0 | |
| `fastapi` | 0.163.1 | `TestClient` y `app.dependency_overrides` para las pruebas |
| `uvicorn` | 0.54.0 | |

- **Versiones exactas:** se fijan en `web/package.json` y en `pnpm-lock.yaml`, sin `^`, porque en Python solo hay rangos y fijarlos le corresponde al rol 4 (`docs/plataforma/Avisos_del_rol_3.md`, "Dependencias fijadas").
- **Python:** en `src/licigt/consulta/requirements.txt` van rangos: `fastapi>=0.163,<0.164` y `uvicorn>=0.54,<0.55`.
- **Herramientas:** solo `pnpm create`, `pnpm install`, `pnpm exec` y `pnpm dlx`. Nunca npm ni npx.

## Partes y paralelismo

| Parte | Quién | Archivos que son suyos | En paralelo con |
|---|---|---|---|
| F6a Contrato de diseño | `design-ux-architect` y `design-ui-designer` | `web/DISENO.md` | F5, F6c |
| F6b Vista de consulta con ejemplos | implementador (Codex u OpenCode) | `web/` salvo `DISENO.md`; `src/licigt/consulta/tests/test_ejemplos_web.py`; línea de "Estructura" en `AGENTS.md` | F5, F6c (empieza cuando F6a está escrita) |
| F6c Adaptador de consulta | implementador | `src/licigt/consulta/api.py`, `tests/test_api.py`, `requirements.txt` de consulta, objetivos `api` y `web` del `Makefile` | F5, F6a, F6b |
| F6d Vista y rutas de la lista | implementador | lo que F5 deje como contrato | después de F5 |
| F6e Guion de la demo y compuerta | gestor, usuario y `design-ui-finish-gate-reviewer` | `docs/consulta/Demo_222.md` | al final |

- **Límites con F5:** F5 no toca `web/`, `api.py`, `Makefile` ni `requirements.txt`; F6 no toca los módulos de la lista, el SQL de la lista, `herramientas.py` ni `esquemas.py`.
- **Si una parte necesita un archivo ajeno:** se detiene y lo reporta.

## F6a: contrato de diseño (agentes de diseño)

`DESIGN.md:45` dice que la identidad visual no está definida, y el revisor de compuerta valida contra un contrato escrito. Por eso el diseño va primero y por escrito.

- **`design-ux-architect`:** arquitectura de la página única. Cubre:
  - las zonas de la página: encabezado con el evento, caja de pregunta, panel de resultado, fuentes y, más tarde, la lista;
  - los cuatro estados del resultado;
  - el orden de lectura, el teclado y el ancho mínimo;
  - las variables CSS: color, espacio y tipografía, con el contraste mínimo AA.
- **`design-ui-designer`:** la apariencia de los componentes sobre esas variables:
  - el panel por estado;
  - la tarjeta de fuente;
  - la banda de revisión humana;
  - el aviso de cobertura;
  - el aviso fijo.
- **Requisitos que el contrato debe cubrir (de `DESIGN.md:47-53` y `Anteproyecto.md:328`):**
  - aviso fijo siempre visible: "La respuesta se basa en los documentos cargados del evento";
  - cuatro estados que se distinguen sin depender solo del color (texto, ícono o forma): respuesta, abstención, revisión humana y aclaración;
  - cada fuente con documento, página o rango (`page`, `page_end`), versión de ingesta, versión oficial, cita literal y enlace al original;
  - contradicciones con las dos fuentes lado a lado y la frase "El sistema no decide cuál está vigente";
  - `coverage_status = "parcial"` y `warnings` visibles, nunca escondidos;
  - en abstención, la frase de que la ausencia en los documentos cargados no prueba que no exista en el expediente (`DESIGN.md:10`);
  - todo en español.
- **Salida:** `web/DISENO.md` con zonas, estados, variables y un boceto en texto de cada estado. Sin código.
- **Visto bueno:** el gestor lo revisa antes de que arranque F6b.

## F6b: vista de consulta contra respuestas de ejemplo

- **Proyecto:** `pnpm create vite web --template react-ts`, con las versiones de la tabla.
  - `server.proxy` envía `/api` a `http://127.0.0.1:8000` (documentación de Vite, `server.proxy`), así que no hace falta CORS en desarrollo.
  - `web/.gitignore` ignora `node_modules` y `dist`.
- **Tipos:**
  - `web/src/tipos.ts` copia a mano `Fuente` y `RespuestaEstructurada` de `esquemas.py`, con los mismos nombres de campo;
  - un comentario de una línea apunta al archivo de origen.
- **Ejemplos:** `web/src/ejemplos/` con cinco JSON, uno por escenario de la demo del 222 (I3, pregunta 4):
  - respondible con fuentes;
  - abstención;
  - comparación con `needs_human_review` y dos fuentes;
  - aclaración;
  - cobertura parcial con los avisos de las páginas 3 y 4.
  - Usa `chunk_id`, páginas, versiones, `source` y citas reales tomadas de `entregables/recuperacion/empresa_demo.zip`. No las inventes.
- **Prueba que amarra los ejemplos al esquema:** `src/licigt/consulta/tests/test_ejemplos_web.py` valida cada JSON con `RespuestaEstructurada.model_validate`.
  - Así, si F4 o F5 cambian el esquema, la prueba falla.
  - Corre dentro de `make test-consulta`, sin red.
- **Selector de ejemplos:**
  - con `VITE_MODO=ejemplos` (por defecto, en desarrollo) la página ofrece el selector y no llama a la API;
  - con `VITE_MODO=api` envía `POST /api/eventos/{evento_id}/consultas` con `{"pregunta": ...}`.
- **Función pura `estadoDe(respuesta)`:**
  - devuelve `respuesta`, `abstencion`, `revision` o `aclaracion`, con la precedencia aclaración, abstención, revisión y respuesta;
  - tiene pruebas con Vitest con los cinco ejemplos.
- **Seguridad, porque los fragmentos son datos no confiables (`AGENTS.md:58`):**
  - `answer`, `cita` y `warnings` se pintan como texto, nunca con `dangerouslySetInnerHTML`;
  - el enlace al original solo se pinta si `source` empieza con `https://`; si no, se muestra el `doc_id` sin enlace;
  - ningún campo de la página ni de la petición lleva `tenant_id` (`AGENTS.md:57`).
- **Objetivos del `Makefile`:** no los escribe esta parte; los escribe F6c.

## F6c: adaptador FastAPI de consulta (reemplazable)

- **Archivo:** `src/licigt/consulta/api.py`. Comentario inicial de una línea: adaptador de desarrollo, reemplazable por la API del rol 4, sin autenticación.
- **Una sola ruta, por ahora:**
  - `POST /api/eventos/{evento_id}/consultas`, con cuerpo `{"pregunta": str}` (1 a 500 caracteres) y `response_model=RespuestaEstructurada`;
  - FastAPI rechaza una salida que no cumpla el modelo: es una segunda barrera además del validador.
- **Contexto de acceso:**
  - sale de una dependencia `contexto_demo()`, que devuelve `Contexto(tenant_id="empresa_demo", usuario="demo")`;
  - el cuerpo y la ruta nunca aceptan `tenant_id`;
  - la respuesta HTTP añade la cabecera `X-LiciGT-Autenticacion: ninguna-demo`, y la web la muestra como aviso.
- **Dependencias reales, construidas una sola vez:**
  - `crear_enrutador()`, que lee su variante de la configuración;
  - el módulo `licigt.recuperacion.busqueda` como recuperador, porque ya cumple el protocolo `Recuperador`;
  - `ClienteGeneradorOpenAI()`.
  - Cada una se puede sustituir con `app.dependency_overrides`.
- **Fallas:** una falla de herramienta o del LLM no es un error HTTP. Llega como `RespuestaEstructurada` con abstención, porque así la devuelve `consultar`. Sin sesión simulada no hay 401: no hay autenticación.
- **Sin CORS:** el proxy de Vite lo evita. Escucha en `127.0.0.1:8000`, nunca en `0.0.0.0`.
- **Pruebas en `tests/test_api.py`, con `TestClient` y `dependency_overrides`, sin red, GPU ni base:**
  - una respuesta respondible y una abstención;
  - un cuerpo con `tenant_id` da 422 (el modelo del cuerpo prohíbe campos extra);
  - una pregunta de 501 caracteres da 422;
  - la cabecera de demo está presente.
- **`Makefile`:**
  - `api` arranca `uvicorn licigt.consulta.api:app --host 127.0.0.1 --port 8000` con `WITH_DB`;
  - `web` corre `pnpm --dir web dev`;
  - `web-build` corre `pnpm --dir web build`;
  - cada objetivo con su ayuda en español.
- **Requisitos:** `fastapi` y `uvicorn` en `src/licigt/consulta/requirements.txt`, con los rangos de arriba. Si `fastapi` no está instalado, `test_api.py` se salta con un mensaje que dice `make deps-consulta`, para no romper `make test-consulta` en una máquina sin dependencias.

## F6d: lista de verificación en la web (después de F5)

Se redacta al cerrar F5, con su contrato: `PropuestaLista`, `ItemLista` y las rutas de guardar y cambiar estado con `confirmado: true` (I3, pregunta 3). Queda fijado desde ahora:

- guardar y cambiar estado exigen un clic aparte, con un resumen de lo que se va a guardar (`AGENTS.md:62`);
- la página dice que los estados no certifican cumplimiento (`DESIGN.md:53`).

## F6e: guion de la demo y compuerta final

- **Guion:** `docs/consulta/Demo_222.md` con los seis pasos de `Plan_rol_3.md:93`, la pregunta exacta de cada uno y lo que debe verse.
  - La pregunta sin evidencia se elige comprobando antes la abstención con `make buscar` (I3, pregunta 4).
- **Corrida real:** la hace el usuario, con `make db-up`, `make importar`, `make llm-servidor`, `make api` y `make web`.
- **Aclaración sin memoria** (decisión del 17 de noviembre): cuando la respuesta pide aclaración, la web conserva la pregunta original en el cuadro, con el cursor al final y la pregunta aclaratoria visible, para que el usuario la complete y la envíe de nuevo. El backend no guarda nada entre preguntas.
- **Compuerta:** `design-ui-finish-gate-reviewer` revisa la página corriendo en los cinco estados contra `web/DISENO.md` y devuelve PASS o HOLD. No edita. Con HOLD, el implementador corrige y se repite la revisión.

## Criterios de aceptación

- `make test-consulta` en verde, con `test_ejemplos_web.py` y `test_api.py` incluidas.
- En `web/`, sin errores:
  - `pnpm exec tsc --noEmit`;
  - `pnpm exec vitest run`;
  - `pnpm build`.
- Los cinco ejemplos se ven con su estado correcto y cumplen el contrato de F6a.
- Ningún `tenant_id` en la web ni en el cuerpo de la API; ningún HTML sin escapar; enlaces solo `https://`.
- No hay archivos tocados fuera de los asignados a cada parte.

## Al terminar

Cada parte responde con:

- los archivos tocados;
- la salida resumida de las pruebas y del build;
- capturas o la descripción de cada estado (F6b);
- las decisiones donde el encargo no era claro.

No amplíes el alcance.
