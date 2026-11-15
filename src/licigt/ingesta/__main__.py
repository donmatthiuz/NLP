"""Carga manual de PDF oficiales del IGSS."""

import argparse
import json
from pathlib import Path

from .pipeline import IngestionService, SourceMetadata


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingesta de PDF de licitaciones del IGSS")
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--data-dir", type=Path, default=Path("data/ingesta"))
    for name in ("tenant-id", "evento-id", "numero-evento", "anio", "modalidad", "document-key", "tipo-documento", "titulo", "url-origen"):
        parser.add_argument("--" + name, required=True)
    parser.add_argument("--unidad-requirente")
    parser.add_argument("--codigo-igss", action="append", default=[])
    parser.add_argument("--nog-referencia")
    parser.add_argument("--fecha-documento")
    parser.add_argument("--fecha-publicacion")
    parser.add_argument("--fecha-ficha")
    parser.add_argument("--fecha-descarga")
    parser.add_argument("--identificador-version-oficial")
    parser.add_argument("--relacion-documental")
    parser.add_argument("--sin-ocr", action="store_true")
    args = parser.parse_args()
    metadata = SourceMetadata(
        tenant_id=args.tenant_id, evento_id=args.evento_id,
        numero_evento=args.numero_evento, anio=int(args.anio), modalidad=args.modalidad,
        document_key=args.document_key, tipo_documento=args.tipo_documento,
        titulo=args.titulo, url_origen=args.url_origen,
        unidad_requirente=args.unidad_requirente,
        codigos_producto_igss=tuple(args.codigo_igss), nog_referencia=args.nog_referencia,
        fecha_documento=args.fecha_documento, fecha_publicacion=args.fecha_publicacion,
        fecha_ficha=args.fecha_ficha,
        fecha_descarga=args.fecha_descarga,
        identificador_version_oficial=args.identificador_version_oficial,
        relacion_documental=args.relacion_documental,
    )
    result = IngestionService(args.data_dir).ingest(args.pdf, metadata, use_ocr=not args.sin_ocr)
    print(json.dumps({"doc_id": result["doc_id"], "version_ingesta": result["version_ingesta"],
                      "status": result["status"], "pages": len(result["pages"]),
                      "chunks": len(result["chunks"]), "warnings": result["warnings"],
                      "object_uri": result["object_uri"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
