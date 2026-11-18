"""Paquete de la segunda empresa: un solo evento, otra empresa, ids propios y hash válido."""

import hashlib
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from licigt.plataforma import empresa_b

ORIGEN = empresa_b.ORIGEN


@unittest.skipUnless(ORIGEN.exists(), "falta entregables/recuperacion/empresa_demo.zip")
class EmpresaBTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporal = tempfile.TemporaryDirectory()
        cls.destino = Path(cls.temporal.name) / "empresa_b.zip"
        cls.resumen = empresa_b.armar(destino=cls.destino)
        cls.z = zipfile.ZipFile(cls.destino)
        cls.inventario = json.loads(cls.z.read("inventario.json"))
        cls.chunks = [json.loads(l) for l in cls.z.read("chunks.jsonl").splitlines()]
        with zipfile.ZipFile(ORIGEN) as o:
            cls.origen_inventario = json.loads(o.read("inventario.json"))
            cls.pdf_origen = {d["doc_id"]: o.read(d["original_zip_path"]) for d in cls.origen_inventario["documents"]}

    @classmethod
    def tearDownClass(cls):
        cls.z.close()
        cls.temporal.cleanup()

    def test_solo_el_evento_363_con_la_empresa_b(self):
        self.assertEqual(self.inventario["tenant_id"], "empresa_b")
        self.assertEqual({d["numero_evento"] for d in self.inventario["documents"]}, {"363-IGSS-2026"})
        self.assertEqual({c["tenant_id"] for c in self.chunks}, {"empresa_b"})
        self.assertEqual({c["numero_evento"] for c in self.chunks}, {"363-IGSS-2026"})
        self.assertEqual(self.resumen["chunks"], len(self.chunks))
        self.assertEqual(self.inventario["chunks_indexables"], len(self.chunks))

    def test_ids_nuevos_y_distintos_de_empresa_demo(self):
        viejos = {d["doc_id"] for d in self.origen_inventario["documents"]}
        nuevos = {d["doc_id"] for d in self.inventario["documents"]}
        self.assertFalse(viejos & nuevos)
        self.assertTrue(all(len(i) == 32 for i in nuevos))
        self.assertTrue(all(c["doc_id"] in nuevos and c["chunk_id"].startswith(c["doc_id"] + ":") for c in self.chunks))

    def test_hash_del_inventario_y_manifiestos_coherentes(self):
        self.assertEqual(hashlib.sha256(self.z.read("chunks.jsonl")).hexdigest(), self.inventario["sha256_chunks_jsonl"])
        for d in self.inventario["documents"]:
            m = json.loads(self.z.read(d["manifiesto_zip_path"]))
            self.assertEqual((m["doc_id"], m["metadata"]["tenant_id"]), (d["doc_id"], "empresa_b"))
            self.assertIn(d["original_zip_path"], self.z.namelist())
            self.assertNotIn("empresa_demo", json.dumps(m))

    def test_el_original_es_el_mismo_pdf(self):
        d = self.inventario["documents"][0]
        self.assertIn(self.z.read(d["original_zip_path"]), self.pdf_origen.values())

    def test_no_se_cuela_otro_evento(self):
        self.assertEqual(len([n for n in self.z.namelist() if n.startswith("originales/")]), 1)


if __name__ == "__main__":
    unittest.main()
