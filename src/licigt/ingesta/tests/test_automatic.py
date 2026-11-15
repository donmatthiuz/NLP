import tempfile
import unittest
import hashlib
import json
from pathlib import Path
from unittest.mock import patch

from licigt.ingesta.automatic import ingest_event, official_url, parse_portal
from licigt.ingesta.download import download_selected
from licigt.ingesta.pdf import Page
from licigt.ingesta.pipeline import IngestionService


ROW = '''<tr data-prov-id="10432" data-pub="2026-11-13"><td>
<span>Licitación</span><span>No. 399-IGSS-2026</span><span>Código: 432</span>
<div class="fw-semibold">MULTIVITAMINICO PRENATAL</div>
<div class="small text-muted">DISTINTAS UNIDADES MEDICAS</div></td>
<td><a href="https://www.igssgt.org/wp-content/uploads/bases.pdf">Descargar</a></td></tr>'''
ROW2 = '''<tr data-prov-id="10433" data-pub="2026-11-13"><td>
<span>Licitación</span><span>No. 363-IGSS-2026</span><span>Código: 345</span>
<div class="fw-semibold">METIMAZOL</div><div class="small text-muted">UNIDADES MEDICAS</div></td>
<td><a href="https://www.igssgt.org/wp-content/uploads/metimazol.pdf">Descargar</a></td></tr>'''
ROW3 = '''<tr data-prov-id="12001" data-pub="2023-07-15"><td>
<span>Licitación</span><span>No. 222-IGSS-2023</span><span>Código: 10527</span>
<div class="fw-semibold">OMALIZUMAB</div><div class="small text-muted">UNIDADES MEDICAS</div></td>
<td><a href="https://www.igssgt.org/wp-content/uploads/222-IGSS-2023-modificacion.pdf">Descargar</a></td></tr>'''


class FakeFetcher:
    def get(self, url, max_bytes):
        return (ROW.encode(), url) if url.endswith("/proveedores/") else (b"%PDF-1.4\nfake", url)


class FakeBatchFetcher:
    def get(self, url, max_bytes):
        if url.endswith("?y=2026"):
            return (ROW + ROW2).encode(), url
        if url.endswith("?y=2023"):
            return ROW3.encode(), url
        return b"%PDF-1.4\n" + url.encode(), url


class AutomaticTests(unittest.TestCase):
    def test_portal_row_and_domain(self):
        self.assertTrue(official_url("https://www.igssgt.org/a.pdf"))
        self.assertFalse(official_url("https://igssgt.org.evil.test/a.pdf"))
        event = parse_portal(ROW)[0]
        self.assertEqual(event.numero_evento, "399-IGSS-2026")
        self.assertEqual(event.codigo_igss, "432")
        self.assertEqual(event.fecha_publicacion, "2026-11-13")

    def test_download_reuses_manual_pipeline(self):
        page = Page(1, "DOCUMENTOS DE LICITACIÓN 399-IGSS-2026\nCÓDIGO IGSS 432", "text", "ok")
        with tempfile.TemporaryDirectory() as temporary, \
                patch("licigt.ingesta.pipeline.extract_pages", return_value=[page]), \
                patch("licigt.ingesta.pipeline.extract_hidden_text", return_value={}):
            service = IngestionService(Path(temporary))
            first = ingest_event("399-IGSS-2026", "empresa_demo", service, fetcher=FakeFetcher())
            second = ingest_event("399-IGSS-2026", "empresa_demo", service, fetcher=FakeFetcher())
            self.assertEqual(first["doc_id"], second["doc_id"])
            self.assertEqual(first["status"], "completo")
            self.assertEqual(first["version_ingesta"], 1)

    def test_batch_download_saves_pdf_and_provenance_without_ingesting(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            selected = ["399-IGSS-2026", "363-IGSS-2026"]
            first = download_selected(selected, root, fetcher=FakeBatchFetcher())
            second = download_selected(selected, root, fetcher=FakeBatchFetcher())
            self.assertEqual([item["estado"] for item in first], ["descargado", "descargado"])
            self.assertEqual([item["estado"] for item in second], ["ya_existia", "ya_existia"])
            for item in first:
                pdf = Path(item["archivo"])
                self.assertEqual(hashlib.sha256(pdf.read_bytes()).hexdigest(), item["sha256"])
                self.assertEqual(json.loads(Path(item["manifiesto"]).read_text())["numero_evento"],
                                 item["numero_evento"])
            self.assertFalse((root / "igss_ingesta.sqlite3").exists())

    def test_historical_event_and_additional_bases(self):
        base_url = "https://www.igssgt.org/wp-content/uploads/222-IGSS-2023-bases.pdf"
        with tempfile.TemporaryDirectory() as temporary:
            result = download_selected(["222-IGSS-2023"], Path(temporary),
                                       fetcher=FakeBatchFetcher(),
                                       extra_pdf_urls={"222-IGSS-2023": [("bases", base_url)]})
            self.assertEqual(len(result), 2)
            manifests = [json.loads(Path(item["manifiesto"]).read_text()) for item in result]
            self.assertEqual([item["enlace_en_ficha"] for item in manifests], [True, False])
            self.assertEqual(manifests[1]["tipo_documento_declarado"], "bases")
            self.assertIsNone(manifests[1]["fecha_publicacion"])
            self.assertEqual(manifests[0]["fecha_ficha"], "2023-07-15")
            self.assertIsNone(manifests[0]["fecha_publicacion"])
            self.assertTrue(all(item["pagina_origen"].endswith("?y=2023") for item in manifests))


if __name__ == "__main__":
    unittest.main()
