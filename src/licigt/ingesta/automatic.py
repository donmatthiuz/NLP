"""Descubre y descarga PDF públicos de GUATECOMPRAS antes de la ingesta local.

Acepta la ficha pública de un NOG o un paquete JSON OCDS oficial. No usa
credenciales, cookies, navegadores automatizados ni evasión de desafíos.
"""

from __future__ import annotations

import hashlib
import json
import re
import tempfile
from dataclasses import dataclass
from datetime import date
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .pipeline import IngestionService, SourceMetadata


class PortalUnavailable(RuntimeError):
    """La fuente oficial no está disponible sin interacción humana."""


def official_url(url: str) -> bool:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    return parsed.scheme == "https" and parsed.username is None and parsed.password is None and (
        host == "guatecompras.gt" or host.endswith(".guatecompras.gt")
    ) and parsed.port in (None, 443)


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


class OfficialFetcher:
    def __init__(self, timeout: int = 20):
        self.opener = build_opener(_NoRedirect)
        self.timeout = timeout

    def get(self, url: str, max_bytes: int) -> tuple[bytes, str, str]:
        for _ in range(5):
            if not official_url(url):
                raise ValueError(f"URL fuera de GUATECOMPRAS: {url}")
            request = Request(url, headers={"User-Agent": "LiciGT/0.1 (+investigacion academica)", "Accept": "application/pdf, application/json, text/html"})
            try:
                with self.opener.open(request, timeout=self.timeout) as response:
                    content_type = response.headers.get_content_type()
                    content = response.read(max_bytes + 1)
                    if len(content) > max_bytes:
                        raise ValueError(f"Respuesta mayor que {max_bytes} bytes")
                    if b"cf-mitigated" in content[:8000] or b"Just a moment" in content[:8000]:
                        raise PortalUnavailable("GUATECOMPRAS solicitó una verificación de navegador")
                    return content, url, content_type
            except HTTPError as exc:
                if exc.code in (301, 302, 303, 307, 308):
                    location = exc.headers.get("Location")
                    if not location:
                        raise PortalUnavailable("Redirección sin destino") from exc
                    url = urljoin(url, location)
                    continue
                if exc.code in (403, 429):
                    raise PortalUnavailable(f"GUATECOMPRAS respondió HTTP {exc.code}; no se intentará evadir el bloqueo") from exc
                raise PortalUnavailable(f"GUATECOMPRAS respondió HTTP {exc.code}") from exc
            except URLError as exc:
                raise PortalUnavailable(f"No se pudo conectar con GUATECOMPRAS: {exc.reason}") from exc
        raise PortalUnavailable("Demasiadas redirecciones")


@dataclass(frozen=True)
class Candidate:
    url: str
    title: str
    date_published: str | None = None


class _Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links: list[tuple[str, str]] = []
        self._href: str | None = None
        self._text: list[str] = []
        self.visible: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self._href = dict(attrs).get("href")
            self._text = []

    def handle_data(self, data):
        self.visible.append(data)
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self._href is not None:
            self.links.append((self._href, " ".join(self._text).strip()))
            self._href = None


def _kind(title: str) -> str:
    value = title.lower()
    for word, kind in (("aclaraci", "aclaracion"), ("modific", "modificacion"),
                       ("anexo", "anexo"), ("términos de referencia", "terminos_referencia"),
                       ("terminos de referencia", "terminos_referencia"), ("base", "bases")):
        if word in value:
            return kind
    return "anexo"


def _key(candidate: Candidate, kind: str) -> str:
    # URL estable: un PDF modificado en el mismo enlace se convierte en nueva versión.
    suffix = hashlib.sha256(candidate.url.encode()).hexdigest()[:12]
    return f"{kind}_{suffix}"


def _iso_date(value: str | None) -> str | None:
    if not value:
        return None
    match = re.search(r"\d{4}-\d{2}-\d{2}", value)
    if match:
        try:
            return date.fromisoformat(match.group()).isoformat()
        except ValueError:
            pass
    return None


def candidates_from_ocds(payload: dict, nog: str) -> tuple[dict, list[Candidate]]:
    """Lee tender.documents de release, release package o record package OCDS."""
    items = payload.get("releases") or payload.get("records") or [payload]
    candidates: list[Candidate] = []
    selected: dict = {}
    for item in items:
        release = item.get("compiledRelease") or item
        if not isinstance(release, dict):
            continue
        ocid = str(release.get("ocid", ""))
        if ocid.split("-")[-1] != nog:
            continue
        tender = release.get("tender") or {}
        if not isinstance(tender, dict):
            continue
        selected = release
        for doc in tender.get("documents") or []:
            if not isinstance(doc, dict):
                continue
            url = doc.get("url")
            if isinstance(url, str) and official_url(url):
                candidates.append(Candidate(url, str(doc.get("title") or doc.get("id") or "Documento"),
                                            _iso_date(doc.get("datePublished"))))
    if not selected:
        raise ValueError(f"El paquete OCDS no contiene el NOG {nog}")
    return selected, list({candidate.url: candidate for candidate in candidates}.values())


def candidates_from_html(html: str, page_url: str) -> tuple[str, str, str | None, list[Candidate]]:
    parser = _Links()
    parser.feed(html)
    text = " ".join(parser.visible)
    title = re.search(r"(?:Descripci[oó]n(?: del concurso)?|Objeto)\s*[:：]?\s*(.{8,160}?)(?=\s{2,}|\b(?:Entidad|Modalidad|Fecha)\b)", text, re.I)
    entity = re.search(r"(?:Entidad|Unidad compradora)\s*[:：]?\s*(.{4,120}?)(?=\s{2,}|\b(?:Modalidad|Fecha|NOG)\b)", text, re.I)
    published = re.search(r"Fecha de publicaci[oó]n\s*[:：]?\s*(\d{4}-\d{2}-\d{2})", text, re.I)
    candidates = []
    for href, label in parser.links:
        url = urljoin(page_url, href)
        if not official_url(url):
            continue
        if re.search(r"\.pdf(?:[?#]|$)", url, re.I) or re.search(r"bases|anexo|aclaraci|modific|t[eé]rminos", label, re.I):
            candidates.append(Candidate(url, label or "Documento"))
    unique = list({candidate.url: candidate for candidate in candidates}.values())
    return title.group(1).strip() if title else "", entity.group(1).strip() if entity else "", _iso_date(published.group(1)) if published else None, unique


def ingest_nog(nog: str, service: IngestionService, *, ocds_json: Path | None = None,
               title: str | None = None, entity: str | None = None, published: str | None = None,
               fetcher=None, max_documents: int = 30) -> dict:
    """Descubre enlaces oficiales, descarga PDF y llama al pipeline existente."""
    if not re.fullmatch(r"\d{1,20}", nog):
        raise ValueError("NOG inválido")
    fetcher = fetcher or OfficialFetcher()
    page_url = f"https://www.guatecompras.gt/concursos/consultaConcurso.aspx?nog={nog}"
    if ocds_json:
        release, candidates = candidates_from_ocds(json.loads(Path(ocds_json).read_text(encoding="utf-8")), nog)
        tender = release.get("tender") or {}
        title = title or tender.get("title")
        buyer = release.get("buyer") or {}
        entity = entity or buyer.get("name")
        published = published or _iso_date(tender.get("datePublished")) or _iso_date(release.get("date"))
    else:
        body, _, content_type = fetcher.get(page_url, 5 * 1024 * 1024)
        if content_type not in ("text/html", "application/xhtml+xml"):
            raise ValueError("La ficha del NOG no devolvió HTML")
        parsed_title, parsed_entity, parsed_date, candidates = candidates_from_html(body.decode("utf-8", "replace"), page_url)
        title, entity, published = title or parsed_title, entity or parsed_entity, published or parsed_date
    if not (title and entity and published):
        raise ValueError("Faltan título, entidad o fecha de publicación; proporciónalos por CLI o usa un paquete OCDS completo")
    if not candidates:
        raise ValueError("No se encontraron enlaces públicos a documentos en la fuente")
    if len(candidates) > max_documents:
        raise ValueError(f"Se encontraron {len(candidates)} enlaces; el máximo es {max_documents}")
    results, skipped = [], []
    for candidate in candidates:
        try:
            content, final_url, _ = fetcher.get(candidate.url, 50 * 1024 * 1024)
            if not content.startswith(b"%PDF-"):
                skipped.append({"url": candidate.url, "reason": "No es un PDF"})
                continue
            kind = _kind(candidate.title)
            metadata = SourceMetadata(
                nog=nog, document_key=_key(candidate, kind), tipo_documento=kind,
                titulo=title, entidad=entity,
                fecha_publicacion=candidate.date_published or published,
                url_origen=final_url,
            )
            with tempfile.TemporaryDirectory() as temporary:
                path = Path(temporary) / "documento.pdf"
                path.write_bytes(content)
                manifest = service.ingest(path, metadata)
            results.append({"doc_id": manifest["doc_id"], "version": manifest["version"],
                            "status": manifest["status"], "url": final_url,
                            "chunks": len(manifest["chunks"])})
        except (PortalUnavailable, ValueError, RuntimeError) as exc:
            skipped.append({"url": candidate.url, "reason": str(exc)})
    return {"nog": nog, "page_url": page_url, "ingested": results, "skipped": skipped}


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Descubrir e ingerir PDF públicos de un NOG")
    parser.add_argument("--nog", required=True)
    parser.add_argument("--data-dir", type=Path, default=Path("data/ingesta"))
    parser.add_argument("--ocds-json", type=Path, help="Paquete OCDS JSON descargado del portal oficial")
    parser.add_argument("--titulo", help="Título si la fuente no lo informa")
    parser.add_argument("--entidad", help="Entidad si la fuente no la informa")
    parser.add_argument("--fecha-publicacion", help="AAAA-MM-DD si la fuente no la informa")
    args = parser.parse_args()
    try:
        result = ingest_nog(
            args.nog, IngestionService(args.data_dir), ocds_json=args.ocds_json,
            title=args.titulo, entity=args.entidad, published=args.fecha_publicacion,
        )
    except (ValueError, PortalUnavailable) as exc:
        parser.exit(2, f"No se completó la extracción: {exc}\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
