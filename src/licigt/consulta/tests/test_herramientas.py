"""Pruebas de buscar_documentos y comparar_versiones con un recuperador falso."""

import os
import subprocess
import sys
import unittest
from pathlib import Path

from licigt.consulta.esquemas import BuscarDocumentosParams, CompararVersionesParams, ExtraerRequisitosParams
from licigt.consulta.herramientas import buscar_documentos, comparar_versiones, extraer_requisitos, tema_comparacion
from licigt.consulta.requisitos import CONSULTAS_POR_CATEGORIA, CONSULTA_CRONOGRAMA


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


def busqueda_222(**cambios):
    """Caso 222: la cláusula 2.2.6 de las bases y la modificación que la toca."""
    datos = {"evento_id": "222", "variante": "mejorada", "suficiente": True,
             "fragmentos": [
                 fragmento(),
                 fragmento(chunk_id="222-mod-p1-0", doc_id="222-mod", tipo_documento="modificacion",
                           seccion="2.2 Modifica", url_origen=None, score=0.8, reranker=0.8,
                           semantico=0.5, lexico=0.3, rrf=0.02,
                           identificador_version_oficial="Modificación Número 1"),
                 fragmento(chunk_id="222-mod-p2-0", doc_id="222-mod", tipo_documento="modificacion",
                           seccion="2.2 Modifica", url_origen=None, score=0.62, reranker=None,
                           semantico=0.62, lexico=None, rrf=None, incluido_por="posible_conflicto",
                           identificador_version_oficial="Modificación Número 1")],
             "alertas": [
                 {"tipo": "posible_conflicto", "doc_id": "222-mod",
                  "documento": "Modificación Número 1", "numerales_modificados": ["2.2"],
                  "chunk_ids_afectados": ["222-bases-p8-0"]},
                 {"tipo": "cobertura_incompleta", "doc_id": "222-bases",
                  "paginas_no_indexadas": [3, 4], "status": "requiere_revision"}]}
    return {**datos, **cambios}


def comparacion_222(**cambios):
    """Los documentos del evento 222 tal como los ordena el rol 2."""
    datos = {"evento_id": "222", "documentos": [
        {"doc_id": "222-bases", "tipo_documento": "bases", "identificador_version_oficial": None,
         "fragmentos": [fragmento_comparado(score=0.7)]},
        {"doc_id": "222-mod", "tipo_documento": "modificacion",
         "identificador_version_oficial": "Modificación Número 1",
         "fragmentos": [fragmento_comparado(chunk_id="222-mod-p1-0", doc_id="222-mod",
                                            tipo_documento="modificacion", url_origen=None,
                                            identificador_version_oficial="Modificación Número 1",
                                            score=0.6)]}]}
    return {**datos, **cambios}


def params_buscar(**cambios):
    datos = {"query": "cláusula 2.2.6", "evento_id": "222"}
    return BuscarDocumentosParams(**{**datos, **cambios})


def params_comparar(**cambios):
    datos = {"evento_id": "222", "tema": "cláusula 2.2.6"}
    return CompararVersionesParams(**{**datos, **cambios})


class RecuperadorFalso:
    """Devuelve diccionarios con la forma exacta del rol 2 y registra cada llamada."""

    def __init__(self, busqueda=None, comparacion=None, error=None):
        self.busqueda, self.comparacion, self.error = busqueda, comparacion, error
        self.llamadas = []

    def buscar(self, ctx, evento_id, pregunta, variante="mejorada", k=5, conn=None):
        self.llamadas.append(("buscar", ctx, evento_id, pregunta, variante, k))
        if self.error:
            raise self.error
        return self.busqueda

    def comparar_versiones(self, ctx, evento_id, pregunta, k=2, conn=None):
        self.llamadas.append(("comparar_versiones", ctx, evento_id, pregunta, k))
        if self.error:
            raise self.error
        return self.comparacion


class BuscarDocumentosTests(unittest.TestCase):
    def test_caso_222(self):
        resultado = buscar_documentos(None, params_buscar(),
                                      RecuperadorFalso(busqueda=busqueda_222()))
        self.assertFalse(resultado.abstener)
        self.assertTrue(resultado.needs_human_review)
        self.assertEqual(resultado.coverage_status, "parcial")
        self.assertEqual(resultado.warnings,
                         ["cobertura_incompleta: 222-bases páginas no indexadas 3, 4"])
        self.assertIsNone(resultado.error)
        self.assertEqual(resultado.documentos, [])
        # Ambas fuentes quedan presentes: bases y la modificación que la toca.
        self.assertEqual({f.chunk_id for f in resultado.fragmentos},
                         {"222-bases-p8-0", "222-mod-p1-0", "222-mod-p2-0"})

    def test_filtro_por_tipo_conserva_el_conflicto(self):
        resultado = buscar_documentos(None, params_buscar(tipo_documento="bases"),
                                      RecuperadorFalso(busqueda=busqueda_222()))
        self.assertEqual({f.chunk_id for f in resultado.fragmentos},
                         {"222-bases-p8-0", "222-mod-p1-0", "222-mod-p2-0"})
        self.assertFalse(resultado.abstener)

    def test_filtro_modificacion_conserva_la_base_afectada(self):
        resultado = buscar_documentos(None, params_buscar(tipo_documento="modificacion"),
                                      RecuperadorFalso(busqueda=busqueda_222()))
        self.assertEqual([f.chunk_id for f in resultado.fragmentos],
                         ["222-bases-p8-0", "222-mod-p1-0", "222-mod-p2-0"])
        self.assertTrue(resultado.needs_human_review)
        self.assertFalse(resultado.abstener)

    def test_filtro_anexo_conserva_solo_las_fuentes_del_conflicto(self):
        busqueda = busqueda_222()
        busqueda["fragmentos"].append(fragmento(chunk_id="222-bases-p9-0", seccion="2.8 Otra cláusula"))
        resultado = buscar_documentos(None, params_buscar(tipo_documento="anexo"),
                                      RecuperadorFalso(busqueda=busqueda))
        self.assertEqual([f.chunk_id for f in resultado.fragmentos],
                         ["222-bases-p8-0", "222-mod-p1-0", "222-mod-p2-0"])
        self.assertTrue(resultado.needs_human_review)
        self.assertFalse(resultado.abstener)

    def test_filtro_sin_fragmentos_abstiene(self):
        # Sin conflicto en juego: el filtro por un tipo sin fragmentos deja el banco vacío.
        busqueda = busqueda_222(fragmentos=[fragmento()], alertas=[
            {"tipo": "cobertura_incompleta", "doc_id": "222-bases",
             "paginas_no_indexadas": [3, 4], "status": "requiere_revision"}])
        resultado = buscar_documentos(None, params_buscar(tipo_documento="anexo"),
                                      RecuperadorFalso(busqueda=busqueda))
        self.assertTrue(resultado.abstener)
        self.assertEqual(resultado.fragmentos, [])
        self.assertEqual(resultado.warnings[-1], "sin_fragmentos_del_tipo: anexo")

    def test_suficiente_false_abstiene(self):
        resultado = buscar_documentos(None, params_buscar(),
                                      RecuperadorFalso(busqueda=busqueda_222(suficiente=False)))
        self.assertTrue(resultado.abstener)
        # El conflicto y la cobertura no desaparecen al abstenerse.
        self.assertTrue(resultado.needs_human_review)
        self.assertEqual(resultado.coverage_status, "parcial")
        self.assertIsNone(resultado.error)

    def test_evento_con_modificaciones_avisa(self):
        busqueda = busqueda_222(alertas=[
            {"tipo": "evento_con_modificaciones", "doc_id": "222-mod",
             "documento": "Modificación Número 1"}])
        resultado = buscar_documentos(None, params_buscar(), RecuperadorFalso(busqueda=busqueda))
        self.assertIn("evento_con_modificaciones: 222-mod", resultado.warnings)
        self.assertEqual(resultado.coverage_status, "sin_faltantes_detectados")
        self.assertFalse(resultado.needs_human_review)

    def test_alerta_desconocida_no_rompe(self):
        busqueda = busqueda_222(alertas=[{"tipo": "firma_pendiente", "doc_id": "222-bases",
                                          "detalle": "sin firmar"}])
        resultado = buscar_documentos(None, params_buscar(), RecuperadorFalso(busqueda=busqueda))
        self.assertIn("alerta_desconocida: firma_pendiente", resultado.warnings)
        self.assertFalse(resultado.abstener)


class CompararVersionesTests(unittest.TestCase):
    def test_sin_ids_compara_todos(self):
        recuperador = RecuperadorFalso(busqueda=busqueda_222(), comparacion=comparacion_222())
        resultado = comparar_versiones(None, params_comparar(), recuperador)
        self.assertFalse(resultado.abstener)
        self.assertTrue(resultado.needs_human_review)
        self.assertEqual([d.doc_id for d in resultado.documentos], ["222-bases", "222-mod"])
        # fragmentos lleva los de buscar; documentos, los de comparar.
        self.assertEqual({f.chunk_id for f in resultado.fragmentos},
                         {"222-bases-p8-0", "222-mod-p1-0", "222-mod-p2-0"})

    def test_con_ids_deja_solo_esos_dos(self):
        comparacion = comparacion_222()
        comparacion["documentos"].insert(0, {
            "doc_id": "222-acl", "tipo_documento": "aclaracion",
            "identificador_version_oficial": "Aclaración Número 1",
            "fragmentos": [fragmento_comparado(chunk_id="222-acl-p1-0", doc_id="222-acl",
                                               tipo_documento="aclaracion", url_origen=None,
                                               identificador_version_oficial="Aclaración Número 1")]})
        recuperador = RecuperadorFalso(busqueda=busqueda_222(), comparacion=comparacion)
        resultado = comparar_versiones(
            None, params_comparar(doc_base_id="222-bases", doc_cambio_id="222-mod"), recuperador)
        self.assertEqual([d.doc_id for d in resultado.documentos], ["222-bases", "222-mod"])
        self.assertFalse(resultado.abstener)

    def test_id_ajeno_al_evento(self):
        recuperador = RecuperadorFalso(busqueda=busqueda_222(), comparacion=comparacion_222())
        resultado = comparar_versiones(
            None, params_comparar(doc_base_id="222-bases", doc_cambio_id="222-ajeno"), recuperador)
        self.assertEqual(resultado.error, "documento_fuera_del_evento")
        self.assertTrue(resultado.abstener)

    def test_un_solo_documento_abstiene(self):
        comparacion = comparacion_222()
        del comparacion["documentos"][1]
        recuperador = RecuperadorFalso(busqueda=busqueda_222(), comparacion=comparacion)
        resultado = comparar_versiones(None, params_comparar(), recuperador)
        self.assertTrue(resultado.abstener)
        self.assertTrue(any(w.startswith("sin_documentos_para_comparar")
                            for w in resultado.warnings))
        self.assertEqual([d.doc_id for d in resultado.documentos], ["222-bases"])

    def test_documento_sin_fragmentos_no_cuenta(self):
        comparacion = comparacion_222()
        comparacion["documentos"][1]["fragmentos"] = []
        recuperador = RecuperadorFalso(busqueda=busqueda_222(), comparacion=comparacion)
        resultado = comparar_versiones(None, params_comparar(), recuperador)
        self.assertTrue(resultado.abstener)
        self.assertEqual([d.doc_id for d in resultado.documentos], ["222-bases"])

    def test_suficiente_false_abstiene(self):
        recuperador = RecuperadorFalso(busqueda=busqueda_222(suficiente=False),
                                       comparacion=comparacion_222())
        resultado = comparar_versiones(None, params_comparar(), recuperador)
        self.assertTrue(resultado.abstener)
        # Hay una modificación en juego: sigue pidiendo revisión humana.
        self.assertTrue(resultado.needs_human_review)


class LlamadasTests(unittest.TestCase):
    def test_buscar_ctx_tal_cual_y_variante_mejorada(self):
        ctx = object()
        recuperador = RecuperadorFalso(busqueda=busqueda_222())
        buscar_documentos(ctx, params_buscar(query="constancia", k=3), recuperador)
        self.assertIs(recuperador.llamadas[0][1], ctx)
        self.assertEqual(recuperador.llamadas,
                         [("buscar", ctx, "222", "constancia", "mejorada", 3)])

    def test_comparar_llama_ambas_funciones(self):
        ctx = object()
        recuperador = RecuperadorFalso(busqueda=busqueda_222(), comparacion=comparacion_222())
        comparar_versiones(ctx, params_comparar(tema="plazo"), recuperador)
        self.assertIs(recuperador.llamadas[0][1], ctx)
        self.assertIs(recuperador.llamadas[1][1], ctx)
        self.assertEqual(recuperador.llamadas, [
            ("comparar_versiones", ctx, "222", "plazo", 2),
            ("buscar", ctx, "222", "plazo", "mejorada", 5)])


class ErroresTests(unittest.TestCase):
    def test_buscar_falla_recuperacion(self):
        resultado = buscar_documentos(None, params_buscar(),
                                      RecuperadorFalso(error=RuntimeError("sin conexión")))
        self.assertEqual(resultado.error, "falla_recuperacion")
        self.assertTrue(resultado.abstener)
        self.assertEqual((resultado.fragmentos, resultado.documentos, resultado.warnings),
                         ([], [], []))

    def test_comparar_falla_recuperacion(self):
        resultado = comparar_versiones(None, params_comparar(),
                                       RecuperadorFalso(error=RuntimeError("sin conexión")))
        self.assertEqual(resultado.error, "falla_recuperacion")
        self.assertTrue(resultado.abstener)

    def test_buscar_contrato_invalido(self):
        sin_suficiente = busqueda_222()
        del sin_suficiente["suficiente"]
        resultado = buscar_documentos(None, params_buscar(), RecuperadorFalso(busqueda=sin_suficiente))
        self.assertEqual(resultado.error, "contrato_invalido")
        sin_chunk = busqueda_222()
        del sin_chunk["fragmentos"][0]["chunk_id"]
        resultado = buscar_documentos(None, params_buscar(), RecuperadorFalso(busqueda=sin_chunk))
        self.assertEqual(resultado.error, "contrato_invalido")
        self.assertTrue(resultado.abstener)

    def test_comparar_contrato_invalido(self):
        comparacion = comparacion_222()
        del comparacion["documentos"][0]["tipo_documento"]
        recuperador = RecuperadorFalso(busqueda=busqueda_222(), comparacion=comparacion)
        resultado = comparar_versiones(None, params_comparar(), recuperador)
        self.assertEqual(resultado.error, "contrato_invalido")
        self.assertTrue(resultado.abstener)


class CategoriasTests(unittest.TestCase):
    """F5: la categoría de cada fragmento sale de la consulta fija que lo recuperó."""

    def extraer(self, por_consulta, categoria=None):
        class Recuperador:
            def buscar(self, ctx, evento_id, pregunta, variante="mejorada", k=5, conn=None):
                return {"evento_id": "222", "variante": "mejorada", "suficiente": True,
                        "fragmentos": por_consulta.get(pregunta, []), "alertas": []}
        return extraer_requisitos(None, ExtraerRequisitosParams(evento_id="222", categoria=categoria),
                                  Recuperador())

    def test_fragmento_de_la_consulta_legal_queda_legal(self):
        legal = fragmento(chunk_id="a", texto="Constancia.")
        r = self.extraer({CONSULTAS_POR_CATEGORIA["legal"]: [legal]})
        self.assertEqual(r.categorias, {"a": "legal"})

    def test_fragmento_en_dos_consultas_conserva_la_primera(self):
        f = fragmento(chunk_id="a", texto="Constancia.")
        r = self.extraer({CONSULTAS_POR_CATEGORIA["legal"]: [f], CONSULTAS_POR_CATEGORIA["tecnica"]: [f]})
        self.assertEqual(r.categorias, {"a": "legal"})
        r = self.extraer({CONSULTAS_POR_CATEGORIA["administrativa"]: [f], CONSULTAS_POR_CATEGORIA["legal"]: [f]},
                         categoria="legal")
        self.assertEqual(r.categorias, {"a": "legal"})

    def test_fragmento_solo_del_cronograma_no_tiene_categoria(self):
        r = self.extraer({CONSULTA_CRONOGRAMA: [fragmento(chunk_id="c", texto="Cronograma.")]})
        self.assertEqual(r.categorias, {})
        self.assertEqual(len(r.fragmentos), 1)

    def test_otras_herramientas_dejan_el_campo_vacio(self):
        r = buscar_documentos(None, BuscarDocumentosParams(query="x", evento_id="222"),
                              RecuperadorFalso(busqueda=busqueda_222()))
        self.assertEqual(r.categorias, {})


class PosibleConflictoTests(unittest.TestCase):
    """C16 H6: el resultado distingue la alerta posible_conflicto de las demás causas de revisión."""

    def extraer(self, alertas):
        class Recuperador:
            def buscar(self, ctx, evento_id, pregunta, variante="mejorada", k=5, conn=None):
                return {"evento_id": "222", "variante": "mejorada", "suficiente": True,
                        "fragmentos": [fragmento(chunk_id="a", texto="Constancia.")], "alertas": alertas}
        return extraer_requisitos(None, ExtraerRequisitosParams(evento_id="222"), Recuperador())

    def test_c16_con_la_alerta_posible_conflicto(self):
        r = self.extraer([{"tipo": "posible_conflicto", "doc_id": "m", "chunk_ids_afectados": ["a"]}])
        self.assertTrue(r.posible_conflicto)
        self.assertTrue(r.needs_human_review)

    def test_c16_sin_alerta_o_con_otra_no_hay_conflicto(self):
        self.assertFalse(self.extraer([]).posible_conflicto)
        r = self.extraer([{"tipo": "evento_con_modificaciones", "doc_id": "m"}])
        self.assertFalse(r.posible_conflicto)


class PreguntaEnExtraerTests(unittest.TestCase):
    """C9-D: la pregunta del usuario es la primera consulta, antes de las fijas y del cronograma."""

    def consultas(self, **params):
        recuperador = RecuperadorFalso(busqueda=busqueda_222())
        extraer_requisitos(None, ExtraerRequisitosParams(evento_id="222", **params), recuperador)
        return [llamada[3] for llamada in recuperador.llamadas]

    def test_con_pregunta_es_la_primera_consulta(self):
        consultas = self.consultas(pregunta="¿Qué requisitos tiene la plica?")
        self.assertEqual(consultas[0], "¿Qué requisitos tiene la plica?")
        self.assertEqual(consultas[1:], [*CONSULTAS_POR_CATEGORIA.values(), CONSULTA_CRONOGRAMA])

    def test_con_categoria_tambien_va_primero(self):
        consultas = self.consultas(pregunta="plica", categoria="legal")
        self.assertEqual(consultas, ["plica", CONSULTAS_POR_CATEGORIA["legal"], CONSULTA_CRONOGRAMA])

    def test_sin_pregunta_no_cambia_nada(self):
        self.assertEqual(self.consultas(), [*CONSULTAS_POR_CATEGORIA.values(), CONSULTA_CRONOGRAMA])

    def test_la_consulta_de_la_pregunta_no_asigna_categoria(self):
        r = extraer_requisitos(None, ExtraerRequisitosParams(evento_id="222", pregunta="plica"),
                               RecuperadorFalso(busqueda=busqueda_222()))
        self.assertEqual(set(r.categorias.values()), {"administrativa"})


class TemaComparacionTests(unittest.TestCase):
    """C9-E: al rol 2 se le pasa el núcleo del tema, sin la orden de comparar."""

    def test_formulaciones_de_la_demo(self):
        for pregunta, tema in (
            ("Compara la fecha de recepción de ofertas entre las bases y la modificación", "fecha de recepción de ofertas"),
            ("Compare el plazo de entrega entre las versiones", "plazo de entrega"),
            ("¿Cuál es la diferencia entre las bases y la modificación en la fecha de recepción de ofertas?",
             "fecha de recepción de ofertas"),
            ("Diferencia entre las versiones en el monto de la garantía", "monto de la garantía"),
        ):
            with self.subTest(pregunta=pregunta):
                self.assertEqual(tema_comparacion(pregunta), tema)

    def test_que_cambio_en_y_numero_de_modificacion_c12(self):
        for pregunta, tema in (
            ("¿Qué cambió en el cronograma entre las bases y la modificación 1?", "cronograma"),
            ("¿Qué cambia en el cronograma entre las bases y la modificación Número 1?", "cronograma"),
            ("¿Qué diferencias hay en la fecha de recepción de ofertas entre las bases y la aclaración 2?",
             "fecha de recepción de ofertas"),
            ("Compara el cronograma entre las bases y la modificación 1", "cronograma"),
            ("¿Qué cambió en la fecha de recepción de ofertas?", "fecha de recepción de ofertas"),
        ):
            with self.subTest(pregunta=pregunta):
                self.assertEqual(tema_comparacion(pregunta), tema)

    def test_lo_que_no_tiene_orden_se_deja_igual(self):
        for pregunta in ("¿Qué cambió con la modificación 1?", "fecha de recepción de ofertas"):
            with self.subTest(pregunta=pregunta):
                self.assertEqual(tema_comparacion(pregunta), pregunta)

    def test_sin_nucleo_queda_vacio(self):
        for pregunta in ("Compara las bases y la modificación", "Compara las versiones", "¿Cuál es la diferencia?"):
            with self.subTest(pregunta=pregunta):
                self.assertEqual(tema_comparacion(pregunta), "")


class ImportacionesTests(unittest.TestCase):
    def test_importar_no_carga_recuperacion(self):
        # Proceso limpio: importar lectura y herramientas no debe cargar al rol 2.
        src = str(Path(__file__).resolve().parents[3])
        codigo = ("import sys; import licigt.consulta.lectura, licigt.consulta.herramientas; "
                  "assert 'licigt.recuperacion' not in sys.modules, "
                  "sorted(m for m in sys.modules if 'recuperacion' in m)")
        resultado = subprocess.run([sys.executable, "-c", codigo], env={**os.environ, "PYTHONPATH": src},
                                   capture_output=True, text=True)
        self.assertEqual(resultado.returncode, 0, resultado.stderr)


if __name__ == "__main__":
    unittest.main()
