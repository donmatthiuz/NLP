# Pendientes del proyecto LiciGT

**Estado al 16 de noviembre de 2026.** Lista viva de lo que falta, con foco en el rol 3. Los detalles por rol están en [Pendientes_rol_1](ingesta/Pendientes_rol_1.md), [Recuperacion](recuperacion/Recuperacion.md#pendientes) y [Plan_rol_3](consulta/Plan_rol_3.md). Los documentos originales del curso están en la carpeta de tareas de OneDrive (`tareas/proyecto`): instrucciones en PDF, plantilla `.docx`, diapositivas del docente, `advisor-summary.md` y diagramas (`diagrams/`, con su `.drawio` y generador).

## Decisiones

Resueltas:

- [x] **Corpus:** se continúa con el IGSS. Las plataformas de contratación pública anteriores dieron inconvenientes; el anteproyecto del repo es el vigente.
- [x] **JEV:** se incluye como medida de la probabilidad de separación de las decisiones (intención y suficiencia). Lo implementa el rol 3 como parte del sistema.

Abiertas:

- [x] **Contratos:** definidos en [Contratos](consulta/Contratos.md). Con el rol 2 se verificó contra el código; con el rol 4 no había contrato y se adopta una propuesta (contexto con `tenant_id`, `usuario` y `rol`; auditoría por función inyectada). Todo corre en local.
- [ ] **Avisar a los roles:** al rol 2, las tres diferencias de su documentación (alerta `evento_con_modificaciones`, firma de `comparar_versiones`, ids de documento); al rol 4, la propuesta de contexto y auditoría; al anteproyecto, los parámetros de `comparar_versiones`.
- [ ] **JEV, detalle:** la adaptación está en [JEV](consulta/JEV.md) (qué decisiones cubre, preguntas y cookbooks). Falta definir el conjunto etiquetado y contra qué se compara. Si se mantiene la comparación con reglas y LLM del resumen para el asesor, la adopción por resultados sigue siendo válida. Actualizar el anteproyecto (sección 11), que hoy no lo menciona, y el diagrama.
- [ ] **Tamaño del banco:** el mínimo del curso es 20 casos (sección 8 de las instrucciones); el resumen para el asesor proponía 50. Sugerencia: 20 a 25.
- [x] **Ejecución:** todo local salvo JEV, que va por API alojada. Equipo: RTX 5070 de 12 GB, 64 GB de RAM, i7-14700KF.
- [ ] **LLM generador local:** elegir un modelo que quepa en la VRAM que deje el rol 2 y cumpla la latencia P95 de 15 s. Verificar que el stack de CUDA en WSL2 soporte la RTX 5070.
- [ ] **Ragas y Langfuse:** no son requisito. Ragas calcula métricas de RAG (fidelidad, precisión del contexto) con un LLM juez; Langfuse es una plataforma de trazas. El curso exige métricas y auditoría, que se pueden cubrir con scripts propios y el registro del rol 4.
- [ ] **Stack propuesto:** backend FastAPI (Python y Pydantic, igual que el RAG) y frontend React con Vite y TypeScript. Acordarlo con el rol 4, que es dueño de la API. NestJS añadiría una tercera capa sin necesidad. Streamlit descartado.
- [ ] **JEV, acceso:** por API alojada de TypeSafe (decidido). Pendiente: documentación de la API que pasará el usuario, custodia de la clave y confirmar que solo se envían textos públicos.
- [ ] **Langfuse:** trazas de cada paso; podría alimentar la auditoría. Su autoalojamiento es pesado y exige sanear datos antes de enviarlos.
- [x] **Parametrización:** `.env.example` sin secretos, `keys/` con un archivo por llave, contraseña de la base generada por `make keys-init`, modelos en `models/` vía `HF_HOME`, `Makefile` como puerta de entrada. La procedencia de los PDF ya la registra el rol 1 en `procedencia/<doc_id>.json`.
- [ ] **Revisiones de modelos:** anotar la revisión exacta de cada modelo en la tabla de `docs/recuperacion/Recuperacion.md` tras la primera descarga (`make models-status`); el rol 2 debe fijarla con `revision=` (ver sus avisos). El LLM local y JEV se anotan cuando se elijan.
- [ ] **Almacenamiento:** MinIO o Google Cloud Storage (ver Pendientes_rol_1).
- [ ] Respuestas del asesor a las preguntas de validación del resumen (documentos privados, LLM externo, tiempo de revisión con usuarios reales).
- [x] **Sin memoria de conversación** (decisión del 17 de noviembre): cada pregunta se responde por sí sola, con el evento como único contexto. El curso propone un "prompt estructurado sin memoria" como línea base (instrucciones, fase 2) y no exige memoria; el banco cubre las preguntas compuestas y la ambigüedad dentro de una sola pregunta. Se declara como limitación y trabajo futuro en el informe. Si se hiciera, la reescritura de preguntas de seguimiento sería del rol 3, y el historial del rol 4.

## Documentos del curso

### Anteproyecto

Los cambios concretos por sección están en [Cambios_pendientes](anteproyecto/Cambios_pendientes.md).

- [ ] Completar los carnets de Edwin Jose y Gustavo Cruz (sección 1).
- [ ] Actualizar la tabla de roles de la sección 15 con la asignación de [Asignacion_de_roles](roles/Asignacion_de_roles.md).
- [ ] Revisar las fechas relativas del plan de trabajo frente a la fecha real de entrega.
- [ ] Comparar las 16 secciones contra la plantilla `.docx` y entregar en el formato que pida el docente (el repo tiene `.md` y `.pdf`).
- [ ] Anotar que los resultados de evaluación son metas, no resultados.

### Diagramas

- [x] Decisión: fuente en HTML autocontenido exportado a PNG, en `docs/arquitectura/diagramas/`. La versión anterior de OneDrive está deprecada y no se usa como referencia. Se borró `arquitectura.jpeg` (GUATECOMPRAS y NOG, sin referencias).
- [x] Diagrama general y flujo de consulta: encargo [D1](consulta/delegacion/D1_diagramas.md), aprobado por el revisor de compuerta (PASS) el 16 de noviembre. Reemplazan a `arquitectura_igss.svg`; referencias actualizadas en el anteproyecto y en `DESIGN.md`.
- [ ] Avisar a quien creó `arquitectura_igss.svg` que se reemplazó.
- [ ] Generación, lista de verificación, E2E de comparación, E2E de inyección y experimento de JEV: en la fase que los use (F4, F5, F6, F7).
- [ ] Ingesta detallada y recuperación: se piden a los roles 1 y 2 (ver sus avisos).

### Documento técnico (10 a 15 páginas)

- [ ] No existe. Debe incluir resumen ejecutivo, problema, usuarios, fuentes, estado del arte, arquitectura, banco de pruebas, métricas, auditoría de seguridad, limitaciones, trabajo futuro, conclusiones y bibliografía.
- [ ] Declaración del uso de herramientas de IA y su grado de intervención (sección 15 de las instrucciones).
- [ ] Citar formalmente librerías, modelos y referencias.

### Presentación final (15 minutos)

- [ ] Las diapositivas de `CC3103 - Procesamiento de Lenguaje Natural.pptx` son del docente, no del equipo. Falta armar la propia.
- [ ] Estructura: problema 2 min, arquitectura 3, demo 4, métricas 3, seguridad 2, cierre 1.
- [ ] Manifiesto del anteproyecto (diapositiva 20): usuario, problema, evidencia, demostración, riesgo y mitigación.
- [ ] Demo en vivo: consulta nominal, trazabilidad de citas, abstención, herramientas, prueba de seguridad y diagnóstico de una falla real.
- [ ] Defensa individual: cada integrante debe poder explicar cada línea de su código.

### Entrega de código

- [ ] README raíz con instalación y ejecución reproducible.
- [ ] Dependencias unificadas y entorno sin credenciales.
- [ ] Scripts de benchmark automatizados.

## Evaluación y seguridad (rol 4, con apoyo de todos)

- [ ] Banco de pruebas con los campos `id`, `question`, `expected_behavior`, `expected_sources`, `expected_pages`, `answerable` y `risk_level`.
- [ ] Composición mínima: 5 directas, 3 paráfrasis, 3 identificadores exactos, 3 compuestas, 2 ambiguas, 2 sin respuesta y 2 de versión o vigencia.
- [ ] Casos de herramientas: ejecución nominal, selección errónea, parámetros fuera de rango, confirmación humana e indisponibilidad.
- [ ] Reservar un evento para evaluación y calibrar umbrales con otro conjunto.
- [ ] Verificar si los dos casos de vigencia tienen respaldo auténtico (evento 222) o reportar la brecha.
- [ ] Suite de seguridad de al menos ocho pruebas, cada una con amenaza, componente, comportamiento esperado, resultado y mitigación.
- [ ] Autenticación, permisos, auditoría sanitizada y despliegue de Postgres.
- [ ] Medición de latencia P95, tokens y costo; reporte reproducible de métricas.
- [ ] Medición exploratoria del tiempo de revisión manual frente a asistido.

## Rol 1: ingesta

Resumen; el detalle está en [Pendientes_rol_1](ingesta/Pendientes_rol_1.md).

- [ ] OCR de las páginas 3 y 4 de la modificación 1 del evento 222 y reextracción desde el PDF original.
- [ ] Corregir la clasificación del conector automático.
- [ ] `tabla_markdown` vacío y `seccion` con pies de página.
- [ ] Registro de eventos de ingesta para el rol 4.

## Rol 2: recuperación

- [ ] Calibrar umbrales con el banco del rol 4 y un evento reservado.
- [ ] Reimportar cuando cambie el ZIP del rol 1.
- [ ] Confirmar el contrato de `buscar` y `comparar_versiones` con el rol 3.

## Rol 3: consulta y herramientas (mío)

El plan por fases está en [Plan_rol_3](consulta/Plan_rol_3.md). Orden sugerido:

- [ ] F0. Confirmar contrato con el rol 2, acordar el `Contexto` con el rol 4 y elegir el LLM.
- [ ] F1. Esquemas Pydantic de respuesta, herramientas y lista de verificación, con pruebas.
- [ ] F2. Validación de entrada y enrutador de intención con JEV como probabilidad de separación (y reglas como línea base); límite de 3 llamadas y una regeneración.
- [ ] F3. Herramientas `buscar_documentos`, `extraer_requisitos` y `comparar_versiones`, de solo lectura.
- [ ] F4. Prompt aumentado, abstención y validador determinista de citas.
- [ ] F5. Lista de verificación con confirmación explícita del usuario.
- [ ] F6. Interfaz mínima y demo con el evento 222.
- [ ] F7. Casos de herramientas y seguridad para el banco del rol 4.
- [ ] Repasar las notas de la semana 15.1 (grounding, abstención, versionado), 2.2 (guardrails) y 7.1 (agentes) para justificar decisiones en el documento y la defensa.
- [ ] Carácter de los literales del numeral 2.7 (listado de documentos): hoy salen `no_indicado` porque `caracter_de_seccion` solo lee la sección del propio fragmento. Saber si cada documento es fundamental exige cruzarlo con lo que dicen los numerales 2.8 y 2.9 del mismo evento. Mientras tanto se declara como limitación: la lista no inventa el carácter.
