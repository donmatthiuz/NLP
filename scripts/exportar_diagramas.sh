#!/usr/bin/env bash
# Exporta los diagramas HTML autocontenidos a PNG con Chrome sin interfaz.
# Uso: scripts/exportar_diagramas.sh
# Variables: CHROME_BIN (por defecto google-chrome)

set -euo pipefail

CHROME="${CHROME_BIN:-google-chrome}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
SOURCE_DIR="${ROOT}/docs/arquitectura/diagramas/fuente"
OUTPUT_DIR="${ROOT}/docs/arquitectura/diagramas"
MARGEN_VENTANA=100

if ! command -v "${CHROME}" >/dev/null 2>&1; then
    echo "Error: no se encontró Chrome en '${CHROME}'." >&2
    echo "Defina CHROME_BIN con la ruta al binario de Chrome o Chromium." >&2
    exit 1
fi

mkdir -p "${OUTPUT_DIR}"

exportado=0
for html in "${SOURCE_DIR}"/*.html; do
    [ -e "${html}" ] || continue
    nombre="$(basename "${html}" .html)"
    output="${OUTPUT_DIR}/${nombre}.png"

    tamano="$(grep -oP '<meta name="diagrama-tamano" content="\K[0-9]+x[0-9]+' "${html}" || true)"
    if [ -z "${tamano}" ]; then
        echo "Aviso: ${html} no declara <meta name=\"diagrama-tamano\">; se usa 1800x1100." >&2
        tamano="1800x1100"
    fi

    ancho="${tamano%x*}"
    alto="${tamano#*x}"

    # Verificación de maquetación con ?verificar y --dump-dom
    echo "Verificando ${nombre}..."
    url="file://${html}?verificar"
    dom="$(${CHROME} --headless=new --hide-scrollbars --window-size="${ancho},${alto}" --dump-dom "${url}" 2>/dev/null)"
    resultado="$(echo "${dom}" | grep -oP '<div id="verificacion"[^>]*>\K[^<]*' | head -n1 || true)"
    if [ "${resultado}" != "OK" ]; then
        echo "Error: la verificación de ${nombre} no pasó. Problemas:" >&2
        echo "${resultado}" | sed 's/ | /\n/g; s/^/  - /' >&2
        exit 1
    fi

    echo "Exportando ${nombre} (${ancho}x${alto}) -> ${output}"
    # Chrome headless=new descuenta ~88 px de alto de la ventana al capturar: se pide más y se recorta.
    "${CHROME}" \
        --headless=new \
        --hide-scrollbars \
        --force-device-scale-factor=2 \
        --window-size="${ancho},$((alto + MARGEN_VENTANA))" \
        --screenshot="${output}" \
        "file://${html}" >/dev/null 2>&1
    if command -v convert >/dev/null 2>&1; then
        convert "${output}" -crop "$((ancho * 2))x$((alto * 2))+0+0" +repage "${output}"
    else
        echo "Aviso: sin ImageMagick (convert); el PNG conserva ${MARGEN_VENTANA} px blancos extra abajo." >&2
    fi

    exportado=$((exportado + 1))
done

if [ "${exportado}" -eq 0 ]; then
    echo "No se encontraron archivos HTML en ${SOURCE_DIR}" >&2
    exit 1
fi

echo "Exportados ${exportado} diagrama(s)."
