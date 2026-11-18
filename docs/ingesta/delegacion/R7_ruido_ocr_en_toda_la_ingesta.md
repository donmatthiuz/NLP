# Encargo R7: filtro de ruido del OCR en toda la ingesta

Rama `proyecto`. No commitees.

## Por qué (revisión retrospectiva, veredicto "mal")

- **El filtro solo vive en un lugar:** `MIN_PALABRAS_OCR`, el umbral de ruido del OCR, solo se aplica en `reextraer.py:87`.
- **Lo que queda sin filtrar:** `make_chunks` marca indexable todo fragmento salvo la inyección (`pipeline.py:493`), y `ingest()` y `reprocess()` no filtran el ruido (`pipeline.py:628-635` y `:701-711`). La línea de comandos (OCR activo por defecto, `__main__.py:39`) y el conector (`automatic.py:214`) indexarían el ruido de sellos y firmas de un PDF escaneado nuevo.
- **Medido por la revisión:** 35 de 35 fragmentos indexables al pasar por `make_chunks` las páginas de la modificación del 222.
- El corpus curado no pasa por esa ruta, porque `reproducir` ingiere sin OCR y luego reextrae.

## Archivos

Solo `src/licigt/ingesta` y sus pruebas.

## Cambios (prueba en rojo primero)

- **Una sola regla:** el filtro `ruido_ocr` se aplica en el camino común que usan `ingest()`, `reprocess()` y `reextraer`, por ejemplo dentro de `make_chunks` para las unidades de páginas con `method != "text"`. No debe haber dos copias del umbral.
- **Pruebas:**
  - `ingest()` con una página OCR de sellos y firmas (sintética) deja esos fragmentos no indexables, con el estado `ruido_ocr`, y la página en `paginas_no_indexadas`;
  - `reprocess()`, lo mismo;
  - `make test-ingesta` en verde y `test_el_paquete_reconstruido_es_identico_al_actual` sigue pasando: el ZIP del repo no debe cambiar. Si cambia, detente y repórtalo.
- **Documentación:** en `docs/ingesta/Pendientes_rol_1.md`, deja registrado el cambio.

## Reglas

- Sin `keys/` ni git.
- No reemplaces el ZIP.
