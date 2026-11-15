"""Flujo de ingesta: validar → extraer → segmentar → versionar → publicar manifiesto."""

from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import uuid
from collections import Counter
from contextlib import closing
from dataclasses import asdict, dataclass, replace
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .pdf import Page, extract_pages
from .storage import store_from_environment

KINDS = {"bases", "especificaciones", "anexo", "convocatoria", "aclaracion", "modificacion", "normativa"}
SUSPICIOUS = re.compile(
    r"(?i)(ignora (todas )?(las )?instrucciones anteriores|ignore (all )?previous instructions|"
    r"revela (el )?prompt (del )?sistema|reveal (the )?system prompt|"
    r"actúa como (el )?sistema|you are now the system)"
)
HEADING = re.compile(r"^(?:\d+(?:\.\d+)*[.)]?\s+|(?:art[íi]culo|numeral|anexo|cap[íi]tulo|secci[óo]n)\s+[\w.-]+[:.]?\s+).{3,120}$", re.I)


@dataclass(frozen=True)
class SourceMetadata:
    """Datos declarados por un usuario autenticado; fechas desconocidas quedan en None."""

    tenant_id: str
    evento_id: str
    numero_evento: str
    anio: int
    modalidad: str
    document_key: str
    tipo_documento: str
    titulo: str
    url_origen: str
    entidad: str = "IGSS"
    unidad_requirente: str | None = None
    codigos_producto_igss: tuple[str, ...] = ()
    nog_referencia: str | None = None
    fecha_documento: str | None = None
    fecha_publicacion: str | None = None
    fecha_descarga: str | None = None
    identificador_version_oficial: str | None = None
    relacion_documental: str | None = None

    def validate(self) -> None:
        for name, value in (("tenant_id", self.tenant_id), ("evento_id", self.evento_id)):
            if not re.fullmatch(r"[a-zA-Z0-9_-]{1,80}", value):
                raise ValueError(f"{name} inválido")
        if not re.fullmatch(r"[A-Za-z0-9 /.-]{3,80}", self.numero_evento):
            raise ValueError("numero_evento inválido")
        if not 2000 <= self.anio <= 2100:
            raise ValueError("anio inválido")
        if str(self.anio) not in self.numero_evento:
            raise ValueError("El año debe aparecer en numero_evento")
        if not self.modalidad.strip():
            raise ValueError("modalidad obligatoria")
        if not re.fullmatch(r"[a-zA-Z0-9_-]{1,80}", self.document_key):
            raise ValueError("document_key admite letras, números, guion y guion bajo")
        if self.tipo_documento not in KINDS:
            raise ValueError(f"tipo_documento debe ser uno de: {', '.join(sorted(KINDS))}")
        if not self.titulo.strip() or self.entidad != "IGSS":
            raise ValueError("titulo obligatorio y entidad debe ser IGSS")
        if self.nog_referencia and not re.fullmatch(r"\d{1,20}", self.nog_referencia):
            raise ValueError("nog_referencia inválido")
        if any(not re.fullmatch(r"\d{1,10}", code) for code in self.codigos_producto_igss):
            raise ValueError("Código IGSS inválido")
        for name in ("fecha_documento", "fecha_publicacion", "fecha_descarga"):
            value = getattr(self, name)
            if value is not None:
                date.fromisoformat(value)
        parsed_url = urlparse(self.url_origen)
        if (parsed_url.scheme != "https" or parsed_url.username is not None
                or parsed_url.password is not None or parsed_url.port not in (None, 443)
                or not parsed_url.hostname or not (
            parsed_url.hostname == "igssgt.org" or parsed_url.hostname.endswith(".igssgt.org")
        )):
            raise ValueError("url_origen debe ser una URL HTTPS oficial del IGSS")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def _table_like(lines: list[str]) -> bool:
    return len(lines) >= 2 and sum(bool(re.search(r"\S {2,}\S", line)) for line in lines) >= 2


def _table_markdown(lines: list[str]) -> str | None:
    rows = [re.split(r" {2,}", line.strip()) for line in lines if line.strip()]
    if len(rows) < 2 or any(len(row) < 2 for row in rows):
        return None
    columns = max(map(len, rows))
    rows = [row + [""] * (columns - len(row)) for row in rows]
    render = lambda row: "| " + " | ".join(cell.replace("|", "\\|") for cell in row) + " |"
    return "\n".join([render(rows[0]), render(["---"] * columns), *(render(row) for row in rows[1:])])


def _units(page: Page, previous_section: str) -> tuple[list[dict[str, Any]], str]:
    """Separa encabezados, párrafos y tablas sin perder el texto extraído."""
    units: list[dict[str, Any]] = []
    section = previous_section
    current: list[str] = []

    def flush() -> None:
        if current:
            body = "\n".join(current).strip()
            if body:
                is_table = _table_like(current)
                units.append({"texto": body, "seccion": section,
                              "tipo_chunk": "tabla" if is_table else "texto",
                              "tabla_markdown": _table_markdown(current) if is_table else None})
            current.clear()

    for line in page.text.splitlines():
        stripped = line.strip()
        if not stripped:
            flush()
        elif HEADING.match(stripped):
            flush()
            section = stripped
            current.append(stripped)
        else:
            current.append(line)
    flush()
    return units, section


def _printed_page(text: str) -> int | None:
    """Solo acepta una numeración aislada al final; no adivina números ambiguos."""
    last_lines = [line.strip() for line in text.splitlines() if line.strip()][-6:]
    for line in reversed(last_lines):
        if re.fullmatch(r"\d{1,3}", line):
            return int(line)
        match = re.match(r"^(\d{1,3})\s+(?:Extensi[óo]n|www\.igssgt\.org)", line, re.I)
        if match:
            return int(match.group(1))
    return None


def _codes(text: str) -> list[str]:
    return sorted(set(re.findall(r"(?:C[ÓO]DIGO(?: DE PRODUCTO)? IGSS|C[ÓO]DIGO)\s*[:#]?\s*(\d{1,10})", text, re.I)))


def _nog_reference(pages: list[Page]) -> str | None:
    first_pages = "\n".join(page.text for page in pages[:3])
    found = re.search(r"\bNOG\)?\s*[:#]?\s*(\d{6,20})\b", first_pages, re.I)
    return found.group(1) if found else None


def _without_repeated_margins(pages: list[Page]) -> list[Page]:
    """Quita encabezados/pies repetidos del índice; conserva el texto original en pages."""
    counts = Counter()
    for page in pages:
        lines = page.text.splitlines()
        counts.update({line.strip() for line in lines[:8] + lines[-6:] if line.strip()})
    threshold = max(3, (len(pages) + 1) // 2)
    repeated = {line for line, count in counts.items() if count >= threshold}
    cleaned = []
    for page in pages:
        lines = page.text.splitlines()
        kept = [line for i, line in enumerate(lines)
                if not ((i < 8 or i >= len(lines) - 6) and line.strip() in repeated)]
        cleaned.append(Page(page.number, "\n".join(kept), page.method, page.quality, page.warnings))
    return cleaned


def make_chunks(pages: list[Page], doc_id: str, metadata: SourceMetadata, version: int,
                max_words: int = 600, overlap_words: int = 90) -> list[dict[str, Any]]:
    """~800 tokens / 120 de solapamiento estimados por palabras; una página por chunk."""
    if max_words < 1 or not 0 <= overlap_words < max_words:
        raise ValueError("Parámetros de segmentación inválidos")
    chunks = []
    section = "Sin sección"
    printed_by_page = {page.number: _printed_page(page.text) for page in pages}
    for page in _without_repeated_margins(pages):
        if page.quality != "ok":
            continue
        units, section = _units(page, section)
        merged = []
        for unit in units:
            if (merged and unit["tipo_chunk"] == "texto" and merged[-1]["tipo_chunk"] == "texto"
                    and unit["seccion"] == merged[-1]["seccion"]
                    and len((merged[-1]["texto"] + unit["texto"]).split()) <= max_words):
                merged[-1]["texto"] += "\n\n" + unit["texto"]
            else:
                merged.append(unit.copy())
        units = merged
        for unit in units:
            words = unit["texto"].split()
            if not words:
                continue
            # Conserva párrafos/tablas pequeños. Solo divide unidades largas.
            step = max_words - overlap_words
            for start in range(0, len(words), step):
                text = unit["texto"] if len(words) <= max_words else " ".join(words[start:start + max_words])
                if not text:
                    break
                index = len(chunks) + 1
                flagged = bool(SUSPICIOUS.search(text))
                chunks.append({
                    "chunk_id": f"{doc_id}:{index:05d}", "doc_id": doc_id,
                    "tenant_id": metadata.tenant_id, "evento_id": metadata.evento_id,
                    "numero_evento": metadata.numero_evento, "anio": metadata.anio,
                    "modalidad": metadata.modalidad, "unidad_requirente": metadata.unidad_requirente,
                    "codigos_producto_igss": sorted(set(metadata.codigos_producto_igss) | set(_codes(text))),
                    "nog_referencia": metadata.nog_referencia,
                    "tipo_documento": metadata.tipo_documento, "document_key": metadata.document_key,
                    "version_ingesta": version,
                    "identificador_version_oficial": metadata.identificador_version_oficial,
                    "relacion_documental": metadata.relacion_documental,
                    "titulo": metadata.titulo, "entidad": metadata.entidad,
                    "fecha_documento": metadata.fecha_documento,
                    "fecha_publicacion": metadata.fecha_publicacion,
                    "fecha_descarga": metadata.fecha_descarga, "url_origen": metadata.url_origen,
                    "pagina_inicio": page.number, "pagina_fin": page.number,
                    "pagina_impresa": printed_by_page[page.number], "estado_calidad": page.quality,
                    "seccion": unit["seccion"], "tipo_chunk": unit["tipo_chunk"],
                    "tabla_markdown": unit["tabla_markdown"] if len(words) <= max_words else None,
                    "texto": text, "metodo_extraccion": page.method,
                    "injection_suspected": flagged, "indexable": not flagged,
                })
                if start + max_words >= len(words):
                    break
    return chunks


class IngestionService:
    def __init__(self, data_dir: Path, store=None):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.store = store or store_from_environment(self.data_dir)
        # Registro nuevo: los datos previos de GUATECOMPRAS quedan intactos y aislados.
        self.database = self.data_dir / "igss_ingesta.sqlite3"
        with closing(sqlite3.connect(self.database)) as connection, connection:
            connection.execute("""CREATE TABLE IF NOT EXISTS events (
                tenant_id TEXT NOT NULL, evento_id TEXT NOT NULL, numero_evento TEXT NOT NULL,
                anio INTEGER NOT NULL, modalidad TEXT NOT NULL, unidad_requirente TEXT,
                PRIMARY KEY (tenant_id, evento_id)
            )""")
            connection.execute("""CREATE TABLE IF NOT EXISTS documents (
                doc_id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, evento_id TEXT NOT NULL,
                document_key TEXT NOT NULL, tipo_documento TEXT NOT NULL,
                version_ingesta INTEGER NOT NULL, sha256 TEXT NOT NULL,
                object_uri TEXT NOT NULL, manifest_path TEXT NOT NULL, status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(tenant_id, evento_id, document_key, version_ingesta),
                UNIQUE(tenant_id, evento_id, document_key, sha256)
            )""")
        os.chmod(self.database, 0o600)

    def ingest(self, pdf_path: Path, metadata: SourceMetadata, *, max_bytes: int = 50 * 1024 * 1024,
               use_ocr: bool = True) -> dict[str, Any]:
        metadata.validate()
        path = Path(pdf_path).resolve(strict=True)
        if not path.is_file() or path.stat().st_size == 0 or path.stat().st_size > max_bytes:
            raise ValueError("Archivo vacío, no regular o superior al límite de tamaño")
        with path.open("rb") as stream:
            if stream.read(5) != b"%PDF-":
                raise ValueError("El archivo no tiene cabecera PDF")
        digest = _sha256(path)
        with closing(sqlite3.connect(self.database)) as connection, connection:
            event = connection.execute(
                "SELECT numero_evento, anio, modalidad, unidad_requirente FROM events WHERE tenant_id=? AND evento_id=?",
                (metadata.tenant_id, metadata.evento_id),
            ).fetchone()
            event_details = (metadata.numero_evento, metadata.anio, metadata.modalidad, metadata.unidad_requirente)
            if event and event != event_details:
                raise ValueError("evento_id ya pertenece a otro evento o sus metadatos no coinciden")
            row = connection.execute(
                "SELECT manifest_path FROM documents WHERE tenant_id=? AND evento_id=? AND document_key=? AND sha256=?",
                (metadata.tenant_id, metadata.evento_id, metadata.document_key, digest),
            ).fetchone()
            if row:
                return json.loads(Path(row[0]).read_text(encoding="utf-8"))

        pages = extract_pages(path, use_ocr=use_ocr)
        extracted_nog = _nog_reference(pages)
        if extracted_nog and metadata.nog_referencia is None:
            metadata = replace(metadata, nog_referencia=extracted_nog)
        all_text = "\n".join(page.text for page in pages)
        normalized = re.sub(r"\s+", "", all_text).upper()
        event_matches = re.sub(r"\s+", "", metadata.numero_evento).upper() in normalized
        has_bases = bool(re.search(r"BASES DE LICITACI[ÓO]N|DOCUMENTOS DE LICITACI[ÓO]N", all_text, re.I))
        only_notice = metadata.tipo_documento == "convocatoria" or (len(pages) <= 2 and not has_bases)
        warnings = []
        if not event_matches:
            warnings.append("No se encontró el número de evento declarado en el PDF")
        if only_notice:
            warnings.append("El archivo parece ser solo una convocatoria; no demuestra cobertura de bases")
        if any(page.quality != "ok" for page in pages):
            warnings.append("Hay páginas incompletas o ilegibles")
        if extracted_nog and metadata.nog_referencia != extracted_nog:
            warnings.append("El NOG declarado difiere de la referencia encontrada en el PDF")
        with closing(sqlite3.connect(self.database, timeout=30)) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            event = connection.execute(
                "SELECT numero_evento, anio, modalidad, unidad_requirente FROM events WHERE tenant_id=? AND evento_id=?",
                (metadata.tenant_id, metadata.evento_id),
            ).fetchone()
            event_details = (metadata.numero_evento, metadata.anio, metadata.modalidad, metadata.unidad_requirente)
            if event and event != event_details:
                raise ValueError("evento_id ya pertenece a otro evento o sus metadatos no coinciden")
            if not event:
                connection.execute("INSERT INTO events VALUES (?, ?, ?, ?, ?, ?)",
                                   (metadata.tenant_id, metadata.evento_id, *event_details))
            if metadata.relacion_documental:
                related = connection.execute(
                    "SELECT 1 FROM documents WHERE tenant_id=? AND evento_id=? AND document_key=? LIMIT 1",
                    (metadata.tenant_id, metadata.evento_id, metadata.relacion_documental),
                ).fetchone()
                if not related:
                    warnings.append("El documento relacionado aún no está cargado en este evento")
            row = connection.execute(
                "SELECT manifest_path FROM documents WHERE tenant_id=? AND evento_id=? AND document_key=? AND sha256=?",
                (metadata.tenant_id, metadata.evento_id, metadata.document_key, digest),
            ).fetchone()
            if row:
                return json.loads(Path(row[0]).read_text(encoding="utf-8"))
            version = connection.execute(
                "SELECT COALESCE(MAX(version_ingesta), 0) + 1 FROM documents WHERE tenant_id=? AND evento_id=? AND document_key=?",
                (metadata.tenant_id, metadata.evento_id, metadata.document_key),
            ).fetchone()[0]
            previous = connection.execute(
                "SELECT doc_id FROM documents WHERE tenant_id=? AND evento_id=? AND document_key=? ORDER BY version_ingesta DESC LIMIT 1",
                (metadata.tenant_id, metadata.evento_id, metadata.document_key),
            ).fetchone()
            doc_id = uuid.uuid4().hex
            key = f"igss/{metadata.tenant_id}/{metadata.evento_id}/{metadata.document_key}/v{version}/{doc_id}.pdf"
            object_uri = self.store.put(path, key)
            chunks = make_chunks(pages, doc_id, metadata, version)
            for chunk in chunks:
                chunk["hash_sha256"] = digest
                if not event_matches or only_notice:
                    chunk["indexable"] = False
            if any(chunk["injection_suspected"] for chunk in chunks):
                warnings.append("Se detectaron posibles instrucciones ajenas al documento")
            status = "completo" if not warnings else "requiere_revision"
            existing_types = {row[0] for row in connection.execute(
                "SELECT DISTINCT tipo_documento FROM documents WHERE tenant_id=? AND evento_id=?",
                (metadata.tenant_id, metadata.evento_id),
            )}
            manifest = {
                "doc_id": doc_id, "hash_sha256": digest, "version_ingesta": version,
                "previous_doc_id": previous[0] if previous else None,
                "object_uri": object_uri, "status": status,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "chunking_revision": 2,
                "warnings": warnings,
                "cobertura": {"solo_convocatoria": only_notice, "evento_confirmado_en_pdf": event_matches,
                              "paginas_legibles": sum(page.quality == "ok" for page in pages),
                              "paginas_total": len(pages),
                              "tipos_cargados": sorted(existing_types | {metadata.tipo_documento})},
                "metadata": asdict(metadata), "pages": [asdict(page) for page in pages],
                "chunks": chunks,
            }
            manifest_dir = self.data_dir / "manifiestos_igss"
            manifest_dir.mkdir(exist_ok=True)
            manifest_path = manifest_dir / f"{doc_id}.json"
            with manifest_path.open("x", encoding="utf-8") as stream:
                json.dump(manifest, stream, ensure_ascii=False, indent=2)
            os.chmod(manifest_path, 0o600)
            connection.execute(
                "INSERT INTO documents VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (doc_id, metadata.tenant_id, metadata.evento_id, metadata.document_key,
                 metadata.tipo_documento, version, digest, object_uri,
                 str(manifest_path.resolve()), status, manifest["created_at"]),
            )
        return manifest

    def reprocess(self, doc_id: str) -> dict[str, Any]:
        """Reconstruye fragmentos desde texto guardado, sin cambiar original ni versión."""
        if not re.fullmatch(r"[0-9a-f]{32}", doc_id):
            raise ValueError("doc_id inválido")
        with closing(sqlite3.connect(self.database)) as connection:
            row = connection.execute("SELECT manifest_path FROM documents WHERE doc_id=?", (doc_id,)).fetchone()
        if not row:
            raise ValueError("Documento no registrado")
        path = Path(row[0])
        manifest = json.loads(path.read_text(encoding="utf-8"))
        pages = [Page(**page) for page in manifest["pages"]]
        metadata = SourceMetadata(**manifest["metadata"])
        if metadata.nog_referencia is None and (nog := _nog_reference(pages)):
            metadata = replace(metadata, nog_referencia=nog)
            manifest["metadata"] = asdict(metadata)
        chunks = make_chunks(pages, doc_id, metadata, manifest["version_ingesta"])
        for chunk in chunks:
            chunk["hash_sha256"] = manifest["hash_sha256"]
            if manifest["cobertura"]["solo_convocatoria"] or not manifest["cobertura"]["evento_confirmado_en_pdf"]:
                chunk["indexable"] = False
        manifest["chunks"] = chunks
        manifest["reprocessed_at"] = datetime.now(timezone.utc).isoformat()
        manifest["chunking_revision"] = 2
        temporary = path.with_suffix(".tmp")
        with temporary.open("x", encoding="utf-8") as stream:
            json.dump(manifest, stream, ensure_ascii=False, indent=2)
        os.chmod(temporary, 0o600)
        temporary.replace(path)
        return manifest
