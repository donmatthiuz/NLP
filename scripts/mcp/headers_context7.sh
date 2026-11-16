#!/usr/bin/env bash
# headersHelper del MCP context7 en .mcp.json (Claude Code). Imprime la cabecera
# con la llave leída de su archivo en cada conexión, sin pasarla por argumentos
# ni por el entorno. Sin llave, imprime {} y Context7 usa límites anónimos.
set -euo pipefail
token_file="$(dirname "${BASH_SOURCE[0]}")/../../keys/mcp/context7.token"
if [[ ! -s "$token_file" ]]; then
    printf 'aviso\tcontext7\tsin llave: límites anónimos\n' >&2
    printf '{}\n'
    exit 0
fi
token="$(tr -d '\r\n' <"$token_file")"
printf '{"Authorization":"Bearer %s"}\n' "$token"
