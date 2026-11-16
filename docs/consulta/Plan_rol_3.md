# Plan del rol 3: consulta y herramientas

**Estado al 16 de noviembre de 2026.** Este plan cubre las [responsabilidades del rol 3](../roles/Asignacion_de_roles.md#rol-3--consulta-y-herramientas) y sigue las secciones [9. Arquitectura](../anteproyecto/Anteproyecto.md#9-arquitectura), [10. Citas y abstención](../anteproyecto/Anteproyecto.md#citas-y-abstención) y [11. Herramientas y agentes](../anteproyecto/Anteproyecto.md#11-herramientas-y-agentes) del anteproyecto. El código irá en [`src/licigt/consulta`](../../src/licigt/consulta/README.md).

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

### F2. Validación de entrada y enrutador — 1.5 días
- [ ] Validación de entrada: formato, longitud, alcance (el evento pertenece al usuario) e indicios de inyección; una solicitud insegura o fuera de dominio conduce a abstención.
- [ ] Enrutador de intención hacia `buscar_documentos`, `extraer_requisitos` o `comparar_versiones`. Implementar dos variantes, reglas y salida estructurada del modelo, y compararlas con los casos de desarrollo, como pide el anteproyecto.
- [ ] Límites: máximo 3 invocaciones de herramienta por solicitud y una sola regeneración ante salida inválida.
- [ ] Manejo de la ambigüedad ("la fecha", "el medicamento"): pedir aclaración en lugar de adivinar.

### F3. Herramientas — 2 días
- [ ] Modelos tolerantes de lectura de lo que devuelve el rol 2 (`FragmentoRecuperado`, `Alerta`, `ResultadoBusqueda`) y `fuente_desde_fragmento`, según [Contratos](Contratos.md#rol-2-hacia-rol-3).
- [ ] `buscar_documentos`: envuelve `buscar()` del rol 2, propaga `suficiente` y `alertas`, y filtra por `tipo_documento` sobre los resultados (el rol 2 no tiene ese filtro).
- [ ] `extraer_requisitos`: extrae requisitos, documentos de la oferta y fechas por categoría; cada dato exige cita. Las fechas con comprobación de actividad y plazo.
- [ ] `comparar_versiones`: envuelve la función del rol 2; muestra ambas fuentes y no decide la vigencia.
- [ ] Todas de solo lectura, sin red ni comandos; ante una falla devuelven error controlado o abstención.

### F4. Generación y validación de salida — 2 días
- [ ] Prompt aumentado: instrucciones del sistema, evidencia y pregunta separadas; la evidencia se marca como datos no confiables.
- [ ] El modelo cita por `chunk_id`; instrucción de abstención explícita y manejo de la trampa "si no está en el contexto, dilo".
- [ ] Validador determinista posterior: esquema, que cada `chunk_id` exista, pertenezca al evento y al usuario, coincidencia de página, versión y texto citado.
- [ ] Una regeneración si falla; si vuelve a fallar, abstención controlada.
- [ ] `needs_human_review` ante contradicción, fecha o condición crítica ambigua.

### F5. Lista de verificación — 1 día
- [ ] Modelos de la lista de verificación: ítem con cita, categoría, carácter fundamental o no, estado (pendiente, preparado, revisado) y cambio de estado con usuario, momento y confirmación explícita.
- [ ] Derivar la propuesta de ítems de la respuesta citada de `extraer_requisitos`.
- [ ] Guardar solo tras confirmación explícita del usuario (acción crítica que no ejecuta el modelo).
- [ ] Marcar ítems y señalar contradicciones para revisión humana.

### F6. Interfaz mínima y demo — 1 día
- [ ] CLI o vista simple que muestre respuesta, fuentes, página y versión.
- [ ] Demo con el evento 222: una consulta respondible, una sin evidencia y la comparación del cronograma (bases frente a modificación 1).

### F7. Pruebas con el rol 4 — 1 día
- [ ] Casos de herramientas para el banco: ejecución nominal, selección errónea, parámetros fuera de rango, confirmación humana e indisponibilidad del servicio.
- [ ] Casos de seguridad que tocan este rol: inyección directa, cita falsa, fabricación de un requisito ausente y solicitud de acción no autorizada.

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
