import json
import shutil
import tempfile
import unittest
from pathlib import Path

from licigt.ingesta.automatic import candidates_from_ocds, ingest_nog, official_url
from licigt.ingesta.pipeline import IngestionService


FIXTURE = Path(__file__).resolve().parents[4] / "docs/presentaciones/Proyecto Final CC3103_ Sistema NLP_RAG Agéntico Empresarial-1.pdf"


class FakeFetcher:
    def __init__(self, pdf):
        self.pdf = pdf
        self.calls = []

    def get(self, url, max_bytes):
        self.calls.append(url)
        if url.endswith(".pdf"):
            return self.pdf, url, "application/pdf"
        return b"<html><a href='https://www.guatecompras.gt/archivos/bases.pdf'>Bases del concurso</a></html>", url, "text/html"


class AutomaticTests(unittest.TestCase):
    def test_only_official_https_links(self):
        self.assertTrue(official_url("https://www.guatecompras.gt/a.pdf"))
        self.assertFalse(official_url("http://www.guatecompras.gt/a.pdf"))
        self.assertFalse(official_url("https://guatecompras.gt.evil.test/a.pdf"))
        self.assertFalse(official_url("https://127.0.0.1/a.pdf"))

    def test_ocds_uses_documents_of_selected_nog(self):
        payload = {"releases": [
            {"ocid": "ocds-xqjsxa-123", "tender": {"documents": [{"url": "https://www.guatecompras.gt/a.pdf", "title": "Bases"}]}},
            {"ocid": "ocds-xqjsxa-456", "tender": {"documents": [{"url": "https://evil.test/b.pdf"}]}},
        ]}
        _, candidates = candidates_from_ocds(payload, "123")
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].title, "Bases")

    @unittest.skipUnless(FIXTURE.exists() and shutil.which("pdftotext") and shutil.which("pdfinfo"), "Se requiere PDF y Poppler")
    def test_nog_page_downloads_pdf_and_reuses_ingestion(self):
        fetcher = FakeFetcher(FIXTURE.read_bytes())
        with tempfile.TemporaryDirectory() as temporary:
            service = IngestionService(Path(temporary))
            result = ingest_nog("123456", service, title="Concurso", entity="Entidad",
                                published="2026-11-14", fetcher=fetcher)
            self.assertEqual(len(result["ingested"]), 1)
            self.assertEqual(result["ingested"][0]["version"], 1)
            self.assertEqual(result["skipped"], [])
            repeated = ingest_nog("123456", service, title="Concurso", entity="Entidad",
                                  published="2026-11-14", fetcher=fetcher)
            self.assertEqual(repeated["ingested"][0]["doc_id"], result["ingested"][0]["doc_id"])


if __name__ == "__main__":
    unittest.main()
