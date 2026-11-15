import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from licigt.ingesta.automatic import ingest_event, official_url, parse_portal
from licigt.ingesta.pdf import Page
from licigt.ingesta.pipeline import IngestionService


ROW = '''<tr data-prov-id="10432" data-pub="2026-11-13"><td>
<span>Licitación</span><span>No. 399-IGSS-2026</span><span>Código: 432</span>
<div class="fw-semibold">MULTIVITAMINICO PRENATAL</div>
<div class="small text-muted">DISTINTAS UNIDADES MEDICAS</div></td>
<td><a href="https://www.igssgt.org/wp-content/uploads/bases.pdf">Descargar</a></td></tr>'''


class FakeFetcher:
    def get(self, url, max_bytes):
        return (ROW.encode(), url) if url.endswith("/proveedores/") else (b"%PDF-1.4\nfake", url)


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
        with tempfile.TemporaryDirectory() as temporary, patch("licigt.ingesta.pipeline.extract_pages", return_value=[page]):
            service = IngestionService(Path(temporary))
            first = ingest_event("399-IGSS-2026", "empresa_demo", service, fetcher=FakeFetcher())
            second = ingest_event("399-IGSS-2026", "empresa_demo", service, fetcher=FakeFetcher())
            self.assertEqual(first["doc_id"], second["doc_id"])
            self.assertEqual(first["status"], "completo")
            self.assertEqual(first["version_ingesta"], 1)


if __name__ == "__main__":
    unittest.main()
