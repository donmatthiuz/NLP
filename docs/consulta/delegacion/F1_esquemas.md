# Encargo F1: esquemas Pydantic del módulo de consulta

Para Codex u OpenCode. Trabajas en la rama `rol/consulta`. Lee primero [`AGENTS.md`](../../../AGENTS.md), [`Contratos.md`](../Contratos.md) y [`Flujo_de_trabajo.md`](../Flujo_de_trabajo.md). El gestor revisará y corregirá tu resultado; no commitees ni hagas push.

Antes de escribir código, consulta con el MCP de Context7 la documentación actual de Pydantic v2 (validadores de modelo, `ConfigDict`, `Field` con límites, `StringConstraints`). Abre el agente con `make codex` o `make opencode` para que el MCP tenga la llave.

## Objetivo

Crear los modelos Pydantic v2 del contrato de salida y de los parámetros de las tres herramientas, con pruebas escritas primero (rojo, verde, refactor). Solo eso: sin LLM, base de datos, red, enrutador ni herramientas.

**Por qué ahora:** el curso exige una salida validada por contrato (instrucciones, sección 11) y casos de parámetros fuera de rango y de abstención en el banco (sección 8); el anteproyecto fija los límites (sección 11). Lo demás se difiere: los modelos que leen la salida del rol 2 van en F3 y los de la lista de verificación en F5.

## Alcance de archivos

- Crear `src/licigt/consulta/__init__.py` (docstring corto).
- Crear `src/licigt/consulta/esquemas.py`.
- Crear `src/licigt/consulta/tests/test_esquemas.py` (con `unittest`, como el resto del repo).
- Crear `src/licigt/consulta/requirements.txt` con `pydantic>=2.6,<3`.
- Añadir al `README.md` de `src/licigt/consulta` una sección breve "Esquemas" con el comando de pruebas.

No modificar nada fuera de `src/licigt/consulta/`.

## Modelos

Todos con `model_config = ConfigDict(extra="forbid", frozen=True)`. Docstrings y comentarios en español, breves; el estilo del repo es compacto (ver `src/licigt/recuperacion/busqueda.py`).

### Respuesta

- `NombreHerramienta = Literal["buscar_documentos", "extraer_requisitos", "comparar_versiones"]`.
- `TEXTO_ABSTENCION = "No hay información suficiente en los documentos para responder"`.
- `Fuente`:
  - `doc_id: str` no vacío;
  - `source: str` no vacío (URL de origen o, si falta, `doc_id`);
  - `page: int >= 1` y `page_end: int | None` (si existe, `>= page`);
  - `chunk_id: str` no vacío;
  - `version_ingesta: int >= 0` y `version_oficial: str | None` (dos conceptos distintos: número de carga y nombre oficial, como "Modificación Número 1");
  - `cita: str` de 1 a 500 caracteres, recortada.
- `RespuestaEstructurada`:
  - `answer: str` no vacío;
  - `sources: list[Fuente]`;
  - `abstained: bool`;
  - `tool_used: NombreHerramienta | None`;
  - `needs_human_review: bool`;
  - `evento_id: str` no vacío;
  - `coverage_status: Literal["parcial", "sin_faltantes_detectados"]`;
  - `warnings: list[str]`, por defecto vacía.
- Reglas del modelo: si `abstained` es falso, debe haber al menos una fuente; si es verdadero, `answer` es exactamente `TEXTO_ABSTENCION`.

### Parámetros de herramientas

- `TipoDocumento = Literal["bases", "anexo", "aclaracion", "modificacion"]` (fuente: `src/licigt/ingesta/download.py`, línea 36).
- `Categoria = Literal["administrativa", "legal", "tecnica", "financiera"]`.
- `BuscarDocumentosParams`: `query: str` (recortada, de 1 a 500 caracteres), `evento_id: str` no vacío, `tipo_documento: TipoDocumento | None = None`, `k: int` de 1 a 10 con 5 por defecto. Nota en el docstring: el filtro por tipo lo aplica la herramienta sobre los resultados, porque `buscar()` del rol 2 no lo tiene.
- `ExtraerRequisitosParams`: `evento_id: str` no vacío, `categoria: Categoria | None = None`.
- `CompararVersionesParams`: `evento_id: str` no vacío, `tema: str` (recortado, de 1 a 500), `doc_base_id: str | None = None`, `doc_cambio_id: str | None = None`. Ambos ids o ninguno; si vienen ambos, distintos.

## Pruebas (escribirlas primero)

- Respuesta válida con una fuente; abstención válida sin fuentes; respuesta sin abstención y sin fuentes falla; abstención con otro texto falla.
- `Fuente` con `page` 0 falla; con `page_end` menor que `page` falla; `cita` vacía o de 501 caracteres falla.
- En cada modelo de parámetros fallan los campos extra `tenant_id`, `empresa`, `rol` y `usuario` (una prueba por campo, o `subTest`).
- `query` de 500 caracteres pasa; de 501, vacía o solo espacios falla.
- `k` igual a 0 o a 11 falla; 1 y 10 pasan; sin `k` vale 5.
- `tipo_documento` o `categoria` fuera de la lista fallan.
- `CompararVersionesParams`: ninguno de los ids pasa; solo uno falla; ambos iguales fallan; ambos distintos pasan.
- Los modelos son inmutables (asignar un campo falla).

## Criterios de aceptación

- `PYTHONPATH=src python -m unittest discover -s src/licigt/consulta/tests -v` en verde, sin red, GPU, Docker ni Postgres.
- Solo `pydantic` y la biblioteca estándar; no importar `licigt.recuperacion`.
- Nombres en español, salvo los campos del contrato de salida del curso (`answer`, `sources`, `abstained`, `tool_used`, `needs_human_review`, `coverage_status`, `warnings`, `page`, `page_end`, `source`).
- Nada más que lo listado: ni modelos de lista de verificación ni de lectura del rol 2.
- Sin emojis; Markdown con `-` para listas.

## Al terminar

Responde con: archivos creados, salida literal del comando de pruebas y cualquier decisión tomada donde el encargo no era claro. No amplíes el alcance.
