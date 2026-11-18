"""Reporte de evaluación del rol 4, con dobles: sin red, base de datos ni LLM."""

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from licigt.consulta.banco import CasoBanco
from licigt.plataforma import evaluacion
from licigt.plataforma.evaluacion import (
    casos_a_evaluar, correr_pruebas, escribir_reporte, estimar_por_100, medir_consultas, percentil,
    render_markdown, resumen_latencia, resumen_tokens, suite_seguridad,
)


def caso(**cambios):
    datos = {"id": "c1", "evento": "222-IGSS-2023", "question": "¿Dónde se reciben ofertas?",
             "expected_behavior": "x", "expected_sources": [{"tipo_documento": "bases", "paginas": [8, 9]}],
             "expected_pages": [8, 9], "answerable": True, "risk_level": "bajo"}
    datos.update(cambios)
    return CasoBanco.model_validate(datos)


class ConversionTests(unittest.TestCase):
    def test_expected_sources_pasa_al_formato_relevantes(self):
        (c,) = casos_a_evaluar([caso()])
        self.assertEqual(c, {"id": "c1", "evento": "222-IGSS-2023", "pregunta": "¿Dónde se reciben ofertas?",
                             "relevantes": [{"tipo_documento": "bases", "paginas": [8, 9]}]})

    def test_fuente_sin_paginas_usa_expected_pages(self):
        (c,) = casos_a_evaluar([caso(expected_sources=[{"tipo_documento": "bases"}], expected_pages=[3])])
        self.assertEqual(c["relevantes"], [{"tipo_documento": "bases", "paginas": [3]}])

    def test_no_respondible_queda_sin_relevantes(self):
        (c,) = casos_a_evaluar([caso(answerable=False, expected_sources=[], expected_pages=[])])
        self.assertEqual(c["relevantes"], [])

    def test_se_omiten_pendientes_sin_evento_y_respondibles_sin_fuente(self):
        casos = [caso(id="a", pendiente="x"), caso(id="b", evento=None),
                 caso(id="c", expected_sources=[], expected_pages=[]), caso(id="d")]
        self.assertEqual([c["id"] for c in casos_a_evaluar(casos)], ["d"])


class PreguntasTests(unittest.TestCase):
    def test_pregunta_del_enrutador_sin_evento_usa_el_evento_por_defecto(self):
        with tempfile.TemporaryDirectory() as d:
            ruta = Path(d) / "ciego.json"
            ruta.write_text(json.dumps({"casos": [{"id": "a", "evento": None, "question": "p"},
                                                  {"id": "b", "evento": "363-IGSS-2026", "question": "q"}]}))
            self.assertEqual(evaluacion._preguntas(ruta, ciego=True),
                             [("a", evaluacion.EVENTO_POR_DEFECTO, "p"), ("b", "363-IGSS-2026", "q")])


class MetricasTests(unittest.TestCase):
    def test_percentil_por_rango_mas_cercano(self):
        valores = list(range(1, 101))
        self.assertEqual(percentil(valores, 95), 95)
        self.assertEqual(percentil(valores, 50), 50)
        self.assertEqual(percentil([3.0], 95), 3.0)
        self.assertEqual(percentil([4, 1, 3, 2], 95), 4)
        self.assertIsNone(percentil([], 95))

    def test_latencia_total_y_por_herramienta(self):
        muestras = [{"herramienta": "buscar_documentos", "segundos": s} for s in (1, 2, 3, 4)] + \
                   [{"herramienta": "extraer_requisitos", "segundos": 10.0},
                    {"herramienta": None, "segundos": 0.5}]
        r = resumen_latencia(muestras)
        self.assertEqual(r["total"], {"n": 6, "p50_s": 2.0, "p95_s": 10.0, "max_s": 10.0})
        self.assertEqual(r["por_herramienta"]["buscar_documentos"]["p95_s"], 4)
        self.assertEqual(r["por_herramienta"]["extraer_requisitos"]["n"], 1)
        self.assertEqual(r["por_herramienta"]["sin_herramienta"]["n"], 1)

    def test_tokens_por_consulta_y_estimacion_por_100(self):
        muestras = [{"segundos": 2.0, "llamadas_llm": 1, "tokens_entrada": 1000, "tokens_salida": 100},
                    {"segundos": 4.0, "llamadas_llm": 2, "tokens_entrada": 3000, "tokens_salida": 300},
                    {"segundos": 0.1, "llamadas_llm": 0, "tokens_entrada": 0, "tokens_salida": 0}]
        t = resumen_tokens(muestras)
        self.assertEqual(t["consultas"], 3)
        self.assertEqual(t["totales"], {"llamadas_llm": 3, "tokens_entrada": 4000, "tokens_salida": 400})
        self.assertAlmostEqual(t["por_consulta"]["tokens_entrada"], 4000 / 3)
        self.assertAlmostEqual(t["por_consulta"]["llamadas_llm"], 1.0)
        e = estimar_por_100(muestras)
        self.assertAlmostEqual(e["tokens_totales"], 4400 / 3 * 100)
        self.assertAlmostEqual(e["tiempo_s"], 6.1 / 3 * 100)
        self.assertEqual(e["costo_monetario"], 0)

    def test_medir_consultas_toma_la_diferencia_de_uso_del_generador(self):
        generador = SimpleNamespace(uso={"llamadas": 5, "tokens_entrada": 50, "tokens_salida": 5})
        relojes = iter([0.0, 2.5, 10.0, 11.0])

        def consultar(ctx, evento, pregunta, **kw):
            generador.uso["llamadas"] += 1
            generador.uso["tokens_entrada"] += 700
            generador.uso["tokens_salida"] += 30
            return SimpleNamespace(tool_used="buscar_documentos")

        def sin_llm(ctx, evento, pregunta, **kw):
            return SimpleNamespace(tool_used=None)

        m = medir_consultas([("a", "222", "p1")], ctx=None, resolver=lambda e: "i-" + e, enrutador=None,
                            recuperador=None, generador=generador, consultar=consultar,
                            reloj=lambda: next(relojes))
        m += medir_consultas([("b", "222", "p2")], ctx=None, resolver=lambda e: e, enrutador=None,
                             recuperador=None, generador=generador, consultar=sin_llm,
                             reloj=lambda: next(relojes))
        self.assertEqual(m[0], {"id": "a", "herramienta": "buscar_documentos", "segundos": 2.5,
                                "llamadas_llm": 1, "tokens_entrada": 700, "tokens_salida": 30})
        self.assertEqual((m[1]["segundos"], m[1]["llamadas_llm"], m[1]["tokens_entrada"]), (1.0, 0, 0))

    def test_una_consulta_que_lanza_cuenta_como_error_y_no_rompe(self):
        def falla(*a, **k):
            raise RuntimeError("x")
        (m,) = medir_consultas([("a", "222", "p")], ctx=None, resolver=lambda e: e, enrutador=None,
                               recuperador=None, generador=SimpleNamespace(), consultar=falla)
        self.assertEqual(m["error"], "RuntimeError")
        self.assertEqual(resumen_latencia([m])["total"]["n"], 0)


def registro(id, cumple=True, **extra):
    return {"id": id, "cumple": cumple, "checks": {"abstained": cumple}, "error": None, "tool_used": None,
            "abstained": True, **extra}


IDS = ["r3-seg-iny-directa", "r3-seg-iny-indirecta", "r3-seg-cita-falsa", "r3-seg-requisito-fabricado",
       "r3-seg-accion"]
PRUEBAS = {"acceso_cruzado": "ok", "mezcla_de_eventos": "ok", "original_sin_permiso": "ok"}


class SeguridadTests(unittest.TestCase):
    def test_ocho_pruebas_con_los_cinco_campos(self):
        filas = suite_seguridad([registro(i) for i in IDS], PRUEBAS)
        self.assertEqual(len(filas), 8)
        for f in filas:
            for campo in ("amenaza", "componente", "esperado", "observado", "mitigacion", "resultado"):
                self.assertTrue(f[campo], (f["id"], campo))
        self.assertEqual({f["resultado"] for f in filas}, {"cumple"})

    def test_un_caso_que_falla_sale_como_fallo(self):
        filas = suite_seguridad([registro(i, cumple=i != "r3-seg-cita-falsa") for i in IDS], PRUEBAS)
        (cita,) = [f for f in filas if f["id"] == "r3-seg-cita-falsa"]
        self.assertEqual(cita["resultado"], "falla")
        self.assertIn("abstained", cita["observado"])

    def test_prueba_de_plataforma_que_falla_o_se_omite_no_se_oculta(self):
        filas = suite_seguridad([registro(i) for i in IDS],
                                {**PRUEBAS, "acceso_cruzado": "falla", "mezcla_de_eventos": "omitida"})
        por_id = {f["id"]: f["resultado"] for f in filas}
        self.assertEqual(por_id["acceso_cruzado"], "falla")
        self.assertEqual(por_id["mezcla_de_eventos"], "no_medido")

    def test_caso_ausente_o_con_error_no_cumple(self):
        filas = suite_seguridad([registro("r3-seg-accion", cumple=False, error="RuntimeError", checks={})], PRUEBAS)
        por_id = {f["id"]: f for f in filas}
        self.assertEqual(por_id["r3-seg-accion"]["resultado"], "falla")
        self.assertEqual(por_id["r3-seg-iny-directa"]["resultado"], "no_medido")

    def test_correr_pruebas_distingue_ok_falla_y_omitida(self):
        def falla():
            raise AssertionError("x")

        def omite():
            raise unittest.SkipTest("sin base")
        suites = {n: unittest.TestSuite([unittest.FunctionTestCase(f)])
                  for n, f in (("a", lambda: None), ("b", falla), ("c", omite))}
        self.assertEqual(correr_pruebas(suites), {"a": "ok", "b": "falla", "c": "omitida"})


def reporte(**extra):
    base = {"fecha": "2026-11-18T00:00:00+00:00", "commit": "abc", "commit_sucio": True,
            "enrutador": "reglas", "modelos": {"m": "rev"}, "parametros_llm": {"modelo": "q"},
            "version_prompt": "v1", "avisos": [], "recuperacion": {}, "extremo_a_extremo": {},
            "latencia": {"total": {"n": 0, "p50_s": None, "p95_s": None, "max_s": None}, "por_herramienta": {}},
            "tokens": {"consultas": 0, "totales": {}, "por_consulta": {}}, "estimacion_100": {},
            "seguridad": suite_seguridad([registro(i) for i in IDS], PRUEBAS)}
    base.update(extra)
    return base


class SalidaTests(unittest.TestCase):
    def test_el_md_no_contiene_texto_de_respuestas(self):
        r = reporte(extremo_a_extremo={"banco_rol3": {"total": {"casos": 1, "cumplen": 1, "metricas": {}},
                                                      "casos": [registro("c1", answer="SECRETO-RESPUESTA")]}})
        md = render_markdown(r)
        self.assertNotIn("SECRETO-RESPUESTA", md)
        self.assertEqual(md.count("\n# "), 0)
        self.assertTrue(md.startswith("# "))
        self.assertNotIn("\n* ", md)

    def test_escribir_reporte_crea_json_y_md_sin_campos_ajenos(self):
        r = reporte(extremo_a_extremo={"banco_rol3": {"total": {"casos": 1}, "casos": [
            registro("c1", answer="SECRETO-RESPUESTA", texto="SECRETO-FRAGMENTO", fuentes=[
                {"chunk_id": "c:1", "page": 3, "page_end": None, "cita": "SECRETO-CITA"}])]}})
        with tempfile.TemporaryDirectory() as d:
            json_ruta, md_ruta = escribir_reporte(r, Path(d), "20261118T000000Z")
            contenido = json_ruta.read_text(encoding="utf-8") + md_ruta.read_text(encoding="utf-8")
            self.assertTrue(json_ruta.name.endswith(".json") and md_ruta.name.endswith(".md"))
            json.loads(json_ruta.read_text(encoding="utf-8"))
        for secreto in ("SECRETO-RESPUESTA", "SECRETO-FRAGMENTO", "SECRETO-CITA"):
            self.assertNotIn(secreto, contenido)

    def test_banco_comun_ausente_se_omite_con_aviso(self):
        avisos = []
        self.assertIsNone(evaluacion.cargar_banco_comun(None, avisos.append))
        self.assertIsNone(evaluacion.cargar_banco_comun("/no/existe.json", avisos.append))
        self.assertEqual(len(avisos), 2)
        self.assertTrue(all("banco común" in a for a in avisos))
        md = render_markdown(reporte(avisos=avisos))
        self.assertIn("banco común", md)


if __name__ == "__main__":
    unittest.main()
