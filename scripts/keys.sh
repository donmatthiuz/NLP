#!/usr/bin/env bash
# Llaves locales en keys/ (ver keys/README.md). Nunca abre ni imprime una llave.
#   bash scripts/keys.sh init | status | set keys/<servicio>/<archivo>
set -euo pipefail
cd "$(dirname "$0")/.."

EXPECTED=(keys/mcp/context7.token keys/jev/api.key keys/database/dev.password)
# Secretos propios del proyecto: se generan al azar en la máquina que los usa.
# Los demás vienen de un proveedor y se pegan con make key-set.
GENERATED='^keys/database/[a-z-]+\.password$'

random_secret() {
    if command -v openssl >/dev/null; then
        openssl rand -hex 32
    else
        python3 -c 'import secrets; print(secrets.token_hex(32))'
    fi
}

init() {
    local f
    umask 077
    for f in "${EXPECTED[@]}"; do
        [ -e "$f" ] && continue
        mkdir -p "$(dirname "$f")"
        if [[ "$f" =~ $GENERATED ]]; then
            printf '%s' "$(random_secret)" >"$f"
            chmod 600 "$f"
            printf 'generada\t%s\n' "$f"
        else
            : >"$f"
            chmod 600 "$f"
            printf 'vacia\t%s\tpega ahí el valor: make key-set FILE=%s\n' "$f" "$f"
        fi
    done
}

status() {
    local f
    for f in "${EXPECTED[@]}"; do
        if [ -s "$f" ]; then
            [ "$(stat -c %a "$f")" = 600 ] && printf 'ok\t%s\n' "$f" || printf 'aviso\t%s\tpermisos deberían ser 600\n' "$f"
        elif [ -e "$f" ]; then
            printf 'vacia\t%s\n' "$f"
        else
            printf 'falta\t%s\tmake keys-init la crea\n' "$f"
        fi
    done
}

set_key() {
    local f="${1:-}" value
    if ! [[ "$f" =~ ^keys/[a-z0-9-]+/[A-Za-z0-9._-]+$ ]] || [[ "$f" == *..* ]]; then
        printf 'Uso: make key-set FILE=keys/<servicio>/<archivo>\n' >&2; exit 2
    fi
    if [ -s "$f" ] && [ "${FORCE:-0}" != 1 ]; then
        printf '%s ya tiene valor; para reemplazarlo: make key-set FILE=%s FORCE=1\n' "$f" "$f" >&2; exit 1
    fi
    [ -t 0 ] || { printf 'key-set necesita una terminal.\n' >&2; exit 1; }
    read -rs -p "Pega el valor para $f (no se muestra) y pulsa Enter: " value
    printf '\n'
    [ -n "$value" ] || { printf 'No se guardó nada: valor vacío.\n' >&2; exit 1; }
    umask 077
    mkdir -p "$(dirname "$f")"
    printf '%s' "$value" >"$f"
    chmod 600 "$f"
    printf 'Guardada en %s (permisos 600).\n' "$f"
}

case "${1:-status}" in
    init) init ;;
    status) status ;;
    set) set_key "${2:-}" ;;
    *) printf 'Uso: %s init | status | set keys/<servicio>/<archivo>\n' "$0" >&2; exit 2 ;;
esac
