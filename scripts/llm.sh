#!/usr/bin/env bash
# LLM generador local (rol 3): binario de llama.cpp y modelo GGUF con versión y sha256 fijados.
#   bash scripts/llm.sh descargar | servidor | estado
set -euo pipefail
cd "$(dirname "$0")/.."

# Binario oficial de llama.cpp "Ubuntu x64 (CUDA 12.8)", versión b12441.
VERSION_LLAMACPP="b12441"
ASSET_LLAMACPP="llama-${VERSION_LLAMACPP}-bin-ubuntu-cuda-12.8-x64.tar.gz"
URL_LLAMACPP="https://github.com/ggml-org/llama.cpp/releases/download/${VERSION_LLAMACPP}/${ASSET_LLAMACPP}"
DIR_BINARIO="tools/llama.cpp/${VERSION_LLAMACPP}"
# El release no publica checksums. Anotar aquí el sha256 del tarball descargado:
# `make llm-descargar` lo imprime cuando esta constante está vacía.
SHA256_BINARIO="fa045da495821f344351e79e3d2035bf1f5de6f64e16d1b165c363842ca11a57"

# Modelo principal (I2, sección 4).
REPO_PRINCIPAL="unsloth/Qwen3.5-9B-GGUF"
ARCHIVO_PRINCIPAL="Qwen3.5-9B-Q4_K_M.gguf"
REVISION_PRINCIPAL="3885219b6810b007914f3a7950a8d1b469d598a5"
SHA256_PRINCIPAL="03b74727a860a56338e042c4420bb3f04b2fec5734175f4cb9fa853daf52b7e8"

# Modelo de respaldo (I2, sección 4); se usa con LICIGT_LLM_RESPALDO=1.
REPO_RESPALDO="Qwen/Qwen3-8B-GGUF"
ARCHIVO_RESPALDO="Qwen3-8B-Q4_K_M.gguf"
REVISION_RESPALDO="7c41481f57cb95916b40956ab2f0b139b296d974"
SHA256_RESPALDO="d98cdcbd03e17ce47681435b5150e34c1417f50b5c0019dd560e4882c5745785"

# Rutas. HF_HOME lo exporta el Makefile (o vale models/).
HF_HOME="${HF_HOME:-models}"

sha256_archivo() {
    if command -v sha256sum >/dev/null; then
        sha256sum "$1" | cut -d' ' -f1
    else
        shasum -a 256 "$1" | cut -d' ' -f1
    fi
}

# Ruta esperada del GGUF dentro de la caché de Hugging Face (revisión fijada).
modelo_archivo() {
    local repo="$1" archivo="$2" revision="$3"
    printf '%s/hub/models--%s/snapshots/%s/%s\n' "${HF_HOME}" "${repo//\//--}" "${revision}" "${archivo}"
}

# Binario llama-server extraído del tarball.
binario_llama_server() {
    find "${DIR_BINARIO}" -maxdepth 4 -type f -name llama-server 2>/dev/null | head -n1 || true
}

descargar_binario() {
    local tarball="${DIR_BINARIO}/${ASSET_LLAMACPP}"
    local binario real
    binario="$(binario_llama_server)"
    if [ -x "${binario}" ] && [ -f "${tarball}" ] && [ -n "${SHA256_BINARIO}" ] \
        && [ "$(sha256_archivo "${tarball}")" = "${SHA256_BINARIO}" ]; then
        printf 'ok\tbinario llama.cpp %s\n' "${VERSION_LLAMACPP}"
        return 0
    fi
    if [ -x "${binario}" ] && [ -f "${tarball}" ] && [ -z "${SHA256_BINARIO}" ]; then
        printf 'sha256\t%s (anótalo en SHA256_BINARIO de scripts/llm.sh)\n' "$(sha256_archivo "${tarball}")"
        return 0
    fi
    mkdir -p "${DIR_BINARIO}"
    printf 'descargando\t%s\n' "${URL_LLAMACPP}"
    curl -fL --retry 3 -o "${tarball}.tmp" "${URL_LLAMACPP}"
    real="$(sha256_archivo "${tarball}.tmp")"
    if [ -n "${SHA256_BINARIO}" ] && [ "${real}" != "${SHA256_BINARIO}" ]; then
        rm -f "${tarball}.tmp"
        printf 'sha256 del binario no coincide; se esperaba %s y se calculó %s\n' "${SHA256_BINARIO}" "${real}" >&2
        exit 1
    fi
    if [ -z "${SHA256_BINARIO}" ]; then
        printf 'sha256\t%s (anótalo en SHA256_BINARIO de scripts/llm.sh)\n' "${real}"
    fi
    mv "${tarball}.tmp" "${tarball}"
    tar -xzf "${tarball}" -C "${DIR_BINARIO}"
    printf 'ok\tbinario en %s\n' "$(binario_llama_server)"
}

descargar_modelo() {
    local repo="$1" archivo="$2" revision="$3" sha="$4"
    local destino real
    destino="$(modelo_archivo "${repo}" "${archivo}" "${revision}")"
    if [ -f "${destino}" ] && [ "$(sha256_archivo "${destino}")" = "${sha}" ]; then
        printf 'ok\t%s\n' "${destino}"
        return 0
    fi
    if [ -f "${destino}" ]; then
        rm -f "${destino}"
        printf 'sha256 no coincide\tse descarga de nuevo %s\n' "${archivo}"
    fi
    if ! command -v hf >/dev/null; then
        printf 'falta hf: instala huggingface_hub (pip install huggingface_hub)\n' >&2
        exit 1
    fi
    printf 'descargando\t%s %s (revisión %s)\n' "${repo}" "${archivo}" "${revision}"
    hf download "${repo}" "${archivo}" --revision "${revision}" >/dev/null
    [ -f "${destino}" ] || { printf 'no quedó %s tras descargar\n' "${destino}" >&2; exit 1; }
    real="$(sha256_archivo "${destino}")"
    if [ "${real}" != "${sha}" ]; then
        rm -f "${destino}"
        printf 'sha256 del modelo no coincide; se borró el archivo descargado\n' >&2
        exit 1
    fi
    printf 'ok\t%s\n' "${destino}"
}

descargar() {
    descargar_binario
    if [ "${LICIGT_LLM_RESPALDO:-0}" = 1 ]; then
        descargar_modelo "${REPO_RESPALDO}" "${ARCHIVO_RESPALDO}" "${REVISION_RESPALDO}" "${SHA256_RESPALDO}"
    else
        descargar_modelo "${REPO_PRINCIPAL}" "${ARCHIVO_PRINCIPAL}" "${REVISION_PRINCIPAL}" "${SHA256_PRINCIPAL}"
    fi
}

servidor() {
    local binario modelo
    binario="$(binario_llama_server)"
    [ -x "${binario}" ] || { printf 'falta el binario: make llm-descargar\n' >&2; exit 1; }
    if [ "${LICIGT_LLM_RESPALDO:-0}" = 1 ]; then
        modelo="$(modelo_archivo "${REPO_RESPALDO}" "${ARCHIVO_RESPALDO}" "${REVISION_RESPALDO}")"
    else
        modelo="$(modelo_archivo "${REPO_PRINCIPAL}" "${ARCHIVO_PRINCIPAL}" "${REVISION_PRINCIPAL}")"
    fi
    [ -f "${modelo}" ] || { printf 'falta el modelo: make llm-descargar\n' >&2; exit 1; }
    printf 'aviso\tcorre make importar con el servidor del LLM apagado (I2, sección 6)\n'
    exec "${binario}" \
        --model "${modelo}" \
        --host 127.0.0.1 --port "${LICIGT_LLM_PUERTO:-8080}" \
        --alias qwen3.5-9b \
        --ctx-size "${LICIGT_LLM_CTX:-16384}" \
        -np 1 \
        --no-mmproj \
        --flash-attn on \
        -b 2048 -ub 512 \
        --reasoning-budget 0
}

estado() {
    local binario tarball
    binario="$(binario_llama_server)"
    if [ -x "${binario}" ]; then
        printf 'ok\tbinario llama.cpp %s (%s)\n' "${VERSION_LLAMACPP}" "${binario}"
        tarball="${DIR_BINARIO}/${ASSET_LLAMACPP}"
        if [ -f "${tarball}" ] && [ -n "${SHA256_BINARIO}" ]; then
            if [ "$(sha256_archivo "${tarball}")" = "${SHA256_BINARIO}" ]; then
                printf 'ok\tsha256 del tarball\n'
            else
                printf 'aviso\tsha256 del tarball no coincide\n'
            fi
        elif [ -z "${SHA256_BINARIO}" ] && [ -f "${tarball}" ]; then
            printf 'aviso\tSHA256_BINARIO vacío; sha256 calculado: %s\n' "$(sha256_archivo "${tarball}")"
        fi
    else
        printf 'falta\tbinario llama.cpp %s (make llm-descargar)\n' "${VERSION_LLAMACPP}"
    fi

    local repo archivo revision sha modelo
    if [ "${LICIGT_LLM_RESPALDO:-0}" = 1 ]; then
        repo="${REPO_RESPALDO}"; archivo="${ARCHIVO_RESPALDO}"; revision="${REVISION_RESPALDO}"; sha="${SHA256_RESPALDO}"
    else
        repo="${REPO_PRINCIPAL}"; archivo="${ARCHIVO_PRINCIPAL}"; revision="${REVISION_PRINCIPAL}"; sha="${SHA256_PRINCIPAL}"
    fi
    modelo="$(modelo_archivo "${repo}" "${archivo}" "${revision}")"
    if [ -f "${modelo}" ]; then
        if [ "$(sha256_archivo "${modelo}")" = "${sha}" ]; then
            printf 'ok\tmodelo %s %s (%s)\n' "${repo}" "${archivo}" "$(sha256_archivo "${modelo}")"
        else
            printf 'aviso\tmodelo %s no coincide con su sha256\n' "${archivo}"
        fi
    else
        printf 'falta\tmodelo %s %s (make llm-descargar)\n' "${repo}" "${archivo}"
    fi

    if command -v nvidia-smi >/dev/null; then
        printf 'vram\t%s\n' "$(nvidia-smi --query-gpu=memory.free,memory.total --format=csv,noheader)"
    else
        printf 'aviso\tnvidia-smi no disponible; no se midió la VRAM\n'
    fi

    if command -v curl >/dev/null; then
        if curl -fsS "http://127.0.0.1:${LICIGT_LLM_PUERTO:-8080}/health" >/dev/null 2>&1; then
            printf 'ok\tservidor responde en http://127.0.0.1:%s/health\n' "${LICIGT_LLM_PUERTO:-8080}"
        else
            printf 'apagado\tservidor no responde en http://127.0.0.1:%s/health\n' "${LICIGT_LLM_PUERTO:-8080}"
        fi
    else
        printf 'aviso\tcurl no disponible; no se comprobó /health\n'
    fi
}

case "${1:-estado}" in
    descargar) descargar ;;
    servidor) servidor ;;
    estado) estado ;;
    *) printf 'Uso: %s descargar | servidor | estado\n' "$0" >&2; exit 2 ;;
esac
