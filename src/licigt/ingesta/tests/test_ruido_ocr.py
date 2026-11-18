import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from licigt.ingesta.pdf import Page
from licigt.ingesta.pipeline import IngestionService, SourceMetadata, make_chunks

BUENA = ("El oferente deberá presentar la garantía de sostenimiento de oferta equivalente al dos por ciento "
         "del monto ofertado, emitida por institución autorizada, con vigencia mínima de ciento veinte días "
         "calendario contados desde la recepción de ofertas, conforme a las bases de la licitación.")
SELLOS = "( AO $ ) firma sello 12 3 DIR GG\nJefe Rec"


def metadata():
    return SourceMetadata(
        tenant_id="empresa_demo", evento_id="evento_399", numero_evento="399-IGSS-2026",
        anio=2026, modalidad="Licitación Pública DA", document_key="bases_integradas",
        tipo_documento="bases", titulo="Prueba", url_origen="https://www.igssgt.org/doc.pdf")


def paginas():
    return [Page(1, "DOCUMENTOS DE LICITACIÓN 399-IGSS-2026\n" + BUENA, "text", "ok"),
            Page(2, SELLOS, "ocr", "ok"),
            Page(3, BUENA, "ocr", "ok")]


class RuidoOcrTests(unittest.TestCase):
    def _ingerir(self, root):
        pdf = root / "source.pdf"
        pdf.write_bytes(b"%PDF-1.4\ncontenido")
        servicio = IngestionService(root / "data")
        with patch("licigt.ingesta.pipeline.extract_pages", return_value=paginas()), \
                patch("licigt.ingesta.pipeline.extract_hidden_text", return_value={}):
            return servicio, servicio.ingest(pdf, metadata())

    def _revisar(self, chunks):
        de_2 = [c for c in chunks if c["pagina_inicio"] == 2]
        self.assertTrue(de_2)
        self.assertTrue(all(not c["indexable"] and c["estado_calidad"] == "ruido_ocr" for c in de_2))
        self.assertTrue(all(c["indexable"] for c in chunks if c["pagina_inicio"] != 2))

    def test_make_chunks_marca_ruido_en_paginas_ocr_pero_no_en_texto(self):
        corto = [Page(1, SELLOS, "text", "ok")]
        self.assertTrue(make_chunks(corto, "d" * 32, metadata(), 1)[0]["indexable"])
        self.assertFalse(make_chunks([Page(1, SELLOS, "ocr", "ok")], "d" * 32, metadata(), 1)[0]["indexable"])

    def test_ingest_deja_el_ruido_ocr_fuera_del_indice(self):
        with tempfile.TemporaryDirectory() as temporal:
            _, manifiesto = self._ingerir(Path(temporal))
            self._revisar(manifiesto["chunks"])
            from licigt.ingesta.pipeline import paginas_sin_indexables
            self.assertEqual(paginas_sin_indexables([1, 2, 3], manifiesto["chunks"]), [2])

    def test_reprocess_deja_el_ruido_ocr_fuera_del_indice(self):
        with tempfile.TemporaryDirectory() as temporal:
            servicio, manifiesto = self._ingerir(Path(temporal))
            for c in manifiesto["chunks"]:
                c["indexable"], c["estado_calidad"] = True, "ok"
            ruta = Path(temporal) / "data" / "manifiestos_igss" / f"{manifiesto['doc_id']}.json"
            ruta.write_text(json.dumps(manifiesto), encoding="utf-8")
            with patch("licigt.ingesta.pipeline.extract_hidden_text", return_value={}):
                nuevo = servicio.reprocess(manifiesto["doc_id"])
            self._revisar(nuevo["chunks"])


if __name__ == "__main__":
    unittest.main()
