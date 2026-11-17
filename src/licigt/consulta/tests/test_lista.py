"""F5: propuesta determinista de la lista de verificación, sin red ni base de datos."""

import os
import unittest
from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

from pydantic import ValidationError

from licigt.consulta.config import obtener_configuracion_llm
from licigt.consulta.esquemas import Fuente, RespuestaEstructurada, TEXTO_ABSTENCION
from licigt.consulta.herramientas import ConflictoEvento, ResultadoHerramienta
from licigt.consulta.lectura import FragmentoRecuperado, fuente_desde_fragmento
from licigt.consulta.lista import (
    AVISO_LISTA, FIN_ORACION, ItemPropuesto, MOTIVO_FECHAS_DISTINTAS, MOTIVO_REVISION_MODIFICACION,
    _es_basura, caracter_de_seccion, proponer_items, proponer_lista, tramo_literal,
)
from licigt.consulta.lista_escritura import _fuente_vigente
from licigt.consulta.tests.test_generacion import DATOS_222, DATOS_TABLA
from licigt.consulta.requisitos import CONSULTAS_POR_CATEGORIA, CONSULTA_CRONOGRAMA, FechaCandidata, encontrar_fechas


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


def resultado(fragmentos, *, fechas=(), categorias=None, warnings=(), revisar=False, conflicto=False, conflictos=()):
    return ResultadoHerramienta(
        herramienta="extraer_requisitos", evento_id="222", fragmentos=[fragmento(f) for f in fragmentos],
        fechas=list(fechas), categorias=categorias or {}, abstener=False, needs_human_review=revisar,
        coverage_status="sin_faltantes_detectados", warnings=list(warnings), error=None,
        posible_conflicto=conflicto, conflictos=list(conflictos))


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

    def test_c17_el_conflicto_solo_no_marca_a_todos_los_requisitos(self):
        categorias = {"c-fund": "legal", "c-pie": "legal"}
        items = proponer_items(resultado([FUNDAMENTAL, PIE], categorias=categorias, conflicto=True), "222")
        self.assertFalse(any(i.requiere_revision for i in items))

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


class FilasDeTablaTests(unittest.TestCase):
    """C15: un ítem por fila con numeral de un fragmento de tabla; la cita es `título | texto` de la fila."""

    def items(self, texto=None, categoria="administrativa"):
        datos = {**DATOS_TABLA, **({"texto": texto} if texto is not None else {})}
        return proponer_items(resultado([datos], categorias={datos["chunk_id"]: categoria}), "222"), datos

    def test_c15_un_item_por_fila_2_2_1_a_2_2_7_sin_el_encabezado(self):
        items, datos = self.items()
        self.assertEqual(len(items), 7)
        self.assertEqual([i.descripcion.split(" | ")[0] for i in items],
                         ["Período para adquirir los DOCUMENTOS DE LICITACIÓN",
                          "Fecha y hora para inducción a interesados en ofertar el OBJETO de los DOCUMENTOS DE LICITACIÓN.",
                          "Período para solicitud de aclaraciones sobre los DOCUMENTOS DE LICITACIÓN.",
                          "Período para respuestas de aclaraciones sobre los DOCUMENTOS DE LICITACIÓN.",
                          "Período para la preparación del FORMULARIO ELECTRÓNICO.",
                          "Lugar, dirección, fecha y hora para la recepción de OFERTAS.",
                          "Apertura de PLICAS."])
        self.assertTrue(all(i.tipo == "requisito" and i.categoria == "administrativa" for i in items))
        self.assertFalse(any("DESCRIPCIÓN" in i.descripcion for i in items))
        for i in items:
            self.assertEqual(i.descripcion, i.fuentes[0].cita)
            self.assertLessEqual(len(i.descripcion), 500)
            self.assertIn(" | ", i.descripcion)
            self.assertNotIn(" ".join(i.descripcion.split()) + "x", datos["texto"])
            self.assertTrue(_fuente_vigente(i, fragmento(datos)))
        self.assertTrue(items[0].descripcion.endswith("hasta el día 31 de julio de 2023."))
        self.assertTrue(items[-1].descripcion.startswith("Apertura de PLICAS. | Después de concluido"))

    def test_c15_fila_larga_se_recorta_en_fin_de_oracion_y_revalida(self):
        texto = ("| 2.2.2 | Fecha y hora para inducción | " + " ".join(["El oferente presenta el documento firmado."] * 20) + " |")
        items, datos = self.items(texto)
        self.assertLessEqual(len(items[0].descripcion), 500)
        self.assertTrue(items[0].descripcion.endswith("firmado."), items[0].descripcion)
        self.assertTrue(_fuente_vigente(items[0], fragmento(datos)))

    def test_c15_tabla_sin_numerales_no_da_items_y_sin_categoria_tampoco(self):
        self.assertEqual(self.items("| DOCUMENTO | PARÁMETROS QUE DEBERÁ INGRESAR |\n| FORMULARIO | texto largo de ejemplo |")[0], [])
        self.assertEqual(proponer_items(resultado([DATOS_TABLA]), "222"), [])

    def test_c15_numerales_con_letra_y_encabezado_intercalado(self):
        texto = ("| DOCUMENTO | PARÁMETROS QUE DEBERÁ INGRESAR EN EL FORMULARIO |\n"
                 "| a) | FORMULARIO ELECTRÓNICO | 1. Generado electrónicamente a través del sistema |\n"
                 "| f.5) | Autorización | Otorgada al representante legal de la entidad oferente |")
        items, _ = self.items(texto)
        self.assertEqual([i.descripcion[:15] for i in items], ["FORMULARIO ELEC", "Autorización | "])

    def test_c15_el_texto_sin_tabla_sigue_igual(self):
        items = proponer_items(resultado([FUNDAMENTAL], categorias={"c-fund": "legal"}), "222")
        self.assertEqual([i.descripcion for i in items], [CITA_FUND])


class FilaCompletaTests(unittest.TestCase):
    """C16 H3: la cita de una fila es `título | texto` completo hasta 500 caracteres, sin cortar antes de un dato."""

    def items(self, texto=None):
        datos = {**DATOS_TABLA, **({"texto": texto} if texto is not None else {})}
        return proponer_items(resultado([datos], categorias={datos["chunk_id"]: "administrativa"}), "222"), datos

    def test_c16_la_fila_2_2_6_trae_la_fecha_de_recepcion(self):
        items, datos = self.items()
        recepcion = next(i for i in items if i.descripcion.startswith("Lugar, dirección, fecha y hora"))
        self.assertIn("31 de julio de 2023", recepcion.descripcion)
        self.assertIn("7ª. Avenida 22-72", recepcion.descripcion)
        self.assertLessEqual(len(recepcion.descripcion), 500)
        self.assertTrue(_fuente_vigente(recepcion, fragmento(datos)))

    def test_c16_la_fila_corta_va_completa_sin_recorte(self):
        items, datos = self.items()
        induccion = next(i for i in items if i.descripcion.startswith("Fecha y hora para inducción"))
        self.assertTrue(induccion.descripcion.endswith("la invitación correspondiente."), induccion.descripcion)

    def test_c16_el_ordinal_y_la_abreviatura_no_son_fin_de_oracion(self):
        for texto in ("ubicados en la 7ª. Avenida", "en el 1º. Nivel", "Oferta No. 5 del evento", "el Art. 24 de la LEY"):
            with self.subTest(texto=texto):
                self.assertIsNone(FIN_ORACION.search(texto))
        self.assertIsNotNone(FIN_ORACION.search("fue firmada. Otra oración"))

    def test_c16_el_recorte_no_cae_justo_antes_de_un_numero_ni_dentro_de_una_fecha(self):
        relleno = " ".join(["documento"] * 29)  # 29 * 10 - 1 = 289 caracteres
        for cola in ("31 de julio de 2023 y más texto " * 10, "7ª. Avenida 22-72 zona 1 y más texto " * 10,
                     "tres (3) días hábiles y más texto " * 10):
            with self.subTest(cola=cola[:20]):
                tramo = tramo_literal(relleno + " " + cola)
                self.assertTrue(tramo.endswith("documento") or tramo.endswith(("2023", "ª.", "(3) días", "hábiles", "texto")), tramo)
                self.assertFalse(tramo.endswith((" 31", " de", " julio", " 7ª.", " tres", " (3)")), tramo)

    def test_c16_fila_de_mas_de_500_se_recorta_en_fin_de_oracion_antes_de_500(self):
        texto = "| 1.1 | Título | " + " ".join(["El oferente presenta el documento firmado en el lugar 7ª. Avenida."] * 12) + " |"
        items, datos = self.items(texto)
        self.assertLessEqual(len(items[0].descripcion), 500)
        self.assertGreater(len(items[0].descripcion), 300)
        self.assertTrue(items[0].descripcion.endswith("Avenida."), items[0].descripcion)
        self.assertTrue(_fuente_vigente(items[0], fragmento(datos)))


class FechasDeTablaTests(unittest.TestCase):
    """C16 H4: cada fecha candidata de una tabla da su propio ítem, con la cita contigua de su fila."""

    def fechas_de(self, datos, estado="no_verificada"):
        return [fecha(datos, literal, f) for literal, f, _ in encontrar_fechas(datos["texto"])]

    def test_c16_una_fecha_por_candidata_igual_al_numero_de_encontrar_fechas(self):
        fechas = self.fechas_de(DATOS_TABLA)
        self.assertEqual(len(fechas), 3)
        items = [i for i in proponer_items(resultado([DATOS_TABLA], fechas=fechas), "222") if i.tipo == "fecha"]
        self.assertEqual(len(items), 3)
        self.assertEqual(len({i.fuentes[0].cita for i in items}), 3)

    def test_c16_la_cita_es_el_tramo_de_su_fila_desde_el_titulo_hasta_la_fecha(self):
        fechas = self.fechas_de(DATOS_TABLA)
        items = [i for i in proponer_items(resultado([DATOS_TABLA], fechas=fechas), "222") if i.tipo == "fecha"]
        citas = [i.fuentes[0].cita for i in items]
        self.assertTrue(citas[0].startswith("Período para adquirir los DOCUMENTOS DE LICITACIÓN | A partir de su"))
        self.assertTrue(citas[0].endswith("hasta el día 31 de julio de 2023"))
        self.assertTrue(citas[1].startswith("Fecha y hora para inducción") and citas[1].endswith("19 de julio de 2023"))
        self.assertTrue(citas[2].startswith("Lugar, dirección, fecha y hora para la recepción de OFERTAS.")
                        and citas[2].endswith("el día 31 de julio de 2023"))
        for i, cita in zip(items, citas):
            self.assertEqual(i.descripcion, f"Fecha sin verificar: {cita}")
            self.assertLessEqual(len(cita), 500)
            self.assertNotIn("2.2.", cita)
            self.assertTrue(_fuente_vigente(i, fragmento(DATOS_TABLA)), cita)

    def test_c16_el_texto_sin_tabla_sigue_con_el_literal(self):
        fechas = [fecha(FECHA_BASES, "31 de julio de 2023", date(2023, 7, 31))]
        items = proponer_items(resultado([FECHA_BASES], fechas=fechas), "222")
        self.assertEqual(items[0].fuentes[0].cita, "31 de julio de 2023")


class BasuraTests(unittest.TestCase):
    """C16: no se propone un encabezado, un resto de frase ni un tramo de menos de 4 palabras de contenido."""

    def propuestos(self, *textos):
        fragmentos = [frag(f"c-{n}", t, "Sin sección") for n, t in enumerate(textos)]
        res = resultado(fragmentos, categorias={f["chunk_id"]: "tecnica" for f in fragmentos})
        return [i.descripcion for i in proponer_items(res, "222")]

    def test_c16_encabezados_restos_y_tramos_cortos_no_se_proponen(self):
        basura = ["4. ESPECIFICACIONES TÉCNICAS", "CANTIDAD TOTAL", "3. ESPECIFICACIONES GENERALES", "correspondiente.",
                  "siguientes:", "Constancia vigente del RTU", "ANEXO 6.2 de los presentes"]
        valido = "El oferente debe presentar la constancia de inscripción en el RTU actualizada."
        self.assertEqual(self.propuestos(*basura, valido), [valido])

    def test_c16_una_fila_de_tabla_basura_tampoco(self):
        texto = "| 1 | CANTIDAD TOTAL | 5 |\n| 2 | Muestra | El oferente debe presentar una muestra vigente del producto ofertado |"
        datos = {**DATOS_TABLA, "texto": texto}
        items = proponer_items(resultado([datos], categorias={datos["chunk_id"]: "legal"}), "222")
        self.assertEqual([i.descripcion[:7] for i in items], ["Muestra"])


class RevisionPorModificacionTests(unittest.TestCase):
    """C16 H6: pide revisión el ítem cuya sección comparte el numeral principal con una modificación o aclaración."""

    MOD = frag("c-mod", "El día 06 de octubre de 2023, a las 11:00 horas, en el mismo lugar indicado.",
               "2.2.6 Recepción", doc_id="222-mod", tipo="modificacion", pagina=1)

    def items(self, *fragmentos, revisar=False, conflicto=False):
        categorias = {f["chunk_id"]: "legal" for f in fragmentos}
        return {i.fuentes[0].chunk_id: i for i in proponer_items(
            resultado(list(fragmentos), categorias=categorias, revisar=revisar, conflicto=conflicto), "222")}

    def test_c16_solo_las_secciones_con_el_mismo_numeral_principal_piden_revision(self):
        tabla = {**DATOS_TABLA, "chunk_id": "c-tabla"}                     # 2.2 CRONOGRAMA
        literal = frag("c-lit", "d.3) Que el oferente no está comprendido en ninguna prohibición legal.", "2.7 Listado")
        items = self.items(tabla, FUNDAMENTAL, literal, self.MOD)
        self.assertTrue(items["c-tabla"].requiere_revision)
        self.assertEqual(items["c-tabla"].motivo_revision, MOTIVO_REVISION_MODIFICACION)
        self.assertFalse(items["c-fund"].requiere_revision)
        self.assertFalse(items["c-lit"].requiere_revision)

    def test_c16_los_literales_de_2_7_piden_revision_si_la_modificacion_es_de_2_7(self):
        mod = frag("c-mod", "Se modifica la literal e) del subnumeral 2.7 de las bases.", "2.7 Listado de documentos",
                   doc_id="222-mod", tipo="aclaracion", pagina=1)
        literal = frag("c-lit", "d.3) Que el oferente no está comprendido en ninguna prohibición legal.", "2.7.1 Declaración")
        items = self.items(literal, FUNDAMENTAL, mod)
        self.assertTrue(items["c-lit"].requiere_revision)
        self.assertFalse(items["c-fund"].requiere_revision)

    def test_c16_sin_modificacion_en_la_evidencia_nadie_pide_revision_aunque_el_resultado_si(self):
        items = self.items(FUNDAMENTAL, PIE, revisar=True)
        self.assertFalse(any(i.requiere_revision for i in items.values()))

    def test_c16_una_seccion_sin_numeral_no_comparte_numeral(self):
        mod = frag("c-mod", "Se modifica la fecha de recepción de las ofertas del evento.", "Sin sección",
                   doc_id="222-mod", tipo="modificacion", pagina=1)
        items = self.items(PIE, FUNDAMENTAL, mod)
        self.assertFalse(items["c-pie"].requiere_revision or items["c-fund"].requiere_revision)


TEXTO_28 = ("2.8 REQUISITOS FUNDAMENTALES\n"
            "      Se consideran Requisitos Fundamentales los siguientes:\n"
            "        a) La presentación del FORMULARIO ELECTRÓNICO en forma física dentro de la\n"
            "           PLICA, como se describe en la literal a) del subnumeral 2.7 de los presentes\n"
            "           DOCUMENTOS DE LICITACIÓN, su no inclusión dará lugar a que la JUNTA,\n"
            "           rechace la OFERTA sin responsabilidad alguna de su parte. (Artículos 24 Bis y 30\n"
            "           de la LEY).\n"
            "                                                                                   15")
TEXTO_ESPECIFICACIONES = ("ESPECIFICACIONES   TÉCNICAS,      DISPOSICIONES      ESPECIALES                    y\n"
                          "         ESPECIFICACIONES GENERALES. (Artículo 16 del REGLAMENTO).\n\n"
                          "Los OFERENTES deben presentar los documentos requeridos en original y copia, en\n"
                          "         PLICAS separadas, rotuladas con la siguiente información del OFERENTE.")


class RevisionAcotadaTests(unittest.TestCase):
    """C17: solo piden revisión los ítems que una modificación o aclaración puede afectar."""

    LITERAL = frag("c-lit", "d.3) Que el oferente no está comprendido en ninguna prohibición legal.", "2.7 Listado")
    AFECTADO = frag("c-afec", "Se solicita presentar fotocopia simple de la patente de comercio.", "2.9 Requisitos no fundamentales")
    MOD = frag("c-mod", "La recepción se traslada a otra fecha indicada en el cronograma vigente.", "Sin sección",
               doc_id="222-mod", tipo="modificacion", pagina=1)

    def items(self, conflictos, *fragmentos):
        categorias = {f["chunk_id"]: "legal" for f in fragmentos}
        return {i.fuentes[0].chunk_id: i for i in proponer_items(
            resultado(list(fragmentos), categorias=categorias, conflicto=True, conflictos=conflictos), "222")}

    def test_c17_alertas_como_las_del_222_solo_marcan_lo_afectado(self):
        conflictos = [ConflictoEvento(doc_id="222-mod", numerales=["2.2", "2.7"], chunk_ids_afectados=["c-afec"])]
        items = self.items(conflictos, FUNDAMENTAL, self.LITERAL, self.AFECTADO, self.MOD)
        self.assertFalse(items["c-fund"].requiere_revision)          # 2.8 no está tocada
        self.assertTrue(items["c-lit"].requiere_revision)            # numeral 2.7 modificado
        self.assertTrue(items["c-afec"].requiere_revision)           # fragmento afectado
        self.assertTrue(items["c-mod"].requiere_revision)            # documento de la modificación
        for id_ in ("c-lit", "c-afec", "c-mod"):
            self.assertEqual(items[id_].motivo_revision, MOTIVO_REVISION_MODIFICACION)

    def test_c17_alerta_sin_numerales_ni_afectados_marca_solo_el_documento_de_la_alerta(self):
        items = self.items([ConflictoEvento(doc_id="222-mod")], FUNDAMENTAL, self.LITERAL, self.MOD)
        self.assertEqual({k for k, i in items.items() if i.requiere_revision}, {"c-mod"})

    def test_c17_el_motivo_es_uno_solo_y_no_repite_la_banda(self):
        self.assertEqual(MOTIVO_REVISION_MODIFICACION, "Una modificación o aclaración del evento toca esta sección; "
                         "el sistema no decide cuál está vigente")
        self.assertNotIn("requiere revisión humana", MOTIVO_REVISION_MODIFICACION)

    def test_c17_a1_las_fechas_de_una_seccion_modificada_piden_revision(self):
        mod = frag("c-modf", "El día 06 de octubre de 2023, a las 11:00 horas, en el mismo lugar.", "2.2.6 Recepción",
                   doc_id="222-mod", tipo="modificacion", pagina=1)
        otra = frag("c-f5", "La apertura de plicas será el 02 de noviembre de 2023, a las 09:00 horas.", "2.5 Apertura")
        fechas = [fecha(FECHA_BASES, "31 de julio de 2023", date(2023, 7, 31), "recepcion_ofertas", "verificada"),
                  fecha(otra, "02 de noviembre de 2023", date(2023, 11, 2), "apertura_plicas", "verificada"),
                  fecha(FECHA_BASES, "31 de julio de 2023", date(2023, 7, 31))]
        items = proponer_items(resultado([FECHA_BASES, otra, mod], fechas=fechas), "222")
        por_cita = {(i.fuentes[0].chunk_id, i.descripcion.split(": ")[0]): i for i in items}
        self.assertEqual(por_cita["c-f1", "Recepción de ofertas"].motivo_revision, MOTIVO_REVISION_MODIFICACION)
        self.assertFalse(por_cita["c-f5", "Apertura de plicas"].requiere_revision)
        # Con otro motivo propio, ese motivo se conserva.
        sin_verificar = [i for i in items if i.descripcion.startswith("Fecha sin verificar")][0]
        self.assertEqual(sin_verificar.motivo_revision, "Fecha sin verificar")

    def test_c17_a1_la_fecha_del_documento_de_la_alerta_pide_revision(self):
        mod = frag("c-modf", "El día 06 de octubre de 2023, a las 11:00 horas, en el mismo lugar.", "Sin sección",
                   doc_id="222-mod", tipo="modificacion", pagina=1)
        fechas = [fecha(mod, "06 de octubre de 2023", date(2023, 10, 6), "recepcion_ofertas", "verificada")]
        items = proponer_items(resultado([mod], fechas=fechas, conflictos=[ConflictoEvento(doc_id="222-mod")]), "222")
        self.assertEqual(items[0].motivo_revision, MOTIVO_REVISION_MODIFICACION)

    def test_c17_a2_el_numeral_que_el_texto_de_la_modificacion_nombra_tambien_cuenta(self):
        mod = frag("c-mod2", "Punto 2: Se modifica la literal e) del subnumeral 2.7 LISTADO DE DOCUMENTOS de las bases.",
                   "2.2 CRONOGRAMA DE ACTIVIDADES", doc_id="222-mod", tipo="modificacion", pagina=1)
        categorias = {f["chunk_id"]: "legal" for f in (self.LITERAL, FUNDAMENTAL, mod)}
        items = {i.fuentes[0].chunk_id: i for i in proponer_items(
            resultado([self.LITERAL, FUNDAMENTAL, mod], categorias=categorias), "222")}
        self.assertTrue(items["c-lit"].requiere_revision)
        self.assertFalse(items["c-fund"].requiere_revision)

    def test_c17_a6_una_seccion_mal_detectada_de_la_modificacion_no_marca_las_secciones_2(self):
        mod = frag("c-mod3", "2 vial, Código IGSS 10527, requerido por distintas Unidades Médicas del Instituto.",
                   "2 vial, Código IGSS 10527, requerido por distintas Unidades Médicas", doc_id="222-mod",
                   tipo="modificacion", pagina=1)
        base = frag("c-b2", "2. Si no concurre a suscribir el CONTRATO respectivo dentro del plazo legal correspondiente.",
                    "2. Si no concurre a suscribir el CONTRATO respectivo dentro del plazo legal")
        categorias = {f["chunk_id"]: "legal" for f in (base, mod)}
        items = {i.fuentes[0].chunk_id: i for i in proponer_items(resultado([base, mod], categorias=categorias), "222")}
        self.assertFalse(items["c-b2"].requiere_revision)

    def test_c17_la_respuesta_de_la_lista_pide_revision_si_la_evidencia_trae_una_modificacion(self):
        recuperador = RecuperadorPorConsulta({CONSULTAS_POR_CATEGORIA["legal"]: [FUNDAMENTAL, self.MOD],
                                              CONSULTA_CRONOGRAMA: []})
        ctx = SimpleNamespace(tenant_id="empresa-a", usuario="persona-a", rol="analista")
        p = proponer_lista(ctx, "222", "legal", recuperador=recuperador)
        self.assertTrue(p.respuesta.needs_human_review)
        sin = RecuperadorPorConsulta({CONSULTAS_POR_CATEGORIA["legal"]: [FUNDAMENTAL], CONSULTA_CRONOGRAMA: []})
        self.assertFalse(proponer_lista(ctx, "222", "legal", recuperador=sin).respuesta.needs_human_review)


class PresentacionDeListaTests(unittest.TestCase):
    """C17: un tramo que solo presenta una lista, o un encabezado con su referencia, no es un requisito."""

    def propuestos(self, *textos, seccion="Sin sección"):
        fragmentos = [frag(f"c-{n}", t, seccion) for n, t in enumerate(textos)]
        res = resultado(fragmentos, categorias={f["chunk_id"]: "legal" for f in fragmentos})
        return [i.descripcion for i in proponer_items(res, "222")]

    def test_c17_la_presentacion_de_una_lista_es_basura(self):
        self.assertTrue(_es_basura("2.8 REQUISITOS FUNDAMENTALES Se consideran Requisitos Fundamentales los siguientes:"))
        self.assertTrue(_es_basura("Fotocopia legible legalizada de los documentos: siguientes:"))

    def test_c17_con_15_palabras_de_contenido_o_mas_no_es_presentacion(self):
        largo = ("El oferente deberá presentar los siguientes documentos originales firmados, sellados y legalizados "
                 "por notario ante la JUNTA durante el acto público de recepción de OFERTAS programado para esta fecha:")
        self.assertFalse(_es_basura(largo))

    def test_c17_encabezado_en_mayusculas_con_una_referencia_es_basura(self):
        self.assertTrue(_es_basura("ESPECIFICACIONES GENERALES. (Artículo 16 del REGLAMENTO)."))
        self.assertFalse(_es_basura("Las especificaciones generales se rigen por el Artículo 16 del REGLAMENTO vigente."))

    def test_c17_el_fragmento_real_del_2_8_da_su_primer_requisito(self):
        items = self.propuestos(TEXTO_28, seccion="2.8 REQUISITOS FUNDAMENTALES")
        self.assertEqual(len(items), 1)
        self.assertTrue(items[0].startswith("a) La presentación del FORMULARIO ELECTRÓNICO en forma física"))
        self.assertLessEqual(len(items[0]), 300)
        self.assertIn(items[0], " ".join(TEXTO_28.split()))

    def test_c17_el_encabezado_con_columnas_cede_al_siguiente_tramo_legible(self):
        items = self.propuestos(TEXTO_ESPECIFICACIONES)
        self.assertEqual(len(items), 1)
        self.assertTrue(items[0].startswith("Los OFERENTES deben presentar los documentos requeridos"))

    def test_c17_el_tramo_de_relevo_no_se_queda_a_medias_antes_de_un_dato(self):
        # Una tabla sin separadores de fila: tras el encabezado, "(12 MESES) Unidad de Consulta Externa de" corta antes de un número.
        texto = "ESPECIFICACIONES GENERALES. (Artículo 16 del REGLAMENTO).\n\n(12 MESES) Unidad de Consulta Externa de"
        self.assertEqual(self.propuestos(texto), [])
        con_fin = texto + "\n\nEl oferente debe presentar la constancia de inscripción en el RTU actualizada."
        self.assertEqual(self.propuestos(con_fin), ["El oferente debe presentar la constancia de inscripción en el RTU actualizada."])

    def test_c17_si_todo_el_fragmento_es_basura_no_hay_item(self):
        self.assertEqual(self.propuestos("4. ESPECIFICACIONES TÉCNICAS\n\nCANTIDAD TOTAL"), [])

    def test_c17_a7_un_literal_con_palabras_en_minuscula_no_es_basura(self):
        self.assertFalse(_es_basura("a) Extendida a favor del INSTITUTO."))
        self.assertFalse(_es_basura("1. Fecha de emisión."))
        self.assertFalse(_es_basura("2.27.4 Fecha de vencimiento."))
        self.assertTrue(_es_basura("a) ABC DEF"))
        self.assertTrue(_es_basura("4. ESPECIFICACIONES TÉCNICAS"))
        self.assertTrue(_es_basura("4."))
        self.assertTrue(_es_basura("ANEXO 6.2 de los presentes"))
        # El numeral no salva a una presentación de lista.
        self.assertTrue(_es_basura("2.8 Se consideran Requisitos Fundamentales los siguientes:"))

    def test_c17_a7_el_fragmento_222_00107_da_su_literal(self):
        texto = "a) Extendida a favor del INSTITUTO.\n\nb) Debe garantizar a:\n   ▪ Si es persona individual."
        self.assertEqual(self.propuestos(texto, seccion="2.23.1 SEGURO DE CAUCIÓN"), ["a) Extendida a favor del INSTITUTO."])


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
