"""Extracción por página con Poppler y OCR opcional mediante Tesseract."""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
import math
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from xml.etree import ElementTree

try:
    import pdfplumber
except ImportError:  # sin la dependencia se conserva el texto de pdftotext
    pdfplumber = None

EXTRACCION = {"metodo": "pdftotext-layout+tablas", "version": 2}
SEPARACION_CELDAS = 6.0  # pt; por debajo, el borde de columna cae en medio de una frase
CLAVE_FILA = re.compile(r"^(\d+(\.\d+)*[.)]?|[a-zñ](\.\d+)?\))$", re.I)


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


def _palabras(texto: str) -> Counter[str]:
    return Counter(w for w in (re.sub(r"[\W_]+", "", x) for x in texto.split()) if w)


def _agrupar(valores: list[float], tolerancia: float) -> list[float]:
    grupos: list[list[float]] = []
    for valor in sorted(valores):
        if grupos and valor - grupos[-1][-1] <= tolerancia:
            grupos[-1].append(valor)
        else:
            grupos.append([valor])
    return [sum(g) / len(g) for g in grupos]


def _rejilla(tabla) -> tuple[list[float], list[float]]:
    """Bordes verticales repetidos en al menos un tercio de las filas y límites de fila de la primera columna."""
    celdas = [c for fila in tabla.rows for c in fila.cells if c]
    conteo: Counter[int] = Counter()
    for c in celdas:
        conteo[round(c[0])] += 1
        conteo[round(c[2])] += 1
    minimo = max(2, len(tabla.rows) // 3)
    bordes = _agrupar([x for x, n in conteo.items() if n >= minimo] + [tabla.bbox[0], tabla.bbox[2]], 8)
    izquierda = min(c[0] for c in celdas)
    primeras = [c for c in celdas if c[0] <= izquierda + 8 and c[2] - c[0] >= 20]
    fuente = primeras if len(primeras) >= 2 else celdas
    return bordes, _agrupar([y for c in fuente for y in (c[1], c[3])], 3)


def _celdas_por_fila(tabla, palabras: list[dict]):
    """Palabras de cada celda por fila y, por fila, los grupos de columnas que un hueco menor que
    SEPARACION_CELDAS une en una sola celda (un borde que parte una celda de ancho completo)."""
    bordes, ys = _rejilla(tabla)
    if len(bordes) < 3:
        return None
    x0, y0, x1, y1 = tabla.bbox
    columnas = len(bordes) - 1
    celdas: dict[int, dict[int, list[dict]]] = {}
    for w in palabras:
        cx, cy = (w["x0"] + w["x1"]) / 2, (w["top"] + w["bottom"]) / 2
        if not (x0 - 2 <= cx <= x1 + 2 and y0 - 2 <= cy <= y1 + 2):
            continue
        columna = max(0, min(columnas - 1, sum(cx > e for e in bordes[1:-1])))
        fila = max(0, sum(cy > y for y in ys) - 1)
        celdas.setdefault(fila, {}).setdefault(columna, []).append(w)
    grupos: dict[int, dict[int, int]] = {}
    for fila, por_columna in celdas.items():
        lineas: dict[int, list[tuple[float, float, int]]] = {}
        for columna, ws in por_columna.items():
            for w in ws:
                lineas.setdefault(round((w["top"] + w["bottom"]) / 6), []).append((w["x0"], w["x1"], columna))
        destino = {c: c for c in por_columna}
        for linea in lineas.values():
            linea.sort()
            for a, b in zip(linea, linea[1:]):
                if a[2] != b[2] and b[0] - a[1] < SEPARACION_CELDAS:
                    viejo, nuevo = sorted((destino[a[2]], destino[b[2]]))[::-1]
                    for c, d in destino.items():
                        if d == viejo:
                            destino[c] = nuevo
        if any(c != d for c, d in destino.items()):
            grupos[fila] = destino
    return celdas, grupos, bordes


def _filas_por_palabras(tabla, palabras: list[dict]) -> list[dict[int, str]] | None:
    """Asigna cada palabra a su celda por el centro; una fila sin celda 0 continúa la anterior."""
    cuadricula = _celdas_por_fila(tabla, palabras)
    if cuadricula is None:
        return None
    celdas, grupos, _ = cuadricula
    filas: list[dict[int, str]] = []
    for fila in sorted(celdas):
        unidas: dict[int, list[dict]] = {}
        for columna, ws in celdas[fila].items():
            unidas.setdefault(grupos.get(fila, {}).get(columna, columna), []).extend(ws)
        textos = {}
        for columna, ws in unidas.items():
            ws.sort(key=lambda w: (round(w["top"] / 3), w["x0"]))
            textos[columna] = " ".join(w["text"] for w in ws)
        if 0 in textos or not filas:
            filas.append(textos)
        else:
            for columna, texto in textos.items():
                filas[-1][columna] = (filas[-1].get(columna, "") + " " + texto).strip()
    return filas


def _columnas_fundidas(tabla, palabras: list[dict]) -> dict[int, int]:
    """Columna donde empieza una celda fundida -> última columna que abarca en alguna fila."""
    cuadricula = _celdas_por_fila(tabla, palabras)
    alcance: dict[int, int] = {}
    for destino in (cuadricula[1].values() if cuadricula else ()):
        for columna, inicio in destino.items():
            alcance[inicio] = max(alcance.get(inicio, inicio), columna)
    return alcance


def _es_descripcion(filas: list[dict[int, str]]) -> bool:
    """Numeral o literal en la columna 0 y texto largo en la última celda; los cuadros de cantidades no."""
    con_clave = [f for f in filas if f.get(0, "").strip()]
    if not con_clave:
        return False
    claves = sum(bool(CLAVE_FILA.match(f[0].strip())) for f in con_clave) / len(con_clave)
    largos = sorted(max((len(v) for k, v in f.items() if k != 0), default=0) for f in con_clave)
    return claves >= 0.6 and largos[len(largos) // 2] >= 60


def _render_filas(filas: list[dict[int, str]]) -> str:
    """`| numeral | título | texto |`; una fila de una sola celda queda como línea de texto (el encabezado)."""
    salida = []
    for fila in filas:
        valores = [fila[c] for c in sorted(fila) if fila[c].strip()]
        if len(valores) == 1:
            salida.append(valores[0])
        elif valores:
            salida.append("| " + " | ".join(v.replace("|", "/") for v in valores) + " |")
    return "\n".join(salida)


def _region(path: Path, number: int, y: float, alto: float, ancho: float, x: float = 0) -> str:
    return _run(["pdftotext", "-layout", "-enc", "UTF-8", "-f", str(number), "-l", str(number),
                 "-x", str(int(x)), "-y", str(int(y)), "-W", str(int(ancho)), "-H", str(int(math.ceil(alto))), str(path), "-"])


def _lista_palabras(texto: str) -> list[str]:
    return [w for w in (re.sub(r"[\W_]+", "", x) for x in texto.split()) if w]


def _en_orden(celda: str, referencia: str) -> bool:
    """Las palabras de la celda aparecen en el mismo orden dentro de la referencia."""
    resto = iter(_lista_palabras(referencia))
    return all(any(w == r for r in resto) for w in _lista_palabras(celda))


def _separacion_minima(tabla, palabras: list[dict]) -> float:
    """Menor hueco entre dos palabras contiguas de una línea que caen en columnas distintas.

    Un borde de columna que parte una frase deja un hueco de espacio normal (2 a 5 pt); entre celdas
    reales hay relleno de varios puntos.
    """
    bordes, _ = _rejilla(tabla)
    x0, y0, x1, y1 = tabla.bbox
    lineas: dict[int, list[tuple[float, float, int]]] = {}
    for w in palabras:
        cx, cy = (w["x0"] + w["x1"]) / 2, (w["top"] + w["bottom"]) / 2
        if x0 - 2 <= cx <= x1 + 2 and y0 - 2 <= cy <= y1 + 2:
            lineas.setdefault(round(cy / 3), []).append((w["x0"], w["x1"], sum(cx > e for e in bordes[1:-1])))
    huecos = [b[0] - a[1] for linea in lineas.values() for a, b in zip(sorted(linea), sorted(linea)[1:])
              if a[2] != b[2]]
    return min(huecos, default=math.inf)


def _columnas_en_orden(path: Path, number: int, top: float, bot: float, filas: list[dict[int, str]],
                       bordes: list[float], fundidas: dict[int, int] | None = None) -> bool:
    """Las palabras de cada columna, de arriba abajo, siguen el orden del texto de su franja.

    La franja de una columna donde empieza una celda fundida llega hasta la última que esa celda abarca."""
    for columna in {c for f in filas for c in f}:
        celdas = " ".join(f[columna] for f in filas if columna in f)
        fin = (fundidas or {}).get(columna, columna)
        franja = _region(path, number, top - 1, bot - top + 3, bordes[fin + 1] - bordes[columna] + 4,
                         bordes[columna] - 2)
        if not _en_orden(celdas, franja):
            return False
    return True


def _sin_anidadas(usadas: list[tuple]) -> list[tuple]:
    """Descarta tablas cuyo bbox cae dentro de otra ya elegida."""
    elegidas: list[tuple] = []
    for u in sorted(usadas, key=lambda u: -(u[0][2] - u[0][0]) * (u[0][3] - u[0][1])):
        x0, y0, x1, y1 = u[0]
        if not any(x0 >= o[0][0] - 3 and x1 <= o[0][2] + 3 and y0 >= o[0][1] - 3 and y1 <= o[0][3] + 3
                   for o in elegidas):
            elegidas.append(u)
    return elegidas


def _con_tablas(pagina, path: Path, number: int, actual: str) -> str | None:
    """Texto de la página con sus tablas de descripción reescritas, o None si no hay ninguna que cambiar.

    Salvaguardas: cada tabla debe tener el mismo multiconjunto de palabras que el texto de su región y,
    en cada columna, sus palabras en el orden del texto de esa franja; una tabla de una fila exige además
    que sus columnas estén separadas por huecos reales. La página entera debe tener los mismos dígitos
    que el texto actual; si no, se conserva el actual.
    """
    palabras, usadas = None, []
    for tabla in pagina.find_tables():
        if palabras is None:
            palabras = pagina.extract_words(x_tolerance=1.5, y_tolerance=2)
        filas = _filas_por_palabras(tabla, palabras)
        if not filas:
            continue
        efectivas = max(len([v for v in f.values() if v.strip()]) for f in filas)
        una_fila = len(filas) == 1 and efectivas >= 3 and _separacion_minima(tabla, palabras) >= SEPARACION_CELDAS
        if (len(filas) >= 2 and efectivas >= 2 or una_fila) and _es_descripcion(filas):
            usadas.append((tabla.bbox, filas, _rejilla(tabla)[0], _columnas_fundidas(tabla, palabras)))
    if not usadas:
        return None
    usadas = sorted(_sin_anidadas(usadas), key=lambda u: u[0][1])
    partes, y, reescritas = [], 0.0, 0
    for (_, top, _, bot), filas, bordes, fundidas in usadas:
        if top - y > 1:
            partes.append(_region(path, number, y, top - y, pagina.width))
        texto = _render_filas(filas)
        referencia = _region(path, number, top - 1, bot - top + 3, pagina.width)
        if _palabras(texto) == _palabras(referencia) and _columnas_en_orden(path, number, top, bot, filas, bordes, fundidas):
            reescritas += 1
        else:
            texto = referencia
        partes.append(texto)
        y = bot
    if not reescritas:
        return None
    if pagina.height - y > 1:
        partes.append(_region(path, number, y, pagina.height - y, pagina.width))
    nuevo = normalize_text("\n\n".join(p.strip("\n") for p in partes if p.strip()))
    if Counter(re.findall(r"\d+", nuevo)) != Counter(re.findall(r"\d+", actual)):
        return None
    return nuevo


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
    plumber = None
    try:
        plumber = pdfplumber.open(path) if pdfplumber and len(page_texts) == count else None
    except Exception:  # un PDF que pdfplumber no abre sigue con el texto de pdftotext
        plumber = None
    for number, raw_text in enumerate(page_texts, 1):
        text = normalize_text(raw_text)
        method = "text"
        warnings = []
        if plumber is not None and len(text) >= min_chars:
            try:
                text = _con_tablas(plumber.pages[number - 1], path, number, text) or text
            except Exception:
                pass
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
    if plumber is not None:
        plumber.close()
    return pages
