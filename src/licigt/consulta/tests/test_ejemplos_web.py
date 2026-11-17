"""Los ejemplos de la web validan contra el esquema y salen de datos reales del 222."""

import json
import re
import unittest
import zipfile
from pathlib import Path

from licigt.consulta.esquemas import RespuestaEstructurada

RAIZ = Path(__file__).resolve().parents[4]
EJEMPLOS = RAIZ / "web" / "src" / "ejemplos"
PAQUETE = RAIZ / "entregables" / "recuperacion" / "empresa_demo.zip"
NOMBRES = ["respuesta", "abstencion", "comparacion", "aclaracion", "cobertura_parcial"]


def colapsar(texto: str) -> str:
    return re.sub(r"\s+", " ", texto).strip()


class EjemplosWebTests(unittest.TestCase):
    def cargar(self, nombre: str) -> dict:
        return json.loads((EJEMPLOS / f"{nombre}.json").read_text(encoding="utf-8"))

    def test_hay_cinco_ejemplos(self):
        self.assertEqual(sorted(p.stem for p in EJEMPLOS.glob("*.json")), sorted(NOMBRES))

    def test_cada_ejemplo_valida_contra_el_esquema(self):
        for nombre in NOMBRES:
            with self.subTest(nombre=nombre):
                RespuestaEstructurada.model_validate(self.cargar(nombre))

    def test_estado_de_cada_ejemplo(self):
        r = {n: RespuestaEstructurada.model_validate(self.cargar(n)) for n in NOMBRES}
        self.assertTrue(r["abstencion"].abstained and not r["abstencion"].sources)
        self.assertTrue(r["aclaracion"].needs_clarification)
        self.assertTrue(r["comparacion"].needs_human_review)
        self.assertGreaterEqual(len({s.doc_id for s in r["comparacion"].sources}), 2)
        for n in ("respuesta", "cobertura_parcial"):
            self.assertFalse(r[n].abstained or r[n].needs_human_review or r[n].needs_clarification)
            self.assertTrue(r[n].sources)

    def test_ningun_ejemplo_lleva_tenant_id(self):
        for nombre in NOMBRES:
            self.assertNotIn("tenant_id", (EJEMPLOS / f"{nombre}.json").read_text(encoding="utf-8"))

    @unittest.skipUnless(PAQUETE.exists(), "falta entregables/recuperacion/empresa_demo.zip")
    def test_las_fuentes_salen_del_paquete_real(self):
        with zipfile.ZipFile(PAQUETE) as z:
            reales = {c["chunk_id"]: c for c in map(json.loads, z.read("chunks.jsonl").decode().splitlines())}
        for nombre in NOMBRES:
            for fuente in RespuestaEstructurada.model_validate(self.cargar(nombre)).sources:
                with self.subTest(nombre=nombre, chunk=fuente.chunk_id):
                    real = reales[fuente.chunk_id]
                    self.assertEqual(real["doc_id"], fuente.doc_id)
                    self.assertEqual(int(real["pagina_inicio"]), fuente.page)
                    self.assertEqual(real["url_origen"], fuente.source)
                    self.assertIn(fuente.cita, colapsar(real["texto"]))


if __name__ == "__main__":
    unittest.main()
