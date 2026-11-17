"""Los ejemplos de la web validan contra el esquema y salen de datos reales del 222."""

import json
import re
import unittest
import zipfile
from pathlib import Path

from licigt.consulta.esquemas import RespuestaEstructurada
from licigt.consulta.lista import MOTIVO_FECHAS_DISTINTAS, PropuestaLista

RAIZ = Path(__file__).resolve().parents[4]
EJEMPLOS = RAIZ / "web" / "src" / "ejemplos"
PAQUETE = RAIZ / "entregables" / "recuperacion" / "empresa_demo.zip"
NOMBRES = ["respuesta", "abstencion", "comparacion", "aclaracion", "cobertura_parcial"]


def colapsar(texto: str) -> str:
    return re.sub(r"\s+", " ", texto).strip()


class EjemplosWebTests(unittest.TestCase):
    def cargar(self, nombre: str) -> dict:
        return json.loads((EJEMPLOS / f"{nombre}.json").read_text(encoding="utf-8"))

    def test_hay_cinco_ejemplos_y_la_propuesta_de_lista(self):
        self.assertEqual(sorted(p.stem for p in EJEMPLOS.glob("*.json")), sorted([*NOMBRES, "lista"]))

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
        self.assertFalse(r["respuesta"].abstained or r["respuesta"].needs_human_review or r["respuesta"].needs_clarification)
        # Citar una modificación escala a revisión humana (validación.TIPOS_QUE_ESCALAN).
        self.assertFalse(r["cobertura_parcial"].abstained or r["cobertura_parcial"].needs_clarification)
        self.assertTrue(r["cobertura_parcial"].needs_human_review)
        self.assertIn("d41480e5b0ce4c16bf18f66225ada2dc:00008", {s.chunk_id for s in r["cobertura_parcial"].sources})
        for n in ("respuesta", "cobertura_parcial"):
            self.assertTrue(r[n].sources)

    def test_answer_lleva_marcadores_como_el_validador(self):
        for nombre in NOMBRES:
            r = RespuestaEstructurada.model_validate(self.cargar(nombre))
            if not r.sources:
                continue
            with self.subTest(nombre=nombre):
                lineas = r.answer.split("\n")
                for linea in lineas:
                    self.assertRegex(linea, r" \[\d+\](?:\[\d+\])*$")
                usados = {int(n) for n in re.findall(r"\[(\d+)\]", r.answer)}
                self.assertEqual(usados, set(range(1, len(r.sources) + 1)))

    @unittest.skipUnless(PAQUETE.exists(), "falta entregables/recuperacion/empresa_demo.zip")
    def test_avisos_de_cobertura_salen_del_inventario(self):
        with zipfile.ZipFile(PAQUETE) as z:
            docs = json.loads(z.read("inventario.json"))["documents"]
        esperados = {
            f"cobertura_incompleta: {d['doc_id']} páginas no indexadas " + ", ".join(map(str, d["paginas_no_indexadas"]))
            for d in docs if d["numero_evento"] == "222-IGSS-2023" and d["paginas_no_indexadas"]
        }
        for nombre in NOMBRES:
            r = RespuestaEstructurada.model_validate(self.cargar(nombre))
            if r.tool_used is None:
                continue
            with self.subTest(nombre=nombre):
                self.assertEqual({w for w in r.warnings if w.startswith("cobertura_incompleta")}, esperados)

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

    def test_la_propuesta_de_lista_valida_contra_propuesta_lista(self):
        propuesta = PropuestaLista.model_validate(self.cargar("lista"))
        self.assertEqual(propuesta.evento_id, "222-IGSS-2023")
        self.assertEqual(propuesta.respuesta.tool_used, "extraer_requisitos")
        self.assertEqual({i.tipo for i in propuesta.items}, {"requisito", "fecha"})
        self.assertEqual({i.caracter for i in propuesta.items if i.tipo == "requisito"}, {"fundamental", "no_fundamental"})
        fechas = [i for i in propuesta.items if i.tipo == "fecha"]
        self.assertEqual(len(fechas), 2)
        self.assertTrue(all(i.requiere_revision and i.motivo_revision == MOTIVO_FECHAS_DISTINTAS for i in fechas))
        self.assertEqual(len({i.fuentes[0].doc_id for i in fechas}), 2)

    def test_las_fuentes_de_la_lista_salen_del_paquete_real(self):
        if not PAQUETE.exists():
            self.skipTest("falta entregables/recuperacion/empresa_demo.zip")
        with zipfile.ZipFile(PAQUETE) as z:
            reales = {c["chunk_id"]: c for c in map(json.loads, z.read("chunks.jsonl").decode().splitlines())}
        propuesta = PropuestaLista.model_validate(self.cargar("lista"))
        self.assertEqual({s.chunk_id for s in propuesta.respuesta.sources}, {i.fuentes[0].chunk_id for i in propuesta.items})
        for item in propuesta.items:
            fuente = item.fuentes[0]
            with self.subTest(chunk=fuente.chunk_id):
                real = reales[fuente.chunk_id]
                self.assertEqual((real["doc_id"], int(real["pagina_inicio"]), real["url_origen"]),
                                 (fuente.doc_id, fuente.page, fuente.source))
                self.assertIn(fuente.cita, colapsar(real["texto"]))
                if item.tipo == "requisito":
                    self.assertIn("fundamentales", colapsar(real["seccion"]).lower())

    def test_el_ejemplo_de_lista_no_lleva_tenant_id(self):
        self.assertNotIn("tenant_id", (EJEMPLOS / "lista.json").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
