"""Pruebas de la lectura tolerante del contrato del rol 2, sin servicios externos."""

import unittest

from pydantic import ValidationError

from licigt.consulta.lectura import (
    TIPOS_ALERTA_CONOCIDOS, Alerta, DocumentoComparado, FragmentoRecuperado,
    ResultadoBusqueda, ResultadoComparacion, fuente_desde_fragmento,
)


def fragmento(**cambios):
    """Forma exacta de un fragmento de buscar() mejorada: CAMPOS más los puntajes."""
    datos = {"chunk_id": "222-bases-p8-0", "doc_id": "222-bases", "tipo_documento": "bases",
             "version_ingesta": 1, "pagina_inicio": 8, "pagina_fin": 8,
             "seccion": "2.2.6 Constancia", "texto": "Se requiere constancia.",
             "url_origen": "https://ejemplo/bases.pdf", "identificador_version_oficial": None,
             "score": 0.91, "reranker": 0.91, "semantico": 0.62, "lexico": 0.4, "rrf": 0.016}
    return {**datos, **cambios}


def fragmento_comparado(**cambios):
    """Forma exacta de un fragmento de comparar_versiones(): CAMPOS y score, nada más."""
    datos = fragmento(**cambios)
    for campo in ("reranker", "semantico", "lexico", "rrf", "incluido_por"):
        datos.pop(campo, None)
    return datos


def busqueda(**cambios):
    """Forma exacta de lo que devuelve buscar() del rol 2."""
    datos = {"evento_id": "222", "variante": "mejorada", "suficiente": True,
             "fragmentos": [fragmento()], "alertas": []}
    return {**datos, **cambios}


def sin(diccionario, campo):
    return {k: v for k, v in diccionario.items() if k != campo}


class FragmentoTests(unittest.TestCase):
    def test_acepta_extras_y_forma_de_comparar(self):
        # comparar_versiones devuelve solo CAMPOS y score; el extra ajeno se ignora.
        de_comparar = fragmento_comparado(campo_ajeno="x")
        leido = FragmentoRecuperado.model_validate(de_comparar)
        self.assertIsNone(leido.reranker)
        self.assertEqual(leido.score, 0.91)
        extra = FragmentoRecuperado.model_validate(fragmento(incluido_por="posible_conflicto", ajeno=1))
        self.assertEqual(extra.incluido_por, "posible_conflicto")

    def test_opcionales_pueden_faltar(self):
        for campo in ("seccion", "url_origen", "identificador_version_oficial", "reranker",
                      "semantico", "lexico", "rrf", "incluido_por"):
            with self.subTest(campo=campo):
                self.assertIsNone(getattr(FragmentoRecuperado.model_validate(sin(fragmento(), campo)), campo))

    def test_nulos_en_opcionales(self):
        leido = FragmentoRecuperado.model_validate(fragmento(
            url_origen=None, identificador_version_oficial=None, semantico=None, seccion=None))
        self.assertIsNone(leido.url_origen)
        self.assertIsNone(leido.identificador_version_oficial)

    def test_falta_un_obligatorio_es_error_de_contrato(self):
        for campo in ("chunk_id", "doc_id", "tipo_documento", "version_ingesta",
                      "pagina_inicio", "pagina_fin", "texto", "score"):
            with self.subTest(campo=campo), self.assertRaises(ValidationError):
                FragmentoRecuperado.model_validate(sin(fragmento(), campo))


class AlertaTests(unittest.TestCase):
    def test_las_tres_formas_del_rol2(self):
        formas = (
            {"tipo": "cobertura_incompleta", "doc_id": "222-bases",
             "paginas_no_indexadas": [3, 4], "status": "requiere_revision"},
            {"tipo": "posible_conflicto", "doc_id": "222-mod", "documento": "Modificación Número 1",
             "numerales_modificados": ["2.2", "2.7"], "chunk_ids_afectados": ["222-bases-p8-0"]},
            {"tipo": "evento_con_modificaciones", "doc_id": "222-mod", "documento": "Modificación Número 1"},
        )
        for forma in formas:
            with self.subTest(forma=forma["tipo"]):
                self.assertEqual(Alerta.model_validate(dict(forma, ajeno=1)).tipo, forma["tipo"])
        self.assertEqual(TIPOS_ALERTA_CONOCIDOS,
                         ("cobertura_incompleta", "posible_conflicto", "evento_con_modificaciones"))

    def test_nulos_y_defectos(self):
        leida = Alerta.model_validate({"tipo": "cobertura_incompleta", "doc_id": "222-bases",
                                       "documento": None, "status": None, "paginas_no_indexadas": None})
        self.assertIsNone(leida.paginas_no_indexadas)
        self.assertIsNone(leida.documento)
        conflicto = Alerta.model_validate({"tipo": "posible_conflicto", "doc_id": "222-mod",
                                           "documento": None})
        self.assertEqual(conflicto.numerales_modificados, [])
        self.assertEqual(conflicto.chunk_ids_afectados, [])

    def test_obligatorios_y_tipo_libre(self):
        for datos in ({"doc_id": "222-bases"}, {"tipo": "cobertura_incompleta"}):
            with self.subTest(datos=datos), self.assertRaises(ValidationError):
                Alerta.model_validate(datos)
        # El tipo no es un Literal: uno desconocido no rompe la lectura.
        self.assertEqual(Alerta.model_validate({"tipo": "otra_cosa", "doc_id": "222-bases"}).tipo, "otra_cosa")


class ResultadosTests(unittest.TestCase):
    def test_busqueda_acepta_extras(self):
        leida = ResultadoBusqueda.model_validate(busqueda(
            ajeno=True, alertas=[{"tipo": "evento_con_modificaciones", "doc_id": "222-mod"}]))
        self.assertTrue(leida.suficiente)
        self.assertEqual(leida.alertas[0].tipo, "evento_con_modificaciones")

    def test_busqueda_sin_suficiente_falla(self):
        for campo in ("suficiente", "evento_id", "variante", "fragmentos"):
            with self.subTest(campo=campo), self.assertRaises(ValidationError):
                ResultadoBusqueda.model_validate(sin(busqueda(), campo))

    def test_comparacion(self):
        documentos = [
            {"doc_id": "222-bases", "tipo_documento": "bases",
             "identificador_version_oficial": None, "fragmentos": [fragmento_comparado()]},
            {"doc_id": "222-mod", "tipo_documento": "modificacion",
             "identificador_version_oficial": "Modificación Número 1",
             "fragmentos": [fragmento_comparado(chunk_id="222-mod-p1-0", doc_id="222-mod",
                                                 tipo_documento="modificacion", url_origen=None,
                                                 identificador_version_oficial="Modificación Número 1")]}]
        leida = ResultadoComparacion.model_validate(
            {"evento_id": "222", "documentos": documentos, "ajeno": 1})
        self.assertEqual([d.doc_id for d in leida.documentos], ["222-bases", "222-mod"])
        self.assertEqual(leida.documentos[1].identificador_version_oficial, "Modificación Número 1")
        self.assertIsInstance(leida.documentos[0].fragmentos[0], FragmentoRecuperado)

    def test_comparacion_obligatorios(self):
        for datos in ({"evento_id": "222"},
                      {"evento_id": "222", "documentos": [
                          {"doc_id": "222-bases", "tipo_documento": "bases", "fragmentos": []}]}):
            with self.subTest(datos=datos), self.assertRaises(ValidationError):
                ResultadoComparacion.model_validate(datos)
        DocumentoComparado.model_validate({"doc_id": "d", "tipo_documento": "bases",
                                           "identificador_version_oficial": None, "fragmentos": []})


class FuenteDesdeFragmentoTests(unittest.TestCase):
    def test_con_y_sin_url_origen(self):
        con_url = fuente_desde_fragmento(FragmentoRecuperado.model_validate(fragmento()),
                                         "Se requiere constancia.")
        self.assertEqual(con_url.source, "https://ejemplo/bases.pdf")
        sin_url = fuente_desde_fragmento(FragmentoRecuperado.model_validate(
            fragmento(url_origen=None)), "cita")
        self.assertEqual(sin_url.source, "222-bases")

    def test_pagina_unica_y_rango(self):
        unica = fuente_desde_fragmento(FragmentoRecuperado.model_validate(fragmento()), "cita")
        self.assertEqual((unica.page, unica.page_end), (8, None))
        rango = fuente_desde_fragmento(FragmentoRecuperado.model_validate(
            fragmento(pagina_fin=10)), "cita")
        self.assertEqual((rango.page, rango.page_end), (8, 10))

    def test_pagina_impresa_es_opcional_y_pasa_a_la_fuente(self):
        sin = FragmentoRecuperado.model_validate(fragmento())
        self.assertIsNone(sin.pagina_impresa)
        self.assertIsNone(fuente_desde_fragmento(sin, "cita").printed_page)
        con = FragmentoRecuperado.model_validate(fragmento(pagina_impresa=7))
        fuente = fuente_desde_fragmento(con, "cita")
        self.assertEqual((fuente.page, fuente.printed_page), (8, 7))
        self.assertEqual(fuente.model_dump()["printed_page"], 7)

    def test_pagina_impresa_dudosa_queda_en_none_sin_romper_la_cita(self):
        for dudoso in (0, -3, 7.5, "7", True):
            with self.subTest(valor=dudoso):
                f = FragmentoRecuperado.model_validate(fragmento(pagina_impresa=dudoso))
                self.assertIsNone(f.pagina_impresa)
                self.assertIsNone(fuente_desde_fragmento(f, "cita").printed_page)

    def test_mapea_identificadores(self):
        fuente = fuente_desde_fragmento(FragmentoRecuperado.model_validate(fragmento(
            identificador_version_oficial="Modificación Número 1", version_ingesta=2)), "cita")
        self.assertEqual(fuente.version_oficial, "Modificación Número 1")
        self.assertEqual(fuente.version_ingesta, 2)
        self.assertEqual(fuente.doc_id, "222-bases")
        self.assertEqual(fuente.chunk_id, "222-bases-p8-0")
        self.assertEqual(fuente.cita, "cita")


if __name__ == "__main__":
    unittest.main()
