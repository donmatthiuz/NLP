"""Reconstruye el paquete del corpus del IGSS con los mismos doc_id y chunk_id, desde corpus_igss.json."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from urllib.parse import urlparse

from . import prepare_corpus
from .automatic import OfficialFetcher, official_url
from .download import PDF_LIMIT
from .handoff import export
from .pipeline import AVISO_MODIFICACION
from .prepare_corpus import CORPUS, cargar_especificacion
from .reextraer import reextraer

AVISOS_AUTOMATICOS = (
    "Hay páginas incompletas o ilegibles", "Posibles instrucciones incrustadas en páginas: ",
    "No se encontró el número de evento", "El archivo parece ser solo una convocatoria",
    "El NOG declarado difiere", "No se pudo revisar el texto oculto",
    "El documento relacionado aún no está cargado", AVISO_MODIFICACION,
)


def generar_especificacion(zip_path: Path) -> dict:
    """Deriva la especificación del inventario y los manifiestos de un paquete; se corre una sola vez."""
    with zipfile.ZipFile(zip_path) as archivo:
        inventario = json.loads(archivo.read("inventario.json"))
        documentos = []
        for entrada in inventario["documents"]:
            manifiesto = json.loads(archivo.read(entrada["manifiesto_zip_path"]))
            if not entrada["procedencia_zip_path"]:
                raise ValueError(f"Sin JSON de descarga para {entrada['doc_id']}")
            procedencia = json.loads(archivo.read(entrada["procedencia_zip_path"]))
            procedencia.pop("original_zip_path", None)
            procedencia.pop("archivo", None)
            documentos.append({
                "numero_evento": entrada["numero_evento"], "evento_id": entrada["evento_id"],
                "tenant_id": inventario["tenant_id"], "document_key": entrada["document_key"],
                "tipo_documento": entrada["tipo_documento"],
                "version_oficial": entrada["identificador_version_oficial"],
                "relacion_documental": entrada["relacion_documental"],
                "url_origen": entrada["url_origen"], "sha256": entrada["sha256"],
                "doc_id": entrada["doc_id"], "version_ingesta": entrada["version_ingesta"],
                "ingested_at": manifiesto["created_at"],
                "paginas_ocr": entrada["paginas_no_indexadas"],
                "advertencias_humanas": [w for w in entrada["warnings"]
                                         if not w.startswith(AVISOS_AUTOMATICOS)],
                "procedencia": procedencia,
            })
    # El orden de ingesta importa dentro de un evento (bases antes de su modificación).
    documentos.sort(key=lambda d: d["ingested_at"])
    return {"schema_version": 1, "tenant_id": inventario["tenant_id"], "documentos": documentos}


def originales_desde_zip(zip_path: Path, spec: dict) -> dict[str, bytes]:
    """Originales del paquete, por SHA-256, sin red."""
    with zipfile.ZipFile(zip_path) as archivo:
        inventario = json.loads(archivo.read("inventario.json"))
        pedidos = {d["sha256"] for d in spec["documentos"]}
        return {e["sha256"]: archivo.read(e["original_zip_path"])
                for e in inventario["documents"] if e["sha256"] in pedidos}


def descargar_originales(spec: dict, fetcher=None) -> dict[str, bytes]:
    """Baja cada url_origen; solo igssgt.org, también tras redirecciones (lo impone OfficialFetcher)."""
    urls = [d["url_origen"] for d in spec["documentos"]]
    for url in urls:
        if not official_url(url) or not urlparse(url).path.lower().endswith(".pdf"):
            raise ValueError(f"Solo se descargan PDF HTTPS de igssgt.org: {url}")
    fetcher = fetcher or OfficialFetcher()
    obtenidos = {}
    for url in urls:
        contenido, final = fetcher.get(url, PDF_LIMIT)
        if not official_url(final):
            raise ValueError(f"La descarga terminó fuera de igssgt.org: {final}")
        obtenidos[hashlib.sha256(contenido).hexdigest()] = contenido
    return obtenidos


def tesseract_con_spa() -> bool:
    try:
        salida = subprocess.run(["tesseract", "--list-langs"], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return False
    return "spa" in ((salida.stdout or "") + (salida.stderr or "")).split()


def version_tesseract() -> str | None:
    try:
        salida = subprocess.run(["tesseract", "--version"], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    primera = ((salida.stdout or "") + (salida.stderr or "")).split()
    return primera[1] if len(primera) > 1 and primera[0] == "tesseract" else None


def reproducir(spec: dict, originales: dict[str, bytes], salida: Path, *, ocr: bool | None = None) -> dict:
    """Verifica todos los SHA-256 y, solo si coinciden, ingiere con ids fijos y exporta el ZIP."""
    for documento in spec["documentos"]:
        contenido = originales.get(documento["sha256"])
        if contenido is None or hashlib.sha256(contenido).hexdigest() != documento["sha256"]:
            raise ValueError(f"Falta el original o su SHA-256 no coincide con la especificación: "
                             f"{documento['numero_evento']} {documento['document_key']} {documento['sha256']}")
    salida = Path(salida).resolve()
    usar_ocr = tesseract_con_spa() if ocr is None else ocr
    avisos, aplicado = [], {}
    esperada = spec.get("ocr", {}).get("version")
    if usar_ocr and esperada and any(d["paginas_ocr"] for d in spec["documentos"]):
        instalada = version_tesseract()
        if instalada != esperada:
            avisos.append(f"Versión de Tesseract distinta: la especificación se generó con {esperada} "
                          f"y hay {instalada}; el texto OCR y los chunk_id nuevos pueden diferir")
    with tempfile.TemporaryDirectory() as temporal:
        data = Path(temporal) / "data"
        for documento in spec["documentos"]:
            carpeta = data / "descargas_igss" / documento["numero_evento"]
            carpeta.mkdir(parents=True, exist_ok=True)
            (carpeta / f"{documento['sha256']}.pdf").write_bytes(originales[documento["sha256"]])
            (carpeta / f"{documento['sha256']}.json").write_text(
                json.dumps({**documento["procedencia"], "archivo": f"{documento['sha256']}.pdf"},
                           ensure_ascii=False, indent=2), encoding="utf-8")
        prepare_corpus.prepare(data, spec=spec)
        paquete = Path(temporal) / "paquete.zip"
        inventario = export(data, spec["tenant_id"], paquete)
        for documento in spec["documentos"]:
            if not documento["paginas_ocr"]:
                continue
            if not usar_ocr:
                avisos.append(f"Sin Tesseract con idioma spa: {documento['numero_evento']} "
                              f"{documento['document_key']} conserva las páginas {documento['paginas_ocr']} "
                              "como ilegibles")
                continue
            resultado = reextraer(paquete, documento["doc_id"], paquete, documento["advertencias_humanas"])
            if resultado["paginas_recuperadas"]:
                aplicado[documento["doc_id"]] = resultado["paginas_recuperadas"]
            else:
                avisos.append(f"El OCR no recuperó páginas de {documento['doc_id']}")
        salida.parent.mkdir(parents=True, exist_ok=True)
        fd, intermedio = tempfile.mkstemp(prefix=".corpus_", suffix=".zip", dir=salida.parent)
        os.close(fd)
        try:
            shutil.copyfile(paquete, intermedio)
            os.chmod(intermedio, 0o600)
            os.replace(intermedio, salida)
        finally:
            if os.path.exists(intermedio):
                os.unlink(intermedio)
        if aplicado:
            inventario = json.loads(zipfile.ZipFile(salida).read("inventario.json"))
    return {"salida": salida.as_posix(), "documentos": len(inventario["documents"]),
            "chunks_indexables": inventario["chunks_indexables"], "avisos": avisos, "ocr": aplicado}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    fuente = parser.add_mutually_exclusive_group(required=True)
    fuente.add_argument("--desde-zip", type=Path, help="toma los originales de un paquete, sin red")
    fuente.add_argument("--descargar", action="store_true", help="baja cada url_origen del portal del IGSS")
    parser.add_argument("--salida", type=Path, required=True)
    parser.add_argument("--especificacion", type=Path, default=CORPUS)
    args = parser.parse_args()
    try:
        spec = cargar_especificacion(args.especificacion)
        originales = (originales_desde_zip(args.desde_zip, spec) if args.desde_zip
                      else descargar_originales(spec))
        resultado = reproducir(spec, originales, args.salida)
    except (ValueError, RuntimeError, OSError, KeyError, zipfile.BadZipFile) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    print(json.dumps(resultado, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
