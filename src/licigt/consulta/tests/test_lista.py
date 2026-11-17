"""F5: propuesta determinista de la lista de verificación, sin red ni base de datos."""

import json
import os
import unittest
from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

from pydantic import ValidationError

from licigt.consulta.config import obtener_configuracion_llm
from licigt.consulta.esquemas import Fuente, RespuestaEstructurada, TEXTO_ABSTENCION
from licigt.consulta.herramientas import ResultadoHerramienta
from licigt.consulta.lectura import FragmentoRecuperado, fuente_desde_fragmento
from licigt.consulta.lista import (
    AVISO_LISTA, ItemPropuesto, MOTIVO_FECHAS_DISTINTAS, caracter_de_seccion, proponer_items, proponer_lista,
)
from licigt.consulta.requisitos import CONSULTAS_POR_CATEGORIA, CONSULTA_CRONOGRAMA, FechaCandidata


def frag(chunk_id, texto, seccion, doc_id="222-bases", tipo="bases", pagina=5):
    return {"chunk_id": chunk_id, "doc_id": doc_id, "tipo_documento": tipo, "version_ingesta": 1,
            "pagina_inicio": pagina, "pagina_fin": pagina, "seccion": seccion, "texto": texto,
            "url_origen": "https://ejemplo/bases.pdf", "identificador_version_oficial": None, "score": 0.9}


FUNDAMENTAL = frag("c-fund", "El oferente debe presentar constancia de inscripción en el RTU actualizada.",
                   "2.8 Requisitos fundamentales")
NO_FUNDAMENTAL = frag("c-nofund", "Se solicita presentar fotocopia simple de la patente de comercio.",
                      "2.9 Requisitos no fundamentales")
PIE = frag("c-pie", "Todo documento debe presentarse foliado y firmado por el representante.", "Pie de página")
FECHA_BASES = frag("c-f1", "La recepción de ofertas se llevará a cabo el 31 de julio de 2023, a las 11:00 horas",
                   "2.2 Cronograma")
FECHA_MOD = frag("c-f2", "En Salones Los Volcanes, el día 06 de octubre de 2023, a las 11:00 horas",
                 "2.2 Cronograma", doc_id="222-mod", tipo="modificacion", pagina=1)
CITA_FUND = "constancia de inscripción en el RTU actualizada"
CITA_NOFUND = "fotocopia simple de la patente de comercio"
CITA_PIE = "foliado y firmado por el representante"


def fragmento(datos):
    return FragmentoRecuperado.model_validate(datos)


def fuente(datos, cita):
    return fuente_desde_fragmento(fragmento(datos), cita)


def fecha(datos, literal, dia, actividad=None, estado="no_verificada"):
    return FechaCandidata(chunk_id=datos["chunk_id"], doc_id=datos["doc_id"], tipo_documento=datos["tipo_documento"],
                          pagina=datos["pagina_inicio"], literal=literal, fecha=dia, actividad=actividad,
                          estado=estado)


def resultado(fragmentos, *, fechas=(), categorias=None, warnings=(), revisar=False):
    return ResultadoHerramienta(
        herramienta="extraer_requisitos", evento_id="222", fragmentos=[fragmento(f) for f in fragmentos],
        fechas=list(fechas), categorias=categorias or {}, abstener=False, needs_human_review=revisar,
        coverage_status="sin_faltantes_detectados", warnings=list(warnings), error=None)


def respuesta(fuentes, *, answer="Respuesta [1]", revisar=False, herramienta="extraer_requisitos"):
    return RespuestaEstructurada(
        answer=answer, sources=fuentes, abstained=False, tool_used=herramienta, needs_human_review=revisar,
        evento_id="222", coverage_status="sin_faltantes_detectados", warnings=[])


class ProponerItemsTests(unittest.TestCase):
    def test_ningun_item_sale_del_texto_de_answer(self):
        r = respuesta([fuente(FUNDAMENTAL, CITA_FUND)],
                      answer="Se exige la constancia del RTU [1]. Se exige también la solvencia fiscal.")
        items = proponer_items(r, resultado([FUNDAMENTAL]))
        self.assertEqual([i.descripcion for i in items], [CITA_FUND])
        self.assertNotIn("solvencia", repr(items))

    def test_abstencion_aclaracion_y_otras_herramientas_dan_lista_vacia(self):
        res = resultado([FUNDAMENTAL])
        abstencion = RespuestaEstructurada(
            answer=TEXTO_ABSTENCION, sources=[], abstained=True, tool_used="extraer_requisitos",
            needs_human_review=False, evento_id="222", coverage_status="sin_faltantes_detectados")
        aclaracion = RespuestaEstructurada(
            answer="¿Cuál?", sources=[], abstained=False, tool_used=None, needs_human_review=False,
            evento_id="222", coverage_status="sin_faltantes_detectados", needs_clarification=True,
            clarification_question="¿Cuál?")
        buscar = respuesta([fuente(FUNDAMENTAL, CITA_FUND)], herramienta="buscar_documentos")
        for r in (abstencion, aclaracion, buscar):
            self.assertEqual(proponer_items(r, res), [])

    def test_222_dos_fechas_distintas_de_recepcion_van_con_revision(self):
        fechas = [fecha(FECHA_BASES, "31 de julio de 2023", date(2023, 7, 31), "recepcion_ofertas", "verificada"),
                  fecha(FECHA_MOD, "06 de octubre de 2023", date(2023, 10, 6), "recepcion_ofertas", "verificada")]
        res = resultado([FECHA_BASES, FECHA_MOD], fechas=fechas,
                        warnings=["fechas_distintas: recepcion_ofertas"], revisar=True)
        items = proponer_items(respuesta([fuente(FECHA_BASES, "recepción de ofertas se llevará a cabo")], revisar=True),
                               res)
        recepcion = [i for i in items if i.tipo == "fecha"]
        self.assertEqual([i.descripcion for i in recepcion],
                         ["Recepción de ofertas: 31 de julio de 2023", "Recepción de ofertas: 06 de octubre de 2023"])
        self.assertTrue(all(i.requiere_revision and i.motivo_revision == MOTIVO_FECHAS_DISTINTAS for i in recepcion))

    def test_fecha_sin_verificar_y_fuera_del_cronograma(self):
        fechas = [fecha(FECHA_BASES, "31 de julio de 2023", date(2023, 7, 31)),
                  fecha(FECHA_MOD, "06 de octubre de 2023", date(2023, 10, 6), "ninguna", "fuera_del_cronograma")]
        items = proponer_items(respuesta([fuente(FUNDAMENTAL, CITA_FUND)]),
                               resultado([FUNDAMENTAL, FECHA_BASES, FECHA_MOD], fechas=fechas))
        fechas_item = [i for i in items if i.tipo == "fecha"]
        self.assertEqual([i.descripcion for i in fechas_item], ["Fecha sin verificar: 31 de julio de 2023"])
        self.assertTrue(fechas_item[0].requiere_revision)
        self.assertEqual(fechas_item[0].fuentes[0].cita, "31 de julio de 2023")

    def test_fecha_verificada_unica_no_pide_revision(self):
        fechas = [fecha(FECHA_BASES, "31 de julio de 2023", date(2023, 7, 31), "recepcion_ofertas", "verificada")]
        items = proponer_items(respuesta([fuente(FUNDAMENTAL, CITA_FUND)]),
                               resultado([FUNDAMENTAL, FECHA_BASES], fechas=fechas))
        self.assertFalse([i for i in items if i.tipo == "fecha"][0].requiere_revision)

    def test_caracter_segun_la_seccion_del_fragmento(self):
        fuentes = [fuente(FUNDAMENTAL, CITA_FUND), fuente(NO_FUNDAMENTAL, CITA_NOFUND), fuente(PIE, CITA_PIE)]
        items = proponer_items(respuesta(fuentes), resultado([FUNDAMENTAL, NO_FUNDAMENTAL, PIE]))
        self.assertEqual([i.caracter for i in items], ["fundamental", "no_fundamental", "no_indicado"])
        self.assertEqual(caracter_de_seccion(None), "no_indicado")
        self.assertEqual(caracter_de_seccion("REQUISITOS  NO  FUNDAMENTALES"), "no_fundamental")

    def test_categoria_sale_de_la_consulta_que_recupero_el_fragmento(self):
        items = proponer_items(respuesta([fuente(FUNDAMENTAL, CITA_FUND), fuente(PIE, CITA_PIE)]),
                               resultado([FUNDAMENTAL, PIE], categorias={"c-fund": "legal"}))
        self.assertEqual([i.categoria for i in items], ["legal", None])

    def test_revision_de_la_respuesta_llega_a_todos_los_requisitos(self):
        items = proponer_items(respuesta([fuente(FUNDAMENTAL, CITA_FUND), fuente(PIE, CITA_PIE)], revisar=True),
                               resultado([FUNDAMENTAL, PIE]))
        self.assertTrue(all(i.requiere_revision and i.motivo_revision for i in items))
        items = proponer_items(respuesta([fuente(PIE, CITA_PIE)]), resultado([PIE]))
        self.assertFalse(items[0].requiere_revision)

    def test_no_repite_items(self):
        f = fuente(FUNDAMENTAL, CITA_FUND)
        otra = fuente(FUNDAMENTAL, "El oferente debe presentar constancia de inscripción")
        items = proponer_items(respuesta([f, f, otra]), resultado([FUNDAMENTAL]))
        self.assertEqual(len(items), 2)

    def test_item_no_admite_texto_libre(self):
        f = fuente(FUNDAMENTAL, CITA_FUND)
        base = dict(tipo="requisito", categoria=None, caracter="no_indicado", fuentes=[f],
                    requiere_revision=False, motivo_revision=None)
        ItemPropuesto(descripcion=CITA_FUND, **base)
        with self.assertRaises(ValidationError):
            ItemPropuesto(descripcion="El oferente debe presentar todo", **base)
        fecha_base = dict(base, tipo="fecha", fuentes=[fuente(FECHA_BASES, "31 de julio de 2023")])
        ItemPropuesto(descripcion="Recepción de ofertas: 31 de julio de 2023", **fecha_base)
        for libre in ("Recepción libre: 31 de julio de 2023", "31 de julio de 2023", "Fecha sin verificar: otra"):
            with self.subTest(libre=libre), self.assertRaises(ValidationError):
                ItemPropuesto(descripcion=libre, **fecha_base)
        with self.assertRaises(ValidationError):
            ItemPropuesto(descripcion=CITA_FUND, **dict(base, requiere_revision=True))
        with self.assertRaises(ValidationError):
            ItemPropuesto(descripcion=CITA_FUND, **dict(base, extra="x"))
        self.assertIn("no certifican cumplimiento", AVISO_LISTA)


class RecuperadorPorConsulta:
    def __init__(self, por_consulta):
        self.por_consulta = por_consulta

    def buscar(self, ctx, evento_id, pregunta, variante="mejorada", k=5, conn=None):
        return {"evento_id": "222", "variante": "mejorada", "suficiente": True, "alertas": [],
                "fragmentos": self.por_consulta.get(pregunta, [])}

    def comparar_versiones(self, ctx, evento_id, pregunta, k=2, conn=None):
        raise AssertionError("proponer_lista no compara versiones")


class GeneradorFalso:
    modelo_generador = "generador-falso"

    def __init__(self, salida=None, error=None):
        self.salida, self.error, self.llamadas = salida, error, 0

    def generar(self, mensajes, esquema, semilla_extra=0):
        self.llamadas += 1
        if self.error:
            raise self.error
        return json.dumps(self.salida)


def salida_requisito():
    return {"abstener": False, "revision_humana": False, "afirmaciones": [
        {"texto": "Se exige constancia de inscripción en el RTU.",
         "citas": [{"fragmento": "F1", "cita": CITA_FUND}], "datos": []}]}


class ProponerListaTests(unittest.TestCase):
    def setUp(self):
        self.ctx = SimpleNamespace(tenant_id="empresa-a", usuario="persona-a", rol="analista")
        self.eventos = []
        self.recuperador = RecuperadorPorConsulta({
            CONSULTAS_POR_CATEGORIA["legal"]: [FUNDAMENTAL], CONSULTA_CRONOGRAMA: [FECHA_BASES]})
        self.entorno = patch.dict(os.environ, {}, clear=True)
        self.entorno.start()
        obtener_configuracion_llm.cache_clear()

    def tearDown(self):
        self.entorno.stop()
        obtener_configuracion_llm.cache_clear()

    def test_devuelve_items_con_fuentes_validadas_y_audita(self):
        generador = GeneradorFalso(salida_requisito())
        p = proponer_lista(self.ctx, "222", "legal", recuperador=self.recuperador, generador=generador,
                           auditar=self.eventos.append)
        self.assertFalse(p.respuesta.abstained)
        requisito, fecha_item = p.items
        self.assertEqual((requisito.tipo, requisito.descripcion, requisito.caracter, requisito.categoria),
                         ("requisito", CITA_FUND, "fundamental", "legal"))
        self.assertEqual(requisito.fuentes, [s for s in p.respuesta.sources if s.chunk_id == "c-fund"])
        self.assertEqual(fecha_item.descripcion, "Fecha sin verificar: 31 de julio de 2023")
        self.assertTrue(fecha_item.requiere_revision)
        self.assertEqual(len(self.eventos), 1)
        evento = self.eventos[0]
        self.assertEqual(evento["intencion"], {"accion": "proponer_lista"})
        self.assertEqual((evento["usuario"], evento["tenant_id"]), ("persona-a", "empresa-a"))
        self.assertNotIn("constancia", repr(evento))

    def test_generador_caido_abstiene_con_lista_vacia(self):
        p = proponer_lista(self.ctx, "222", recuperador=self.recuperador,
                           generador=GeneradorFalso(error=RuntimeError("secreto remoto")),
                           auditar=self.eventos.append)
        self.assertTrue(p.respuesta.abstained)
        self.assertEqual(p.items, [])
        self.assertNotIn("secreto remoto", repr(p))
        self.assertEqual(len(self.eventos), 1)

    def test_evento_invalido_abstiene_sin_llamar_nada(self):
        generador = GeneradorFalso(salida_requisito())
        p = proponer_lista(self.ctx, "  ", recuperador=self.recuperador, generador=generador,
                           auditar=self.eventos.append)
        self.assertTrue(p.respuesta.abstained)
        self.assertEqual((p.items, generador.llamadas), ([], 0))
        self.assertEqual(self.eventos[0]["error"], "parametros_invalidos")


if __name__ == "__main__":
    unittest.main()
