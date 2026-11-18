"""Ingiere las copias verificadas del corpus de evaluación del IGSS que describe corpus_igss.json."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .automatic import PortalEvent, event_id_for
from .pipeline import IngestionService, SourceMetadata, _sha256

CORPUS = Path(__file__).with_name("corpus_igss.json")


def cargar_especificacion(ruta: Path = CORPUS) -> dict:
    return json.loads(Path(ruta).read_text(encoding="utf-8"))


def prepare(data_dir: Path, tenant_id: str | None = None, *, spec: dict | None = None) -> list[dict]:
    """Ingiere en el orden de la especificación, con sus doc_id e ingested_at fijados.

    Sin OCR en la ingesta: así los chunk_id no dependen de si el entorno tiene Tesseract. Las páginas
    ilegibles se recuperan después con reextraer, que agrega fragmentos sin mover los previos.
    """
    spec = spec or cargar_especificacion()
    if tenant_id is not None and tenant_id != spec["tenant_id"]:
        raise ValueError(f"El tenant {tenant_id} no es el de la especificación ({spec['tenant_id']}): "
                         "los doc_id fijos pertenecen a un solo espacio")
    tenant_id = spec["tenant_id"]
    service = IngestionService(data_dir)
    results = []
    for documento in spec["documentos"]:
        number, digest = documento["numero_evento"], documento["sha256"]
        document_key, kind = documento["document_key"], documento["tipo_documento"]
        official_version, relation = documento["version_oficial"], documento["relacion_documental"]
        stage = data_dir / "descargas_igss" / number / digest
        sidecar = json.loads(stage.with_suffix(".json").read_text(encoding="utf-8"))
        pdf = stage.with_suffix(".pdf")
        if sidecar["numero_evento"] != number or sidecar["sha256"] != digest or _sha256(pdf) != digest:
            raise ValueError(f"Descarga o metadatos inconsistentes: {number}, {digest}")
        event = PortalEvent(
            number, sidecar["anio"], sidecar["modalidad"], sidecar["titulo"],
            sidecar.get("unidad_requirente"), sidecar.get("codigo_igss"),
            sidecar.get("fecha_ficha"), sidecar["url_origen"],
        )
        metadata = SourceMetadata(
            tenant_id=tenant_id, evento_id=event_id_for(tenant_id, event),
            numero_evento=number, anio=event.anio, modalidad=event.modalidad,
            document_key=document_key, tipo_documento=kind, titulo=event.titulo,
            url_origen=event.pdf_url, unidad_requirente=event.unidad_requirente,
            codigos_producto_igss=(event.codigo_igss,) if event.codigo_igss else (),
            fecha_publicacion=sidecar.get("fecha_publicacion"),
            fecha_ficha=event.fecha_publicacion,
            fecha_descarga=sidecar["fecha_descarga"][:10],
            identificador_version_oficial=official_version,
            relacion_documental=relation,
        )
        if event_id_for(tenant_id, event) != documento["evento_id"]:
            raise ValueError(f"evento_id distinto al de la especificación: {number}")
        manifest = service.ingest(pdf, metadata, doc_id=documento["doc_id"],
                                  ingested_at=documento["ingested_at"], use_ocr=False)
        results.append({
            "numero_evento": number, "tipo_documento": kind,
            "doc_id": manifest["doc_id"], "evento_id": metadata.evento_id,
            "estado": manifest["status"],
            "fragmentos_indexables": sum(chunk["indexable"] for chunk in manifest["chunks"]),
            "paginas": manifest["cobertura"]["paginas_total"],
            "advertencias": manifest["warnings"],
        })
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tenant-id", help="opcional; debe ser el de la especificación")
    parser.add_argument("--data-dir", type=Path, default=Path("data/ingesta"))
    args = parser.parse_args()
    print(json.dumps(prepare(args.data_dir, args.tenant_id), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
