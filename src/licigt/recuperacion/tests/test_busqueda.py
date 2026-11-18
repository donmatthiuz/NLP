"""Pruebas de recuperación. Las de integración requieren Postgres con el paquete importado:
docker compose up -d && PYTHONPATH=src python -m licigt.recuperacion importar"""

import unittest
from pathlib import Path

from licigt.recuperacion.busqueda import Contexto, _bajo_numeral, _redundante, buscar, comparar_versiones, rrf
from licigt.recuperacion.indice import MODELO_BASE, conectar, leer_paquete, modelo, ventanas_base
from licigt.recuperacion.evaluar import leer_como

PACKAGE = Path(__file__).resolve().parents[4] / "entregables" / "recuperacion" / "empresa_demo.zip"


class UnidadTests(unittest.TestCase):
    def test_rrf_pondera_y_combina(self):
        a, b, c = ({"chunk_id": x} for x in "abc")
        orden = [f["chunk_id"] for f in rrf([(0.6, [a, b]), (0.4, [c, b])])]
        self.assertEqual(orden, ["b", "a", "c"])  # b aparece en ambas listas

    def test_numeral(self):
        self.assertTrue(_bajo_numeral("2.2.6 Recepción", "2.2"))
        self.assertTrue(_bajo_numeral("2.2      CRONOGRAMA", "2.2"))
        self.assertFalse(_bajo_numeral("2.21 Otra", "2.2"))

    def test_otra_version_no_es_redundante(self):
        f = {"doc_id": "x", "pagina_inicio": 1, "pagina_fin": 1, "texto": "plazo de recepción de ofertas"}
        self.assertTrue(_redundante(f, dict(f)))
        self.assertFalse(_redundante(f, dict(f, doc_id="y")))

    def test_ventanas_base_no_se_truncan(self):
        _, _, manifiestos = leer_paquete(PACKAGE)
        tok = modelo(MODELO_BASE).tokenizer
        limite = modelo(MODELO_BASE).max_seq_length
        ventanas = [v for m in manifiestos.values() for v in ventanas_base(m, tok)]
        self.assertGreater(len(ventanas), 1003)
        for v in ventanas:
            self.assertLessEqual(len(tok(v["texto"])["input_ids"]), limite, v["chunk_id"])


class IntegracionTests(unittest.TestCase):
    @classmethod
    def tearDownClass(cls):
        cls.conn.close()

    @classmethod
    def setUpClass(cls):
        try:
            cls.conn = conectar()
        except Exception as exc:  # sin base de datos: solo corren las pruebas unitarias
            raise unittest.SkipTest(f"Postgres no disponible: {exc}")
        # La conexión de la aplicación no ve filas sin sesión: se lee como empresa_demo. Con base y sin filas, falla.
        eventos = dict(leer_como(cls.conn, Contexto("empresa_demo"),
                                 "SELECT DISTINCT numero_evento, evento_id FROM documentos"))
        if "222-IGSS-2023" not in eventos:
            cls.conn.close()
            raise AssertionError("La base responde pero empresa_demo no tiene el evento 222: corre make importar")
        cls.e222, cls.e399 = eventos["222-IGSS-2023"], eventos["399-IGSS-2026"]
        cls.ctx = Contexto("empresa_demo")

    def test_otra_empresa_no_ve_nada(self):
        for variante in ("base", "mejorada"):
            r = buscar(Contexto("otra_empresa"), self.e222, "cronograma de actividades", variante, conn=self.conn)
            self.assertEqual(r["fragmentos"], [])
            self.assertFalse(r["suficiente"])

    def test_rls_bloquea_sin_where(self):
        with self.conn.transaction():
            self.conn.execute("SET LOCAL ROLE licigt_app")
            self.conn.execute("SELECT set_config('app.tenant_id', 'otra_empresa', true)")
            self.assertEqual(self.conn.execute("SELECT count(*) FROM fragmentos").fetchone()[0], 0)

    def test_resultados_solo_del_evento(self):
        r = buscar(self.ctx, self.e399, "cronograma de actividades", conn=self.conn)
        docs = {d for (d,) in leer_como(self.conn, self.ctx, "SELECT doc_id FROM documentos WHERE evento_id = %s",
                                        (self.e399,))}
        self.assertTrue(r["fragmentos"])
        self.assertTrue({f["doc_id"] for f in r["fragmentos"]} <= docs)

    def test_222_conflicto_y_cobertura(self):
        r = buscar(self.ctx, self.e222, "fecha y hora para la recepción de ofertas", conn=self.conn)
        tipos = {a["tipo"] for a in r["alertas"]}
        self.assertIn("posible_conflicto", tipos)
        self.assertIn("cobertura_incompleta", tipos)
        self.assertEqual({f["tipo_documento"] for f in r["fragmentos"]}, {"bases", "modificacion"})
        for f in r["fragmentos"]:
            self.assertTrue({"chunk_id", "doc_id", "pagina_inicio", "version_ingesta", "score"} <= f.keys())

    def test_codigo_exacto(self):
        r = buscar(self.ctx, self.e399, "código IGSS 432", conn=self.conn)
        self.assertTrue(any("432" in f["texto"] for f in r["fragmentos"]))

    def test_comparar_versiones_222(self):
        r = comparar_versiones(self.ctx, self.e222, "recepción de ofertas", conn=self.conn)
        self.assertEqual({d["tipo_documento"] for d in r["documentos"]}, {"bases", "modificacion"})


if __name__ == "__main__":
    unittest.main()
