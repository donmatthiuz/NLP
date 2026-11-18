# Encargo J2: comparar la variante LLM del enrutador

Rama `proyecto`. No commitees.

## Por qué (revisión retrospectiva; decisión del usuario del 18 de noviembre)

- **Compromiso sin cumplir:**
  - `Anteproyecto.md:342` y `DESIGN.md:24` comprometen comparar reglas, LLM con salida estructurada y JEV;
  - solo se compararon reglas y JEV (`docs/consulta/Experimento_JEV.md`);
  - `EnrutadorLlm` existe sin cliente.
- **El usuario decidió medirla** con el LLM local (`llama-server` en Docker, sin costo de API).

## Lee primero

- `src/licigt/consulta/enrutador.py` (`EnrutadorLlm` y la interfaz común), `experimento.py` (corrida, `comparar` y veredicto), `llm.py` (cliente compatible con OpenAI), `config.py` y sus pruebas;
- `docs/consulta/Experimento_JEV.md` (protocolo, conjuntos y regla de adopción);
- `docs/consulta/Guia_de_etiquetado.md`.

## Archivos

- `enrutador.py`, `experimento.py` y `llm.py` (solo si hace falta reutilizar el cliente), con sus pruebas.
- `docs/consulta/Experimento_JEV.md`: una sección nueva.
- **No toques** `orquestador.py`, `validacion.py` ni `config.py` (salvo una variable nueva para el enrutador LLM): otro agente trabaja ahí.

## Cambios (prueba en rojo primero)

- **Cliente:** `EnrutadorLlm` usa el cliente local con salida estructurada (esquema JSON con `accion`, `motivo` y `herramienta`), con temperatura 0, la misma semilla y un prompt corto que describe las clases con las definiciones de la guía de etiquetado.
  - Un JSON inválido o una espera agotada degrada a reglas, como JEV (`degradado`).
- **Corrida:** `experimento correr <conjunto> --variante llm` no necesita JEV ni confirmación, porque no sale de la máquina.
  - Graba la decisión y la latencia por caso, con el mismo formato que la corrida de JEV, en `data/consulta/experimentos/`.
- **`comparar`:** acepta la variante `llm`.
  - Reporta la exactitud y los críticos de reglas, JEV (de la corrida de prueba existente) y LLM.
  - Reporta McNemar de LLM frente a reglas.
  - Reporta el P95 del enrutador LLM.
- **Protocolo:** el conjunto de prueba ya se usó para reglas contra JEV. Esta comparación se hace con la misma regla de adopción, sin cambiarla, y una sola corrida de prueba. Primero corre el conjunto de desarrollo.
- **Pruebas con dobles:** JSON válido, JSON inválido que degrada y espera agotada que degrada.

## Medición

- Corre desarrollo y luego prueba (una sola vez) con el LLM local.
- Escribe en `Experimento_JEV.md` la sección "Variante LLM": cifras, McNemar, latencia y el veredicto con la regla.

## Reglas

- Sin `keys/`.
- No llames a JEV.
- No uses `make … PYTHON=…`. Para correr, agrega o usa un objetivo `make` (por ejemplo `make experimento-llm CONJUNTO=…`).
