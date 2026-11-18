"""Reporte de evaluación del rol 4, con dobles: sin red, base de datos ni LLM."""

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from licigt.consulta.banco import CasoBanco
from licigt.plataforma import evaluacion
from licigt.plataforma.evaluacion import (
    casos_a_evaluar, comprobar_aislamiento, correr_pruebas, escribir_reporte, estimar_por_100, leer_entero_entorno,
    medir_concurrencia, medir_consultas, percentil, render_markdown, resumen_concurrencia, resumen_latencia,
    resumen_tokens, suite_seguridad,
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


class ConcurrenciaTests(unittest.TestCase):
    DOCS = {"empresa_demo": {"d1", "d2"}, "empresa_b": {"b1"}}
    CTXS = [SimpleNamespace(tenant_id="empresa_demo"), SimpleNamespace(tenant_id="empresa_b")]

    def correr(self, consultar, preguntas, usuarios=5, reloj=None, **kw):
        propio = {"empresa_demo": "222", "empresa_b": "363"}
        resolver = lambda ctx, evento: "i-" + evento if (ctx.tenant_id == "empresa_demo") == (evento != "363") else None
        return medir_concurrencia(preguntas, contextos=self.CTXS, resolver=resolver, enrutador=None,
                                  recuperador=None, generador=None, consultar=consultar, usuarios=usuarios,
                                  evento_propio=propio, **({"reloj": reloj} if reloj else {}), **kw)

    @staticmethod
    def salida(*doc_ids, herramienta="buscar_documentos"):
        return SimpleNamespace(tool_used=herramienta, sources=[SimpleNamespace(doc_id=d) for d in doc_ids])

    def test_corre_en_rondas_de_cinco_hilos_realmente_en_paralelo(self):
        import threading
        barrera = threading.Barrier(5, timeout=5)
        activos = set()

        def consultar(ctx, evento, pregunta, **kw):
            barrera.wait()  # solo pasa si los 5 hilos están dentro a la vez
            activos.add(threading.get_ident())
            return self.salida()
        preguntas = [(f"p{i}", "222", "q") for i in range(10)]
        muestras = self.correr(consultar, preguntas)
        self.assertEqual(len(muestras), 10)
        self.assertEqual(len(activos), 5)
        self.assertEqual([m["id"] for m in muestras], [f"p{i}" for i in range(10)])
        self.assertTrue(all("segundos" in m and m["usuarios"] == 5 for m in muestras))

    def test_alterna_empresa_por_hilo_y_sustituye_el_evento_ajeno(self):
        vistos = {}

        def consultar(ctx, evento, pregunta, **kw):
            vistos[pregunta] = (ctx.tenant_id, evento)
            return self.salida()
        preguntas = [(f"p{i}", "222", f"q{i}") for i in range(4)]
        muestras = self.correr(consultar, preguntas, usuarios=4)
        self.assertEqual([vistos[f"q{i}"][0] for i in range(4)], ["empresa_demo", "empresa_b"] * 2)
        self.assertEqual(vistos["q1"][1], "i-363")  # empresa_b no tiene el 222: usa su evento
        self.assertTrue(muestras[1]["evento_sustituido"])
        self.assertFalse(muestras[0]["evento_sustituido"])

    def test_error_de_una_consulta_no_rompe_a_las_demas(self):
        def consultar(ctx, evento, pregunta, **kw):
            if pregunta == "malo":
                raise RuntimeError("x")
            return self.salida("d1")
        muestras = self.correr(consultar, [("a", "222", "malo"), ("b", "222", "bien")], usuarios=2)
        self.assertEqual(muestras[0]["error"], "RuntimeError")
        self.assertNotIn("error", muestras[1])

    def test_aislamiento_detecta_fuente_de_la_otra_empresa(self):
        def consultar(ctx, evento, pregunta, **kw):
            return self.salida("b1") if ctx.tenant_id == "empresa_demo" else self.salida("b1")
        muestras = self.correr(consultar, [("a", "222", "q"), ("b", "222", "q")], usuarios=2)
        a = comprobar_aislamiento(muestras, self.DOCS)
        self.assertEqual(a["fuentes_revisadas"], 2)
        self.assertEqual([(v["id"], v["tenant"], v["doc_id"]) for v in a["violaciones"]], [("a", "empresa_demo", "b1")])

    def test_aislamiento_limpio(self):
        def consultar(ctx, evento, pregunta, **kw):
            return self.salida("d1") if ctx.tenant_id == "empresa_demo" else self.salida("b1")
        muestras = self.correr(consultar, [("a", "222", "q"), ("b", "222", "q")], usuarios=2)
        self.assertEqual(comprobar_aislamiento(muestras, self.DOCS), {"fuentes_revisadas": 2, "violaciones": []})

    def test_resumen_con_p50_p95_por_herramienta_y_fallidas(self):
        muestras = [{"id": f"p{i}", "tenant": "empresa_demo", "herramienta": "buscar_documentos",
                     "segundos": float(i), "doc_ids": ["d1"]} for i in range(1, 11)]
        muestras += [{"id": "x", "tenant": "empresa_b", "herramienta": None, "segundos": 1.0, "doc_ids": []},
                     {"id": "f", "tenant": "empresa_b", "error": "RuntimeError", "segundos": 0.1}]
        r = resumen_concurrencia(muestras, self.DOCS, usuarios=5, slots=1)
        self.assertEqual(r["usuarios"], 5)
        self.assertEqual(r["slots_llama_server"], 1)
        self.assertEqual(r["latencia"]["total"]["n"], 11)
        self.assertEqual(r["latencia"]["total"]["p95_s"], 10.0)
        self.assertEqual(r["latencia"]["por_herramienta"]["buscar_documentos"]["p50_s"], 5.0)
        self.assertEqual(r["fallidas"], ["f"])
        self.assertEqual(r["aislamiento"]["violaciones"], [])

    def test_render_incluye_el_bloque_de_concurrencia(self):
        muestras = [{"id": "a", "tenant": "empresa_demo", "herramienta": "buscar_documentos", "segundos": 2.0,
                     "doc_ids": ["d1"]}]
        r = reporte(concurrencia=resumen_concurrencia(muestras, self.DOCS, usuarios=5, slots=1))
        md = render_markdown(r)
        self.assertIn("## Latencia con 5 usuarios simultáneos", md)
        self.assertIn("1 slot", md)
        self.assertIn("Violaciones de aislamiento: 0", md)

    def test_render_sin_concurrencia_no_lo_menciona(self):
        self.assertNotIn("simultáneos", render_markdown(reporte()))

    def test_variable_de_entorno_entera(self):
        self.assertEqual(leer_entero_entorno({}, "X", 5), 5)
        self.assertEqual(leer_entero_entorno({"X": "0"}, "X", 5), 0)
        self.assertEqual(leer_entero_entorno({"X": "12"}, "X", 5), 12)
        self.assertEqual(leer_entero_entorno({"X": ""}, "X", 5), 5)
        with self.assertRaises(ValueError):
            leer_entero_entorno({"X": "abc"}, "X", 5)


if __name__ == "__main__":
    unittest.main()
