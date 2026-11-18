"""Lectura del original del PDF desde el paquete: solo si la fila existe para la empresa de la sesión."""

import io
import os
import tempfile
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from licigt.plataforma import originales

DOC = "a" * 32
OTRO = "b" * 32


class ConexionDocumentos:
    """Conexión doble: responde que existe la fila solo para (empresa, evento, documento) conocidos."""
    def __init__(self, filas):
        self.filas, self.consultas, self.cerrada = set(filas), [], False

    def transaction(self):
        from contextlib import nullcontext
        return nullcontext()

    def execute(self, sql, params=()):
        self.consultas.append(params)
        return SimpleNamespace(fetchone=lambda: (1,) if tuple(params) in self.filas else None)

    def close(self):
        self.cerrada = True


class OriginalesTests(unittest.TestCase):
    def setUp(self):
        self.temporal = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporal.cleanup)
        carpeta = Path(self.temporal.name)
        with zipfile.ZipFile(carpeta / "empresa_demo.zip", "w") as z:
            z.writestr(f"originales/{DOC}.pdf", b"%PDF-demo")
        entorno = patch.dict(os.environ, {"LICIGT_PAQUETES_DIRS": str(carpeta)})
        entorno.start()
        self.addCleanup(entorno.stop)
        self.conn = ConexionDocumentos({("empresa_demo", "ev1", DOC)})
        self.sesiones = []
        self.abrir = lambda: (self.conn, lambda c, x: self.sesiones.append(x.tenant_id))

    def leer(self, tenant="empresa_demo", evento="ev1", doc=DOC):
        return originales.leer_original(SimpleNamespace(tenant_id=tenant, usuario="u"), evento, doc, abrir=self.abrir)

    def test_propio(self):
        self.assertEqual(self.leer(), b"%PDF-demo")
        self.assertEqual(self.sesiones, ["empresa_demo"])
        self.assertTrue(self.conn.cerrada)

    def test_de_otra_empresa_otro_evento_o_inexistente_da_none(self):
        self.assertIsNone(self.leer(tenant="empresa_b"))
        self.assertIsNone(self.leer(evento="ev2"))
        self.assertIsNone(self.leer(doc=OTRO))

    def test_fila_existente_sin_pdf_en_el_paquete_da_none(self):
        self.conn.filas.add(("empresa_demo", "ev1", OTRO))
        self.assertIsNone(self.leer(doc=OTRO))

    def test_doc_id_que_no_es_hex_nunca_toca_la_base_ni_el_disco(self):
        for malo in ("..", "../x", "a/b", DOC + ".pdf", "", "A" * 32, "a" * 31):
            with self.subTest(malo=malo):
                self.assertIsNone(self.leer(doc=malo))
        self.assertEqual(self.conn.consultas, [])

    def test_tenant_con_caracteres_raros_no_arma_una_ruta(self):
        self.conn.filas.add(("../empresa_demo", "ev1", DOC))
        self.assertIsNone(self.leer(tenant="../empresa_demo"))


if __name__ == "__main__":
    unittest.main()
