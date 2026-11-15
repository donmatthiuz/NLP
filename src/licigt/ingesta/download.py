"""Descarga por lote PDF oficiales del IGSS y conserva su procedencia.

Este paso prepara archivos públicos; no crea eventos ni ejecuta la ingesta RAG.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tempfile
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from .automatic import PORTAL, OfficialFetcher, parse_portal, official_url

EVENT_NUMBER = re.compile(r"\d{1,5}-IGSS-\d{4}", re.I)
PDF_LIMIT = 50 * 1024 * 1024


def download_selected(numbers: list[str], data_dir: Path, *, fetcher=None,
                      extra_pdf_urls: dict[str, list[tuple[str, str]]] | None = None) -> list[dict]:
    """Descarga cada PDF enlazado a los eventos indicados, sin sobrescribir versiones."""
    selected = list(dict.fromkeys(number.upper() for number in numbers))
    if not selected or any(not EVENT_NUMBER.fullmatch(number) for number in selected):
        raise ValueError("Indica números institucionales como 399-IGSS-2026")
    extras = {number.upper(): documents for number, documents in (extra_pdf_urls or {}).items()}
    if any(number not in selected for number in extras):
        raise ValueError("Los PDF adicionales deben pertenecer a un evento seleccionado")
    for number, documents in extras.items():
        for kind, url in documents:
            if (kind not in {"bases", "anexo", "aclaracion", "modificacion"}
                    or not official_url(url) or not urlparse(url).path.lower().endswith(".pdf")
                    or number.lower() not in urlparse(url).path.lower()):
                raise ValueError(f"PDF adicional inválido para {number}")
    fetcher = fetcher or OfficialFetcher()
    events = {}
    for year in sorted({number.rsplit("-", 1)[1] for number in selected}):
        page_url = f"{PORTAL}?y={year}"
        html, _ = fetcher.get(page_url, 8 * 1024 * 1024)
        events.update({event.numero_evento.upper(): (event, page_url)
                       for event in parse_portal(html.decode("utf-8", "replace"))
                       if str(event.anio) == year})
    missing = [number for number in selected if number not in events]
    if missing:
        raise ValueError("Eventos no encontrados en Proveedores IGSS: " + ", ".join(missing))

    root = Path(data_dir) / "descargas_igss"
    results = []
    for number in selected:
        event, page_url = events[number]
        event_dir = root / number
        event_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        sources = [(url, "ficha", None) for url in event.pdf_urls or (event.pdf_url,)]
        sources.extend((url, "adicional", kind) for kind, url in extras.get(number, []))
        for source_url, source_type, document_type in dict.fromkeys(sources):
            if not official_url(source_url) or not urlparse(source_url).path.lower().endswith(".pdf"):
                raise ValueError(f"Enlace PDF no oficial para {number}")
            pdf_bytes, final_url = fetcher.get(source_url, PDF_LIMIT)
            if not official_url(final_url) or not pdf_bytes.startswith(b"%PDF-"):
                raise ValueError(f"El enlace de {number} no devolvió un PDF oficial válido")
            digest = hashlib.sha256(pdf_bytes).hexdigest()
            target = event_dir / f"{digest}.pdf"
            if target.exists():
                if hashlib.sha256(target.read_bytes()).hexdigest() != digest:
                    raise ValueError(f"La copia local de {number} no coincide con su nombre SHA-256")
                status = "ya_existia"
            else:
                with tempfile.NamedTemporaryFile(dir=event_dir, prefix=".descarga-", delete=False) as stream:
                    temporary = Path(stream.name)
                    stream.write(pdf_bytes)
                    stream.flush()
                    os.fsync(stream.fileno())
                try:
                    os.chmod(temporary, 0o600)
                    os.link(temporary, target)
                finally:
                    temporary.unlink(missing_ok=True)
                status = "descargado"
            manifest = {
                "numero_evento": event.numero_evento, "anio": event.anio,
                "modalidad": event.modalidad, "titulo": event.titulo,
                "unidad_requirente": event.unidad_requirente,
                "codigo_igss": event.codigo_igss,
                "fecha_ficha": event.fecha_publicacion,
                "fecha_publicacion": None,
                "fecha_descarga": datetime.now(ZoneInfo("America/Guatemala")).isoformat(),
                "pagina_origen": page_url, "enlace_en_ficha": source_type == "ficha",
                "tipo_documento_declarado": document_type,
                "url_origen": final_url,
                "sha256": digest, "bytes": len(pdf_bytes),
                "archivo": target.name,
            }
            manifest_path = target.with_suffix(".json")
            if not manifest_path.exists():
                with manifest_path.open("x", encoding="utf-8") as stream:
                    json.dump(manifest, stream, ensure_ascii=False, indent=2)
                os.chmod(manifest_path, 0o600)
            results.append({"numero_evento": number, "estado": status,
                            "tipo_documento_declarado": document_type,
                            "archivo": str(target.resolve()), "sha256": digest,
                            "bytes": len(pdf_bytes), "manifiesto": str(manifest_path.resolve())})
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Descargar PDF oficiales de eventos seleccionados del IGSS")
    parser.add_argument("--numero-evento", action="append", required=True,
                        help="Repite esta opción para descargar varios eventos")
    parser.add_argument("--pdf-adicional", action="append", default=[],
                        metavar="EVENTO:TIPO:URL",
                        help="PDF oficial adicional no enlazado en la ficha; repite para varios")
    parser.add_argument("--data-dir", type=Path, default=Path("data/ingesta"))
    args = parser.parse_args()
    try:
        extras: dict[str, list[tuple[str, str]]] = {}
        for value in args.pdf_adicional:
            number, kind, url = value.split(":", 2)
            extras.setdefault(number, []).append((kind, url))
        results = download_selected(args.numero_evento, args.data_dir, extra_pdf_urls=extras)
    except (ValueError, RuntimeError, OSError) as exc:
        parser.exit(2, f"No se completó la descarga: {exc}\n")
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
