"""Experimento de JEV en las fechas de la lista: reglas, puntuación, veredicto y exportación, sin red."""

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from unittest import mock

from licigt.consulta import experimento_fechas, fechas_reglas
from licigt.consulta.experimento_fechas import (
    PARTICIONES, asignar_por_reglas, candidatas_evento, comparar, conflictos, correr, estados_jev, estados_reglas,
    exportar, huella_palabras_clave, puntuar, veredicto, veredicto_sin_jev,
)
from licigt.consulta.lista import proponer_lista
from licigt.consulta.requisitos import CONSULTA_CRONOGRAMA
from licigt.consulta.jev import RespuestaJev
from licigt.consulta.preguntas_jev import ACTIVIDADES_CRONOGRAMA


def candidata(identificador, pasaje, evento="222", fecha="1 de enero de 2023", seccion="2.2 Cronograma"):
    return {"id": f"{evento}-{identificador}", "evento": f"{evento}-IGSS-2023", "fecha": fecha,
            "pasaje": pasaje, "seccion": seccion}


def separar(pasaje, fecha):
    """Reglas reciben antes+literal y el resto aparte; aquí basta una candidata con el pasaje completo."""
    return {"pasaje": pasaje, "fecha": fecha}


def respuesta(actividades):
    """Respuesta de JEV con una actividad y un respaldo por candidata local (c0, c1...)."""
    datos = {}
    for local, (actividad, prob_actividad, respaldo) in actividades.items():
        datos[f"actividad_{local}"] = {
            "type": "choice", "choice": actividad, "confidence": 0.01,
            "probabilities": {a: (prob_actividad if a == actividad else (1 - prob_actividad) / (len(ACTIVIDADES_CRONOGRAMA) - 1))
                              for a in ACTIVIDADES_CRONOGRAMA}}
        datos[f"respaldo_{local}"] = {"type": "noul", "noul": respaldo}
    return RespuestaJev(respuestas=datos, modelo="jev-1.14.0", request_id="x", tokens_entrada=1, tokens_salida=1)


class ClienteQueFalla:
    def __init__(self):
        self.llamadas = 0

    def preguntar(self, estado, preguntas):
        self.llamadas += 1
        raise AssertionError("no debía llamarse")


class ReglasPorFila(unittest.TestCase):
    def test_una_sola_actividad_en_la_fila(self):
        casos = {
            "| 2.2.1 | Período para adquirir los DOCUMENTOS DE LICITACIÓN | Del 3 de abril de 2023": "adquirir_documentos",
            "| 2.2.2 | Fecha y hora para inducción a interesados | 5 de abril de 2023": "induccion",
            "| 2.2.3 | Período para solicitud de aclaraciones sobre los DOCUMENTOS | 7 de abril de 2023": "solicitud_aclaraciones",
            "| 2.2.4 | Período para respuestas de aclaraciones | 10 de abril de 2023": "respuesta_aclaraciones",
            "| 2.2.5 | Período para la preparación del FORMULARIO ELECTRÓNICO | 12 de abril de 2023": "formulario_electronico",
            "| 2.2.6 | Lugar, dirección, fecha y hora para la recepción de OFERTAS | 14 de abril de 2023": "recepcion_ofertas",
            "| 2.2.7 | Apertura de PLICAS | 14 de abril de 2023": "apertura_plicas",
            "| 2.2.8 | Plazo para adjudicar | 20 de abril de 2023": "adjudicacion",
        }
        for pasaje, esperada in casos.items():
            with self.subTest(esperada=esperada):
                self.assertEqual(asignar_por_reglas(pasaje), esperada)

    def test_sin_coincidencia_no_asigna(self):
        self.assertIsNone(asignar_por_reglas("Solvencia patronal emitida el 3 de abril de 2023"))

    def test_dos_actividades_distintas_no_asignan(self):
        self.assertIsNone(asignar_por_reglas("recepción de ofertas y apertura de plicas el 14 de abril de 2023"))

    def test_la_misma_actividad_repetida_si_asigna(self):
        self.assertEqual(asignar_por_reglas("Apertura de PLICAS: la apertura de plicas será el 14 de abril de 2023"),
                         "apertura_plicas")

    def test_ignora_mayusculas_y_tildes(self):
        self.assertEqual(asignar_por_reglas("INDUCCION a interesados el 5 de abril de 2023"), "induccion")

    def test_fuera_de_tabla_no_mira_lo_posterior(self):
        pasaje = "Solvencia Patronal con el pago operado al 31 de julio de 2023, que se presenta en la recepción de ofertas"
        fila = candidata("c0", pasaje, fecha="31 de julio de 2023")
        self.assertIsNone(estados_reglas([fila], {})["222-c0"]["actividad"])

    def test_en_tabla_si_mira_la_fila_completa(self):
        pasaje = "| 2.2.6 | Recepción de ofertas | Hasta el 14 de abril de 2023 a las 10:00 |"
        fila = candidata("c0", pasaje, fecha="14 de abril de 2023")
        self.assertEqual(estados_reglas([fila], {"222-c0": True})["222-c0"]["actividad"], "recepcion_ofertas")

    def test_fuera_de_tabla_nunca_se_verifica(self):
        # F7c: solo se verifica en filas de tabla, que es lo medido en F7b.
        fila = candidata("c0", "recepción de ofertas, fecha 3 de abril de 2023", fecha="3 de abril de 2023")
        self.assertEqual(estados_reglas([fila], {"222-c0": False})["222-c0"], {"estado": "no_verificada", "actividad": None})
        self.assertEqual(estados_reglas([fila], {"222-c0": True})["222-c0"]["actividad"], "recepcion_ofertas")

    def test_en_tabla_no_mira_la_fila_siguiente(self):
        pasaje = "| 2.2.9 | Otra actividad | 3 de abril de 2023 | | 2.2.6 | Recepción de ofertas | 5 de abril de 2023 |"
        fila = candidata("c0", pasaje, fecha="3 de abril de 2023")
        self.assertEqual(estados_reglas([fila], {"222-c0": True})["222-c0"], {"estado": "no_verificada", "actividad": None})

    def test_solo_las_formas_de_las_definiciones(self):
        for pasaje in ("ADQUISICIÓN DE MEDICAMENTO publicada el 06 de octubre de 2023",
                       "la adjudicación del 06 de octubre de 2023"):
            self.assertIsNone(asignar_por_reglas(pasaje))

    def test_estados_de_reglas(self):
        filas = [candidata("c0", "recepción de ofertas el 1 de enero de 2023"), candidata("c1", "sin nada")]
        self.assertEqual(estados_reglas([candidata("c0", "recepción de ofertas el 1 de enero de 2023"),
                                         candidata("c1", "sin nada")], {"222-c0": True, "222-c1": True}), {
            "222-c0": {"estado": "verificada", "actividad": "recepcion_ofertas"},
            "222-c1": {"estado": "no_verificada", "actividad": None}})


class VistaPrevia(unittest.TestCase):
    def test_sin_confirmar_no_llama_al_cliente(self):
        cliente = ClienteQueFalla()
        vista = correr([candidata("c0", "x")], cliente_jev=cliente)
        self.assertEqual(cliente.llamadas, 0)
        self.assertEqual(vista["lotes"][0]["ids"], ["222-c0"])
        self.assertIn("actividad_c0", vista["questions"][0])

    def test_lotes_de_20_por_evento(self):
        filas = [candidata(f"c{i}", "x") for i in range(25)] + [candidata("c0", "y", evento="363")]
        vista = correr(filas, cliente_jev=None)
        self.assertEqual([len(l["ids"]) for l in vista["lotes"]], [20, 5, 1])

    def test_confirmado_graba_la_respuesta_cruda(self):
        class Cliente:
            def preguntar(self, estado, preguntas):
                self.estado = estado
                return respuesta({"c0": ("recepcion_ofertas", 0.9, 0.95)})
        cliente = Cliente()
        corrida = correr([candidata("c0", "x")], cliente_jev=cliente, confirmar=True)
        self.assertEqual(list(cliente.estado["candidatas"]), ["c0"])
        self.assertEqual(set(cliente.estado["candidatas"]["c0"]), {"seccion", "pasaje", "fecha"})
        lote = corrida["lotes"][0]
        self.assertEqual(lote["respuesta"]["respuestas"]["actividad_c0"]["choice"], "recepcion_ofertas")
        self.assertIsNone(lote["error"])
        self.assertTrue(corrida["limpia"])


class EstadosDeJev(unittest.TestCase):
    def corrida(self, actividades, error=None):
        ids = [f"222-{k}" for k in actividades]
        return {"lotes": [{"evento": "222", "ids": ids, "error": error,
                           "respuesta": None if error else respuesta(actividades).model_dump(mode="json")}]}

    def test_mismas_reglas_que_la_propuesta(self):
        corrida = self.corrida({"c0": ("recepcion_ofertas", 0.9, 0.95),   # verificada
                                "c1": ("ninguna", 0.9, 0.2),              # fuera del cronograma
                                "c2": ("apertura_plicas", 0.9, 0.5),      # respaldo bajo
                                "c3": ("induccion", 0.4, 0.95)})          # actividad baja
        estados = estados_jev(corrida)
        self.assertEqual(estados["222-c0"], {"estado": "verificada", "actividad": "recepcion_ofertas"})
        self.assertEqual(estados["222-c1"]["estado"], "fuera_del_cronograma")
        self.assertEqual(estados["222-c2"]["estado"], "no_verificada")
        self.assertEqual(estados["222-c3"]["estado"], "no_verificada")

    def test_una_falla_deja_el_lote_sin_verificar(self):
        estados = estados_jev(self.corrida({"c0": ("induccion", 0.9, 0.9)}, error="api"))
        self.assertEqual(estados["222-c0"], {"estado": "no_verificada", "actividad": None})


class Puntuacion(unittest.TestCase):
    def test_aciertos_criticos_y_no_verificadas(self):
        etiquetas = {"a": "induccion", "b": "induccion", "c": "ninguna", "d": "apertura_plicas", "e": "ninguna"}
        estados = {
            "a": {"estado": "verificada", "actividad": "induccion"},            # acierto
            "b": {"estado": "verificada", "actividad": "apertura_plicas"},      # crítico
            "c": {"estado": "verificada", "actividad": "induccion"},            # crítico: etiqueta ninguna
            "d": {"estado": "no_verificada", "actividad": None},
            "e": {"estado": "fuera_del_cronograma", "actividad": "ninguna"}}
        resultado = puntuar(estados, etiquetas)
        self.assertEqual((resultado["aciertos"], resultado["criticos"], resultado["no_verificadas"],
                          resultado["fuera_del_cronograma"], resultado["n"]), (1, 2, 1, 1, 5))
        self.assertEqual(resultado["ids_aciertos"], ["a"])
        self.assertEqual(resultado["ids_criticos"], ["b", "c"])


class Conflictos(unittest.TestCase):
    def test_detecta_dos_fechas_verificadas_de_la_misma_actividad(self):
        filas = [candidata("c0", "x", fecha="3 de abril de 2023"), candidata("c1", "x", fecha="4 de abril de 2023"),
                 candidata("c2", "x", fecha="5 de abril de 2023"), candidata("c3", "x", fecha="5 de abril de 2023")]
        estados = {"222-c0": {"estado": "verificada", "actividad": "adquirir_documentos"},
                   "222-c1": {"estado": "verificada", "actividad": "adquirir_documentos"},
                   "222-c2": {"estado": "verificada", "actividad": "recepcion_ofertas"},
                   "222-c3": {"estado": "no_verificada", "actividad": None}}
        self.assertEqual(conflictos(filas, estados, "222"), ["adquirir_documentos"])

    def test_una_fecha_repetida_no_es_conflicto(self):
        filas = [candidata("c0", "x"), candidata("c1", "x")]
        estados = {f"222-c{i}": {"estado": "verificada", "actividad": "induccion"} for i in range(2)}
        self.assertEqual(conflictos(filas, estados, "222"), [])


class Veredicto(unittest.TestCase):
    def pareja(self, jev_aciertos, jev_criticos, reg_aciertos, reg_criticos, n=40):
        # Las discordancias se reparten para que el McNemar salga de los ids.
        def lado(aciertos, criticos):
            return {"aciertos": aciertos, "criticos": criticos}
        return lado(jev_aciertos, jev_criticos), lado(reg_aciertos, reg_criticos)

    def test_jev_se_queda(self):
        jev, reglas = self.pareja(30, 0, 10, 0)
        self.assertEqual(veredicto(jev, reglas, 1e-6)["decision"], "jev")

    def test_jev_con_mas_criticos_no_se_queda_y_gana_reglas_sin_criticos(self):
        jev, reglas = self.pareja(30, 1, 10, 0)
        self.assertEqual(veredicto(jev, reglas, 1e-6)["decision"], "reglas")

    def test_sin_significancia_y_reglas_sin_criticos_adopta_reglas(self):
        jev, reglas = self.pareja(12, 0, 10, 0)
        self.assertEqual(veredicto(jev, reglas, 0.3)["decision"], "reglas")

    def test_ambas_con_criticos_no_verificar(self):
        jev, reglas = self.pareja(12, 2, 10, 1)
        self.assertEqual(veredicto(jev, reglas, 0.3)["decision"], "no_verificar")

    def test_jev_sin_criticos_y_reglas_con_uno_se_queda_sin_significancia(self):
        jev, reglas = self.pareja(12, 0, 10, 1)
        resultado = veredicto(jev, reglas, 0.3)
        self.assertEqual(resultado["decision"], "jev")
        self.assertNotIn("p < 0,05", resultado["motivo"])
        self.assertIn("crítico", resultado["motivo"])

    def test_jev_sin_criticos_ni_aciertos_contra_reglas_con_critico_no_verificar(self):
        resultado = veredicto({"aciertos": 0, "criticos": 0}, {"aciertos": 10, "criticos": 1}, 0.002)
        self.assertEqual(resultado["decision"], "no_verificar")

    def test_jev_con_un_acierto_y_sin_criticos_se_queda_contra_reglas_con_critico(self):
        resultado = veredicto({"aciertos": 3, "criticos": 0}, {"aciertos": 10, "criticos": 1}, 0.002)
        self.assertEqual(resultado["decision"], "jev")

    def test_jev_con_criticos_y_reglas_sin_ellos_adopta_reglas_aunque_gane(self):
        jev, reglas = self.pareja(30, 1, 10, 0)
        self.assertEqual(veredicto(jev, reglas, 1e-6)["decision"], "reglas")

    def test_empate_de_criticos_con_criticos_exige_significancia(self):
        jev, reglas = self.pareja(30, 1, 10, 1)
        self.assertEqual(veredicto(jev, reglas, 1e-6)["decision"], "jev")


class VeredictoSinJev(unittest.TestCase):
    def test_reglas_sin_criticos_y_poco_margen_para_jev(self):
        etiquetas = {f"x-c{i}": "induccion" for i in range(5)}
        estados = {i: {"estado": "verificada", "actividad": "induccion"} for i in list(etiquetas)[:3]}
        estados.update({i: {"estado": "no_verificada", "actividad": None} for i in list(etiquetas)[3:]})
        resultado = veredicto_sin_jev(puntuar(estados, etiquetas), etiquetas)
        self.assertEqual(resultado["decision"], "reglas")
        self.assertIn("JEV no puede superar a las reglas con estos datos", resultado["motivo"])

    def test_con_margen_suficiente_no_esta_determinado(self):
        etiquetas = {f"x-c{i}": "induccion" for i in range(8)}
        estados = {i: {"estado": "no_verificada", "actividad": None} for i in etiquetas}
        self.assertIsNone(veredicto_sin_jev(puntuar(estados, etiquetas), etiquetas))

    def test_las_ninguna_no_cuentan_para_el_maximo_de_jev(self):
        etiquetas = {f"x-c{i}": "ninguna" for i in range(8)}
        estados = {i: {"estado": "no_verificada", "actividad": None} for i in etiquetas}
        self.assertEqual(veredicto_sin_jev(puntuar(estados, etiquetas), etiquetas)["decision"], "reglas")

    def test_con_criticos_de_las_reglas_no_esta_determinado(self):
        etiquetas = {f"x-c{i}": "induccion" for i in range(3)}
        estados = {i: {"estado": "verificada", "actividad": "apertura_plicas"} for i in etiquetas}
        self.assertIsNone(veredicto_sin_jev(puntuar(estados, etiquetas), etiquetas))


def fragmento_de(texto, chunk_id="ev-p1-0"):
    return {"chunk_id": chunk_id, "doc_id": "ev-bases", "tipo_documento": "bases", "version_ingesta": 1,
            "pagina_inicio": 1, "pagina_fin": 1, "seccion": "2.2 Cronograma", "texto": texto,
            "url_origen": None, "identificador_version_oficial": None,
            "score": 0.9, "reranker": 0.9, "semantico": 0.5, "lexico": 0.4, "rrf": 0.02}


class RecuperadorPorConsulta:
    """Devuelve fragmentos distintos según la consulta: si los parámetros divergen, divergen las fechas."""
    def __init__(self):
        self.consultas = []

    def resolver_evento(self, ctx, evento):
        return "ev"

    def buscar(self, ctx, evento_id, consulta, variante="mejorada", k=5, conn=None):
        self.consultas.append(consulta)
        if consulta == "Requisitos y fechas del evento":
            texto, chunk = "Recepción de ofertas el 3 de abril de 2023 en el salón.", "ev-p1-0"
        elif consulta == CONSULTA_CRONOGRAMA:
            texto, chunk = "Apertura de plicas el 4 de abril de 2023 a las diez.", "ev-p2-0"
        else:
            texto, chunk = "Solvencia con pago operado al 5 de abril de 2023 o posterior.", "ev-p3-0"
        return {"evento_id": "ev", "variante": "mejorada", "suficiente": True, "alertas": [],
                "fragmentos": [fragmento_de(texto, chunk)]}


class MismaConsultaQueLaPropuesta(unittest.TestCase):
    def test_las_fechas_exportadas_son_las_de_la_propuesta_en_el_mismo_orden(self):
        propuesta = proponer_lista(object(), "ev", recuperador=RecuperadorPorConsulta())
        fechas_propuesta = [i.descripcion.split(": ", 1)[1] for i in propuesta.items if i.tipo == "fecha"]
        filas = candidatas_evento(object(), "222", RecuperadorPorConsulta())
        self.assertGreaterEqual(len(filas), 3)
        self.assertEqual([f["fecha"] for f in filas], fechas_propuesta)


class SinSuficiencia(RecuperadorPorConsulta):
    def buscar(self, *args, **kwargs):
        return {**super().buscar(*args, **kwargs), "suficiente": False}


class CandidatasDeEvento(unittest.TestCase):
    def test_si_extraer_requisitos_se_abstiene_no_son_de_la_propuesta(self):
        filas = candidatas_evento(object(), "222", SinSuficiencia())
        self.assertTrue(filas)
        self.assertFalse(any(f["en_propuesta"] for f in filas))
        self.assertTrue(all(f["en_propuesta"] for f in candidatas_evento(object(), "222", RecuperadorPorConsulta())))

    def test_en_propuesta_no_depende_de_un_tope_de_candidatas(self):
        class Muchas(RecuperadorPorConsulta):
            def buscar(self, ctx, evento_id, consulta, **kwargs):
                crudo = super().buscar(ctx, evento_id, consulta, **kwargs)
                crudo["fragmentos"][0]["texto"] = " ".join(f"Pago al {d} de abril de 2023." for d in range(1, 26))
                return crudo
        filas = candidatas_evento(object(), "222", Muchas())
        self.assertGreater(len(filas), 20)
        self.assertTrue(all(f["en_propuesta"] for f in filas))

    def test_la_marca_de_tabla_sale_del_fragmento(self):
        class ConTabla(RecuperadorPorConsulta):
            def buscar(self, ctx, evento_id, consulta, **kwargs):
                crudo = super().buscar(ctx, evento_id, consulta, **kwargs)
                crudo["fragmentos"][0]["texto"] = "| 2.2.6 | Recepción de ofertas | 3 de abril de 2023 |"
                return crudo
        filas = candidatas_evento(object(), "222", ConTabla())
        self.assertTrue(all(f["tabla"] for f in filas))
        self.assertFalse(any(f["tabla"] for f in candidatas_evento(object(), "222", RecuperadorPorConsulta())))


class Auditoria(unittest.TestCase):
    """comparar y la vista previa leen de los directorios del módulo: se redirigen a uno temporal."""
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.agentes, self.experimentos = Path(self.tmp.name) / "agentes", Path(self.tmp.name) / "exp"
        self.experimentos.mkdir()
        for nombre, valor in (("AGENTES", self.agentes), ("EXPERIMENTOS", self.experimentos)):
            parche = mock.patch.object(experimento_fechas, nombre, valor)
            parche.start()
            self.addCleanup(parche.stop)

    def preparar(self, n=8, conjunto="desarrollo", pasaje="Fecha de algo sin palabras clave"):
        """Candidatas de tabla: las reglas solo verifican en filas de tabla."""
        filas = [{"id": f"399-c{i}", "evento": "399-IGSS-2026", "fecha": f"{i + 1} de abril de 2026",
                  "fecha_iso": f"2026-04-{i + 1:02d}", "pasaje": f"{pasaje} el {i + 1} de abril de 2026", "seccion": "s",
                  "chunk_id": "ch", "pagina": 1, "en_propuesta": True, "tabla": True} for i in range(n)]
        exportar(conjunto, filas, self.agentes)
        etiquetas = {f["id"]: "induccion" for f in filas}
        (self.agentes / f"etiquetas_fechas_{conjunto}.json").write_text(json.dumps(etiquetas), encoding="utf-8")
        return filas

    def grabar(self, filas, conjunto="desarrollo", **cambios):
        class Cliente:
            def preguntar(self, estado, preguntas):
                return respuesta({local: ("induccion", 0.9, 0.95) for local in estado["candidatas"]})
        corrida = correr(filas, cliente_jev=Cliente(), confirmar=True)
        corrida.update(cambios)
        ruta = self.experimentos / f"fechas_{conjunto}_20261118T000000Z.json"
        ruta.write_text(json.dumps(corrida), encoding="utf-8")
        return corrida

    def test_corrida_valida_da_veredicto(self):
        self.grabar(self.preparar())
        resultado = comparar("desarrollo")
        self.assertEqual(resultado["problemas"], [])
        self.assertEqual(resultado["veredicto"]["decision"], "jev")

    def test_sin_veredicto_si_la_corrida_no_es_limpia(self):
        self.grabar(self.preparar(), limpia=False)
        resultado = comparar("desarrollo")
        self.assertIsNone(resultado["veredicto"])
        self.assertTrue(resultado["problemas"])

    def test_sin_veredicto_con_otra_version_de_preguntas(self):
        self.grabar(self.preparar(), version_preguntas="antigua")
        self.assertIsNone(comparar("desarrollo")["veredicto"])

    def test_sin_veredicto_si_los_ids_no_son_los_del_ciego(self):
        filas = self.preparar()
        self.grabar(filas[:-1])
        resultado = comparar("desarrollo")
        self.assertIsNone(resultado["veredicto"])
        self.assertTrue(any("ids" in p for p in resultado["problemas"]))

    def test_sin_veredicto_con_un_lote_en_error(self):
        corrida = self.grabar(self.preparar())
        corrida["lotes"][0].update(error="api", respuesta=None)
        (self.experimentos / "fechas_desarrollo_20261118T000000Z.json").write_text(json.dumps(corrida), encoding="utf-8")
        self.assertIsNone(comparar("desarrollo")["veredicto"])

    def test_las_no_enviadas_a_jev_quedan_aparte_y_no_verificadas(self):
        filas = self.preparar()
        filas[-1]["en_propuesta"] = False
        exportar("desarrollo", filas, self.agentes)
        self.grabar(filas[:-1])
        resultado = comparar("desarrollo")
        self.assertEqual(resultado["problemas"], [])
        self.assertEqual(resultado["sin_verificar_por_tope"], 1)

    def test_veredicto_de_reglas_sin_corrida_cuando_esta_determinado(self):
        filas = self.preparar(n=4, pasaje="Período para inducción a interesados")
        resultado = comparar("desarrollo")
        self.assertEqual(resultado["veredicto"]["decision"], "reglas")
        self.assertIn("JEV no puede superar a las reglas con estos datos", resultado["veredicto"]["motivo"])
        self.assertFalse(list(self.experimentos.iterdir()))

    def test_sin_corrida_y_sin_veredicto_determinado_lo_dice(self):
        self.preparar()
        resultado = comparar("desarrollo")
        self.assertIsNone(resultado["veredicto"])
        self.assertTrue(resultado["problemas"])

    def test_una_segunda_corrida_de_prueba_no_es_limpia(self):
        filas = self.preparar(conjunto="prueba")
        (self.experimentos / "fechas_prueba_20261118T000000Z.json").write_text("{}", encoding="utf-8")
        class Cliente:
            def preguntar(self, estado, preguntas):
                return respuesta({local: ("induccion", 0.9, 0.95) for local in estado["candidatas"]})
        corrida = correr(filas, cliente_jev=Cliente(), confirmar=True, repetida=experimento_fechas.hay_corrida_previa("prueba"))
        self.assertFalse(corrida["limpia"])
        primera = correr(filas, cliente_jev=Cliente(), confirmar=True, repetida=experimento_fechas.hay_corrida_previa("desarrollo"))
        self.assertTrue(primera["limpia"])

    def test_huella_en_el_veredicto_y_estable(self):
        self.grabar(self.preparar())
        resultado = comparar("desarrollo")
        self.assertEqual(resultado["veredicto"]["huella_reglas"], huella_palabras_clave())
        self.assertEqual(len(huella_palabras_clave()), 12)
        reglas_distintas = {**fechas_reglas.PALABRAS_CLAVE, "induccion": (r"\botra\b",)}
        with mock.patch.object(fechas_reglas, "PALABRAS_CLAVE", reglas_distintas):
            self.assertNotEqual(huella_palabras_clave(), resultado["veredicto"]["huella_reglas"])

    def test_huella_de_las_reglas_medidas_en_el_experimento(self):
        # Si cambia, las reglas de producción ya no son las que midió F7b.
        self.assertEqual(huella_palabras_clave(), "d925b6f6f849")

    def test_el_veredicto_sin_jev_reporta_las_fuera_del_tope(self):
        filas = self.preparar(n=4, pasaje="Período para inducción a interesados")
        filas[-1]["en_propuesta"] = False
        exportar("desarrollo", filas, self.agentes)
        resultado = comparar("desarrollo")
        self.assertEqual(resultado["veredicto"]["decision"], "reglas")
        self.assertEqual(resultado["sin_verificar_por_tope"], 1)

    def test_detalle_solo_en_desarrollo(self):
        self.preparar(n=2, conjunto="desarrollo")
        self.preparar(n=2, conjunto="prueba")
        for conjunto, muestra in (("desarrollo", True), ("prueba", False)):
            salida = io.StringIO()
            with contextlib.redirect_stdout(salida):
                experimento_fechas.main(["reglas", conjunto, "--detalle"])
            self.assertEqual("399-c0" in salida.getvalue(), muestra, conjunto)

    def test_segunda_corrida_de_prueba_aborta_sin_crear_el_cliente(self):
        self.preparar(conjunto="prueba")
        (self.experimentos / "fechas_prueba_20261118T000000Z.json").write_text("{}", encoding="utf-8")
        with mock.patch.object(experimento_fechas, "ClienteJevSdk", side_effect=AssertionError("cliente")), \
                mock.patch.object(experimento_fechas, "obtener_configuracion", side_effect=AssertionError("config")):
            salida = io.StringIO()
            with contextlib.redirect_stdout(salida):
                self.assertEqual(experimento_fechas.main(["correr", "prueba", "--confirmar-envio"]), 1)
        self.assertIn("REPETIR", salida.getvalue())

    def test_repetir_fuerza_la_corrida_y_queda_marcada(self):
        self.preparar(conjunto="prueba")
        (self.experimentos / "fechas_prueba_20261118T000000Z.json").write_text("{}", encoding="utf-8")
        class Cliente:
            def __init__(self, config):
                pass
            def preguntar(self, estado, preguntas):
                return respuesta({local: ("induccion", 0.9, 0.95) for local in estado["candidatas"]})
            def cerrar(self):
                pass
        with mock.patch.object(experimento_fechas, "ClienteJevSdk", Cliente), \
                mock.patch.object(experimento_fechas, "obtener_configuracion", return_value=None), \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(experimento_fechas.main(["correr", "prueba", "--confirmar-envio", "--repetir"]), 0)
        nuevas = [r for r in self.experimentos.glob("fechas_prueba_*.json") if r.name != "fechas_prueba_20261118T000000Z.json"]
        self.assertEqual(len(nuevas), 1)
        corrida = json.loads(nuevas[0].read_text(encoding="utf-8"))
        self.assertFalse(corrida["limpia"])
        self.assertTrue(corrida["repetida"])

    def test_reglas_solo_puntua_desarrollo(self):
        import contextlib, io
        self.preparar(n=2, conjunto="desarrollo", pasaje="Período para inducción")
        self.preparar(n=2, conjunto="prueba", pasaje="Período para inducción")
        for conjunto, puntua in (("desarrollo", True), ("prueba", False)):
            salida = io.StringIO()
            with contextlib.redirect_stdout(salida):
                experimento_fechas.main(["reglas", conjunto])
            self.assertEqual("aciertos" in salida.getvalue(), puntua, conjunto)

    def test_la_vista_previa_no_crea_cliente_ni_lee_configuracion(self):
        self.preparar()
        with mock.patch.object(experimento_fechas, "ClienteJevSdk", side_effect=AssertionError("cliente")), \
                mock.patch.object(experimento_fechas, "obtener_configuracion", side_effect=AssertionError("config")):
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(experimento_fechas.main(["correr", "desarrollo"]), 0)


class Exportacion(unittest.TestCase):
    def test_particiones_fijadas(self):
        self.assertEqual(PARTICIONES["desarrollo"], ("399", "363"))
        self.assertEqual(PARTICIONES["prueba"], ("368", "327", "222"))

    def test_ciego_sin_etiquetas_ni_ubicacion_y_mapa_aparte(self):
        fila = {"id": "399-c0", "evento": "399-IGSS-2026", "fecha": "1 de enero de 2026", "fecha_iso": "2026-01-01",
                "pasaje": "p", "seccion": "s", "chunk_id": "ch", "pagina": 3, "en_propuesta": True, "tabla": True}
        with tempfile.TemporaryDirectory() as tmp:
            rutas = exportar("desarrollo", [fila], Path(tmp))
            ciego = json.loads(rutas["ciego"].read_text(encoding="utf-8"))
            mapa = json.loads(rutas["mapa"].read_text(encoding="utf-8"))
        self.assertEqual(ciego, [{"id": "399-c0", "evento": "399-IGSS-2026", "fecha": "1 de enero de 2026",
                                  "pasaje": "p", "seccion": "s"}])
        self.assertEqual(mapa["399-c0"]["chunk_id"], "ch")
        self.assertEqual(mapa["399-c0"]["pagina"], 3)
        self.assertTrue(mapa["399-c0"]["tabla"])


if __name__ == "__main__":
    unittest.main()
