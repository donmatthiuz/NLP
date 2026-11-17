# Encargo L1: LLM local reproducible y conmutador a OpenAI

Para Codex u OpenCode. Rama `rol/consulta`. Abre el agente con `make codex` o `make opencode`. El gestor auditará el resultado; no commitees.

Lee primero:

- [`AGENTS.md`](../../../AGENTS.md) y [`DESIGN.md`](../../../DESIGN.md) (stack y LLM generador);
- [I2](../investigacion/I2_llm_local.md), completo: tiene los ids, las revisiones, los sha256 y los parámetros;
- el `Makefile`, `scripts/keys.sh`, `.env.example` y `.gitignore`.

**Se lanza después de C1**, porque las dos tocan el `Makefile` y `.env.example`. En paralelo puede correr F4, que solo toca `src/licigt/consulta/`: no toques ese directorio.

## Objetivo

Que cualquiera del equipo levante el LLM generador con `make`, con la versión fijada y verificada, y que el código cambie entre el modelo local y OpenAI solo con `.env`.

**Por qué:**

- `Anteproyecto.md:299`: el modelo generativo se documenta con proveedor, versión y parámetros.
- Diapositiva 263: reproducibilidad.
- `DESIGN.md`: descargas controladas en `models/`.
- Decisión del 16 de noviembre: local por defecto, con un interruptor a OpenAI para máquinas sin GPU.

## Archivos

| Archivo | Qué |
|---|---|
| `scripts/llm.sh` | Crear: `descargar`, `servidor`, `estado` |
| `Makefile` | Objetivos `llm-descargar`, `llm-servidor` y `llm-estado`; corregir `models-status` |
| `.env.example` | Variables del LLM, sin secretos |
| `.gitignore` | Ignorar `tools/` |
| `scripts/keys.sh` | Añadir `llm/openai.key` como llave opcional de proveedor (vacía hasta que se llene con `make key-set`) |

Nada más. **No edites nada dentro de `keys/`.** El usuario añadirá la línea de `llm/openai.key` al `keys/README.md`.

## 1. `scripts/llm.sh`

Sigue el estilo de `scripts/keys.sh`: `set -euo pipefail`, mensajes cortos y en español.

### `descargar`

1. **El binario de llama.cpp:**
   - descarga la versión `b12441`, "Ubuntu x64 (CUDA 12.8)", de las releases oficiales de `ggml-org/llama.cpp` a `tools/llama.cpp/b12441/`;
   - comprueba su sha256 contra una constante del script; si la constante está vacía, imprime el sha256 calculado y pide anotarlo;
   - no instala nada en el sistema.
2. **El modelo:**
   - con `hf download` y `HF_HOME` (ya exportado por el `Makefile`), descarga `unsloth/Qwen3.5-9B-GGUF`, archivo `Qwen3.5-9B-Q4_K_M.gguf`, revisión `3885219b6810b007914f3a7950a8d1b469d598a5`;
   - verifica el sha256 `03b74727a860a56338e042c4420bb3f04b2fec5734175f4cb9fa853daf52b7e8`;
   - si no coincide, borra el archivo descargado y falla.
3. **Respaldo:** con `LICIGT_LLM_RESPALDO=1`, descarga en su lugar `Qwen/Qwen3-8B-GGUF`, `Qwen3-8B-Q4_K_M.gguf`, revisión `7c41481f…` con su sha256 `d98cdcbd03e17ce47681435b5150e34c1417f50b5c0019dd560e4882c5745785`. Toma la revisión completa de I2 o de la página del repositorio.
4. **Idempotente:** si todo ya está y verificado, solo lo informa.

### `servidor`

Arranca `llama-server` en primer plano con:

- `--host 127.0.0.1 --port ${LICIGT_LLM_PUERTO:-8080}`;
- `--alias qwen3.5-9b`;
- `--ctx-size ${LICIGT_LLM_CTX:-16384} -np 1 --no-mmproj --flash-attn on`;
- tamaños de lote explícitos;
- razonamiento apagado (`--reasoning-budget 0` o el equivalente vigente; verifícalo en el README del servidor de esa versión);
- sin `-v` ni `--log-file`.

Antes de arrancar, avisa que `make importar` debe correrse con el servidor apagado (I2, sección 6).

### `estado`

Muestra:

- si el binario y el modelo están y coinciden con su sha256;
- la VRAM libre (`nvidia-smi` si existe);
- si el servidor responde en `/health`.

Nunca imprime llaves.

## 2. `Makefile`

- `llm-descargar`, `llm-servidor` y `llm-estado` llaman al script, con `##` para la ayuda y en `.PHONY`.
- `models-status`:
  - al descargar con `--revision <commit>`, Hugging Face no escribe `refs/main`, y el objetivo mostraría `sin-revision`;
  - corrígelo para que liste el snapshot real de cada modelo de `models/hub/`, sin romper lo que ya muestra de los modelos del rol 2.

## 3. `.env.example`

Debajo del bloque de JEV, con un comentario breve:

```text
# LLM generador (rol 3): local por defecto u openai (llave en keys/llm/openai.key)
LICIGT_LLM=local
LICIGT_LLM_PUERTO=8080
LICIGT_LLM_CTX=16384
LICIGT_LLM_API_KEY_FILE=keys/llm/openai.key
```

Lo demás tiene valor por defecto en `config.py` (encargo F4).

## Verificación

**Sí ejecuta:**

- `make help`;
- `make llm-estado` (debe decir qué falta, sin fallar de forma fea);
- `bash -n scripts/llm.sh`;
- `shellcheck`, si está instalado;
- `make test-consulta`, que debe seguir en verde.

**No ejecutes `make llm-descargar`** (son unos 6 GB): lo corre el usuario. Tampoco arranques el servidor.

## Al terminar

Responde con:

- los archivos tocados;
- la salida de `make help` y de `make llm-estado`;
- cómo verificaste las opciones de `llama-server` de la versión `b12441`;
- las decisiones donde el encargo no era claro.

No amplíes el alcance.
