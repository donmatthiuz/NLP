# Entorno de ejecución para el llama-server precompilado de llama.cpp b12441.
# El binario oficial exige GLIBC 2.38 y Ubuntu 22.04 trae 2.35; esta imagen (Ubuntu 24.04) la aporta.
# No se copia el binario: scripts/llm.sh lo monta de solo lectura en /llama para conservar el sha256 verificado.
# Base fijada por digest (nvidia/cuda:12.8.1-runtime-ubuntu24.04).
FROM nvidia/cuda:12.8.1-runtime-ubuntu24.04@sha256:ebef3c171eeef0298e4eb2e4be843105edf3b8b0ac45e0b43acee358e8046867

# libgomp1: lo exigen las bibliotecas de CPU de ggml. curl: para el healthcheck.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 curl \
    && rm -rf /var/lib/apt/lists/*

ENV LD_LIBRARY_PATH=/llama
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=120s --retries=3 \
    CMD curl -sf http://127.0.0.1:8080/health || exit 1
