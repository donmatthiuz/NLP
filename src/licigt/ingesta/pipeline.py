"""Flujo de ingesta: validar → extraer → segmentar → versionar → publicar manifiesto."""

from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import uuid
from contextlib import closing
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .pdf import Page, extract_pages
from .storage import store_from_environment

KINDS = {"bases", "terminos_referencia", "anexo", "aclaracion", "modificacion", "ley", "reglamento"}
SUSPICIOUS = re.compile(
    r"(?i)(ignora (todas )?(las )?instrucciones anteriores|ignore (all )?previous instructions|"
    r"revela (el )?prompt (del )?sistema|reveal (the )?system prompt|"
    r"actúa como (el )?sistema|you are now the system)"
)
HEADING = re.compile(r"^(?:\d+(?:\.\d+)*[.)]?\s+|(?:art[íi]culo|numeral|anexo|cap[íi]tulo|secci[óo]n)\s+[\w.-]+[:.]?\s+).{3,120}$", re.I)


@dataclass(frozen=True)
class SourceMetadata:
    """Estos datos deben provenir de la carga autenticada, nunca de un PDF."""

    nog: str
    document_key: str
    tipo_documento: str
    titulo: str
    entidad: str
    fecha_publicacion: str
    url_origen: str
    tenant_id: str | None = None
    visibilidad: str = "publica"

    def validate(self) -> None:
        if not re.fullmatch(r"\d{1,20}", self.nog):
            raise ValueError("NOG debe contener entre 1 y 20 dígitos")
        if not re.fullmatch(r"[a-zA-Z0-9_-]{1,80}", self.document_key):
            raise ValueError("document_key admite letras, números, guion y guion bajo")
        if self.tipo_documento not in KINDS:
            raise ValueError(f"tipo_documento debe ser uno de: {', '.join(sorted(KINDS))}")
        if self.visibilidad not in {"publica", "privada"}:
            raise ValueError("visibilidad debe ser publica o privada")
        if self.visibilidad == "privada" and not self.tenant_id:
            raise ValueError("Los documentos privados requieren tenant_id")
        if self.visibilidad == "publica" and self.tenant_id:
            raise ValueError("Los documentos públicos no deben tener tenant_id")
        if self.tenant_id and not re.fullmatch(r"[a-zA-Z0-9_-]{1,80}", self.tenant_id):
            raise ValueError("tenant_id inválido")
        if not self.titulo.strip() or not self.entidad.strip():
            raise ValueError("titulo y entidad son obligatorios")
        date.fromisoformat(self.fecha_publicacion)
        parsed_url = urlparse(self.url_origen)
        if parsed_url.scheme != "https" or not parsed_url.hostname or not (
            parsed_url.hostname == "guatecompras.gt" or parsed_url.hostname.endswith(".guatecompras.gt")
        ):
            raise ValueError("url_origen debe ser una URL HTTPS de GUATECOMPRAS")


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


def make_chunks(pages: list[Page], doc_id: str, metadata: SourceMetadata, version: int,
                max_words: int = 600, overlap_words: int = 90) -> list[dict[str, Any]]:
    """~800 tokens / 120 de solapamiento estimados por palabras; una página por chunk."""
    if max_words < 1 or not 0 <= overlap_words < max_words:
        raise ValueError("Parámetros de segmentación inválidos")
    chunks = []
    section = "Sin sección"
    for page in pages:
        if page.quality != "ok":
            continue
        units, section = _units(page, section)
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
                chunks.append({
                    "chunk_id": f"{doc_id}:{index:05d}", "doc_id": doc_id,
                    "nog": metadata.nog, "tenant_id": metadata.tenant_id,
                    "visibilidad": metadata.visibilidad, "tipo_documento": metadata.tipo_documento,
                    "document_key": metadata.document_key, "version": version,
                    "titulo": metadata.titulo, "entidad": metadata.entidad,
                    "fecha_publicacion": metadata.fecha_publicacion, "url_origen": metadata.url_origen,
                    "pagina_inicio": page.number, "pagina_fin": page.number,
                    "seccion": unit["seccion"], "tipo_chunk": unit["tipo_chunk"],
                    "tabla_markdown": unit["tabla_markdown"] if len(words) <= max_words else None,
                    "texto": text, "metodo_extraccion": page.method,
                    "injection_suspected": bool(SUSPICIOUS.search(text)),
                    "indexable": not bool(SUSPICIOUS.search(text)),
                })
                if start + max_words >= len(words):
                    break
    return chunks


class IngestionService:
    def __init__(self, data_dir: Path, store=None):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.store = store or store_from_environment(self.data_dir)
        self.database = self.data_dir / "ingesta.sqlite3"
        with closing(sqlite3.connect(self.database)) as connection, connection:
            connection.execute("""CREATE TABLE IF NOT EXISTS documents (
                doc_id TEXT PRIMARY KEY, scope TEXT NOT NULL, nog TEXT NOT NULL,
                document_key TEXT NOT NULL, version INTEGER NOT NULL, sha256 TEXT NOT NULL,
                object_uri TEXT NOT NULL, manifest_path TEXT NOT NULL, status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(scope, nog, document_key, version),
                UNIQUE(scope, nog, document_key, sha256)
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
        scope = metadata.tenant_id if metadata.visibilidad == "privada" else "__publico__"
        with closing(sqlite3.connect(self.database)) as connection, connection:
            row = connection.execute(
                "SELECT manifest_path FROM documents WHERE scope=? AND nog=? AND document_key=? AND sha256=?",
                (scope, metadata.nog, metadata.document_key, digest),
            ).fetchone()
            if row:
                return json.loads(Path(row[0]).read_text(encoding="utf-8"))

        pages = extract_pages(path, use_ocr=use_ocr)
        with closing(sqlite3.connect(self.database, timeout=30)) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT manifest_path FROM documents WHERE scope=? AND nog=? AND document_key=? AND sha256=?",
                (scope, metadata.nog, metadata.document_key, digest),
            ).fetchone()
            if row:
                return json.loads(Path(row[0]).read_text(encoding="utf-8"))
            version = connection.execute(
                "SELECT COALESCE(MAX(version), 0) + 1 FROM documents WHERE scope=? AND nog=? AND document_key=?",
                (scope, metadata.nog, metadata.document_key),
            ).fetchone()[0]
            previous = connection.execute(
                "SELECT doc_id FROM documents WHERE scope=? AND nog=? AND document_key=? ORDER BY version DESC LIMIT 1",
                (scope, metadata.nog, metadata.document_key),
            ).fetchone()
            doc_id = uuid.uuid4().hex
            key = f"{scope}/{metadata.nog}/{metadata.document_key}/v{version}/{doc_id}.pdf"
            object_uri = self.store.put(path, key)
            chunks = make_chunks(pages, doc_id, metadata, version)
            for chunk in chunks:
                chunk["hash_sha256"] = digest
            status = "completo" if all(page.quality == "ok" for page in pages) and all(c["indexable"] for c in chunks) else "requiere_revision"
            manifest = {
                "doc_id": doc_id, "hash_sha256": digest, "version": version,
                "previous_doc_id": previous[0] if previous else None,
                "object_uri": object_uri, "status": status,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "metadata": asdict(metadata), "pages": [asdict(page) for page in pages],
                "chunks": chunks,
            }
            manifest_dir = self.data_dir / "manifiestos"
            manifest_dir.mkdir(exist_ok=True)
            manifest_path = manifest_dir / f"{doc_id}.json"
            with manifest_path.open("x", encoding="utf-8") as stream:
                json.dump(manifest, stream, ensure_ascii=False, indent=2)
            os.chmod(manifest_path, 0o600)
            connection.execute(
                "INSERT INTO documents VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (doc_id, scope, metadata.nog, metadata.document_key, version, digest, object_uri,
                 str(manifest_path.resolve()), status, manifest["created_at"]),
            )
        return manifest
