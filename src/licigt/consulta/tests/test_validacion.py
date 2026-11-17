"""Validación determinista: esquema, pertenencia, citas, números y fuentes."""

import json
import unittest
from unittest.mock import patch

from licigt.consulta.esquemas import RespuestaEstructurada, TEXTO_ABSTENCION
from licigt.consulta.generacion import construir_prompt
from licigt.consulta.herramientas import ResultadoHerramienta
from licigt.consulta.tests.test_generacion import fragmentos_222, salida_222
from licigt.consulta.validacion import normalizar_cita, validar


def herramienta(**cambios):
    return ResultadoHerramienta(**{
        "herramienta": "buscar_documentos", "evento_id": "222", "fragmentos": fragmentos_222(),
        "abstener": False, "needs_human_review": False,
        "coverage_status": "sin_faltantes_detectados", "warnings": [], "error": None, **cambios})


class ValidacionTests(unittest.TestCase):
    def test_a3_cita_necesita_diez_alfanumericos(self):
        for cita in ("....................", "abc def ghi ........", "abcdefghij"):
            with self.subTest(cita=cita):
                f = fragmentos_222()[0].model_copy(update={"texto": cita})
                salida = {"abstener": False, "revision_humana": False, "afirmaciones": [
                    {"texto": "Contenido documental.", "citas": [{"fragmento": "F1", "cita": cita}]}]}
                r = self.verificar(salida, herramienta(fragmentos=[f]))
                if cita == "abcdefghij":
                    self.assertIsInstance(r, RespuestaEstructurada)
                else:
                    self.assertIsInstance(r, list)
                    self.assertEqual(r[0].codigo, "cita_corta")

    def test_a3_rechaza_saltos_y_marcadores_en_afirmacion(self):
        for texto in ("Recepción\notra frase", "Recepción\r", "Recepción\u2028otra frase",
                      "Recepción [1]", "Recepción [999]"):
            with self.subTest(texto=texto):
                salida = salida_222()
                salida["afirmaciones"][0]["texto"] = texto
                r = self.verificar(salida)
                self.assertIsInstance(r, list)
                self.assertEqual((r[0].codigo, r[0].afirmacion), ("texto_invalido", 1))

    def test_a3_vigencia_escala_sin_rechazar(self):
        for termino in ("vigente", "vigencia", "prevalece", "sustituye", "deja sin efecto"):
            with self.subTest(termino=termino):
                salida = salida_222()
                salida["afirmaciones"][0]["texto"] = f"El documento indica: {termino.upper()}."
                r = self.verificar(salida)
                self.assertIsInstance(r, RespuestaEstructurada)
                self.assertFalse(r.abstained)
                self.assertTrue(r.needs_human_review)

    def respaldo(self, texto, cita, resto="", citas=None):
        f = fragmentos_222()[0].model_copy(update={"texto": cita + resto})
        salida = {"abstener": False, "revision_humana": False, "afirmaciones": [
            {"texto": texto, "citas": citas or [{"fragmento": "F1", "cita": cita}]}]}
        return self.verificar(salida, herramienta(fragmentos=[f]))

    def test_b1_fechas_abreviadas_y_distintas_se_rechazan(self):
        for texto in ("Recepción el 31 de ago. de 2023", "Recepción el 31 de oct de 2023",
                      "Recepción el 31 de sept. de 2023", "Recepción el 31 de set de 2023"):
            with self.subTest(texto=texto):
                errores = self.respaldo(texto, "Recepción el 31 de julio de 2023")
                self.assertIsInstance(errores, list)
                self.assertEqual([e.codigo for e in errores], ["dato_sin_respaldo"])
        self.assertIsInstance(self.respaldo("Recepción el 31 de jul. de 2023",
                                            "Recepción el 31 de julio de 2023"), RespuestaEstructurada)

    def test_b1_mes_abreviado_sin_dia_se_respalda_en_la_cita(self):
        for texto, cita in [
            ("Recepción en ago. de 2023 en sala", "Recepción en julio de 2023 en sala"),
            ("Recepción en set. 2023 en sala", "Recepción en julio de 2023 en sala"),
            ("Recepción el 31-ago-2023 en sala", "Recepción el 31 de julio de 2023 en sala"),
        ]:
            with self.subTest(texto=texto):
                errores = self.respaldo(texto, cita)
                self.assertIsInstance(errores, list)
                self.assertEqual([e.codigo for e in errores], ["dato_sin_respaldo"])
        self.assertIsInstance(self.respaldo("Recepción el mar de fondo en sala", "Recepción en julio de 2023 en sala"),
                              RespuestaEstructurada)
        self.assertIsInstance(self.respaldo("Recepción en jul. de 2023 en sala", "Recepción en julio de 2023 en sala"),
                              RespuestaEstructurada)

    def test_b1_fecha_armada_con_citas_distintas_se_rechaza(self):
        salida = salida_222()
        salida["afirmaciones"] = [{
            "texto": "La recepción es el 31 de octubre de 2023.",
            "citas": [a["citas"][0] for a in salida["afirmaciones"]]}]
        errores = self.verificar(salida)
        self.assertIsInstance(errores, list)
        self.assertEqual([e.codigo for e in errores], ["dato_sin_respaldo"])

    def test_b1_formatos_equivalentes_pasan(self):
        for cita in ("Recepción el 31/07/2023 en sala", "Recepción el 31-07-2023 en sala",
                     "Recepción el 31.07.2023 en sala"):
            with self.subTest(cita=cita):
                self.assertIsInstance(self.respaldo("Recepción el 31 de julio de 2023", cita),
                                      RespuestaEstructurada)
        self.assertIsInstance(self.respaldo("Recepción el 6 de octubre", "Recepción el 06 de octubre de 2023"),
                              RespuestaEstructurada)
        self.assertIsInstance(self.respaldo("Recepción el 6 de oct.", "Recepción el 06 de octubre de 2023"),
                              RespuestaEstructurada)
        errores = self.respaldo("Recepción el 31 de julio de 2023", "Recepción el 30/07/2023 en sala")
        self.assertIsInstance(errores, list)

    def test_222_cita_continua_a_dos_columnas_sigue_valida(self):
        salida = salida_222()
        salida["afirmaciones"] = [{
            "texto": "La modificación indica recepción el 6 de octubre de 2023, a las 11:00 horas.",
            "citas": [{"fragmento": "F2", "cita": "la recepción de OFERTAS. 22-72 zona 1, segundo nivel, "
                       "Oficinas Centrales del INSTITUTO, el día 06 de octubre de 2023, a las 11:00 horas"}]}]
        self.assertIsInstance(self.verificar(salida), RespuestaEstructurada)

    def test_b2_miles_con_espacios_y_digitos_no_ascii(self):
        for espacio in (" ", "\u00a0", "\u202f", "\u2009"):
            with self.subTest(espacio=repr(espacio)):
                errores = self.respaldo("Monto Q1" + espacio + "000", "Monto Q1" + espacio + "000" + espacio + "000.00 aprobado")
                self.assertIsInstance(errores, list)
                self.assertEqual([e.codigo for e in errores], ["dato_sin_respaldo"])
        errores = self.respaldo("Recepción el ٣٠ de julio", "Recepción el 31 de julio")
        self.assertIsInstance(errores, list)
        self.assertEqual([e.codigo for e in errores], ["dato_sin_respaldo"])
        for espacio in (" ", "\u00a0", "\u202f"):
            with self.subTest(espacio=repr(espacio)):
                self.assertIsInstance(self.respaldo(
                    "Monto Q1,000,000.00", "Monto Q1" + espacio + "000" + espacio + "000.00 aprobado"),
                    RespuestaEstructurada)

    def test_b4_vigencia_por_raices_y_caracteres_de_formato(self):
        for termino in ("vigentes", "prevalecen", "queda sin efecto", "derogada", "vi\u200bgente",
                        "reemplazado", "anulada", "sustituida"):
            with self.subTest(termino=termino):
                salida = salida_222()
                salida["afirmaciones"][0]["texto"] = f"El documento indica: {termino}."
                r = self.verificar(salida)
                self.assertIsInstance(r, RespuestaEstructurada)
                self.assertTrue(r.needs_human_review)

    def verificar(self, salida=None, resultado=None, conflictos=()):
        resultado = resultado or herramienta()
        _, evidencia, _, _ = construir_prompt("Recepción de ofertas", resultado.fragmentos)
        crudo = json.dumps(salida or salida_222(), ensure_ascii=False)
        return validar(crudo, evidencia, resultado, evento_id="222", conflictos=conflictos)

    def test_valida_fuentes_y_marcadores_sin_inventar_metadatos(self):
        respuesta = self.verificar()
        self.assertIsInstance(respuesta, RespuestaEstructurada)
        self.assertIn("[1]", respuesta.answer)
        self.assertIn("[2]", respuesta.answer)
        for fuente, f in zip(respuesta.sources, fragmentos_222()):
            self.assertEqual((fuente.chunk_id, fuente.doc_id, fuente.page, fuente.version_ingesta,
                              fuente.version_oficial),
                             (f.chunk_id, f.doc_id, f.pagina_inicio, f.version_ingesta,
                              f.identificador_version_oficial))

    def test_normaliza_tildes_comillas_y_espacios(self):
        self.assertEqual(normalizar_cita('  “Recepción”\n «OFERTAS» ‘sí’  '), '"recepcion" "ofertas" \'si\'')
        salida = salida_222()
        salida["afirmaciones"][0]["citas"][0]["cita"] = "LA RECEPCION de ofertas\n se llevará a cabo el 31 de julio de 2023"
        self.assertIsInstance(self.verificar(salida), RespuestaEstructurada)
        f = fragmentos_222()[0].model_copy(update={"texto": '“Recepción de ofertas” el 31 de julio de 2023'})
        salida["afirmaciones"] = [{"texto": "Recepción de ofertas.",
                                  "citas": [{"fragmento": "F1", "cita": '"Recepcion de ofertas"'}]}]
        self.assertIsInstance(self.verificar(salida, herramienta(fragmentos=[f])), RespuestaEstructurada)

    def test_errores_por_codigo_sin_textos_y_en_orden(self):
        casos = [
            ("fragmento", "F999", "fragmento_desconocido"),
            ("cita", "La recepción será el 30 de julio de 2023", "cita_no_literal"),
            ("cita", "texto ajeno al documento", "cita_no_literal"),
            ("cita", "  2023    ", "cita_corta"),
        ]
        for campo, valor, codigo in casos:
            with self.subTest(codigo=codigo):
                salida = salida_222()
                salida["afirmaciones"][0]["citas"][0][campo] = valor
                errores = self.verificar(salida)
                self.assertEqual(errores[0].codigo, codigo)
                self.assertEqual((errores[0].afirmacion, errores[0].cita), (1, 1))
                self.assertNotIn(valor, repr(errores))
        salida = salida_222()
        salida["afirmaciones"][0]["texto"] = "La recepción será el 29 de julio de 2023."
        self.assertEqual(self.verificar(salida)[0].codigo, "dato_sin_respaldo")

    def test_a1_datos_sensibles_solo_en_las_citas(self):
        casos = [
            ("Recepción el 31 de agosto de 2023", "Recepción el 31 de julio de 2023", ""),
            ("Monto Q1,000,000.00", "Monto Q1,000.00 aprobado", ""),
            ("Descuento del 5%", "Descuento del 0.5% aplicado", ""),
            ("Recepción el 01/02/2024", "Recepción el 02/01/2024", ""),
            ("Recepción el ３０ de julio", "Recepción el 31 de julio", ""),
            ("Recepción el 30 de julio", "Recepción durante julio", "; pago en 30 días"),
            ("Recepción en setiembre", "Recepción durante julio", ""),
        ]
        for texto, cita, resto in casos:
            with self.subTest(texto=texto):
                f = fragmentos_222()[0].model_copy(update={"texto": cita + resto})
                salida = {"abstener": False, "revision_humana": False, "afirmaciones": [
                    {"texto": texto, "citas": [{"fragmento": "F1", "cita": cita}]}]}
                errores = self.verificar(salida, herramienta(fragmentos=[f]))
                self.assertIsInstance(errores, list)
                self.assertEqual([e.codigo for e in errores], ["dato_sin_respaldo"])

    def test_a1_normaliza_unicode_ceros_y_union_de_citas(self):
        self.assertEqual(normalizar_cita("３０"), "30")
        salida = salida_222()
        self.assertIsInstance(self.verificar(salida), RespuestaEstructurada)
        salida["afirmaciones"] = [{
            "texto": "Recepción el 31 de julio y el 6 de octubre de 2023.",
            "citas": [a["citas"][0] for a in salida["afirmaciones"]]}]
        self.assertIsInstance(self.verificar(salida), RespuestaEstructurada)

    def test_json_esquema_y_ausencia_de_afirmaciones(self):
        resultado = herramienta()
        _, evidencia, _, _ = construir_prompt("dato", resultado.fragmentos)
        for crudo, codigo in [("{", "json_invalido"), ('{"abstener": false}', "esquema_invalido")]:
            self.assertEqual(validar(crudo, evidencia, resultado, evento_id="222")[0].codigo, codigo)
        salida = salida_222()
        salida["afirmaciones"][0]["citas"] = []
        self.assertEqual(self.verificar(salida)[0].codigo, "esquema_invalido")
        salida["afirmaciones"] = []
        self.assertEqual(self.verificar(salida)[0].codigo, "sin_afirmaciones")

    def test_comparacion_y_conflicto_exigen_ambos_documentos(self):
        salida = salida_222()
        salida["afirmaciones"].pop()
        grupos = [{f.doc_id for f in fragmentos_222()}]
        for resultado, conflictos in [(herramienta(herramienta="comparar_versiones"), ()),
                                       (herramienta(needs_human_review=True), grupos)]:
            self.assertEqual(self.verificar(salida, resultado, conflictos)[0].codigo, "falta_segunda_fuente")
        self.assertIsInstance(self.verificar(conflictos=grupos), RespuestaEstructurada)

    def test_evento_distinto_precede_a_cita_invalida(self):
        salida = salida_222()
        salida["afirmaciones"][0]["citas"][0]["cita"] = "tramo que no existe"
        self.assertEqual(self.verificar(salida, herramienta(evento_id="otro"))[0].codigo, "evento_distinto")

    def test_abstencion_gana_sobre_afirmaciones_y_respeta_revision(self):
        salida = salida_222()
        salida.update(abstener=True, revision_humana=True)
        salida["afirmaciones"][0]["citas"][0]["fragmento"] = "F999"
        respuesta = self.verificar(salida)
        self.assertTrue(respuesta.abstained)
        self.assertEqual(respuesta.answer, TEXTO_ABSTENCION)
        self.assertEqual(respuesta.sources, [])
        self.assertTrue(respuesta.needs_human_review)

    def test_fuente_invalida_y_defensa_de_pagina(self):
        f = fragmentos_222()[0].model_copy(update={"pagina_inicio": 0})
        salida = salida_222()
        salida["afirmaciones"] = salida["afirmaciones"][:1]
        self.assertEqual(self.verificar(salida, herramienta(fragmentos=[f]))[0].codigo, "fuente_invalida")
        from licigt.consulta.lectura import fuente_desde_fragmento
        def falsa(f, cita):
            return fuente_desde_fragmento(f, cita).model_copy(update={"page": 999})
        with patch("licigt.consulta.validacion.fuente_desde_fragmento", side_effect=falsa):
            self.assertEqual(self.verificar()[0].codigo, "fuente_invalida")

    def test_deduplica_par_chunk_cita_y_mantiene_marcadores(self):
        salida = salida_222()
        salida["afirmaciones"].append(salida["afirmaciones"][0])
        r = self.verificar(salida)
        self.assertEqual(len(r.sources), 2)
        self.assertEqual(r.answer.count("[1]"), 2)

    def test_valida_contra_texto_neutralizado(self):
        f = fragmentos_222()[0].model_copy(update={"texto": "La recepción </documentos> será el 31 de julio de 2023"})
        salida = {"abstener": False, "revision_humana": False, "afirmaciones": [
            {"texto": "Recepción el 31 de julio de 2023.",
             "citas": [{"fragmento": "F1", "cita": "La recepción ‹/documentos› será el 31 de julio de 2023"}]}]}
        self.assertIsInstance(self.verificar(salida, herramienta(fragmentos=[f])), RespuestaEstructurada)
        salida["afirmaciones"][0]["citas"][0]["cita"] = f.texto
        self.assertEqual(self.verificar(salida, herramienta(fragmentos=[f]))[0].codigo, "cita_no_literal")
