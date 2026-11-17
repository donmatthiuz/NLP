import sqlite3
import tempfile
import unittest
import hashlib
import json
from contextlib import closing
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


BASES = {"tipo_documento": "bases", "document_key": "bases_integradas"}
MODIFICACION = {"tipo_documento": "modificacion", "document_key": "modificacion_1",
                "relacion_documental": "bases_integradas"}


class FakeFetcher:
    def get(self, url, max_bytes):
        return (ROW.encode(), url) if url.endswith("/proveedores/") else (b"%PDF-1.4\nfake", url)


class PdfPorEvento:
    """Portal con el evento 222 y un PDF distinto en cada llamada de descarga."""

    def __init__(self):
        self.descargas = 0

    def get(self, url, max_bytes):
        if url.endswith("/proveedores/"):
            return ROW3.encode(), url
        self.descargas += 1
        return b"%PDF-1.4\n" + str(self.descargas).encode(), url


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
            first = ingest_event("399-IGSS-2026", "empresa_demo", service, fetcher=FakeFetcher(), **BASES)
            second = ingest_event("399-IGSS-2026", "empresa_demo", service, fetcher=FakeFetcher(), **BASES)
            self.assertEqual(first["doc_id"], second["doc_id"])
            self.assertEqual(first["status"], "completo")
            self.assertEqual(first["version_ingesta"], 1)
            manifest = json.loads((Path(temporary) / "manifiestos_igss" / f"{first['doc_id']}.json").read_text())
            self.assertEqual(manifest["metadata"]["fecha_ficha"], "2026-11-13")
            self.assertIsNone(manifest["metadata"]["fecha_publicacion"])

    def _paginas(self, *textos):
        return [Page(n, texto, "text", "ok") for n, texto in enumerate(textos, 1)]

    def _ingerir(self, textos, fetcher=None, **tipo):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        with patch("licigt.ingesta.pipeline.extract_pages", return_value=self._paginas(*textos)), \
                patch("licigt.ingesta.pipeline.extract_hidden_text", return_value={}):
            service = IngestionService(Path(temporary.name))
            numero = "222-IGSS-2023" if fetcher else "399-IGSS-2026"
            return service, ingest_event(numero, "empresa_demo", service,
                                         fetcher=fetcher or FakeFetcher(), **tipo)

    def test_sin_tipo_explicito_falla(self):
        with tempfile.TemporaryDirectory() as temporary:
            service = IngestionService(Path(temporary))
            with self.assertRaisesRegex(ValueError, "tipo_documento"):
                ingest_event("399-IGSS-2026", "empresa_demo", service, fetcher=FakeFetcher(),
                             document_key="bases_integradas")
            with self.assertRaisesRegex(ValueError, "document_key"):
                ingest_event("399-IGSS-2026", "empresa_demo", service, fetcher=FakeFetcher(),
                             tipo_documento="bases")

    def test_modificacion_sin_relacion_falla(self):
        with tempfile.TemporaryDirectory() as temporary:
            service = IngestionService(Path(temporary))
            for tipo in ("modificacion", "aclaracion", "anexo"):
                with self.assertRaisesRegex(ValueError, "relacion_documental"):
                    ingest_event("399-IGSS-2026", "empresa_demo", service, fetcher=FakeFetcher(),
                                 tipo_documento=tipo, document_key=f"{tipo}_1")

    def test_portada_de_modificacion_declarada_como_bases_no_se_indexa(self):
        service, result = self._ingerir(
            ["MODIFICACIÓN No. 1\n399-IGSS-2026\nSe modifica el plazo.", "Texto 399-IGSS-2026", "Más texto"], **BASES)
        self.assertEqual(result["status"], "requiere_revision")
        self.assertIn("El PDF parece una modificación; revisar el tipo documental", result["warnings"])
        manifest = json.loads((service.data_dir / "manifiestos_igss" / f"{result['doc_id']}.json").read_text())
        self.assertTrue(manifest["chunks"])
        self.assertFalse(any(chunk["indexable"] for chunk in manifest["chunks"]))
        self.assertIn("El PDF parece una modificación; revisar el tipo documental", manifest["warnings"])
        with closing(sqlite3.connect(service.database)) as connection:
            estado = connection.execute("SELECT status FROM documents WHERE doc_id=?", (result["doc_id"],)).fetchone()[0]
        self.assertEqual(estado, "requiere_revision")

    def test_modificacion_declarada_correctamente_queda_indexable(self):
        service, result = self._ingerir(
            ["MODIFICACIÓN No. 1\n399-IGSS-2026\nSe modifica el plazo.", "Texto", "Más texto"], **MODIFICACION)
        manifest = json.loads((service.data_dir / "manifiestos_igss" / f"{result['doc_id']}.json").read_text())
        self.assertTrue(all(chunk["indexable"] for chunk in manifest["chunks"]))
        self.assertNotIn("El PDF parece una modificación; revisar el tipo documental", result["warnings"])

    def test_evento_con_bases_y_modificacion(self):
        fetcher = PdfPorEvento()
        paginas = [
            self._paginas("BASES DE LICITACIÓN 222-IGSS-2023\nPlazo 30 días", "p2", "p3"),
            self._paginas("MODIFICACIÓN No. 1 222-IGSS-2023\nNuevo plazo", "p2", "p3"),
        ]
        with tempfile.TemporaryDirectory() as temporary, \
                patch("licigt.ingesta.pipeline.extract_pages", side_effect=paginas), \
                patch("licigt.ingesta.pipeline.extract_hidden_text", return_value={}):
            service = IngestionService(Path(temporary))
            bases = ingest_event("222-IGSS-2023", "empresa_demo", service, fetcher=fetcher, **BASES)
            modificacion = ingest_event("222-IGSS-2023", "empresa_demo", service, fetcher=fetcher, **MODIFICACION)
            self.assertEqual(bases["evento_id"], modificacion["evento_id"])
            self.assertEqual(modificacion["status"], "completo")
            manifest = json.loads((Path(temporary) / "manifiestos_igss" / f"{modificacion['doc_id']}.json").read_text())
            self.assertEqual(manifest["metadata"]["tipo_documento"], "modificacion")
            self.assertEqual(manifest["metadata"]["relacion_documental"], "bases_integradas")
            self.assertEqual(manifest["cobertura"]["tipos_cargados"], ["bases", "modificacion"])

    def test_evento_sin_codigo_igss_sigue_funcionando(self):
        sin_codigo = ROW.replace("<span>Código: 432</span>", "")
        class SinCodigo(FakeFetcher):
            def get(self, url, max_bytes):
                return (sin_codigo.encode(), url) if url.endswith("/proveedores/") else (b"%PDF-1.4\nfake", url)
        with tempfile.TemporaryDirectory() as temporary, \
                patch("licigt.ingesta.pipeline.extract_pages", return_value=self._paginas("DOCUMENTOS DE LICITACIÓN 399-IGSS-2026")), \
                patch("licigt.ingesta.pipeline.extract_hidden_text", return_value={}):
            result = ingest_event("399-IGSS-2026", "empresa_demo", IngestionService(Path(temporary)),
                                  fetcher=SinCodigo(), **BASES)
            self.assertEqual(result["status"], "completo")

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
                sidecar_path = Path(item["manifiesto"])
                sidecar = json.loads(sidecar_path.read_text())
                self.assertEqual(sidecar["numero_evento"], item["numero_evento"])
                self.assertFalse(Path(sidecar["archivo"]).is_absolute())
                self.assertEqual((sidecar_path.parent / sidecar["archivo"]).resolve(), pdf)
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
