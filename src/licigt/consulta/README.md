# Consulta y herramientas — rol 3

**Integrante:** ______________________________

Aquí se implementarán el enrutador de intención y tres herramientas de solo lectura: `buscar_documentos`, `extraer_requisitos` (incluidas fechas) y `comparar_versiones`. La respuesta propondrá una lista de verificación con citas; la aplicación guardará sus cambios únicamente tras confirmación del analista.

**Entrada:** pregunta del usuario y contexto autenticado; evidencia entregada por recuperación.

**Salida:** respuesta estructurada con `answer`, `sources`, `abstained`, `tool_used`, `needs_human_review`, `evento_id`, `coverage_status` y `warnings`, más propuesta de lista con citas.

Ver [responsabilidades e integración](../../../docs/roles/Asignacion_de_roles.md#rol-3--consulta-y-herramientas).

## Esquemas

`esquemas.py` define la respuesta con citas y los parámetros de las tres herramientas con Pydantic v2. Las dependencias están en `requirements.txt`. Pruebas desde la raíz, sin servicios externos:

```bash
PYTHONPATH=src python -m unittest discover -s src/licigt/consulta/tests -v
```
