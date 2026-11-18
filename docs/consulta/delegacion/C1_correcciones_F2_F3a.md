# Encargo C1: correcciones de F2 y F3a

Para Codex u OpenCode. Rama `rol/consulta`. Lee primero [`AGENTS.md`](../../../AGENTS.md), [`Contratos.md`](../Contratos.md) (reglas de uso) y `src/licigt/recuperacion/busqueda.py`, función `_alertas` (líneas 104-129). Abre el agente con `make codex` o `make opencode`. El gestor auditará el resultado; no commitees.

**En paralelo:**

- otro agente corrige los diagramas en `docs/arquitectura/diagramas/` y `scripts/exportar_diagramas.sh`;
- otro hace F3b en `src/licigt/consulta/requisitos.py`, `preguntas_jev.py` y `tests/test_requisitos.py`.

No toques esos archivos.

## Archivos

| Archivo | Qué |
|---|---|
| `src/licigt/consulta/herramientas.py` | Corrección 1 |
| `src/licigt/consulta/tests/test_herramientas.py` | Pruebas de la corrección 1 |
| `Makefile` | Objetivos `deps-consulta` y `sondeo-jev`; no toques el objetivo `diagramas` |
| `.env.example` | Variables del enrutador y de JEV, sin secretos |
| `src/licigt/consulta/README.md` | Sección nueva, sin borrar la de Esquemas |

Nada más.

## 1. El filtro por tipo pierde la cláusula base del conflicto (defecto confirmado)

En el rol 2, la alerta `posible_conflicto` lleva el `doc_id` de la **modificación o aclaración**, y los fragmentos de las bases que modifica van en `chunk_ids_afectados` (`busqueda.py:119-123`). `buscar_documentos` (`herramientas.py:93-95`) conserva los fragmentos de `doc_id` en conflicto y los de `incluido_por == "posible_conflicto"`, pero no los de `chunk_ids_afectados`.

Reproducción con el propio fixture de las pruebas:

```python
buscar_documentos(ctx, params_buscar(tipo_documento="modificacion"),
                  RecuperadorFalso(busqueda=busqueda_222()))
# fragmentos: ['222-mod-p1-0', '222-mod-p2-0']; falta '222-bases-p8-0'
```

Viola la regla no negociable de mostrar ambas fuentes de una contradicción.

**Corrección:** al filtrar por tipo, conserva también los fragmentos cuyo `chunk_id` esté en `chunk_ids_afectados` de alguna alerta `posible_conflicto`. Comenta en una línea por qué hay tres vías: `doc_id` de la alerta, `incluido_por` y `chunk_ids_afectados`.

**Pruebas (primero en rojo):**

- con `tipo_documento="modificacion"` en el caso 222 quedan `222-bases-p8-0` y los dos fragmentos de `222-mod`;
- con `tipo_documento="anexo"` quedan las dos fuentes del conflicto y nada más.

## 2. Poder correr el sondeo de JEV

`sondeo_jev.py` no tiene un objetivo de make y el SDK no se instala con nada. Añade al `Makefile`, siguiendo el estilo de los objetivos existentes (con `##` para la ayuda y en `.PHONY`):

- `deps-consulta`: `$(PYTHON) -m pip install -r src/licigt/consulta/requirements.txt`.
- `sondeo-jev`:
  - sin variables, corre `PYTHONPATH=src $(PYTHON) -m licigt.consulta.sondeo_jev` (vista previa, sin envío);
  - con `CONFIRMAR=1`, añade `--confirmar-envio`;
  - pasa al proceso `LICIGT_JEV_API_KEY_FILE` y, si están definidas en `.env`, `LICIGT_JEV_MODELO`, `LICIGT_JEV_REINTENTOS`, `LICIGT_JEV_TIEMPO_ESPERA`, `LICIGT_JEV_ESPERA_REINTENTO`, `LICIGT_JEV_MAX_SOLICITUDES_SEG` y `LICIGT_JEV_ESPERA_FRECUENCIA`;
  - la clave nunca pasa por la línea de comandos: el código la lee del archivo.

En `.env.example`, debajo de `LICIGT_JEV_API_KEY_FILE`, añade con un comentario breve cada una:

- `LICIGT_ENRUTADOR=reglas` (valores: `reglas`, `jev`, `llm`);
- `LICIGT_JEV_MODELO=jev-1.14.0`.

Los demás límites no van en `.env.example`: tienen valor por defecto en `config.py`.

**No ejecutes** `make sondeo-jev CONFIRMAR=1`: envía datos a un servicio externo y lo corre el usuario. Sí ejecuta `make sondeo-jev` (vista previa) y `make help`, y pega la salida en tu respuesta, recortando la vista previa a las primeras 15 líneas.

## 3. README de consulta

Añade una sección `## Entrada, enrutador y herramientas` al README de consulta, de 15 a 25 líneas con:

- qué hace cada módulo (`entrada`, `enrutador`, `decision`, `preguntas_jev`, `jev`, `presupuesto`, `lectura`, `herramientas`, `sondeo_jev`), una línea cada uno;
- las tres variantes del enrutador y cómo se elige (`LICIGT_ENRUTADOR`);
- el principio "JEV juzga, el código decide", enlazando `docs/consulta/JEV.md`;
- cómo correr el sondeo (`make deps-consulta`, `make sondeo-jev`, `make sondeo-jev CONFIRMAR=1`), qué se envía (solo el texto de las preguntas) y dónde queda el registro (`data/consulta/sondeos/`, ignorado por Git).

Markdown sin emojis, listas con `-`, sin otro `#`.

## Criterios de aceptación

- `make test-consulta` en verde, sin servicios.
- `make help` muestra los dos objetivos nuevos.
- `make sondeo-jev` (sin `CONFIRMAR`) imprime la vista previa y no crea archivos en `data/`.

## Al terminar

Responde con los archivos tocados, la salida literal de `make test-consulta` (solo el resumen final), de `make help` y de `make sondeo-jev` (recortada), y las decisiones donde el encargo no era claro. No amplíes el alcance.
