"""Pruebas del contrato de consulta, sin servicios externos."""

import unittest

from pydantic import ValidationError

from licigt.consulta.esquemas import (
    TEXTO_ABSTENCION, BuscarDocumentosParams, CompararVersionesParams,
    ExtraerRequisitosParams, Fuente, RespuestaEstructurada,
)


def datos_fuente(**cambios):
    return dict({"doc_id": "bases", "source": "bases", "page": 2, "page_end": None,
                 "chunk_id": "bases-p2", "version_ingesta": 0, "version_oficial": None,
                 "cita": "Se requiere constancia."}, **cambios)


def datos_respuesta(**cambios):
    return dict({"answer": "Se requiere constancia.", "sources": [datos_fuente()],
                 "abstained": False, "tool_used": "buscar_documentos",
                 "needs_human_review": False, "evento_id": "222",
                 "coverage_status": "parcial"}, **cambios)


class EsquemasTests(unittest.TestCase):
    def test_aclaracion_valida_sin_fuentes(self):
        from licigt.consulta.esquemas import TEXTO_ACLARACION_FECHA
        respuesta = RespuestaEstructurada(**datos_respuesta(
            answer=TEXTO_ACLARACION_FECHA, sources=[], tool_used=None,
            needs_clarification=True, clarification_question=TEXTO_ACLARACION_FECHA))
        self.assertFalse(respuesta.abstained)
        self.assertTrue(respuesta.needs_clarification)

    def test_aclaracion_inconsistente_falla(self):
        datos = datos_respuesta(answer="¿Qué actividad?", sources=[], tool_used=None,
                                needs_clarification=True, clarification_question="¿Qué actividad?")
        for cambios in ({"abstained": True}, {"clarification_question": None},
                        {"clarification_question": " "}, {"answer": "Otro texto"},
                        {"tool_used": "buscar_documentos"}, {"needs_clarification": "true"}):
            with self.subTest(cambios=cambios), self.assertRaises(ValidationError):
                RespuestaEstructurada(**dict(datos, **cambios))

    def test_sin_aclaracion_no_admite_pregunta(self):
        with self.assertRaises(ValidationError):
            RespuestaEstructurada(**datos_respuesta(clarification_question="¿Cuál?"))
        respuesta = RespuestaEstructurada(**datos_respuesta())
        self.assertFalse(respuesta.needs_clarification)
        self.assertIsNone(respuesta.clarification_question)

    def test_respuesta_valida(self):
        respuesta = RespuestaEstructurada.model_validate(datos_respuesta())
        self.assertEqual(respuesta.sources[0].chunk_id, "bases-p2")
        self.assertFalse(respuesta.abstained)
        self.assertEqual(respuesta.warnings, [])

    def test_abstencion_valida(self):
        respuesta = RespuestaEstructurada.model_validate(datos_respuesta(
            answer=TEXTO_ABSTENCION, sources=[], abstained=True, tool_used=None))
        self.assertTrue(respuesta.abstained)
        self.assertEqual(respuesta.sources, [])
        self.assertEqual(respuesta.answer,
                         "No hay información suficiente en los documentos para responder")

    def test_respuesta_sin_fuentes_falla(self):
        with self.assertRaises(ValidationError):
            RespuestaEstructurada.model_validate(datos_respuesta(sources=[]))

    def test_abstencion_exige_texto_exacto(self):
        for texto in ("No sé", " " + TEXTO_ABSTENCION, TEXTO_ABSTENCION + " "):
            with self.subTest(texto=texto), self.assertRaises(ValidationError):
                RespuestaEstructurada.model_validate(datos_respuesta(answer=texto, abstained=True))

    def test_fuente_paginas(self):
        for cambios in ({"page": 0}, {"page_end": 1}):
            with self.subTest(cambios=cambios), self.assertRaises(ValidationError):
                Fuente.model_validate(datos_fuente(**cambios))
        for fin in (None, 2, 3):
            with self.subTest(fin=fin):
                self.assertEqual(Fuente.model_validate(datos_fuente(page_end=fin)).page_end, fin)
        self.assertEqual(Fuente.model_validate(datos_fuente(page=1)).page, 1)

    def test_fuente_cita_limites_y_recorte(self):
        for cita in ("", " \t\n", "x" * 501):
            with self.subTest(cita=cita), self.assertRaises(ValidationError):
                Fuente.model_validate(datos_fuente(cita=cita))
        for cita in ("x", "x" * 500):
            with self.subTest(longitud=len(cita)):
                self.assertEqual(Fuente.model_validate(datos_fuente(cita=" " + cita + " ")).cita, cita)

    def test_fuente_versiones_distintas(self):
        fuente = Fuente.model_validate(datos_fuente(version_ingesta=0, version_oficial="Modificación Número 1"))
        self.assertEqual(fuente.version_ingesta, 0)
        self.assertEqual(fuente.version_oficial, "Modificación Número 1")
        with self.assertRaises(ValidationError):
            Fuente.model_validate(datos_fuente(version_ingesta=-1))

    def test_textos_obligatorios_no_vacios(self):
        casos = [(Fuente, datos_fuente(), ("doc_id", "source", "chunk_id")),
                 (RespuestaEstructurada, datos_respuesta(), ("answer", "evento_id")),
                 (BuscarDocumentosParams, {"query": "fecha", "evento_id": "222"}, ("evento_id",)),
                 (ExtraerRequisitosParams, {"evento_id": "222"}, ("evento_id",)),
                 (CompararVersionesParams, {"tema": "fecha", "evento_id": "222"}, ("evento_id",))]
        for modelo, datos, campos in casos:
            for campo in campos:
                for valor in ("", " \t\n"):
                    with self.subTest(modelo=modelo.__name__, campo=campo, valor=valor):
                        with self.assertRaises(ValidationError):
                            modelo.model_validate(dict(datos, **{campo: valor}))

    def test_parametros_rechazan_contexto_de_acceso(self):
        for modelo, datos in (
            (BuscarDocumentosParams, {"query": "fecha", "evento_id": "222"}),
            (ExtraerRequisitosParams, {"evento_id": "222"}),
            (CompararVersionesParams, {"tema": "fecha", "evento_id": "222"}),
        ):
            for campo in ("tenant_id", "empresa", "rol", "usuario"):
                with self.subTest(modelo=modelo.__name__, campo=campo):
                    with self.assertRaises(ValidationError) as error:
                        modelo.model_validate(dict(datos, **{campo: "ajeno"}))
                    self.assertEqual(error.exception.errors()[0]["type"], "extra_forbidden")

    def test_salida_rechaza_campos_extra(self):
        for modelo, datos in ((Fuente, datos_fuente()), (RespuestaEstructurada, datos_respuesta())):
            with self.subTest(modelo=modelo.__name__), self.assertRaises(ValidationError):
                modelo.model_validate(dict(datos, extra="ajeno"))

    def test_query_limites_y_recorte(self):
        for query in ("", " \t\n", "x" * 501):
            with self.subTest(query=query), self.assertRaises(ValidationError):
                BuscarDocumentosParams(query=query, evento_id="222")
        for query in ("x", "x" * 500):
            with self.subTest(longitud=len(query)):
                self.assertEqual(BuscarDocumentosParams(
                    query=" " + query + " ", evento_id="222").query, query)

    def test_k_limites_y_defecto(self):
        for k in (0, 11):
            with self.subTest(k=k), self.assertRaises(ValidationError):
                BuscarDocumentosParams(query="fecha", evento_id="222", k=k)
        for k in (1, 10):
            with self.subTest(k=k):
                self.assertEqual(BuscarDocumentosParams(query="fecha", evento_id="222", k=k).k, k)
        self.assertEqual(BuscarDocumentosParams(query="fecha", evento_id="222").k, 5)

    def test_tipo_documento(self):
        with self.assertRaises(ValidationError):
            BuscarDocumentosParams(query="fecha", evento_id="222", tipo_documento="otro")
        for tipo in (None, "bases", "anexo", "aclaracion", "modificacion"):
            with self.subTest(tipo=tipo):
                self.assertEqual(BuscarDocumentosParams(
                    query="fecha", evento_id="222", tipo_documento=tipo).tipo_documento, tipo)
        self.assertIsNone(BuscarDocumentosParams(query="fecha", evento_id="222").tipo_documento)

    def test_categoria(self):
        with self.assertRaises(ValidationError):
            ExtraerRequisitosParams(evento_id="222", categoria="otra")
        for categoria in (None, "administrativa", "legal", "tecnica", "financiera"):
            with self.subTest(categoria=categoria):
                self.assertEqual(ExtraerRequisitosParams(
                    evento_id="222", categoria=categoria).categoria, categoria)
        self.assertIsNone(ExtraerRequisitosParams(evento_id="222").categoria)

    def test_comparar_ids(self):
        parametros = CompararVersionesParams(evento_id="222", tema="fecha")
        self.assertIsNone(parametros.doc_base_id)
        self.assertIsNone(parametros.doc_cambio_id)
        for ids in ({"doc_base_id": "bases"}, {"doc_cambio_id": "cambio"},
                    {"doc_base_id": "bases", "doc_cambio_id": "bases"}):
            with self.subTest(ids=ids), self.assertRaises(ValidationError):
                CompararVersionesParams(evento_id="222", tema="fecha", **ids)
        parametros = CompararVersionesParams(evento_id="222", tema="fecha",
                                              doc_base_id="bases", doc_cambio_id="cambio")
        self.assertEqual((parametros.doc_base_id, parametros.doc_cambio_id), ("bases", "cambio"))

    def test_comparar_ids_no_vacios(self):
        for vacio in ("", " \t"):
            with self.subTest(vacio=vacio), self.assertRaises(ValidationError):
                CompararVersionesParams(evento_id="222", tema="fecha",
                                        doc_base_id=vacio, doc_cambio_id="cambio")

    def test_numeros_y_booleanos_sin_coercion(self):
        # La salida del modelo no debe colar true como página 1 ni "7" como k.
        for modelo, datos in (
            (Fuente, datos_fuente(page=True)), (Fuente, datos_fuente(page="3")),
            (Fuente, datos_fuente(page_end=2.0)), (Fuente, datos_fuente(version_ingesta=True)),
            (BuscarDocumentosParams, {"query": "fecha", "evento_id": "222", "k": True}),
            (BuscarDocumentosParams, {"query": "fecha", "evento_id": "222", "k": "7"}),
            (RespuestaEstructurada, datos_respuesta(abstained="false")),
            (RespuestaEstructurada, datos_respuesta(needs_human_review=0)),
        ):
            with self.subTest(modelo=modelo.__name__, datos=datos), self.assertRaises(ValidationError):
                modelo.model_validate(datos)

    def test_warnings_no_vacios(self):
        with self.assertRaises(ValidationError):
            RespuestaEstructurada.model_validate(datos_respuesta(warnings=["", "páginas 3 y 4 sin OCR"]))

    def test_tema_limites_y_recorte(self):
        for tema in ("", " \t\n", "x" * 501):
            with self.subTest(tema=tema), self.assertRaises(ValidationError):
                CompararVersionesParams(evento_id="222", tema=tema)
        for tema in ("x", "x" * 500):
            with self.subTest(longitud=len(tema)):
                self.assertEqual(CompararVersionesParams(
                    evento_id="222", tema=" " + tema + " ").tema, tema)

    def test_literales_respuesta(self):
        for campo, valor in (("tool_used", "otra"), ("coverage_status", "completo")):
            with self.subTest(campo=campo), self.assertRaises(ValidationError):
                RespuestaEstructurada.model_validate(datos_respuesta(**{campo: valor}))
        for herramienta in (None, "buscar_documentos", "extraer_requisitos", "comparar_versiones"):
            with self.subTest(herramienta=herramienta):
                respuesta = RespuestaEstructurada.model_validate(datos_respuesta(
                    tool_used=herramienta, coverage_status="sin_faltantes_detectados"))
                self.assertEqual(respuesta.tool_used, herramienta)

    def test_campos_anulables_sin_defecto_son_obligatorios(self):
        for modelo, datos, campos in (
            (Fuente, datos_fuente(), ("page_end", "version_oficial")),
            (RespuestaEstructurada, datos_respuesta(), ("tool_used",)),
        ):
            for campo in campos:
                incompletos = {k: v for k, v in datos.items() if k != campo}
                with self.subTest(modelo=modelo.__name__, campo=campo):
                    with self.assertRaises(ValidationError):
                        modelo.model_validate(incompletos)

    def test_modelos_inmutables(self):
        for modelo, campo, valor in (
            (Fuente.model_validate(datos_fuente()), "page", 3),
            (RespuestaEstructurada.model_validate(datos_respuesta()), "answer", "Otro texto"),
            (BuscarDocumentosParams(query="fecha", evento_id="222"), "k", 6),
            (ExtraerRequisitosParams(evento_id="222"), "categoria", "legal"),
            (CompararVersionesParams(evento_id="222", tema="fecha"), "tema", "plazo"),
        ):
            with self.subTest(modelo=type(modelo).__name__):
                with self.assertRaises(ValidationError) as error:
                    setattr(modelo, campo, valor)
                self.assertEqual(error.exception.errors()[0]["type"], "frozen_instance")


if __name__ == "__main__":
    unittest.main()
