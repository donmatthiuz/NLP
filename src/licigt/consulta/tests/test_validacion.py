"""Validación determinista: esquema, pertenencia, citas, datos literales y fuentes."""

import json
import unicodedata
import unittest
from unittest.mock import patch

from licigt.consulta.esquemas import RespuestaEstructurada, TEXTO_ABSTENCION
from licigt.consulta.generacion import Afirmacion, construir_prompt
from licigt.consulta.herramientas import ResultadoHerramienta
from licigt.consulta.lectura import DocumentoComparado, FragmentoRecuperado
from licigt.consulta.tests.test_generacion import DATOS_TABLA, fragmentos_222, salida_222
from licigt.consulta.validacion import _armar, normalizar_cita, validar

# Pasajes del 222: bases 00001 (p. 1) y p. 27; M009 conserva la maquetación a dos columnas de la extracción anterior
# para probar que el validador tolera ese diseño en otros PDF.
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
        for texto, codigo in [("Recepción {2}.", "texto_invalido"),
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

    def test_c19_url_o_correo_copiado_de_la_cita_pasa_como_dato_y_en_el_texto_no(self):
        for literal in ("https://servicios.igssgt.org", "www.igssgt.org/licitaciones", "compras@igssgt.org"):
            cita = "La solvencia se obtiene en " + literal + " del IGSS"
            with self.subTest(literal=literal):
                self.assertIsInstance(self.armar("La solvencia se obtiene en {1}.", cita, [literal]), RespuestaEstructurada)
                if literal.startswith("www."):
                    continue  # sin dígitos ni "//" el texto de "www.x.org/y" hoy pasa la lista blanca; fuera de alcance de C19
                self.assertEqual(self.codigos(self.armar("La solvencia se obtiene en " + literal + ".", cita)), ["texto_invalido"])
        # Una URL que no está en la cita no pasa como dato.
        cita = "La solvencia se obtiene en el portal del IGSS"
        self.assertEqual(self.codigos(self.armar("La solvencia está en {1}.", cita, ["https://servicios.igssgt.org"])),
                         ["dato_no_literal"])

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

    def test_222_cita_continua_de_la_fila_con_dato_literal_y_revision(self):
        salida = salida_222()
        salida["afirmaciones"] = [{
            "texto": "La recepción de ofertas es el {1}.",
            "citas": [{"fragmento": "F2", "cita": "En Salones Los Volcanes, ubicados en la 7ª. Avenida 22-72 zona 1, segundo nivel, "
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
        cita = ("En Salones Los Volcanes, ubicados en la 7ª. Avenida 22-72 zona 1, segundo nivel, "
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
        # Un dato sin marcador y sin aparición en el texto no se publica: el código lo descarta (C9-A).
        self.assertIsInstance(self.armar_en(B115, "Vigencia de {1}.", CITA_VIG, ["120", "días"]), RespuestaEstructurada)
        self.assertIsInstance(self.armar("Recepción.", "La recepción de ofertas se llevará a cabo el 31 de julio de 2023",
                                         ["31 de julio de 2023"]), RespuestaEstructurada)

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
                      "Recepción de ofertas /otras.", "Recepción de ofertas [a].", "Recepción de ofertas\tahora.",
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
        relleno = " ".join(["relleno de prueba"] * 31)
        cita = "la recepción de OFERTAS. 22-72 zona 1, segundo nivel, " + relleno
        self.assertGreater(len(" ".join(cita.split())), 500)
        self.assertEqual(self.codigos(self.armar_en(cita, "Recepción.", cita)), ["esquema_invalido"])

    def test_c11_cita_literal_de_450_caracteres_pasa_y_una_de_520_no(self):
        for largo, publica in [(450, True), (520, False)]:
            cita = ("relleno de prueba " * 40)[:largo].strip()
            r = self.armar_en(cita, "Recepción.", cita)
            with self.subTest(largo=largo):
                if publica:
                    self.assertIsInstance(r, RespuestaEstructurada)
                else:
                    self.assertEqual(self.codigos(r), ["esquema_invalido"])

    # C6: cierre de F4.
    CITA_AV = CITA_REC + ", en Salones Los Volcanes, ubicados en la 7ª. Avenida 22-72 Zona 1"
    CITA_SEG = ("(120) días a partir de la fecha de recepción y apertura de PLICAS. Sin embargo, con el adjudicatario "
                "puede convenirse su prórroga. d) Constituida por un porcentaje no menor del uno por ciento (1%)")

    def test_c6_fra_y_o_entre_letras_pasa(self):
        r = self.armar("La falta de información y/o formalidades rechaza la oferta.", "Recepción durante la semana")
        self.assertIsInstance(r, RespuestaEstructurada)
        for texto in ("Falta y/ o formalidades.", "Falta y /o formalidades.", "Falta y/.", "Falta /y.", "Falta 1/2 hoy."):
            with self.subTest(texto=texto):
                self.assertNotIsInstance(self.armar(texto, "Recepción durante la semana"), RespuestaEstructurada)
        for texto, datos in (("Vigencia {1}/{2}.", ["120", "días"]), ("Vigencia {1}/.", ["120"]),
                             ("Vigencia y/{1}.", ["120"])):
            with self.subTest(texto=texto):
                self.assertEqual(self.codigos(self.armar_en(B115, texto, CITA_VIG, datos)), ["marcador_pegado"])

    def test_c6_frb_dos_puntos_tras_marcador(self):
        for texto in ("Punto {1}: se modifica la literal.", "Vigencia {1}:", "Vigencia ({1}): fin."):
            with self.subTest(texto=texto):
                self.assertIsInstance(self.armar_en(B115, texto, CITA_VIG, ["120"]), RespuestaEstructurada)
        for texto, datos in (("Vigencia {1}:{2}", ["120", "días"]), ("Vigencia {1}:30", ["120"]),
                             ("Vigencia {1}:a.", ["120"])):
            with self.subTest(texto=texto):
                self.assertEqual(self.codigos(self.armar_en(B115, texto, CITA_VIG, datos)), ["marcador_pegado"])

    def test_c6_ha1_marcadores_compuestos_deben_estar_juntos_en_la_cita(self):
        casos = [("La recepción de ofertas es el {1} de {2} de {3}.", self.CITA_AV, ["1", "julio", "2023"]),
                 ("La recepción de ofertas es el {1} de {2}.", self.CITA_AV, ["7ª.", "julio de 2023"]),
                 ("El seguro es del {1} {2} del valor.", self.CITA_SEG, ["(120)", "(1%)"]),
                 ("El seguro es del {1} – {2} del valor.", self.CITA_SEG, ["(120)", "(1%)"]),
                 ("La recepción es el {1} - {2}.", self.CITA_AV, ["31", "julio"])]
        for texto, cita, datos in casos:
            with self.subTest(texto=texto):
                self.assertEqual(self.codigos(self.armar_en(B001 + " " + B115, texto, cita, datos)),
                                 ["dato_no_literal"])

    def test_c6_ha1_conectores_y_no_conectores(self):
        fuente = B001 + "\n" + B115
        r = self.armar_en(fuente, "El seguro es de entre {1} y {2} del valor.", CITA_PCT, ["1%", "5%"])
        self.assertIsInstance(r, RespuestaEstructurada)
        r = self.armar_en(fuente, "La recepción es el {1}, a las {2}.", CITA_REC, ["31 de julio de 2023", "11:00 horas"])
        self.assertIsInstance(r, RespuestaEstructurada)
        self.assertIn("31 de julio de 2023, a las 11:00 horas", r.answer)
        r = self.armar_en(fuente, "La recepción es el {1} de {2} de {3}.", CITA_REC, ["31", "julio", "2023"])
        self.assertIsInstance(r, RespuestaEstructurada)

    def test_c6_ha1_literal_sin_cifra_ni_letra(self):
        for literal in ("%", "(", ")"):
            with self.subTest(literal=literal):
                self.assertEqual(self.codigos(self.armar_en(B115, "Dato {1}.", CITA_PCT, [literal])),
                                 ["dato_no_literal"])

    def test_c6_ha2_unidad_fuera_del_literal(self):
        cita = "El plazo contractual es de dieciocho (18) meses contados a partir"
        casos = [("El plazo es de {1} días.", cita, ["dieciocho (18)"]),
                 ("El plazo es de {1} meses.", cita, ["dieciocho (18)"]),
                 ("El seguro es del {1} por ciento del valor.", "equivale al diez por ciento (10%) del monto", ["diez"]),
                 ("El monto es de Q {1}.", "monto máximo de Q 1,000.00 por renglón", ["1,000.00"]),
                 ("El monto es de US$ {1}.", "monto máximo de US$ 1,000.00 por renglón", ["1,000.00"]),
                 ("La dosis es de {1} mg.", "dosis máxima de 150 mg por vial", ["150"]),
                 ("Se piden {1} unidades.", "cantidad de 1,096 unidades en total", ["1,096"])]
        for texto, cita, datos in casos:
            with self.subTest(texto=texto):
                self.assertEqual(self.codigos(self.armar(texto, cita, datos)), ["unidad_fuera_de_literal"])
        cita = "El plazo contractual es de dieciocho (18) meses contados a partir"
        r = self.armar("El plazo es de {1}.", cita, ["dieciocho (18) meses"])
        self.assertIsInstance(r, RespuestaEstructurada)
        r = self.armar("El plazo es de {1}, meses aparte.", cita, ["dieciocho (18)"])
        self.assertNotEqual(self.codigos(r) if isinstance(r, list) else [], ["unidad_fuera_de_literal"])

    def test_c6_ha3_letras_que_parecen_digitos(self):
        for texto in ("El seguro es del lOO por ciento.", "El plazo es de lO dias.", "Plazo de lS dias.", "Plazo lOo."):
            with self.subTest(texto=texto):
                self.assertEqual(self.codigos(self.armar(texto, "Recepción durante la semana")),
                                 ["dato_fuera_de_literal"])
        for texto in ("El lo y los os del IGSS aplican.",):
            with self.subTest(texto=texto):
                self.assertIsInstance(self.armar(texto, "Recepción durante la semana"), RespuestaEstructurada)

    def test_c7_a3_vigencia_por_la_evidencia(self):
        # Con la modificación en la evidencia, citar solo las bases escala sin importar las palabras.
        frases = ("La fecha de recepción del {1} es inválida.", "La modificación corrige la fecha del {1}.",
                  "La fecha de recepción del {1} fue modificada.", "La fecha de recepción del {1} cambió.",
                  "La fecha de recepción se mantiene en el {1}.", "La fecha definitiva de recepción es el {1}.",
                  "La fecha que aplica para la recepción es el {1}.", "La fecha de recepción sigue siendo el {1}.",
                  "La fecha oficial de recepción es el {1}.", "Hay que usar la fecha del {1}.",
                  "La fecha del {1} quedó invalidada.", "La fecha del {1} ya no cuenta.",
                  "La fecha de recepción ya no es el {1}; se pospuso.", "La nueva fecha de recepción es el {1}.")
        cita = "se llevará a cabo el 31 de julio de 2023, a las 11:00 horas"
        for texto in frases:
            with self.subTest(texto=texto):
                salida = {"abstener": False, "revision_humana": False, "afirmaciones": [
                    {"texto": texto, "datos": [{"cita": 1, "literal": "31 de julio de 2023"}],
                     "citas": [{"fragmento": "F1", "cita": cita}]}]}
                r = self.verificar(salida)
                self.assertIsInstance(r, RespuestaEstructurada)
                self.assertTrue(r.needs_human_review)
        # Sin modificaciones en la evidencia, el texto honesto con "anterior" o "no aplica" no escala.
        for texto in ("La certificación se emite con dos meses anteriores a la fecha.", "Esta excepción no aplica aquí.",
                      "La fecha de recepción se mantiene en el {1}."):
            with self.subTest(texto=texto, sin_modificacion=True):
                datos = ["31 de julio de 2023"] if "{1}" in texto else []
                self.assertFalse(self.armar_en(B001, texto, cita, datos).needs_human_review)

    def test_c6_ha7_mas_separadores_numericos(self):
        texto = "El monto máximo es de Q 1'500'000 por renglón, ubicado en la zona 1."
        self.assertEqual(self.codigos(self.armar_en(texto, "Dato documental.", "500'000 por renglón, ubicado")),
                         ["cita_no_literal"])
        self.assertIsInstance(self.armar_en(texto, "Dato documental.", "1'500'000 por renglón, ubicado"),
                              RespuestaEstructurada)
        cita = "Se aplica una tasa de 2½ por ciento sobre el monto"
        self.assertEqual(self.codigos(self.armar_en(cita, "La tasa es de {1}.", cita, ["2"])), ["dato_no_literal"])
        for sep in ("–", "‑"):
            with self.subTest(sep=sep):
                texto = f"El monto es de 1{sep}500{sep}000 por renglón, ubicado"
                self.assertEqual(self.codigos(self.armar_en(texto, "Dato documental.", f"500{sep}000 por renglón, ubicado")),
                                 ["cita_no_literal"])

    def test_c6_ha8_fragmento_en_nfd(self):
        nfc = "La recepción de ofertas será el 31 de julio de 2023, a las 11:00 horas, en el salón del Perú."
        nfd = unicodedata.normalize("NFD", nfc)
        r = self.armar_en(nfd, "La recepción es el {1}.", "La recepción de ofertas será el 31 de julio de 2023",
                          ["31 de julio de 2023"])
        self.assertIsInstance(r, RespuestaEstructurada)
        self.assertEqual(r.answer, "La recepción es el 31 de julio de 2023. [1]")
        r = self.armar_en(nfd, "La recepción tiene fecha.", "La recepción de ofertas sera")
        self.assertEqual(r.sources[0].cita, "La recepción de ofertas será")
        # Una marca que no compone con su letra queda en el tramo publicado.
        r = self.armar_en("Código de la muestra 5x\u0301 en total", "Hay un código.", "Código de la muestra 5x")
        self.assertEqual(r.sources[0].cita, "Código de la muestra 5x\u0301")

    def test_c6_ha8_signos_neutralizados_se_publican_como_en_el_documento(self):
        original = "El contenido de humedad debe ser <5% y el pH >6.5 en la muestra del lote."
        r = self.armar_en(original, "La humedad debe ser {1}.", "El contenido de humedad debe ser ‹5% y el pH", ["‹5%"])
        self.assertIsInstance(r, RespuestaEstructurada)
        self.assertEqual(r.answer, "La humedad debe ser <5%. [1]")
        self.assertEqual(r.sources[0].cita, "El contenido de humedad debe ser <5% y el pH")

    def test_c6_nl_numeros_romanos_en_el_texto(self):
        for texto in ("La recepción es el día Ⅻ.", "La recepción es el día ⅠⅠ.", "Recepción Ⅼ."):
            with self.subTest(texto=texto):
                self.assertEqual(self.codigos(self.armar(texto, "Recepción durante la semana")),
                                 ["dato_fuera_de_literal"])

    # C7: reglas que fallan cerrado.
    def test_c7_a1_a4_entre_marcadores_el_tramo_debe_estar_en_la_cita(self):
        fuente = B001 + "\n" + B115
        casos = [("La recepción es el {1} DE {2} DE {3}.", self.CITA_AV, ["1", "julio", "2023"]),
                 ("La recepción es el {1} ｄｅ {2}.", self.CITA_AV, ["1", "julio de 2023"]),
                 ("La recepción es el día {1} del mes de {2}.", self.CITA_AV, ["1", "julio de 2023"]),
                 ("El seguro es del {1} ({2}) del valor.", CITA_PCT, ["uno por ciento", "5%"]),
                 ("La recepción es {1}: {2}.", CITA_REC, ["31 de julio de 2023", "11:00 horas"]),
                 ("La recepción es el {1} De {2}, A LAS {3}.", self.CITA_AV, ["1", "julio de 2023", "11:00 horas"]),
                 ("La recepción es el {1} De {2}, A LAS {3}.", self.CITA_AV, ["31", "julio", "2023"])]
        for texto, cita, datos in casos:
            with self.subTest(texto=texto, datos=datos):
                self.assertEqual(self.codigos(self.armar_en(fuente, texto, cita, datos)), ["dato_no_literal"])

    def test_c7_a1_a4_excepciones_y_tramos_presentes_pasan(self):
        fuente = B001 + "\n" + B115 + "\nLa atención es de 8:00 a 16:00 horas y el plazo es 15 o 20 días hábiles."
        r = self.armar_en("Se citan los artículos 65, 69 y 70 del reglamento.", "Se citan los artículos {1}, {2}.",
                          "Se citan los artículos 65, 69 y 70 del reglamento", ["65", "69"])
        self.assertIsInstance(r, RespuestaEstructurada)
        for texto, cita, datos in [("La atención es de {1} a {2}.", "atención es de 8:00 a 16:00 horas", ["8:00", "16:00 horas"]),
                                   ("No menor del {1} ni mayor del {2}.", CITA_PCT, ["uno por ciento (1%)", "cinco por ciento (5%)"]),
                                   ("Es de entre {1} y {2}.", CITA_PCT, ["1%", "5%"]),
                                   ("Es {1} o {2}.", "es 15 o 20 días hábiles", ["15", "20 días hábiles"]),
                                   ("Es del {1}, a las {2}.", CITA_REC, ["31 de julio de 2023", "11:00 horas"]),
                                   ("Es el {1}, a las {2} (hora límite {3}).", CITA_REC, ["31 de julio de 2023", "11:00 horas", "11:30"])]:
            with self.subTest(texto=texto):
                self.assertIsInstance(self.armar_en(fuente, texto, cita, datos), RespuestaEstructurada)
        r = self.armar_en(fuente, "Es el {1}, a las {2}.", CITA_REC, ["31 de julio de 2023", "11:00 horas"])
        self.assertIn("31 de julio de 2023, a las 11:00 horas", r.answer)

    def test_c7_tramo_con_palabra_de_contenido_queda_libre_de_contiguidad(self):
        casos = [("Polvo para uso parenteral 150 mg, vial, Código IGSS 10527", "Es de {1}, vial, con código IGSS {2}.", ["150 mg", "10527"]),
                 ("(Artículo 2 numeral 5 del Acuerdo Gubernativo", "Artículo {1}, numeral {2}, del Acuerdo.", ["2", "5"]),
                 ("10527 Omalizumab 1,096", "El código {1} corresponde a Omalizumab, con una cantidad total de {2}.", ["10527", "1,096"])]
        for cita, texto, datos in casos:
            with self.subTest(texto=texto):
                self.assertIsInstance(self.armar_en(cita + " en total del lote", texto, cita, datos), RespuestaEstructurada)
        # La unidad pegada al marcador sigue fallando aunque el tramo sea libre.
        r = self.armar_en(self.CITA_AV, "El plazo es de {1} meses de {2}.", self.CITA_AV, ["31", "2023"])
        self.assertEqual(self.codigos(r), ["unidad_fuera_de_literal"])

    def test_c7_a2_unidades_con_nfkc_minusculas_y_ampliadas(self):
        cita = "El plazo contractual es de dieciocho (18) meses contados a partir"
        for unidad in ("semana", "semanas", "trimestre", "semestres", "quincenas", "millón", "millones", "mil",
                       "centavo", "gramos", "miligramos", "microgramos", "mcg", "tabletas", "frascos", "ampollas",
                       "litros", "cc", "DÍAS", "Meses", "ｄｉａｓ", "días"):
            with self.subTest(unidad=unidad):
                self.assertEqual(self.codigos(self.armar(f"El plazo es de {{1}} {unidad}.", cita, ["dieciocho (18)"])),
                                 ["unidad_fuera_de_literal"])
        for texto in ("El monto es de Q. {1}.", "El monto es de Q  {1}.", "El monto es de Ｑ {1}.", "El monto es de GTQ {1}.",
                      "El monto es de gtq {1}.", "El monto es de US$ {1}.", "El monto es de us$ {1}.", "El monto es de $ {1}."):
            with self.subTest(texto=texto):
                self.assertEqual(self.codigos(self.armar(texto, cita, ["(18)"])), ["unidad_fuera_de_literal"])
        self.assertIsInstance(self.armar("El plazo es de {1}.", cita, ["dieciocho (18) meses"]), RespuestaEstructurada)

    def test_c7_a6_a7_letras_que_parecen_digitos_sin_rechazar_siglas(self):
        for texto in ("El seguro es del lOO por ciento.", "El plazo es de lO dias.", "Plazo de lS dias.", "Es lOo.",
                      "Plazo de IlI dias.", "Plazo de l.S dias.", "Plazo de l,S dias.", "Plazo de l/Z dias.",
                      "Plazo de S.O dias.", "Plazo de O,I dias."):
            with self.subTest(texto=texto):
                self.assertEqual(self.codigos(self.armar(texto, "Recepción durante la semana")),
                                 ["dato_fuera_de_literal"])
        for texto in ("SI EL OFERENTE NO PRESENTA LA MUESTRA SE RECHAZA LA OFERTA.", "Se aplica la norma ISO.",
                      "Plazo OS III IGSS.", "El lo y los os aplican."):
            with self.subTest(texto=texto):
                self.assertIsInstance(self.armar(texto, "Recepción durante la semana"), RespuestaEstructurada)
        r = self.armar("Se exige la norma ISO {1}.", "se exige la norma ISO 9001 en el producto", ["9001"])
        self.assertIsInstance(r, RespuestaEstructurada)

    def test_c7_a8_cualquier_signo_en_el_borde_con_digito_al_otro_lado(self):
        for sep in ("‒", "−", "⸺", "․", "‧", "٫", "٬", "＇", "ʼ", "∙", "⋅", "~", "_", "*", "#"):
            with self.subTest(sep=sep):
                fuente = f"El descuento aplicado del 0{sep}5% en total de la oferta presentada"
                self.assertEqual(self.codigos(self.armar_en(fuente, "Dato documental.", f"{sep}5% en total de la oferta")),
                                 ["cita_no_literal"])
                # La "ʼ" es una letra no latina y el literal se rechaza antes por texto_invalido.
                if sep != "ʼ":
                    self.assertEqual(self.codigos(self.armar_en(fuente, "El descuento es {1}.", "El descuento aplicado del 0" + sep + "5% en total",
                                                               [f"{sep}5%"])), ["dato_no_literal"])
        for sep in ("‒", "⸺", "ʼ", "~", "_"):
            with self.subTest(derecha=sep):
                fuente = f"El monto es de 1{sep}500{sep}000 por renglón, ubicado"
                self.assertEqual(self.codigos(self.armar_en(fuente, "Dato documental.", f"500{sep}000 por renglón, ubicado")),
                                 ["cita_no_literal"])
        # Un cierre con ")" o "." seguido de espacio sigue siendo un borde válido.
        for cita in ("El plazo (dieciocho meses)", "El plazo es de dieciocho meses."):
            with self.subTest(cita=cita):
                self.assertIsInstance(self.armar_en(cita + " contados a partir de la firma", "Dato documental.", cita),
                                      RespuestaEstructurada)

    def test_c8_h1_espacio_con_marca_combinante_cuenta_como_signo(self):
        for sep in ("´", "˙", "¨", "¯", "¸", "˘", "˚", "˛", "˜", "˝", "‾", "￣", "΄"):
            with self.subTest(sep=sep):
                fuente = f"El monto máximo es de Q 1{sep}500,000.00 por renglón, ubicado en la zona 1 del municipio."
                self.assertEqual(self.codigos(self.armar_en(fuente, "Dato documental.", "500,000.00 por renglón, ubicado")),
                                 ["cita_no_literal"])
                r = self.armar_en(fuente, "El monto es de {1}.", f"El monto máximo es de Q 1{sep}500,000.00 por renglón",
                                  ["500,000.00"])
                self.assertEqual(self.codigos(r), ["dato_no_literal"])

    def test_c8_h2_vigencia_por_la_evidencia_con_cualquier_tipo_citado(self):
        base, mod = fragmentos_222()
        cita = "se llevará a cabo el 31 de julio de 2023, a las 11:00 horas"
        salida = {"abstener": False, "revision_humana": False, "afirmaciones": [
            {"texto": "La fecha de recepción sigue siendo el {1}.", "datos": [{"cita": 1, "literal": "31 de julio de 2023"}],
             "citas": [{"fragmento": "F1", "cita": cita}]}]}
        for tipo in ("bases", "anexo", "especificaciones", "convocatoria", "normativa"):
            with self.subTest(tipo=tipo):
                fb = base.model_copy(update={"texto": B001, "tipo_documento": tipo})
                r = self.verificar(salida, herramienta(fragmentos=[fb, mod]))
                self.assertIsInstance(r, RespuestaEstructurada)
                self.assertTrue(r.needs_human_review)

    def test_c8_h3_unidad_antes_con_parentesis_o_coma(self):
        cita = "El plazo contractual es de dieciocho (18) meses contados a partir"
        for texto in ("El monto es de Q ({1}).", "El monto es de Q. ({1}).", "El monto es de Q, {1}."):
            with self.subTest(texto=texto):
                self.assertEqual(self.codigos(self.armar(texto, cita, ["(18)"])), ["unidad_fuera_de_literal"])

    def test_c8_h4_letras_i_o_que_parecen_cifras(self):
        for palabra in ("IOO", "IO.OOO", "IO,OOO", "ll"):
            with self.subTest(palabra=palabra):
                self.assertEqual(self.codigos(self.armar(f"El seguro es del {palabra} del valor.",
                                                         "Recepción durante la semana")), ["dato_fuera_de_literal"])
        for palabra in ("SI", "ISO", "OS", "III"):
            with self.subTest(palabra=palabra):
                self.assertIsInstance(self.armar(f"Aplica la norma {palabra} del valor.", "Recepción durante la semana"),
                                      RespuestaEstructurada)

    def test_c7_a9_comparar_versiones_publica_desde_el_original_de_documentos(self):
        base, mod = fragmentos_222()
        fb = base.model_copy(update={"texto": "El contenido de humedad debe ser <5% según las bases del evento y su anexo."})
        fm = mod.model_copy(update={"texto": "El contenido de humedad debe ser <3% según la modificación número uno."})
        docs = [DocumentoComparado(doc_id=f.doc_id, tipo_documento=f.tipo_documento,
                                   identificador_version_oficial=f.identificador_version_oficial, fragmentos=[f])
                for f in (fb, fm)]
        resultado = herramienta(herramienta="comparar_versiones", fragmentos=[], documentos=docs, needs_human_review=True)
        salida = {"abstener": False, "revision_humana": True, "afirmaciones": [
            {"texto": "Las bases piden humedad {1}.", "datos": [{"cita": 1, "literal": "‹5%"}],
             "citas": [{"fragmento": "F1", "cita": "El contenido de humedad debe ser ‹5% según las bases"}]},
            {"texto": "La modificación pide humedad {1}.", "datos": [{"cita": 1, "literal": "‹3%"}],
             "citas": [{"fragmento": "F2", "cita": "El contenido de humedad debe ser ‹3% según la modificación"}]}]}
        _, evidencia, _, _ = construir_prompt("humedad", [fb, fm])
        r = validar(json.dumps(salida, ensure_ascii=False), evidencia, resultado, evento_id="222")
        self.assertIsInstance(r, RespuestaEstructurada)
        self.assertEqual(r.answer, "Las bases piden humedad <5%. [1]\nLa modificación pide humedad <3%. [2]")
        self.assertEqual(r.sources[0].cita, "El contenido de humedad debe ser <5% según las bases")

    def test_pagina_impresa_cero_no_impide_publicar_una_cita_literal(self):
        base = fragmentos_222()
        f = FragmentoRecuperado.model_validate({**base[0].model_dump(), "pagina_impresa": 0})
        r = self.verificar(resultado=herramienta(fragmentos=[f, *base[1:]]))
        self.assertIsInstance(r, RespuestaEstructurada)
        self.assertIsNone(r.sources[0].printed_page)

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

    def test_abstencion_gana_sobre_afirmaciones_y_solo_un_conflicto_pide_revision(self):
        salida = salida_222()
        salida.update(abstener=True, revision_humana=True)
        salida["afirmaciones"][0]["citas"][0]["fragmento"] = "F999"
        respuesta = self.verificar(salida)
        self.assertTrue(respuesta.abstained)
        self.assertEqual(respuesta.answer, TEXTO_ABSTENCION)
        self.assertEqual(respuesta.sources, [])
        self.assertFalse(respuesta.needs_human_review)
        grupos = [{f.doc_id for f in fragmentos_222()}]
        self.assertTrue(self.verificar(salida, conflictos=grupos).needs_human_review)

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

    def test_c17_a4_la_fuente_invalida_de_una_sola_cita_lleva_su_posicion(self):
        cuerpo = ("relleno de prueba " * 30)[:479].rstrip()
        texto = f"| 2.2.6 | Recepción de ofertas | {cuerpo} |"
        cita = " ".join(f"Recepción de ofertas {cuerpo}".split())
        self.assertLessEqual(len(cita), 500)
        self.assertGreater(len(f"Recepción de ofertas | {cuerpo}"), 500)
        otra = {"texto": "Las bases fijan la recepción.", "datos": [],
                "citas": [{"fragmento": "F1", "cita": "Recepción de ofertas"}]}
        larga = {"texto": "La fila dice otra cosa.", "datos": [], "citas": [{"fragmento": "F1", "cita": cita}]}
        f = fragmentos_222()[0].model_copy(update={"texto": texto})
        salida = {"abstener": False, "revision_humana": False, "afirmaciones": [otra, larga]}
        errores = self.verificar(salida, herramienta(fragmentos=[f]))
        self.assertEqual([(e.codigo, e.afirmacion, e.cita) for e in errores], [("esquema_invalido", 2, 1)])

    def test_deduplica_par_chunk_cita_y_mantiene_marcadores(self):
        salida = salida_222()
        # C13: una afirmación repetida tal cual es afirmacion_duplicada; la misma cita en otra afirmación se deduplica.
        salida["afirmaciones"].append({**salida["afirmaciones"][0], "texto": "Las bases confirman recepción el {1}."})
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


ENTREGA = "El CONTRATISTA entregará directamente el producto en la bodega de cada UNIDAD SOLICITANTE"
CAUCION = "Constituida por una suma equivalente al diez por ciento (10%) del monto del CONTRATO."
IGSS = ("Adquisición del medicamento Omalizumab, Polvo para uso parenteral 150 mg, vial, Código IGSS 10527, "
        "requerido por distintas Unidades Médicas del Instituto.")
# Salidas crudas del modelo real (Qwen3.5-9B) en la primera corrida con servicios, sin tocar.
CRUDO_ENTREGA = (
    '{"abstener": false, "afirmaciones": [{"texto": "El lugar de entrega es la bodega de cada UNIDAD SOLICITANTE.", '
    '"citas": [{"fragmento": "F1", "cita": "' + ENTREGA + '"}], '
    '"datos": [{"cita": 1, "literal": "bodega de cada UNIDAD SOLICITANTE"}]}], "revision_humana": false}')
CRUDO_CAUCION = (
    '{"abstener": false, "afirmaciones": [{"texto": "El monto del Seguro de Caución de Cumplimiento es equivalente '
    'al diez por ciento del monto del CONTRATO.", "citas": [{"fragmento": "F1", "cita": "' + CAUCION + '"}], '
    '"datos": [{"cita": 1, "literal": "diez por ciento (10%) del monto del CONTRATO"}]}], "revision_humana": false}')
CRUDO_IGSS = (
    '{"abstener": false, "afirmaciones": [{"texto": "El código IGSS del medicamento es {1}.", '
    '"citas": [{"fragmento": "F1", "cita": "' + IGSS + '"}], "datos": [{"cita": 1, "literal": "10527"}]}], '
    '"revision_humana": false}')


class MarcadoresDelCodigoTests(unittest.TestCase):
    """C9-A: el código pone el marcador cuando el modelo copia el dato en el texto, sin aflojar la regla."""

    def validar(self, crudo, fragmento, informe=None):
        f = fragmentos_222()[0].model_copy(update={"texto": fragmento})
        resultado = herramienta(fragmentos=[f])
        _, evidencia, _, _ = construir_prompt("pregunta", resultado.fragmentos)
        return validar(crudo, evidencia, resultado, evento_id="222", informe=informe)

    def salida(self, texto, cita, datos):
        return json.dumps({"abstener": False, "revision_humana": False, "afirmaciones": [
            {"texto": texto, "citas": [{"fragmento": "F1", "cita": cita}],
             "datos": [{"cita": 1, "literal": d} for d in datos]}]}, ensure_ascii=False)

    def test_crudo_real_lugar_de_entrega_publica(self):
        r = self.validar(CRUDO_ENTREGA, ENTREGA + " según el contrato.")
        self.assertIsInstance(r, RespuestaEstructurada)
        self.assertIn("bodega de cada UNIDAD SOLICITANTE", r.answer)

    def test_crudo_real_codigo_igss_sigue_publicando(self):
        self.assertIsInstance(self.validar(CRUDO_IGSS, IGSS), RespuestaEstructurada)

    def test_crudo_real_caucion_descarta_el_dato_que_no_esta_en_el_texto(self):
        informe = {}
        r = self.validar(CRUDO_CAUCION, CAUCION, informe)
        self.assertIsInstance(r, RespuestaEstructurada)
        self.assertEqual(informe["datos_descartados"], 1)
        self.assertNotIn("10%", r.answer)

    def test_fecha_copiada_en_el_texto_se_sustituye(self):
        crudo = self.salida("La recepción de ofertas es el 31 de julio de 2023.", CITA_REC, ["31 de julio de 2023"])
        r = self.validar(crudo, B001)
        self.assertIsInstance(r, RespuestaEstructurada)
        self.assertTrue(r.answer.startswith("La recepción de ofertas es el 31 de julio de 2023."))

    def test_sustituye_primero_el_literal_mas_largo_y_una_aparicion_por_dato(self):
        # "31 de julio" está dentro de "31 de julio de 2023": el largo gana y el corto ya no tiene aparición.
        crudo = self.salida("Es el 31 de julio de 2023.", CITA_REC, ["31 de julio", "31 de julio de 2023"])
        informe = {}
        r = self.validar(crudo, B001, informe)
        self.assertIsInstance(r, RespuestaEstructurada)
        self.assertEqual(informe["datos_descartados"], 1)
        # Dos datos iguales usan dos apariciones distintas, una por dato.
        crudo = self.salida("Del 31 de julio de 2023 al 31 de julio de 2023.", CITA_REC,
                            ["31 de julio de 2023", "31 de julio de 2023"])
        informe = {}
        self.assertIsInstance(self.validar(crudo, B001, informe), RespuestaEstructurada)
        self.assertEqual(informe.get("datos_descartados", 0), 0)

    def test_marcador_existente_se_respeta_y_se_renumera_si_sobra_un_dato(self):
        crudo = self.salida("Recepción el {2}.", CITA_REC, ["11:00 horas", "31 de julio de 2023"])
        informe = {}
        r = self.validar(crudo, B001, informe)
        self.assertIsInstance(r, RespuestaEstructurada)
        self.assertEqual(informe["datos_descartados"], 1)
        self.assertIn("31 de julio de 2023", r.answer)

    def test_afirmacion_sin_cifras_con_datos_sobrantes_publica(self):
        crudo = self.salida("La recepción se hace en la sede del Instituto.", "ubicados en la 7ª. Avenida 22-72 Zona 1",
                            ["31 de julio de 2023"])
        informe = {}
        self.assertIsInstance(self.validar(crudo, B001, informe), RespuestaEstructurada)
        self.assertEqual(informe["datos_descartados"], 1)
        crudo = self.salida("La recepción se hace en la sede del Instituto.", "ubicados en la 7ª. Avenida 22-72 Zona 1", [])
        self.assertIsInstance(self.validar(crudo, B001), RespuestaEstructurada)

    def test_fecha_escrita_a_mano_sigue_rechazada(self):
        # "6 de octubre" no es el literal "06 de octubre de 2023": no se sustituye y el dígito queda en el texto.
        crudo = self.salida("La recepción es el 6 de octubre.", "INSTITUTO, el día 06 de octubre de 2023",
                            ["06 de octubre de 2023"])
        r = self.validar(crudo, M009)
        self.assertEqual(self.codigos(r), ["dato_fuera_de_literal"])

    def test_digito_suelto_sin_literal_sigue_rechazado(self):
        crudo = self.salida("Recepción el 31 de julio de 2023 a las {1}.", CITA_REC, ["11:00 horas"])
        r = self.validar(crudo, B001)
        # C10: la fecha sale de la cita, pero "a las" entre dos marcadores no está seguido en ella (hay una coma).
        self.assertEqual(self.codigos(r), ["dato_no_literal"])

    def test_literal_dentro_de_otra_palabra_o_numero_no_se_sustituye(self):
        crudo = self.salida("El año es 12023 en el texto.", "a las 11:00 horas (hora\n     límite 11:30)", ["2023"])
        informe = {}
        r = self.validar(crudo, B001, informe)
        self.assertIsInstance(r, list)

    def test_literal_que_aparece_dentro_de_un_marcador_no_se_toca(self):
        crudo = self.salida("Recepción el {1}.", CITA_REC, ["31 de julio de 2023", "1"])
        informe = {}
        r = self.validar(crudo, B001, informe)
        self.assertIsInstance(r, RespuestaEstructurada)
        self.assertEqual(informe["datos_descartados"], 1)

    def codigos(self, errores):
        self.assertIsInstance(errores, list)
        return [e.codigo for e in errores]


class DatosDesdeLaCitaTests(unittest.TestCase):
    """C10: el código toma de la cita los tramos con dígitos que el modelo escribió sin declararlos."""

    def validar(self, crudo, fragmentos, informe=None):
        resultado = herramienta(fragmentos=fragmentos)
        _, evidencia, _, _ = construir_prompt("pregunta", resultado.fragmentos)
        return validar(crudo, evidencia, resultado, evento_id="222", informe=informe)

    def un_fragmento(self, texto):
        return [fragmentos_222()[0].model_copy(update={"texto": texto})]

    def salida(self, texto, citas, datos=()):
        return json.dumps({"abstener": False, "revision_humana": False, "afirmaciones": [
            {"texto": texto, "citas": [{"fragmento": f, "cita": c} for f, c in citas],
             "datos": [{"cita": n, "literal": d} for n, d in datos]}]}, ensure_ascii=False)

    def test_identificador_de_la_modificacion_se_toma_de_la_cita(self):
        cita = "Modificación Número 1 al documento de bases"
        informe = {}
        r = self.validar(self.salida("Existe la Modificación Número 1 del evento.", [("F1", cita)]),
                         self.un_fragmento(cita + " de la licitación"), informe)
        self.assertIsInstance(r, RespuestaEstructurada)
        self.assertIn("Modificación Número 1 del evento.", r.answer)
        self.assertEqual(informe["datos_desde_cita"], 1)

    def test_subnumeral_se_toma_de_la_cita(self):
        cita = "conforme al subnumeral 2.30 de las bases"
        informe = {}
        r = self.validar(self.salida("Aplica el subnumeral 2.30.", [("F1", cita)]),
                         self.un_fragmento(cita + " del evento"), informe)
        self.assertIsInstance(r, RespuestaEstructurada)
        self.assertIn("subnumeral 2.30.", r.answer)
        self.assertEqual(informe["datos_desde_cita"], 1)

    def test_fecha_con_dia_distinto_en_la_cita_se_sigue_rechazando(self):
        informe = {}
        r = self.validar(self.salida("La recepción es el 1 de julio de 2023.", [("F1", CITA_REC)]),
                         self.un_fragmento(B001), informe)
        self.assertEqual([e.codigo for e in r], ["dato_fuera_de_literal"])
        self.assertEqual(informe["datos_desde_cita"], 0)

    def test_tramo_que_solo_esta_en_otra_cita_mezcla_citas_y_se_rechaza(self):
        f1, f2 = fragmentos_222()
        crudo = self.salida("Recepción {1} y modificación 06 de octubre de 2023.", [
            ("F1", "La recepción de ofertas se llevará a cabo el 31 de julio de 2023"),
            ("F2", "INSTITUTO, el día 06 de octubre de 2023")], [(1, "31 de julio de 2023")])
        r = self.validar(crudo, [f1, f2])
        self.assertEqual([e.codigo for e in r], ["datos_de_varias_citas"])

    def test_tramo_en_dos_citas_usa_la_cita_de_los_datos_que_ya_tiene(self):
        f1, f2 = fragmentos_222()
        f2 = f2.model_copy(update={"texto": "el día 06 de octubre de 2023, con 31 de julio de 2023"})
        crudo = self.salida("Recepción {1}; además el 31 de julio de 2023.", [
            ("F1", "La recepción de ofertas se llevará a cabo el 31 de julio de 2023"),
            ("F2", "el día 06 de octubre de 2023, con 31 de julio de 2023")], [(2, "06 de octubre de 2023")])
        informe = {}
        self.assertIsInstance(self.validar(crudo, [f1, f2], informe), RespuestaEstructurada)
        self.assertEqual(informe["datos_desde_cita"], 1)
        crudo = self.salida("Recepción {1}; además el 31 de julio de 2023.", [
            ("F1", "La recepción de ofertas se llevará a cabo el 31 de julio de 2023"),
            ("F2", "el día 06 de octubre de 2023, con 31 de julio de 2023")], [(1, "31 de julio de 2023")])
        informe = {}
        self.assertIsInstance(self.validar(crudo, [f1, f2], informe), RespuestaEstructurada)
        self.assertEqual(informe["datos_desde_cita"], 1)

    def test_tramo_con_unidad_pegada_sigue_rechazado(self):
        # C13: la unidad que la cita trae seguida entra en el tramo; con otra unidad en el texto sigue rechazado.
        cita = "con vigencia de 120 días a partir de la fecha"
        r = self.validar(self.salida("Vigencia de 120 meses.", [("F1", cita)]), self.un_fragmento(cita))
        self.assertEqual([e.codigo for e in r], ["unidad_fuera_de_literal"])

    def test_c11_identificador_de_version_del_fragmento_citado_se_acepta(self):
        f1, f2 = fragmentos_222()
        self.assertEqual(f2.identificador_version_oficial, "Modificación Número 1")
        crudo = self.salida("En la Modificación Número 1, la recepción es el {1}.",
                            [("F2", "INSTITUTO, el día 06 de octubre de 2023")], [(1, "06 de octubre de 2023")])
        informe = {}
        r = self.validar(crudo, [f1, f2], informe)
        self.assertIsInstance(r, RespuestaEstructurada)
        self.assertIn("En la Modificación Número 1, la recepción es el 06 de octubre de 2023.", r.answer)
        self.assertEqual(informe["datos_desde_cita"], 1)

    def test_c11_cita_de_las_bases_sin_identificador_se_rechaza_como_antes(self):
        f1, f2 = fragmentos_222()
        self.assertIsNone(f1.identificador_version_oficial)
        crudo = self.salida("En la Modificación Número 1, la recepción es el {1}.",
                            [("F1", "La recepción de ofertas se llevará a cabo el 31 de julio de 2023")],
                            [(1, "31 de julio de 2023")])
        r = self.validar(crudo, [f1, f2])
        self.assertEqual([e.codigo for e in r], ["dato_fuera_de_literal"])

    def test_c11_el_identificador_solo_vale_con_limites_de_palabra(self):
        f1, f2 = fragmentos_222()
        f2 = f2.model_copy(update={"identificador_version_oficial": "Modificación Número 12"})
        crudo = self.salida("En la Modificación Número 1, la recepción es el {1}.",
                            [("F2", "INSTITUTO, el día 06 de octubre de 2023")], [(1, "06 de octubre de 2023")])
        self.assertEqual([e.codigo for e in self.validar(crudo, [f1, f2])], ["dato_fuera_de_literal"])


class OctavaPasadaTests(unittest.TestCase):
    """C13: identificador completo, relleno con otro documento, tramos largos, uniones mixtas y unidades."""

    CITA_M11 = "Hasta diez (10) días hábiles contados a partir del día siguiente de la fecha de recepción de OFERTAS."

    def validar(self, salida, fragmentos, conflictos=(), informe=None):
        resultado = herramienta(fragmentos=fragmentos)
        _, evidencia, _, _ = construir_prompt("pregunta", resultado.fragmentos)
        crudo = json.dumps({"abstener": False, "revision_humana": False, "afirmaciones": salida}, ensure_ascii=False)
        return validar(crudo, evidencia, resultado, evento_id="222", conflictos=conflictos, informe=informe)

    def af(self, texto, cita, datos=(), fragmento="F1"):
        return {"texto": texto, "citas": [{"fragmento": fragmento, "cita": cita}],
                "datos": [{"cita": 1, "literal": d} for d in datos]}

    def con_texto(self, indice, texto):
        return fragmentos_222()[indice].model_copy(update={"texto": texto})

    def codigos(self, r):
        self.assertIsInstance(r, list)
        return [e.codigo for e in r]

    def test_h1_un_uno_suelto_no_sale_del_identificador(self):
        f2 = self.con_texto(1, self.CITA_M11)
        self.assertEqual(f2.identificador_version_oficial, "Modificación Número 1")
        for texto in ("La apertura de plicas es hasta un (1) día hábil después de la recepción de ofertas.",
                      "La apertura de plicas se hace a la 1 de la tarde.", "Se requiere 1 muestra del producto.",
                      "La apertura de plicas es hasta un ({1}) día hábil después de la recepción de ofertas."):
            with self.subTest(texto=texto):
                datos = ["1"] if "{1}" in texto else []
                r = self.validar([self.af(texto, self.CITA_M11, datos, "F1")], [f2])
                self.assertIsInstance(r, list)

    def test_h1_el_identificador_completo_publica_con_o_sin_marcador(self):
        f2 = self.con_texto(1, "INSTITUTO, el día 06 de octubre de 2023")
        for texto, datos in (("En la Modificación Número 1, la recepción es el {1}.", ["06 de octubre de 2023"]),
                             ("En la Modificación Número 1, la recepción es el 06 de octubre de 2023.", [])):
            with self.subTest(texto=texto):
                informe = {}
                r = self.validar([self.af(texto, "INSTITUTO, el día 06 de octubre de 2023", datos)], [f2], informe=informe)
                self.assertIsInstance(r, RespuestaEstructurada)
                self.assertIn("En la Modificación Número 1, la recepción es el 06 de octubre de 2023.", r.answer)

    def test_h1_dato_declarado_que_es_solo_parte_del_identificador_se_rechaza(self):
        f2 = self.con_texto(1, self.CITA_M11)
        r = self.validar([self.af("La apertura es en la Modificación Número {1}.", self.CITA_M11, ["1"])], [f2])
        self.assertEqual(self.codigos(r), ["dato_no_literal"])

    def test_h2_dos_afirmaciones_con_el_mismo_texto_se_rechazan(self):
        f1, f2 = fragmentos_222()
        a = self.af("La recepción de ofertas se hace en el lugar indicado.",
                    "La recepción de ofertas se llevará a cabo el 31 de julio de 2023")
        b = self.af("La recepción  de ofertas se hace en el lugar INDICADO.", "Salones Los Volcanes, ubicados en la 7ª. Avenida",
                    [], "F2")
        for conflictos in ((), [{f1.doc_id, f2.doc_id}]):
            with self.subTest(conflictos=conflictos):
                self.assertEqual(self.codigos(self.validar([a, b], [f1, f2.model_copy(update={
                    "texto": "Salones Los Volcanes, ubicados en la 7ª. Avenida"})], conflictos)), ["afirmacion_duplicada"])

    def test_h2_con_conflicto_la_cita_del_otro_documento_debe_compartir_una_palabra(self):
        f1, f2 = fragmentos_222()
        grupo = [{f1.doc_id, f2.doc_id}]
        a = self.af("La recepción de ofertas es el {1}.", "La recepción de ofertas se llevará a cabo el 31 de julio de 2023",
                    ["31 de julio de 2023"])
        ajena = self.af("El monto del seguro de caución es el diez por ciento del contrato.",
                        "Salones Los Volcanes, ubicados en la 7ª. Avenida", [], "F2")
        self.assertEqual(self.codigos(self.validar([a, ajena], [f1, f2], grupo)), ["cita_ajena"])
        propia = self.af("Los Volcanes son el lugar de la recepción de ofertas.",
                         "Salones Los Volcanes, ubicados en la 7ª. Avenida", [], "F2")
        self.assertIsInstance(self.validar([a, propia], [f1, f2], grupo), RespuestaEstructurada)

    def test_h2_la_palabra_compartida_no_puede_ser_vacia_ni_el_nombre_del_documento(self):
        f1, f2 = fragmentos_222()
        grupo = [{f1.doc_id, f2.doc_id}]
        a = self.af("La recepción de ofertas es el {1}.", "La recepción de ofertas se llevará a cabo el 31 de julio de 2023",
                    ["31 de julio de 2023"])
        vacia = "Según las bases, hasta la fecha cuando desde ocurra"
        b = self.af("Según la modificación, desde ahora hasta cuando sea.", vacia, [], "F2")
        self.assertEqual(self.codigos(self.validar([a, b], [f1, f2.model_copy(update={"texto": vacia})], grupo)),
                         ["cita_ajena"])

    def test_h4_tramo_de_mas_de_200_caracteres_no_lanza(self):
        lista = ", ".join(str(1000 + i) for i in range(45))
        cita = "Las extensiones son " + lista
        self.assertGreater(len(lista), 200)
        r = self.validar([self.af("Las extensiones son " + lista + ".", cita)], [self.con_texto(0, cita)])
        self.assertIn(self.codigos(r)[0], {"dato_fuera_de_literal", "texto_invalido"})

    def test_h7_marcador_del_codigo_y_dato_creado_contiguos_exigen_el_compuesto_en_la_cita(self):
        f = self.con_texto(0, B001)
        r = self.validar([self.af("La recepción de ofertas es el 31 de julio, 11:30.", CITA_REC, ["31 de julio"])], [f])
        self.assertEqual(self.codigos(r), ["dato_no_literal"])
        cita = "los códigos 10527, 10528 del evento"
        r = self.validar([self.af("Los códigos son 10527, 10528.", cita, ["10527"])], [self.con_texto(0, cita + " demo")])
        self.assertIsInstance(r, RespuestaEstructurada)
        self.assertIn("10527, 10528", r.answer)

    def test_unidad_que_sigue_al_dato_y_esta_en_la_cita_entra_en_el_tramo(self):
        cita = "con vigencia de 120 días a partir de la fecha"
        for texto, esperado in (("Vigencia de 120 días.", "120 días"), ("Tableta de 150 mg.", "150 mg"),
                                ("Hasta las 10:00 horas.", "10:00 horas")):
            with self.subTest(texto=texto):
                c = {"Vigencia de 120 días.": cita, "Tableta de 150 mg.": "tableta de 150 mg, vial",
                     "Hasta las 10:00 horas.": "hasta las 10:00 horas del día"}[texto]
                r = self.validar([self.af(texto, c)], [self.con_texto(0, c + " del evento")])
                self.assertIsInstance(r, RespuestaEstructurada)
                self.assertIn(esperado, r.answer)
        r = self.validar([self.af("Vigencia de 120 meses.", cita)], [self.con_texto(0, cita)])
        self.assertEqual(self.codigos(r), ["unidad_fuera_de_literal"])
        r = self.validar([self.af("Vigencia de {1} días.", cita, ["120"])], [self.con_texto(0, cita)])
        self.assertEqual(self.codigos(r), ["unidad_fuera_de_literal"])


class TablasValidacionTests(unittest.TestCase):
    """C15: las barras de celda de una tabla no rompen la cita ni los literales."""

    def verificar(self, texto_fragmento, cita, afirmacion="Dato de la tabla.", datos=()):
        base = FragmentoRecuperado.model_validate({**DATOS_TABLA, "texto": texto_fragmento})
        res = ResultadoHerramienta(
            herramienta="buscar_documentos", evento_id="222", fragmentos=[base], abstener=False,
            needs_human_review=False, coverage_status="sin_faltantes_detectados", warnings=[], error=None)
        _, evidencia, _, _ = construir_prompt("Cronograma", res.fragmentos)
        salida = {"abstener": False, "revision_humana": False, "afirmaciones": [
            {"texto": afirmacion, "citas": [{"fragmento": "F1", "cita": cita}],
             "datos": [{"cita": 1, "literal": d} for d in datos]}]}
        return validar(json.dumps(salida, ensure_ascii=False), evidencia, res, evento_id="222")

    def test_c15_normalizar_trata_la_barra_de_celda_como_espacio(self):
        self.assertEqual(normalizar_cita("| 2.2.1 | Período |  A partir |"), normalizar_cita("2.2.1 Período A partir"))
        self.assertEqual(normalizar_cita("código AB|12"), "codigo ab|12")
        self.assertEqual(normalizar_cita("a |b y c| d"), "a |b y c| d")

    def test_c15_cita_sin_barras_de_la_fila_real_pasa_y_publica_el_tramo_original(self):
        cita = ("2.2.1 Período para adquirir los DOCUMENTOS DE LICITACIÓN "
                "A partir de su publicación en GUATECOMPRAS, hasta el día 31 de julio de 2023.")
        r = self.verificar(DATOS_TABLA["texto"], cita)
        self.assertIsInstance(r, RespuestaEstructurada, r)
        self.assertEqual(r.sources[0].cita,
                         "2.2.1 | Período para adquirir los DOCUMENTOS DE LICITACIÓN | "
                         "A partir de su publicación en GUATECOMPRAS, hasta el día 31 de julio de 2023.")

    def test_c15_cita_con_una_celda_y_dato_literal(self):
        r = self.verificar(DATOS_TABLA["texto"], "El día 19 de julio de 2023, a las 10:00 horas",
                           afirmacion="La inducción es el {1}.", datos=["19 de julio de 2023"])
        self.assertIsInstance(r, RespuestaEstructurada, r)

    def test_c15_la_cita_con_barras_tambien_pasa(self):
        r = self.verificar(DATOS_TABLA["texto"],
                           "| 2.2.7 | Apertura de PLICAS. | Después de concluido el período de presentación")
        self.assertIsInstance(r, RespuestaEstructurada, r)

    def test_c15_la_barra_dentro_de_una_palabra_no_se_toca(self):
        texto = "El código AB|12 corresponde al producto indicado en la lista"
        self.assertIsInstance(self.verificar(texto, "El código AB|12 corresponde al producto"), RespuestaEstructurada)
        r = self.verificar(texto, "El código AB 12 corresponde al producto")
        self.assertEqual([e.codigo for e in r], ["cita_no_literal"])

    def test_c15_siguen_fallando_citas_falsas_sobre_la_tabla(self):
        for cita in ("2.2.7 Apertura de PLICAS. Antes de concluido el período de presentación",
                     "2.2.1 Período para adquirir los DOCUMENTOS DE LICITACIÓN hasta el día 30 de julio de 2023",
                     "Apertura de PLICAS. 2.2.7 Después de concluido el período de presentación"):
            with self.subTest(cita=cita):
                r = self.verificar(DATOS_TABLA["texto"], cita)
                self.assertEqual([e.codigo for e in r], ["cita_no_literal"])

    def test_c16_la_cita_que_cruza_el_fin_de_una_fila_y_el_inicio_de_la_siguiente_se_rechaza(self):
        for cita in ("hasta el día 31 de julio de 2023. 2.2.2 Fecha y hora para inducción a interesados",
                     "hasta el día 31 de julio de 2023. | 2.2.2 | Fecha y hora para inducción a interesados",
                     "| 2.2.1 | Período para adquirir los DOCUMENTOS DE LICITACIÓN | A partir de su publicación en GUATECOMPRAS,"
                     " hasta el día 31 de julio de 2023. |\n| 2.2.2 | Fecha y hora para inducción"):
            with self.subTest(cita=cita):
                r = self.verificar(DATOS_TABLA["texto"], cita)
                self.assertEqual([e.codigo for e in r], ["cita_cruza_filas"])

    def test_c16_el_encabezado_y_la_primera_fila_no_son_dos_filas_de_datos(self):
        cita = "| DESCRIPCIÓN | FECHA | | 2.2.1 | Período para adquirir los DOCUMENTOS DE LICITACIÓN"
        self.assertIsInstance(self.verificar(DATOS_TABLA["texto"], cita), RespuestaEstructurada)
        self.assertIsInstance(self.verificar(DATOS_TABLA["texto"], "DESCRIPCIÓN FECHA 2.2.1 Período para adquirir"),
                              RespuestaEstructurada)

    def test_c16_la_cita_dentro_de_una_fila_con_o_sin_barras_sigue_publicando(self):
        for cita in ("| 2.2.2 | Fecha y hora para inducción a interesados en ofertar el OBJETO de los DOCUMENTOS DE LICITACIÓN."
                     " | El día 19 de julio de 2023, a las 10:00 horas. |",
                     "2.2.2 Fecha y hora para inducción a interesados en ofertar el OBJETO de los DOCUMENTOS DE LICITACIÓN.",
                     "El día 19 de julio de 2023, a las 10:00 horas. La inducción se impartirá de forma virtual",
                     "| 2.2.7 | Apertura de PLICAS. | Después de concluido el período de presentación y recepción de OFERTAS. |"):
            with self.subTest(cita=cita):
                self.assertIsInstance(self.verificar(DATOS_TABLA["texto"], cita), RespuestaEstructurada)

    def test_c15_un_dato_inventado_en_la_fila_falla(self):
        r = self.verificar(DATOS_TABLA["texto"], "El día 19 de julio de 2023, a las 10:00 horas",
                           afirmacion="La inducción es el {1}.", datos=["20 de julio de 2023"])
        self.assertIsInstance(r, list)
