"""Ingiere las seis copias verificadas del corpus de evaluación del IGSS."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .automatic import PortalEvent, event_id_for
from .pipeline import IngestionService, SourceMetadata, _sha256


# Orden documental: las bases de 222 deben existir antes de su modificación.
SELECTION = (
    ("399-IGSS-2026", "1f9aa9fdf38e8ce7780a00f37b49a9edda4ec9ef9426a979b2962127ff740444", "bases_integradas", "bases", None, None),
    ("363-IGSS-2026", "953eab12d975d203d1d4f27aed8e14c39581095d67ac91efbcda7a8934cb9426", "bases_integradas", "bases", None, None),
    ("222-IGSS-2023", "93fc4e4fa0ef1376c2d2163f092f08236986ac72f5caf828dd7869de36a3ed2f", "bases_integradas", "bases", None, None),
    ("222-IGSS-2023", "4101799486c95dc6d109a10043c3907704a3fc8ff1af249f7c1dc6faa61e8434", "modificacion_1", "modificacion", "Modificación Número 1", "bases_integradas"),
    ("327-IGSS-2023", "759ac61bfc2282b8012358001d66ad364447f7dc2b4435fa66d511435db57ae3", "bases_integradas", "bases", None, None),
    ("368-IGSS-2026", "1161c9f8b49aac197857a6de891d2b9e5db2d91df71a1221bf8d6a96ffb2e8a0", "bases_integradas", "bases", None, None),
)


def prepare(data_dir: Path, tenant_id: str) -> list[dict]:
    service = IngestionService(data_dir)
    results = []
    for number, digest, document_key, kind, official_version, relation in SELECTION:
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
        manifest = service.ingest(pdf, metadata)
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
    parser.add_argument("--tenant-id", required=True)
    parser.add_argument("--data-dir", type=Path, default=Path("data/ingesta"))
    args = parser.parse_args()
    print(json.dumps(prepare(args.data_dir, args.tenant_id), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
