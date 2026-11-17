"""F5: propuesta determinista de la lista de verificación, sin red ni base de datos."""

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
    tramo_literal,
)
from licigt.consulta.lista_escritura import _fuente_vigente
from licigt.consulta.tests.test_generacion import DATOS_222
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
# C14: la cita de la propuesta es el primer tramo legible del fragmento, no un recorte elegido por un modelo.
CITA_FUND = FUNDAMENTAL["texto"]
CITA_NOFUND = NO_FUNDAMENTAL["texto"]
CITA_PIE = PIE["texto"]


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


class TramoLiteralTests(unittest.TestCase):
    def test_c14_toma_hasta_el_salto_doble_y_colapsa_espacios(self):
        texto = "El oferente  debe presentar\nconstancia de inscripción.\n\nOtro párrafo que no entra."
        self.assertEqual(tramo_literal(texto), "El oferente debe presentar constancia de inscripción.")

    def test_c14_corta_en_el_ultimo_fin_de_oracion_antes_de_300(self):
        oracion = "El oferente debe presentar la constancia de inscripción en el RTU actualizada."
        texto = " ".join([oracion] * 6)
        tramo = tramo_literal(texto)
        self.assertLessEqual(len(tramo), 300)
        self.assertTrue(tramo.endswith("actualizada."))
        self.assertIn(tramo, texto)

    def test_c14_sin_fin_de_oracion_corta_en_palabra(self):
        texto = " ".join(["documento"] * 80)
        tramo = tramo_literal(texto)
        self.assertLessEqual(len(tramo), 300)
        self.assertTrue(tramo.endswith("documento"))
        self.assertIn(tramo, texto)

    def test_c14_columnas_intercaladas_toman_la_primera_linea_sin_separacion(self):
        texto = ("Lugar, dirección, fecha y hora para           En Salones Los Volcanes, ubicados\n"
                 "El oferente debe presentar el formulario firmado por el representante legal.\n"
                 "              la recepción de OFERTAS.                      22-72 zona 1")
        self.assertEqual(tramo_literal(texto),
                         "El oferente debe presentar el formulario firmado por el representante legal.")

    def test_c14_222_real_con_columnas_da_un_tramo_literal(self):
        for datos in DATOS_222:
            tramo = tramo_literal(datos["texto"])
            self.assertTrue(tramo)
            self.assertNotIn("   ", tramo)
            self.assertIn(tramo, " ".join(datos["texto"].split()))

    def test_c14_texto_vacio_no_da_tramo(self):
        self.assertIsNone(tramo_literal("   \n\n  "))


class ProponerItemsTests(unittest.TestCase):
    def test_c14_un_item_por_fragmento_con_categoria_en_el_orden_de_la_herramienta(self):
        res = resultado([PIE, FUNDAMENTAL, NO_FUNDAMENTAL, FECHA_BASES],
                        categorias={"c-fund": "legal", "c-nofund": "administrativa", "c-pie": "tecnica"})
        items = proponer_items(res, "222")
        self.assertEqual([i.fuentes[0].chunk_id for i in items], ["c-pie", "c-fund", "c-nofund"])
        self.assertEqual([i.categoria for i in items], ["tecnica", "legal", "administrativa"])
        for i in items:
            self.assertEqual(i.descripcion, i.fuentes[0].cita)
            self.assertEqual(i.tipo, "requisito")

    def test_c14_sin_categoria_no_hay_item(self):
        self.assertEqual(proponer_items(resultado([FUNDAMENTAL, FECHA_BASES]), "222"), [])

    def test_222_dos_fechas_distintas_de_recepcion_van_con_revision(self):
        fechas = [fecha(FECHA_BASES, "31 de julio de 2023", date(2023, 7, 31), "recepcion_ofertas", "verificada"),
                  fecha(FECHA_MOD, "06 de octubre de 2023", date(2023, 10, 6), "recepcion_ofertas", "verificada")]
        res = resultado([FECHA_BASES, FECHA_MOD], fechas=fechas,
                        warnings=["fechas_distintas: recepcion_ofertas"], revisar=True)
        items = proponer_items(res, "222")
        recepcion = [i for i in items if i.tipo == "fecha"]
        self.assertEqual([i.descripcion for i in recepcion],
                         ["Recepción de ofertas: 31 de julio de 2023", "Recepción de ofertas: 06 de octubre de 2023"])
        self.assertTrue(all(i.requiere_revision and i.motivo_revision == MOTIVO_FECHAS_DISTINTAS for i in recepcion))

    def test_fecha_sin_verificar_y_fuera_del_cronograma(self):
        fechas = [fecha(FECHA_BASES, "31 de julio de 2023", date(2023, 7, 31)),
                  fecha(FECHA_MOD, "06 de octubre de 2023", date(2023, 10, 6), "ninguna", "fuera_del_cronograma")]
        items = proponer_items(resultado([FUNDAMENTAL, FECHA_BASES, FECHA_MOD], fechas=fechas,
                                         categorias={"c-fund": "legal"}), "222")
        fechas_item = [i for i in items if i.tipo == "fecha"]
        self.assertEqual([i.descripcion for i in fechas_item], ["Fecha sin verificar: 31 de julio de 2023"])
        self.assertTrue(fechas_item[0].requiere_revision)
        self.assertEqual(fechas_item[0].fuentes[0].cita, "31 de julio de 2023")

    def test_fecha_verificada_unica_no_pide_revision(self):
        fechas = [fecha(FECHA_BASES, "31 de julio de 2023", date(2023, 7, 31), "recepcion_ofertas", "verificada")]
        items = proponer_items(resultado([FUNDAMENTAL, FECHA_BASES], fechas=fechas, categorias={"c-fund": "legal"}),
                               "222")
        self.assertFalse([i for i in items if i.tipo == "fecha"][0].requiere_revision)

    def test_caracter_segun_la_seccion_del_fragmento(self):
        categorias = {"c-fund": "legal", "c-nofund": "legal", "c-pie": "legal"}
        items = proponer_items(resultado([FUNDAMENTAL, NO_FUNDAMENTAL, PIE], categorias=categorias), "222")
        self.assertEqual([i.caracter for i in items], ["fundamental", "no_fundamental", "no_indicado"])
        self.assertEqual(caracter_de_seccion(None), "no_indicado")
        self.assertEqual(caracter_de_seccion("REQUISITOS  NO  FUNDAMENTALES"), "no_fundamental")

    def test_revision_por_conflicto_llega_a_todos_los_requisitos(self):
        categorias = {"c-fund": "legal", "c-pie": "legal"}
        items = proponer_items(resultado([FUNDAMENTAL, PIE], categorias=categorias, revisar=True), "222")
        self.assertTrue(all(i.requiere_revision and i.motivo_revision for i in items))
        items = proponer_items(resultado([PIE], categorias={"c-pie": "legal"}), "222")
        self.assertFalse(items[0].requiere_revision)

    def test_no_repite_items(self):
        copia = dict(FUNDAMENTAL, chunk_id="c-fund")  # mismo chunk_id y mismo tramo
        res = resultado([FUNDAMENTAL, copia], categorias={"c-fund": "legal"})
        self.assertEqual(len(proponer_items(res, "222")), 1)

    def test_c14_cada_cita_es_subcadena_literal_y_pasa_la_revalidacion_de_guardar(self):
        fragmentos = [dict(f, chunk_id=f"r-{n}", seccion="2.8 Requisitos fundamentales")
                      for n, f in enumerate(DATOS_222)] + [FUNDAMENTAL, NO_FUNDAMENTAL, PIE]
        res = resultado(fragmentos, categorias={f["chunk_id"]: "legal" for f in fragmentos})
        items = proponer_items(res, "222")
        self.assertGreaterEqual(len(items), 3)
        por_chunk = {f.chunk_id: f for f in res.fragmentos}
        for item in items:
            f = por_chunk[item.fuentes[0].chunk_id]
            self.assertIn(item.descripcion, " ".join(f.texto.split()))
            self.assertTrue(_fuente_vigente(item, f), item.descripcion)

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


class GeneradorProhibido:
    """C14: la propuesta no genera nada; cualquier llamada rompe la prueba."""
    modelo_generador = "prohibido"

    def generar(self, *args, **kwargs):
        raise AssertionError("la propuesta de lista no llama al generador")


class JevDeLista:
    def __init__(self):
        self.llamadas = []

    def preguntar(self, estado, preguntas):
        from licigt.consulta.jev import RespuestaJev
        from licigt.consulta.preguntas_jev import ACTIVIDADES_CRONOGRAMA
        self.llamadas.append(estado)
        respuestas = {}
        for identificador in estado["candidatas"]:
            p = {a: 0.01 for a in ACTIVIDADES_CRONOGRAMA}
            p["recepcion_ofertas"] = 0.9
            respuestas[f"actividad_{identificador}"] = {
                "type": "choice", "choice": "recepcion_ofertas", "probabilities": p, "confidence": 0.01}
            respuestas[f"respaldo_{identificador}"] = {"type": "noul", "noul": 0.9}
        return RespuestaJev(respuestas=respuestas, modelo="jev-falso", request_id=None,
                            tokens_entrada=None, tokens_salida=None)


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

    def proponer(self, categoria="legal", **extra):
        return proponer_lista(self.ctx, "222", categoria, recuperador=self.recuperador,
                              auditar=self.eventos.append, **extra)

    def test_devuelve_items_con_fuentes_validadas_y_audita(self):
        p = self.proponer()
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

    def test_c14_no_acepta_ni_llama_a_un_generador(self):
        with self.assertRaises(TypeError):
            proponer_lista(self.ctx, "222", "legal", recuperador=self.recuperador,
                           generador=GeneradorProhibido())
        self.assertFalse(self.proponer().respuesta.abstained)

    def test_c14_222_real_tiene_items_y_pasan_la_revalidacion(self):
        recuperador = RecuperadorPorConsulta({
            CONSULTAS_POR_CATEGORIA["legal"]: DATOS_222, CONSULTA_CRONOGRAMA: DATOS_222})
        p = proponer_lista(self.ctx, "222", "legal", recuperador=recuperador, auditar=self.eventos.append)
        self.assertFalse(p.respuesta.abstained)
        requisitos = [i for i in p.items if i.tipo == "requisito"]
        self.assertEqual(len(requisitos), 2)
        por_chunk = {d["chunk_id"]: fragmento(d) for d in DATOS_222}
        for item in requisitos:
            self.assertTrue(_fuente_vigente(item, por_chunk[item.fuentes[0].chunk_id]))

    def test_c14_con_jev_las_fechas_se_verifican(self):
        jev = JevDeLista()
        p = self.proponer(cliente_jev=jev)
        self.assertEqual(len(jev.llamadas), 1)
        fecha_item = [i for i in p.items if i.tipo == "fecha"][0]
        self.assertEqual(fecha_item.descripcion, "Recepción de ofertas: 31 de julio de 2023")
        self.assertFalse(fecha_item.requiere_revision)

    def test_c14_sin_items_abstiene(self):
        recuperador = RecuperadorPorConsulta({CONSULTA_CRONOGRAMA: [PIE]})
        p = proponer_lista(self.ctx, "222", "legal", recuperador=recuperador, auditar=self.eventos.append)
        self.assertTrue(p.respuesta.abstained)
        self.assertEqual((p.items, len(self.eventos)), ([], 1))

    def test_c14_recuperador_caido_abstiene_con_lista_vacia(self):
        class Caido:
            def buscar(self, *a, **k):
                raise RuntimeError("secreto remoto")

        p = proponer_lista(self.ctx, "222", recuperador=Caido(), auditar=self.eventos.append)
        self.assertTrue(p.respuesta.abstained)
        self.assertEqual(p.items, [])
        self.assertNotIn("secreto remoto", repr(p))
        self.assertEqual(len(self.eventos), 1)

    def test_evento_invalido_abstiene_sin_llamar_nada(self):
        p = proponer_lista(self.ctx, "  ", recuperador=self.recuperador, auditar=self.eventos.append)
        self.assertTrue(p.respuesta.abstained)
        self.assertEqual(p.items, [])
        self.assertEqual(self.eventos[0]["error"], "parametros_invalidos")


if __name__ == "__main__":
    unittest.main()
