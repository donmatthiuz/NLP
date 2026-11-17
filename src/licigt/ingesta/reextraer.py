"""Reextrae con OCR las páginas ilegibles de un documento del paquete ZIP, sin cambiar los chunk_id previos."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
import zipfile
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .pdf import Page, extract_pages
from .pipeline import SUSPICIOUS, SourceMetadata, make_chunks

AVISO_PAGINAS = "Hay páginas incompletas o ilegibles"
AVISO_INSTRUCCIONES = "Posibles instrucciones incrustadas en páginas: "

# Medición del 17 de noviembre (R1_ingesta, Parte D) sobre las páginas 3 y 4 de la modificación del 222:
# los fragmentos buenos tenían 25, 101 y 40 palabras de 4 o más letras; el ruido de sellos y firmas, 9, 3 y 9.
MIN_PALABRAS_OCR = 20
PALABRA = re.compile(r"[^\W\d_]{4,}")


def _json(datos: Any) -> bytes:
    return (json.dumps(datos, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _linea(chunk: dict[str, Any]) -> bytes:
    return (json.dumps(chunk, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")


def _indice(chunk_id: str) -> int:
    return int(chunk_id.rsplit(":", 1)[1])


def reextraer(zip_path: Path, doc_id: str, salida: Path, advertencias: list[str] | None = None) -> dict[str, Any]:
    """Escribe un ZIP nuevo con las páginas recuperadas por OCR; si no recupera ninguna, no escribe nada."""
    if not re.fullmatch(r"[0-9a-f]{32}", doc_id):
        raise ValueError("doc_id inválido")
    zip_path, salida = Path(zip_path), Path(salida).resolve()
    with zipfile.ZipFile(zip_path) as archive:
        infos = archive.infolist()
        contenido = {info.filename: archive.read(info) for info in infos}
    inventario = json.loads(contenido["inventario.json"])
    entrada = next((d for d in inventario["documents"] if d["doc_id"] == doc_id), None)
    if entrada is None:
        raise ValueError(f"doc_id no está en el inventario del paquete: {doc_id}")
    manifiesto = json.loads(contenido[entrada["manifiesto_zip_path"]])
    original = contenido[entrada["original_zip_path"]]
    digest = hashlib.sha256(original).hexdigest()
    if not (digest == entrada["sha256"] == manifiesto["hash_sha256"]):
        raise ValueError(f"El hash del original no coincide con el inventario y el manifiesto: {doc_id}")

    with tempfile.TemporaryDirectory() as temporal:
        pdf = Path(temporal) / "original.pdf"
        pdf.write_bytes(original)
        nuevas = extract_pages(pdf, use_ocr=True)
    antes = {page["number"]: page for page in manifiesto["pages"]}
    recuperadas = [page for page in nuevas
                   if page.quality == "ok" and antes.get(page.number, {}).get("quality") != "ok"]
    if not recuperadas:
        return {"doc_id": doc_id, "paginas_recuperadas": [], "chunks_nuevos": [],
                "mensaje": "Sin cambios: el OCR no recuperó ninguna página (¿falta tesseract-ocr-spa?)"}

    metadata = SourceMetadata(**manifiesto["metadata"])
    version = manifiesto["version_ingesta"]
    base = max(_indice(c["chunk_id"]) for c in manifiesto["chunks"]) if manifiesto["chunks"] else 0
    por_numero = {page.number: page for page in recuperadas}
    paginas = [Page(**antes[n]) if n not in por_numero else por_numero[n] for n in sorted(antes)]
    escaneo = manifiesto["security_scan"]
    sospechosas = sorted(set(escaneo.get("suspicious_pages", []))
                         | {page.number for page in recuperadas if SUSPICIOUS.search(page.text)})
    cobertura = manifiesto["cobertura"]
    chunks_nuevos = make_chunks(recuperadas, doc_id, metadata, version)
    for chunk in chunks_nuevos:
        chunk["chunk_id"] = f"{doc_id}:{base + _indice(chunk['chunk_id']):05d}"
        chunk["hash_sha256"] = manifiesto["hash_sha256"]
        if chunk["pagina_inicio"] in sospechosas:
            chunk["injection_suspected"] = True
            chunk["indexable"] = False
        if len(PALABRA.findall(chunk["texto"])) < MIN_PALABRAS_OCR:
            chunk["indexable"] = False
            if not chunk.get("injection_suspected"):
                chunk["estado_calidad"] = "ruido_ocr"
        if cobertura["solo_convocatoria"] or not cobertura["evento_confirmado_en_pdf"] or not escaneo["scan_complete"]:
            chunk["indexable"] = False

    avisos = [w for w in manifiesto["warnings"] if not w.startswith(AVISO_INSTRUCCIONES)]
    if all(page.quality == "ok" for page in paginas):
        avisos = [w for w in avisos if w != AVISO_PAGINAS]
    if sospechosas:
        avisos.append(AVISO_INSTRUCCIONES + ", ".join(map(str, sospechosas)))
    avisos += [w for w in (advertencias or []) if w not in avisos]
    status = "completo" if not avisos else "requiere_revision"
    legibles = sum(page.quality == "ok" for page in paginas)

    manifiesto["pages"] = [asdict(page) for page in paginas]
    manifiesto["chunks"] = manifiesto["chunks"] + chunks_nuevos
    escaneo["suspicious_pages"] = sospechosas
    cobertura["paginas_legibles"] = legibles
    manifiesto["warnings"], manifiesto["status"] = avisos, status
    manifiesto["reextracted_at"] = datetime.now(timezone.utc).isoformat()
    indexables = sum(c["indexable"] for c in manifiesto["chunks"])
    entrada.update({"paginas_no_indexadas": [page.number for page in paginas if page.quality != "ok"],
                    "chunks_indexables": indexables,
                    "chunks_excluidos": len(manifiesto["chunks"]) - indexables,
                    "cobertura": cobertura, "warnings": avisos, "status": status,
                    "security_scan": escaneo})
    inventario["chunks_indexables"] = sum(d["chunks_indexables"] for d in inventario["documents"])
    inventario["chunks_excluidos"] = sum(d["chunks_excluidos"] for d in inventario["documents"])

    # Las líneas previas quedan intactas; las nuevas van tras las de este documento.
    lineas = contenido["chunks.jsonl"].splitlines(keepends=True)
    ultima = max((i for i, linea in enumerate(lineas)
                  if json.loads(linea)["doc_id"] == doc_id), default=len(lineas) - 1)
    lineas[ultima + 1:ultima + 1] = [_linea(c) for c in chunks_nuevos if c["indexable"]]
    contenido["chunks.jsonl"] = b"".join(lineas)
    inventario["sha256_chunks_jsonl"] = hashlib.sha256(contenido["chunks.jsonl"]).hexdigest()
    contenido[entrada["manifiesto_zip_path"]] = _json(manifiesto)
    contenido["inventario.json"] = _json(inventario)

    salida.parent.mkdir(parents=True, exist_ok=True)
    fd, temporal = tempfile.mkstemp(prefix=".reextraer_", suffix=".zip", dir=salida.parent)
    os.close(fd)
    os.chmod(temporal, 0o600)
    try:
        with zipfile.ZipFile(temporal, "w") as archive:
            for info in infos:
                archive.writestr(info, contenido[info.filename])
        os.replace(temporal, salida)
    finally:
        if os.path.exists(temporal):
            os.unlink(temporal)
    return {"doc_id": doc_id, "paginas_recuperadas": [page.number for page in recuperadas],
            "chunks_nuevos": [c["chunk_id"] for c in chunks_nuevos],
            "chunks_nuevos_indexables": [c["chunk_id"] for c in chunks_nuevos if c["indexable"]],
            "status": status, "mensaje": f"Páginas recuperadas por OCR: {[p.number for p in recuperadas]}"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--zip", type=Path, required=True)
    parser.add_argument("--doc-id", required=True)
    parser.add_argument("--salida", type=Path, required=True)
    parser.add_argument("--advertencia", action="append", default=[])
    args = parser.parse_args()
    try:
        resultado = reextraer(args.zip, args.doc_id, args.salida, args.advertencia)
    except (ValueError, RuntimeError, TimeoutError, KeyError, zipfile.BadZipFile) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    print(json.dumps(resultado, ensure_ascii=False, indent=2))
    return 0 if resultado["paginas_recuperadas"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
