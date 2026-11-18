import json
import os
import re
import unittest
import zipfile
from pathlib import Path

from licigt.ingesta.pdf import Page
from licigt.ingesta.pipeline import HEADING, _units, _without_repeated_margins, make_chunks
from licigt.ingesta.tests.test_pipeline import metadata

RAIZ = Path(__file__).resolve().parents[4]
ZIP_ACTUAL = Path(os.environ.get("LICIGT_ZIP_CORPUS") or RAIZ / "entregables" / "recuperacion" / "empresa_demo.zip")
ZIP_VIEJO = RAIZ / "entregables" / "recuperacion" / "empresa_demo.zip"


PALABRAS = ["alfa", "bravo", "cobre", "delta", "eco", "fuego", "gamma", "helio", "indio", "jade"]


def paginas_con_pie(n=6, pie="{n} Extensión: 99175"):
    # El cuerpo cambia en palabras, no solo en dígitos: enmascarados, los números lo harían repetirse.
    return [Page(i, f"Cuerpo propio {PALABRAS[i]} con texto suficiente.\nOtra línea distinta {PALABRAS[-i]}.\n"
                 + pie.format(n=i), "text", "ok") for i in range(1, n + 1)]


class PiesConNumeroTests(unittest.TestCase):
    def test_el_pie_con_numero_se_quita_en_todas_las_paginas(self):
        limpias = _without_repeated_margins(paginas_con_pie())
        for pagina in limpias:
            self.assertNotIn("Extensión", pagina.text)
            self.assertIn("Cuerpo propio", pagina.text)

    def test_los_numeros_de_uno_y_dos_digitos_y_los_espacios_cuentan_igual(self):
        paginas = paginas_con_pie(6, pie="{n}      Extensión:   99175")
        paginas[2] = Page(3, paginas[2].text.replace("3      Extensión:", "25 Extensión:"), "text", "ok")
        self.assertFalse([p for p in _without_repeated_margins(paginas) if "Extensión" in p.text])

    def test_el_texto_original_se_conserva_y_el_fragmento_no_lleva_el_pie(self):
        paginas = paginas_con_pie()
        _without_repeated_margins(paginas)
        self.assertIn("Extensión: 99175", paginas[0].text)
        chunks = make_chunks(paginas, "d" * 32, metadata(), 1)
        self.assertFalse([c for c in chunks if "Extensión" in c["texto"] or "Extensión" in c["seccion"]])

    def test_una_linea_de_contenido_con_numeral_en_dos_paginas_de_un_documento_largo_no_se_quita(self):
        paginas = paginas_con_pie(8)
        for i in (0, 1):
            paginas[i] = Page(i + 1, "2.2.1 Plazo de entrega del producto\n" + paginas[i].text, "text", "ok")
        limpias = _without_repeated_margins(paginas)
        self.assertIn("2.2.1 Plazo de entrega", limpias[0].text)
        self.assertIn("2.2.1 Plazo de entrega", limpias[1].text)

    def test_en_un_documento_corto_el_pie_ya_no_es_titulo_y_se_quita_pero_un_titulo_no(self):
        paginas = paginas_con_pie(3)
        self.assertFalse([p for p in _without_repeated_margins(paginas) if "Extensión" in p.text])
        con_titulo = [Page(i, f"2.1 DOCUMENTOS DE LICITACIÓN\nCuerpo {PALABRAS[i]} suficiente para la prueba.", "text", "ok")
                      for i in (1, 2, 3)]
        self.assertTrue(all("2.1 DOCUMENTOS" in p.text for p in _without_repeated_margins(con_titulo)))


class MargenesSoloConNumeroDePaginaTests(unittest.TestCase):
    def test_una_modificacion_de_tres_paginas_conserva_sus_puntos_y_la_seccion(self):
        textos = [
            "Se emite la modificación.\nPunto 1:\nSe modifica el subnumeral 2.2 CRONOGRAMA DE ACTIVIDADES, así.\nTexto alfa.",
            "Continúa el texto.\nPunto 2:\nSe modifica el subnumeral 2.7 LISTADO DE DOCUMENTOS QUE DEBERÁ CONTENER LA PLICA, así.\nTexto bravo.",
            "Final.\nPunto 3:\nSe aclara lo demás.\nTexto cobre.",
        ]
        paginas = [Page(i + 1, t, "text", "ok") for i, t in enumerate(textos)]
        limpias = _without_repeated_margins(paginas)
        self.assertIn("Punto 1:", limpias[0].text)
        self.assertIn("Punto 2:", limpias[1].text)
        self.assertIn("Punto 3:", limpias[2].text)
        chunks = make_chunks(paginas, "d" * 32, metadata(tipo_documento="modificacion"), 1)
        solvencia = next(c for c in chunks if "Punto 2:" in c["texto"])
        self.assertTrue(solvencia["seccion"].startswith("2.7"), solvencia["seccion"])

    def test_un_oficio_conserva_las_dos_fechas(self):
        paginas = [Page(1, "Guatemala, 10 de octubre de 2023\nAsunto: primero con texto.", "text", "ok"),
                   Page(2, "Guatemala, 12 de octubre de 2023\nAsunto: segundo con texto.", "text", "ok")]
        limpias = _without_repeated_margins(paginas)
        self.assertIn("10 de octubre de 2023", limpias[0].text)
        self.assertIn("12 de octubre de 2023", limpias[1].text)

    def test_los_numeros_de_pagina_sueltos_siguen_cayendo(self):
        paginas = [Page(i, f"Cuerpo {PALABRAS[i]} suficiente.\nOtra {PALABRAS[-i]} línea.\n{i}", "text", "ok")
                   for i in range(1, 7)]
        self.assertFalse([p for p in _without_repeated_margins(paginas) if p.text.splitlines()[-1].isdigit()])

    def test_una_linea_que_solo_difiere_en_un_numero_interior_no_se_enmascara(self):
        paginas = [Page(i, f"Artículo {i} del acuerdo número {i} y más.\nCuerpo {PALABRAS[i]} suficiente.", "text", "ok")
                   for i in range(1, 7)]
        self.assertTrue(all("Artículo" in p.text for p in _without_repeated_margins(paginas)))


class MascaraDelNumeroFinalTests(unittest.TestCase):
    def test_cantidades_distintas_al_final_de_la_linea_se_conservan(self):
        paginas = [Page(1, "Cantidad requerida 252\nCuerpo alfa suficiente.", "text", "ok"),
                   Page(2, "Cantidad requerida 396\nCuerpo bravo suficiente.", "text", "ok")]
        limpias = _without_repeated_margins(paginas)
        self.assertIn("Cantidad requerida 252", limpias[0].text)
        self.assertIn("Cantidad requerida 396", limpias[1].text)

    def test_los_pies_de_pagina_y_extension_siguen_cayendo(self):
        paginas = [Page(i, f"Cuerpo {PALABRAS[i]} suficiente.\nPágina {i}\n{i}", "text", "ok") for i in range(1, 3)]
        self.assertTrue(all("Página" not in p.text for p in _without_repeated_margins(paginas)))


class SeccionTrasElIndiceTests(unittest.TestCase):
    def test_un_indice_con_cuerpo_en_la_pagina_deja_el_ultimo_titulo_vigente(self):
        p31 = Page(31, "2.32 FACTURA ELECTRÓNICA\nTexto de la factura electrónica y su emisión.\n\n"
                   "3. ESPECIFICACIONES GENERALES\n\n4. ESPECIFICACIONES TÉCNICAS", "text", "ok")
        p32 = Page(32, "Texto de las especificaciones técnicas del producto.", "text", "ok")
        chunks = make_chunks([p31, p32], "d" * 32, metadata(), 1)
        self.assertTrue(chunks[-1]["seccion"].startswith("4."), chunks[-1]["seccion"])


@unittest.skipUnless(ZIP_ACTUAL.is_file(), "requiere el paquete del corpus")
class OcrNoSeFundeTests(unittest.TestCase):
    def test_las_paginas_ocr_de_la_modificacion_conservan_el_ruido_fuera_del_indice(self):
        from licigt.ingesta.pipeline import SourceMetadata, paginas_sin_indexables
        from licigt.ingesta.reextraer import MIN_PALABRAS_OCR, PALABRA
        with zipfile.ZipFile(ZIP_ACTUAL) as z:
            inventario = json.loads(z.read("inventario.json"))
            entrada = next(d for d in inventario["documents"] if d["doc_id"].startswith("d41480"))
            manifiesto = json.loads(z.read(entrada["manifiesto_zip_path"]))
        paginas = [Page(**p) for p in manifiesto["pages"]]
        ocr = [p for p in paginas if p.method == "ocr"]
        self.assertEqual([p.number for p in ocr], [3, 4])
        nuevos = make_chunks(ocr, manifiesto["doc_id"], SourceMetadata(**manifiesto["metadata"]), manifiesto["version_ingesta"])
        for c in nuevos:
            c["indexable"] = len(PALABRA.findall(c["texto"])) >= MIN_PALABRAS_OCR
        previos = [c for c in manifiesto["chunks"] if c["pagina_inicio"] <= 2]
        self.assertEqual(paginas_sin_indexables([p.number for p in paginas], previos + nuevos), [4])
        self.assertEqual([c["chunk_id"] for c in nuevos if c["indexable"] and "( AO $" in c["texto"]], [])


class TituloTests(unittest.TestCase):
    SI = ["2.7 LISTADO DE DOCUMENTOS QUE DEBERÁ CONTENER LA PLICA", "2.27.3 Que incurra en alguna causal",
          "4. ESPECIFICACIONES TÉCNICAS", "6. ANEXO (S)", "5.5 Texto.", "ARTÍCULO 15 DISPOSICIONES FINALES", "Anexo 1: Formulario de identificación del oferente",
          "Artículo 5. Del objeto del contrato", "Capítulo II. De las garantías",
          "ANEXO 3 FORMULARIO ELECTRÓNICO", "1) DISPOSICIONES FINALES"]
    NO = ["3 del Decreto Número 295 del Congreso", "37 de la LEY. En los casos en los que",
          "5 mg/ml, vial de vidrio con tapa", "33 y 35 de la LEY).", "Artículo 55 de la LEY.", "Numeral 15 del Decreto Número 27-92, del Congreso", "Numeral 15 del Decreto Número 27-92",
          "Artículo 62 Bis de su REGLAMENTO", "Capítulo III del Título XIII", "Artículo 16 del Acuerdo Gubernativo Número 122-2016",
          "numeral 4. (Artículos 18 y 20 del Decreto Número 57-92)", "Artículo 2 numeral 12 del Acuerdo Gubernativo",
          "Capítulo III del Título XIII del Decreto Número 17-73", "ANEXO 6.2 de los presentes DOCUMENTOS DE LICITACIÓN.", "2 vial, Código IGSS 10527, requerido",
          "8. Clasificación o categoría del deudor de conformidad con la normativa",
          "1. Si el adjudicatario no sostiene su OFERTA.", "9 Extensión: 99175", "25"]

    def test_son_titulos(self):
        self.assertEqual([t for t in self.SI if not HEADING.match(t)], [])

    def test_no_son_titulos(self):
        self.assertEqual([t for t in self.NO if HEADING.match(t)], [])

    def test_una_linea_de_lista_conserva_la_seccion_vigente(self):
        pagina = Page(1, "2.7 LISTADO DE DOCUMENTOS\nIntro.\n\n8. Clasificación o categoría del deudor de la normativa\n"
                      "p) Solvencia o cualquier otro documento vigente.", "text", "ok")
        chunks = make_chunks([pagina], "d" * 32, metadata(), 1)
        self.assertEqual({c["seccion"] for c in chunks}, {"2.7 LISTADO DE DOCUMENTOS"})


class IndiceHermanoTests(unittest.TestCase):
    def test_un_titulo_padre_del_siguiente_no_es_indice(self):
        pagina = Page(1, "5.5 Texto.\n\n6. ANEXO (S)\n6.1 Instructivo para el llenado\n6.2 Formulario electrónico\n"
                      "FORMULARIO ELECTRÓNICO.", "text", "ok")
        chunks = make_chunks([pagina], "d" * 32, metadata(), 1)
        anexo = next(c for c in chunks if "6. ANEXO (S)" in c["texto"])
        self.assertEqual(anexo["seccion"], "6. ANEXO (S)")
        self.assertEqual(chunks[-1]["seccion"], "6.2 Formulario electrónico")

    def test_padre_e_hijo_titulo_solo_en_la_pagina_31_dejan_3_1_en_la_32(self):
        p31 = Page(31, "2.32 FACTURA ELECTRÓNICA\nTexto de la factura.\n\n3. ESPECIFICACIONES GENERALES\n\n3.1 ALCANCE", "text", "ok")
        p32 = Page(32, "Texto del alcance de las especificaciones.", "text", "ok")
        chunks = make_chunks([p31, p32], "d" * 32, metadata(), 1)
        self.assertEqual(chunks[-1]["pagina_inicio"], 32)
        self.assertEqual(chunks[-1]["seccion"], "3.1 ALCANCE")

    def test_tres_hermanos_en_mayusculas_se_juntan_y_con_minusculas_no(self):
        mayus = Page(1, "1. UNO\n2. DOS\n3. TRES", "text", "ok")
        self.assertEqual(len(_units(mayus, "Sin sección")[0]), 1)
        minus = Page(1, "1. Uno aparte\n2. Dos aparte\n3. Tres aparte", "text", "ok")
        self.assertEqual(len(_units(minus, "Sin sección")[0]), 1)  # no son títulos: un solo párrafo

    def test_entradas_de_indice_con_numerales_de_dos_niveles_hermanas_se_juntan(self):
        pagina = Page(1, "1.1 UNO\n1.2 DOS\n1.3 TRES", "text", "ok")
        unidades, seccion = _units(pagina, "Sin sección")
        self.assertEqual(len(unidades), 1)
        self.assertEqual(seccion, "Sin sección")


class EntradasDelIndiceTests(unittest.TestCase):
    INDICE = Page(3, "CONTENIDO DE LOS DOCUMENTOS\n1. TERMINOLOGÍA\n2. BASES DE LICITACIÓN\n3. ESPECIFICACIONES GENERALES\n"
                  "4. ESPECIFICACIONES TÉCNICAS\n5. DISPOSICIONES ESPECIALES\n6. ANEXOS", "text", "ok")
    CUERPO = Page(4, "1. TERMINOLOGÍA\n1.1 ANEXO (S)\nApartado de estos documentos que forman parte del proceso.", "text", "ok")

    def test_seis_titulos_seguidos_son_una_unidad_con_la_seccion_vigente_antes(self):
        unidades, seccion = _units(self.INDICE, "Sin sección")
        titulos = [u for u in unidades if "1. TERMINOLOGÍA" in u["texto"]]
        self.assertEqual(len(titulos), 1)
        self.assertEqual(len(unidades), 2)  # el rótulo "CONTENIDO..." y las seis entradas juntas
        self.assertEqual(titulos[0]["seccion"], "Sin sección")
        self.assertIn("6. ANEXOS", titulos[0]["texto"])
        self.assertEqual(seccion, "Sin sección")

    def test_la_seccion_correcta_vuelve_en_la_pagina_siguiente(self):
        chunks = make_chunks([self.INDICE, self.CUERPO], "d" * 32, metadata(), 1)
        self.assertEqual([c["pagina_inicio"] for c in chunks], [3, 4, 4])
        self.assertEqual(chunks[0]["seccion"], "Sin sección")
        self.assertEqual(chunks[1]["seccion"], "1. TERMINOLOGÍA")
        self.assertEqual(chunks[2]["seccion"], "1.1 ANEXO (S)")

    def test_el_texto_del_indice_no_se_pierde(self):
        chunks = make_chunks([self.INDICE], "d" * 32, metadata(), 1)
        self.assertEqual(" ".join(" ".join(c["texto"] for c in chunks).split()), " ".join(self.INDICE.text.split()))

    def test_un_titulo_solo_con_cuerpo_aparte_no_se_junta(self):
        pagina = Page(1, "2.1 PRIMERO\nTexto del primero.\n\n2.2 SEGUNDO\n\nCuerpo del segundo tras línea en blanco.", "text", "ok")
        unidades, _ = _units(pagina, "Sin sección")
        self.assertEqual([u["seccion"] for u in unidades], ["2.1 PRIMERO", "2.2 SEGUNDO", "2.2 SEGUNDO"])

    def test_un_titulo_aislado_no_se_toca(self):
        pagina = Page(1, "Texto previo.\n\n2.2 UNICO TITULO\n", "text", "ok")
        unidades, seccion = _units(pagina, "Sin sección")
        self.assertEqual(seccion, "2.2 UNICO TITULO")


@unittest.skipUnless(ZIP_ACTUAL.is_file(), "requiere el paquete del corpus")
class CorpusSinPiesNiIndiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with zipfile.ZipFile(ZIP_ACTUAL) as z:
            cls.chunks = [json.loads(l) for l in z.read("chunks.jsonl").splitlines() if l.strip()]

    PIE = re.compile(r"Extensi[óo]n:\s*99175|PBX:\s*2412", re.I)

    def test_ninguna_seccion_es_un_pie(self):
        self.assertEqual([c["chunk_id"] for c in self.chunks if self.PIE.search(c["seccion"])], [])

    def test_ningun_fragmento_contiene_solo_un_pie(self):
        solos = [c["chunk_id"] for c in self.chunks
                 if self.PIE.search(c["texto"]) and len(c["texto"].split()) <= 8]
        self.assertEqual(solos, [])

    def test_los_pies_que_quedan_son_los_datos_de_contacto_de_la_portada(self):
        # La portada no lleva número de página, así que su "Extensión: 99175" o "PBX: 2412-1224" no se repite
        # enmascarado; es el dato de contacto de la portada y se conserva. En las demás páginas no queda ninguno.
        sueltos = [(c["chunk_id"], c["pagina_inicio"]) for c in self.chunks
                   for linea in c["texto"].splitlines()
                   if re.match(r"^\s*\d*\s*(Extensi[óo]n:\s*99175|PBX:\s*2412)", linea) and c["pagina_inicio"] != 1]
        self.assertEqual(sueltos, [])

    def test_en_ninguna_pagina_quedan_dos_entradas_hermanas_de_indice_seguidas(self):
        def solo_titulo(c):
            return (len(c["texto"].strip().splitlines()) == 1 and HEADING.match(c["texto"].strip())
                    and c["texto"] == c["texto"].upper())
        def nivel(c):
            return re.match(r"\d+(?:\.\d+)*", c["texto"].strip()).group(0)
        seguidas = [(a["chunk_id"], b["chunk_id"]) for a, b in zip(self.chunks, self.chunks[1:])
                    if a["doc_id"] == b["doc_id"] and a["pagina_inicio"] == b["pagina_inicio"]
                    and solo_titulo(a) and solo_titulo(b) and not nivel(b).startswith(nivel(a) + ".")]
        self.assertEqual(seguidas, [])

    def test_el_literal_p_de_la_plica_lleva_la_seccion_2_7(self):
        c = next(c for c in self.chunks if c["doc_id"].startswith("4182413774fa4149")
                 and re.search(r"p\)\s+Solvencia o cualquier otro documento", c["texto"]))
        self.assertTrue(c["seccion"].startswith("2.7"), c["seccion"])

    def test_no_quedan_secciones_de_un_nivel_con_frase_en_minusculas(self):
        malas = sorted({c["seccion"] for c in self.chunks
                        if re.match(r"^\d+(?!\.\d)[.)]?\s+", c["seccion"]) and re.search(r"[a-záéíóúñ]", c["seccion"])})
        self.assertEqual(malas, [])

    def test_ninguna_entrada_de_indice_queda_sola(self):
        titulo = re.compile(r"^\d+(\.\d+)*[.)]?\s+[A-ZÁÉÍÓÚÑ ,/()-]{3,}$")
        sueltas = [c["chunk_id"] for c in self.chunks
                   if c["pagina_inicio"] == 3 and len(c["texto"].strip().splitlines()) == 1
                   and titulo.match(c["texto"].strip())]
        self.assertEqual(sueltas, [])

    @staticmethod
    def _chunks(ruta):
        with zipfile.ZipFile(ruta) as z:
            return [json.loads(l) for l in z.read("chunks.jsonl").splitlines() if l.strip()]

    @classmethod
    def _lineas(cls, ruta, con_seccion=False):
        tabla = {}
        for c in cls._chunks(ruta):
            for linea in c["texto"].splitlines():
                if linea.strip():
                    clave = (c["doc_id"], c["pagina_inicio"], " ".join(linea.split()))
                    tabla.setdefault(clave, []).append((c["seccion"], c["metodo_extraccion"], c["pagina_impresa"]))
        return tabla

    def test_el_texto_y_la_pagina_solo_cambian_por_los_pies_quitados(self):
        if ZIP_ACTUAL == ZIP_VIEJO:
            self.skipTest("el paquete del repo aún es el viejo")
        viejas, nuevas = self._lineas(ZIP_VIEJO), self._lineas(ZIP_ACTUAL)
        pie = re.compile(r"(\d{1,3})(?: Extensi[óo]n: 99175)?")
        # Las páginas OCR no se funden (B1): su texto de ruido y de membrete queda en fragmentos no indexables, fuera
        # del paquete; solo se exigen las demás páginas.
        quitadas = [k for k, v in viejas.items()
                    if len(nuevas.get(k, [])) < len(v) and not all(m == "ocr" for _, m, _ in v)]
        self.assertTrue(quitadas)
        self.assertEqual([k for k in quitadas if not pie.fullmatch(k[2])], [])
        # el número quitado es el de la página impresa del fragmento
        for doc, pagina, linea in quitadas:
            impresa = {i for _, _, i in viejas[(doc, pagina, linea)]}
            self.assertIn(int(pie.fullmatch(linea).group(1)), impresa, (doc, pagina, linea))
        # ni líneas duplicadas ni líneas nuevas ni páginas distintas; salvo el OCR, donde el texto de ruido que
        # antes quedaba en fragmentos no indexables (y fuera del paquete) ahora se junta con su fragmento vecino
        nuevas_en_texto = [k for k, v in nuevas.items()
                           if len(v) > len(viejas.get(k, [])) and not all(m == "ocr" for _, m, _ in v)]
        self.assertEqual(nuevas_en_texto, [])

    # Líneas cuya sección cambia respecto de R5 por la regla nueva de título (R7): la sección de R5 era una línea de
    # lista o una cita que ya no es título. Las entradas del índice (la línea es su propia sección) también cambian.
    def test_toda_linea_conserva_su_seccion_salvo_por_la_regla_de_titulo(self):
        if ZIP_ACTUAL == ZIP_VIEJO:
            self.skipTest("el paquete del repo aún es el viejo")
        viejas, nuevas = self._lineas(ZIP_VIEJO), self._lineas(ZIP_ACTUAL)
        cambian = []
        for clave, valores in viejas.items():
            if clave not in nuevas:
                continue
            seccion_vieja = valores[0][0]
            if self.PIE.search(seccion_vieja):
                continue
            if nuevas[clave][0][0] != seccion_vieja:
                cambian.append((clave, seccion_vieja, nuevas[clave][0][0]))
        no_explicados = [c for c in cambian
                         if HEADING.match(c[1].strip()) and c[0][2] != c[1].strip() and c[1] != "Sin sección"]
        self.assertEqual(no_explicados, [])


EQUIVALENCIAS = Path(__file__).resolve().parents[1] / "equivalencias_r6.json"


@unittest.skipUnless(ZIP_ACTUAL.is_file() and EQUIVALENCIAS.is_file(), "requiere el paquete y la tabla")
class EquivalenciasR6Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tabla = json.loads(EQUIVALENCIAS.read_text(encoding="utf-8"))["equivalencias"]

    def test_cada_id_viejo_con_otro_texto_tiene_su_entrada(self):
        if ZIP_ACTUAL == ZIP_VIEJO:
            self.skipTest("el paquete del repo ya es el nuevo; la tabla ya se aplicó")
        from licigt.ingesta.migrar_ids import ids_con_otro_texto
        faltan = [i for i in ids_con_otro_texto(ZIP_VIEJO, ZIP_ACTUAL) if i not in self.tabla]
        self.assertEqual(faltan, [])

    def test_los_ids_nuevos_de_la_tabla_existen_en_el_paquete(self):
        with zipfile.ZipFile(ZIP_ACTUAL) as z:
            chunks = [json.loads(l) for l in z.read("chunks.jsonl").splitlines() if l.strip()]
        if any(re.search(r"Extensi[óo]n: ?99175", c["seccion"]) for c in chunks):
            self.skipTest("el paquete aún es el anterior a R6")
        ids = {c["chunk_id"] for c in chunks}
        self.assertEqual([e["nuevo"] for e in self.tabla.values() if e["nuevo"] and e["nuevo"] not in ids], [])
        self.assertTrue(all(e["estado"] != "revision" or e["nuevo"] is None for e in self.tabla.values()))


if __name__ == "__main__":
    unittest.main()
