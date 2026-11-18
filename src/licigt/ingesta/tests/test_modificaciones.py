import json
import os
import unittest
import zipfile
from pathlib import Path

from licigt.ingesta.pdf import Page
from licigt.ingesta.pipeline import _without_repeated_margins, make_chunks
from licigt.ingesta.tests.test_pipeline import metadata

RAIZ = Path(__file__).resolve().parents[4]
ZIP_ACTUAL = Path(os.environ.get("LICIGT_ZIP_CORPUS") or RAIZ / "entregables" / "recuperacion" / "empresa_demo.zip")
ENCABEZADO = ("Instituto Guatemalteco de Seguridad Social\n"
              "Documentos de Licitación DA No. 222-IGSS-2023\n"
              "Departamento de Abastecimientos\n")
PUNTOS = (
    "Se emite la siguiente modificación:\n\n"
    "Punto 1:\nSe modifica el subnumeral 2.2 CRONOGRAMA DE ACTIVIDADES, de acuerdo a lo siguiente:\n"
    "Hasta el 06 de octubre de 2023.\n\n"
    "Punto 2:\nSe modifica la literal e) del subnumeral 2.7 LISTADO DE DOCUMENTOS QUE DEBERÁ\n"
    "CONTENER LA PLICA de los Documentos de Licitación, de acuerdo a lo siguiente:\n"
    "e) Solvencia Patronal con el pago operado al 31 de julio de 2023.\n\n"
    "PUNTO 3: Se aclara lo demás sin nombrar ningún numeral.\nTexto final."
)


def chunks_de(texto: str, tipo: str = "modificacion"):
    return make_chunks([Page(1, texto, "text", "ok")], "d" * 32, metadata(tipo_documento=tipo), 1)


class PuntosDeUnaModificacionTests(unittest.TestCase):
    def test_cada_punto_abre_una_unidad_con_el_numeral_que_nombra(self):
        chunks = chunks_de(PUNTOS)
        por_texto = {("Solvencia Patronal" in c["texto"], "06 de octubre" in c["texto"]): c for c in chunks}
        self.assertEqual(por_texto[(False, True)]["seccion"], "2.2 CRONOGRAMA DE ACTIVIDADES")
        self.assertEqual(por_texto[(True, False)]["seccion"], "2.7 LISTADO DE DOCUMENTOS QUE DEBERÁ CONTENER LA PLICA")

    def test_el_texto_no_cambia(self):
        chunks = chunks_de(PUNTOS)
        self.assertEqual(" ".join(" ".join(c["texto"] for c in chunks).split()), " ".join(PUNTOS.split()))

    def test_el_punto_sin_numeral_no_abre_unidad_nueva(self):
        chunks = chunks_de(PUNTOS)
        ultimo = chunks[-1]
        self.assertIn("PUNTO 3:", ultimo["texto"])
        self.assertTrue(ultimo["seccion"].startswith("2.7"))

    def test_solo_aplica_a_modificaciones_y_aclaraciones(self):
        self.assertEqual({c["seccion"] for c in chunks_de(PUNTOS, "bases")}, {"Sin sección"})
        self.assertTrue(any(c["seccion"].startswith("2.7") for c in chunks_de(PUNTOS, "aclaracion")))

    def test_punto_y_numeral_en_la_misma_linea(self):
        chunks = chunks_de("Intro.\n\nPunto 4: Se modifica el numeral 3.1 PLAZO DE ENTREGA de los Documentos.\nNuevo plazo.")
        self.assertEqual(chunks[-1]["seccion"], "3.1 PLAZO DE ENTREGA")


class MargenesRepetidosTests(unittest.TestCase):
    def paginas(self, n=4, repetir=(0, 1)):
        return [Page(i + 1, (ENCABEZADO if i in repetir else "") + f"Cuerpo distinto {i} de la página.\n"
                     + "Más texto propio de la página %d con contenido suficiente." % i, "text", "ok")
                for i in range(n)]

    def test_encabezado_de_tres_lineas_en_dos_paginas_de_un_documento_de_cuatro(self):
        limpias = _without_repeated_margins(self.paginas())
        for pagina in limpias:
            self.assertNotIn("Instituto Guatemalteco", pagina.text)
            self.assertNotIn("Departamento de Abastecimientos", pagina.text)
        self.assertIn("Cuerpo distinto 0", limpias[0].text)

    def test_el_texto_original_de_las_paginas_se_conserva(self):
        paginas = self.paginas()
        _without_repeated_margins(paginas)
        self.assertIn("Instituto Guatemalteco", paginas[0].text)
        chunks = make_chunks(paginas, "d" * 32, metadata(), 1)
        self.assertFalse([c for c in chunks if "Instituto Guatemalteco" in c["texto"]])

    def test_la_pagina_sin_capa_de_texto_no_cuenta(self):
        paginas = self.paginas(3, repetir=(0,))
        paginas[1] = Page(2, "", "text", "incompleta")
        paginas[2] = Page(3, "Otro cuerpo " * 5, "text", "ok")
        self.assertIn("Instituto Guatemalteco", _without_repeated_margins(paginas)[0].text)

    def test_la_pagina_de_ocr_tampoco_cuenta(self):
        paginas = self.paginas(4, repetir=(0, 2))
        paginas[2] = Page(3, paginas[2].text, "ocr", "ok")
        self.assertIn("Instituto Guatemalteco", _without_repeated_margins(paginas)[0].text)
        self.assertIn("Instituto Guatemalteco", _without_repeated_margins(paginas)[2].text)

    def test_una_linea_con_numeral_de_seccion_nunca_se_quita(self):
        paginas = [Page(i, "2.1 DOCUMENTOS DE LICITACIÓN\nCuerpo %d con texto suficiente para la prueba." % i, "text", "ok")
                   for i in (1, 2, 3)]
        self.assertTrue(all("2.1 DOCUMENTOS" in p.text for p in _without_repeated_margins(paginas)))

    def test_los_documentos_largos_conservan_su_regla(self):
        paginas = [Page(i, ("Encabezado largo\n" if i < 3 else "") + "Cuerpo %d con texto suficiente para la prueba." % i,
                        "text", "ok") for i in range(1, 9)]
        self.assertIn("Encabezado largo", _without_repeated_margins(paginas)[0].text)


@unittest.skipUnless(ZIP_ACTUAL.is_file(), "requiere el paquete del corpus")
class ModificacionDelCorpusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with zipfile.ZipFile(ZIP_ACTUAL) as z:
            cls.chunks = [json.loads(l) for l in z.read("chunks.jsonl").splitlines() if l.strip()]
        cls.mod = [c for c in cls.chunks if c["doc_id"].startswith("d41480e5b0ce4c16bf18f66225ada2dc")]

    def test_la_solvencia_patronal_lleva_la_seccion_2_7(self):
        c = next(c for c in self.mod if "Solvencia Patronal" in c["texto"] and "31 de julio" in c["texto"])
        self.assertTrue(c["seccion"].startswith("2.7"), c["seccion"])

    def test_ningun_fragmento_de_la_modificacion_empieza_por_el_encabezado(self):
        self.assertTrue(self.mod)
        self.assertEqual([c["chunk_id"] for c in self.mod
                          if c["texto"].startswith("Instituto Guatemalteco de Seguridad Social\n")], [])

    # Desde R6 el membrete de la p3 (caso 20230031880, asunto, firma) queda como ruido_ocr porque las páginas OCR
    # no se funden; el NOG y el asunto están también en la p1 y en las bases. Es un límite declarado del OCR.
    def test_la_pagina_3_conserva_el_parrafo_de_la_aprobacion(self):
        p3 = [c for c in self.mod if c["pagina_inicio"] == 3]
        self.assertTrue(any("En fecha 14 de julio de 2023" in c["texto"] for c in p3))
        self.assertEqual([c for c in self.mod if c["pagina_inicio"] == 4], [])


if __name__ == "__main__":
    unittest.main()
