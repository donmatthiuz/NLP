"""Uso: PYTHONPATH=src python -m licigt.ingesta --help"""

import argparse
import json
from pathlib import Path

from .pipeline import IngestionService, SourceMetadata


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingesta de PDF de GUATECOMPRAS para LiciGT")
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--data-dir", type=Path, default=Path("data/ingesta"))
    for name in ("nog", "document-key", "tipo-documento", "titulo", "entidad", "fecha-publicacion", "url-origen"):
        parser.add_argument("--" + name, required=True)
    parser.add_argument("--tenant-id")
    parser.add_argument("--visibilidad", choices=["publica", "privada"], default="publica")
    parser.add_argument("--sin-ocr", action="store_true")
    args = parser.parse_args()
    metadata = SourceMetadata(
        nog=args.nog, document_key=args.document_key, tipo_documento=args.tipo_documento,
        titulo=args.titulo, entidad=args.entidad, fecha_publicacion=args.fecha_publicacion,
        url_origen=args.url_origen, tenant_id=args.tenant_id, visibilidad=args.visibilidad,
    )
    result = IngestionService(args.data_dir).ingest(args.pdf, metadata, use_ocr=not args.sin_ocr)
    print(json.dumps({"doc_id": result["doc_id"], "version": result["version"],
                      "status": result["status"], "pages": len(result["pages"]),
                      "chunks": len(result["chunks"]), "object_uri": result["object_uri"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
