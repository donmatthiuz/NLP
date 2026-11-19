#!/usr/bin/env bash
# Genera el informe con herramientas locales, sin servicios ni credenciales.
# Uso: bash scripts/exportar_informe.sh
# Variables: CHROME_BIN (por defecto google-chrome).
set -euo pipefail

CHROME="${CHROME_BIN:-google-chrome}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
INFORME_DIR="${ROOT}/docs/informe"
OUTPUT="${INFORME_DIR}/Documento_tecnico.pdf"

for herramienta in pandoc "${CHROME}" pdfinfo; do
    if ! command -v "${herramienta}" >/dev/null 2>&1; then
        echo "Error: no se encontró ${herramienta}." >&2
        exit 1
    fi
done

TEMPORAL="$(mktemp -d)"
trap 'rm -rf "${TEMPORAL}"' EXIT

# La base conserva las referencias al repositorio al convertir desde un temporal.
printf '<base href="file://%s/">\n' "${INFORME_DIR}" > "${TEMPORAL}/base.html"
cd "${INFORME_DIR}"
pandoc Documento_tecnico.md --from=markdown --to=html5 --standalone \
    --self-contained --fail-if-warnings --metadata lang=es \
    --metadata title="LiciGT: documento técnico" \
    --css=pdf/estilo.css --include-in-header="${TEMPORAL}/base.html" \
    --output="${TEMPORAL}/informe.html"

if ! "${CHROME}" --headless=new --disable-gpu --disable-dev-shm-usage \
    --disable-background-networking --no-pdf-header-footer \
    --user-data-dir="${TEMPORAL}/perfil" \
    --print-to-pdf="${TEMPORAL}/informe.pdf" "file://${TEMPORAL}/informe.html" \
    >"${TEMPORAL}/chrome.log" 2>&1; then
    cat "${TEMPORAL}/chrome.log" >&2
    exit 1
fi

paginas="$(pdfinfo "${TEMPORAL}/informe.pdf" | awk '/^Pages:/ { print $2 }')"
if [[ ! "${paginas}" =~ ^[0-9]+$ ]] || (( paginas < 10 || paginas > 15 )); then
    echo "Error: el informe tiene ${paginas:-desconocidas} páginas; el curso exige entre 10 y 15." >&2
    exit 1
fi

# Solo reemplaza la entrega después de verificar la conversión y su extensión.
cp "${TEMPORAL}/informe.pdf" "${OUTPUT}"
echo "Informe generado: ${OUTPUT} (${paginas} páginas)."
