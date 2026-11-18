# Encargo E1: reporte reproducible de evaluación

Rama `proyecto`. No commitees.

Lee primero:

- [`AGENTS.md`](../../../AGENTS.md);
- `docs/anteproyecto/Anteproyecto.md`, secciones de métricas, banco de pruebas y seguridad (`:390-420`): qué se reporta;
- `docs/roles/Asignacion_de_roles.md`, rol 4: la entrega verificable es un "reporte reproducible con resultados por caso, métricas y fallos conocidos";
- `src/licigt/consulta/banco.py` (`correr`, `metricas`, registro) y `src/licigt/recuperacion/evaluar.py`, que reutilizas en vez de reescribir;
- `src/licigt/consulta/llm.py`, para saber de dónde salen los tokens;
- `src/licigt/consulta/casos_banco.json` (rol 3) y `src/licigt/plataforma/tests/test_integracion.py` (permisos);
- `docs/consulta/Experimento_JEV.md`: la regla de adopción usa el P95 del resto del flujo.

## Por qué (cinco porqués del gestor; plan aprobado por el usuario)

- El rol 4 no tiene reporte. Hoy cada métrica vive en un documento distinto:
  - el banco del rol 3, en el informe;
  - Hit@5, en `Recuperacion.md`;
  - el P95, en `Experimento_JEV.md`.
- **El P95 de 29,3 s está viejo:** se midió con el reranker en CPU. Con la recuperación en GPU (R2C) hay que medirlo de nuevo con el código final, porque decide el veredicto de JEV.
- **Tokens y costo:** el anteproyecto los pide y nadie los midió.
- **Suite de seguridad:** el anteproyecto pide 8 pruebas, cada una con amenaza, componente, esperado, resultado y mitigación. Están repartidas entre el banco del rol 3 y las pruebas de plataforma.

## Archivos

- **Nuevos:** `src/licigt/plataforma/evaluacion.py` (o un paquete `evaluacion/`) y sus pruebas.
- **Makefile:** el objetivo `reporte`.
- **Cambios mínimos:**
  - en `banco.py` y en `evaluar.py`, solo si hacen falta para reutilizarlos (por ejemplo, devolver datos en vez de solo imprimirlos);
  - en `llm.py`, para exponer el `usage` de tokens que devuelve el servidor compatible con OpenAI.
- **No toques:** `web/`.

## Qué hace `make reporte`

Usa los servicios reales: Postgres con R6 y `empresa_b`, el LLM en Docker y la recuperación en GPU. Arma la URL de la base dentro del `Makefile`, como `make banco`.

1. **Recuperación, línea base contra mejorada:** Hit@5, MRR@5 y suficiencia por variante sobre `casos_desarrollo.json` y sobre un banco común.
   - El banco común se pasa por variable (`BANCO_COMUN=ruta`) y, si no existe todavía, se omite con un aviso.
   - Convierte `expected_sources` de `CasoBanco` al formato `relevantes` de `evaluar`.
2. **Extremo a extremo:** corre `banco.correr` sobre `casos_banco.json` y, si existe, sobre el banco común. Junta las métricas por caso y en total.
3. **Latencia y costo:** sobre todas las preguntas del extremo a extremo y las 47 de desarrollo del enrutador (`ciego_desarrollo.json`, si existe en `data/`):
   - P50 y P95 de la consulta completa, dentro del proceso, con `consultar()` real;
   - P95 por herramienta;
   - tokens de entrada y de salida por consulta (del `usage` del LLM);
   - llamadas al LLM;
   - una estimación por 100 consultas: tokens totales y tiempo de GPU. El costo monetario local es 0; JEV se reporta aparte con lo medido en `Experimento_JEV.md`.
4. **Suite de seguridad de 8 pruebas**, en tabla con amenaza, componente, comportamiento esperado, resultado observado y mitigación:
   - inyección directa, inyección indirecta, cita falsa, requisito fabricado y acción no autorizada, tomadas del banco del rol 3;
   - acceso cruzado entre empresas, mezcla de eventos y original sin permiso, tomadas de las pruebas de integración de plataforma, que se corren y cuyo resultado se lee.
5. **Salida:** `data/plataforma/reporte/<UTC>.json` y `<UTC>.md`.
   - Llevan fecha, commit, si el árbol está sucio, modelos con revisión, parámetros del LLM y versión del prompt.
   - No llevan texto de respuestas ni de fragmentos, contraseñas ni `tenant_id` fuera de los nombres ficticios.
   - El `.md` tiene las tablas listas para el informe: Markdown sin emojis y listas con `-`.

## Pruebas (en rojo primero, con dobles, sin red ni base)

- La conversión de `CasoBanco` a `relevantes`.
- El cálculo del P95, el de tokens y la estimación por 100 consultas, con valores conocidos.
- La tabla de seguridad: un caso que falla sale como fallo, no se oculta.
- El `.md` no contiene texto de respuestas.
- Si falta el banco común, se omite con un aviso, sin romper.

## Criterios de aceptación

- `make test-plataforma` y `make test-consulta` en verde.
- Una corrida real de `make reporte` sin el banco común (todavía no existe), con el archivo generado. Repórtame las cifras: P95 total y por herramienta, tokens, y Hit@5 y MRR@5 de desarrollo.

## Reglas

- Sin `keys/`.
- No uses `make ... PYTHON=...` para correr scripts propios.
- Las pruebas contra la base, con los objetivos `make`.
