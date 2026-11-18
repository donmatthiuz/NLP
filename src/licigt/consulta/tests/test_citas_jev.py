"""Citation check de JEV posterior al validador, con dobles y sin red."""

import json
import os
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from licigt.consulta.citas_jev import AUTO_ACCEPT, aplicar_citas, citas_activas
from licigt.consulta.config import obtener_configuracion_llm
from licigt.consulta.enrutador import EnrutadorReglas
from licigt.consulta.esquemas import RespuestaEstructurada
from licigt.consulta.jev import FallaJev, RespuestaJev
from licigt.consulta.lectura import fuente_desde_fragmento
from licigt.consulta.orquestador import consultar
from licigt.consulta.tests.test_generacion import fragmentos_222
from licigt.consulta.tests.test_orquestador import GeneradorFalso, RecuperadorFalso

OPCIONES = ("supports", "contradicts", "says_nothing")


def respuesta_citas(elecciones, confianza=0.95):
    """Una respuesta de JEV por afirmación: a1, a2, ..."""
    respuestas = {}
    for i, eleccion in enumerate(elecciones, 1):
        resto = (1 - confianza) / 2
        respuestas[f"a{i}"] = {
            "type": "choice", "choice": eleccion, "confidence": confianza,
            "probabilities": {o: (confianza if o == eleccion else resto) for o in OPCIONES}}
    return RespuestaJev(respuestas=respuestas, modelo="jev-1.14.0", request_id="r",
                        tokens_entrada=10, tokens_salida=2)


class JevCitasFalso:
    def __init__(self, respuesta=None, error=None):
        self.respuesta, self.error, self.llamadas = respuesta, error, []

    def preguntar(self, estado, preguntas):
        self.llamadas.append((estado, preguntas))
        if self.error:
            raise self.error
        return self.respuesta


def respuesta_222():
    base, mod = fragmentos_222()
    fuentes = [fuente_desde_fragmento(base, "La recepción de ofertas se llevará a cabo el 31 de julio de 2023"),
               fuente_desde_fragmento(mod, "el día 06 de octubre de 2023")]
    r = RespuestaEstructurada(
        answer="Las bases indican recepción el 31 de julio de 2023. [1]\n"
               "La modificación indica recepción el 06 de octubre de 2023. [2]",
        sources=fuentes, abstained=False, tool_used="buscar_documentos", needs_human_review=False,
        evento_id="222", coverage_status="sin_faltantes_detectados", warnings=["previo"])
    return r, [base, mod]


class CitasJevTests(unittest.TestCase):
    def test_todo_respaldado_no_cambia_nada(self):
        r, frags = respuesta_222()
        jev = JevCitasFalso(respuesta_citas(["supports", "supports"]))
        salida, auditoria = aplicar_citas(r, frags, jev)
        self.assertEqual(salida, r)
        self.assertEqual(auditoria["modelo"], "jev-1.14.0")
        self.assertEqual(auditoria["codigos"], ["supports", "supports"])

    def test_pregunta_es_choice_de_tres_opciones_sobre_afirmacion_y_seccion(self):
        r, frags = respuesta_222()
        jev = JevCitasFalso(respuesta_citas(["supports", "supports"]))
        aplicar_citas(r, frags, jev)
        estado, preguntas = jev.llamadas[0]
        self.assertEqual(set(preguntas), {"a1", "a2"})
        for p in preguntas.values():
            self.assertEqual(p["type"], "choice")
            self.assertEqual(tuple(p["criteria"]), OPCIONES)
        self.assertEqual(estado["a1"]["claim"], "Las bases indican recepción el 31 de julio de 2023.")
        self.assertEqual(estado["a1"]["section"], frags[0].texto)
        self.assertEqual(set(estado["a1"]), {"claim", "section"})

    def test_no_sale_tenant_usuario_ni_pregunta_ni_marcadores(self):
        r, frags = respuesta_222()
        jev = JevCitasFalso(respuesta_citas(["supports", "supports"]))
        aplicar_citas(r, frags, jev)
        carga = json.dumps(jev.llamadas, ensure_ascii=False)
        for privado in ("empresa-privada", "persona-privada", "[1]", "[2]", "222", "chunk"):
            self.assertNotIn(privado, carga)

    def test_contradice_o_nada_escala_y_avisa_sin_cambiar_texto(self):
        for eleccion in ("contradicts", "says_nothing"):
            with self.subTest(eleccion=eleccion):
                r, frags = respuesta_222()
                jev = JevCitasFalso(respuesta_citas(["supports", eleccion]))
                salida, auditoria = aplicar_citas(r, frags, jev)
                self.assertEqual(salida.answer, r.answer)
                self.assertEqual(salida.sources, r.sources)
                self.assertFalse(salida.abstained)
                self.assertTrue(salida.needs_human_review)
                self.assertEqual(salida.warnings, ["previo", "cita_sin_respaldo_jev: 1"])
                self.assertEqual(auditoria["codigos"], ["supports", eleccion])

    def test_confianza_bajo_el_umbral_cuenta_como_sin_respaldo(self):
        self.assertEqual(AUTO_ACCEPT, 0.8)
        r, frags = respuesta_222()
        jev = JevCitasFalso(respuesta_citas(["supports", "supports"], confianza=0.7))
        salida, auditoria = aplicar_citas(r, frags, jev)
        self.assertEqual(salida.warnings[-1], "cita_sin_respaldo_jev: 2")
        self.assertTrue(salida.needs_human_review)
        self.assertEqual(auditoria["codigos"], ["baja_confianza", "baja_confianza"])

    def test_jev_caido_avisa_y_no_escala(self):
        r, frags = respuesta_222()
        for error in (FallaJev("api"), FallaJev("respuesta_incompleta")):
            salida, auditoria = aplicar_citas(r, frags, JevCitasFalso(error=error))
            self.assertEqual(salida.warnings, ["previo", "citas_jev_no_disponible"])
            self.assertFalse(salida.needs_human_review)
            self.assertEqual(auditoria, {"modelo": None, "codigos": [error.codigo]})

    def test_sin_cliente_es_no_disponible(self):
        r, frags = respuesta_222()
        salida, _ = aplicar_citas(r, frags, None)
        self.assertEqual(salida.warnings, ["previo", "citas_jev_no_disponible"])
        self.assertFalse(salida.needs_human_review)

    def test_abstencion_y_aclaracion_no_llaman_a_jev(self):
        r, frags = respuesta_222()
        abst = r.model_copy(update={"answer": "No hay información suficiente", "sources": [], "abstained": True})
        jev = JevCitasFalso(respuesta_citas([]))
        salida, auditoria = aplicar_citas(abst, frags, jev)
        self.assertEqual(salida, abst)
        self.assertIsNone(auditoria)
        self.assertEqual(jev.llamadas, [])

    def test_interruptor_apagado_por_defecto(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(citas_activas())
        for valor, esperado in (("0", False), ("1", True), ("", False)):
            with patch.dict(os.environ, {"LICIGT_CITAS_JEV": valor}, clear=True):
                self.assertEqual(citas_activas(), esperado)

    def test_casos_citas_json_formato_y_seis_ejemplos_del_222(self):
        ruta = Path(__file__).parent.parent / "casos_citas.json"
        casos = json.loads(ruta.read_text(encoding="utf-8"))
        self.assertEqual(len(casos), 6)
        self.assertEqual(sorted(c["fiel"] for c in casos), [False] * 3 + [True] * 3)
        for c in casos:
            self.assertEqual(set(c), {"id", "afirmacion", "seccion", "fiel"})


class OrquestadorCitasTests(unittest.TestCase):
    def setUp(self):
        self.ctx = SimpleNamespace(tenant_id="empresa-privada", usuario="persona-privada", rol="analista")
        self.eventos = []
        obtener_configuracion_llm.cache_clear()

    def correr(self, entorno, jev):
        with patch.dict(os.environ, entorno, clear=True):
            obtener_configuracion_llm.cache_clear()
            return consultar(self.ctx, "222", "¿Dónde se reciben ofertas?", enrutador=EnrutadorReglas(),
                             recuperador=RecuperadorFalso(), generador=GeneradorFalso(),
                             cliente_jev=jev, auditar=self.eventos.append)

    def test_apagado_no_llama_a_jev(self):
        jev = JevCitasFalso(respuesta_citas(["says_nothing", "says_nothing"]))
        r = self.correr({}, jev)
        self.assertEqual(jev.llamadas, [])
        self.assertFalse([w for w in r.warnings if "jev" in w])
        self.assertNotIn("citas_jev", self.eventos[0])

    def test_encendido_escala_y_audita_codigos_sin_texto(self):
        jev = JevCitasFalso(respuesta_citas(["supports", "says_nothing"]))
        r = self.correr({"LICIGT_CITAS_JEV": "1"}, jev)
        self.assertTrue(r.needs_human_review)
        self.assertIn("cita_sin_respaldo_jev: 1", r.warnings)
        self.assertEqual(self.eventos[0]["citas_jev"], {"modelo": "jev-1.14.0",
                                                        "codigos": ["supports", "says_nothing"]})

    def test_encendido_con_jev_caido_no_escala(self):
        base = self.correr({}, None)
        r = self.correr({"LICIGT_CITAS_JEV": "1"}, JevCitasFalso(error=FallaJev("api")))
        self.assertIn("citas_jev_no_disponible", r.warnings)
        self.assertEqual(r.needs_human_review, base.needs_human_review)
        self.assertEqual(r.answer, base.answer)


if __name__ == "__main__":
    unittest.main()
