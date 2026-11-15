"""Contrato ejecutable del paquete que recibe el rol de Recuperación y RAG."""

import hashlib
import json
import re
import tempfile
import unittest
import zipfile
from collections import Counter
from pathlib import Path, PurePosixPath
from urllib.parse import urlparse


REPO = Path(__file__).resolve().parents[4]
PACKAGE = REPO / "entregables" / "recuperacion" / "empresa_demo.zip"
ABSOLUTE_LOCAL = re.compile(r"^(?:/|[A-Za-z]:[\\/]|file://|\\\\)")
REQUIRED_CHUNK = {
    "chunk_id", "doc_id", "tenant_id", "evento_id", "numero_evento",
    "version_ingesta", "pagina_inicio", "pagina_fin", "seccion", "texto",
    "indexable", "hash_sha256", "url_origen", "tipo_documento",
}


def archive_path(name):
    """Resuelve una ruta del inventario sin permitir salir del paquete extraído."""
    if not isinstance(name, str) or not name or "\\" in name or ABSOLUTE_LOCAL.match(name):
        raise AssertionError(f"Ruta no transportable: {name!r}")
    path = PurePosixPath(name)
    if ".." in path.parts or "." in path.parts:
        raise AssertionError(f"Ruta no transportable: {name!r}")
    return Path(*path.parts)


class EntregaRecuperacionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not PACKAGE.is_file():
            raise AssertionError(f"Falta el entregable: {PACKAGE}")
        cls.temporary = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.root = Path(cls.temporary.name)
        with zipfile.ZipFile(PACKAGE) as archive:
            names = archive.namelist()
            if len(names) != len(set(names)) or archive.testzip() is not None:
                raise AssertionError("ZIP corrupto o con nombres duplicados")
            for name in names:
                archive_path(name)
            archive.extractall(cls.root)
        cls.inventory = json.loads((cls.root / "inventario.json").read_text(encoding="utf-8"))
        cls.jsonl = (cls.root / "chunks.jsonl").read_bytes()
        cls.chunks = [json.loads(line) for line in cls.jsonl.splitlines()]

    def test_originales_y_json_son_transportables(self):
        inventory = self.inventory
        self.assertEqual(inventory["schema_version"], 1)
        self.assertEqual(inventory["tenant_id"], "empresa_demo")
        self.assertEqual(len(inventory["documents"]), 6)
        self.assertEqual(len({doc["evento_id"] for doc in inventory["documents"]}), 5)
        self.assertEqual(hashlib.sha256(self.jsonl).hexdigest(), inventory["sha256_chunks_jsonl"])
        self.assertEqual(len(self.chunks), inventory["chunks_indexables"])

        for doc in inventory["documents"]:
            original = self.root / archive_path(doc["original_zip_path"])
            manifest_file = self.root / archive_path(doc["manifiesto_zip_path"])
            provenance_file = self.root / archive_path(doc["procedencia_zip_path"])
            self.assertTrue(original.read_bytes().startswith(b"%PDF-"))
            self.assertEqual(hashlib.sha256(original.read_bytes()).hexdigest(), doc["sha256"])
            manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
            provenance = json.loads(provenance_file.read_text(encoding="utf-8"))
            self.assertEqual(manifest["object_uri"], doc["original_zip_path"])
            self.assertEqual(provenance["original_zip_path"], doc["original_zip_path"])
            self.assertEqual(manifest["doc_id"], doc["doc_id"])
            self.assertEqual(manifest["hash_sha256"], doc["sha256"])
            self.assertEqual(manifest["metadata"]["evento_id"], doc["evento_id"])
            self.assertEqual(provenance["sha256"], doc["sha256"])
            self.assertEqual(doc["cobertura"]["paginas_total"], len(manifest["pages"]))
            self.assertEqual(
                sorted(doc["paginas_no_indexadas"]),
                sorted(page["number"] for page in manifest["pages"] if page["quality"] != "ok"),
            )
            self.assertEqual(len(manifest["chunks"]), doc["chunks_indexables"] + doc["chunks_excluidos"])

    def test_fragmentos_sirven_para_busqueda_y_citas(self):
        documents = {doc["doc_id"]: doc for doc in self.inventory["documents"]}
        self.assertEqual(len(documents), len(self.inventory["documents"]))
        manifest_chunks = {}
        for doc in documents.values():
            manifest = json.loads((self.root / archive_path(doc["manifiesto_zip_path"])).read_text(encoding="utf-8"))
            for original_chunk in manifest["chunks"]:
                self.assertNotIn(original_chunk["chunk_id"], manifest_chunks)
                manifest_chunks[original_chunk["chunk_id"]] = original_chunk
        counts = Counter()
        chunk_ids = set()
        for chunk in self.chunks:
            self.assertTrue(REQUIRED_CHUNK <= chunk.keys())
            self.assertNotIn(chunk["chunk_id"], chunk_ids)
            chunk_ids.add(chunk["chunk_id"])
            doc = documents[chunk["doc_id"]]
            counts[chunk["doc_id"]] += 1
            self.assertTrue(chunk["indexable"])
            self.assertFalse(chunk["injection_suspected"])
            self.assertTrue(chunk["texto"].strip())
            self.assertEqual(chunk, manifest_chunks[chunk["chunk_id"]])
            self.assertEqual(chunk["tenant_id"], self.inventory["tenant_id"])
            self.assertEqual(chunk["evento_id"], doc["evento_id"])
            self.assertEqual(chunk["numero_evento"], doc["numero_evento"])
            self.assertEqual(chunk["version_ingesta"], doc["version_ingesta"])
            self.assertEqual(chunk["hash_sha256"], doc["sha256"])
            self.assertLessEqual(1, chunk["pagina_inicio"])
            self.assertLessEqual(chunk["pagina_inicio"], chunk["pagina_fin"])
            self.assertLessEqual(chunk["pagina_fin"], doc["cobertura"]["paginas_total"])
            self.assertNotIn(chunk["pagina_inicio"], doc["paginas_no_indexadas"])
            self.assertEqual(urlparse(chunk["url_origen"]).scheme, "https")
            for field, value in chunk.items():
                if isinstance(value, str) and field != "url_origen":
                    self.assertIsNone(ABSOLUTE_LOCAL.match(value), (chunk["chunk_id"], field))

        for doc in documents.values():
            self.assertEqual(counts[doc["doc_id"]], doc["chunks_indexables"])

        # Consulta de ejemplo con filtros de empresa y evento antes de leer la evidencia.
        modification = next(doc for doc in documents.values()
                            if doc["numero_evento"] == "222-IGSS-2023"
                            and doc["tipo_documento"] == "modificacion")

        def search(tenant_id, evento_id, phrase):
            return [chunk for chunk in self.chunks
                    if chunk["tenant_id"] == tenant_id and chunk["evento_id"] == evento_id
                    and phrase.casefold() in chunk["texto"].casefold()]

        matches = search("empresa_demo", modification["evento_id"], "CRONOGRAMA DE ACTIVIDADES")
        self.assertTrue(any(chunk["doc_id"] == modification["doc_id"] for chunk in matches))
        self.assertEqual(search("otra_empresa", modification["evento_id"], "CRONOGRAMA DE ACTIVIDADES"), [])
        self.assertEqual(modification["paginas_no_indexadas"], [3, 4])
        self.assertEqual(modification["status"], "requiere_revision")


if __name__ == "__main__":
    unittest.main()
