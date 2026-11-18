"""Sesión, permisos y auditoría de la API (TestClient con dobles, sin base de datos)."""

import json
import os
import unittest
from unittest.mock import patch

from licigt.consulta.config import obtener_configuracion_llm
from licigt.consulta.enrutador import EnrutadorReglas
from licigt.consulta.lista_escritura import RepositorioMemoria
from licigt.consulta.tests.test_lista_escritura import LectorFalso, propuesta as items_propuestos
from licigt.consulta.tests.test_orquestador import GeneradorFalso, RecuperadorFalso
from licigt.consulta.tests import test_lista as tl
from licigt.plataforma.tests import soporte

try:
    from fastapi.testclient import TestClient
except ImportError:
    TestClient = None
else:
    from licigt.consulta import api

URL = "/api/eventos/222/consultas"
LISTA = "/api/eventos/222/lista"
PDF = b"%PDF-1.7 original de prueba"
DOC = "c" * 32


@unittest.skipIf(TestClient is None, "fastapi no está instalado: ejecuta make deps-consulta")
class SesionTests(unittest.TestCase):
    def setUp(self):
        self.carpeta = soporte.carpeta_temporal(self)
        entorno = patch.dict(os.environ, soporte.preparar(self.carpeta), clear=True)
        entorno.start()
        self.addCleanup(entorno.stop)
        obtener_configuracion_llm.cache_clear()
        self.addCleanup(obtener_configuracion_llm.cache_clear)
        self.recuperador = RecuperadorFalso()
        self.repositorio = RepositorioMemoria()
        self.originales = {}
        self.llamadas_originales = []
        api.app.dependency_overrides[api.obtener_enrutador] = EnrutadorReglas
        api.app.dependency_overrides[api.resolver_evento] = lambda evento_id: evento_id
        api.app.dependency_overrides[api.obtener_recuperador] = lambda: self.recuperador
        api.app.dependency_overrides[api.obtener_generador] = GeneradorFalso
        api.app.dependency_overrides[api.obtener_cliente_jev] = lambda: None
        api.app.dependency_overrides[api.obtener_repositorio] = lambda: self.repositorio
        lector = LectorFalso({"222": {f["chunk_id"]: f for f in (
            tl.FUNDAMENTAL, tl.NO_FUNDAMENTAL, tl.FECHA_BASES, tl.FECHA_MOD)}})
        api.app.dependency_overrides[api.obtener_lector] = lambda: lector
        api.app.dependency_overrides[api.obtener_lector_originales] = lambda: self.leer_original
        self.addCleanup(api.app.dependency_overrides.clear)
        self.cliente = TestClient(api.app)

    def leer_original(self, ctx, evento_id, doc_id):
        self.llamadas_originales.append((ctx.tenant_id, evento_id, doc_id))
        return self.originales.get((ctx.tenant_id, evento_id, doc_id))

    def cuerpo_items(self):
        return {"items": [i.model_dump(mode="json") for i in items_propuestos()], "confirmado": True}

    def lineas_de_auditoria(self):
        carpeta = self.carpeta / "auditoria"
        return [json.loads(l) for f in sorted(carpeta.glob("*.jsonl")) for l in f.read_text().splitlines()]

    # Inicio y cierre de sesión

    def test_login_correcto_da_204_y_cookie_endurecida(self):
        r = soporte.iniciar_sesion(self.cliente)
        self.assertEqual(r.content, b"")
        cookie = r.headers["set-cookie"].lower()
        self.assertIn("licigt_sesion=", cookie)
        self.assertIn("httponly", cookie)
        self.assertIn("samesite=strict", cookie)
        self.assertIn("max-age=", cookie)
        self.assertEqual(self.cliente.get("/api/sesion").json(),
                         {"usuario": "analista_demo", "tenant_id": "empresa_demo", "rol": "analista"})

    def test_credenciales_malas_dan_401_generico_y_sin_cookie(self):
        malas = [{"usuario": "analista_demo", "contrasena": "mala"}, {"usuario": "nadie", "contrasena": "mala"}]
        respuestas = [self.cliente.post("/api/sesion", json=c) for c in malas]
        for r in respuestas:
            self.assertEqual(r.status_code, 401)
            self.assertNotIn("set-cookie", r.headers)
        self.assertEqual(respuestas[0].json(), respuestas[1].json())
        self.assertNotIn("analista_demo", respuestas[0].text)

    def test_login_rechaza_campos_extra_y_faltantes_con_422(self):
        c = {"usuario": "analista_demo", "contrasena": soporte.CONTRASENAS["analista_demo"]}
        self.assertEqual(self.cliente.post("/api/sesion", json={**c, "tenant_id": "empresa_b"}).status_code, 422)
        self.assertEqual(self.cliente.post("/api/sesion", json={"usuario": "x"}).status_code, 422)
        self.assertEqual(self.cliente.post("/api/sesion", json={**c, "contrasena": ""}).status_code, 422)

    def test_el_tenant_de_la_sesion_sale_del_archivo_de_usuarios(self):
        soporte.iniciar_sesion(self.cliente, "analista_b")
        self.assertEqual(self.cliente.get("/api/sesion").json()["tenant_id"], "empresa_b")

    def test_delete_cierra_la_sesion(self):
        soporte.iniciar_sesion(self.cliente)
        r = self.cliente.delete("/api/sesion")
        self.assertEqual(r.status_code, 204)
        self.assertEqual(self.cliente.get("/api/sesion").status_code, 401)
        self.assertEqual(self.cliente.post(URL, json={"pregunta": "hola"}).status_code, 401)

    def test_sin_clave_de_sesion_no_hay_login_ni_acceso(self):
        os.environ["LICIGT_SESION_CLAVE_ARCHIVO"] = str(self.carpeta / "no-existe.key")
        r = self.cliente.post("/api/sesion", json={"usuario": "analista_demo",
                                                    "contrasena": soporte.CONTRASENAS["analista_demo"]})
        self.assertEqual(r.status_code, 503)
        self.assertEqual(self.cliente.get("/api/sesion").status_code, 503)

    # Rutas protegidas

    def test_ninguna_ruta_de_api_responde_sin_sesion(self):
        publicas = {("POST", "/api/sesion"), ("DELETE", "/api/sesion")}
        rutas = [(m, r.path) for r in api.app.routes if r.path.startswith("/api") for m in r.methods
                 if m not in ("HEAD", "OPTIONS")]
        self.assertGreaterEqual(len(rutas), 8)
        for metodo, ruta in rutas:
            if (metodo, ruta) in publicas:
                continue
            url = ruta.replace("{evento_id}", "222").replace("{item_id}", "x").replace("{doc_id}", DOC)
            with self.subTest(metodo=metodo, ruta=ruta):
                r = self.cliente.request(metodo, url, json={"pregunta": "x"})
                self.assertEqual(r.status_code, 401, r.text)
        self.assertEqual(self.recuperador.llamadas, [])

    def test_cookie_alterada_da_401(self):
        soporte.iniciar_sesion(self.cliente)
        valor = self.cliente.cookies["licigt_sesion"]
        for malo in (valor[:-3] + "AAA", "x" + valor, "basura"):
            with self.subTest(malo=malo):
                otro = TestClient(api.app)
                otro.cookies.set("licigt_sesion", malo)
                self.assertEqual(otro.post(URL, json={"pregunta": "hola"}).status_code, 401)

    def test_cookie_vencida_da_401(self):
        soporte.iniciar_sesion(self.cliente)
        with patch("licigt.plataforma.sesion.time.time", return_value=4_000_000_000):
            self.assertEqual(self.cliente.get("/api/sesion").status_code, 401)
            self.assertEqual(self.cliente.post(URL, json={"pregunta": "hola"}).status_code, 401)

    def test_cookie_de_otra_clave_da_401(self):
        soporte.iniciar_sesion(self.cliente)
        (self.carpeta / "sesion.key").write_text("z" * 64)
        self.assertEqual(self.cliente.get("/api/sesion").status_code, 401)

    def test_ya_no_existe_la_cabecera_de_demo(self):
        r = self.cliente.get("/api/sesion")
        self.assertNotIn("x-licigt-autenticacion", r.headers)
        self.assertFalse(hasattr(api, "contexto_demo"))

    # A2: la sesión se exige antes de leer el cuerpo

    def test_sin_cookie_el_cuerpo_roto_da_401_y_no_llega_al_recuperador(self):
        item = "x"
        rutas = [("POST", URL), ("POST", LISTA + "/propuesta"), ("POST", LISTA), ("PATCH", f"{LISTA}/{item}")]
        for metodo, url in rutas:
            with self.subTest(url=url):
                r = self.cliente.request(metodo, url, content="{", headers={"content-type": "application/json"})
                self.assertEqual(r.status_code, 401, r.text)
        self.assertEqual(self.recuperador.llamadas, [])

    # A3: el usuario de la cookie debe seguir existiendo con el mismo tenant y rol

    def reescribir_usuarios(self, cambio):
        ruta = self.carpeta / "usuarios.json"
        datos = json.loads(ruta.read_text())
        cambio(datos["usuarios"])
        ruta.write_text(json.dumps(datos))

    def test_usuario_borrado_o_con_otro_rol_o_tenant_pierde_la_sesion(self):
        casos = {"borrado": lambda u: u.pop("analista_demo"),
                 "lector": lambda u: u["analista_demo"].update(rol="lector"),
                 "otro_tenant": lambda u: u["analista_demo"].update(tenant_id="empresa_b")}
        for nombre, cambio in casos.items():
            with self.subTest(caso=nombre):
                soporte.preparar(self.carpeta)
                cliente = TestClient(api.app)
                soporte.iniciar_sesion(cliente)
                self.reescribir_usuarios(cambio)
                self.assertEqual(cliente.get("/api/sesion").status_code, 401)
                self.assertIn(cliente.post(LISTA, json=self.cuerpo_items()).status_code, (401, 403))
                self.assertEqual(self.repositorio.items("empresa_demo", "222"), [])

    def test_usuarios_json_con_usuarios_que_no_es_un_dict_da_401_y_no_500(self):
        (self.carpeta / "usuarios.json").write_text(json.dumps({"usuarios": []}))
        r = self.cliente.post("/api/sesion", json={"usuario": "analista_demo", "contrasena": "x"})
        self.assertEqual(r.status_code, 401)
        self.assertEqual(self.cliente.get("/api/sesion").status_code, 401)

    # A4: Origin y Referer ajenos

    def test_origin_o_referer_ajeno_da_403_en_post_patch_y_delete(self):
        soporte.iniciar_sesion(self.cliente)
        for cabecera in ({"Origin": "http://malo.example"}, {"Referer": "http://malo.example/pagina"},
                         {"Origin": "null"}):
            for metodo, url in (("POST", LISTA + "/propuesta"), ("PATCH", f"{LISTA}/x"), ("DELETE", "/api/sesion"),
                                ("POST", "/api/sesion")):
                with self.subTest(cabecera=cabecera, url=url, metodo=metodo):
                    r = self.cliente.request(metodo, url, headers=cabecera)
                    self.assertEqual(r.status_code, 403, r.text)
        self.assertEqual(self.recuperador.llamadas, [])

    def test_origenes_locales_pasan_y_los_de_lectura_no_se_revisan(self):
        soporte.iniciar_sesion(self.cliente)
        for origen in ("http://127.0.0.1:8000", "http://localhost:8000", "http://127.0.0.1:5173",
                       "http://localhost:5173"):
            with self.subTest(origen=origen):
                r = self.cliente.post(URL, json={"pregunta": "¿Dónde se reciben ofertas?"}, headers={"Origin": origen})
                self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(self.cliente.get("/api/sesion", headers={"Origin": "http://malo.example"}).status_code, 200)
        r = self.cliente.post(URL, json={"pregunta": "hola"}, headers={"Referer": "http://localhost:5173/eventos/1"})
        self.assertEqual(r.status_code, 200)

    def test_los_origenes_permitidos_se_configuran(self):
        soporte.iniciar_sesion(self.cliente)
        h = {"Origin": "https://licigt.example"}
        self.assertEqual(self.cliente.post(URL, json={"pregunta": "hola"}, headers=h).status_code, 403)
        with patch.dict(os.environ, {"LICIGT_ORIGENES_PERMITIDOS": "https://licigt.example"}):
            self.assertEqual(self.cliente.post(URL, json={"pregunta": "hola"}, headers=h).status_code, 200)
        with patch.dict(os.environ, {"LICIGT_API_PUERTO": "8123"}):
            r = self.cliente.post(URL, json={"pregunta": "hola"}, headers={"Origin": "http://127.0.0.1:8123"})
            self.assertEqual(r.status_code, 200)

    # Duración de la sesión acotada a (0, 24] horas

    def test_horas_de_sesion_fuera_de_rango_vuelven_al_valor_por_defecto(self):
        for malo in ("nan", "inf", "-1", "0", "25", "abc"):
            with self.subTest(valor=malo), patch.dict(os.environ, {"LICIGT_SESION_HORAS": malo}):
                with self.assertLogs("licigt.consulta.api", "WARNING"):
                    self.assertEqual(api._horas_de_sesion(), 8)
        with patch.dict(os.environ, {"LICIGT_SESION_HORAS": "2.5"}):
            self.assertEqual(api._horas_de_sesion(), 2.5)

    # Rol

    def test_lector_consulta_y_ve_la_lista_pero_no_la_cambia(self):
        soporte.iniciar_sesion(self.cliente)
        self.assertEqual(self.cliente.post(LISTA, json=self.cuerpo_items()).status_code, 200)
        item = self.repositorio.items("empresa_demo", "222")[0]
        lector = TestClient(api.app)
        soporte.iniciar_sesion(lector, "lector_demo")
        self.assertEqual(lector.post(URL, json={"pregunta": "¿Dónde se reciben ofertas?"}).status_code, 200)
        self.assertEqual(len(lector.get(LISTA).json()), 3)

    def test_lector_no_guarda_ni_cambia_ni_propone_con_403(self):
        lector = TestClient(api.app)
        soporte.iniciar_sesion(lector, "lector_demo")
        r = lector.post(LISTA, json=self.cuerpo_items())
        self.assertEqual((r.status_code, r.json()["detail"]["codigo"]), (403, "sin_permiso"))
        self.assertEqual(self.repositorio.items("empresa_demo", "222"), [])
        soporte.iniciar_sesion(self.cliente)
        self.cliente.post(LISTA, json=self.cuerpo_items())
        item = self.repositorio.items("empresa_demo", "222")[0]
        cambio = {"estado_anterior": "pendiente", "estado_nuevo": "preparado", "confirmado": True}
        self.assertEqual(lector.patch(f"{LISTA}/{item.item_id}", json=cambio).status_code, 403)
        self.assertEqual(self.repositorio.obtener("empresa_demo", item.item_id).estado, "pendiente")
        self.assertEqual(lector.post(LISTA + "/propuesta").status_code, 403)

    def test_el_403_llega_antes_que_la_validacion_del_cuerpo(self):
        lector = TestClient(api.app)
        soporte.iniciar_sesion(lector, "lector_demo")
        self.assertEqual(lector.post(LISTA, json={"basura": 1}).status_code, 403)

    # El tenant solo sale de la cookie

    def test_tenant_id_no_se_fija_desde_cuerpo_consulta_ni_cabecera(self):
        soporte.iniciar_sesion(self.cliente)
        self.assertEqual(self.cliente.post(URL, json={"pregunta": "hola", "tenant_id": "empresa_b"}).status_code, 422)
        for extra in ({"params": {"tenant_id": "empresa_b"}},
                      {"headers": {"X-Tenant-Id": "empresa_b", "X-LiciGT-Tenant": "empresa_b", "tenant_id": "empresa_b"}}):
            with self.subTest(extra=list(extra)):
                self.cliente.post(URL, json={"pregunta": "¿Dónde se reciben ofertas?"}, **extra)
        self.assertEqual({(c[0].tenant_id, c[0].usuario) for c in self.recuperador.llamadas},
                         {("empresa_demo", "analista_demo")})

    def test_el_contexto_sale_de_la_sesion_de_cada_usuario(self):
        soporte.iniciar_sesion(self.cliente, "analista_b")
        self.cliente.post(URL, json={"pregunta": "¿Dónde se reciben ofertas?"})
        ctx = self.recuperador.llamadas[0][0]
        self.assertEqual((ctx.tenant_id, ctx.usuario), ("empresa_b", "analista_b"))

    def test_patch_de_un_item_de_otro_evento_da_404_y_no_cambia_nada(self):
        soporte.iniciar_sesion(self.cliente)
        self.cliente.post(LISTA, json=self.cuerpo_items())
        item = self.repositorio.items("empresa_demo", "222")[0]
        cambio = {"estado_anterior": "pendiente", "estado_nuevo": "preparado", "confirmado": True}
        r = self.cliente.patch(f"/api/eventos/otro/lista/{item.item_id}", json=cambio)
        self.assertEqual((r.status_code, r.json()["detail"]["codigo"]), (404, "item_no_encontrado"))
        self.assertEqual(self.repositorio.obtener("empresa_demo", item.item_id).estado, "pendiente")
        self.assertEqual(self.cliente.patch(f"{LISTA}/{item.item_id}", json=cambio).status_code, 200)

    # Original del PDF

    def test_original_propio_200_sin_exponer_rutas(self):
        self.originales[("empresa_demo", "222", DOC)] = PDF
        soporte.iniciar_sesion(self.cliente)
        r = self.cliente.get(f"/api/eventos/222/documentos/{DOC}/original")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.content, PDF)
        self.assertEqual(r.headers["content-type"], "application/pdf")
        self.assertEqual(r.headers["x-content-type-options"], "nosniff")
        self.assertNotIn("/", r.headers.get("content-disposition", "").replace("inline; filename=", ""))

    def test_original_ajeno_o_inexistente_da_404_igual(self):
        self.originales[("empresa_demo", "222", DOC)] = PDF
        soporte.iniciar_sesion(self.cliente, "analista_b")
        ajeno = self.cliente.get(f"/api/eventos/222/documentos/{DOC}/original")
        soporte.iniciar_sesion(self.cliente)
        inexistente = self.cliente.get(f"/api/eventos/222/documentos/{'d' * 32}/original")
        otro_evento = self.cliente.get(f"/api/eventos/999/documentos/{DOC}/original")
        self.assertEqual((ajeno.status_code, inexistente.status_code, otro_evento.status_code), (404, 404, 404))
        self.assertEqual(ajeno.json(), inexistente.json())

    def test_original_con_doc_id_invalido_se_rechaza_sin_leer(self):
        soporte.iniciar_sesion(self.cliente)
        for malo in ("..", "%2e%2e", "..%2f..%2fetc%2fpasswd", "x.pdf", "A" * 32):
            with self.subTest(malo=malo):
                r = self.cliente.get(f"/api/eventos/222/documentos/{malo}/original")
                self.assertIn(r.status_code, (400, 404))
        self.assertEqual(self.llamadas_originales, [])

    # Auditoría

    def test_se_audita_login_consulta_propuesta_y_lista_sin_texto_sensible(self):
        pregunta = "PREGUNTA-UNICA-¿Dónde se reciben ofertas?"
        self.cliente.post("/api/sesion", json={"usuario": "analista_demo", "contrasena": "CONTRASENA-MALA-123"})
        soporte.iniciar_sesion(self.cliente)
        cookie = self.cliente.cookies["licigt_sesion"]
        r = self.cliente.post(URL, json={"pregunta": pregunta})
        self.recuperador = tl.RecuperadorPorConsulta({})
        self.cliente.post(LISTA + "/propuesta")
        self.recuperador = RecuperadorFalso()
        self.cliente.post(LISTA, json=self.cuerpo_items())
        acciones = [(l["accion"], l["resultado"]) for l in self.lineas_de_auditoria()]
        self.assertEqual(acciones[0], ("login", "credenciales_invalidas"))
        self.assertEqual(acciones[1], ("login", "ok"))
        for esperada in ("consulta", "proponer_lista", "lista_alta"):
            self.assertIn(esperada, [a for a, _ in acciones])
        texto = "".join(f.read_text() for f in (self.carpeta / "auditoria").glob("*.jsonl"))
        for prohibido in ("PREGUNTA-UNICA", "CONTRASENA-MALA-123", cookie, soporte.CONTRASENAS["analista_demo"],
                          r.json()["answer"]):
            self.assertNotIn(prohibido, texto)
        consulta = next(l for l in self.lineas_de_auditoria() if l["accion"] == "consulta")
        self.assertEqual((consulta["usuario"], consulta["tenant_id"]), ("analista_demo", "empresa_demo"))
        fallido = self.lineas_de_auditoria()[0]
        self.assertTrue(fallido["usuario"].startswith("hmac:"))


if __name__ == "__main__":
    unittest.main()
