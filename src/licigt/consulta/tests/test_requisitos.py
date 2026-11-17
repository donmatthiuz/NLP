"""Fechas y evidencia del evento 222, sin red, SDK ni base de datos."""

import json
import os
import subprocess
import sys
import unittest
from copy import deepcopy
from datetime import date
from typing import get_args

from pydantic import ValidationError

from licigt.consulta.esquemas import Categoria, ExtraerRequisitosParams
from licigt.consulta.herramientas import extraer_requisitos
from licigt.consulta.tests.test_generacion import DATOS_TABLA
from licigt.consulta.jev import FallaJev, RespuestaJev
from licigt.consulta.preguntas_jev import (
    ACTIVIDADES_CRONOGRAMA, MAX_CANDIDATAS_JEV, preguntas_fechas,
)
from licigt.consulta.requisitos import (
    CONSULTAS_POR_CATEGORIA, CONSULTA_CRONOGRAMA, FechaCandidata, encontrar_fechas,
)

# Recortes literales de chunks.jsonl de entregables/recuperacion/empresa_demo.zip.
FRAGMENTOS_222 = [{'chunk_id': '03791a3471c04c0f9cc260814564756e:00001',
  'doc_id': '03791a3471c04c0f9cc260814564756e',
  'tipo_documento': 'bases',
  'version_ingesta': 1,
  'pagina_inicio': 1,
  'pagina_fin': 1,
  'seccion': 'Sin sección',
  'url_origen': 'https://www.igssgt.org/wp-content/uploads/2026/10/222-IGSS-2023.pdf',
  'identificador_version_oficial': None,
  'texto': 'La recepción de ofertas se llevará a cabo el 31 de julio de 2023',
  'score': 0.91,
  'reranker': 0.91,
  'semantico': 0.62,
  'lexico': 0.4,
  'rrf': 0.016},
 {'chunk_id': '03791a3471c04c0f9cc260814564756e:00040',
  'doc_id': '03791a3471c04c0f9cc260814564756e',
  'tipo_documento': 'bases',
  'version_ingesta': 1,
  'pagina_inicio': 8,
  'pagina_fin': 8,
  'seccion': '2.2   CRONOGRAMA DE ACTIVIDADES',
  'url_origen': 'https://www.igssgt.org/wp-content/uploads/2026/10/222-IGSS-2023.pdf',
  'identificador_version_oficial': None,
  'texto': '2.2   CRONOGRAMA DE ACTIVIDADES',
  'score': 0.91,
  'reranker': 0.91,
  'semantico': 0.62,
  'lexico': 0.4,
  'rrf': 0.016},
 {'chunk_id': '03791a3471c04c0f9cc260814564756e:00041',
  'doc_id': '03791a3471c04c0f9cc260814564756e',
  'tipo_documento': 'bases',
  'version_ingesta': 1,
  'pagina_inicio': 8,
  'pagina_fin': 8,
  'seccion': '2.2   CRONOGRAMA DE ACTIVIDADES',
  'url_origen': 'https://www.igssgt.org/wp-content/uploads/2026/10/222-IGSS-2023.pdf',
  'identificador_version_oficial': None,
  'texto': '| 2.2.6 | Lugar, dirección, fecha y hora para la recepción de OFERTAS. | En Salones '
           'Los Volcanes, ubicados en la 7ª. Avenida 22-72 zona 1, segundo nivel, Oficinas '
           'Centrales del INSTITUTO, el día 31 de julio de 2023, a las 11:00 horas (hora límite '
           '11:30)',
  'score': 0.91,
  'reranker': 0.91,
  'semantico': 0.62,
  'lexico': 0.4,
  'rrf': 0.016},
 {'chunk_id': '03791a3471c04c0f9cc260814564756e:00055',
  'doc_id': '03791a3471c04c0f9cc260814564756e',
  'tipo_documento': 'bases',
  'version_ingesta': 1,
  'pagina_inicio': 13,
  'pagina_fin': 13,
  'seccion': '2.7      LISTADO DE DOCUMENTOS QUE DEBERÁ CONTENER LA PLICA',
  'url_origen': 'https://www.igssgt.org/wp-content/uploads/2026/10/222-IGSS-2023.pdf',
  'identificador_version_oficial': None,
  'texto': 'Solvencia Patronal extendida por el INSTITUTO a nombre del OFERENTE, con el\n'
           '            pago operado al 31 de mayo de 2023',
  'score': 0.91,
  'reranker': 0.91,
  'semantico': 0.62,
  'lexico': 0.4,
  'rrf': 0.016},
 {'chunk_id': 'd41480e5b0ce4c16bf18f66225ada2dc:00003',
  'doc_id': 'd41480e5b0ce4c16bf18f66225ada2dc',
  'tipo_documento': 'modificacion',
  'version_ingesta': 1,
  'pagina_inicio': 1,
  'pagina_fin': 1,
  'seccion': '2.2      CRONOGRAMA DE ACTIVIDADES',
  'url_origen': 'https://www.igssgt.org/wp-content/uploads/2026/10/LICITACION-DA-No.-222-IGSS-2023-IGSS.pdf',
  'identificador_version_oficial': 'Modificación Número 1',
  'texto': '| 2.2.6 | Lugar, dirección, fecha y hora para la recepción de OFERTAS. | En Salones '
           'Los Volcanes, ubicados en la 7ª. Avenida 22-72 zona 1, segundo nivel, Oficinas '
           'Centrales del INSTITUTO, el día 06 de octubre de 2023, a las 11:00 horas (hora límite '
           '11:30)',
  'score': 0.91,
  'reranker': 0.91,
  'semantico': 0.62,
  'lexico': 0.4,
  'rrf': 0.016},
 {'chunk_id': 'd41480e5b0ce4c16bf18f66225ada2dc:00005',
  'doc_id': 'd41480e5b0ce4c16bf18f66225ada2dc',
  'tipo_documento': 'modificacion',
  'version_ingesta': 1,
  'pagina_inicio': 2,
  'pagina_fin': 2,
  'seccion': '2.2      CRONOGRAMA DE ACTIVIDADES',
  'url_origen': 'https://www.igssgt.org/wp-content/uploads/2026/10/LICITACION-DA-No.-222-IGSS-2023-IGSS.pdf',
  'identificador_version_oficial': 'Modificación Número 1',
  'texto': 'Solvencia Patronal extendida por el INSTITUTO a nombre del OFERENTE, con el pago\n'
           '      operado al 31 de julio de 2023',
  'score': 0.91,
  'reranker': 0.91,
  'semantico': 0.62,
  'lexico': 0.4,
  'rrf': 0.016}]


def busqueda(fragmentos=None, **cambios):
    return {"evento_id": "222", "variante": "mejorada", "suficiente": True,
            "fragmentos": deepcopy(FRAGMENTOS_222 if fragmentos is None else fragmentos),
            "alertas": [], **cambios}


class RecuperadorFalso:
    def __init__(self, resultados=None):
        self.resultados = resultados or [busqueda()] * 5
        self.llamadas = []

    def buscar(self, ctx, evento_id, pregunta, variante="mejorada", k=5, conn=None):
        resultado = self.resultados[len(self.llamadas)]
        self.llamadas.append((ctx, evento_id, pregunta, variante, k))
        if isinstance(resultado, Exception):
            raise resultado
        return resultado


class JevFalso:
    def __init__(self, elecciones=None, probabilidad=0.9, respaldo=0.9, error=None,
                 incompleta=False):
        self.elecciones = elecciones or {}
        self.probabilidad, self.respaldo = probabilidad, respaldo
        self.error, self.incompleta = error, incompleta
        self.llamadas = []

    def preguntar(self, estado, preguntas):
        self.llamadas.append((deepcopy(estado), deepcopy(preguntas)))
        if self.error:
            raise self.error
        respuestas = {}
        for identificador in estado["candidatas"]:
            actividad = self.elecciones.get(identificador, "recepcion_ofertas")
            probabilidades = {a: (1 - self.probabilidad) / (len(ACTIVIDADES_CRONOGRAMA) - 1)
                              for a in ACTIVIDADES_CRONOGRAMA}
            probabilidades[actividad] = self.probabilidad
            respuestas[f"actividad_{identificador}"] = {
                "type": "choice", "choice": actividad, "probabilities": probabilidades,
                "confidence": 0.01,  # La concentración no debe decidir la aceptación.
            }
            respuestas[f"respaldo_{identificador}"] = {"type": "noul", "noul": self.respaldo}
        if self.incompleta:
            respuestas.pop(next(reversed(respuestas)))
        return RespuestaJev(respuestas=respuestas, modelo="jev-falso", request_id=None,
                            tokens_entrada=None, tokens_salida=None)


class FechasTests(unittest.TestCase):
    def test_formatos_y_posiciones_originales(self):
        for literal, esperada in [
            ("31 de julio de 2023", date(2023, 7, 31)),
            ("06 de octubre de 2023", date(2023, 10, 6)),
            ("1 de setiembre del 2023", date(2023, 9, 1)),
            ("31 DE JULIO DE 2023", date(2023, 7, 31)),
            ("31 de júlio de 2023", date(2023, 7, 31)),
        ]:
            with self.subTest(literal=literal):
                texto = "día ésta: " + literal + "."
                self.assertEqual(encontrar_fechas(texto), [(literal, esperada, len("día ésta: "))])
        self.assertEqual(encontrar_fechas("día 31 de julio de 2023")[0][2], 4)

    def test_descarta_imposibles_incompletas_y_formatos_no_admitidos(self):
        for texto in ("30 de febrero de 2023", "julio de 2023", "31/07/2023",
                      "131 de julio de 2023", "31 de julio de 20231", "1 de enero de 0000"):
            with self.subTest(texto=texto):
                self.assertEqual(encontrar_fechas(texto), [])

    def test_recortes_del_corpus_y_literal_con_salto_de_linea(self):
        self.assertEqual([len(encontrar_fechas(f["texto"])) for f in FRAGMENTOS_222],
                         [1, 0, 1, 1, 1, 1])
        # Con la tabla contigua ya no hay fechas partidas en el corpus; el salto de línea se cubre aparte.
        texto = "el día 31 de julio de\n2023, a las 11:00"
        literal, fecha, posicion = encontrar_fechas(texto)[0]
        self.assertIn("\n", literal)
        self.assertEqual(fecha, date(2023, 7, 31))
        self.assertEqual(texto[posicion:posicion + len(literal)], literal)

    def test_modelo_inmutable_sin_extras_y_probabilidades_validas(self):
        datos = dict(chunk_id="c", doc_id="d", tipo_documento="bases", pagina=1,
                     literal="31 de julio de 2023", fecha=date(2023, 7, 31),
                     actividad=None, estado="no_verificada", prob_actividad=None,
                     prob_respaldo=None)
        candidata = FechaCandidata(**datos)
        with self.assertRaises(ValidationError):
            candidata.actividad = "recepcion_ofertas"
        with self.assertRaises(ValidationError):
            FechaCandidata(**datos, tenant_id="ajeno")
        for valor in (-0.1, 1.1, float("nan"), float("inf"), True, "0.9"):
            with self.subTest(valor=valor), self.assertRaises(ValidationError):
                FechaCandidata(**{**datos, "prob_actividad": valor})


class FechasEnTablaTests(unittest.TestCase):
    """C15: las fechas de las filas de una tabla salen con su fila como contexto."""

    def test_c15_encontrar_fechas_con_barras(self):
        self.assertEqual([(l, f.isoformat()) for l, f, _ in encontrar_fechas(DATOS_TABLA["texto"])],
                         [("31 de julio de 2023", "2023-07-31"), ("19 de julio de 2023", "2023-07-19"),
                          ("31 de julio de 2023", "2023-07-31")])

    def test_c15_cada_candidata_lleva_el_titulo_de_su_fila(self):
        jev = JevFalso(elecciones={"c0": "adquirir_documentos", "c1": "induccion", "c2": "recepcion_ofertas"})
        recuperador = RecuperadorFalso([busqueda([DATOS_TABLA])] * 5)
        r = extraer_requisitos(None, ExtraerRequisitosParams(evento_id="222"), recuperador, cliente_jev=jev)
        candidatas = jev.llamadas[0][0]["candidatas"]
        self.assertEqual([c["fecha"] for c in candidatas.values()],
                         ["31 de julio de 2023", "19 de julio de 2023", "31 de julio de 2023"])
        self.assertIn("2.2.2 | Fecha y hora para inducción", candidatas["c1"]["pasaje"])
        self.assertIn("Lugar, dirección, fecha y hora para la recepción de OFERTAS", candidatas["c2"]["pasaje"])
        self.assertTrue(candidatas["c2"]["pasaje"].startswith("| 2.2.6 | Lugar"))
        self.assertEqual([(f.actividad, f.estado) for f in r.fechas],
                         [("adquirir_documentos", "verificada"), ("induccion", "verificada"),
                          ("recepcion_ofertas", "verificada")])

    def test_c16_el_pasaje_de_una_fecha_de_tabla_termina_en_el_fin_de_su_fila(self):
        jev = JevFalso(elecciones={"c0": "adquirir_documentos", "c1": "induccion", "c2": "recepcion_ofertas"})
        recuperador = RecuperadorFalso([busqueda([DATOS_TABLA])] * 5)
        extraer_requisitos(None, ExtraerRequisitosParams(evento_id="222"), recuperador, cliente_jev=jev)
        candidatas = jev.llamadas[0][0]["candidatas"]
        for identificador, otra_fila in (("c0", "2.2.2"), ("c1", "2.2.3"), ("c2", "2.2.7")):
            with self.subTest(candidata=identificador):
                self.assertNotIn(otra_fila, candidatas[identificador]["pasaje"])
        self.assertTrue(candidatas["c0"]["pasaje"].endswith("31 de julio de 2023. |"))
        self.assertNotIn("Fecha y hora para inducción", candidatas["c0"]["pasaje"])


    def test_c15_la_consulta_del_cronograma_nombra_las_actividades_de_la_tabla(self):
        # Medido: con la consulta anterior, la tabla 2.2 (chunk 00041) no salía entre los 5 mejores del evento 222.
        consulta = CONSULTA_CRONOGRAMA.lower()
        for palabra in ("cronograma", "adquirir", "inducción", "aclaraciones", "recepción de ofertas", "apertura de plicas"):
            self.assertIn(palabra, consulta)

class ExtraerRequisitosTests(unittest.TestCase):
    def extraer(self, recuperador=None, jev=None, **params):
        return extraer_requisitos(self.ctx, ExtraerRequisitosParams(evento_id="222", **params),
                                 recuperador or RecuperadorFalso(), cliente_jev=jev)

    def setUp(self):
        self.ctx = {"tenant_id": "empresa_privada", "usuario": "usuario_privado"}

    def test_sin_categoria_consulta_cinco_veces_y_conserva_contexto(self):
        recuperador = RecuperadorFalso()
        resultado = self.extraer(recuperador)
        self.assertEqual(set(CONSULTAS_POR_CATEGORIA), set(get_args(Categoria)))
        consultas = [*CONSULTAS_POR_CATEGORIA.values(), CONSULTA_CRONOGRAMA]
        self.assertEqual(recuperador.llamadas,
                         [(self.ctx, "222", c, "mejorada", 5) for c in consultas])
        self.assertTrue(all(c[0] is self.ctx for c in recuperador.llamadas))
        self.assertEqual(resultado.herramienta, "extraer_requisitos")
        self.assertFalse(resultado.abstener)

    def test_con_categoria_siempre_consulta_cronograma(self):
        for categoria in get_args(Categoria):
            with self.subTest(categoria=categoria):
                recuperador = RecuperadorFalso()
                self.extraer(recuperador, categoria=categoria)
                self.assertEqual([c[2] for c in recuperador.llamadas],
                                 [CONSULTAS_POR_CATEGORIA[categoria], CONSULTA_CRONOGRAMA])

    def test_deduplica_fragmentos_y_alertas_en_orden(self):
        alertas = [{"tipo": "posible_conflicto", "doc_id": "mod"},
                   {"tipo": "cobertura_incompleta", "doc_id": "base", "paginas_no_indexadas": [3]},
                   {"tipo": "evento_con_modificaciones", "doc_id": "mod"},
                   {"tipo": "nueva", "doc_id": "base"}]
        recuperador = RecuperadorFalso([busqueda(alertas=alertas)] * 5)
        resultado = self.extraer(recuperador)
        self.assertEqual([f.chunk_id for f in resultado.fragmentos],
                         [f["chunk_id"] for f in FRAGMENTOS_222])
        self.assertEqual(len(resultado.fechas), 5)
        self.assertTrue(resultado.needs_human_review)
        self.assertEqual(resultado.coverage_status, "parcial")
        self.assertEqual(resultado.warnings, ["cobertura_incompleta: base páginas no indexadas 3",
                                             "evento_con_modificaciones: mod",
                                             "alerta_desconocida: nueva", "fechas_no_verificadas: 5"])

    def test_sin_jev_no_inventa_actividad_ni_revision(self):
        resultado = self.extraer()
        self.assertFalse(resultado.needs_human_review)
        self.assertIn("fechas_no_verificadas: 5", resultado.warnings)
        for fecha in resultado.fechas:
            self.assertEqual(fecha.estado, "no_verificada")
            self.assertIsNone(fecha.actividad)
            self.assertIsNone(fecha.prob_actividad)
            self.assertIsNone(fecha.prob_respaldo)

    def test_caso_222_compara_recepcion_y_excluye_solvencias(self):
        jev = JevFalso({"c2": "ninguna", "c4": "ninguna"})
        resultado = self.extraer(jev=jev)
        self.assertTrue(resultado.needs_human_review)
        self.assertEqual(resultado.warnings, ["fechas_distintas: recepcion_ofertas"])
        self.assertEqual([f.estado for f in resultado.fechas],
                         ["verificada", "verificada", "fuera_del_cronograma", "verificada",
                          "fuera_del_cronograma"])
        self.assertEqual({f.fecha for f in resultado.fechas if f.actividad == "recepcion_ofertas"},
                         {date(2023, 7, 31), date(2023, 10, 6)})
        self.assertEqual(len(resultado.fragmentos), 6)

    def test_confianza_baja_y_limites_inclusivos(self):
        for probabilidad, respaldo, estado in [(0.49, 0.9, "no_verificada"),
                                               (0.9, 0.69, "no_verificada"),
                                               (0.9, 0.2, "no_verificada"),
                                               (0.5, 0.7, "verificada")]:
            with self.subTest(probabilidad=probabilidad, respaldo=respaldo):
                jev = JevFalso(probabilidad=probabilidad, respaldo=respaldo)
                resultado = self.extraer(RecuperadorFalso([busqueda(FRAGMENTOS_222[:1])] * 5), jev)
                candidata = resultado.fechas[0]
                self.assertEqual(candidata.estado, estado)
                self.assertEqual(candidata.prob_actividad, probabilidad)
                self.assertEqual(candidata.prob_respaldo, respaldo)
                self.assertEqual(resultado.needs_human_review, estado == "no_verificada")

    def test_ninguna_se_decide_por_choice(self):
        for probabilidad, estado in [(0.5, "fuera_del_cronograma"), (0.49, "no_verificada")]:
            with self.subTest(probabilidad=probabilidad):
                jev = JevFalso({"c0": "ninguna"}, probabilidad=probabilidad, respaldo=0.1)
                resultado = self.extraer(RecuperadorFalso([busqueda(FRAGMENTOS_222[:1])] * 5), jev)
                self.assertEqual(resultado.fechas[0].estado, estado)
                self.assertEqual(resultado.needs_human_review, estado == "no_verificada")

    def test_fallas_jev_no_publican_verificacion_parcial(self):
        for error in (FallaJev("api"), TimeoutError(),
                      ValidationError.from_exception_data("Respuesta", []), None):
            with self.subTest(error=error):
                resultado = self.extraer(jev=JevFalso(error=error, incompleta=error is None))
                self.assertIn("jev_no_disponible", resultado.warnings)
                self.assertTrue(resultado.needs_human_review)
                self.assertTrue(all(f.estado == "no_verificada" and f.prob_actividad is None
                                    for f in resultado.fechas))

    def test_estado_publico_preguntas_y_una_solicitud(self):
        jev = JevFalso()
        self.extraer(jev=jev)
        self.assertEqual(len(jev.llamadas), 1)
        estado, preguntas = jev.llamadas[0]
        self.assertEqual(set(estado), {"candidatas"})
        self.assertEqual(list(estado["candidatas"]), [f"c{i}" for i in range(5)])
        for identificador, candidata in estado["candidatas"].items():
            self.assertEqual(set(candidata), {"seccion", "pasaje", "fecha"})
            self.assertTrue(all(isinstance(v, str) for v in candidata.values()))
            self.assertLessEqual(len(candidata["pasaje"]), 300 + len(candidata["fecha"]))
            for prefijo, tipo in (("actividad", "choice"), ("respaldo", "noul")):
                pregunta = preguntas[f"{prefijo}_{identificador}"]
                self.assertEqual(pregunta["type"], tipo)
                self.assertIn(f"`candidatas.{identificador}.", pregunta["instructions"])
            self.assertEqual(preguntas[f"actividad_{identificador}"]["criteria"], ACTIVIDADES_CRONOGRAMA)
        self.assertEqual(estado["candidatas"]["c1"]["seccion"], FRAGMENTOS_222[2]["seccion"])
        self.assertIn("recepción de OFERTAS", estado["candidatas"]["c3"]["pasaje"])
        serializado = json.dumps(jev.llamadas)
        for privado in ("ctx", "tenant_id", "empresa_privada", "usuario_privado"):
            self.assertNotIn(privado, serializado)
        self.assertEqual(preguntas, preguntas_fechas(estado["candidatas"]))

    def test_limita_envio_y_conserva_sobrantes(self):
        fragmento = {**FRAGMENTOS_222[0], "texto": "31 de julio de 2023; " * (MAX_CANDIDATAS_JEV + 2)}
        jev = JevFalso()
        resultado = self.extraer(RecuperadorFalso([busqueda([fragmento])] * 5), jev)
        self.assertEqual(len(jev.llamadas), 1)
        self.assertEqual(len(jev.llamadas[0][0]["candidatas"]), MAX_CANDIDATAS_JEV)
        self.assertEqual(len(jev.llamadas[0][1]), 2 * MAX_CANDIDATAS_JEV)
        self.assertEqual([f.estado for f in resultado.fechas[-2:]], ["no_verificada"] * 2)
        self.assertIn("candidatas_sin_verificar: 2", resultado.warnings)
        self.assertTrue(resultado.needs_human_review)

    def test_ventana_conserva_espacios_a_ambos_lados_de_la_fecha(self):
        texto = "La recepción será el \n 31 de julio de 2023 \n a las once horas."
        fragmento = {**FRAGMENTOS_222[0], "texto": texto}
        jev = JevFalso()
        self.extraer(RecuperadorFalso([busqueda([fragmento])] * 5), jev)
        candidata = jev.llamadas[0][0]["candidatas"]["c0"]
        self.assertEqual(candidata["pasaje"],
                         "La recepción será el 31 de julio de 2023 a las once horas.")

    def test_fechas_distintas_dentro_del_mismo_documento(self):
        fragmento = {**FRAGMENTOS_222[0], "texto": "31 de julio de 2023 y 06 de octubre de 2023"}
        resultado = self.extraer(RecuperadorFalso([busqueda([fragmento])] * 5), JevFalso())
        self.assertIn("fechas_distintas: recepcion_ofertas", resultado.warnings)
        self.assertTrue(resultado.needs_human_review)

    def test_fechas_iguales_no_son_conflicto(self):
        resultado = self.extraer(RecuperadorFalso([busqueda(FRAGMENTOS_222[:1])] * 5), JevFalso())
        self.assertFalse(resultado.needs_human_review)
        self.assertEqual(resultado.warnings, [])

    def test_falla_segunda_busqueda_y_contrato_invalido(self):
        for crudo, error in ((RuntimeError("texto privado"), "falla_recuperacion"),
                             ({"evento_id": "222"}, "contrato_invalido")):
            with self.subTest(error=error):
                jev = JevFalso()
                resultado = self.extraer(RecuperadorFalso([busqueda(), crudo]), jev)
                self.assertEqual(resultado.error, error)
                self.assertTrue(resultado.abstener)
                self.assertEqual(resultado.fragmentos, [])
                self.assertEqual(resultado.fechas, [])
                self.assertEqual(jev.llamadas, [])

    def test_todas_insuficientes_abstiene_sin_jev(self):
        jev = JevFalso()
        resultado = self.extraer(RecuperadorFalso([busqueda(suficiente=False)] * 5), jev)
        self.assertTrue(resultado.abstener)
        self.assertEqual(jev.llamadas, [])

    def test_una_suficiente_basta_y_sin_fragmentos_abstiene(self):
        resultado = self.extraer(RecuperadorFalso([busqueda(suficiente=False)] * 4 + [busqueda()]))
        self.assertFalse(resultado.abstener)
        jev = JevFalso()
        resultado = self.extraer(RecuperadorFalso([busqueda([])] * 5), jev)
        self.assertTrue(resultado.abstener)
        self.assertEqual(resultado.fechas, [])
        self.assertEqual(jev.llamadas, [])

    def test_sin_fechas_no_llama_jev(self):
        jev = JevFalso()
        resultado = self.extraer(RecuperadorFalso([busqueda(FRAGMENTOS_222[1:2])] * 5), jev)
        self.assertFalse(resultado.abstener)
        self.assertEqual(resultado.fechas, [])
        self.assertEqual(resultado.warnings, [])
        self.assertEqual(jev.llamadas, [])

    def test_importaciones_sin_sdk_ni_recuperacion(self):
        codigo = '''
import sys
from licigt.consulta import herramientas, requisitos
assert not any(n == "typesafe_sdk" or n.startswith("typesafe_sdk.")
               or n == "licigt.recuperacion" or n.startswith("licigt.recuperacion.")
               for n in sys.modules)
'''
        resultado = subprocess.run([sys.executable, "-c", codigo], capture_output=True, text=True,
                                   env={**os.environ, "PYTHONPATH": "src"})
        self.assertEqual(resultado.returncode, 0, resultado.stderr)
