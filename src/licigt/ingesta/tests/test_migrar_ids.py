import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from licigt.ingesta.migrar_ids import calcular_equivalencias, ids_con_otro_texto, migrar

DOC = "a" * 32


def chunk(indice, texto, pagina=1):
    return {"chunk_id": f"{DOC}:{indice:05d}", "doc_id": DOC, "pagina_inicio": pagina, "texto": texto}


def paquete(ruta: Path, chunks) -> Path:
    with zipfile.ZipFile(ruta, "w") as z:
        z.writestr("chunks.jsonl", "".join(json.dumps(c) + "\n" for c in chunks))
    return ruta


class EquivalenciasTests(unittest.TestCase):
    def test_texto_identico_con_otro_numero_y_contenido_en_la_tabla(self):
        with tempfile.TemporaryDirectory() as t:
            t = Path(t)
            viejo = paquete(t / "v.zip", [
                chunk(1, "uno dos tres cuatro cinco seis siete ocho nueve diez", 1),
                chunk(2, "fecha 31 julio 2023 recepcion ofertas lugar sede", 2),
                chunk(3, "sin relacion alguna palabras raras xyz", 3)])
            nuevo = paquete(t / "n.zip", [
                chunk(5, "uno dos tres cuatro cinco seis siete ocho nueve diez", 1),
                chunk(6, "| 2.2.1 | recepcion ofertas | fecha 31 julio 2023 lugar sede |", 2)])
            tabla = calcular_equivalencias(viejo, nuevo, [f"{DOC}:00001", f"{DOC}:00002", f"{DOC}:00003"])
        self.assertEqual(tabla[f"{DOC}:00001"]["nuevo"], f"{DOC}:00005")
        self.assertEqual(tabla[f"{DOC}:00001"]["estado"], "identico")
        self.assertEqual(tabla[f"{DOC}:00002"]["nuevo"], f"{DOC}:00006")
        self.assertEqual(tabla[f"{DOC}:00002"]["estado"], "contenido")
        self.assertIsNone(tabla[f"{DOC}:00003"]["nuevo"])
        self.assertEqual(tabla[f"{DOC}:00003"]["estado"], "revision")

    def test_el_mismo_texto_en_otra_pagina_no_es_equivalente(self):
        # Una entrada de índice de la página 3 ("4. TÉCNICAS") no equivale al título igual de la página 32.
        with tempfile.TemporaryDirectory() as t:
            t = Path(t)
            viejo = paquete(t / "v.zip", [chunk(1, "4. TECNICAS", 3), chunk(2, "texto aparte de la página 32", 32)])
            nuevo = paquete(t / "n.zip", [chunk(7, "4. TECNICAS", 32), chunk(8, "texto aparte de la página 32", 32)])
            tabla = calcular_equivalencias(viejo, nuevo, [f"{DOC}:00001", f"{DOC}:00002"])
        self.assertEqual(tabla[f"{DOC}:00001"]["estado"], "revision")
        self.assertIsNone(tabla[f"{DOC}:00001"]["nuevo"])
        self.assertEqual(tabla[f"{DOC}:00002"]["nuevo"], f"{DOC}:00008")

    def test_el_numero_de_pagina_o_el_pie_quitado_no_cuenta_en_la_comparacion(self):
        with tempfile.TemporaryDirectory() as t:
            t = Path(t)
            viejo = paquete(t / "v.zip", [chunk(1, "Artículo 62 Bis de su REGLAMENTO.\n\n27", 2),
                                          chunk(2, "Se hará efectivo en el caso siguiente\n    9   Extensión: 99175", 3)])
            nuevo = paquete(t / "n.zip", [chunk(1, "Artículo 62 Bis de su REGLAMENTO.", 2),
                                          chunk(2, "Se hará efectivo en el caso siguiente", 3)])
            tabla = calcular_equivalencias(viejo, nuevo, [f"{DOC}:00001", f"{DOC}:00002"])
        self.assertEqual(tabla[f"{DOC}:00001"]["estado"], "contenido")
        self.assertEqual(tabla[f"{DOC}:00002"]["estado"], "contenido")

    def test_cada_id_viejo_con_otro_texto_tiene_su_entrada(self):
        with tempfile.TemporaryDirectory() as t:
            t = Path(t)
            viejo = paquete(t / "v.zip", [chunk(1, "primero igual"), chunk(2, "segundo texto largo aqui", 1),
                                          chunk(3, "tercero se desplaza", 2), chunk(4, "cuarto | igual ya", 2)])
            nuevo = paquete(t / "n.zip", [chunk(1, "primero  igual"), chunk(2, "nuevo fragmento intercalado", 1),
                                          chunk(3, "segundo texto largo aqui", 1), chunk(4, "tercero se desplaza", 2),
                                          chunk(5, "cuarto | igual ya", 2)])
            cambiados = ids_con_otro_texto(viejo, nuevo)
            tabla = calcular_equivalencias(viejo, nuevo, cambiados)
        self.assertEqual(cambiados, [f"{DOC}:00002", f"{DOC}:00003", f"{DOC}:00004"])
        self.assertEqual(tabla[f"{DOC}:00002"]["nuevo"], f"{DOC}:00003")
        self.assertEqual(tabla[f"{DOC}:00003"]["nuevo"], f"{DOC}:00004")
        self.assertEqual(tabla[f"{DOC}:00004"]["nuevo"], f"{DOC}:00005")
        self.assertNotIn(f"{DOC}:00001", tabla)


class MigrarTests(unittest.TestCase):
    def setUp(self):
        self.viejo, self.nuevo, self.dudoso = f"{DOC}:00001", f"{DOC}:00007", f"{DOC}:00002"
        self.tabla = {self.viejo: {"nuevo": self.nuevo, "estado": "identico"},
                      self.dudoso: {"nuevo": None, "estado": "revision"},
                      f"{DOC}:00007": {"nuevo": f"{DOC}:00009", "estado": "identico"}}

    def test_vista_previa_no_escribe_y_aplicar_reemplaza_en_una_pasada(self):
        with tempfile.TemporaryDirectory() as t:
            archivo = Path(t) / "x.md"
            original = f"cita {self.viejo} y {self.dudoso} y {self.nuevo}\n"
            archivo.write_text(original, encoding="utf-8")
            previa = migrar([archivo], self.tabla, aplicar=False)
            self.assertEqual(archivo.read_text(encoding="utf-8"), original)
            self.assertEqual(previa["reemplazos"], 2)
            self.assertEqual(previa["revision"], [self.dudoso])
            migrar([archivo], self.tabla, aplicar=True)
            self.assertEqual(archivo.read_text(encoding="utf-8"),
                             f"cita {self.nuevo} y {self.dudoso} y {DOC}:00009\n")


if __name__ == "__main__":
    unittest.main()
