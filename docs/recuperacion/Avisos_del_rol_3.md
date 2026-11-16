# Avisos del rol 3 para el rol 2

**Estado al 16 de noviembre de 2026.** Lo que el rol 3 consume de recuperación y lo que necesita saber o confirmar. Ninguno bloquea el trabajo del rol 3: si no hay respuesta, se avanza con la opción por defecto indicada. El contrato completo está en [Contratos](../consulta/Contratos.md#rol-2-hacia-rol-3).

## Confirmaciones

- [ ] **Contrato tal como está en el código.** El rol 3 consume `buscar()` y `comparar_versiones()` con la forma que devuelven hoy (commit `5ccbc50`). Por defecto: no se renombra ningún campo sin avisar.
- [ ] **`chunk_id` estable.** Las citas del rol 3 y las listas de verificación guardadas dependen de que un `chunk_id` no cambie al reimportar el ZIP. Por defecto: se asume estable, como indica el [plan del rol 2](Plan_rol_2.md) (importación idempotente, identificadores sin cambios).

## Diferencias de documentación

- [ ] El [README de recuperación](../../src/licigt/recuperacion/README.md) lista dos alertas; el código emite tres. Falta `evento_con_modificaciones` (`busqueda.py`, función `_alertas`).
- [ ] [`Plan_rol_2.md`](Plan_rol_2.md) describe `comparar_versiones(ctx, evento_id, seccion)`; el código recibe `pregunta` y `k`.
- [ ] El anteproyecto declara `comparar_versiones(evento_id, doc_base_id, doc_cambio_id)`. El rol 3 lo adapta: la herramienta recibe `tema` y ids opcionales, y llama a la función de recuperación con `tema` como `pregunta`. Si faltan ids, se usan todos los documentos del evento.

## Peticiones de baja prioridad

- [ ] **Filtro `tipo_documento` en `buscar()`.** La herramienta `buscar_documentos` lo declara como opcional. Por defecto: el rol 3 filtra los resultados después de recibirlos. Se pide el filtro en SQL solo si ese recorte deja menos de `k` fragmentos en los casos del banco.

## Configuración y reproducibilidad

- [ ] **Contraseña de la base.** Se quitó `licigt_dev` de `docker-compose.yml`: ahora `make keys-init` genera `keys/database/dev.password` y Compose la lee como secreto. En un volumen ya creado con la contraseña anterior, correr `make db-up` y luego `make db-password-sync`; no se borran datos.
- [ ] **Quitar el valor por defecto de `LICIGT_DB_URL`** en `indice.py` (línea 14), que contiene la contraseña vieja. El `Makefile` ya arma la URL desde `keys/`. Por defecto: se deja hasta que el rol 2 lo cambie, porque es su código.
- [ ] **Fijar la revisión de los modelos.** `SentenceTransformer` y `CrossEncoder` se crean sin `revision=` (`indice.py`, función `modelo`; `busqueda.py`, función `reranker`). Pedimos fijarla y guardarla en la salida de `evaluar.py` junto con los nombres. Mientras tanto, `make models-status` muestra la revisión descargada en `models/` y se anota en la tabla de [Recuperacion](Recuperacion.md#índices).
- [ ] **Caché de modelos.** `make` exporta `HF_HOME=<repo>/models`, así que los modelos se descargan dentro del proyecto (ignorado por Git) sin cambiar código. Usar `make importar`, `make buscar` y `make test-recuperacion`.

## Coordinación de GPU

- [ ] La máquina de desarrollo del rol 3 tiene una RTX 5070 de 12 GB. El reranker y los embeddings de recuperación comparten GPU con el LLM local del rol 3. Pedimos el consumo de VRAM medido de `bge-m3` y `bge-reranker-v2-m3` para repartir memoria. Por defecto: se asumen unos pocos GB y el LLM se elige para caber en el resto.
