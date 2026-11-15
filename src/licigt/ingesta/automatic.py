"""Descarga opcional de PDF públicos desde Proveedores del IGSS.

El MVP conserva la carga manual. Este conector selecciona un evento concreto,
sin rastrear masivamente el portal ni seguir enlaces a otras plataformas.
"""

from __future__ import annotations

import json
import re
import tempfile
import uuid
from dataclasses import dataclass
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener
from zoneinfo import ZoneInfo

from .pipeline import IngestionService, SourceMetadata

PORTAL = "https://www.igssgt.org/proveedores/"


def official_url(url: str) -> bool:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    return parsed.scheme == "https" and parsed.username is None and parsed.password is None and (
        host == "igssgt.org" or host.endswith(".igssgt.org")
    ) and parsed.port in (None, 443)


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


class OfficialFetcher:
    def __init__(self, timeout: int = 25):
        self.opener = build_opener(_NoRedirect)
        self.timeout = timeout

    def get(self, url: str, max_bytes: int) -> tuple[bytes, str]:
        for _ in range(5):
            if not official_url(url):
                raise ValueError("Solo se permiten descargas HTTPS del dominio oficial igssgt.org")
            try:
                request = Request(url, headers={"User-Agent": "LiciGT/0.2 (corpus academico IGSS)"})
                with self.opener.open(request, timeout=self.timeout) as response:
                    if response.headers.get("Content-Length") and int(response.headers["Content-Length"]) > max_bytes:
                        raise ValueError("Archivo superior al límite permitido")
                    content = response.read(max_bytes + 1)
                    if len(content) > max_bytes:
                        raise ValueError("Archivo superior al límite permitido")
                    return content, url
            except HTTPError as exc:
                if exc.code in (301, 302, 303, 307, 308) and exc.headers.get("Location"):
                    url = urljoin(url, exc.headers["Location"])
                    continue
                raise RuntimeError(f"IGSS respondió HTTP {exc.code}") from exc
            except URLError as exc:
                raise RuntimeError(f"No se pudo conectar con IGSS: {exc.reason}") from exc
        raise RuntimeError("Demasiadas redirecciones")


@dataclass(frozen=True)
class PortalEvent:
    numero_evento: str
    anio: int
    modalidad: str
    titulo: str
    unidad_requirente: str | None
    codigo_igss: str | None
    fecha_publicacion: str | None
    pdf_url: str


class _PortalRows(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows: list[PortalEvent] = []
        self.row: dict | None = None
        self.capture: str | None = None

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "tr" and attributes.get("data-prov-id"):
            self.row = {"text": [], "title": [], "unit": [], "date": attributes.get("data-pub"), "links": []}
        if self.row is None:
            return
        if tag == "div":
            classes = attributes.get("class", "")
            if "fw-semibold" in classes:
                self.capture = "title"
            elif "text-muted" in classes:
                self.capture = "unit"
        if tag == "a" and attributes.get("href"):
            self.row["links"].append(attributes["href"])

    def handle_data(self, data):
        if self.row is not None:
            self.row["text"].append(data)
            if self.capture:
                self.row[self.capture].append(data)

    def handle_endtag(self, tag):
        if tag == "div":
            self.capture = None
        if tag != "tr" or self.row is None:
            return
        row = self.row
        self.row = None
        text = " ".join(row["text"])
        number = re.search(r"(?:No\.|N[oº]\.?)\s*(\d{1,5}-IGSS-(\d{4}))", text, re.I)
        if not number:
            return
        links = [urljoin(PORTAL, url) for url in row["links"]]
        pdf_links = [url for url in links if official_url(url) and urlparse(url).path.lower().endswith(".pdf")]
        if not pdf_links:
            return
        code = re.search(r"C[óo]digo:\s*(\d{1,10})", text, re.I)
        modality = "Licitación Pública DA" if "licitaci" in text.lower() else "Cotización DA"
        published = row["date"] if row["date"] and re.fullmatch(r"\d{4}-\d{2}-\d{2}", row["date"]) else None
        self.rows.append(PortalEvent(
            numero_evento=number.group(1), anio=int(number.group(2)), modalidad=modality,
            titulo=" ".join(row["title"]).strip() or f"Evento {number.group(1)}",
            unidad_requirente=" ".join(row["unit"]).strip() or None,
            codigo_igss=code.group(1) if code else None,
            fecha_publicacion=published, pdf_url=pdf_links[0],
        ))


def parse_portal(html: str) -> list[PortalEvent]:
    parser = _PortalRows()
    parser.feed(html)
    return parser.rows


def event_id_for(tenant_id: str, event: PortalEvent) -> str:
    key = f"igss:{tenant_id}:{event.modalidad}:{event.numero_evento}:{event.unidad_requirente or ''}"
    return uuid.uuid5(uuid.NAMESPACE_URL, key).hex


def ingest_event(numero_evento: str, tenant_id: str, service: IngestionService, *,
                 evento_id: str | None = None, fetcher=None) -> dict:
    if not re.fullmatch(r"\d{1,5}-IGSS-\d{4}", numero_evento, re.I):
        raise ValueError("Número institucional esperado, por ejemplo 399-IGSS-2026")
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", tenant_id):
        raise ValueError("tenant_id inválido")
    fetcher = fetcher or OfficialFetcher()
    html_bytes, _ = fetcher.get(PORTAL, 8 * 1024 * 1024)
    event = next((item for item in parse_portal(html_bytes.decode("utf-8", "replace"))
                  if item.numero_evento.upper() == numero_evento.upper()), None)
    if event is None:
        raise ValueError("El evento no aparece en la página Proveedores del IGSS")
    pdf_bytes, final_url = fetcher.get(event.pdf_url, 50 * 1024 * 1024)
    if not pdf_bytes.startswith(b"%PDF-"):
        raise ValueError("El enlace del IGSS no devolvió un PDF válido")
    metadata = SourceMetadata(
        tenant_id=tenant_id, evento_id=evento_id or event_id_for(tenant_id, event),
        numero_evento=event.numero_evento, anio=event.anio,
        modalidad=event.modalidad, document_key="bases_integradas", tipo_documento="bases",
        titulo=event.titulo, entidad="IGSS", unidad_requirente=event.unidad_requirente,
        codigos_producto_igss=(event.codigo_igss,) if event.codigo_igss else (),
        fecha_publicacion=event.fecha_publicacion,
        fecha_descarga=datetime.now(ZoneInfo("America/Guatemala")).date().isoformat(),
        url_origen=final_url,
    )
    with tempfile.TemporaryDirectory() as temporary:
        path = Path(temporary) / "igss.pdf"
        path.write_bytes(pdf_bytes)
        result = service.ingest(path, metadata)
    return {"evento_id": metadata.evento_id, "numero_evento": event.numero_evento,
            "doc_id": result["doc_id"], "version_ingesta": result["version_ingesta"],
            "status": result["status"], "paginas": len(result["pages"]),
            "fragmentos": len(result["chunks"]), "url_origen": final_url,
            "warnings": result["warnings"], "object_uri": result["object_uri"]}


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Descargar e ingerir un evento del portal Proveedores IGSS")
    parser.add_argument("--numero-evento", required=True, help="Ejemplo: 399-IGSS-2026")
    parser.add_argument("--tenant-id", required=True, help="Identificador de empresa autorizado")
    parser.add_argument("--evento-id", help="ID interno existente; si se omite se genera uno estable")
    parser.add_argument("--data-dir", type=Path, default=Path("data/ingesta"))
    args = parser.parse_args()
    try:
        result = ingest_event(args.numero_evento, args.tenant_id, IngestionService(args.data_dir), evento_id=args.evento_id)
    except (ValueError, RuntimeError) as exc:
        parser.exit(2, f"No se completó la descarga: {exc}\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
