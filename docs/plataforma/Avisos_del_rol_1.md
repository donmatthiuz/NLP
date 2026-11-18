# Avisos del rol 1 para el rol 4

Lo que ingesta propone al rol 4 (API, auditoría). Sin cambios en el contrato del rol 4 hasta que lo acepte.

## Evento de carga

- [ ] **Contrato propuesto.** `licigt.ingesta.eventos.evento_de_carga(manifest) -> dict`, función pura que resume una carga para la auditoría:
  - `tenant_id`, `evento_id`, `doc_id`, `hash_sha256`;
  - `status` (`completo` o `requiere_revision`; si hay páginas ilegibles siempre es `requiere_revision`);
  - `paginas_legibles`, `paginas_total`, `warnings`;
  - `created_at` y, si hubo reextracción con OCR, `reextracted_at`.
- El evento nunca incluye texto de páginas ni de fragmentos, rutas locales ni credenciales.
- **Por defecto:** el rol 4 guarda ese diccionario en su auditoría al terminar cada carga. Mientras no exista, la CLI lo imprime en JSON:

  ```bash
  PYTHONPATH=src python -m licigt.ingesta.eventos --manifiesto data/ingesta/manifiestos_igss/<doc_id>.json
  ```

## Conector del portal

- [ ] **`tipo_documento` y `document_key` explícitos.** `ingest_event` y la CLI de `automatic.py` ya no asumen `bases`; las modificaciones, aclaraciones y anexos exigen `relacion_documental`. Si la API del rol 4 llama al conector, debe pasar esos tres datos. Por defecto: la interfaz de carga los pide al usuario.
