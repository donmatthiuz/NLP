# Recuperación y RAG — rol 2

**Integrante:** ______________________________

Este módulo importa el [paquete de ingesta](../../../entregables/recuperacion/README.md) a PostgreSQL con `pgvector` y devuelve evidencia autorizada de un evento, con puntajes y alertas. El diseño y los resultados están en [`docs/recuperacion`](../../../docs/recuperacion/Recuperacion.md).

| Archivo | Qué hace |
|---|---|
| `schema.sql` | Crea las tablas `documentos` y `fragmentos`, el índice `tsvector` en español (GIN), los índices HNSW de coseno (384 y 1024 dimensiones) y la seguridad por fila con el rol `licigt_app`. |
| `indice.py` | Valida el ZIP, genera las ventanas de 120 tokens de la línea base, calcula los embeddings e importa todo. La importación se puede repetir sin duplicar datos. |
| `busqueda.py` | Contiene `buscar()` (variantes `base` y `mejorada`) y `comparar_versiones()`. |
| `__main__.py` | CLI de desarrollo. |

## Uso

```bash
docker compose up -d                       # Postgres + pgvector en 127.0.0.1:5432
nix-shell                                  # NixOS; en otros sistemas: python3.12 -m venv .venv && pip install -r src/licigt/recuperacion/requirements.txt
export PYTHONPATH=src
export LICIGT_DB_URL="postgresql://licigt:<contraseña>@127.0.0.1:5432/licigt"   # o usar make
python -m licigt.recuperacion importar     # usa entregables/recuperacion/empresa_demo.zip
python -m licigt.recuperacion buscar --evento 222-IGSS-2023 "fecha de recepción de ofertas"
python -m licigt.recuperacion buscar --evento 222-IGSS-2023 --variante base "fecha de recepción de ofertas"
python -m licigt.recuperacion comparar --evento 222-IGSS-2023 "cronograma de actividades"
python -m unittest discover -s src/licigt/recuperacion/tests -v
```

La conexión exige `LICIGT_DB_URL` y no tiene valor por defecto. Con el `Makefile` del equipo, `make importar` y `make test-recuperacion` la arman a partir de `keys/database/dev.password`. Los modelos usan revisiones fijas en Hugging Face (`REVISION`, en `indice.py`).

## Contrato para el rol 3

`buscar(ctx, evento_id, pregunta, variante="mejorada", k=5)` devuelve:

```json
{"evento_id": "...", "variante": "mejorada", "suficiente": true,
 "fragmentos": [{"chunk_id": "...", "doc_id": "...", "tipo_documento": "bases", "version_ingesta": 1,
                 "identificador_version_oficial": null, "pagina_inicio": 8, "pagina_fin": 8,
                 "seccion": "2.2 CRONOGRAMA ...", "texto": "...", "url_origen": "https://...",
                 "score": 0.91, "reranker": 0.91, "semantico": 0.62, "lexico": 0.4, "rrf": 0.016}],
 "alertas": [{"tipo": "posible_conflicto", "doc_id": "...", "numerales_modificados": ["2.2", "2.7"],
              "chunk_ids_afectados": ["..."]},
             {"tipo": "cobertura_incompleta", "doc_id": "...", "paginas_no_indexadas": [3, 4]},
             {"tipo": "evento_con_modificaciones", "doc_id": "...", "documento": "Modificación Número 1"}]}
```

- `ctx` es un `Contexto(tenant_id)` que entrega el rol 4 desde la sesión autenticada. El `tenant_id` del paquete no autoriza nada por sí solo.
- Cada consulta filtra por empresa y evento en el `WHERE` y además activa la seguridad por fila (`SET LOCAL ROLE licigt_app`).
- `suficiente=false` significa que la evidencia no supera el umbral, y en ese caso el rol 3 debe abstenerse.
- `evento_con_modificaciones` indica que el evento tiene una modificación que no aparece en los resultados.
- `comparar_versiones(ctx, evento_id, pregunta, k=2)` devuelve los `k` mejores fragmentos de cada documento del evento.
- `chunk_id` es estable al reimportar. En la variante mejorada lo asigna la ingesta (rol 1). En la base es `<doc_id>:b<página>-<ventana>`, que es determinista mientras no cambie el texto de la página.
- Ante un `posible_conflicto`, se devuelven tanto la cláusula de las bases como la de la modificación. La búsqueda no decide cuál está vigente.
