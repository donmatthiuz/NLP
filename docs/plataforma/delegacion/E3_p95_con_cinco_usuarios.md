# Encargo E3: P95 con 5 usuarios simultáneos

Rama `proyecto`. No commitees.

## Por qué

- **Lo que pide el anteproyecto:** `Anteproyecto.md:218` y `:397` piden registrar la latencia con concurrencia (5 usuarios), y `docs/plataforma/Avisos_del_rol_3.md:49` pide el P95 con 1 y con 5.
- **Lo que hay:** el reporte solo mide en secuencia, y `README.md:70` afirma una medición que no existe. El usuario decidió medirla el 18 de noviembre.

## Archivos

- `src/licigt/plataforma/evaluacion.py` y sus pruebas.
- **No toques** `auditoria.py`, el `Makefile`, `src/licigt/consulta` ni `web/`: otros agentes trabajan ahí.
- El bloque lee `LICIGT_REPORTE_CONCURRENCIA` del entorno (por defecto 5; 0 lo salta).

## Cambios (prueba en rojo primero)

- **Bloque de concurrencia en `make reporte`:**
  - 5 hilos que llaman a `consultar()` real en paralelo, cada uno con su contexto de `empresa_demo` o `empresa_b` alternado;
  - sobre la misma lista de preguntas del bloque de latencia, repartida en rondas de 5.
- **Qué reporta:**
  - P50 y P95 con 5 usuarios, total y por herramienta;
  - las consultas que fallaron;
  - el aislamiento: ninguna fuente de la otra empresa.
  - Registra que `llama-server` atiende con un solo slot, si así lo indica su configuración (`docker inspect` o los registros, sin secretos).
- **Pruebas con dobles:** el cálculo con hilos y la comprobación del aislamiento.

## Medición

- **Coordinación:** no corras el reporte completo; otro agente (C21) lo correrá al final.
- **Corrida corta:** si puedes, corre solo el bloque con 10 a 20 preguntas con `make reporte` y una variable de entorno que limite las preguntas (`LICIGT_REPORTE_MAX_PREGUNTAS`, que agregas tú), sin editar el `Makefile`, y reporta las cifras.

## Reglas

- Sin `keys/`.
- No uses `make … PYTHON=…`.
