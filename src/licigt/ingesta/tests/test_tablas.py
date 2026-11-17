import json
import os
import re
import tempfile
import zipfile
import unittest
from collections import Counter
from pathlib import Path
from unittest.mock import patch

try:
    import pdfplumber  # noqa: F401
except ImportError:  # pragma: no cover
    pdfplumber = None

from licigt.ingesta import pdf
from licigt.ingesta.pdf import Page, extract_pages
from licigt.ingesta.pipeline import _units, make_chunks
from licigt.ingesta.tests.test_pipeline import metadata


RAIZ = Path(__file__).resolve().parents[4]
ZIP_ACTUAL = Path(os.environ.get("LICIGT_ZIP_CORPUS") or RAIZ / "entregables" / "recuperacion" / "empresa_demo.zip")


def _escapar(texto: str) -> str:
    return texto.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def pdf_sintetico(filas, anchos, *, encabezado=None, alto_linea=11, y0=700, libre=()) -> bytes:
    """PDF de una página con una tabla de bordes dibujados; cada celda es una lista de líneas."""
    ops, y = [], y0
    x = [50]
    for ancho in anchos:
        x.append(x[-1] + ancho)
    ops.append("BT /F1 12 Tf 50 740 Td (Bases de licitacion 222-IGSS-2023) Tj ET")
    if encabezado:
        ops.append(f"BT /F1 11 Tf 50 {y0 + 14} Td ({_escapar(encabezado)}) Tj ET")
    for fila in filas:
        alto = max(len(c) for c in fila) * alto_linea + 6
        ops.append(f"{x[0]} {y} m {x[-1]} {y} l S")
        ops.append(f"{x[0]} {y - alto} m {x[-1]} {y - alto} l S")
        for borde in x:
            ops.append(f"{borde} {y} m {borde} {y - alto} l S")
        for izquierda, celda in zip(x, fila):
            for k, linea in enumerate(celda):
                ops.append(f"BT /F1 9 Tf {izquierda + 4} {y - 12 - k * alto_linea} Td ({_escapar(linea)}) Tj ET")
        y -= alto
    for izquierda, arriba, linea in libre:  # texto suelto, sin respetar las columnas
        ops.append(f"BT /F1 9 Tf {izquierda} {arriba} Td ({_escapar(linea)}) Tj ET")
    flujo = "\n".join(ops).encode("latin-1")
    objetos = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length %d >>\nstream\n" % len(flujo) + flujo + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
    ]
    salida, posiciones = bytearray(b"%PDF-1.4\n"), []
    for numero, cuerpo in enumerate(objetos, 1):
        posiciones.append(len(salida))
        salida += b"%d 0 obj\n" % numero + cuerpo + b"\nendobj\n"
    inicio = len(salida)
    salida += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objetos) + 1)
    for pos in posiciones:
        salida += b"%010d 00000 n \n" % pos
    salida += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objetos) + 1, inicio)
    return bytes(salida)


CRONOGRAMA = [
    [["2.2.1"], ["Recepcion de ofertas"],
     ["Hasta el dia 31 de julio de 2023, a las 10:00 horas, en la sede", "central del Instituto, 7a. avenida 22-72 zona 1."]],
    [["2.2.2"], ["Induccion a interesados"],
     ["El dia 19 de julio de 2023, a las 10:00 horas. La induccion se", "impartira de forma virtual por correo electronico."]],
    [["2.2.3"], ["Plazo para adjudicar"],
     ["Hasta diez (10) dias habiles contados a partir de la fecha de", "recepcion de las ofertas, segun el numeral 2.2.1 de estas bases."]],
]
CANTIDADES = [
    [["No."], ["Producto"], ["Cantidad"]],
    [["1"], ["Acetaminofen 500 mg"], ["400 unidades"]],
    [["2"], ["Ibuprofeno 400 mg"], ["1200 unidades"]],
]


VIGENCIA = [
    "VIGENCIA DEL CONTRATO",
    "La vigencia del CONTRATO sera a partir del dia siguiente de la notificacion de la",
    "Resolucion de aprobacion del CONTRATO, hasta que el INSTITUTO a traves de cada",
    "UNIDAD SOLICITANTE extienda la constancia de haber recibido a satisfaccion la",
    "totalidad de lo contratado en la presente negociacion.",
]


def pdf_vigencia() -> bytes:
    """Párrafo numerado sangrado cuyos bordes de columna caen en medio de las líneas."""
    libre = [(125, 700 - 12 - k * 11, linea) for k, linea in enumerate(VIGENCIA)]
    return pdf_sintetico([[["2.25", "", "", "", ""], [], [], []]], [75, 240, 15, 170], libre=libre)


def extraer(contenido: bytes) -> Page:
    with tempfile.TemporaryDirectory() as temporal:
        ruta = Path(temporal) / "t.pdf"
        ruta.write_bytes(contenido)
        return extract_pages(ruta, use_ocr=False)[0]


def digitos(texto: str) -> Counter:
    return Counter(re.findall(r"\d+", texto))


@unittest.skipIf(pdfplumber is None, "pdfplumber no está instalado")
class TablasDeDescripcionTests(unittest.TestCase):
    def setUp(self):
        self.contenido = pdf_sintetico(CRONOGRAMA, [45, 120, 345], encabezado="2.2 CRONOGRAMA DE ACTIVIDADES")

    def actual(self) -> Page:
        with patch.object(pdf, "_con_tablas", return_value=None):
            return extraer(self.contenido)

    def test_tabla_de_tres_columnas_sale_con_sus_filas_unidas(self):
        texto = extraer(self.contenido).text
        self.assertIn("2.2 CRONOGRAMA DE ACTIVIDADES", texto)
        filas = [linea for linea in texto.splitlines() if linea.startswith("|")]
        self.assertEqual(len(filas), 3)
        self.assertEqual(
            filas[0],
            "| 2.2.1 | Recepcion de ofertas | Hasta el dia 31 de julio de 2023, a las 10:00 horas, en la sede "
            "central del Instituto, 7a. avenida 22-72 zona 1. |")
        self.assertTrue(filas[2].startswith("| 2.2.3 | Plazo para adjudicar | Hasta diez (10) dias habiles"))
        self.assertNotIn("   ", texto.split("2.2.1", 1)[1])

    def test_el_texto_fuera_de_la_tabla_no_cambia(self):
        self.assertIn("Bases de licitacion 222-IGSS-2023", extraer(self.contenido).text)

    def test_no_se_pierde_ni_se_anade_ningun_digito(self):
        self.assertEqual(digitos(extraer(self.contenido).text), digitos(self.actual().text))

    def test_la_salvaguarda_devuelve_el_texto_actual_si_una_palabra_no_coincide(self):
        original = pdf._render_filas
        with patch.object(pdf, "_render_filas", side_effect=lambda f: original(f).replace("Induccion", "")):
            self.assertEqual(extraer(self.contenido).text, self.actual().text)

    def test_un_cuadro_de_cantidades_no_cambia(self):
        contenido = pdf_sintetico(CANTIDADES, [45, 220, 240])
        with patch.object(pdf, "_con_tablas", return_value=None):
            esperado = extraer(contenido).text
        self.assertEqual(extraer(contenido).text, esperado)
        self.assertNotIn("| ", extraer(contenido).text)

    def test_sin_pdfplumber_se_conserva_el_texto_actual(self):
        with patch.object(pdf, "pdfplumber", None):
            self.assertEqual(extraer(self.contenido).text, self.actual().text)


@unittest.skipIf(pdfplumber is None, "pdfplumber no está instalado")
class OrdenEnTablasTests(unittest.TestCase):
    def test_un_parrafo_numerado_sangrado_conserva_el_orden_de_sus_palabras(self):
        texto = " ".join(extraer(pdf_vigencia()).text.split())
        self.assertIn("a partir del dia siguiente de la notificacion de la Resolucion de aprobacion", texto)
        self.assertIn("hasta que el INSTITUTO a traves de cada UNIDAD SOLICITANTE extienda", texto)

    def test_ese_parrafo_no_se_reescribe_como_tabla(self):
        self.assertNotIn("|", extraer(pdf_vigencia()).text)

    def test_la_salvaguarda_compara_el_orden_de_las_palabras_de_cada_celda(self):
        self.assertFalse(pdf._en_orden("uno tres dos cuatro", "2.25 uno dos tres cuatro"))
        self.assertTrue(pdf._en_orden("uno tres cuatro", "2.25 uno dos tres cuatro"))

    def test_una_celda_con_las_palabras_trocadas_devuelve_el_texto_actual(self):
        contenido = pdf_sintetico(CRONOGRAMA, [45, 120, 345])
        original = pdf._filas_por_palabras

        def trocadas(tabla, palabras):
            filas = original(tabla, palabras)
            for fila in filas or []:
                fila[2] = fila[2].replace("Hasta el dia 31", "el Hasta dia 31")
            return filas

        with patch.object(pdf, "_filas_por_palabras", side_effect=trocadas):
            texto = extraer(contenido).text
        with patch.object(pdf, "_con_tablas", return_value=None):
            self.assertEqual(texto, extraer(contenido).text)

    def test_ningun_digito_cambia_en_el_parrafo(self):
        contenido = pdf_vigencia()
        with patch.object(pdf, "_con_tablas", return_value=None):
            actual = extraer(contenido).text
        self.assertEqual(digitos(extraer(contenido).text), digitos(actual))


@unittest.skipUnless(ZIP_ACTUAL.is_file(), "requiere el paquete del corpus")
class VigenciaEnElCorpusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with zipfile.ZipFile(ZIP_ACTUAL) as z:
            cls.chunks = [json.loads(l) for l in z.read("chunks.jsonl").splitlines() if l.strip()]

    def test_el_2_25_de_los_cinco_eventos_conserva_el_orden_del_original(self):
        vigencias = [c for c in self.chunks if "VIGENCIA DEL CONTRATO" in c["texto"] and "2.25" in c["texto"][:12]]
        self.assertEqual(len({c["evento_id"] for c in vigencias}), 5)
        for c in vigencias:
            self.assertIn("día siguiente de la notificación de la Resolución", " ".join(c["texto"].split()), c["chunk_id"])
            self.assertNotIn("|", c["texto"], c["chunk_id"])

    def test_el_cronograma_sigue_con_sus_filas_unidas(self):
        por_evento = {}
        for c in self.chunks:
            if c["tipo_chunk"] == "tabla" and re.search(r"^\| 2\.2\.\d+ \| .+ \|$", c["texto"], re.M):
                por_evento.setdefault(c["evento_id"], []).append(c)
        self.assertEqual(len(por_evento), 5)
        for evento, tablas in por_evento.items():
            filas = [l for c in tablas for l in c["texto"].splitlines() if l.startswith("| 2.2.")]
            self.assertGreaterEqual(len(filas), 5, evento)


class UnidadesDeTablaTests(unittest.TestCase):
    TEXTO = (
        "2.2 CRONOGRAMA DE ACTIVIDADES\n"
        "| 2.2.1 | Recepcion de ofertas | Hasta el 31 de julio de 2023. |\n"
        "| 2.2.2 | Induccion | El 19 de julio de 2023. |\n"
        "\n"
        "Texto posterior de la pagina."
    )

    def test_una_tabla_de_descripcion_forma_una_unidad_con_su_encabezado_como_seccion(self):
        unidades, seccion = _units(Page(1, self.TEXTO, "text", "ok"), "Sin sección")
        tablas = [u for u in unidades if u["tipo_chunk"] == "tabla"]
        self.assertEqual(len(tablas), 1)
        self.assertEqual(tablas[0]["seccion"], "2.2 CRONOGRAMA DE ACTIVIDADES")
        self.assertIn("| 2.2.2 | Induccion | El 19 de julio de 2023. |", tablas[0]["texto"])
        self.assertIsNotNone(tablas[0]["tabla_markdown"])
        self.assertIn("| --- | --- | --- |", tablas[0]["tabla_markdown"])
        self.assertEqual(seccion, "2.2 CRONOGRAMA DE ACTIVIDADES")

    def test_la_tabla_que_continua_en_otra_pagina_conserva_la_seccion(self):
        pagina = Page(2, "| 2.2.8 | Plazo para adjudicar | Hasta diez dias. |", "text", "ok")
        unidades, _ = _units(pagina, "2.2 CRONOGRAMA DE ACTIVIDADES")
        self.assertEqual(unidades[0]["seccion"], "2.2 CRONOGRAMA DE ACTIVIDADES")
        self.assertEqual(unidades[0]["tipo_chunk"], "tabla")

    def test_una_tabla_larga_se_corta_por_filas_y_conserva_cada_numeral(self):
        filas = [f"| 2.2.{n} | Titulo {n} | " + " ".join(f"palabra{n}x{k}" for k in range(40)) + " |"
                 for n in range(1, 31)]
        pagina = Page(1, "2.2 CRONOGRAMA\n" + "\n".join(filas), "text", "ok")
        chunks = make_chunks([pagina], "d" * 32, metadata(), 1)
        tablas = [c for c in chunks if c["tipo_chunk"] == "tabla"]
        self.assertGreater(len(tablas), 1)
        todas = [linea for c in tablas for linea in c["texto"].splitlines() if linea.startswith("|")]
        self.assertEqual(sorted(todas), sorted(filas))
        self.assertTrue(all(c["seccion"] == "2.2 CRONOGRAMA" for c in tablas))


if __name__ == "__main__":
    unittest.main()
