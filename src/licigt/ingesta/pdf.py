"""Extracción por página con Poppler y OCR opcional mediante Tesseract."""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from xml.etree import ElementTree


@dataclass
class Page:
    number: int
    text: str
    method: str
    quality: str
    warnings: list[str] = field(default_factory=list)


def _run(args: list[str], timeout: int = 120) -> str:
    try:
        result = subprocess.run(args, capture_output=True, check=True, timeout=timeout)
    except FileNotFoundError as exc:
        raise RuntimeError(f"Falta la herramienta {args[0]}; instala poppler-utils") from exc
    except subprocess.CalledProcessError as exc:
        raise ValueError(f"No se pudo leer el PDF: {exc.stderr.decode('utf-8', 'replace')[:300]}") from exc
    except subprocess.TimeoutExpired as exc:
        raise TimeoutError(f"Tiempo agotado al ejecutar {args[0]}") from exc
    return result.stdout.decode("utf-8", "replace")


def normalize_text(text: str) -> str:
    """Limpia ruido visual sin alterar fechas, códigos ni cifras."""
    text = unicodedata.normalize("NFC", text)
    text = "".join(c for c in text if c in "\n\t" or unicodedata.category(c) != "Cc")
    return "\n".join(re.sub(r"[ \t]+$", "", line) for line in text.splitlines()).strip()


def extract_hidden_text(path: Path) -> dict[int, list[str]]:
    """Compara texto visible y total de Poppler por página para revisar capas ocultas."""
    def text_by_page(include_hidden: bool) -> dict[int, Counter[str]]:
        command = ["pdftohtml", "-xml", "-i", "-stdout"]
        if include_hidden:
            command.append("-hidden")
        command.append(str(path))
        xml = _run(command, timeout=180)
        root = ElementTree.fromstring(xml)
        return {
            int(page.attrib["number"]): Counter(
                normalized for node in page.findall("text")
                if (normalized := " ".join("".join(node.itertext()).split()))
            )
            for page in root.findall("page")
        }

    visible = text_by_page(False)
    complete = text_by_page(True)
    return {
        number: list((complete[number] - visible.get(number, Counter())).elements())
        for number in complete
        if complete[number] - visible.get(number, Counter())
    }


def _ocr_page(path: Path, number: int) -> str | None:
    if not shutil.which("tesseract"):
        return None
    with tempfile.TemporaryDirectory() as temporary:
        prefix = str(Path(temporary) / "page")
        _run(["pdftoppm", "-f", str(number), "-l", str(number), "-singlefile", "-r", "200", "-png", str(path), prefix])
        try:
            return normalize_text(_run(["tesseract", prefix + ".png", "stdout", "-l", "spa"]))
        except ValueError:
            return None


def extract_pages(path: Path, max_pages: int = 300, min_chars: int = 30, use_ocr: bool = True) -> list[Page]:
    info = _run(["pdfinfo", str(path)])
    found = re.search(r"^Pages:\s+(\d+)$", info, re.MULTILINE)
    if not found:
        raise ValueError("pdfinfo no informó el número de páginas")
    count = int(found.group(1))
    if count < 1 or count > max_pages:
        raise ValueError(f"El PDF tiene {count} páginas; el límite es {max_pages}")
    raw = _run(["pdftotext", "-layout", "-enc", "UTF-8", str(path), "-"], timeout=max(120, count * 3))
    page_texts = raw.split("\f")
    if page_texts and not page_texts[-1].strip():
        page_texts.pop()
    if len(page_texts) != count:
        raise ValueError(f"Se esperaban {count} páginas, pero se extrajeron {len(page_texts)}")
    pages = []
    for number, raw_text in enumerate(page_texts, 1):
        text = normalize_text(raw_text)
        method = "text"
        warnings = []
        if len(text) < min_chars and use_ocr:
            ocr_text = _ocr_page(path, number)
            if ocr_text and len(ocr_text) > len(text):
                text, method = ocr_text, "ocr"
            elif ocr_text is None:
                warnings.append("OCR no disponible: instala Tesseract y el idioma spa")
        quality = "ok" if len(text) >= min_chars else "incompleta"
        if quality != "ok":
            warnings.append("Página sin texto suficiente; requiere revisión manual")
        pages.append(Page(number, text, method, quality, warnings))
    return pages
