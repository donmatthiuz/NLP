import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from licigt.ingesta.pdf import Page
from licigt.ingesta.pipeline import IngestionService, SourceMetadata, make_chunks


def metadata(**changes):
    values = dict(tenant_id="empresa_demo", evento_id="evento_399", numero_evento="399-IGSS-2026",
                  anio=2026, modalidad="Licitación Pública DA", document_key="bases_integradas",
                  tipo_documento="bases", titulo="Multivitamínico prenatal", entidad="IGSS",
                  url_origen="https://www.igssgt.org/wp-content/uploads/bases.pdf",
                  codigos_producto_igss=("432",))
    values.update(changes)
    return SourceMetadata(**values)


class IngestionTests(unittest.TestCase):
    def test_duplicate_version_and_tenant_isolation(self):
        pages = [Page(1, "DOCUMENTOS DE LICITACIÓN 399-IGSS-2026\nCÓDIGO IGSS 432\nBases de licitación", "text", "ok")]
        with tempfile.TemporaryDirectory() as temporary, patch("licigt.ingesta.pipeline.extract_pages", return_value=pages):
            root = Path(temporary)
            source = root / "doc.pdf"
            source.write_bytes(b"%PDF-1.4\nfirst")
            service = IngestionService(root / "data")
            first = service.ingest(source, metadata())
            self.assertEqual(first["doc_id"], service.ingest(source, metadata())["doc_id"])
            self.assertEqual(first["version_ingesta"], 1)
            self.assertEqual(first["status"], "completo")
            self.assertIsNone(first["metadata"]["fecha_publicacion"])
            self.assertEqual(first["chunks"][0]["codigos_producto_igss"], ["432"])
            self.assertEqual(first["chunking_revision"], 2)
            source.write_bytes(b"%PDF-1.4\nsecond")
            second = service.ingest(source, metadata())
            self.assertEqual(second["version_ingesta"], 2)
            self.assertEqual(second["previous_doc_id"], first["doc_id"])
            other = service.ingest(source, metadata(tenant_id="otra_empresa"))
            self.assertEqual(other["version_ingesta"], 1)
            self.assertNotEqual(other["object_uri"], second["object_uri"])

    def test_wrong_event_and_notice_are_not_indexable(self):
        pages = [Page(1, "CONVOCATORIA 111-IGSS-2026. Las bases no están aquí.", "text", "ok")]
        with tempfile.TemporaryDirectory() as temporary, patch("licigt.ingesta.pipeline.extract_pages", return_value=pages):
            root = Path(temporary)
            source = root / "notice.pdf"
            source.write_bytes(b"%PDF-1.4\nnotice")
            result = IngestionService(root / "data").ingest(source, metadata(tipo_documento="convocatoria"))
            self.assertEqual(result["status"], "requiere_revision")
            self.assertTrue(result["cobertura"]["solo_convocatoria"])
            self.assertFalse(result["cobertura"]["evento_confirmado_en_pdf"])
            self.assertTrue(all(not chunk["indexable"] for chunk in result["chunks"]))

    def test_event_id_cannot_be_reused_for_another_event(self):
        pages = [Page(1, "DOCUMENTOS DE LICITACIÓN 399-IGSS-2026", "text", "ok")]
        with tempfile.TemporaryDirectory() as temporary, patch("licigt.ingesta.pipeline.extract_pages", return_value=pages):
            root = Path(temporary)
            source = root / "doc.pdf"
            source.write_bytes(b"%PDF-1.4\nfirst")
            service = IngestionService(root / "data")
            service.ingest(source, metadata())
            with self.assertRaisesRegex(ValueError, "evento_id"):
                service.ingest(source, metadata(numero_evento="363-IGSS-2026", document_key="otro"))
            with self.assertRaisesRegex(ValueError, "evento_id"):
                service.ingest(source, metadata(numero_evento="363-IGSS-2026"))


class MetadataTests(unittest.TestCase):
    def test_igss_url_tenant_and_unknown_date(self):
        with self.assertRaises(ValueError):
            metadata(url_origen="https://www.guatecompras.gt/a.pdf").validate()
        with self.assertRaises(ValueError):
            metadata(tenant_id="").validate()
        with self.assertRaises(ValueError):
            metadata(url_origen="https://usuario:clave@www.igssgt.org/bases.pdf").validate()
        metadata(fecha_publicacion=None, nog_referencia=None).validate()

    def test_table_keeps_raw_text_and_markdown(self):
        page = Page(4, "Documento     Plazo\nConstancia    5 días", "text", "ok")
        chunk = make_chunks([page], "documento", metadata(), 1)[0]
        self.assertEqual(chunk["tipo_chunk"], "tabla")
        self.assertIn("Constancia    5 días", chunk["texto"])
        self.assertIn("| Constancia | 5 días |", chunk["tabla_markdown"])

    def test_declared_product_code_remains_on_every_chunk(self):
        page = Page(4, "Esta sección contiene requisitos documentales.", "text", "ok")
        chunk = make_chunks([page], "documento", metadata(), 1)[0]
        self.assertEqual(chunk["codigos_producto_igss"], ["432"])


if __name__ == "__main__":
    unittest.main()
