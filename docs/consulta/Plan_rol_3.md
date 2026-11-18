# Plan del rol 3: consulta y herramientas

**Estado al 17 de noviembre de 2026.** Este plan cubre las [responsabilidades del rol 3](../roles/Asignacion_de_roles.md#rol-3--consulta-y-herramientas) y sigue las secciones [9. Arquitectura](../anteproyecto/Anteproyecto.md#9-arquitectura), [10. Citas y abstención](../anteproyecto/Anteproyecto.md#citas-y-abstención) y [11. Herramientas y agentes](../anteproyecto/Anteproyecto.md#11-herramientas-y-agentes) del anteproyecto. El código irá en [`src/licigt/consulta`](../../src/licigt/consulta/README.md).

> **Avance:** el módulo está vacío (solo README). Contratos definidos en [Contratos](Contratos.md). Cada fase sigue el [flujo de trabajo](Flujo_de_trabajo.md): cinco porqués y visto bueno antes de delegar.

## Qué exigen las instrucciones del curso que toca este rol

- 5.5 Generación fundamentada: usar solo el contexto recuperado, declarar falta de evidencia, conservar citas y respetar el formato.
- 5.6 Herramienta o flujo agéntico: enrutamiento condicional entre recuperación y acciones alternativas, con límites estrictos.
- 8 Banco de pruebas: si hay herramientas, añadir casos de ejecución nominal, selección errónea de herramienta, parámetros fuera de rango, acción que exige confirmación humana e indisponibilidad del servicio.
- 11 Formato de salida: esquema validado con Pydantic o JSON Schema (`answer`, `sources` con fuente, página y `chunk_id`, `abstained`, `tool_used`, `needs_human_review`).
- 13 Demostración: consulta nominal, trazabilidad de citas, abstención, uso de herramientas, prueba de seguridad y diagnóstico de una falla real.

## Lo que ya entrega el rol 2

- `buscar(ctx, evento_id, pregunta, variante, k)` con fragmentos, puntajes, `suficiente` y `alertas`.
- `comparar_versiones(ctx, evento_id, pregunta, k)` con los mejores fragmentos de cada documento del evento.
- Alerta `posible_conflicto` (hacia `needs_human_review`) y `cobertura_incompleta` (hacia `coverage_status` y `warnings`).

## Fases

### F0. Contrato e integración — 0.5 días
- [ ] Confirmar con el rol 2 el contrato de `buscar` y `comparar_versiones` (pendiente que figura en `Recuperacion.md`).
- [ ] Acordar con el rol 4 cómo llega el `Contexto` autenticado. Mientras no exista, usar un `Contexto` simulado solo en pruebas.
- [x] LLM generador local en la RTX 5070 de 12 GB (compartida con el rol 2); JEV por API alojada, con la clave en el archivo que indica `LICIGT_JEV_API_KEY_FILE`. Nunca en el repo.

### F1. Esquemas — 1 día

> **Hecho el 16 de noviembre.** Implementó Codex con el encargo; la auditoría del gestor añadió tres correcciones con pruebas: ids de documento vacíos se rechazaban mal, enteros y booleanos sin coerción (la salida del modelo no puede colar `true` como página 1 ni `"7"` como `k`) y `warnings` sin textos vacíos. 22 pruebas en verde con `make test-consulta`.

- [ ] Modelos Pydantic de la respuesta: `answer`, `sources` (`doc_id`, `source`, `page`, `chunk_id`, versión, cita), `abstained`, `tool_used`, `needs_human_review`, `evento_id`, `coverage_status`, `warnings`.
- [ ] Modelos de parámetros de las tres herramientas con los límites del anteproyecto: `query` de hasta 500 caracteres, `k` entre 1 y 10, categorías administrativa, legal, técnica y financiera, y mismo evento en `comparar_versiones`.
- [ ] Pruebas: parámetros fuera de rango se rechazan; `tenant_id` nunca es un campo aceptado.
- Encargo: [F1_esquemas](delegacion/F1_esquemas.md). Por decisión del 16 de noviembre, los modelos de la lista de verificación pasan a F5 y los de lectura del rol 2 a F3, donde se usan por primera vez.

### F2. Validación de entrada, ambigüedad, enrutador y JEV — 2 días

Encargo: [F2_entrada_enrutador](delegacion/F2_entrada_enrutador.md). Decisiones del 16 de noviembre: JEV real entra en F2 (hay clave y presupuesto); el LLM solo queda conectado por interfaz hasta elegir el modelo; los límites de frecuencia se simulan y el límite de 3 llamadas y 1 regeneración se implementa como presupuesto listo para F3 y F4; fuera de dominio por temas prohibidos más la suficiencia de la recuperación; la comprobación de que el evento pertenece al usuario la hacen el SQL del rol 2 y el contexto del rol 4, no F2; pedir aclaración es un campo propio del contrato.

- [ ] Juicios de entrada por reglas: longitud, inyección, temas prohibidos y pregunta concreta.
- [ ] Enrutador con interfaz común: variantes de reglas, JEV (con degradación a reglas) y LLM sin cliente.
- [ ] Preguntas y umbrales de JEV en un solo módulo; cliente con clave por archivo, modelo fijado, reintentos explícitos y limitador.
- [ ] Tabla de decisión: abstener, aclarar o usar herramienta.
- [ ] Presupuesto de 3 llamadas y 1 regeneración.
- [ ] Sondeo manual reglas frente a JEV con la API real.

### F3a. Lectura del rol 2 y herramientas de búsqueda y comparación — 1 día

Encargo: [F3a_herramientas](delegacion/F3a_herramientas.md). En paralelo con F2.

- [ ] Modelos tolerantes de lectura y `fuente_desde_fragmento`.
- [ ] `buscar_documentos` con filtro por tipo que no quita la otra fuente de un conflicto.
- [ ] `comparar_versiones` que además pide alertas con `buscar()`, filtra por ids y pide revisión humana al comparar con una modificación o aclaración.
- [ ] Errores controlados, sin excepciones hacia afuera.

### F3b. `extraer_requisitos` — 1.5 días

Depende del cliente de JEV de F2. Diseño acordado (cookbook oficial de fechas de JEV, "seleccionar en vez de generar"; notas de la semana 2 sobre expresiones regulares; puntos débiles de JEV con fechas):

- [ ] Evidencia por categoría con `buscar()` y consultas fijas por categoría en un solo lugar.
- [ ] Fechas candidatas con expresiones regulares (meses en español), cada una con su `chunk_id`.
- [ ] JEV asigna cada candidata a su actividad (`Choice` más `Noul` compañero); el código normaliza, valida y compara fechas.
- [ ] La confianza mínima entre las partes decide revisión humana; una fecha que el documento no dice siempre va a revisión. Sin JEV, las candidatas salen como no verificadas.

Decisiones del 16 de noviembre, tras los cinco porqués ([encargo](delegacion/F3b_extraer_requisitos.md)):

- El cronograma se consulta siempre con una consulta fija. La firma del anteproyecto no cambia, porque la herramienta promete fechas en cualquier categoría (`Anteproyecto.md:335` y `:338`).
- Sin `RequisitoCandidato`: los requisitos los redacta F4 con citas y F5 arma la lista.
- La función vive en `herramientas.py`, con el mismo resultado que las otras dos. La lógica pura de fechas va en `requisitos.py` y las preguntas de JEV en `preguntas_jev.py`.
- Solo fechas con el mes en español: el formato `dd/mm/aaaa` no aparece en el corpus.
- La herramienta no consume el presupuesto de llamadas; cuenta como una invocación.
- La comparación de fechas por actividad detecta el conflicto de recepción del 222 (31 de julio en la portada de las bases, 06 de octubre en la modificación), que la alerta del rol 2 no marca.

### F4. Generación y validación de salida — 2 días

Cerrada tras siete pasadas del adversario ([Auditoria_F4](Auditoria_F4.md)).
- [x] Prompt aumentado: instrucciones del sistema, evidencia y pregunta separadas; la evidencia se marca como datos no confiables.
- [x] El modelo cita por `chunk_id`; instrucción de abstención explícita y manejo de la trampa "si no está en el contexto, dilo".
- [x] Validador determinista posterior: esquema, que cada `chunk_id` exista, pertenezca al evento y al usuario, coincidencia de página, versión y texto citado.
- [x] Una regeneración si falla; si vuelve a fallar, abstención controlada.
- [x] `needs_human_review` ante contradicción, fecha o condición crítica ambigua.

### F5. Lista de verificación — 1 día

Hecha con un repositorio en memoria ([F5](delegacion/F5_lista_de_verificacion.md)). El SQL de Postgres queda para F5b.
- [x] Modelos de la lista de verificación: ítem con cita, categoría, carácter fundamental o no, estado (pendiente, preparado, revisado) y cambio de estado con usuario, momento y confirmación explícita.
- [x] Derivar la propuesta de ítems de la respuesta citada de `extraer_requisitos`.
- [x] Guardar solo tras confirmación explícita del usuario (acción crítica que no ejecuta el modelo).
- [x] Marcar ítems y señalar contradicciones para revisión humana.

### F6. Interfaz web y demo

Hecha (F6 a F6f): la compuerta de diseño dio PASS el 17 de noviembre y la demo está medida en [Demo_222](Demo_222.md). El adaptador de API vive en `src/licigt/consulta/api.py`.
- [x] Interfaz web desde el inicio: React, Vite y TypeScript, con pnpm, sobre FastAPI. Decisión del 16 de noviembre. El curso solo exige la demo en vivo ([I3](investigacion/I3_lista_e_interfaz.md)); la vista web la promete el anteproyecto (`Anteproyecto.md:146`, `:222`).
- [x] Muestra respuesta, fuentes, página, versión, advertencias, revisión humana y aclaración, y confirma la lista explícitamente.
- [x] Puede empezar en paralelo con F4, contra respuestas de ejemplo que cumplan `RespuestaEstructurada`.
- [x] La API es del rol 4. Si no la entrega al cerrar F5, el rol 3 escribe un adaptador reemplazable, sin tocar `src/licigt/plataforma`.
- [x] Demo con el evento 222: una consulta respondible, una sin evidencia, la comparación del cronograma (bases frente a modificación 1), una aclaración, una inyección contra la lista y la falla real de OCR de las páginas 3 y 4.

### F7. Pruebas con el rol 4
- [x] Casos de herramientas para el banco: ejecución nominal, selección errónea, parámetros fuera de rango, confirmación humana e indisponibilidad del servicio. Medidos con `make banco` (21 de 23 cumplen; [informe](../informe/Aportes_roles_1_y_3.md), banco del rol 3).
- [x] Casos de seguridad que tocan este rol (6 de 6 bloqueados tras C20): inyección directa, cita falsa, fabricación de un requisito ausente y solicitud de acción no autorizada. Propuesta de casos en [I4](investigacion/I4_evaluacion_y_jev.md).
- [x] **Experimento de JEV** ([resultado](Experimento_JEV.md): no adoptar con el flujo actual, por latencia), una mejora que el curso no exige:
  - las preguntas de prueba nuevas (unas 60) las redacta un agente proponente, las revisa un agente revisor independiente y el usuario da el visto bueno;
  - un agente adversario aporta los casos engañosos ([I5](investigacion/I5_agentes_agnosticos.md));
  - las 47 preguntas del sondeo quedan solo para desarrollo.
- [ ] **Criterio para adoptar JEV** (decisión del 16 de noviembre; reemplaza al del resumen para el asesor):
  - no aumenta los errores críticos;
  - McNemar con p < 0.05 sobre las mismas preguntas;
  - P95 dentro de los 15 s del anteproyecto;
  - motivo del cambio: con 60 casos, una diferencia de 0.05 no se distingue del ruido, y los 300 ms no tenían respaldo medido.

## Pruebas

- Esquema de salida válido en todos los caminos, incluida la abstención y el error controlado.
- El enrutador elige la herramienta esperada en el conjunto de desarrollo y respeta el límite de llamadas.
- El validador rechaza una cita inexistente, de otro evento o con texto que no coincide.
- Con `suficiente=false` la respuesta es `abstained=true`.
- El evento 222 produce `needs_human_review=true` y `coverage_status` parcial.

## Dependencias y decisiones pendientes

- **Rol 2:** confirmar contrato de F5 de su plan.
- **Rol 4:** `Contexto` autenticado, auditoría, banco de pruebas y dónde se despliega Postgres.
- **Equipo:** modelo generador y presupuesto de latencia (meta P95 de 15 s con documentos indexados).
- **Rol 1:** el OCR de las páginas 3 y 4 de la modificación del evento 222 afecta la comparación de versiones.

## Pendientes del anteproyecto que dependen de este rol

- La tabla de roles de la sección 15 del anteproyecto está desactualizada frente a `Asignacion_de_roles.md`.
- Falta incluir los carnets de Edwin Jose y Gustavo Cruz.
