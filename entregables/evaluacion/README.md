# Dataset y resultados de evaluación de LiciGT

Entrega del 19/11/2026. `Evaluacion_LiciGT.zip` reúne bancos estructurados, metadatos de revisión, fuentes/páginas esperadas y resultados comparativos de la corrida oficial `20261119T061552Z` (commit `3085334b8b6fd63c78cbe61cfa79a9fb0b5c7107`). No representa una nueva corrida ni transforma metas en resultados.

## Contenido

- `bancos/comun.json`: 20 casos del conjunto común, con comportamiento esperado, fuentes, páginas, partición y revisor declarado.
- `bancos/rol3.json`: 23 casos de consulta, herramientas y seguridad, incluidos los ajustes documentados antes de la corrida oficial.
- `bancos/desarrollo.json` y `calibracion.json`: conjuntos usados para desarrollar y calibrar recuperación; no son prueba independiente.
- `resultados/reporte.json` y `reporte.md`: recuperación base/mejorada, resultados completos, latencia, tokens, concurrencia y suite de seguridad.
- `resultados/comun.json` y `rol3.json`: resultados por caso de cada banco.
- `manifiesto.json`: procedencia y SHA-256 de cada archivo, commit de medición y declaración del árbol sucio durante aquella corrida.

## Reproducción y límites

Desde la raíz, `make evaluacion-paquete` reconstruye el ZIP usando los resultados ya medidos en `data/`. El comando valida ids, cantidades, commit y CRC, no ejecuta el LLM ni consulta la base. Los archivos de `data/` no viajan en un clon limpio: el ZIP entregado los conserva. Para una nueva evaluación se usan los objetivos existentes `make reporte` y `make banco`, declarando la nueva fecha y sin sustituir retrospectivamente esta corrida.

Los casos contienen preguntas y fragmentos de documentos públicos del IGSS; las empresas son ficticias. El paquete usa una lista explícita de archivos y no incluye llaves, entorno, usuarios de acceso ni auditorías de sesiones.

Cumplen 19/23 casos del rol 3 y 11/20 del banco común. P95 de 32,0 s con un usuario y 37,5 s con cinco, frente a la meta de 15 s. No hubo evento reservado limpio: los cinco eventos se usaron en desarrollo. La revisión de etiquetas usó agentes y adjudicación del usuario; no equivale a dos revisores humanos independientes. Fidelidad factual, cobertura de requisitos y tiempo de revisión con usuarios no están medidos. Los detalles y demás limitaciones se conservan en el informe técnico.
