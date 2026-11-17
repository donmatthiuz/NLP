import json
import tempfile
import unittest
from pathlib import Path

from licigt.ingesta.eventos import evento_de_carga, main

TEXTO_PAGINA = "El oferente debe presentar solvencia patronal vigente y fianza de sostenimiento"


def manifiesto(legibles=2, total=2, warnings=None, status="completo", **extra):
    return {
        "doc_id": "a" * 32, "hash_sha256": "b" * 64, "version_ingesta": 1, "status": status,
        "object_uri": "file:///home/usuario/data/ingesta/originales/a.pdf",
        "created_at": "2026-11-14T10:00:00+00:00", "warnings": warnings or [],
        "cobertura": {"paginas_legibles": legibles, "paginas_total": total},
        "metadata": {"tenant_id": "empresa_demo", "evento_id": "e" * 32, "url_origen": "https://www.igssgt.org/a.pdf"},
        "pages": [{"number": 1, "text": TEXTO_PAGINA, "method": "text", "quality": "ok"}],
        "chunks": [{"chunk_id": "x:00001", "texto": TEXTO_PAGINA, "indexable": True}],
        **extra,
    }


class EventosTests(unittest.TestCase):
    def test_campos_y_sin_texto_ni_rutas(self):
        evento = evento_de_carga(manifiesto())
        self.assertEqual(set(evento), {"tenant_id", "evento_id", "doc_id", "hash_sha256", "status",
                                       "paginas_legibles", "paginas_total", "warnings", "created_at"})
        self.assertEqual(evento["tenant_id"], "empresa_demo")
        self.assertEqual(evento["status"], "completo")
        serializado = json.dumps(evento, ensure_ascii=False)
        self.assertNotIn("solvencia patronal", serializado)
        self.assertNotIn("fianza", serializado)
        self.assertNotIn("/home/", serializado)
        self.assertNotIn("file://", serializado)

    def test_pagina_ilegible_pide_revision(self):
        evento = evento_de_carga(manifiesto(legibles=1, total=2))
        self.assertEqual(evento["status"], "requiere_revision")
        self.assertIn("Hay páginas incompletas o ilegibles", evento["warnings"])
        self.assertEqual((evento["paginas_legibles"], evento["paginas_total"]), (1, 2))

    def test_aviso_no_se_duplica(self):
        aviso = "Hay páginas incompletas o ilegibles"
        evento = evento_de_carga(manifiesto(legibles=1, total=2, warnings=[aviso], status="requiere_revision"))
        self.assertEqual(evento["warnings"].count(aviso), 1)

    def test_reextracted_at_solo_si_existe(self):
        self.assertNotIn("reextracted_at", evento_de_carga(manifiesto()))
        evento = evento_de_carga(manifiesto(reextracted_at="2026-11-17T09:00:00+00:00"))
        self.assertEqual(evento["reextracted_at"], "2026-11-17T09:00:00+00:00")

    def test_no_modifica_el_manifiesto(self):
        original = manifiesto(legibles=1, total=2)
        evento_de_carga(original)
        self.assertEqual(original, manifiesto(legibles=1, total=2))

    def test_cli_imprime_json(self):
        import contextlib
        import io
        with tempfile.TemporaryDirectory() as temporary:
            ruta = Path(temporary) / "m.json"
            ruta.write_text(json.dumps(manifiesto()), encoding="utf-8")
            salida = io.StringIO()
            with contextlib.redirect_stdout(salida):
                main(["--manifiesto", str(ruta)])
        self.assertEqual(json.loads(salida.getvalue())["doc_id"], "a" * 32)


if __name__ == "__main__":
    unittest.main()
