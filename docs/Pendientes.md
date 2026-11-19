# Pendientes del proyecto LiciGT

**Estado al 18 de noviembre de 2026**, tras la revisión retrospectiva ([Revision_retrospectiva](consulta/Revision_retrospectiva.md)). Lista viva de lo que falta, con foco en el rol 3. Las casillas marcadas llevan el commit donde se hicieron. Los detalles por rol están en [Pendientes_rol_1](ingesta/Pendientes_rol_1.md), [Recuperacion](recuperacion/Recuperacion.md#pendientes) y [Plan_rol_3](consulta/Plan_rol_3.md). Los documentos originales del curso están en la carpeta de tareas de OneDrive (`tareas/proyecto`): instrucciones en PDF, plantilla `.docx`, diapositivas del docente, `advisor-summary.md` y diagramas (`diagrams/`, con su `.drawio` y generador).

## Actualización visual del 19 de noviembre de 2026

- [x] W3 aplicado en la web, sin commit: favicon genérico, tarjetas y selectores compactos, menos texto auxiliar y transiciones. Compuerta independiente PASS; [verificación y límites](consulta/delegacion/W3_verificacion.md).

- [x] Corrección posterior de W3, sin commit: tema con sol/luna, selector Radix, cabecera adaptable y pie retirado. 80 pruebas, compilación, 30 vistas, seis menús y tres sesiones simuladas aprobados; compuerta PASS. [Detalle y límites](consulta/delegacion/W3_correccion_controles.md).

## Decisiones

Resueltas:

- [x] **Corpus:** se continúa con el IGSS. Las plataformas de contratación pública anteriores dieron inconvenientes; el anteproyecto del repo es el vigente.
- [x] **JEV:** se incluye como medida de la probabilidad de separación de las decisiones (intención y suficiencia). Lo implementa el rol 3 como parte del sistema.

Abiertas:

- [x] **Contratos:** definidos en [Contratos](consulta/Contratos.md). Con el rol 2 se verificó contra el código; con el rol 4 no había contrato y se adopta una propuesta (contexto con `tenant_id`, `usuario` y `rol`; auditoría por función inyectada). Todo corre en local.
- [x] **Avisar a los roles:** hecho en los `Avisos_del_rol_N.md` de cada módulo; el rol 2 respondió las diferencias de documentación el 16 de noviembre (`4a002a0`) y la sesión y la auditoría del rol 4 se entregaron en P1 (`946d228`). Abierto: reflejar en el anteproyecto los parámetros de `comparar_versiones` ([Cambios_pendientes](anteproyecto/Cambios_pendientes.md)).
- [x] **JEV, detalle:** la adaptación está en [JEV](consulta/JEV.md). El conjunto etiquetado y la comparación con reglas y con la variante LLM están hechos y medidos (`bfc5a4a`, `afc6b07`, `e837ea2`; [Experimento_JEV](consulta/Experimento_JEV.md)): el sistema entregado usa reglas. Abierto: actualizar el anteproyecto (sección 11), que no lo menciona, y el diagrama.
- [x] **Tamaño del banco:** banco común de 20 casos (`f4e58d8`) y banco del rol 3 de 23 (`6b9910e`).
- [x] **Ejecución:** todo local salvo JEV, que va por API alojada. Equipo: RTX 5070 de 12 GB, 64 GB de RAM, i7-14700KF.
- [x] **LLM generador local:** Qwen3.5-9B en `llama-server` con Docker y GPU (`b729647`, `7d84ba0`). Cabe junto a la recuperación y funciona en la RTX 5070. No cumple la latencia: P95 de 32,0 s con un usuario y 37,5 s con cinco en la corrida oficial `20261119T061552Z` (GPU compartida; la corrida previa `20261119T042331Z` dio 18,5 s, solo como referencia de sensibilidad al hardware; meta 15 s).
- [x] **Ragas y Langfuse:** no se adoptaron; las métricas se calculan con código propio (`make reporte`, `926863b`) y la auditoría es la del rol 4. No son requisito. Ragas calcula métricas de RAG (fidelidad, precisión del contexto) con un LLM juez; Langfuse es una plataforma de trazas. El curso exige métricas y auditoría, que se pueden cubrir con scripts propios y el registro del rol 4.
- [x] **Stack propuesto (adoptado):** backend FastAPI (Python y Pydantic, igual que el RAG) y frontend React con Vite y TypeScript. Acordarlo con el rol 4, que es dueño de la API. NestJS añadiría una tercera capa sin necesidad. Streamlit descartado.
- [x] **JEV, acceso:** por API alojada de TypeSafe, con la llave en `keys/` que ningún agente lee, y solo la pregunta y fragmentos de documentos públicos ([JEV](consulta/JEV.md#datos-que-salen-del-equipo)).
- [ ] **Langfuse:** trazas de cada paso; podría alimentar la auditoría. Su autoalojamiento es pesado y exige sanear datos antes de enviarlos.
- [x] **Parametrización:** `.env.example` sin secretos, `keys/` con un archivo por llave, contraseña de la base generada por `make keys-init`, modelos en `models/` vía `HF_HOME`, `Makefile` como puerta de entrada. La procedencia de los PDF ya la registra el rol 1 en `procedencia/<doc_id>.json`.
- [x] **Revisiones de modelos:** fijadas con `revision=` en `REVISION` (`4a002a0`) y listadas, con las del LLM local y JEV (`jev-1.14.0`), en la bibliografía del [documento técnico](informe/Documento_tecnico.md).
- [ ] **Almacenamiento:** MinIO o Google Cloud Storage (ver Pendientes_rol_1).
- [ ] Respuestas del asesor a las preguntas de validación del resumen (documentos privados, LLM externo, tiempo de revisión con usuarios reales).
- [x] **Sin memoria de conversación** (decisión del 17 de noviembre): cada pregunta se responde por sí sola, con el evento como único contexto. El curso propone un "prompt estructurado sin memoria" como línea base (instrucciones, fase 2) y no exige memoria; el banco cubre las preguntas compuestas y la ambigüedad dentro de una sola pregunta. Se declara como limitación y trabajo futuro en el informe. Si se hiciera, la reescritura de preguntas de seguimiento sería del rol 3, y el historial del rol 4.

## Documentos del curso

### Anteproyecto

Los cambios concretos por sección están en [Cambios_pendientes](anteproyecto/Cambios_pendientes.md).

- [x] Completar los carnets de Edwin Jose y Gustavo Cruz (sección 1).
- [ ] Actualizar la tabla de roles de la sección 15 con la asignación de [Asignacion_de_roles](roles/Asignacion_de_roles.md).
- [ ] Revisar las fechas relativas del plan de trabajo frente a la fecha real de entrega.
- [ ] Comparar las 16 secciones contra la plantilla `.docx` y entregar en el formato que pida el docente (el repo tiene `.md` y `.pdf`).
- [ ] Anotar que los resultados de evaluación son metas, no resultados.

### Diagramas

- [ ] Actualizar las dos figuras frente al código actual: estados de implementación, reglas/JEV, propuesta de lista, autenticación y regeneración. La [revisión del 19 de noviembre](arquitectura/diagramas/Revision_actualidad.md) verificó maquetación OK, pero contenido desactualizado.

- [x] Decisión: fuente en HTML autocontenido exportado a PNG, en `docs/arquitectura/diagramas/`. La versión anterior de OneDrive está deprecada y no se usa como referencia. Se borró `arquitectura.jpeg` (GUATECOMPRAS y NOG, sin referencias).
- [x] Diagrama general y flujo de consulta: encargo [D1](consulta/delegacion/D1_diagramas.md), aprobado por el revisor de compuerta (PASS) el 16 de noviembre. Reemplazan a `arquitectura_igss.svg`; referencias actualizadas en el anteproyecto y en `DESIGN.md`.
- [ ] Avisar a quien creó `arquitectura_igss.svg` que se reemplazó.
- [ ] Generación, lista de verificación, E2E de comparación, E2E de inyección y experimento de JEV: en la fase que los use (F4, F5, F6, F7).
- [ ] Ingesta detallada y recuperación: se piden a los roles 1 y 2 (ver sus avisos).

### Documento técnico (10 a 15 páginas)

- [x] Existe en [Documento_tecnico](informe/Documento_tecnico.md) (`e2eead7`, actualizado con la revisión retrospectiva) con todas las secciones pedidas. Abierto: su longitud (el curso pide 10 a 15 páginas) y el formato final de entrega.
- [x] Declaración del uso de herramientas de IA y su grado de intervención: sección 13 del documento técnico.
- [x] Citar formalmente librerías, modelos y referencias: sección 14 del documento técnico.

### Presentación final (15 minutos)

- [ ] Las diapositivas de `CC3103 - Procesamiento de Lenguaje Natural.pptx` son del docente, no del equipo (desde el 18 de noviembre están en `.referencias/`, fuera del repositorio). Falta armar la propia.
- [ ] Estructura: problema 2 min, arquitectura 3, demo 4, métricas 3, seguridad 2, cierre 1.
- [ ] Manifiesto del anteproyecto (diapositiva 20): usuario, problema, evidencia, demostración, riesgo y mitigación.
- [ ] Demo en vivo: consulta nominal, trazabilidad de citas, abstención, herramientas, prueba de seguridad y diagnóstico de una falla real.
- [ ] Defensa individual: cada integrante debe poder explicar cada línea de su código.

### Entrega de código

- [x] README raíz con instalación y ejecución reproducible (E2, `345445c`; verificado en un clon limpio).
- [x] Dependencias unificadas y entorno sin credenciales (E2, `345445c`). Abierto: las versiones no están fijadas con exactitud.
- [x] Scripts de benchmark automatizados: `make reporte`, `make banco` y `make evaluar` (`926863b`).

## Evaluación y seguridad (rol 4, con apoyo de todos)

- [x] Banco de pruebas con los campos `id`, `question`, `expected_behavior`, `expected_sources`, `expected_pages`, `answerable` y `risk_level` (`f4e58d8`). Los `expected_pages` son páginas físicas del PDF.
- [x] Composición mínima: 5 directas, 3 paráfrasis, 3 identificadores exactos, 3 compuestas, 2 ambiguas, 2 sin respuesta y 2 de versión o vigencia (`f4e58d8`).
- [x] Casos de herramientas: ejecución nominal, selección errónea, parámetros fuera de rango, confirmación humana e indisponibilidad (`6b9910e`).
- [ ] Reservar un evento para evaluación y calibrar umbrales con otro conjunto. No se cumplió: los casos de desarrollo cubren los cinco eventos. Declarado en el documento técnico, sección 7.
- [x] Verificar si los dos casos de vigencia tienen respaldo auténtico (evento 222): el revisor confirmó la evidencia de los 20 casos del banco común (`f4e58d8`).
- [x] Suite de seguridad de al menos ocho pruebas: 8 de 8 en el reporte (`926863b`).
- [x] Autenticación, permisos y auditoría sanitizada (P1, `946d228`; auditoría seudonimizada y rol sin superusuario en P2, `9b22d02`). Abierto: el despliegue de Postgres fuera de la máquina local; hoy corre con `make db-up`.
- [x] Medición de latencia P95, tokens y costo; reporte reproducible (`926863b`; con 5 usuarios, E3, `987b2f6`).
- [ ] Medición exploratoria del tiempo de revisión manual frente a asistido. No se hizo.

## Rol 1: ingesta

Resumen; el detalle está en [Pendientes_rol_1](ingesta/Pendientes_rol_1.md).

- [x] OCR de las páginas 3 y 4 de la modificación 1 del evento 222 y reextracción desde el PDF original (R1, `4bd2d7f`). La página 4 queda sin indexar y el anexo de 11 hojas no está publicado.
- [x] Corregir la clasificación del conector automático (`8df7c95`).
- [x] `tabla_markdown` vacío (R3, `87c5d90`) y `seccion` con pies de página (R6, `7c117d9`).
- [x] Filtro de ruido del OCR en toda la ingesta (R7, `3c8a4c9`).
- [ ] Registro de eventos de ingesta para el rol 4: existe `evento_de_carga` (`a3ce147`), pero la API no lo guarda en la auditoría.

## Rol 2: recuperación

- [ ] Calibrar umbrales con el banco del rol 4 y un evento reservado. El umbral de 0,005 se calibró con desarrollo y se declara; no abstiene en las 4 preguntas sin respuesta del banco común.
- [x] Reimportar cuando cambie el ZIP del rol 1: hecho con el paquete R6 (625 fragmentos indexables); se repite con cada ZIP nuevo.
- [x] Confirmar el contrato de `buscar` y `comparar_versiones` con el rol 3 (`4a002a0`).
- [x] Cierre del rol 2: GPU con respaldo a CPU, `resolver_evento` y `obtener_fragmentos` (R2C, `c7d0dcc`).

## Rol 3: consulta y herramientas (mío)

El plan por fases está en [Plan_rol_3](consulta/Plan_rol_3.md). Orden sugerido:

- [x] F0. Contrato con el rol 2, `Contexto` con el rol 4 y LLM elegido (`4a002a0`, `946d228`).
- [x] F1. Esquemas Pydantic de respuesta, herramientas y lista de verificación (`626d806`).
- [x] F2. Validación de entrada y enrutador de intención (`b05bc37`). Reglas por defecto: JEV y el LLM se midieron y no se adoptan.
- [x] F3. Herramientas `buscar_documentos`, `extraer_requisitos` y `comparar_versiones`, de solo lectura (`53d448d`).
- [x] F4. Prompt aumentado, abstención y validador determinista de citas (`3a52016`; diez pasadas del adversario). Con cobertura veraz y presupuesto de tiempo en C21 (`4d997dd`).
- [x] F5. Lista de verificación con confirmación explícita del usuario (`edb2496`, `ecb37e0`, `182bbdf`).
- [x] F6. Interfaz web y demo con el evento 222 (`13f3e22`, `6098603`, `1c07617`; W1 `85ad53f`, W2 `0b2f143`). Abierto: una quinta medición de la demo con sesión.
- [x] F7. Casos de herramientas y seguridad para el banco, y experimento de JEV (`60c24fe`, `bfc5a4a`, `1b85e08`).
- [ ] Repasar las notas de la semana 15.1 (grounding, abstención, versionado), 2.2 (guardrails) y 7.1 (agentes) para justificar decisiones en el documento y la defensa.
- [x] **Revisión retrospectiva** (pedido del usuario, 18 de noviembre): hecha en [Revision_retrospectiva](consulta/Revision_retrospectiva.md) (`f333c19`). Quedó planteada así:
  - aplicar a todo lo hecho el mismo criterio que a los cambios nuevos: cinco porqués con evidencia, diseño, buenas prácticas y visión del sistema completo;
  - el alcance son los encargos R1 a R5, C1 a C20, F1 a F7, B1, el experimento de JEV y las decisiones de `Pendientes.md` y `Plan_rol_3.md`;
  - el resultado, en `docs/consulta/Revision_retrospectiva.md`, dice por decisión si está bien, mal o es mejorable, con su evidencia y qué se hace: mantener, corregir o declarar como limitación;
  - lo que no tenga respuesta se escala al usuario con contexto y plan;
  - en esa misma pasada se actualizaron las casillas de `Plan_rol_3.md`, `Pendientes_rol_1.md` y de este archivo.
  - Correcciones aplicadas: R7 (`3c8a4c9`), J2 (`afc6b07`), E3 (`987b2f6`), P2 (`9b22d02`), C21 (`4d997dd`), F7b y F7c (`e837ea2`) y `make web` en modo API (`8584c73`).
  - Declaradas como limitación en el documento técnico: lo que la revisión marcó como "declarar".
- [ ] **Abiertos tras la retrospectiva:**
  - volver a entregar el anteproyecto con [Cambios_pendientes](anteproyecto/Cambios_pendientes.md) aplicado (16 de 17 cambios sin aplicar);
  - el repositorio sigue con el material del docente en su historial: hacerlo privado le corresponde a su dueño;
  - la quinta medición de la demo con sesión y la preparación de la demo con `make usuarios-demo`;
  - el P95 sigue sobre 15 s (32,0 s en la corrida oficial);
  - las métricas con usuarios del documento técnico (sección "Métricas con usuarios") quedan pendientes de la medición.
- [ ] Carácter de los literales del numeral 2.7 (listado de documentos): hoy salen `no_indicado` porque `caracter_de_seccion` solo lee la sección del propio fragmento. Saber si cada documento es fundamental exige cruzarlo con lo que dicen los numerales 2.8 y 2.9 del mismo evento. Mientras tanto se declara como limitación: la lista no inventa el carácter.
