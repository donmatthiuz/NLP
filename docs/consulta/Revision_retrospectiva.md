# Revisión retrospectiva de los cuatro roles

Pedida por el usuario el 18 de noviembre de 2026 (`docs/Pendientes.md`, rol 3). Aplica a lo ya hecho el mismo criterio que se exige a los cambios nuevos: cinco porqués con evidencia del repositorio, diseño, buenas prácticas y visión del sistema completo.

## Cómo se hizo

- **Agentes:** cuatro agentes `five-whys` de solo lectura, uno por área:
  - ingesta;
  - consulta;
  - recuperación y plataforma;
  - web, documentos y proceso.
- **Material:** cada uno leyó los encargos, el código y las mediciones (`docs/plataforma/Reporte_evaluacion.md`, `docs/consulta/Demo_222.md`, `docs/consulta/Experimento_JEV.md` y `docs/recuperacion/Recuperacion.md`) y corrió las pruebas sin servicios.
- **Veredicto por decisión:**
  - `bien`, `mal`, `mejorable` o `escalar` (falta una decisión escrita del usuario);
  - con una acción: mantener, corregir o declarar.
- **Escalamiento:** lo que no tiene respuesta en el repositorio se presenta al usuario con opciones y una recomendación.

## Resumen

| Área | Decisiones | Bien | Mejorable | Mal | Escalar |
|---|---|---|---|---|---|
| Ingesta (R1 a R6, ids, C20 en la ingesta, muestreo) | 12 | 7 | 2 | 1 | 2 |
| Consulta (F1 a F7, C14 a C20, B1, banco, JEV) | 18 | 7 | 6 | 0 | 5 |
| Recuperación y plataforma (R2C, P1, I1, E1, E2, banco común) | 19 | 11 | 7 | 0 | 1 |
| Web, documentos y proceso (F6, W1, W2, informe, flujo) | 20 | 7 | 7 | 0 | 6 |

**Lo que está bien y medido:**

- **Validador de citas:** "seleccionar, no generar", con un validador determinista que falla cerrado. Las 45 citas publicadas son válidas: la verificación es que cada `chunk_id` pertenezca a la evidencia, no que la cita respalde la afirmación.
- **Vigencia:** nunca se decide cuál documento rige.
- **Herramientas y lista:** las herramientas son de solo lectura y la lista se arma sin LLM y se guarda solo con confirmación explícita.
- **Experimento de JEV:** se fijó antes de correrlo, a ciegas, y se respetó sin cambiar la regla.
- **Banco común:** sus fallos no se corrigieron, porque es el conjunto de prueba.
- **Ingesta:** R1 a R6 corrigieron defectos medidos.
- **Seguridad:** la sesión, las contraseñas, la comprobación del Origin y los originales.
- **Recuperación:** en GPU con fp16, sin pérdida de calidad.
- **Rediseño de la web** con shadcn/ui.

**El único defecto de código ("mal"):** el filtro de ruido del OCR (`MIN_PALABRAS_OCR`) solo se aplica en `reextraer.py`. Por `ingest()`, `reprocess()`, la línea de comandos y el conector, el ruido de un PDF escaneado nuevo se indexaría. En una simulación sobre las páginas de la modificación, 35 de 35 fragmentos quedaron indexables. No afecta al corpus actual.

## Hallazgos por área

### Ingesta

| Decisión | Veredicto | Acción | Evidencia clave |
|---|---|---|---|
| R1: reextracción con OCR sobre el ZIP | bien | mantener | `reextraer.py`; `corpus_igss.json` (Tesseract 4.1.1) |
| R1: tipo documental explícito en el conector | bien | mantener | `automatic.py:183-190` y sus pruebas |
| R2: corpus reproducible | mejorable | declarar | poppler no está fijado; podría cambiar los cortes |
| R3: tablas por celdas | bien | mantener | 0 dígitos perdidos; las tablas 4.1 y 4.2 se declaran |
| R4: orden en tablas | bien | mantener | el 2.25 en los cinco eventos |
| R5: modificaciones, márgenes y celdas | bien | mantener | `d41480…:00006` con la sección 2.7 |
| R6: pies, índice y títulos | bien | mantener | la sección pasó de 23/30 a 30/30 en el muestreo |
| R6: OCR sin fundir | escalar | declarar | se pierde la fecha de la resolución y dos órdenes de trámite de la página 3 |
| Filtro de ruido del OCR solo en `reextraer` | **mal** | corregir | `pipeline.py:493`; `reextraer.py:87` |
| Ids posicionales con tablas de equivalencias | mejorable | corregir el texto | la tabla de R3 fue parcial, no hay tabla de R4 y las listas en Postgres no se migran |
| C20 en la ingesta (dos señales) | mejorable | declarar | falso positivo de un cargo "Asistente" cerca de "omite" |
| Muestreo de calidad | escalar | declarar | los juicios por fragmento no estaban versionados |

### Consulta

| Decisión | Veredicto | Acción | Evidencia clave |
|---|---|---|---|
| F1: esquemas estrictos | bien | mantener | JSON válido en 43 de 43 |
| F2: enrutador de reglas | mejorable | declarar | 6 errores críticos en el conjunto de prueba del experimento; la lista de actividades es cerrada (`comun-019`) |
| F3: solo lectura y límite de llamadas | bien | declarar | el tope de 3 nunca se alcanza; `limite_llamadas` cuenta las regeneraciones |
| F3b: JEV en las fechas de la lista | escalar | declarar | `DESIGN.md:24` exige un experimento de adopción que no se hizo |
| F4: seleccionar literales y validador | bien | mantener | 45/45; `Auditoria_F4.md` |
| Regeneración única | mejorable | declarar | 11 de las 14 consultas sobre 15 s regeneraron; rescata 5 de 8 |
| C14: publicación parcial con `coverage_status='parcial'` | escalar | corregir | contradice `Anteproyecto.md:351`; la web muestra "páginas no indexadas" donde no las hay |
| C14 y F5: lista sin LLM y confirmación | bien | mantener | de 67 a 70 s bajó a 3,8-5,0 s; `Literal[True]` |
| C17: revisión acotada | mejorable | declarar | riesgo cuando la modificación tiene cobertura incompleta |
| Conflictos sin decidir la vigencia | bien | mantener | revisión humana con precisión y recall de 3/3 |
| C18 y C19: pistas de regeneración | mejorable | declarar | efecto no demostrado (n=1 por pregunta) |
| C20: patrón de dos señales | escalar | declarar | se aparta del encargo sin una decisión escrita; el 6/6 se midió con un fragmento sintético |
| B1: ejecutor del banco | mejorable | declarar | `limite_llamadas` y `regeneracion` miden algo distinto de lo que dice su nombre |
| Banco del rol 3 | bien | declarar | dos casos se corrigieron después de la primera corrida (sin esas correcciones serían 18/23) |
| Experimento de JEV | bien | mantener | método ejemplar; el sistema entregado usa reglas |
| Variante LLM del enrutador | escalar | declarar | nunca se comparó (`Anteproyecto.md:342`) |
| Suficiencia efectiva | mejorable | corregir el texto | `comun-006` y `comun-009` son fallos de recuperación (hit@5 falso), no del 9B |
| `tiempo_espera` de 20 s frente a `max_tokens` de 3072 | escalar | declarar | la consulta que fija el P95 terminó por espera agotada |

### Recuperación y plataforma

| Decisión | Veredicto | Acción | Evidencia clave |
|---|---|---|---|
| Búsqueda híbrida con RRF y reranker | mejorable | declarar | Hit@5 0,875 frente a 0,625 (p=0,125, n=16); el MRR igual; sin ablación |
| RLS con `SET LOCAL ROLE` | mejorable | corregir | la API se conecta como `licigt`, superusuario con BYPASSRLS |
| Umbral 0,005 | mejorable | declarar | 0/4 de abstención en recuperación en el banco común; la abstención la logran la generación y el validador |
| GPU fp16 con respaldo a CPU | bien | mantener | 0,21 s frente a 13,6 s; la misma calidad |
| `resolver_evento` y `obtener_fragmentos` | bien | mantener | la seguridad en un solo lugar |
| Página impresa | bien | mantener | `Anteproyecto.md:270` |
| Cookie firmada y sin estado | bien | mantener | límites declarados |
| scrypt con semáforo y hash falso | bien | mantener | corrigió la enumeración de usuarios por tiempo |
| Roles analista y lector | bien | mantener | el lector tampoco propone (más restrictivo que P1) |
| Usuario verificado en cada solicitud | bien | mantener | sirve en lugar de la revocación |
| Comprobación de Origin y Referer | bien | mantener | defensa contra CSRF |
| Auditoría JSONL | escalar | corregir | `Anteproyecto.md:416` pide seudonimizar al usuario; las fallas de escritura son silenciosas |
| Original del PDF | bien | mantener | 404 que no distingue la causa |
| `empresa_b` | bien | declarar | la ingesta de varias empresas no está resuelta (clave primaria global) |
| Pruebas de permisos y concurrencia | mejorable | corregir | `README.md:70` afirma un P95 con 5 usuarios que no existe |
| I1: integración | bien | mantener | sin regresiones |
| E1: reporte | mejorable | declarar | sin P95 con 5 usuarios; 47 preguntas salen de `data/`; no guarda el rango por caso |
| Banco común | mejorable | declarar | el revisor no etiquetó a ciegas la acción; las adjudicaciones solo están en `data/` |
| E2: README y dependencias | mejorable | corregir | `README.md:70` y `:97`; versiones sin fijar |

### Web, documentos y proceso

| Decisión | Veredicto | Acción | Evidencia clave |
|---|---|---|---|
| F6: web con un contrato escrito antes | bien | mantener | el adaptador "reemplazable" quedó como la API final |
| F6f: HOLD y luego PASS | bien | mantener | `c08c3ce` |
| W1: sesión y copia archivada | bien | mantener | falta una quinta medición de la demo con sesión |
| W2: shadcn/ui | escalar | declarar | la compuerta dio PASS en la sesión, pero no quedó registrado en el repo |
| Modo ejemplos por defecto | mejorable | corregir | `make web` sin `VITE_MODO=api` muestra respuestas fijas |
| Página impresa en la web | bien | mantener | `fuentes.test.ts` |
| Documento técnico | mejorable | corregir | afirmaciones sin registro, falta la gobernanza de JEV, la fecha de `:543` y la longitud |
| Aportes de los roles 1 y 3 | mejorable | corregir | cifras superadas; necesita un aviso |
| Demo del 222 | mejorable | corregir | la preparación no incluye la sesión |
| README | mejorable | corregir | `:44`, `:70`, `:95` y `:97` |
| Cambios pendientes del anteproyecto | escalar | declarar | 16 de 17 sin aplicar; ¿se vuelve a entregar? |
| Flujo de trabajo | mejorable | corregir | no refleja la práctica real |
| Implementadores Sonnet | escalar | declarar | el flujo escrito dice Codex u OpenCode |
| Correcciones del banco del rol 3 | mejorable | declarar | no figuran en el documento técnico |
| No corregir el banco común | bien | mantener | corrido una sola vez, con el árbol limpio |
| Kimi reemplazado por DeepSeek | bien | mantener | autorizado y declarado |
| `make … PYTHON=script` | escalar | corregir | incidente sin registro; la regla no está en `AGENTS.md` |
| Repositorio público con material del docente | escalar | corregir | es una decisión del usuario y del dueño del repositorio |
| Trabajo directo en `proyecto` | mejorable | corregir | `CLAUDE.md` había dejado de ser un enlace (restaurado en `5a1d419`) |

## Registros que faltaban

- **Compuerta de diseño de W2:** PASS el 18 de noviembre, con el reporte del revisor en vivo en claro y oscuro, a 1366 y 320 px, y 0 fallas de contraste. Las capturas (`r_w2_*.png`) quedaron en el espacio de trabajo del gestor y no se versionaron.
- **Verificación de E2 en un clon limpio:** las 5 suites y la web pasaron siguiendo el README. Se corrigió lo único que faltaba: las pruebas de recuperación descargan un modelo de unos 450 MB.
- **Incidente `make importar PYTHON=…` (I1):**
  - el implementador ejecutó un script propio por esa vía y el `Makefile` le pasó la URL de la base;
  - según su informe, el script (`scratchpad/real.py`) se borró, no imprimió ni guardó la URL ni la contraseña y solo hizo lecturas;
  - desde E1, los encargos lo prohíben.

## Decisiones del usuario (18 de noviembre)

**Correcciones de código aprobadas:**

- Rol de conexión a la base sin superusuario para la API y el reporte, más la rotación de la contraseña de administración (encargo P2).
- Auditoría con el usuario seudonimizado y aviso cuando falla la escritura (P2).
- `coverage_status` veraz: solo según el inventario. El descarte de afirmaciones se señala como aviso (C21).
- `make web` en modo API y `make web-ejemplos` para el modo de ejemplos.
- El filtro de ruido del OCR en toda la ingesta (R7); era el único veredicto "mal", así que no requirió decisión.

**Decisiones ratificadas, que quedan como del usuario:**

- El patrón C20 de dos señales y la regla "si el fragmento sospechoso era el mejor resultado, la búsqueda es insuficiente".
- El OCR sin fundir en R6: se pierden como evidencia la fecha de la resolución y dos órdenes de trámite de la página 3.
- El rol lector no puede pedir la propuesta de lista.

**No ratificada:** la implementación con subagentes Sonnet y la auditoría con Opus. Queda declarada como desvío del flujo escrito (que dice Codex u OpenCode, y Kimi para el adversario).

**Lo que se mide en vez de solo declararse:**

- el P95 con 5 usuarios simultáneos (E3);
- el tiempo de espera y el tope de tokens alineados, con un presupuesto de tiempo por solicitud (C21);
- la variante LLM del enrutador comparada con reglas y JEV (J2);
- JEV en las fechas de la lista, con un experimento de adopción (F7b).

El umbral de suficiencia y el esquema de ids quedan declarados.

**Proceso:**

- la prohibición de `make … PYTHON=script`, que pasa a `AGENTS.md`;
- la rotación de la contraseña (P2);
- volver a entregar el anteproyecto con `Cambios_pendientes.md` aplicado;
- el material del docente fuera del repositorio, en `.referencias/` (ignorada, con `.gitkeep`). Sigue en el historial de Git; hacer el repositorio privado le corresponde a su dueño.

## Correcciones aplicadas

Se anotan aquí a medida que se aplican, con su commit.
