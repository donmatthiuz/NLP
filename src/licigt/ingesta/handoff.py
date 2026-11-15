"""Empaqueta originales y fragmentos indexables para Recuperación y RAG."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import tempfile
import zipfile
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urlparse

from .pipeline import _sha256


def _local_original(uri: str, data_dir: Path) -> Path:
    parsed = urlparse(uri)
    if parsed.scheme != "file" or parsed.netloc:
        raise ValueError("Esta exportación portátil requiere originales locales; para MinIO comparta el bucket y sus permisos")
    original = Path(unquote(parsed.path)).resolve(strict=True)
    if not original.is_relative_to(data_dir.resolve()):
        raise ValueError(f"El original queda fuera de {data_dir}: {original}")
    return original


def export(data_dir: Path, tenant_id: str, output: Path) -> dict:
    """Crea un ZIP atómico para un espacio de prueba; falla si hay referencias inconsistentes."""
    if not tenant_id or not all(c.isalnum() or c in "_-" for c in tenant_id):
        raise ValueError("tenant_id inválido")
    database = data_dir / "igss_ingesta.sqlite3"
    if not database.is_file():
        raise FileNotFoundError(database)
    with closing(sqlite3.connect(database)) as connection:
        rows = connection.execute(
            """SELECT doc_id, evento_id, document_key, tipo_documento, version_ingesta,
                      sha256, object_uri, manifest_path, status
                 FROM documents WHERE tenant_id=?
                 ORDER BY evento_id, document_key, version_ingesta, doc_id""",
            (tenant_id,),
        ).fetchall()
    if not rows:
        raise ValueError(f"No hay documentos para {tenant_id}")

    inventory = {
        "schema_version": 1, "generated_at": datetime.now(timezone.utc).isoformat(),
        "tenant_id": tenant_id, "documents": [], "chunks_indexables": 0,
        "chunks_excluidos": 0,
        "nota": "El estado del documento y la cobertura deben mostrarse al consultar; la ausencia de alertas no garantiza expediente completo.",
    }
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".entrega_", suffix=".zip", dir=output.parent)
    os.close(fd)
    os.chmod(temporary, 0o600)
    try:
        chunk_lines = []
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for doc_id, event_id, document_key, kind, version, digest, uri, manifest_path, status in rows:
                manifest_file = Path(manifest_path).resolve(strict=True)
                if not manifest_file.is_relative_to(data_dir.resolve()):
                    raise ValueError(f"Manifiesto fuera de {data_dir}: {manifest_file}")
                manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
                meta = manifest["metadata"]
                expected = (tenant_id, event_id, doc_id, document_key, kind, version, digest, uri, status)
                actual = (meta["tenant_id"], meta["evento_id"], manifest["doc_id"], meta["document_key"],
                          meta["tipo_documento"], manifest["version_ingesta"], manifest["hash_sha256"],
                          manifest["object_uri"], manifest["status"])
                if actual != expected:
                    raise ValueError(f"Registro y manifiesto difieren: {doc_id}")
                original = _local_original(uri, data_dir)
                if _sha256(original) != digest:
                    raise ValueError(f"El hash del original no coincide: {doc_id}")
                pdf_name = f"originales/{doc_id}.pdf"
                archive.write(original, pdf_name)
                portable_manifest = dict(manifest)
                portable_manifest["object_uri"] = pdf_name
                portable_manifest["original_zip_path"] = pdf_name
                manifest_name = f"manifiestos/{doc_id}.json"
                archive.writestr(manifest_name, json.dumps(portable_manifest, ensure_ascii=False, indent=2) + "\n")
                sidecar_path = data_dir / "descargas_igss" / meta["numero_evento"] / f"{digest}.json"
                provenance_name = None
                if sidecar_path.is_file():
                    provenance = json.loads(sidecar_path.read_text(encoding="utf-8"))
                    if (provenance["numero_evento"], provenance["sha256"], provenance["url_origen"]) != (
                            meta["numero_evento"], digest, meta["url_origen"]):
                        raise ValueError(f"JSON de descarga no corresponde al original: {doc_id}")
                    provenance.pop("archivo", None)
                    provenance["original_zip_path"] = pdf_name
                    provenance_name = f"procedencia/{doc_id}.json"
                    archive.writestr(provenance_name, json.dumps(provenance, ensure_ascii=False, indent=2) + "\n")
                indexable = []
                excluded = 0
                for chunk in manifest["chunks"]:
                    if (chunk["doc_id"], chunk["tenant_id"], chunk["evento_id"],
                        chunk["version_ingesta"], chunk["hash_sha256"]) != (
                            doc_id, tenant_id, event_id, version, digest):
                        raise ValueError(f"Fragmento no corresponde al documento: {doc_id}")
                    if chunk["indexable"]:
                        if chunk["injection_suspected"] or not chunk["texto"].strip():
                            raise ValueError(f"Fragmento marcado indebidamente como indexable: {chunk['chunk_id']}")
                        indexable.append(chunk)
                        chunk_lines.append(json.dumps(chunk, ensure_ascii=False, sort_keys=True) + "\n")
                    else:
                        excluded += 1
                inventory["documents"].append({
                    "doc_id": doc_id, "evento_id": event_id, "numero_evento": meta["numero_evento"],
                    "document_key": document_key, "tipo_documento": kind,
                    "version_ingesta": version, "identificador_version_oficial": meta["identificador_version_oficial"],
                    "relacion_documental": meta["relacion_documental"], "sha256": digest,
                    "url_origen": meta["url_origen"], "original_zip_path": pdf_name,
                    "manifiesto_zip_path": manifest_name,
                    "procedencia_zip_path": provenance_name,
                    "fecha_documento": meta["fecha_documento"],
                    "fecha_publicacion": meta["fecha_publicacion"],
                    "fecha_ficha": meta.get("fecha_ficha"), "fecha_descarga": meta["fecha_descarga"],
                    "status": status, "warnings": manifest["warnings"], "cobertura": manifest["cobertura"],
                    "paginas_no_indexadas": [page["number"] for page in manifest["pages"] if page["quality"] != "ok"],
                    "security_scan": manifest["security_scan"],
                    "chunks_indexables": len(indexable), "chunks_excluidos": excluded,
                })
                inventory["chunks_indexables"] += len(indexable)
                inventory["chunks_excluidos"] += excluded
            chunks_jsonl = "".join(chunk_lines).encode("utf-8")
            inventory["sha256_chunks_jsonl"] = hashlib.sha256(chunks_jsonl).hexdigest()
            archive.writestr("chunks.jsonl", chunks_jsonl)
            archive.writestr("inventario.json", json.dumps(inventory, ensure_ascii=False, indent=2) + "\n")
        os.replace(temporary, output)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return inventory


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tenant-id", required=True)
    parser.add_argument("--data-dir", type=Path, default=Path("data/ingesta"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    inventory = export(args.data_dir, args.tenant_id, args.output)
    print(json.dumps({"archivo": args.output.as_posix(), "documentos": len(inventory["documents"]),
                      "chunks_indexables": inventory["chunks_indexables"],
                      "chunks_excluidos": inventory["chunks_excluidos"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
