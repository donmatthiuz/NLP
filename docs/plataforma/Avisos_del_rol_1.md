# Avisos del rol 1 para el rol 4

**Estado al 19 de noviembre de 2026:** cerrado. `auditoria.registrar_carga(evento)` guarda el evento en el archivo JSONL del rol 4 y descarta los campos fuera del contrato. La ingesta lo conecta con `--auditar` en `licigt.ingesta.prepare_corpus` y en `licigt.ingesta.automatic`; el conector se importa solo cuando se usa, para no acoplar las capas. Mientras no se pase la opción, la CLI sigue imprimiendo el evento en JSON.

## Evento de carga

- [x] **Contrato aceptado.** `licigt.ingesta.eventos.evento_de_carga(manifest) -> dict`, función pura que resume una carga para la auditoría:
  - `tenant_id`, `evento_id`, `doc_id`, `hash_sha256`;
  - `status` (`completo` o `requiere_revision`; si hay páginas ilegibles siempre es `requiere_revision`);
  - `paginas_legibles`, `paginas_total`, `warnings`;
  - `created_at` y, si hubo reextracción con OCR, `reextracted_at`.
- El evento nunca incluye texto de páginas ni de fragmentos, rutas locales ni credenciales.
- **Cómo se usa:** con `--auditar`, la carga termina guardando el diccionario en la auditoría del rol 4. Sin la opción, la CLI lo imprime en JSON:

  ```bash
  PYTHONPATH=src python -m licigt.ingesta.eventos --manifiesto data/ingesta/manifiestos_igss/<doc_id>.json
  ```

## Conector del portal

- [ ] **`tipo_documento` y `document_key` explícitos.** `ingest_event` y la CLI de `automatic.py` ya no asumen `bases`; las modificaciones, aclaraciones y anexos exigen `relacion_documental`. Si la API del rol 4 llama al conector, debe pasar esos tres datos. Por defecto: la interfaz de carga los pide al usuario.
