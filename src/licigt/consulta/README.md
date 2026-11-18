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

## Entrada, enrutador y herramientas

- `entrada`: valida el formato y detecta señales de inyección, alcance y ambigüedad.
- `enrutador`: clasifica la intención con las variantes `reglas`, `jev` o `llm`.
- `decision`: decide si abstenerse, pedir aclaración o ejecutar una herramienta.
- `preguntas_jev`: concentra las preguntas tipadas, opciones y umbrales de JEV.
- `jev`: adapta el SDK de TypeSafe, valida respuestas y controla fallas y frecuencia.
- `presupuesto`: limita cada solicitud a tres llamadas de herramienta y una regeneración.
- `lectura`: valida la evidencia del rol 2 y convierte fragmentos en fuentes citables.
- `herramientas`: reúne evidencia con búsqueda, extracción de requisitos y comparación de versiones.
- `sondeo_jev`: compara reglas y JEV con preguntas fijas; muestra una vista previa por defecto.

`LICIGT_ENRUTADOR` elige `reglas` (por defecto), `jev` o `llm`.
El principio es «JEV juzga, el código decide»; véase [JEV en LiciGT](../../../docs/consulta/JEV.md).

- `make llm-servidor` levanta el LLM local; en WSL con Ubuntu 22.04 corre en Docker (`LICIGT_LLM_MODO`, `make llm-detener`; véase I2).
- `make deps-consulta` instala las dependencias de consulta y el SDK de JEV.
- `make sondeo-jev` muestra lo previsto, sin enviar datos ni crear registros.
- `make sondeo-jev CONFIRMAR=1` envía solo el texto de las preguntas del sondeo a JEV.
- El envío guarda su registro en `data/consulta/sondeos/`, ignorado por Git.
