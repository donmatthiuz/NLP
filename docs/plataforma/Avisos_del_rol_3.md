# Avisos del rol 3 para el rol 4

**Estado al 18 de noviembre de 2026**, con lo resuelto marcado. Lo que el rol 3 necesita del rol 4 y lo que ofrece. Ninguno bloquea el trabajo del rol 3: si no hay respuesta, se avanza con la propuesta indicada. El detalle está en [Contratos](../consulta/Contratos.md#rol-4-hacia-rol-3).

## Propuestas que el rol 3 adopta por defecto

- [x] **Contexto de acceso.** Objeto inmutable con `tenant_id`, `usuario` y `rol`, construido desde la sesión autenticada. Hoy existe `Contexto(tenant_id, usuario)` en `recuperacion/busqueda.py`; falta `rol`. Resuelto en P1 (`946d228`): la sesión lleva `tenant_id`, `usuario` y `rol`; el rol se exige en las rutas y `Contexto` conserva `tenant_id` y `usuario`.
- [x] **Auditoría.** El rol 3 llama a `auditar(evento)`, función que el rol 4 inyecta (por defecto no hace nada). Campos: `momento`, `usuario`, `tenant_id`, `evento_id`, `intencion`, `herramienta`, `chunk_ids`, `abstained`, `needs_human_review`, `validacion`, `latencia_ms`, `error`. Sin texto de PDF ni pregunta completa. Resuelto en P1; desde P2 (`9b22d02`) el usuario va seudonimizado.
- [x] **Salida.** La API devuelve tal cual la `RespuestaEstructurada` del rol 3 (`answer`, `sources`, `abstained`, `tool_used`, `needs_human_review`, `evento_id`, `coverage_status`, `warnings`). Resuelto: la API devuelve `RespuestaEstructurada`.
- [x] **Confirmación de la lista de verificación.** Guardar cambios solo con una acción explícita del usuario. El rol 3 produce la propuesta y el rol 4 expone el guardado con usuario y momento. Resuelto (F6c y F6d, `13f3e22`, `d3221f0`).
- [x] **Configuración compartida (hecha por el rol 3 por falta de respuesta).** `.env.example` con parámetros sin secretos, `keys/` con un archivo por llave y lista de permitidos en Git, `Makefile` como puerta de entrada (`make setup`, `db-up`, `importar`, `test-*`) y `docker-compose.yml` con la contraseña generada en `keys/database/dev.password` vía secreto de Compose. El rol 4 puede ajustarlo; es su responsabilidad según la asignación. Mantenida por el rol 3.
- [ ] **Dependencias fijadas.** Los `requirements.txt` usan rangos (`>=`). Queda para el rol 4 fijar versiones exactas antes de la entrega. Abierto: E2 (`345445c`) unificó las dependencias, pero las versiones siguen sin fijarse con exactitud.

## Preguntas abiertas

- [x] **Stack de API y de pantalla.** Propuesta del rol 3: FastAPI en el backend y React con Vite y TypeScript en el frontend (Streamlit descartado). Falta definir quién construye la pantalla: el rol 3 la describe como "mostrar respuesta, fuentes, página y versión", y el rol 4 es dueño de la API. Adoptado: FastAPI y React con Vite y TypeScript; la pantalla la hizo el rol 3.
- [x] **JEV.** Se usará por API alojada. Cada integrante guarda su clave en `keys/jev/api.key` y el código la lee desde `LICIGT_JEV_API_KEY_FILE`. Falta confirmar que a un tercero solo se envían textos de documentos públicos y la pregunta, nunca datos de empresa. Confirmado: solo salen la pregunta y fragmentos públicos ([JEV](../consulta/JEV.md#datos-que-salen-del-equipo)).
- [x] **Banco de pruebas.** El rol 3 aportará los casos de herramientas: ejecución nominal, selección errónea, parámetros fuera de rango, confirmación humana e indisponibilidad del servicio, más los de seguridad que tocan su módulo. Se necesita el formato final de cada caso (`id`, `question`, `expected_behavior`, `expected_sources`, `expected_pages`, `answerable`, `risk_level`). Entregado: banco del rol 3 (`6b9910e`) y banco común (`f4e58d8`).
- [x] **GPU.** El LLM local y la recuperación del rol 2 comparten una RTX 5070 de 12 GB. Coordinar con el rol 2 el reparto. Resuelto en R2C (`c7d0dcc`).

## Lo que ofrece el rol 3

- Núcleo sin dependencias de red ni base de datos, probable con contextos y recuperadores simulados.
- Validación de parámetros y de citas con el mismo esquema; el rol 4 puede repetirla en la API como segunda barrera.

## Avisos del 16 de noviembre (investigaciones I1 a I4)

Cada aviso trae su texto completo y su opción por defecto en la investigación de origen; aquí va el resumen.

- [x] **API e interfaz** ([I3](../consulta/investigacion/I3_lista_e_interfaz.md#avisos-propuestos-para-el-rol-4)): Hecho (`13f3e22`, `946d228`).
  - cinco rutas mínimas: consulta, propuesta de lista, listar, guardar y cambiar estado;
  - `RespuestaEstructurada` tal cual;
  - guardar la lista solo con `confirmado: true` en una petición aparte del usuario.

  Por defecto: la interfaz web es del rol 3 (React, Vite y TypeScript). Si al cerrar F5 no hay API, el rol 3 escribe un adaptador FastAPI reemplazable, sin tocar `src/licigt/plataforma`.
- [x] **Tablas de la lista de verificación:** `lista_items` y `lista_cambios`, con la misma seguridad por fila que el rol 2. Por defecto: las crea el rol 3 en un SQL de su módulo y el rol 4 revisa las políticas. Hecho (`ecb37e0`).
- [x] **Auditoría ampliada.** Campos opcionales nuevos en el evento: `chunk_ids_citados`, `modelo_generador` y `version_prompt` (diapositivas 259 y 263). Por defecto: el rol 3 los envía y la función `auditar` puede ignorarlos. Hecho: la auditoría acepta `chunk_ids_citados`, `modelo_generador` y `version_prompt`.
- [x] **Banco y métricas** ([I4](../consulta/investigacion/I4_evaluacion_y_jev.md#avisos-propuestos-para-el-rol-4)): Hecho (`926863b`).
  - formato de casos compatible con `casos_desarrollo.json`;
  - unos 15 casos mínimos del rol 3;
  - métricas calculadas en código;
  - plantilla de fidelidad para revisión humana;
  - reporte separado del experimento de JEV.

  Por defecto: el rol 3 entrega sus casos y la función de métricas en su módulo.
- [x] **LLM generador** ([I2](../consulta/investigacion/I2_llm_local.md#6-avisos-para-el-rol-2-y-el-rol-4)): Hecho: el reporte registra modelo, revisión y parámetros, y el P95 con 1 y con 5 usuarios (E3, `987b2f6`).
  - es un proceso aparte en `127.0.0.1:8080`, sin llave y nunca expuesto fuera de la máquina;
  - con OpenAI activado, solo salen la pregunta y los fragmentos públicos;
  - el P95 se reporta con 1 y con 5 usuarios por separado;
  - el resultado del banco registra el modelo, la revisión, el sha256 y los parámetros.

  Por defecto: el rol 3 añade esos campos al resultado del banco, no a la auditoría.
