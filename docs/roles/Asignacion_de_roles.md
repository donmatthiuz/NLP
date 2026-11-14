# Asignación de roles para LiciGT

Esta distribución corresponde a los cuatro frentes de la [arquitectura](../arquitectura/arquitectura.jpeg). Cada integrante debe escribir su nombre en **un** espacio. La persona responsable de un módulo coordina sus cambios e integración; la revisión de resultados y la defensa del proyecto corresponden a todo el equipo.

| Rol | Nombre del integrante | Carpeta principal | Resultado a entregar |
| :--- | :--- | :--- | :--- |
| 1. Ingesta y documentos | ______________________________ | [`src/licigt/ingesta`](../../src/licigt/ingesta/README.md) | PDF originales registrados, texto por página, fragmentos y versiones. |
| 2. Recuperación y RAG | ______________________________ | [`src/licigt/recuperacion`](../../src/licigt/recuperacion/README.md) | Índices y búsqueda con evidencia recuperada y ordenada. |
| 3. Consulta y herramientas | ______________________________ | [`src/licigt/consulta`](../../src/licigt/consulta/README.md) | Flujo de preguntas, respuestas con citas y lista de verificación. |
| 4. Plataforma, seguridad y evaluación | ______________________________ | [`src/licigt/plataforma`](../../src/licigt/plataforma/README.md) | Acceso aislado por empresa, auditoría, pruebas y reporte de métricas. |

## Rol 1 — Ingesta y documentos

**Responsabilidades:**

1. Recibir PDF y metadatos de la licitación (NOG, tipo de documento, fecha, fuente y empresa); validar formato, tamaño y hash SHA-256.
2. Guardar el original en MinIO con versionado y protección contra sobrescritura; relacionar bases, anexos, aclaraciones y modificaciones sin borrar versiones anteriores.
3. Extraer texto y tablas por página, usar OCR cuando haga falta y señalar páginas ilegibles o documentos incompletos.
4. Limpiar y segmentar por títulos, numerales, cláusulas y tablas; conservar página, sección, documento y versión en cada fragmento.
5. Entregar al rol 2 fragmentos preparados para indexación y al rol 4 los eventos de carga y fallos de calidad.

**Entrega verificable:** una carga reproducible que permita localizar en el PDF original la página de cualquier fragmento; una segunda versión debe conservar la primera.

## Rol 2 — Recuperación y RAG

**Responsabilidades:**

1. Crear los embeddings de la línea base y de la versión mejorada; mantener índices separados cuando cambie la dimensión del vector.
2. Guardar y consultar fragmentos en PostgreSQL con `pgvector`, `tsvector` y metadatos. Aplicar los filtros de empresa y NOG antes de devolver texto.
3. Implementar recuperación semántica básica y búsqueda híbrida con fusión, reranking y reducción de fragmentos redundantes.
4. Entregar fragmentos con `chunk_id`, documento, página, versión y puntajes; detectar evidencia insuficiente y versiones potencialmente contradictorias.
5. Acordar con el rol 3 el contrato de `buscar_documentos` y `comparar_versiones`; medir Recall@5 y MRR@5 junto con el rol 4.

**Entrega verificable:** una misma pregunta puede ejecutarse en línea base y versión mejorada, con resultados trazables y sin fragmentos de empresas no autorizadas.

## Rol 3 — Consulta y herramientas

**Responsabilidades:**

1. Construir el flujo de consulta: validar pregunta, clasificar intención y elegir entre búsqueda, extracción de requisitos, extracción de fechas y comparación de versiones.
2. Implementar las herramientas acotadas y el límite de llamadas; generar la lista de verificación con requisitos y fechas respaldados por citas.
3. Generar la respuesta estructurada con `answer`, `sources`, `abstained`, `tool_used` y `needs_human_review`.
4. Mostrar al analista la respuesta, las fuentes, la página y la versión; permitir marcar ítems de la lista y señalar contradicciones para revisión humana.
5. Integrar los fragmentos del rol 2 y el contexto autenticado que entregue el rol 4; nunca aceptar un `tenant_id` proporcionado por el modelo o la pregunta.

**Entrega verificable:** demostrar una consulta respondible, una sin evidencia y una comparación de versiones, todas con salida válida y citas visibles.

## Rol 4 — Plataforma, seguridad y evaluación

**Responsabilidades:**

1. Preparar la API y configuración compartida, la autenticación y los roles de usuario; aplicar el aislamiento por empresa con filtros y políticas de seguridad por fila.
2. Validar entradas, contrato JSON, citas y permisos en la salida; controlar errores, límites de herramienta y solicitudes fuera de alcance.
3. Registrar auditoría sin credenciales ni texto sensible y documentar despliegue, variables de entorno y dependencias.
4. Coordinar el banco de al menos 20 casos, la suite adversaria, la comparación entre variantes, la latencia P95 y el costo por consulta. Cada responsable de módulo aportará casos y corregirá las fallas de su área.
5. Ejecutar pruebas de acceso cruzado, inyección de instrucciones, abstención, concurrencia y fallos de herramientas.

**Entrega verificable:** reporte reproducible con resultados por caso, métricas y fallos conocidos; una consulta de una empresa no debe mostrar documentos privados de otra.

## Acuerdos de integración

1. **Rol 1 → rol 2:** cada fragmento conserva como mínimo `chunk_id`, `doc_id`, `nog`, `tenant_id` o visibilidad pública, `version`, `pagina_inicio`, `pagina_fin`, `seccion` y `texto`.
2. **Rol 2 → rol 3:** la búsqueda devuelve fragmentos autorizados con puntaje y datos suficientes para construir una cita; los conflictos de versión se indican explícitamente.
3. **Rol 4 → roles 2 y 3:** el contexto de acceso proviene de la sesión autenticada. Los roles 2 y 3 no aceptan empresa, rol o permisos escritos por el usuario como fuente de autoridad.
4. **Roles 1, 2 y 3 → rol 4:** cada módulo aporta casos de prueba, instrucciones de ejecución y ejemplos de fallo para la evaluación común.
5. **Equipo completo:** integrar por etapas (ingesta → recuperación → consulta → validación), revisar cambios de otros módulos y preparar juntos la demostración y defensa.
