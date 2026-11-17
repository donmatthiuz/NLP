"""Validación determinista: esquema, pertenencia, citas, datos literales y fuentes."""

import json
import unittest
from unittest.mock import patch

from licigt.consulta.esquemas import RespuestaEstructurada, TEXTO_ABSTENCION
from licigt.consulta.generacion import Afirmacion, construir_prompt
from licigt.consulta.herramientas import ResultadoHerramienta
from licigt.consulta.tests.test_generacion import fragmentos_222, salida_222
from licigt.consulta.validacion import _armar, normalizar_cita, validar

# Pasajes literales del 222: bases 00001 (p. 1) y 00115 (p. 27), modificación 00009 (dos columnas).
B001 = ("La recepción de ofertas se llevará a cabo el 31 de julio de 2023, a las 11:00 horas (hora\n"
        "     límite 11:30), en Salones Los Volcanes, ubicados en la 7ª. Avenida 22-72 Zona 1, segundo\n"
        "     nivel de Oficinas Centrales del Instituto y la apertura de plicas se realizará en el mismo\n"
        "     lugar, después de concluida la recepción de ofertas.")
B115 = ("c)    Con vigencia de ciento veinte (120) días a partir de la fecha de recepción y apertura\n"
        "               de PLICAS. Sin embargo, con el adjudicatario puede convenirse su prórroga.\n\n"
        "d)    Constituida por un porcentaje no menor del uno por ciento (1%) ni mayor del cinco\n"
        "               por ciento (5%) del valor total del CONTRATO.")
M009 = ("2.2.5   Período para la preparación del               puede elaborarse en GUATECOMPRAS desde el\n"
        "              Lugar, dirección, fecha y hora para           En Salones Los Volcanes, ubicados en la 7ª. Avenida\n"
        "              la recepción de OFERTAS.                      22-72 zona 1, segundo nivel, Oficinas Centrales del\n"
        "                                                            INSTITUTO, el día 06 de octubre de 2023, a las\n"
        "                                                            11:00 horas (hora límite 11:30), transcurrido este")
CITA_PCT = "porcentaje no menor del uno por ciento (1%) ni mayor del cinco por ciento (5%) del valor total del CONTRATO"
CITA_VIG = "Con vigencia de ciento veinte (120) días a partir de la fecha de recepción y apertura"
CITA_REC = "La recepción de ofertas se llevará a cabo el 31 de julio de 2023, a las 11:00 horas (hora\n     límite 11:30)"


def herramienta(**cambios):
    return ResultadoHerramienta(**{
        "herramienta": "buscar_documentos", "evento_id": "222", "fragmentos": fragmentos_222(),
        "abstener": False, "needs_human_review": False,
        "coverage_status": "sin_faltantes_detectados", "warnings": [], "error": None, **cambios})


class ValidacionTests(unittest.TestCase):
    def armar(self, texto, cita, datos=(), resto="", citas=None):
        """Una afirmación con su cita copiada del fragmento F1; datos como literales de la cita 1."""
        f = fragmentos_222()[0].model_copy(update={"texto": cita + resto})
        salida = {"abstener": False, "revision_humana": False, "afirmaciones": [
            {"texto": texto, "citas": citas or [{"fragmento": "F1", "cita": cita}],
             "datos": [{"cita": 1, "literal": d} for d in datos]}]}
        return self.verificar(salida, herramienta(fragmentos=[f]))

    def armar_en(self, fragmento, texto, cita, datos=()):
        """Como armar, pero el fragmento F1 es el pasaje real completo."""
        f = fragmentos_222()[0].model_copy(update={"texto": fragmento})
        salida = {"abstener": False, "revision_humana": False, "afirmaciones": [
            {"texto": texto, "citas": [{"fragmento": "F1", "cita": cita}],
             "datos": [{"cita": 1, "literal": d} for d in datos]}]}
        return self.verificar(salida, herramienta(fragmentos=[f]))

    def codigos(self, errores):
        self.assertIsInstance(errores, list)
        return [e.codigo for e in errores]

    def test_a3_cita_necesita_diez_alfanumericos(self):
        for cita in ("....................", "abc def ghi ........", "abcdefghij"):
            with self.subTest(cita=cita):
                r = self.armar("Contenido documental.", cita)
                if cita == "abcdefghij":
                    self.assertIsInstance(r, RespuestaEstructurada)
                else:
                    self.assertEqual(self.codigos(r), ["cita_corta"])

    def test_a3_rechaza_saltos_y_marcadores_en_afirmacion(self):
        for texto in ("Recepción\notra frase {1}", "Recepción\r{1}", "Recepción otra frase {1}",
                      "Recepción [1] {1}", "Recepción [999] {1}", "Recepción ［2］ {1}", "Recepción [²] {1}",
                      "Recepción [٢] {1}"):
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
                salida["afirmaciones"][0]["texto"] = f"El documento indica: {termino.upper()} {{1}}."
                r = self.verificar(salida)
                self.assertIsInstance(r, RespuestaEstructurada)
                self.assertFalse(r.abstained)
                self.assertTrue(r.needs_human_review)

    def test_b4_vigencia_por_raices(self):
        for termino in ("vigentes", "prevalecen", "queda sin efecto", "derogada",
                        "reemplazado", "anulada", "sustituida"):
            with self.subTest(termino=termino):
                salida = salida_222()
                salida["afirmaciones"][0]["texto"] = f"El documento indica: {termino} {{1}}."
                r = self.verificar(salida)
                self.assertIsInstance(r, RespuestaEstructurada)
                self.assertTrue(r.needs_human_review)

    def test_b4_caracter_de_formato_en_la_vigencia_se_rechaza(self):
        salida = salida_222()
        salida["afirmaciones"][0]["texto"] = "El documento indica: vi​gente {1}."
        self.assertEqual(self.codigos(self.verificar(salida)), ["texto_invalido"])

    def test_h1_cita_que_empieza_a_mitad_de_un_numero(self):
        for cita, fragmento in [("1 de julio de 2023", "Recepción el 31 de julio de 2023 en sala"),
                                ("20) días hábiles contados", "ciento veinte (120) días hábiles contados"),
                                ("31 de julio de 202", "Recepción el 31 de julio de 2023 en sala")]:
            with self.subTest(cita=cita):
                self.assertEqual(self.codigos(self.armar_fragmento(fragmento, cita)), ["cita_no_literal"])
        self.assertIsInstance(self.armar_fragmento("Recepción el 31 de julio de 2023 en sala",
                                                   "31 de julio de 2023 en sala"), RespuestaEstructurada)

    def armar_fragmento(self, fragmento, cita):
        f = fragmentos_222()[0].model_copy(update={"texto": fragmento})
        salida = {"abstener": False, "revision_humana": False, "afirmaciones": [
            {"texto": "Dato documental.", "datos": [], "citas": [{"fragmento": "F1", "cita": cita}]}]}
        return self.verificar(salida, herramienta(fragmentos=[f]))

    def test_h1_literal_que_empieza_a_mitad_de_un_numero(self):
        cita = "La recepción de ofertas se llevará a cabo el 31 de julio de 2023"
        for literal in ("1 de julio de 2023", "31 de julio de 202", "31 de julio de 2023 y 5"):
            with self.subTest(literal=literal):
                self.assertEqual(self.codigos(self.armar("Recepción el {1}.", cita, [literal])),
                                 ["dato_no_literal"])
        self.assertIsInstance(self.armar("Recepción el {1}.", cita, ["31 de julio de 2023"]),
                              RespuestaEstructurada)

    def test_h1_separadores_numericos_cuentan_como_continuacion(self):
        for texto, literal in [("Descuento aplicado del 0.5% en total", "5%"),
                               ("Monto Q1,000,000.00 aprobado", "Q1,000"),
                               ("Monto Q1,000,000.00 aprobado", "000,000"),
                               ("Fecha 2023-07-31 en sala", "2023-07")]:
            with self.subTest(literal=literal):
                self.assertEqual(self.codigos(self.armar("Dato {1}.", texto, [literal])),
                                 ["dato_no_literal"])
        for texto, literal in [("Descuento aplicado del 5%. Fin", "5%"), ("Monto de Q1,000.00. Fin", "Q1,000.00"),
                               ("Recepción 06 de octubre de 2023, a las 11:00 horas", "06 de octubre de 2023")]:
            with self.subTest(literal=literal):
                self.assertIsInstance(self.armar("Dato {1}.", texto, [literal]), RespuestaEstructurada)

    def test_h2_datos_de_varias_citas_se_rechazan(self):
        salida = salida_222()
        salida["afirmaciones"] = [{
            "texto": "La recepción es el {1} y el {2}.",
            "citas": [a["citas"][0] for a in salida["afirmaciones"]],
            "datos": [{"cita": 1, "literal": "31 de julio de 2023"}, {"cita": 2, "literal": "06 de octubre de 2023"}]}]
        self.assertEqual(self.codigos(self.verificar(salida)), ["datos_de_varias_citas"])
        salida["afirmaciones"][0]["texto"] = "La recepción es el {1} de {2}."
        salida["afirmaciones"][0]["datos"] = [{"cita": 1, "literal": "31"}, {"cita": 2, "literal": "octubre"}]
        self.assertEqual(self.codigos(self.verificar(salida)), ["datos_de_varias_citas"])

    def test_h4_fecha_y_hora_de_citas_distintas_se_rechazan(self):
        salida = salida_222()
        salida["afirmaciones"] = [{
            "texto": "La recepción es el {1}, a las {2}.",
            "citas": [{"fragmento": "F2", "cita": "INSTITUTO, el día 06 de octubre de 2023"},
                      {"fragmento": "F1", "cita": "a las 11:00 horas"}],
            "datos": [{"cita": 1, "literal": "06 de octubre de 2023"}, {"cita": 2, "literal": "11:00 horas"}]}]
        self.assertEqual(self.codigos(self.verificar(salida)), ["datos_de_varias_citas"])

    def test_h4_porcentaje_no_sale_de_un_plazo(self):
        self.assertEqual(self.codigos(self.armar("Garantía del {1}.", "plazo de ciento veinte (120) días hábiles",
                                                 ["120%"])), ["dato_no_literal"])

    def test_h3_datos_escritos_fuera_de_un_marcador(self):
        for texto in ("Recepción el 31 de octubre.", "Recepción el 31/ago/2023.", "Recepción en ago-2023.",
                      "Recepción el 31ago2023.", "Recepción el August 31.", "Recepción en agosto.",
                      "Recepción en Sept. próximo.", "Recepción en set próximo.", "Recepción en setiembre.",
                      "Recepción en Dec próximo.", "Recepción el ٣٠ de julio.", "Recepción el ３０ de julio.",
                      "Recepción a las 11 horas.", "Descuento del 120%."):
            with self.subTest(texto=texto):
                self.assertEqual(self.codigos(self.armar(texto, "Recepción durante la semana")),
                                 ["dato_fuera_de_literal"])

    def test_h3_h6_caracteres_ocultos_y_alfabetos_ajenos(self):
        for texto in ("Recepción en octu­bre.", "Recepción en agos​to.", "Recepción en оctubre.",
                      "Recepción en аgosto.", "Recepción ［2］.", "Recepción [²].", "Recepción [٢].",
                      "Recepción ‮octubre.", "Recepción en 日本."):
            with self.subTest(texto=texto):
                self.assertIn(self.codigos(self.armar(texto, "Recepción durante la semana"))[0],
                              {"texto_invalido", "dato_fuera_de_literal"})
        self.assertEqual(self.codigos(self.armar("Recepción en octu­bre.", "Recepción durante la semana")),
                         ["texto_invalido"])

    def test_h3_literal_con_caracteres_prohibidos(self):
        for literal in ("31 de оctubre", "31 de oc​tubre", "31 de [1] octubre"):
            with self.subTest(literal=literal):
                cita = "Recepción el " + literal + " en sala"
                self.assertEqual(self.codigos(self.armar("Recepción {1}.", cita, [literal])), ["texto_invalido"])

    def test_marcadores_bien_formados_y_usados(self):
        cita = "La recepción de ofertas se llevará a cabo el 31 de julio de 2023"
        for texto, codigo in [("Recepción {2}.", "texto_invalido"), ("Recepción.", "texto_invalido"),
                              ("Recepción {1.", "texto_invalido"), ("Recepción {a} {1}.", "texto_invalido"),
                              ("Recepción {0} {1}.", "texto_invalido"), ("Recepción {01} {1}.", "texto_invalido"),
                              ("Recepción } {1}.", "texto_invalido")]:
            with self.subTest(texto=texto):
                self.assertEqual(self.codigos(self.armar(texto, cita, ["31 de julio de 2023"])), [codigo])
        self.assertEqual(self.codigos(self.armar("Recepción {1}; repito {1}.", cita, ["31 de julio de 2023"])),
                         ["marcador_pegado"])

    def test_indice_de_cita_fuera_de_rango(self):
        salida = salida_222()
        salida["afirmaciones"][0]["datos"][0]["cita"] = 2
        self.assertEqual(self.codigos(self.verificar(salida)), ["dato_no_literal"])

    def test_literal_exacto_sin_ceros_ni_formatos_cambiados(self):
        for literal, cita in [("6 de octubre de 2023", "el 06 de octubre de 2023"),
                              ("31 de julio de 2023", "el 31/07/2023 en sala"),
                              ("31 de ago. de 2023", "el 31 de julio de 2023 en sala"),
                              ("Q1,000,000.00", "monto Q1 000 000.00 aprobado"),
                              ("٣٠", "el 30 de julio de 2023 en sala"),
                              ("30 de julio", "pago en 30 días y recepción durante julio")]:
            with self.subTest(literal=literal):
                self.assertEqual(self.codigos(self.armar("Dato {1}.", cita, [literal])), ["dato_no_literal"])
        self.assertIsInstance(self.armar("Dato {1}.", "el 31   de  julio de 2023 en sala", ["31 de julio  de 2023"]),
                              RespuestaEstructurada)
        self.assertIsInstance(self.armar("Dato {1}.", "el ３１ de julio de 2023 en sala", ["31 de julio de 2023"]),
                              RespuestaEstructurada)

    def test_hora_sin_minutos_ya_no_es_falso_rechazo(self):
        cita = "En Salones Los Volcanes, a las 11:00 horas (hora límite 11:30)"
        r = self.armar("La recepción es a las {1}.", cita, ["11:00 horas"])
        self.assertIsInstance(r, RespuestaEstructurada)
        self.assertIn("a las 11:00 horas.", r.answer)
        self.assertEqual(self.codigos(self.armar("La recepción es a las 11 horas.", cita)),
                         ["dato_fuera_de_literal"])

    def test_222_cita_continua_a_dos_columnas_con_dato_literal_y_revision(self):
        salida = salida_222()
        salida["afirmaciones"] = [{
            "texto": "La recepción de ofertas es el {1}.",
            "citas": [{"fragmento": "F2", "cita": "la recepción de OFERTAS. 22-72 zona 1, segundo nivel, "
                       "Oficinas Centrales del INSTITUTO, el día 06 de octubre de 2023, a las 11:00 horas"}],
            "datos": [{"cita": 1, "literal": "06 de octubre de 2023, a las 11:00 horas"}]}]
        r = self.verificar(salida)
        self.assertIsInstance(r, RespuestaEstructurada)
        self.assertEqual(r.answer, "La recepción de ofertas es el 06 de octubre de 2023, a las 11:00 horas. [1]")
        self.assertTrue(r.needs_human_review)

    def test_afirmacion_sin_datos_y_dos_afirmaciones_con_datos_propios(self):
        r = self.armar("Se requiere constancia de inscripción en el RGAE.",
                       "constancia de inscripción vigente en el RGAE")
        self.assertIsInstance(r, RespuestaEstructurada)
        self.assertEqual(r.answer, "Se requiere constancia de inscripción en el RGAE. [1]")
        r = self.verificar()
        self.assertIsInstance(r, RespuestaEstructurada)
        self.assertEqual(r.answer, "Las bases indican recepción el 31 de julio de 2023. [1]\n"
                                   "La modificación indica recepción el 06 de octubre de 2023. [2]")

    def test_h5_modificacion_o_aclaracion_como_unica_fuente_escala(self):
        cita = ("la recepción de OFERTAS. 22-72 zona 1, segundo nivel, "
                "Oficinas Centrales del INSTITUTO, el día 06 de octubre de 2023, a las 11:00 horas")
        for texto in ("La fecha que rige es la de la modificación.", "La de las bases ya no aplica.",
                      "Esta es la fecha definitiva del evento."):
            with self.subTest(texto=texto):
                salida = {"abstener": False, "revision_humana": False, "afirmaciones": [
                    {"texto": texto, "datos": [], "citas": [{"fragmento": "F2", "cita": cita}]}]}
                r = self.verificar(salida)
                self.assertIsInstance(r, RespuestaEstructurada)
                self.assertTrue(r.needs_human_review)
        f = fragmentos_222()[1].model_copy(update={"tipo_documento": "aclaracion"})
        salida = {"abstener": False, "revision_humana": False, "afirmaciones": [
            {"texto": "Se aclara el punto.", "datos": [], "citas": [{"fragmento": "F1", "cita": cita}]}]}
        self.assertTrue(self.verificar(salida, herramienta(fragmentos=[f])).needs_human_review)

    def test_bases_como_unica_fuente_no_escala(self):
        r = self.armar("Se requiere constancia de inscripción en el RGAE.", "constancia de inscripción en el RGAE")
        self.assertFalse(r.needs_human_review)

    def test_n1_n2_n6_marcador_pegado_a_otro_texto_o_marcador(self):
        casos = [("El seguro de sostenimiento es del {1}% del valor.", B115, CITA_PCT, ["1"]),
                 ("El seguro de sostenimiento es del {1}{2}% del valor.", B115, CITA_PCT, ["1", "5"]),
                 ("La recepción de ofertas es el {1}/{2}/{3}.", B001, CITA_REC, ["31", "1", "2023"]),
                 ("La recepción de ofertas es a las {1}:{2} horas.", B001, CITA_REC, ["1", "31"]),
                 ("La vigencia del seguro es de {1}{1} días.", B115, CITA_VIG, ["120"]),
                 ("El seguro es obligatorio [{1}].", B115, CITA_PCT, ["5"]),
                 ("La recepción es el {1} de ma{2}o de {3}.", B001, CITA_REC, ["31", "y", "2023"]),
                 ("La vigencia corre desde el {1} de octu{2}re.", B115, CITA_VIG, ["120", "d"]),
                 ("La recepción es en a{1}ril.", B001, CITA_REC, ["31"]),
                 ("La vigencia es de {1}.5 días.", B115, CITA_VIG, ["120"]),
                 ("La vigencia es de{1}.", B115, CITA_VIG, ["120"])]
        for texto, fragmento, cita, datos in casos:
            with self.subTest(texto=texto):
                self.assertEqual(self.codigos(self.armar_en(fragmento, texto, cita, datos)), ["marcador_pegado"])

    def test_c5_cierre_de_oracion_tras_marcador(self):
        for texto in ("El plazo es de quince ({1}).", "Según el numeral ({1}); además aplica.", "La vigencia es {1}), según.",
                      "La vigencia es {1}.. Fin.", "La vigencia es {1}.) días."):
            with self.subTest(texto=texto):
                self.assertIsInstance(self.armar_en(B115, texto, CITA_VIG, ["120"]), RespuestaEstructurada)
        for texto, datos in (("Vigencia {1}.{2}", ["120", "días"]), ("Vigencia {1},{2}", ["120", "días"]),
                             ("Vigencia {1}.5 días.", ["120"]), ("Vigencia {1}a.", ["120"]),
                             ("Vigencia {1}%.", ["120"]), ("Vigencia {1}.a.", ["120"])):
            with self.subTest(texto=texto):
                self.assertEqual(self.codigos(self.armar_en(B115, texto, CITA_VIG, datos)), ["marcador_pegado"])

    def test_c5_lista_blanca_con_rayas_y_comillas(self):
        texto = "Según «las bases» — “vigentes” – ‘ahora’ ’ok’ aplica."
        self.assertIsInstance(self.armar(texto, "Recepción durante la semana"), RespuestaEstructurada)
        for texto in ("Recepción de ɡarantías — ok.", "Recepción — octubre.", "Recepción “ᴏctubre”."):
            with self.subTest(texto=texto):
                self.assertIn(self.codigos(self.armar(texto, "Recepción durante la semana"))[0],
                              {"texto_invalido", "dato_fuera_de_literal"})
        self.assertEqual(self.codigos(self.armar("Recepción “ɡ”.", "Recepción durante la semana")), ["texto_invalido"])

    def test_n1_marcador_aislado_pasa(self):
        for texto in ("{1} es la vigencia.", "La vigencia es de {1}.", "La vigencia ({1}) según las bases.",
                      "La vigencia, {1}, aplica.", "La vigencia es de {1}", "La vigencia es de ({1})",
                      "Vigencia: {1}. Fin."):
            with self.subTest(texto=texto):
                self.assertIsInstance(self.armar_en(B115, texto, CITA_VIG, ["120"]), RespuestaEstructurada)

    def test_n1_cada_dato_se_usa_exactamente_una_vez(self):
        self.assertEqual(self.codigos(self.armar_en(B115, "Vigencia de {1} y {2}.", CITA_VIG, ["120"])),
                         ["texto_invalido"])
        self.assertEqual(self.codigos(self.armar_en(B115, "Vigencia de {1}.", CITA_VIG, ["120", "días"])),
                         ["texto_invalido"])

    def test_n1_segunda_barrera_sobre_la_linea_armada(self):
        def armada(texto, literal):
            a = Afirmacion.model_validate({"texto": texto, "datos": [{"cita": 1, "literal": literal}],
                                           "citas": [{"fragmento": "F1", "cita": "Con vigencia de ciento"}]})
            return _armar(a, [literal])
        self.assertEqual(armada("Vigencia de {1}.", "120 días"), ("Vigencia de 120 días.", None))
        self.assertEqual(armada("Vigencia de {1}.", "[2]")[1], "texto_invalido")
        self.assertEqual(armada("Vigencia de octubre {1}.", "120 días")[1], "dato_fuera_de_literal")
        self.assertEqual(armada("Vigencia de {1}.", "octubre de 2023"), ("Vigencia de octubre de 2023.", None))

    def test_n3_lista_blanca_de_caracteres_en_el_texto(self):
        for texto in ("Recepción de ɡarantías.", "Recepcıón de ofertas.", "Recepción de ȷunio.", "Recepción de ɑgosto.",
                      "Recepción de ᴏctubre.", "Recepción de ⠀ofertas.", "Recepción de ofertas %.",
                      "Recepción de ofertas/otras.", "Recepción de ofertas [a].", "Recepción de ofertas\tahora.",
                      "Recepción de ofertas € ahora."):
            with self.subTest(texto=texto):
                self.assertEqual(self.codigos(self.armar(texto, "Recepción durante la semana")), ["texto_invalido"])
        texto = "¿Qué dice? ¡Sí! \"ok\" 'ok' (ÁÉÍÓÚÜÑ áéíóúüñ): a-b; c, d."
        self.assertIsInstance(self.armar(texto, "Recepción durante la semana"), RespuestaEstructurada)

    def test_n3_riesgo_residual_mes_partido_con_espacios(self):
        # Declarado: requiere inyección y deja un texto visiblemente roto.
        self.assertIsInstance(self.armar("Recepción en oc tubre.", "Recepción durante la semana"),
                              RespuestaEstructurada)

    def test_n4_cita_que_empieza_o_termina_dentro_de_un_numero(self):
        for cita in ("(hora\n     límite 11:", ":30), en Salones Los Volcanes, ubicados",
                     "-72 Zona 1, segundo\n     nivel de Oficinas"):
            with self.subTest(cita=cita):
                self.assertEqual(self.codigos(self.armar_en(B001, "Dato documental.", cita)), ["cita_no_literal"])
        self.assertIsInstance(self.armar_en(B001, "Dato documental.", "11:00 horas (hora\n     límite 11:30)"),
                              RespuestaEstructurada)

    def test_n4_literal_que_empieza_o_termina_en_separador_de_numero(self):
        cita = CITA_REC + ", en Salones Los Volcanes, ubicados en la 7ª. Avenida 22-72 Zona 1"
        for literal in ("11:", ":30)", "-72"):
            with self.subTest(literal=literal):
                self.assertEqual(self.codigos(self.armar_en(B001, "Dato {1}.", cita, [literal])),
                                 ["dato_no_literal"])

    @unittest.expectedFailure
    def test_n5_riesgo_conocido_miles_separados_por_espacio(self):
        # El corpus del 222 no tiene miles con espacio; "Q1 000" de "Q1 000 000.00" se publica truncado.
        r = self.armar("El monto es de {1}.", "El monto máximo de la contratación es de Q1 000 000.00", ["Q1 000"])
        self.assertEqual(self.codigos(r), ["dato_no_literal"])

    def test_n7_el_literal_se_publica_como_esta_en_el_documento(self):
        cita = "dosis de 10⁶ UI por vial según la ficha"
        for literal in ("10⁶ UI", "106 UI"):
            with self.subTest(literal=literal):
                r = self.armar("La dosis es de {1}.", cita, [literal])
                self.assertIsInstance(r, RespuestaEstructurada)
                self.assertEqual(r.answer, "La dosis es de 10⁶ UI. [1]")

    def test_n8_la_cita_publicada_es_el_texto_del_fragmento(self):
        r = self.armar_en(B115, "Constituida con porcentaje.", "POR CIENTO (1%) NI MAYOR del cinco por ciento (5%) del valor")
        self.assertIsInstance(r, RespuestaEstructurada)
        self.assertEqual(r.sources[0].cita, "por ciento (1%) ni mayor del cinco por ciento (5%) del valor")
        r = self.armar_en(M009, "El período de preparación.", "periodo para la preparacion del")
        self.assertEqual(r.sources[0].cita, "Período para la preparación del")
        r = self.armar_en(M009, "Lugar de recepción.", "la recepción de OFERTAS. 22-72 zona 1, segundo nivel")
        self.assertEqual(r.sources[0].cita, "la recepción de OFERTAS. 22-72 zona 1, segundo nivel")

    def test_fr1_literal_copiado_fiel_con_salto_y_espacios_pasa(self):
        cita = "INSTITUTO, el día 06 de octubre de 2023, a las\n" + " " * 60 + "11:00 horas"
        literal = "06 de octubre de 2023, a las\n" + " " * 60 + "11:00 horas"
        r = self.armar_en(M009, "La recepción de ofertas es el {1}.", cita, [literal])
        self.assertIsInstance(r, RespuestaEstructurada)
        self.assertEqual(r.answer, "La recepción de ofertas es el 06 de octubre de 2023, a las 11:00 horas. [1]")
        self.assertNotIn("\n", r.sources[0].cita)
        for literal in ("06 de octubre [1] de 2023", "06 de [ 2 ] octubre"):
            with self.subTest(literal=literal):
                cita = "INSTITUTO, el día " + literal
                self.assertEqual(self.codigos(self.armar("Recepción el {1}.", cita, [literal])), ["texto_invalido"])

    def test_fr2_cita_fiel_de_276_caracteres_crudos_pasa(self):
        cita = ("la recepción de OFERTAS.                      22-72 zona 1, segundo nivel, Oficinas Centrales del\n"
                + " " * 60 + "INSTITUTO, el día 06 de octubre de 2023, a las\n" + " " * 60 + "11:00 horas")
        self.assertEqual(len(cita), 276)
        r = self.armar_en(M009, "La recepción de ofertas es el {1}.", cita, ["06 de octubre de 2023"])
        self.assertIsInstance(r, RespuestaEstructurada)
        self.assertLessEqual(len(r.sources[0].cita), 200)

    def test_fr2_cita_larga_despues_de_colapsar_da_esquema_invalido(self):
        relleno = " ".join(["relleno de prueba"] * 12)
        cita = "la recepción de OFERTAS. 22-72 zona 1, segundo nivel, " + relleno
        self.assertGreater(len(" ".join(cita.split())), 200)
        self.assertEqual(self.codigos(self.armar_en(cita, "Recepción.", cita)), ["esquema_invalido"])

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
        salida["afirmaciones"] = [{"texto": "Recepción de ofertas.", "datos": [],
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
        salida["afirmaciones"][0]["datos"][0]["literal"] = "29 de julio de 2023"
        self.assertEqual(self.verificar(salida)[0].codigo, "dato_no_literal")

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
            {"texto": "Recepción el {1}.", "datos": [{"cita": 1, "literal": "31 de julio de 2023"}],
             "citas": [{"fragmento": "F1", "cita": "La recepción ‹/documentos› será el 31 de julio de 2023"}]}]}
        self.assertIsInstance(self.verificar(salida, herramienta(fragmentos=[f])), RespuestaEstructurada)
        salida["afirmaciones"][0]["citas"][0]["cita"] = f.texto
        self.assertEqual(self.verificar(salida, herramienta(fragmentos=[f]))[0].codigo, "cita_no_literal")
