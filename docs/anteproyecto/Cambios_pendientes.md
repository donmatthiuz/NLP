# Cambios pendientes en el anteproyecto

**Estado al 16 de noviembre de 2026.** Lista de lo que hay que corregir en el [anteproyecto](Anteproyecto.md) para que coincida con las decisiones y el código actuales. Se aplica al final de cada fase o antes de la entrega, no en cada cambio. Cada punto indica de dónde sale para poder verificarlo.

## Sección 1. Información general

- [ ] Completar los carnets de Edwin Jose y Gustavo Cruz.

## Sección 9. Arquitectura

- [ ] Añadir JEV en la capa de decisión (intención y suficiencia) como variante comparada con reglas y LLM, consumida por API alojada. Origen: decisión del 16 de noviembre; [DESIGN](../../DESIGN.md#capa-de-decisión).
- [ ] Indicar que el LLM generador corre en local y JEV por API. Origen: decisión del 16 de noviembre.
- [ ] Actualizar el diagrama `arquitectura_igss.svg`: nodo de JEV, estado compartido, guardrails de salida y tratamiento de excepciones como nodos visibles. Origen: instrucciones del curso, sección 6.
- [ ] Nombrar el proveedor real de almacenamiento (MinIO o Google Cloud Storage) cuando se decida. Origen: [Pendientes_rol_1](../ingesta/Pendientes_rol_1.md).
- [ ] Nombrar el stack de API y pantalla cuando se acuerde con el rol 4 (propuesta: FastAPI y React). Origen: [Avisos al rol 4](../plataforma/Avisos_del_rol_3.md).

## Sección 10. Citas y abstención

- [ ] Fijar el texto exacto de abstención: "No hay información suficiente en los documentos para responder". Origen: notas de la semana 15.1 (la instrucción de abstención debe ser explícita y verificable); [Contratos](../consulta/Contratos.md#rol-3-hacia-el-usuario).

## Sección 11. Herramientas y agentes

- [ ] `comparar_versiones`: parámetros `evento_id`, `tema` y, opcionales, `doc_base_id` y `doc_cambio_id` (ambos o ninguno). Sin ids, se comparan todos los documentos del evento. Origen: la función del rol 2 recibe `pregunta` y no ids (`recuperacion/busqueda.py`, `comparar_versiones`).
- [ ] `buscar_documentos`: aclarar que el filtro `tipo_documento` se aplica sobre los resultados de la búsqueda. Origen: `buscar()` del rol 2 no tiene ese filtro.
- [ ] Contrato de salida: `sources` con `page_end` y la versión separada en `version_ingesta` y `version_oficial`. Origen: decisión del 16 de noviembre; el propio anteproyecto pide no confundir versión de ingesta con modificación oficial.
- [ ] Orquestación: describir el flujo como "flujo de decisión con enrutamiento condicional" (instrucciones, sección 5.6), no como agente autónomo. Origen: notas de la semana 7.1 y diapositiva 266 del curso.

## Sección 12. Evaluación

- [ ] Si se mantiene el experimento de JEV, describir el conjunto etiquetado de decisiones (intención y suficiencia) separado del banco de 20 casos, con desarrollo y prueba distintos. Origen: `advisor-summary.md` de OneDrive y decisión del 16 de noviembre.

## Sección 13. Seguridad

- [ ] Indicar que a JEV, servicio externo, solo se envían la pregunta y textos de documentos públicos; nunca datos de la empresa ni credenciales. Origen: decisión del 16 de noviembre; instrucciones, sección 15 (gobernanza de datos).

## Sección 15. Plan de trabajo

- [ ] Reemplazar la tabla de roles por la de [Asignacion_de_roles](../roles/Asignacion_de_roles.md): el rol 3 ya no lleva interfaz y autenticación; el rol 4 lleva plataforma, seguridad y evaluación.
- [ ] Ajustar las fechas relativas a la fecha real de entrega.

## Sección 16. Referencias

- [ ] Añadir JEV (TypeSafe) y los modelos efectivamente usados: embeddings, reranker y LLM local.

## Por verificar

- [ ] La sección 10 (segmentación, embeddings, umbrales) frente a lo que ya implementó el rol 2 en [Recuperacion](../recuperacion/Recuperacion.md). Lo revisa el rol 2.
