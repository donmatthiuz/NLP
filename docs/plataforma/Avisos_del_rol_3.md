# Avisos del rol 3 para el rol 4

**Estado al 16 de noviembre de 2026.** Lo que el rol 3 necesita del rol 4 y lo que ofrece. Ninguno bloquea el trabajo del rol 3: si no hay respuesta, se avanza con la propuesta indicada. El detalle está en [Contratos](../consulta/Contratos.md#rol-4-hacia-rol-3).

## Propuestas que el rol 3 adopta por defecto

- [ ] **Contexto de acceso.** Objeto inmutable con `tenant_id`, `usuario` y `rol`, construido desde la sesión autenticada. Hoy existe `Contexto(tenant_id, usuario)` en `recuperacion/busqueda.py`; falta `rol`.
- [ ] **Auditoría.** El rol 3 llama a `auditar(evento)`, función que el rol 4 inyecta (por defecto no hace nada). Campos: `momento`, `usuario`, `tenant_id`, `evento_id`, `intencion`, `herramienta`, `chunk_ids`, `abstained`, `needs_human_review`, `validacion`, `latencia_ms`, `error`. Sin texto de PDF ni pregunta completa.
- [ ] **Salida.** La API devuelve tal cual la `RespuestaEstructurada` del rol 3 (`answer`, `sources`, `abstained`, `tool_used`, `needs_human_review`, `evento_id`, `coverage_status`, `warnings`).
- [ ] **Confirmación de la lista de verificación.** Guardar cambios solo con una acción explícita del usuario. El rol 3 produce la propuesta y el rol 4 expone el guardado con usuario y momento.
- [ ] **Configuración compartida (hecha por el rol 3 por falta de respuesta).** `.env.example` con parámetros sin secretos, `keys/` con un archivo por llave y lista de permitidos en Git, `Makefile` como puerta de entrada (`make setup`, `db-up`, `importar`, `test-*`) y `docker-compose.yml` con la contraseña generada en `keys/database/dev.password` vía secreto de Compose. El rol 4 puede ajustarlo; es su responsabilidad según la asignación.
- [ ] **Dependencias fijadas.** Los `requirements.txt` usan rangos (`>=`). Queda para el rol 4 fijar versiones exactas antes de la entrega.

## Preguntas abiertas

- [ ] **Stack de API y de pantalla.** Propuesta del rol 3: FastAPI en el backend y React con Vite y TypeScript en el frontend (Streamlit descartado). Falta definir quién construye la pantalla: el rol 3 la describe como "mostrar respuesta, fuentes, página y versión", y el rol 4 es dueño de la API.
- [ ] **JEV.** Se usará por API alojada. Cada integrante guarda su clave en `keys/jev/api.key` y el código la lee desde `LICIGT_JEV_API_KEY_FILE`. Falta confirmar que a un tercero solo se envían textos de documentos públicos y la pregunta, nunca datos de empresa.
- [ ] **Banco de pruebas.** El rol 3 aportará los casos de herramientas: ejecución nominal, selección errónea, parámetros fuera de rango, confirmación humana e indisponibilidad del servicio, más los de seguridad que tocan su módulo. Se necesita el formato final de cada caso (`id`, `question`, `expected_behavior`, `expected_sources`, `expected_pages`, `answerable`, `risk_level`).
- [ ] **GPU.** El LLM local y la recuperación del rol 2 comparten una RTX 5070 de 12 GB. Coordinar con el rol 2 el reparto.

## Lo que ofrece el rol 3

- Núcleo sin dependencias de red ni base de datos, probable con contextos y recuperadores simulados.
- Validación de parámetros y de citas con el mismo esquema; el rol 4 puede repetirla en la API como segunda barrera.
