# Encargo C21: cobertura veraz y presupuesto de tiempo

Rama `proyecto`. No commitees. Decisiones del usuario del 18 de noviembre, a partir de la revisión retrospectiva ([`Revision_retrospectiva.md`](../Revision_retrospectiva.md)).

## Por qué

- **`coverage_status` miente:** con afirmaciones descartadas, la publicación parcial (C14) pone `coverage_status='parcial'`. `Anteproyecto.md:351` y `Contratos.md` lo definen como la cobertura según el inventario. La web dice entonces "hay páginas o documentos sin indexar" donde no los hay (`r3-nom-extraer`, evento 368).
- **Latencia:** el P95 es de 25,2 s frente a la meta de 15 s (`docs/plataforma/Reporte_evaluacion.md`).
  - 11 de las 14 consultas que pasan de 15 s regeneraron.
  - `tiempo_espera` de 20 s (`config.py:49`) no cuadra con `max_tokens` de 3072: a unos 85 tok/s, 3072 tokens tardan unos 36 s.
  - La consulta que fija el P95 (`222-plica`) terminó por espera agotada.

## Archivos

- En `src/licigt/consulta`: `orquestador.py`, `validacion.py`, `config.py`, `llm.py` y `generacion.py` (solo si hace falta), con sus pruebas.
- En `web/src`: solo el texto del aviso de afirmaciones descartadas en `Resultado.tsx` y `estado.ts`, con su prueba.
- **No toques** `enrutador.py` ni `experimento.py`: otro agente trabaja ahí.

## Cambios (prueba en rojo primero)

### 1. Cobertura veraz

- `coverage_status` sale solo de las alertas de cobertura del inventario (`cobertura_incompleta`).
- El descarte de afirmaciones se señala solo con el aviso `afirmaciones_descartadas`.
- La web muestra para ese aviso un texto propio: "Se omitieron afirmaciones que no pasaron la validación de citas", sin hablar de páginas.
- **Pruebas:**
  - publicación parcial en un evento sin páginas faltantes da `coverage_status='sin_faltantes_detectados'` con el aviso;
  - en el 222 sigue saliendo `parcial` por la página 4.

### 2. Presupuesto de tiempo por solicitud

- **Mide primero**, con el JSON del reporte (`data/plataforma/reporte/20261118T203231Z.json` y su detalle) y los registros de `llama-server` (`docker logs licigt-llm`), la distribución de tokens de salida de las respuestas válidas y el tiempo por llamada. Reporta p50, p95 y p99.
- **Con esa medición:**
  - `max_tokens` queda en un valor que cubra el p99 de las salidas válidas y quepa en `tiempo_espera`, o `tiempo_espera` se ajusta a ese tope. Justifica los números.
  - **Presupuesto total por solicitud** (`LICIGT_PRESUPUESTO_SEGUNDOS`, por defecto 15): antes de regenerar, si el tiempo ya gastado más el de una generación estimada supera el presupuesto, no se regenera. Se publica lo válido (publicación parcial) o se abstiene, como hoy tras una regeneración fallida.
- **Lo que no cambia:** el validador, la regla de una regeneración como máximo y la abstención segura.
- **Pruebas con dobles de reloj:** sin presupuesto, regenera; con el presupuesto agotado, no regenera y termina en parcial o en abstención.

### 3. Medición

- Corre `make reporte BANCO_COMUN=src/licigt/plataforma/casos_comun.json`. Tarda unos 40 min.
- Reporta antes y después:
  - P50 y P95 total, por herramienta y solo con herramienta;
  - las abstenciones indebidas;
  - los casos que cumplen en los dos bancos.
- **El banco común es de prueba:** no ajustes nada mirando sus casos. Los parámetros salen de la medición del punto 2, no del banco.

## Criterios

- `make test-consulta`, `pnpm --dir web test` y `pnpm --dir web build` en verde.
- El reporte nuevo generado.

## Reglas

- Sin `keys/`.
- No uses `make … PYTHON=…`.
- Usa pnpm.
