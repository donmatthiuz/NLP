# Cambios pendientes en el anteproyecto

**Estado al 19 de noviembre de 2026 (reentrega).** Cada ítem indica si se aplicó y dónde.

**Estado de la lista original al 16 de noviembre de 2026.** Lista de lo que hay que corregir en el [anteproyecto](Anteproyecto.md) para que coincida con las decisiones y el código actuales. Se aplica al final de cada fase o antes de la entrega, no en cada cambio. Cada punto indica de dónde sale para poder verificarlo.

## Sección 1. Información general

- [x] Completar los carnets de Edwin Jose y Gustavo Cruz. **Aplicado:** sección 1 (22809 y 22779, dados por el usuario el 19 de noviembre de 2026).

## Sección 9. Arquitectura

- [x] Añadir JEV en la capa de decisión (intención y suficiencia) como variante comparada con reglas y LLM, consumida por API alojada. Origen: decisión del 16 de noviembre; [DESIGN](../../DESIGN.md#capa-de-decisión). **Aplicado:** en la sección 9 ("Capa de decisión"). Redactado como variante comparada con criterio de adopción, con reglas por defecto, porque el sistema entregado no usa JEV (resultado del experimento, no copiado al anteproyecto).
- [x] Indicar que el LLM generador corre en local por defecto (Qwen3.5-9B sobre `llama-server`), con un interruptor a OpenAI para máquinas sin GPU, y que JEV va por API. Registrar proveedor, versión y parámetros como pide la línea 299. Origen: decisiones del 16 de noviembre; [I2](../consulta/investigacion/I2_llm_local.md). **Aplicado:** en la sección 9 ("Modelo generativo") y en la sección 10 (línea de "Embeddings e índices"); JEV por API alojada "cuando se active".
- [x] Reemplazar el diagrama `arquitectura_igss.svg` por `diagramas/arquitectura_general.png` y `diagramas/flujo_consulta.png`, con JEV, el estado compartido, las compuertas, las excepciones y la confirmación de la lista como nodos visibles. Referencia de la línea 482 actualizada. Origen: instrucciones del curso, sección 6.
- [ ] Nombrar el proveedor real de almacenamiento (MinIO o Google Cloud Storage) cuando se decida. Origen: [Pendientes_rol_1](../ingesta/Pendientes_rol_1.md). **No aplicado:** no hay decisión (MinIO o GCS siguen abiertos en `Pendientes_rol_1`). La sección 9 ("Stack") lo deja "por fijar al desplegar" y declara el almacén local de desarrollo.
- [x] Nombrar el stack de API y pantalla cuando se acuerde con el rol 4 (propuesta: FastAPI y React). Origen: [Avisos al rol 4](../plataforma/Avisos_del_rol_3.md). **Aplicado:** en la sección 9 ("Stack"): FastAPI y Pydantic; React, Vite y TypeScript, que son los usados en el sistema entregado; referencias en la sección 16.

## Sección 10. Citas y abstención

- [x] Fijar el texto exacto de abstención: "No hay información suficiente en los documentos para responder". Origen: notas de la semana 15.1 (la instrucción de abstención debe ser explícita y verificable); [Contratos](../consulta/Contratos.md#rol-3-hacia-el-usuario). **Aplicado:** en la sección 10 ("Citas y abstención"); coincide con `TEXTO_ABSTENCION` en `esquemas.py`.

## Sección 11. Herramientas y agentes

- [x] `comparar_versiones`: parámetros `evento_id`, `tema` y, opcionales, `doc_base_id` y `doc_cambio_id` (ambos o ninguno). Sin ids, se comparan todos los documentos del evento. Origen: la función del rol 2 recibe `pregunta` y no ids (`recuperacion/busqueda.py`, `comparar_versiones`). **Aplicado:** en la tabla de la sección 11.
- [x] `buscar_documentos`: aclarar que el filtro `tipo_documento` se aplica sobre los resultados de la búsqueda. Origen: `buscar()` del rol 2 no tiene ese filtro. **Aplicado:** en la tabla y en el párrafo siguiente de la sección 11.
- [x] Contrato de salida: `sources` con `page_end` y la versión separada en `version_ingesta` y `version_oficial`. Origen: decisión del 16 de noviembre; el propio anteproyecto pide no confundir versión de ingesta con modificación oficial. **Aplicado:** en la sección 11 ("Contrato de salida").
- [x] Contrato de salida: añadir `needs_clarification` y `clarification_question` (pedir aclaración ante ambigüedad como salida propia). Origen: decisión del 16 de noviembre; [Contratos](../consulta/Contratos.md#rol-3-hacia-el-usuario). **Aplicado:** en la sección 11 ("Contrato de salida"); coincide con `RespuestaEstructurada`.
- [x] Validación de entrada: fuera de dominio por temas prohibidos (los de la sección 6, "No incluye") más el umbral de suficiencia de la recuperación, no por lista de palabras permitidas. Origen: decisión del 16 de noviembre. **Aplicado:** en la sección 11 ("Orquestación", párrafo "Validación de entrada").
- [x] Orquestación: describir el flujo como "flujo de decisión con enrutamiento condicional" (instrucciones, sección 5.6), no como agente autónomo. Origen: notas de la semana 7.1 y diapositiva 266 del curso. **Aplicado:** en la sección 11 ("Orquestación").

## Sección 12. Evaluación

- [x] Si se mantiene el experimento de JEV, describir el conjunto etiquetado de decisiones (intención y suficiencia) separado del banco de 20 casos, con desarrollo y prueba distintos. Origen: `advisor-summary.md` de OneDrive y decisión del 16 de noviembre. **Aplicado:** en la sección 12 ("Evaluación de las decisiones"). El experimento medido cubrió la intención del enrutador y las fechas de la lista; la suficiencia no se midió con JEV (la decide el umbral del reranker), así que no se promete un conjunto de suficiencia.
- [x] **Segunda revisión de fidelidad** (línea 376). La hace un agente revisor independiente, con otra familia de modelos y en una sesión aislada, y el usuario adjudica los desacuerdos. Se declara como limitación: un humano más agentes, no dos personas. Origen: decisión del 16 de noviembre; [I5](../consulta/investigacion/I5_agentes_agnosticos.md). **Aplicado:** en la sección 12 ("Corpus y banco de pruebas" y "Limitaciones declaradas").
- [x] **Criterio para adoptar JEV.** Se adopta solo si no aumenta los errores críticos, si McNemar da p < 0.05 sobre las mismas preguntas y si el P95 queda dentro de los 15 s. **Aplicado:** en la sección 12 ("Evaluación de las decisiones"). El anteproyecto no contenía el criterio anterior (+0.05 de F1, ECE, 300 ms), así que no hubo nada que reemplazar. Sin resultados: el veredicto medido vive en el informe.
  - Reemplaza el criterio anterior: +0.05 de F1, mejor ECE y menos de 300 ms.
  - Las preguntas de prueba las redacta un agente proponente, las revisa un agente revisor y el usuario da el visto bueno; esta limitación se declara en el informe.
  - Origen: decisión del 16 de noviembre y la investigación [I4](../consulta/investigacion/I4_evaluacion_y_jev.md).

- [x] **Limitación: sin memoria de conversación.** Cada pregunta se responde por sí sola; una pregunta de seguimiento ("¿y en la modificación?") debe escribirse completa. Se declara como limitación y trabajo futuro: la reescritura de seguimientos con el historial abriría una vía de inyección y exigiría su propio banco. Origen: decisión del 17 de noviembre; instrucciones del curso, fase 2. **Aplicado:** en la sección 12 ("Limitaciones declaradas").

## Sección 13. Seguridad

- [x] Indicar que a los servicios externos (JEV y, si se activa, el LLM en la nube de OpenAI) solo se envían la pregunta y textos de documentos públicos; nunca datos de la empresa ni credenciales. OpenAI no entrena con los datos de la API y los guarda 30 días para vigilar abusos ([política de datos](https://developers.openai.com/api/docs/guides/your-data)). Origen: decisión del 16 de noviembre; instrucciones, sección 15 (gobernanza de datos). **Aplicado:** en la sección 13 ("Servicios externos"), condicionado a que se activen, porque con la configuración por defecto nada sale de la máquina. La política de OpenAI (30 días, sin entrenamiento) se copió del ítem y no se pudo verificar sin red.

## Sección 15. Plan de trabajo

- [x] Reemplazar la tabla de roles por la de [Asignacion_de_roles](../roles/Asignacion_de_roles.md): el rol 3 ya no lleva interfaz y autenticación; el rol 4 lleva plataforma, seguridad y evaluación. **Aplicado:** en la sección 15 con los cuatro roles de `Asignacion_de_roles`.
- [ ] Ajustar las fechas relativas a la fecha real de entrega. **No aplicado:** no hay fecha real de entrega en el repositorio (`docs/Pendientes.md` lo tiene abierto); las semanas relativas quedan como estaban. Solo se actualizó la fecha de la portada.

## Sección 16. Referencias

- [x] Añadir JEV (TypeSafe) y los modelos efectivamente usados: embeddings, reranker y LLM local. **Aplicado:** en la sección 16 (JEV, Qwen3.5-9B, llama.cpp, FastAPI, React y Vite; embeddings y reranker ya figuraban).

## Por verificar

- [ ] La sección 10 (segmentación, embeddings, umbrales) frente a lo que ya implementó el rol 2 en [Recuperacion](../recuperacion/Recuperacion.md). Lo revisa el rol 2. **No aplicado:** es una verificación que corresponde al rol 2, no un cambio. Contraste hecho con el informe técnico (sección 6.2): ventanas de 120, RRF k = 60 con pesos 0,6 y 0,4, 20 candidatos y reranker coinciden; sin contradicciones.
