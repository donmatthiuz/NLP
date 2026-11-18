"""Evento de carga para la auditoría del rol 4.

Función pura sobre el manifiesto: resume el resultado de una carga sin texto de
páginas ni de fragmentos, sin rutas locales y sin credenciales.
"""

from __future__ import annotations

import json
from typing import Any

AVISO_ILEGIBLES = "Hay páginas incompletas o ilegibles"


def evento_de_carga(manifest: dict[str, Any]) -> dict[str, Any]:
    metadata = manifest["metadata"]
    cobertura = manifest["cobertura"]
    warnings = list(manifest["warnings"])
    status = manifest["status"]
    if cobertura["paginas_legibles"] < cobertura["paginas_total"]:
        status = "requiere_revision"
        if AVISO_ILEGIBLES not in warnings:
            warnings.append(AVISO_ILEGIBLES)
    evento = {
        "tenant_id": metadata["tenant_id"], "evento_id": metadata["evento_id"],
        "doc_id": manifest["doc_id"], "hash_sha256": manifest["hash_sha256"],
        "status": status, "paginas_legibles": cobertura["paginas_legibles"],
        "paginas_total": cobertura["paginas_total"], "warnings": warnings,
        "created_at": manifest["created_at"],
    }
    if manifest.get("reextracted_at"):
        evento["reextracted_at"] = manifest["reextracted_at"]
    return evento


def main(argv: list[str] | None = None) -> None:
    import argparse
    from pathlib import Path

    parser = argparse.ArgumentParser(description="Imprime el evento de carga de un manifiesto")
    parser.add_argument("--manifiesto", type=Path, required=True)
    args = parser.parse_args(argv)
    manifest = json.loads(args.manifiesto.read_text(encoding="utf-8"))
    print(json.dumps(evento_de_carga(manifest), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
