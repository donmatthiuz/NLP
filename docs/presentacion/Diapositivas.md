<!--
Formato para `pandoc -t pptx` (make presentacion-pptx). Aquí se permite un `#` por diapositiva
porque pandoc usa los encabezados de nivel 1 como títulos de diapositiva; las notas del orador
van entre `::: notes` y `:::`. Las rutas de imagen son relativas a docs/presentacion.
Cifras del reporte data/plataforma/reporte/20261119T061552Z.md y de docs/informe/Documento_tecnico.md.
-->

# LiciGT: RAG para licitaciones de medicamentos del IGSS

- CC3103 (UVG)
- Edwin Jose 22809
- Gustavo Cruz 22779
- Josue Say 22801
- Mathew Cordero 22982
- Noviembre de 2026

::: notes
Presentación del proyecto. El analista de una empresa proveedora del IGSS cruza bases, cronograma y modificaciones a mano; el error caro es usar una fecha o un requisito que ya cambió. El cliente es la empresa proveedora; el IGSS es la fuente.
:::

# Hipótesis y alcance

- Un RAG especializado reduce el tiempo de identificar requisitos sin perder precisión ni trazabilidad.
- Toda afirmación lleva cita: documento, página y versión.
- Sin evidencia, abstención; ante conflicto, revisión humana.
- Corpus: 5 licitaciones de medicamentos, 6 PDF.
- Fuera de alcance: presentar ofertas, decidir la vigencia, certificar cumplimiento.

::: notes
Se plantea la hipótesis y sus límites. El sistema ayuda a leer, no decide: nunca dice qué documento está vigente ni certifica cumplimiento.
:::

# Corpus utilizado

- Portal de proveedores del IGSS (igssgt.org): 5 licitaciones de medicamentos.
- 399-IGSS-2026, 363-IGSS-2026, 368-IGSS-2026, 327-IGSS-2023 y 222-IGSS-2023.
- 6 PDF oficiales: cinco bases y la Modificación 1 del 222; 184 páginas.
- 625 fragmentos indexados; 28 excluidos por ruido de OCR en la modificación.
- La página 4 de la Modificación 1 remite a un anexo no publicado: cobertura parcial declarada.

::: notes
Corpus local del 14 de noviembre de 2026, empresa ficticia empresa_demo; una segunda empresa ficticia, empresa_b, con una copia del evento 363 para probar el aislamiento. Las páginas 3 y 4 de la modificación son imágenes y se recuperaron por OCR.
:::

# Manifiesto: usuario, problema y riesgo

- **Usuario:** analista de una empresa proveedora que prepara una oferta para el IGSS.
- **Problema:** cruzar bases, cronograma y modificaciones a mano; usar una fecha o un requisito vencido cuesta caro.
- **Evidencia:** 5 licitaciones y 6 PDF; bancos de 23 y 20 casos; reporte reproducible.
- **Demostración:** evento 222 con cita verificada, conflicto, abstención y lista confirmada.
- **Riesgo:** inyección en documentos y fuga de datos entre empresas.
- **Mitigación:** fragmentos como datos no confiables, validador de citas, `tenant_id` de la sesión y 8 de 8 pruebas de seguridad.

::: notes
Manifiesto en una diapositiva, como pide la diapositiva 20 del anteproyecto. Dos minutos con la hipótesis anterior: usuario, problema, evidencia, demostración, riesgo y mitigación. No prometer latencia ni métricas humanas.
:::

# Arquitectura general

![](../arquitectura/diagramas/arquitectura_general.png)

::: notes
Cuatro carriles, uno por rol. La recuperación es híbrida (vectores y texto) con reranking sobre PostgreSQL. Las tres herramientas solo leen. JEV fue una variante experimental no adoptada; el recorrido entregado usa reglas. Puntos: Cuatro carriles: ingesta, recuperación, consulta y plataforma. PostgreSQL con pgvector y búsqueda de texto; híbrida con reranking. Tres herramientas de solo lectura. JEV experimental, no activo por defecto.
:::

# Flujo de una consulta

![](../arquitectura/diagramas/flujo_consulta.png)

::: notes
Recorrido de una pregunta. Antes de publicar, un validador determinista comprueba las citas; si falla, permite una regeneración dentro del presupuesto y publica solo afirmaciones válidas o se abstiene. La auditoría no guarda texto de PDF ni datos personales. Puntos: Guardrail, enrutador, herramienta, recuperación, generación. Validador determinista de citas, hasta una regeneración, publicación parcial o abstención. Auditoría sin texto sensible.
:::

# Ingesta: del PDF a fragmentos

![](../arquitectura/diagramas/ingesta_detallada.png)

::: notes
Validación del PDF y su hash, extracción con Poppler y OCR cuando no hay texto, tablas por geometría, filtro de ruido e inyección por página, y versionado del paquete que consume la recuperación.
:::

# Recuperación híbrida

![](../arquitectura/diagramas/recuperacion.png)

::: notes
Vectores y texto en PostgreSQL, fusión RRF con pesos 0,6 y 0,4, reordenamiento con bge-reranker, umbral de suficiencia y alertas de cobertura y de posible conflicto.
:::

# Generación con citas

![](../arquitectura/diagramas/generacion.png)

::: notes
El modelo selecciona literales de la evidencia; un validador determinista comprueba cada cita. Si falla, una regeneración dentro del presupuesto; si no, publicación parcial de lo válido o abstención.
:::

# Decisiones clave (1): confianza

- Seleccionar, no generar: el modelo elige literales y el validador comprueba cada cita.
- Abstención ante evidencia insuficiente.
- Revisión humana ante conflicto.
- Nunca se decide qué documento está vigente.

::: notes
Cinco porqués encadenados, de dato equivocado a validador determinista: la confianza no descansa en el modelo sino en una comprobación que no es probabilística.
:::

# Decisiones clave (2): acceso y enrutador

- Tenant desde la sesión firmada, nunca de la pregunta ni del modelo.
- Seguridad por fila como segunda barrera; la API sin superusuario.
- Enrutador por reglas; en 60 casos, aciertos: reglas 37, JEV 53, LLM local 51.
- Errores críticos: 6, 0 y 0.
- Regla de adopción fijada antes de medir: P95 total mayor que 15 s, no se adopta. Fechas: JEV fuera.

::: notes
Dos barreras de aislamiento. JEV y el LLM local mejoran el enrutamiento (McNemar p = 3,1·10⁻⁵ para JEV), pero la regla fijada de antemano exige P95 dentro de 15 s y no se cumple, así que el sistema entregado usa reglas.
:::

# Experimento de adopción: reglas, JEV y LLM local

![](../arquitectura/diagramas/experimento_jev.png)

::: notes
Tres variantes del enrutador sobre los mismos conjuntos, con etiquetado a ciegas y la regla de adopción fijada antes de correr: sin más errores críticos, McNemar p menor a 0,05 y P95 de 15 s o menos. JEV y el LLM local aciertan más que las reglas, pero no cumplen la latencia: el sistema entregado usa reglas. En las fechas de la lista, las reglas tuvieron 11 aciertos y 0 críticos y JEV no podía superarlas.
:::

# Demostración: evento 222-IGSS-2023

- Nueve pasos: login, cita con página, conflicto, abstención, página 4.
- Lista de verificación con confirmación.
- Inyección, otra empresa, lector.
- Rótulo con commit, fecha y condición de GPU.

::: notes
Video grabado de la demo (el curso pide demostración en vivo; se confirma con el docente). Los cortes de espera llevan el rótulo con la latencia real.
:::

# Caso: bases contra modificación

![](../arquitectura/diagramas/e2e_comparacion.png)

::: notes
Comparación del evento 222: la fecha de recepción cambia entre las bases y la Modificación 1. Se muestran las dos fuentes y se pide revisión humana; el sistema no decide cuál está vigente.
:::

# Caso: lista de verificación

![](../arquitectura/diagramas/e2e_lista.png)

::: notes
La propuesta de lista se arma sin enrutador ni LLM, con fechas verificadas por reglas en filas de tabla. Solo se guarda tras la confirmación explícita del analista; el lector no puede guardarla.
:::

# Evaluación: recuperación

- Tres bancos: desarrollo 27, rol 3 con 23 y común con 20 casos.
- Desarrollo: Hit@5 de 0,560 a 1,000; MRR@5 de 0,330 a 0,900.
- Rol 3: Hit@5 de 0,667 a 1,000.
- Común: Hit@5 de 0,625 a 0,875; MRR@5 se mantiene en 0,51.

::: notes
Comparación de línea base contra recuperación mejorada. En el banco común la mejora de Hit@5 no es significativa (McNemar exacto p = 0,125) y no hay ablación.
:::

# Evaluación: de punta a punta

- Cumplen 19 de 23 (rol 3) y 11 de 20 (común).
- Citas válidas: 41 de 41; JSON válido en todos los casos.
- Abstención correcta: 13 de 14 y 4 de 4.
- El validador comprueba existencia y texto, no que la cita respalde la afirmación.
- Tiempo de revisión: exploratorio, n = 1 (el propio desarrollador); sin conclusión de reducción.
- Fidelidad factual y cobertura de requisitos: no medidas.

::: notes
Resultados medidos tal cual, de la corrida oficial anterior a las correcciones motivadas por la evaluación humana (no se volvieron a medir). Fase manual de la evaluación humana: 6 intentos, 2 correctos y 1 parcial, mediana 78,8 s; la fase asistida se detuvo por dos defectos que se corrigieron y su repetición no se cronometró. Corrida oficial con la GPU de escritorio compartida: el LLM generó a 62,5 tokens por segundo de mediana. Como referencia, una corrida previa a 86 tokens por segundo dio P95 de 18,5 s; no es resultado, solo muestra la sensibilidad al hardware.
:::

# Latencia, costo y condición de GPU

- P95: 32,0 s con 1 usuario y 37,5 s con 5; meta 15 s, no cumplida.
- Condición: corrida oficial con GPU de escritorio compartida, 62,5 tokens por segundo de mediana.
- Referencia: 86 tokens por segundo con P95 18,5 s; no es resultado.
- Costo: 0 en dinero; 0,75 llamadas y 3 938 tokens de entrada por consulta.
- Recuperación en GPU (cuda, fp16): búsqueda de 13,6 s a 0,21 s.

::: notes
La causa de fondo es la generación del LLM local de 9B con un solo hueco en llama-server. La asociación con la carga de la GPU no se aisló con un experimento. No se demostró que con la GPU libre se cumpla la meta.
:::

# Seguridad: inyección directa e indirecta

![](../arquitectura/diagramas/e2e_inyeccion.png)

::: notes
La inyección directa la detiene el guardrail de entrada y el sistema se abstiene sin herramienta ni LLM. La indirecta, dentro de un documento, la marca la ingesta con dos señales y la búsqueda la quita de la evidencia: los fragmentos son datos, nunca instrucciones.
:::

# Seguridad: 8 de 8

- Inyección directa e indirecta, cita falsa, requisito fabricado, acción no autorizada.
- Acceso cruzado, mezcla de eventos, original sin permiso.
- 102 fuentes revisadas, 0 violaciones de aislamiento.
- No implica seguridad universal.

::: notes
Suite de ocho pruebas con amenaza, mitigación y resultado. Todas cumplen, pero acotado a lo probado.
:::

# Limitaciones

- P95 sobre la meta; modelo local de 9B que se abstiene más de lo deseable.
- Banco común 11 de 20; bancos pequeños; cinco licitaciones.
- Página 4 sin indexar y anexo no publicado.
- Evaluación humana exploratoria (n = 1) sin conclusión; fidelidad y cobertura de requisitos sin medir.
- Correcciones posteriores a la corrida oficial sin nueva medición de los bancos.

::: notes
Se reportan sin maquillar. La evaluación humana reveló defectos (regla de conflicto, enrutamiento de plazos, enlaces al PDF) que se corrigieron y auditaron; las cifras de los bancos son anteriores. Las metas sin medida se declaran como no medidas.
:::

# Uso de IA en el desarrollo

- Implementación asistida por agentes, con auditoría adversarial de cada entrega.
- Casos de prueba etiquetados a ciegas por dos modelos de familias distintas.
- Los desacuerdos y las decisiones de diseño los resolvió una persona.
- Experimentos con la regla de adopción fijada antes de correr.

::: notes
La IA se usó con papeles separados: quien implementa no audita. Ninguna cifra del informe sale de un modelo sin medición.
:::

# Conclusiones y cierre

- Trazabilidad: toda cita publicada pasa el validador.
- Aislamiento por dos barreras; suite de seguridad 8 de 8.
- Faltan: latencia bajo 15 s y una evaluación con usuarios más allá de la exploratoria.
- Siguiente paso: acortar la evidencia al LLM y reaplicar la regla de adopción de JEV.
- "El sistema no decide cuál está vigente."

::: notes
Cierre: el sistema cumple trazabilidad y aislamiento; falta la latencia y la evaluación con humanos. Preguntas.
:::
