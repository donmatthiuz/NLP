# LiciGT

Proyecto final de CC3103 (UVG): un sistema RAG que analiza licitaciones de medicamentos del IGSS y responde con citas verificables (documento, página, versión y fragmento). Cuando no hay evidencia suficiente se abstiene, y ante una contradicción pide revisión humana en lugar de decidir qué documento está vigente.

- Documentación completa: [`docs/anteproyecto/Anteproyecto.md`](docs/anteproyecto/Anteproyecto.md).
- Decisiones de diseño: [`DESIGN.md`](DESIGN.md).
- Informe y resultados: [`docs/informe/`](docs/informe/).
- Lo que falta: [`docs/Pendientes.md`](docs/Pendientes.md).

## Requisitos

- Linux o WSL2 (Ubuntu). Se desarrolló en WSL2.
- Docker con Compose, para Postgres con pgvector y, si el sistema no tiene GLIBC suficiente, para el LLM local.
- GPU de NVIDIA con CUDA (opcional). Sin GPU, la recuperación y el LLM caen a CPU, más lento. El LLM local se probó en una RTX 5070.
- Python 3.12 o superior con `venv` (`shell.nix` fija 3.12; se verificó también con 3.14).
- Node 22 o superior y pnpm 10 (solo para la web). No uses `npm` ni `npx`.
- Unos 12 GB de disco para los modelos (`models/`: bge-m3, reranker y GGUF del LLM) y `tools/` (llama.cpp).
- `poppler-utils` solo si vas a regenerar el corpus desde los PDF.

## Puesta en marcha desde un clon limpio

Todo se hace desde la raíz del repo. `make help` lista los objetivos.

```bash
git clone <url-del-repo> licigt && cd licigt
python3 -m venv .venv                 # el Makefile usa .venv/bin/python si existe
make setup
make deps
```

- `make setup` (segundos): crea `.env` desde `.env.example` (sin pisarlo) y las llaves de `keys/`: genera la contraseña de la base y deja vacías las de proveedores. `make keys-status` dice cuáles faltan sin abrirlas.
- `make deps` (varios minutos, descarga torch): instala las dependencias de Python de `requirements.txt` (que incluye los tres `requirements.txt` de módulo, con el SDK de JEV) y las de la web con `pnpm --dir web install --frozen-lockfile`. Si usas la caché de pip y pnpm, tarda mucho menos.

Los pasos siguientes necesitan Docker, red para la primera descarga y, el LLM, GPU:

```bash
make db-up                            # Postgres con pgvector en 127.0.0.1:5432 (segundos)
make llm-descargar                    # llama.cpp b12441 y el GGUF del LLM, unos 6 GB (según la red)
make llm-servidor                     # llama-server en 127.0.0.1:8080; en primer plano (nativo) o en Docker; usa otra terminal
make importar                         # paquete de ingesta a Postgres; la primera vez baja bge-m3 y el reranker a models/ (minutos)
make empresa-b                        # empresa ficticia empresa_b con el evento 363, para probar el aislamiento (segundos)
make usuarios-demo                    # clave de sesión y usuarios de la demo en keys/plataforma (segundos)
make api                              # API en 127.0.0.1:8000 (LICIGT_API_PUERTO)
make web                              # web en http://127.0.0.1:5173 en modo API, con proxy de /api (otra terminal)
```

- `make llm-estado` muestra el binario, el modelo, la VRAM y el servidor; `make llm-detener` detiene el contenedor del modo Docker; `make db-down` detiene Postgres sin borrar datos.
- `make importar` lee `entregables/recuperacion/empresa_demo.zip`. Ese paquete lo produce la ingesta (rol 1); no se edita a mano.
- Las contraseñas de la demo quedan en `keys/plataforma/contrasenas_demo.txt`. `make usuarios-demo` no las imprime: ábrelo tú. Usuarios: `analista_demo` y `lector_demo` (empresa_demo) y `analista_b` (empresa_b).
- Si el volumen de Postgres se creó con otra contraseña, `make db-password-sync` la alinea con la de `keys/` sin borrar datos.
- `make web-ejemplos` levanta la web con respuestas fijas de ejemplo, sin API, base ni LLM (versión sin servicios). Para la demo completa: `make api` y `make web`, con los usuarios de `make usuarios-demo`.
- `make web-build` compila la web (`tsc` y `vite build`). `make buscar Q="fecha de recepción de ofertas"` prueba la recuperación sin la API.
- El enrutador usa `reglas` por defecto (`LICIGT_ENRUTADOR` en `.env`). Solo `jev` y los objetivos `sondeo-jev` y `experimento-jev` llaman a JEV y piden `keys/jev/api.key`; todo lo demás funciona sin llaves de proveedores.

## Pruebas

| Objetivo | Qué necesita |
| --- | --- |
| `make test-ingesta` | Solo `make deps` (145 pruebas, unos 20 s). |
| `make test-consulta` | Solo `make deps`: sin red, GPU ni base de datos (usa dobles de `buscar()` y del LLM). |
| `make test-recuperacion` | Red en la primera corrida (baja a `models/` el modelo paraphrase-multilingual-MiniLM-L12-v2 que usan las pruebas unitarias, unos 450 MB). Las de integración requieren `make db-up` y `make importar`; sin ellos se saltan. |
| `make test-consulta-sql` | `make db-up` (la lista de verificación en Postgres; antes `make lista-schema` si las tablas no existen). |
| `make test-plataforma` | Las unitarias solo piden `make deps`. Las de integración requieren `make db-up`, `make importar` y `make empresa-b`. |

## Evaluación

Todo queda en `data/`, que Git ignora. Los resultados se reportan como se miden; las metas del anteproyecto no son resultados.

- `make evaluar`: Hit@5, MRR@5, suficiencia y latencia de la recuperación base y mejorada con los casos de desarrollo del rol 2. Requiere `db-up` e `importar`. Imprime en pantalla.
- `make banco`: corre el banco de casos del rol 3 de punta a punta con los servicios reales (requiere `db-up`, `importar` y el LLM). Guarda en `data/consulta/banco`. Con `RUTA=archivo.json` corre otro banco.
- `make reporte BANCO_COMUN=ruta/banco.json`: reporte de evaluación del rol 4 (recuperación base y mejorada, banco de punta a punta, P95 con 1 y 5 usuarios, tokens y suite de seguridad). Requiere `db-up`, `importar`, `empresa-b` y el LLM; `BANCO_COMUN` es opcional y, si falta o no existe, se omite con un aviso. Guarda en `data/plataforma/reporte`.
- `make experimento-jev CONJUNTO=desarrollo`: compara el enrutador de reglas con JEV. Sin `CONFIRMAR=1` solo muestra lo previsto; con `CONFIRMAR=1` envía a JEV el texto de las preguntas (requiere `keys/jev/api.key`). Guarda en `data/consulta/experimentos`. Detalle en [`docs/consulta/Experimento_JEV.md`](docs/consulta/Experimento_JEV.md).

## Estructura

- `src/licigt/ingesta`: rol 1. PDF, extracción, fragmentos y versiones.
- `src/licigt/recuperacion`: rol 2. Índices pgvector y tsvector, búsqueda y alertas.
- `src/licigt/consulta`: rol 3. Enrutador, herramientas, respuesta con citas y lista de verificación.
- `src/licigt/plataforma`: rol 4. API, autenticación, auditoría y evaluación.
- `web/`: interfaz web (React, Vite, TypeScript, pnpm); su contrato es [`web/DISENO.md`](web/DISENO.md).
- `entregables/recuperacion`: paquete de ingesta que consume la recuperación.
- `docs/<módulo>`: planes y resultados de cada rol. Responsabilidades en [`docs/roles/Asignacion_de_roles.md`](docs/roles/Asignacion_de_roles.md).
- `docker-compose.yml`, `docker/`, `scripts/`: Postgres, el LLM en Docker y los scripts del `Makefile`.

Cada módulo tiene su propio README en `src/licigt/<módulo>/README.md`.

## Seguridad

- Las credenciales viven en `keys/`, un archivo por llave, y nunca en el repo ni en `.env`. `.env` solo lleva parámetros sin secretos.
- `make keys-status` dice qué llaves faltan sin mostrarlas; `make key-set FILE=keys/jev/api.key` guarda una sin imprimirla. Ver [`keys/README.md`](keys/README.md).
- La demo usa datos ficticios o públicos: `empresa_demo` (licitaciones públicas del IGSS) y `empresa_b` (ficticia, para el aislamiento entre empresas).
- El `tenant_id` sale solo de la sesión autenticada; los fragmentos recuperados se tratan como datos, nunca como instrucciones.

## Limitaciones conocidas

Cifras de la corrida oficial `20261119T061552Z` (commit `3085334`, [`Reporte_evaluacion.md`](docs/plataforma/Reporte_evaluacion.md)). Se tomó con la GPU de escritorio compartida (RTX de 12 GB en Windows y WSL2): el LLM generó a una mediana de 62,5 tokens por segundo, contra 86 en la corrida previa `20261119T042331Z` (P95 de 18,5 s, solo como referencia de sensibilidad al hardware, no como resultado).

- Latencia: el P95 total es de 32,0 s con un usuario (`buscar_documentos` 18,5 s, `comparar_versiones` 15,1 s, `extraer_requisitos` 39,1 s) y de 37,5 s con 5 simultáneos, sin violaciones de aislamiento. No cumple la meta de 15 s del anteproyecto. Costo: 0,75 llamadas al LLM, 3 938 tokens de entrada y 286 de salida por consulta.
- Banco del rol 3: cumplen 19 de 23. Banco común: cumplen 11 de 20 (4 abstenciones indebidas, 2 fallos de recuperación, 3 de enrutador y 1 espera agotada del generador). Suite de seguridad: 8 de 8, que no implica seguridad universal.
- Recuperación (mejorada): Hit@5 de 1,000 y MRR@5 de 0,900 en desarrollo; Hit@5 de 0,875 y MRR@5 de 0,512 en el banco común.
- El LLM local es de 9B parámetros (Qwen3.5-9B cuantizado), que cabe en la GPU de desarrollo pero limita la calidad de redacción: a veces se abstiene con evidencia suficiente.
- Cobertura parcial en el evento 222: la página 4 de la Modificación 1 es un escaneo cuyo OCR solo da ruido y no se indexa, y el anexo de 11 hojas que menciona no viene en el PDF publicado; el sistema lo avisa y pide revisión humana.
- Sin medir: fidelidad factual, cobertura de requisitos y tiempo de revisión con usuarios.
- Detalle y cifras en [`docs/informe/`](docs/informe/) y [`docs/Pendientes.md`](docs/Pendientes.md).
