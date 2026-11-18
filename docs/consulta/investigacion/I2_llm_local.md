# Investigación I2: LLM generador local

**Fecha:** 16 de noviembre de 2026. **Estado:** propuesta para visto bueno. No implementa nada; resuelve el pendiente "LLM generador local" de [`docs/Pendientes.md`](../../Pendientes.md) (línea 19).

Documentación oficial de las herramientas evaluadas:

- llama.cpp, servidor `llama-server`: https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md
- Ollama: https://docs.ollama.com (salida estructurada: https://docs.ollama.com/capabilities/structured-outputs)
- vLLM: https://docs.vllm.ai
- Hugging Face Transformers: https://huggingface.co/docs/transformers
- Descargas de Hugging Face Hub (`hf download`, caché en `HF_HOME`): https://huggingface.co/docs/huggingface_hub/guides/download
- Sentence Transformers (embeddings y reranker del rol 2): https://sbert.net

Nota de método: Context7 devolvió "Invalid API key" en esta sesión (no se abrió con `make claude`), así que la documentación de Ollama y llama.cpp se consultó directamente en las páginas oficiales enlazadas. Las cifras de los modelos salen de sus model cards y de la API de Hugging Face consultadas hoy. Las cifras marcadas como "estimado" son cálculos propios: el banco debe confirmarlas.

## Resumen

- La GPU no tiene 12 GB libres: el escritorio de Windows ya ocupa 2724 MiB de 12227 MiB (medido hoy con `nvidia-smi` desde WSL2; el i7-14700KF no tiene gráficos integrados, así que el monitor siempre usa la RTX 5070). Quedan unos 9,3 GiB.
- Con el rol 2 en fp32 (como está hoy) más cualquier LLM de 8-9B no cabe. Cabe si el reranker pasa a fp16 en GPU y el embedding de la pregunta se calcula en CPU. Mover el reranker a CPU no se recomienda: se estima que tardaría varios segundos y pondría en riesgo el P95 de 15 s.
- Principal: `Qwen3.5-9B` en modo sin razonamiento, GGUF `Q4_K_M`, servido con `llama-server` (llama.cpp, binario oficial con CUDA 12.8). Respaldo: `Qwen3-8B` `Q4_K_M` del repositorio GGUF oficial de Qwen. Ollama queda como servidor alternativo con la misma API compatible con OpenAI.
- Lo obligatorio por el curso es documentar el modelo y sus parámetros, validar la salida con un esquema y medir latencia, tokens y costo. Que el LLM sea local es una decisión del equipo, no un requisito del curso.

## Qué exige el curso y qué es decisión del equipo

Mínimo obligatorio:

- Generación fundamentada: solo el contexto recuperado, declarar falta de evidencia y conservar citas (PDF del curso, p. 4, sección 5.5).
- Validación y verificación de las salidas del modelo (PDF, p. 5, sección 5.8).
- Salida validada con Pydantic o JSON Schema con `answer`, `sources`, `abstained`, `tool_used` y `needs_human_review` (PDF, p. 8, sección 11).
- Reportar latencia media y P95, tokens, invocaciones al motor de inferencia y costo estimado (PDF, p. 7, fila "Operación").
- Dependencias, parametrización sin credenciales y scripts de benchmark reproducibles (PDF, p. 8, sección 12), y citar formalmente modelos y librerías (PDF, p. 10, sección 15).
- Lo que comprometió el anteproyecto: "El modelo generativo se seleccionará y documentará antes de la evaluación, registrando proveedor, versión y parámetros" (`docs/anteproyecto/Anteproyecto.md:299`), reproducibilidad con versiones de modelos (`Anteproyecto.md:221`) y P95 de hasta 15 s con documentos indexados (`Anteproyecto.md:217`, `:397`).

Decisión del equipo, no exigida por el curso:

- LLM local: el PDF no exige local ni nube. Las notas del curso proponen "Ollama local o API externa" (`anotaciones/semana15.1.md:591`) y Ollama como LLM local (`semana15.1.md:427`, `:431`). LiciGT lo fijó local (`DESIGN.md:38`), y la pregunta al asesor sobre un LLM externo sigue abierta (`docs/Pendientes.md:27`).
- Variante `llm` del enrutador: la comparación reglas, LLM y JEV es una decisión de diseño (`DESIGN.md:24`), y el cliente ya existe como interfaz sin implementar (`src/licigt/consulta/enrutador.py:37-39` y `:96-115`).

El deck del curso no nombra modelos, Ollama, vLLM ni cuantización. Sí pide registrar el "modelo generativo" junto con documentos, chunking, embeddings, índice, reranker, prompt y fecha (`NLP (2).pptx`, diapositiva 263), propone pasar al LLM el top-5 tras el reranker (diapositiva 203) y pide analizar el costo de latencia, contexto y llamadas a modelos (diapositiva 241). Las notas de la semana 10.1 insisten en elegir por la ficha del modelo, incluida su licencia (`semana10.1.md:51`, `:303`), y en atender memoria, latencia y versionado en producción (`semana10.1.md:89`).

## 1. Presupuesto de VRAM

### Qué carga hoy el rol 2

- `BAAI/bge-m3` con `SentenceTransformer(nombre)` sin `device` ni `dtype` (`src/licigt/recuperacion/indice.py:29-32`), y `BAAI/bge-reranker-v2-m3` con `CrossEncoder(MODELO_RERANKER)` (`src/licigt/recuperacion/busqueda.py:32-35`). Ambos se cargan en fp32 y en la GPU si está disponible.
- La línea base usa `paraphrase-multilingual-MiniLM-L12-v2` (117,65 M de parámetros, API de Hugging Face).
- El reranker recibe 20 candidatos y devuelve 5 (`busqueda.py:10`). Cada fragmento tiene hasta 600 palabras, unos 800 tokens según la ingesta (`src/licigt/ingesta/pipeline.py:198-199`).
- El tokenizer del reranker declara `model_max_length` de 8192, así que `CrossEncoder` no trunca a 512 salvo que se le indique (tokenizer_config de `bge-reranker-v2-m3`).

Pesos del rol 2 (parámetros por bytes por parámetro):

| Modelo | Parámetros | fp32 | fp16 | Fuente |
|---|---|---|---|---|
| `BAAI/bge-m3` | 568 M (XLM-RoBERTa large) | 2,27 GB (2,11 GiB) | 1,14 GB (1,06 GiB) | `pytorch_model.bin` de 2,27 GB en el repositorio |
| `BAAI/bge-reranker-v2-m3` | 567.755.777 | 2,27 GB (2,11 GiB) | 1,14 GB (1,06 GiB) | API de Hugging Face, `safetensors.parameters` |
| MiniLM-L12-v2 (línea base) | 117.653.760 | 0,47 GB | 0,24 GB | API de Hugging Face |

Además de los pesos (estimado): contexto CUDA de PyTorch de 0,3 a 0,5 GiB por proceso y activaciones del reranker para 20 pares de unos 900 tokens, entre 0,2 y 1 GiB según dtype e implementación de atención. BAAI recomienda `use_fp16=True` en ambos modelos: "speeds up computation with a slight performance degradation" (model cards de `bge-m3` y `bge-reranker-v2-m3`).

### Qué necesita el LLM con unos 12k tokens de contexto

Se reservan 16.384 tokens: hasta 10k de evidencia, instrucciones y pregunta, más hasta 1k de salida. La caché KV se calculó con el `config.json` de cada modelo, en f16:

| Modelo | Archivo `Q4_K_M` | Caché KV a 16k | Comentario |
|---|---|---|---|
| Qwen3.5-9B | 5,29 GiB | 0,5 GiB, más unos 0,05 GiB de estado recurrente | Solo 8 de 32 capas usan atención completa (4 cabezas KV de dim. 256); las otras 24 son Gated DeltaNet con estado fijo |
| Qwen3-8B | 4,68 GiB | 2,25 GiB (1,2 GiB con `q8_0`) | 36 capas, 8 cabezas KV de dim. 128 |
| Gemma 4 12B | 6,63 GiB | unos 0,6 GiB | 40 capas con ventana deslizante de 1024 y 8 capas globales con K=V |
| Gemma 4 E4B | 4,64 GiB | pequeña (ventana deslizante) | Alternativa ligera |

Se suman unos 0,5 a 0,9 GiB de búferes de cómputo de llama.cpp y unos 0,3 GiB de contexto CUDA (estimado; `llama-server` los imprime al cargar). Total del LLM: unos 6,8 GiB para Qwen3.5-9B, 6,8 GiB para Qwen3-8B con KV `q8_0` (7,8 GiB en f16) y 8,2 GiB para Gemma 4 12B.

### Escenarios (9,3 GiB libres tras el escritorio)

| Escenario | Rol 2 en GPU | LLM | Total | ¿Cabe? |
|---|---|---|---|---|
| A. Como hoy: todo el rol 2 en fp32 | unos 5,9 GiB | Qwen3.5-9B, 6,8 | 12,7 | No |
| B. Todo el rol 2 en fp16 | unos 3,1 GiB | Qwen3.5-9B, 6,8 | 9,9 | No, por unos 0,6 GiB |
| C. Reranker en fp16 en GPU; embedding de la pregunta en CPU | unos 1,9 GiB | Qwen3.5-9B, 6,8 | 8,7 | Sí, con unos 0,6 GiB de margen |
| D. Igual que C | unos 1,9 GiB | Qwen3-8B con KV `q8_0`, 6,8 | 8,7 | Sí, mismo margen |
| E. Igual que C | unos 1,9 GiB | Gemma 4 12B, 8,2 | 10,1 | No |
| F. Todo el rol 2 en CPU | 0 | Qwen3.5-9B, 6,8 | 6,8 | Sí, pero el reranker se vuelve lento |

Respuesta a la pregunta: no caben simultáneos tal como está el código. Lo recomendado es el escenario C, no mover el reranker a CPU:

- El embedding de la pregunta son unos 20 tokens: en CPU tarda decenas de milisegundos y libera más de 1 GiB.
- El reranker en CPU procesa 20 pares de unos 900 tokens: unos 18k tokens por las 24 capas de XLM-R large, cerca de 11 TFLOP. En un i7-14700KF con AVX2 se estiman entre 7 y 20 s. Eso solo ya rompe el P95 de 15 s. Hay que medirlo antes de descartarlo del todo.
- La importación masiva (`make importar`, lotes de 32 en `indice.py:66`) se corre con el servidor del LLM apagado. Es un paso fuera de línea.
- El margen de 0,6 GiB depende de lo que tenga abierto Windows (navegadores con aceleración por hardware usan VRAM). Si falta, se baja el contexto a 12k o se usa KV `q8_0` en el LLM.

## 2. Shortlist

Se excluyeron los siguientes modelos:

- Qwen4: no hay pesos abiertos a la fecha. Qwen4-Max está en vista previa desde el 11 de noviembre de 2026; Alibaba promete Qwen4-27B abierto, que no cabría en 12 GB.
- Ministral 3 de 8B y 14B (2512, Apache 2.0): tasa de alucinación de 21,7 % y 19,4 % en el leaderboard HHEM de Vectara, la peor de los candidatos.
- Phi-4 (14B, MIT, diciembre de 2024): `Q4_K_M` de unos 9 GB, no cabe junto al rol 2, y está centrado en inglés.
- Llama 3.1 8B: es de 2024 y no hay modelos Llama densos y pequeños más recientes.

| | Qwen3.5-9B (principal) | Qwen3-8B (respaldo) | Gemma 4 12B (solo si se libera GPU) |
|---|---|---|---|
| Repositorio de pesos | `Qwen/Qwen3.5-9B` | `Qwen/Qwen3-8B` | `google/gemma-4-12B-it` |
| GGUF | `unsloth/Qwen3.5-9B-GGUF` (Qwen no publica GGUF oficial de 3.5) | `Qwen/Qwen3-8B-GGUF` (oficial) | `unsloth/gemma-4-12B-it-GGUF` |
| Parámetros | 9B, híbrido Gated DeltaNet más atención | 8,2B, denso | 11,95B, denso, multimodal |
| Cuantización propuesta | `Q4_K_M` (5,68 GB); `Q5_K_M` 6,58 GB si sobra margen | `Q4_K_M` (5,03 GB) | `Q4_K_M` (7,12 GB) |
| VRAM estimada a 16k | unos 6,8 GiB | unos 6,8 GiB (KV `q8_0`) o 7,8 GiB | unos 8,2 GiB |
| Licencia | Apache 2.0 | Apache 2.0 | Apache 2.0 (Gemma 4 dejó los términos propios de Gemma) |
| Español | 201 idiomas; MMMLU 81,2; MMLU-ProX 76,3; MAXIFE 83,4 | más de 100 idiomas; sin cifras multilingües en la card | más de 140 idiomas en preentrenamiento y 35 listos para usar; MMMLU 83,4 |
| Seguimiento de instrucciones | IFEval 91,5; IFBench 64,5 | sin cifra en la card | sin IFEval en la card |
| Fidelidad (HHEM de Vectara, resumen en inglés) | 9B sin medir; la familia 3.5 está entre 10,5 % y 12,1 % | 4,8 % de alucinación | 12B sin medir; 26B-A4B 5,2 % y 31B 7,4 % |
| Salida estructurada | por gramática del servidor; en 2026 hubo fallos de JSON con razonamiento activo, corregidos en Ollama 0.31.2 | por gramática del servidor; modelo maduro | por gramática del servidor |
| Contexto | 262.144 nativo | 32.768 nativo (131.072 con YaRN, no recomendado bajo 32k) | 256K |
| Razonamiento | activo por defecto; se apaga con `enable_thinking: false` | activo por defecto; se apaga con `enable_thinking: false` o `/no_think` | apagado por defecto |
| Publicación | 27 de febrero a 2 de marzo de 2026 | 27 de abril de 2025 | creado el 23 de mayo de 2026; artículo de julio de 2026 |
| Revisión del GGUF | `3885219b6810b007914f3a7950a8d1b469d598a5` | `7c41481f57cb95916b40956ab2f0b139b296d974` | `fc034cfff751157913579611efad8462ac1be606` |

Notas:

- Las cifras de cada card son autodeclaradas. Las de Qwen3.5-9B se comparan contra modelos "Thinking", así que probablemente se midieron con razonamiento activo; LiciGT lo usará sin razonamiento.
- El HHEM de Vectara mide fidelidad al resumir en inglés (README actualizado al 22 de octubre de 2026), no RAG en español. Sirve como señal, no como resultado de LiciGT. Es el único dato público que favorece a Qwen3-8B, y por eso es el respaldo.
- Gemma 4 E4B (4,98 GB en `Q4_K_M`, MMMLU 76,6) es la opción si el margen de VRAM resulta menor que lo estimado.

## 3. Servidor

| Criterio | `llama-server` (llama.cpp) | Ollama | vLLM | Transformers en proceso |
|---|---|---|---|---|
| RTX 50 (sm_120) en WSL2 | Binarios oficiales "Ubuntu x64 (CUDA 12.8)" y "(CUDA 13.5)" en la versión b12441 del 16 de noviembre de 2026; no hay que compilar | Soporte oficial de capacidad 12.0, RTX 5070 incluida, con driver 550 o superior; la versión 0.32.14 ya está instalada en la máquina | Funciona en WSL2 con Blackwell, pero con PyTorch nightly o cu130 y ajustes no documentados (FlashAttention sin sm_120, AWQ solo con Marlin, según reportes del foro de vLLM) | Requiere PyTorch cu128; un 9B en bf16 ocupa unos 18 GB, así que habría que cuantizar con bitsandbytes |
| JSON Schema | `response_format` con `json_schema` en `/v1/chat/completions`, `json_schema` y `grammar` en `/completion`, y `--json-schema-file` | `format` con un JSON Schema (por ejemplo `model_json_schema()` de Pydantic) y `response_format` en la API OpenAI | Decodificación guiada | Requiere una librería extra |
| Reproducibilidad | `seed` (por defecto aleatorio) y `temperature` 0; advierte que los logits pueden variar con el tamaño de lote y con `cache_prompt` | `seed` ("same text for the same prompt") y `temperature` 0; la documentación recomienda temperatura 0 para salida estructurada | Bueno, pero reserva el 90 % de la VRAM por defecto | Bueno |
| Control de VRAM | Exacto: `--ctx-size`, `-ngl`, `--cache-type-k`, `-np` y `--no-mmproj` para no cargar el proyector de visión | Por variables globales (`OLLAMA_CONTEXT_LENGTH`, `OLLAMA_KV_CACHE_TYPE`); la etiqueta `qwen3.5:9b-q4_K_M` pesa 6,6 GB porque incluye visión | Choca con el rol 2 en la misma GPU | Comparte proceso con el rol 2 |
| Descarga controlada | Archivo GGUF fijado por revisión y sha256 en `models/` con `hf download`, o `-hf` con `LLAMA_CACHE` | Almacén propio de blobs; el servicio guarda en `/usr/share/ollama/.ollama/models` salvo que se defina `OLLAMA_MODELS`; las etiquetas pueden cambiar (fijar por digest) | Hugging Face | Hugging Face |
| Trampas conocidas | Fallos de 2026 con `json_schema` y razonamiento en Qwen3.5 (el esquema se aplicaba al bloque de razonamiento); se evitan apagándolo | Contexto por defecto de 4096 tokens: trunca la evidencia si no se fija `num_ctx`, y la API OpenAI no permite fijarlo (hace falta un Modelfile) | | |
| Facilidad para el equipo | Un binario y un comando en el `Makefile` | La más simple, y es la que muestran las notas del curso | Baja | Media |

Recomendación: `llama-server` como servidor principal, por tres razones con evidencia:

- Permite fijar el modelo como un archivo GGUF con revisión y sha256 dentro de `models/` vía `HF_HOME`, igual que el resto del proyecto (`DESIGN.md:37`, `Makefile:11` y `:18`).
- Controla la VRAM con exactitud (`--no-mmproj`, `--ctx-size`, `-np 1`), y aquí sobra poco margen.
- Expone `/v1/chat/completions` con `response_format`, así que el cliente es el mismo que para Ollama.

Ollama queda como alternativa documentada para quien la prefiera (respaldo del servidor, no del modelo). Requiere Ollama 0.31.2 o superior por el arreglo de `format` con `think: false` (issue ollama/ollama#14645), un Modelfile con `PARAMETER num_ctx 16384` y `OLLAMA_MODELS` dentro del proyecto. Se descartan vLLM y Transformers en proceso: no aportan nada para un usuario a la vez y complican compartir la GPU.

## Ejecución en WSL con Ubuntu 22.04

El binario oficial de la versión b12441 exige GLIBC 2.38 y Ubuntu 22.04 trae 2.35, así que `llama-server` no arranca de forma nativa. No hay imagen oficial de llama.cpp con esa etiqueta, de modo que `scripts/llm.sh` corre el mismo binario dentro de un contenedor (`docker/llm/Dockerfile`, base `nvidia/cuda:12.8.1-runtime-ubuntu24.04` fijada por digest, con `libgomp1` y `curl`).

- El binario y `models/` se montan de solo lectura, sin copiarlos a la imagen, para conservar el sha256 verificado. Los argumentos de `llama-server` son los mismos que en modo nativo.
- `LICIGT_LLM_MODO=auto|nativo|docker` elige el modo; `auto` usa el nativo si `llama-server --version` corre y si no, docker.
- En modo docker `make llm-servidor` regresa en cuanto arranca el contenedor `licigt-llm` (puerto publicado solo en 127.0.0.1); `make llm-detener` lo elimina y `make llm-estado` informa modo y contenedor.
- Medido el 17 de noviembre: con el modelo cargado y contexto de 16384, la GPU queda en 8309 MiB usados de 12227; antes de arrancar estaba entre 2531 y 2756 MiB (escritorio de Windows), así que el LLM ocupa unos 5,6 GiB.

## 4. Recomendación final y cómo fijarla

Modelo principal: Qwen3.5-9B en modo sin razonamiento.

- Repositorio: `unsloth/Qwen3.5-9B-GGUF`, revisión `3885219b6810b007914f3a7950a8d1b469d598a5`.
- Archivo: `Qwen3.5-9B-Q4_K_M.gguf`, 5.680.522.464 bytes, sha256 `03b74727a860a56338e042c4420bb3f04b2fec5734175f4cb9fa853daf52b7e8`.
- Pesos de origen: `Qwen/Qwen3.5-9B`, revisión `c202236235762e1c871ad0ccb60c8ee5ba337b9a`, Apache 2.0.
- Sin `mmproj`: LiciGT solo usa texto.

Modelo de respaldo: Qwen3-8B en modo sin razonamiento.

- Repositorio: `Qwen/Qwen3-8B-GGUF`, revisión `7c41481f57cb95916b40956ab2f0b139b296d974`.
- Archivo: `Qwen3-8B-Q4_K_M.gguf`, 5.027.783.488 bytes, sha256 `d98cdcbd03e17ce47681435b5150e34c1417f50b5c0019dd560e4882c5745785`.
- Con caché KV `q8_0` si la VRAM aprieta.

Servidor: llama.cpp `b12441`, binario "Ubuntu x64 (CUDA 12.8)" de https://github.com/ggml-org/llama.cpp/releases. Se anota el sha256 del archivo descargado. El driver 621.01 reporta CUDA 13.5, así que también sirve el binario de CUDA 13.5.

Parámetros fijos, iguales en el banco y en la demo:

- `temperature: 0`, `seed: 42`, `max_tokens` de unos 768.
- `chat_template_kwargs: {"enable_thinking": false}` (model card de Qwen3.5-9B, línea 992), o `--reasoning-budget 0` en el servidor.
- Servidor con `--ctx-size 16384 -np 1 --no-mmproj --flash-attn on`, tamaños de lote (`-b`, `-ub`) explícitos, solo en `127.0.0.1`.
- `cache_prompt: false` en las corridas del banco, porque el README advierte que la caché de prompt puede cambiar los logits.

Por qué el principal es Qwen3.5-9B:

- Es el modelo pequeño más reciente con Apache 2.0.
- Tiene las mejores cifras publicadas de seguimiento de instrucciones y multilingüe entre los que caben.
- Su caché KV a 16k es unas cuatro veces menor que la de Qwen3-8B. Eso deja margen al reranker y permite atender a más de un usuario después.

Riesgos y mitigaciones:

- La familia 3.5 tiene peor HHEM que Qwen3: el banco decide entre los dos.
- La arquitectura es nueva y hubo fallos al combinar JSON con razonamiento: se apaga el razonamiento y se mide la tasa de JSON válido.
- Qwen desaconseja la decodificación voraz en modo con razonamiento ("DO NOT use greedy decoding", card de Qwen3-8B, línea 129) y recomienda temperatura 0,7 sin razonamiento (línea 148). Usar temperatura 0 es una desviación deliberada por reproducibilidad; se limita con `max_tokens` y se mide si aparecen repeticiones.

Cómo se fija sin tocar código (lo implementa otro agente con encargo):

```bash
HF_HOME=models hf download unsloth/Qwen3.5-9B-GGUF Qwen3.5-9B-Q4_K_M.gguf \
  --revision 3885219b6810b007914f3a7950a8d1b469d598a5
sha256sum models/hub/models--unsloth--Qwen3.5-9B-GGUF/snapshots/3885219b*/Qwen3.5-9B-Q4_K_M.gguf
```

Detalle para `make models-status` (`Makefile:74-77`): el objetivo lee `refs/main`, y al descargar con `--revision <commit>` Hugging Face no escribe ese archivo. Saldría `sin-revision`. Se corrige listando `snapshots/` o descargando `main` y verificando que el snapshot coincida con la revisión fijada.

En `.env.example` irían, sin secretos: `LICIGT_LLM_BASE_URL=http://127.0.0.1:8080/v1`, `LICIGT_LLM_MODELO`, `LICIGT_LLM_ARCHIVO` y `LICIGT_LLM_SHA256`.

Diseño de la salida (mejora barata con mucho efecto):

- El LLM no genera todo `RespuestaEstructurada` (`src/licigt/consulta/esquemas.py:40-53`). Genera un esquema reducido: `answer`, citas con `chunk_id` y un fragmento corto de texto, `abstained` y `needs_human_review`.
- El código completa lo demás de forma determinista: `doc_id`, página, versión, `tool_used`, `evento_id`, `coverage_status` y `warnings` salen de los metadatos del fragmento y de las alertas del rol 2.
- Así la salida es más corta, y por tanto más rápida, y el modelo no puede inventar una página ni una versión.
- Como mejora adicional, el esquema de cada solicitud puede declarar `chunk_id` como `enum` de los fragmentos recuperados, y la gramática impide citar uno inexistente. El validador determinista sigue siendo obligatorio (PDF, p. 5) y comprueba el texto citado.
- La variante `llm` del enrutador usaría el mismo servidor y modelo con su propio esquema (`JuiciosLlm`, `enrutador.py:42`), sin un segundo modelo en la VRAM.

## 5. Qué medir en el banco para confirmar la elección

Mínimo, sin sobreingeniería:

- Un único script que corra los casos del banco (al menos 20, `Anteproyecto.md:114`) con la evidencia recuperada congelada: el mismo JSON de fragmentos para ambos modelos, para aislar al LLM. Se corren el principal y el respaldo con los mismos parámetros.
- Tasa de JSON válido contra el esquema Pydantic en el primer intento y tras la única regeneración. Con gramática debería acercarse al 100 %; si no, señala un fallo del servidor (razonamiento o plantilla).
- Citas válidas: porcentaje de `chunk_id` que pertenecen a los recuperados y cuyo texto citado aparece en el fragmento, con el mismo validador de F4. Meta del anteproyecto: 95 % o más (`Anteproyecto.md:395`).
- Abstención: 2 de 2 en los casos sin evidencia, y abstenciones indebidas en los que sí tienen evidencia (`Anteproyecto.md:396`).
- Latencia por llamada al LLM con los `timings` que devuelve `llama-server` (`prompt_ms`, `predicted_ms` y tokens de entrada y salida): P50 y P95 sobre 3 repeticiones por caso. Por separado, latencia de extremo a extremo. Referencia externa: en una RTX 5070, Qwen3-8B `Q4_K` procesa unos 3488 tokens/s de prompt y genera 85,8 tokens/s a 4k, y 1601 y 59,1 tokens/s a 16k (hardware-corner.net). Con unos 8k de entrada y 400 de salida, eso da unos 9 a 10 s solo en el LLM (estimado). Una regeneración dejaría el P95 por encima de 15 s, de ahí la salida corta.
- VRAM pico con `nvidia-smi --query-gpu=memory.used` durante la corrida, restando el escritorio medido antes de empezar.
- Determinismo: repetir cada caso y reportar el porcentaje de salidas idénticas con temperatura 0.
- Tokens y costo: tokens de entrada y salida por consulta; el costo de API es cero y se reporta el tiempo de GPU (fila "Operación", PDF p. 7; `Anteproyecto.md:398`).

Regla de decisión propuesta: se queda Qwen3.5-9B salvo que no quepa en VRAM, supere 15 s de P95 en la latencia de extremo a extremo, o que Qwen3-8B lo supere por 5 puntos o más en citas válidas o abstención correcta.

Mejoras opcionales: comparar `Q4_K_M` contra `Q5_K_M`; evaluar Gemma 4 12B en una máquina con más VRAM; medir el P95 con 5 usuarios concurrentes (`Anteproyecto.md:430`). Como referencia sobre la pérdida por cuantización existe una evaluación unificada de los niveles de llama.cpp (arXiv 2601.14277); aquí se mide en la tarea real en lugar de suponer.

## 6. Avisos para el rol 2 y el rol 4

Para el rol 2, en [`docs/recuperacion/Avisos_del_rol_3.md`](../../recuperacion/Avisos_del_rol_3.md) (completa el aviso de GPU de la línea 89):

- Hacer configurables el dispositivo y el dtype: reranker en GPU en fp16 y embedding de la pregunta en CPU durante la consulta. Por ejemplo `SentenceTransformer(..., device=...)` y `CrossEncoder(..., model_kwargs={"torch_dtype": torch.float16})`, por variables de entorno. Opción por defecto si no responde: el rol 3 arranca el LLM con `--ctx-size 12288` y KV `q8_0` y reporta si hay falta de memoria.
- Fijar `max_length` del reranker (por ejemplo 1024). Hoy hereda 8192 del tokenizer. Opción por defecto: se deja como está; los fragmentos ya miden menos de unos 900 tokens.
- Volver a medir Hit@5 y MRR@5 en fp16 con sus 27 casos (`docs/recuperacion/Recuperacion.md:29`), porque BAAI reconoce una ligera degradación. Opción por defecto: se acepta fp16 si la diferencia es menor de 2 puntos.
- Medir la VRAM real con `torch.cuda.max_memory_allocated()` y anotarla en `Recuperacion.md`. Opción por defecto: se usan las estimaciones de esta investigación.
- Correr `make importar` con el servidor del LLM apagado. Opción por defecto: el objetivo del `Makefile` del LLM lo advierte.

Para el rol 4, en [`docs/plataforma/Avisos_del_rol_3.md`](../../plataforma/Avisos_del_rol_3.md) (completa la línea 19):

- Registrar en los resultados del banco: repositorio, revisión, archivo, sha256 y cuantización del modelo; servidor y versión; `temperature`, `seed`, `ctx` y `max_tokens`; GPU y driver; tokens y tiempos por etapa. Es lo que pide la diapositiva 263 y `Anteproyecto.md:299`. La auditoría ya lleva `latencia_ms` (línea 8) y no debe incluir el prompt ni el texto de PDF. `llama-server` no debe correr con `-v` ni `--log-file` en la demo. Opción por defecto: el rol 3 agrega estos campos al resultado del banco, no a la auditoría.
- El LLM es un proceso aparte en `127.0.0.1:8080` con API compatible con OpenAI, sin clave y nunca expuesto fuera de la máquina. Opción por defecto: arranca con un objetivo del `Makefile`.
- Concurrencia: con un solo slot las consultas se encolan, y el P95 con 5 usuarios será mucho mayor que con uno. Opción por defecto: se reportan las dos cifras por separado, como permite `Anteproyecto.md:402`.

## Decisiones propuestas

| Decisión | Recomendación | Respaldo | Obligatoria o mejora |
|---|---|---|---|
| Documentar el modelo generativo con versión y parámetros antes de evaluar | Qwen3.5-9B, GGUF `Q4_K_M`, revisión y sha256 de la sección 4 | Qwen3-8B, GGUF oficial `Q4_K_M` | Obligatoria (`Anteproyecto.md:299`; PDF p. 10) |
| Local o externo | Local, como ya decidió el equipo | API externa si el asesor lo pide | Decisión del equipo (`DESIGN.md:38`) |
| Servidor | `llama-server` b12441 con CUDA 12.8 | Ollama 0.31.2 o superior con Modelfile (`num_ctx`, `temperature`, `seed`) | Mejora; lo obligatorio es que sea reproducible |
| Reparto de GPU | Reranker en GPU en fp16, embedding de la pregunta en CPU y LLM de unos 6,8 GiB | Contexto de 12k y KV `q8_0`; o Gemma 4 E4B | Necesaria para que funcione |
| Salida estructurada | Esquema reducido por gramática (`response_format`) más el validador determinista | Solo el validador con una regeneración | El validador es obligatorio (PDF pp. 5 y 8); la gramática es mejora |
| `chunk_id` como `enum` en el esquema | Sí, por solicitud | Sin `enum` | Mejora |
| Razonamiento del modelo | Apagado (`enable_thinking: false`) | `--reasoning-budget 0` | Necesaria por latencia y por los fallos de JSON conocidos |
| Parámetros de muestreo | `temperature` 0, `seed` 42, `max_tokens` 768 y `cache_prompt` falso en el banco | `temperature` 0,1 si aparecen repeticiones | Obligatoria la reproducibilidad (PDF p. 8) |
| Variante `llm` del enrutador | Mismo servidor y modelo con el esquema `JuiciosLlm` | No implementarla; quedan reglas y JEV | Mejora (`DESIGN.md:24`) |
| Medición | Script único con evidencia congelada: JSON válido, citas válidas, abstención, latencia, VRAM y determinismo | | Obligatoria la latencia, P95 y tokens (PDF p. 7) |

## Preguntas para el usuario

- ¿La evaluación y la demo se harán en esta máquina, con el escritorio de Windows usando unos 2,7 GB de VRAM, o en otra? Por defecto: en esta máquina, cerrando navegadores con aceleración por hardware durante las mediciones y registrando la VRAM base.
- ¿Acepta el equipo `llama-server` como servidor principal aunque las notas del curso muestren Ollama? Por defecto: sí. El cliente usa la API compatible con OpenAI, así que cambiar a Ollama es solo configuración, y ambos quedan documentados.
- ¿Dónde se guarda el binario de llama.cpp? Por defecto: se descarga a `tools/llama.cpp/b12441/` (ignorado por Git) con el sha256 anotado; no se instala en el sistema.
- ¿Se implementa la variante `llm` del enrutador en esta entrega? Por defecto: solo después de F4, con el mismo modelo y si sobra tiempo; la comparación obligatoria del banco no la necesita.

## Fuentes

Repositorio:

- `DESIGN.md:24`, `:37` y `:38`; `docs/Pendientes.md:19`, `:25` y `:27`; `docs/consulta/Plan_rol_3.md:26`, `:75-80` y `:108`.
- `docs/recuperacion/Avisos_del_rol_3.md:80` y `:89`; `docs/plataforma/Avisos_del_rol_3.md:8` y `:19`; `docs/recuperacion/Recuperacion.md:29`.
- `docs/anteproyecto/Anteproyecto.md:114`, `:217`, `:221`, `:299`, `:395-398`, `:402` y `:430`.
- `Makefile:11`, `:18` y `:74-77`; `src/licigt/recuperacion/indice.py:29-32` y `:66`; `src/licigt/recuperacion/busqueda.py:10` y `:32-35`; `src/licigt/ingesta/pipeline.py:198-199`; `src/licigt/consulta/esquemas.py:40-53`; `src/licigt/consulta/enrutador.py:37-42` y `:96-115`.
- Medición local del 16 de noviembre de 2026: `nvidia-smi` con RTX 5070, 12227 MiB, 2724 MiB en uso por el escritorio, driver 621.01 y capacidad 12.0; Ollama 0.32.14 instalado como servicio; WSL2 con 47 GB de RAM visibles.

Curso:

- "Proyecto Final CC3103: Sistema NLP/RAG Agéntico Empresarial" (PDF): p. 1 (Transformers o modelos modernos), p. 4 (5.5), p. 5 (5.8), p. 6 (fases), p. 7 (métricas de operación), p. 8 (secciones 11 y 12) y p. 10 (sección 15).
- Notas: `anotaciones/semana15.1.md:427`, `:431` y `:591`; `anotaciones/semana10.1.md:51`, `:89` y `:303`.
- Deck `NLP (2).pptx`: diapositivas 117 (Hugging Face), 185 (laboratorio RAG local), 203 (top-k para el LLM), 241 (costo y latencia) y 263 (versionado del modelo generativo).

Modelos:

- Qwen3.5-9B: https://huggingface.co/Qwen/Qwen3.5-9B (benchmarks, líneas 123-298; muestreo, líneas 833-836; `enable_thinking`, línea 992). GGUF: https://huggingface.co/unsloth/Qwen3.5-9B-GGUF
- Qwen3-8B: https://huggingface.co/Qwen/Qwen3-8B (contexto, línea 34; voraz, línea 129; sin razonamiento, línea 148). GGUF: https://huggingface.co/Qwen/Qwen3-8B-GGUF
- Gemma 4 12B: https://huggingface.co/google/gemma-4-12B-it (tabla de benchmarks, líneas 90-112). GGUF: https://huggingface.co/unsloth/gemma-4-12B-it-GGUF. Gemma 4 E4B: https://huggingface.co/unsloth/gemma-4-E4B-it-GGUF
- Lanzamiento de Gemma 4 con Apache 2.0: https://9to5google.com/2026/04/02/google-gemma-4/
- Ministral 3 8B: https://huggingface.co/mistralai/Ministral-3-8B-Instruct-2512
- Estado de Qwen4: https://aifirstlook.com/qwen-4/ y https://techpilot.ai/qwen-4-release-date/
- BGE: https://huggingface.co/BAAI/bge-m3 y https://huggingface.co/BAAI/bge-reranker-v2-m3
- HHEM de Vectara (actualizado al 22 de octubre de 2026): https://github.com/vectara/hallucination-leaderboard

Servidores y hardware:

- llama.cpp: README del servidor (enlace al inicio), versiones en https://github.com/ggml-org/llama.cpp/releases (b12441) e issue de Qwen3.5 con razonamiento en https://github.com/ggml-org/llama.cpp/issues/20837
- Ollama: https://docs.ollama.com/gpu, https://docs.ollama.com/faq, https://docs.ollama.com/modelfile, https://docs.ollama.com/api/openai-compatibility, https://docs.ollama.com/capabilities/thinking y https://github.com/ollama/ollama/issues/14645
- vLLM en Blackwell y WSL2: https://discuss.vllm.ai/t/running-nvfp4-nemotron-model-on-win11-wsl-rtx-5080-5070-ti/2310 y https://discuss.vllm.ai/t/field-report-awq-on-rtx-5060-ti-sm-120-blackwell-awq-marlin-triton-attn-working/2463
- Guía de migración a Blackwell (CUDA 12.8): https://forums.developer.nvidia.com/t/software-migration-guide-for-nvidia-blackwell-rtx-gpus-a-guide-to-cuda-12-8-pytorch-tensorrt-and-llama-cpp/321330
- Rendimiento en RTX 5070: https://www.hardware-corner.net/gpu-llm-benchmarks/rtx-5070/
- Cuantización en llama.cpp: https://arxiv.org/abs/2601.14277

## Configuración medida para la demo (17 de noviembre)

- **LLM:** contexto de 12288 (valor por defecto desde ahora; con 16384 no caben los modelos del rol 2). Con el LLM cargado, la GPU queda en 7377 MiB, contando los 1653 MiB del escritorio.
- **Modelos del rol 2 en la misma GPU** (proceso de la API sin `CUDA_VISIBLE_DEVICES` vacío): la GPU queda en 11442 de 12227 MiB.
- **Latencias reales del 222 por la API:**
  - consulta respondible: de 6 a 7,5 s (16 s en la primera, que carga los modelos);
  - abstención: 0,8 s;
  - propuesta de lista con 41 ítems: 4 s.
- **Con la recuperación en CPU** las mismas operaciones tardaban:
  - consulta respondible: de 15 a 24 s;
  - abstención: 7 s;
  - propuesta de lista: de 67 a 70 s.
- **Riesgo:** quedan unos 800 MiB libres. Si el escritorio crece, la recuperación vuelve a CPU con `CUDA_VISIBLE_DEVICES=` en el proceso de la API.

