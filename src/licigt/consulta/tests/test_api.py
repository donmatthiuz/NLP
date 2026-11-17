"""Adaptador FastAPI de consulta con TestClient y dobles, sin red, GPU ni base de datos."""

import os
import sys
import unittest
from dataclasses import dataclass
from types import SimpleNamespace
from unittest.mock import patch

from licigt.consulta.config import obtener_configuracion_llm
from licigt.consulta.enrutador import EnrutadorReglas
from licigt.consulta.esquemas import RespuestaEstructurada, TEXTO_ABSTENCION
from licigt.consulta.tests.test_orquestador import GeneradorFalso, RecuperadorFalso

try:
    from fastapi.testclient import TestClient
except ImportError:
    TestClient = None
else:
    from licigt.consulta import api

URL = "/api/eventos/222/consultas"


@unittest.skipIf(TestClient is None, "fastapi no está instalado: ejecuta make deps-consulta")
class ApiTests(unittest.TestCase):
    def setUp(self):
        self.entorno = patch.dict(os.environ, {}, clear=True)
        self.entorno.start()
        obtener_configuracion_llm.cache_clear()
        self.recuperador = RecuperadorFalso()
        self.generador = GeneradorFalso()
        api.app.dependency_overrides[api.obtener_enrutador] = EnrutadorReglas
        api.app.dependency_overrides[api.obtener_recuperador] = lambda: self.recuperador
        api.app.dependency_overrides[api.obtener_generador] = lambda: self.generador
        # Sin psycopg se sustituye solo el módulo que define Contexto.
        try:
            import licigt.recuperacion.busqueda  # noqa: F401
            falso = {}
        except ImportError:
            @dataclass
            class Contexto:
                tenant_id: str
                usuario: str = "dev"
            falso = {"licigt.recuperacion.busqueda": SimpleNamespace(Contexto=Contexto)}
        sustituto = patch.dict(sys.modules, falso)
        sustituto.start()
        self.addCleanup(sustituto.stop)
        self.cliente = TestClient(api.app)

    def tearDown(self):
        api.app.dependency_overrides.clear()
        self.entorno.stop()
        obtener_configuracion_llm.cache_clear()

    def test_respuesta_respondible_con_fuentes(self):
        r = self.cliente.post(URL, json={"pregunta": "¿Dónde se reciben ofertas?"})
        self.assertEqual(r.status_code, 200)
        cuerpo = RespuestaEstructurada.model_validate(r.json())
        self.assertFalse(cuerpo.abstained)
        self.assertEqual(cuerpo.evento_id, "222")
        self.assertEqual(len(cuerpo.sources), 2)

    def test_abstencion_sin_evidencia_no_es_error_http(self):
        self.recuperador = RecuperadorFalso(suficiente=False)
        r = self.cliente.post(URL, json={"pregunta": "¿Dónde se reciben ofertas?"})
        self.assertEqual(r.status_code, 200)
        cuerpo = RespuestaEstructurada.model_validate(r.json())
        self.assertTrue(cuerpo.abstained)
        self.assertEqual(cuerpo.answer, TEXTO_ABSTENCION)
        self.assertEqual(self.generador.llamadas, [])

    def test_falla_del_generador_llega_como_abstencion(self):
        self.generador = GeneradorFalso(salidas=[RuntimeError("secreto")])
        r = self.cliente.post(URL, json={"pregunta": "¿Dónde se reciben ofertas?"})
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["abstained"])
        self.assertNotIn("secreto", r.text)

    def test_tenant_id_en_el_cuerpo_da_422(self):
        r = self.cliente.post(URL, json={"pregunta": "hola", "tenant_id": "otra"})
        self.assertEqual(r.status_code, 422)
        self.assertEqual(self.recuperador.llamadas, [])

    def test_tenant_id_sale_del_contexto_de_demo(self):
        self.cliente.post(URL, json={"pregunta": "¿Dónde se reciben ofertas?"})
        ctx = self.recuperador.llamadas[0][0]
        self.assertEqual((ctx.tenant_id, ctx.usuario), ("empresa_demo", "demo"))

    def test_pregunta_de_501_caracteres_da_422(self):
        self.assertEqual(self.cliente.post(URL, json={"pregunta": "a" * 501}).status_code, 422)
        self.assertEqual(self.cliente.post(URL, json={"pregunta": ""}).status_code, 422)

    def test_cabecera_de_demo_presente(self):
        for cuerpo in ({"pregunta": "¿Dónde se reciben ofertas?"}, {"pregunta": ""}):
            r = self.cliente.post(URL, json=cuerpo)
            self.assertEqual(r.headers["X-LiciGT-Autenticacion"], "ninguna-demo")

    def test_sin_cors(self):
        r = self.cliente.options(URL, headers={"Origin": "http://x", "Access-Control-Request-Method": "POST"})
        self.assertNotIn("access-control-allow-origin", r.headers)


if __name__ == "__main__":
    unittest.main()
