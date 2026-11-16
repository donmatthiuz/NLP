# Encargo F3a: lectura del rol 2, `buscar_documentos` y `comparar_versiones`

Para Codex u OpenCode. Rama `rol/consulta`. Lee primero [`AGENTS.md`](../../../AGENTS.md), [`Contratos.md`](../Contratos.md) (sección "Rol 2 hacia rol 3") y `src/licigt/recuperacion/busqueda.py` (funciones `buscar`, `comparar_versiones` y `_alertas`). Abre el agente con `make codex` o `make opencode`. El gestor auditará el resultado; no commitees.

**En paralelo** otro agente hace F2 en `esquemas.py`, `config.py`, `entrada.py`, `enrutador.py`, `preguntas_jev.py`, `jev.py`, `presupuesto.py`, `decision.py`, `sondeo_jev.py`, `requirements.txt` y sus pruebas; otro hace los diagramas. No toques esos archivos. De `esquemas.py` solo se importa (`Fuente`, `NombreHerramienta`, los modelos de parámetros); no lo modifiques.

## Objetivo

Dos de las tres herramientas de solo lectura. Leen lo que devuelve recuperación, aplican las reglas de uso del contrato y entregan un resultado intermedio que consumirá la generación (F4). `extraer_requisitos` queda para F3b, porque necesita el cliente de JEV de F2.

**Por qué:** `Plan_rol_3.md` (F3), `Anteproyecto.md` (sección 11) y las reglas de uso de `Contratos.md`. La demo pide comparar las bases y la modificación del evento 222 mostrando ambas fuentes y pidiendo revisión humana.

## Archivos

Solo crear:

- `src/licigt/consulta/lectura.py`;
- `src/licigt/consulta/herramientas.py`;
- `src/licigt/consulta/tests/test_lectura.py`;
- `src/licigt/consulta/tests/test_herramientas.py`.

Nada más.

## 1. Lectura tolerante (`lectura.py`)

Modelos con `ConfigDict(extra="ignore", frozen=True)`: se acepta cualquier campo extra y faltar uno obligatorio es error de contrato.

- **`FragmentoRecuperado`:**
  - obligatorios: `chunk_id`, `doc_id`, `tipo_documento`, `version_ingesta`, `pagina_inicio`, `pagina_fin`, `texto`, `score`;
  - opcionales, que pueden venir nulos: `seccion`, `url_origen`, `identificador_version_oficial`, `reranker`, `semantico`, `lexico`, `rrf`, `incluido_por`.
- **`Alerta`:**
  - `tipo: str` (no un `Literal`) y `doc_id: str`;
  - opcionales, que pueden venir nulos: `documento`, `status`, `paginas_no_indexadas: list[int] | None`;
  - `numerales_modificados: list[str] = []` y `chunk_ids_afectados: list[str] = []`.
  - Constante `TIPOS_ALERTA_CONOCIDOS` con los tres tipos.
- **`ResultadoBusqueda`:** `evento_id`, `variante`, `suficiente: StrictBool`, `fragmentos: list[FragmentoRecuperado]`, `alertas: list[Alerta] = []`.
- **`DocumentoComparado`:** `doc_id`, `tipo_documento`, `identificador_version_oficial: str | None`, `fragmentos: list[FragmentoRecuperado]`. Los fragmentos de comparar traen los mismos campos que los de buscar (`busqueda.py`, `CAMPOS`).
- **`ResultadoComparacion`:** `evento_id`, `documentos: list[DocumentoComparado]`.
- **`fuente_desde_fragmento(fragmento, cita) -> Fuente`:**
  - `source` es `url_origen` y, si falta, `doc_id`;
  - `page` es `pagina_inicio`;
  - `page_end` solo si difiere de `pagina_inicio`;
  - `version_oficial` es `identificador_version_oficial`.

## 2. Herramientas (`herramientas.py`)

- `Recuperador` es un `Protocol` con las firmas exactas del rol 2: `buscar(ctx, evento_id, pregunta, variante="mejorada", k=5)` y `comparar_versiones(ctx, evento_id, pregunta, k=2)`. El módulo `licigt.recuperacion.busqueda` lo cumple por tipado estructural, pero **no lo importes**: quien conecte el real lo hará en otra fase.
- `ctx` se pasa tal cual al recuperador; las herramientas no lo leen ni definen su tipo.
- Se usa siempre `variante="mejorada"`.

### Resultado intermedio

`ResultadoHerramienta`, con `ConfigDict(extra="forbid", frozen=True)`:

- `herramienta: NombreHerramienta` y `evento_id: str`;
- `fragmentos: list[FragmentoRecuperado]`;
- `documentos: list[DocumentoComparado] = []`, solo en comparar;
- `abstener: StrictBool` y `needs_human_review: StrictBool`;
- `coverage_status: Literal["parcial", "sin_faltantes_detectados"]`;
- `warnings: list[str]`;
- `error: Literal["falla_recuperacion", "contrato_invalido", "documento_fuera_del_evento"] | None`.

### Reglas comunes (de `Contratos.md`)

- `suficiente = false` significa abstener, y no se llama a nada más.
- `posible_conflicto` significa `needs_human_review = true`, y se conservan ambas fuentes.
- `cobertura_incompleta` significa `coverage_status = "parcial"` y una advertencia con el `doc_id` y las páginas no indexadas.
- `evento_con_modificaciones` añade una advertencia.
- Un tipo de alerta desconocido no rompe nada: se conserva y se añade una advertencia `alerta_desconocida: <tipo>`.
- Advertencias: textos cortos con un código al inicio (`cobertura_incompleta: ...`). Nunca incluyen texto del PDF.
- Sin `cobertura_incompleta`, el estado es `sin_faltantes_detectados`.
- Una excepción del recuperador da `error="falla_recuperacion"` y `abstener=True`. Un `ValidationError` al leer da `error="contrato_invalido"` y `abstener=True`. Nunca se lanza una excepción hacia afuera.

### `buscar_documentos(ctx, params: BuscarDocumentosParams, recuperador)`

1. Llama a `buscar(ctx, params.evento_id, params.query, variante="mejorada", k=params.k)`.
2. Si hay `tipo_documento`, filtra los fragmentos por ese tipo, **pero conserva siempre** los que tienen `incluido_por == "posible_conflicto"` y los de documentos nombrados en una alerta `posible_conflicto`. Mostrar ambas fuentes es una regla no negociable (`AGENTS.md`).
3. Si tras el filtro no queda ningún fragmento, abstiene con la advertencia `sin_fragmentos_del_tipo`, aunque `suficiente` fuera verdadero.

### `comparar_versiones(ctx, params: CompararVersionesParams, recuperador)`

1. Llama a `recuperador.comparar_versiones(ctx, params.evento_id, params.tema, k=2)` y además a `recuperador.buscar(ctx, params.evento_id, params.tema, variante="mejorada", k=5)`. La función de comparar del rol 2 no devuelve alertas ni suficiencia, y la de buscar sí.
2. Si vienen `doc_base_id` y `doc_cambio_id`:
   - ambos deben estar entre los documentos devueltos; si no, `error="documento_fuera_del_evento"` y abstener;
   - se conservan solo esos dos documentos.
3. Si quedan menos de dos documentos con fragmentos, abstiene con la advertencia `sin_documentos_para_comparar`.
4. `needs_human_review` es verdadero si hay una alerta `posible_conflicto` o si algún documento comparado es `modificacion` o `aclaracion`. El sistema muestra ambas cláusulas y nunca decide la vigencia (`Anteproyecto.md`, secciones 10 y 13).
5. `fragmentos` lleva los de buscar; `documentos`, los de comparar.

## Pruebas (escribirlas primero, sin Postgres, GPU ni red)

Usa un recuperador falso que devuelva diccionarios con la forma exacta del código del rol 2: todos los campos de `CAMPOS` más los puntajes, y las tres alertas como las arma `_alertas`, incluidos nulos.

Casos mínimos:

- **Lectura:**
  - acepta campos extra;
  - falla si falta `suficiente` o `chunk_id`;
  - acepta nulos en `paginas_no_indexadas`, `documento` e `identificador_version_oficial`.
- **`fuente_desde_fragmento`:** con y sin `url_origen`, con una página y con un rango.
- **Caso 222 con `buscar_documentos`:** bases con la cláusula 2.2.6, el fragmento de la modificación con `incluido_por="posible_conflicto"`, y las alertas `posible_conflicto` y `cobertura_incompleta` (páginas 3 y 4). Resultado: `needs_human_review` verdadero, `coverage_status` parcial, advertencia de páginas y ambas fuentes presentes.
- **Filtro por tipo:** con `tipo_documento="bases"` no se pierde el fragmento de la modificación en conflicto. Con un tipo sin fragmentos, abstiene.
- `suficiente = false` abstiene.
- **Comparar 222 sin ids:** dos documentos, `needs_human_review` verdadero.
- **Comparar con ids:** con ids válidos, solo esos dos documentos. Con un id ajeno al evento, `documento_fuera_del_evento`.
- **Comparar con un solo documento:** abstiene con `sin_documentos_para_comparar`.
- Una alerta de tipo desconocido da una advertencia y no rompe.
- **Errores:** si el recuperador lanza una excepción, `falla_recuperacion`; si devuelve un diccionario sin un campo obligatorio, `contrato_invalido`.
- El `ctx` llega al recuperador sin cambios, sea el objeto que sea.
- Importar `herramientas` y `lectura` no carga `licigt.recuperacion` (revisa `sys.modules`).

## Criterios de aceptación

- `make test-consulta` en verde, sin servicios.
- Sin texto de PDF en advertencias ni errores.
- Nombres en español, salvo los campos del contrato del curso.

## Al terminar

Responde con los archivos creados, la salida literal de `make test-consulta` y las decisiones que tomaste donde el encargo no era claro. No amplíes el alcance.
