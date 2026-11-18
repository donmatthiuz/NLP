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
from licigt.consulta.lista_escritura import RepositorioMemoria
from licigt.consulta.tests import test_lista as tl
from licigt.consulta.tests.test_lista_escritura import LectorFalso, propuesta as items_propuestos
from licigt.consulta.tests.test_orquestador import GeneradorFalso, RecuperadorFalso
from licigt.plataforma.tests import soporte

try:
    from fastapi.testclient import TestClient
except ImportError:
    TestClient = None
else:
    from licigt.consulta import api

URL = "/api/eventos/222/consultas"
LISTA = "/api/eventos/222/lista"


@unittest.skipIf(TestClient is None, "fastapi no está instalado: ejecuta make deps-consulta")
class ApiTests(unittest.TestCase):
    def setUp(self):
        # Sesión de prueba: clave, usuarios y auditoría en un directorio temporal, no en keys/ ni data/.
        self.entorno = patch.dict(os.environ, soporte.preparar(soporte.carpeta_temporal(self)), clear=True)
        self.entorno.start()
        obtener_configuracion_llm.cache_clear()
        self.recuperador = RecuperadorFalso()
        self.generador = GeneradorFalso()
        api.app.dependency_overrides[api.obtener_enrutador] = EnrutadorReglas
        # Sin base: el valor de la ruta ya es el id interno.
        api.app.dependency_overrides[api.resolver_evento] = lambda evento_id: evento_id
        api.app.dependency_overrides[api.obtener_recuperador] = lambda: self.recuperador
        api.app.dependency_overrides[api.obtener_generador] = lambda: self.generador
        self.jev = None
        api.app.dependency_overrides[api.obtener_cliente_jev] = lambda: self.jev
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
        self.repositorio = RepositorioMemoria()
        self.lector = LectorFalso({"222": {f["chunk_id"]: f for f in (
            tl.FUNDAMENTAL, tl.NO_FUNDAMENTAL, tl.FECHA_BASES, tl.FECHA_MOD)}})
        api.app.dependency_overrides[api.obtener_repositorio] = lambda: self.repositorio
        api.app.dependency_overrides[api.obtener_lector] = lambda: self.lector
        self.cliente = TestClient(api.app)
        soporte.iniciar_sesion(self.cliente)

    def cuerpo_items(self, **extra):
        return {"items": [i.model_dump(mode="json") for i in items_propuestos()], "confirmado": True, **extra}

    def guardar(self):
        r = self.cliente.post(LISTA, json=self.cuerpo_items())
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()

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

    def test_tenant_id_sale_de_la_sesion(self):
        self.cliente.post(URL, json={"pregunta": "¿Dónde se reciben ofertas?"})
        ctx = self.recuperador.llamadas[0][0]
        self.assertEqual((ctx.tenant_id, ctx.usuario), ("empresa_demo", "analista_demo"))

    def test_pregunta_de_501_caracteres_da_422(self):
        self.assertEqual(self.cliente.post(URL, json={"pregunta": "a" * 501}).status_code, 422)
        self.assertEqual(self.cliente.post(URL, json={"pregunta": ""}).status_code, 422)

    def test_sin_cabecera_de_demo(self):
        for cuerpo in ({"pregunta": "¿Dónde se reciben ofertas?"}, {"pregunta": ""}):
            r = self.cliente.post(URL, json=cuerpo)
            self.assertNotIn("x-licigt-autenticacion", r.headers)

    def test_sin_cors(self):
        r = self.cliente.options(URL, headers={"Origin": "http://x", "Access-Control-Request-Method": "POST"})
        self.assertNotIn("access-control-allow-origin", r.headers)

    # Lista de verificación (F6d)

    def test_propuesta_devuelve_items_y_no_escribe(self):
        self.generador = tl.GeneradorProhibido()
        self.recuperador = tl.RecuperadorPorConsulta({
            tl.CONSULTAS_POR_CATEGORIA["legal"]: [tl.FUNDAMENTAL], tl.CONSULTA_CRONOGRAMA: [tl.FECHA_BASES]})
        r = self.cliente.post(LISTA + "/propuesta", json={"categoria": "legal"})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual([i["tipo"] for i in r.json()["items"]], ["requisito", "fecha"])
        self.assertEqual(self.repositorio.items("empresa_demo", "222"), [])
        self.assertEqual(self.repositorio._cambios, {})

    def test_c14_la_propuesta_recibe_el_cliente_jev_y_verifica_las_fechas(self):
        self.jev = tl.JevDeLista()
        self.recuperador = tl.RecuperadorPorConsulta({
            tl.CONSULTAS_POR_CATEGORIA["legal"]: [tl.FUNDAMENTAL], tl.CONSULTA_CRONOGRAMA: [tl.FECHA_BASES]})
        r = self.cliente.post(LISTA + "/propuesta", json={"categoria": "legal"})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(len(self.jev.llamadas), 1)
        fecha = [i for i in r.json()["items"] if i["tipo"] == "fecha"][0]
        self.assertEqual(fecha["descripcion"], "Recepción de ofertas: 31 de julio de 2023")

    def test_propuesta_sin_cuerpo_es_valida(self):
        self.recuperador = tl.RecuperadorPorConsulta({})
        r = self.cliente.post(LISTA + "/propuesta")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["respuesta"]["abstained"])
        self.assertNotIn("secreto", r.text)

    def test_tenant_id_en_el_cuerpo_da_422_en_todas_las_rutas(self):
        item = self.guardar()[0]
        casos = [
            ("post", LISTA + "/propuesta", {"tenant_id": "otra"}),
            ("post", LISTA, self.cuerpo_items(tenant_id="otra")),
            ("patch", f"{LISTA}/{item['item_id']}", {"estado_anterior": "pendiente", "estado_nuevo": "preparado",
                                                      "confirmado": True, "tenant_id": "otra"}),
        ]
        for metodo, url, cuerpo in casos:
            with self.subTest(url=url):
                self.assertEqual(getattr(self.cliente, metodo)(url, json=cuerpo).status_code, 422)
        self.assertEqual(self.repositorio.obtener("empresa_demo", item["item_id"]).estado, "pendiente")

    def test_guardar_y_listar_con_el_tenant_de_la_sesion(self):
        guardados = self.guardar()
        self.assertEqual(len(guardados), 3)
        self.assertEqual({g["estado"] for g in guardados}, {"pendiente"})
        self.assertEqual({g["creado_por"] for g in guardados}, {"analista_demo"})
        self.assertEqual(len(self.repositorio.items("empresa_demo", "222")), 3)
        r = self.cliente.get(LISTA)
        self.assertEqual(r.status_code, 200)
        self.assertEqual({i["item_id"] for i in r.json()}, {g["item_id"] for g in guardados})
        self.assertNotIn("tenant_id", r.text)
        self.assertEqual(self.cliente.get("/api/eventos/otro/lista").json(), [])

    def test_guardar_sin_confirmado_true_da_422_y_no_escribe(self):
        for extra in ({"confirmado": False}, {"confirmado": 1}, {"confirmado": "true"}):
            with self.subTest(extra=extra):
                self.assertEqual(self.cliente.post(LISTA, json=self.cuerpo_items(**extra)).status_code, 422)
        sin = self.cuerpo_items()
        del sin["confirmado"]
        self.assertEqual(self.cliente.post(LISTA, json=sin).status_code, 422)
        self.assertEqual(self.repositorio.items("empresa_demo", "222"), [])
        self.assertEqual(self.lector.llamadas, [])

    def test_guardar_sin_items_o_con_item_invalido_da_422(self):
        self.assertEqual(self.cliente.post(LISTA, json={"items": [], "confirmado": True}).status_code, 422)
        cuerpo = self.cuerpo_items()
        cuerpo["items"][0]["descripcion"] = "texto libre"
        self.assertEqual(self.cliente.post(LISTA, json=cuerpo).status_code, 422)
        self.assertEqual(self.repositorio.items("empresa_demo", "222"), [])

    def test_cita_que_no_pasa_la_revalidacion_da_422_con_codigo_y_sin_texto(self):
        self.lector = LectorFalso({"222": {}})
        r = self.cliente.post(LISTA, json=self.cuerpo_items())
        self.assertEqual(r.status_code, 422)
        self.assertEqual(r.json()["detail"]["codigo"], "cita_no_valida")
        self.assertNotIn("constancia", r.text)
        self.assertEqual(self.repositorio.items("empresa_demo", "222"), [])

    def test_cambiar_estado(self):
        item = self.guardar()[0]
        cuerpo = {"estado_anterior": "pendiente", "estado_nuevo": "preparado", "confirmado": True}
        r = self.cliente.patch(f"{LISTA}/{item['item_id']}", json=cuerpo)
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["estado"], "preparado")
        self.assertEqual(self.repositorio.obtener("empresa_demo", item["item_id"]).estado, "preparado")

    def test_cambiar_estado_sin_confirmar_da_422_y_no_escribe(self):
        item = self.guardar()[0]
        for cuerpo in ({"estado_anterior": "pendiente", "estado_nuevo": "preparado"},
                       {"estado_anterior": "pendiente", "estado_nuevo": "preparado", "confirmado": False},
                       {"estado_anterior": "pendiente", "estado_nuevo": "inventado", "confirmado": True}):
            with self.subTest(cuerpo=cuerpo):
                self.assertEqual(self.cliente.patch(f"{LISTA}/{item['item_id']}", json=cuerpo).status_code, 422)
        self.assertEqual(self.repositorio.obtener("empresa_demo", item["item_id"]).estado, "pendiente")

    def test_estado_desactualizado_da_409(self):
        item = self.guardar()[0]
        cuerpo = {"estado_anterior": "revisado", "estado_nuevo": "preparado", "confirmado": True}
        r = self.cliente.patch(f"{LISTA}/{item['item_id']}", json=cuerpo)
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.json()["detail"]["codigo"], "estado_desactualizado")
        self.assertEqual(self.repositorio.obtener("empresa_demo", item["item_id"]).estado, "pendiente")

    def test_item_no_encontrado_da_404(self):
        cuerpo = {"estado_anterior": "pendiente", "estado_nuevo": "preparado", "confirmado": True}
        r = self.cliente.patch(f"{LISTA}/no-existe", json=cuerpo)
        self.assertEqual(r.status_code, 404)
        self.assertEqual(r.json()["detail"]["codigo"], "item_no_encontrado")

    def test_obtener_repositorio_por_defecto_es_unico_en_memoria(self):
        api.obtener_repositorio.cache_clear()
        with patch.dict(os.environ, {}, clear=True):
            self.assertIs(api.obtener_repositorio(), api.obtener_repositorio())
            self.assertIsInstance(api.obtener_repositorio(), RepositorioMemoria)
        api.obtener_repositorio.cache_clear()

    def test_con_lista_postgres_se_importan_de_forma_diferida_las_clases_sql(self):
        class RepoSql:
            def __init__(self, conn_factory):
                self.conn_factory = conn_factory

        class LectorSql(RepoSql):
            pass

        falso = {"licigt.consulta.lista_sql": SimpleNamespace(RepositorioPostgres=RepoSql, LectorFragmentosPostgres=LectorSql),
                 "licigt.recuperacion.indice": SimpleNamespace(conectar=lambda: None)}
        api.obtener_repositorio.cache_clear()
        api.obtener_lector.cache_clear()
        with patch.dict(os.environ, {"LICIGT_LISTA": "postgres"}), patch.dict(sys.modules, falso):
            self.assertIsInstance(api.obtener_repositorio(), RepoSql)
            self.assertIsInstance(api.obtener_lector(), LectorSql)
        api.obtener_repositorio.cache_clear()
        api.obtener_lector.cache_clear()


if __name__ == "__main__":
    unittest.main()


class ConexionFalsa:
    """Doble de la conexión del rol 2: guarda las consultas y devuelve una fila según el valor buscado."""
    def __init__(self, filas, documentos=()):
        self.filas, self.consultas, self.cerrada = filas, [], False
        self.documentos = list(documentos)

    def transaction(self):
        from contextlib import nullcontext
        return nullcontext()

    def execute(self, sql, params=()):
        self.consultas.append((" ".join(sql.split()), params))
        if "inventario" in sql:
            return SimpleNamespace(fetchall=lambda: self.documentos)
        tenant, valor = params if len(params) == 2 else (None, None)
        fila = next((f for f in self.filas if f[0] == tenant and valor in f[1:]), None)
        return SimpleNamespace(fetchone=lambda: (fila[1],) if fila else None)

    def close(self):
        self.cerrada = True


@unittest.skipIf(TestClient is None, "fastapi no está instalado: ejecuta make deps-consulta")
class ResolverEventoTests(unittest.TestCase):
    INTERNO = "69099f7184e65924a3e0aebf0ee238de"
    # (doc_id, tipo_documento, identificador_version_oficial, version_ingesta, status, paginas_no_indexadas,
    #  paginas_total, warnings), como las devuelve la consulta de la tabla documentos del rol 2.
    DOCUMENTOS = [
        ("d-bases", "bases", None, 1, "completo", [], "35", []),
        ("d-mod", "modificacion", "Modificación Número 1", 1, "requiere_revision", [4], "4",
         ["Hay páginas incompletas o ilegibles", "Menciona un anexo de 11 hojas que no está cargado"]),
    ]

    def setUp(self):
        self.entorno = patch.dict(os.environ, soporte.preparar(soporte.carpeta_temporal(self)), clear=True)
        self.entorno.start()
        obtener_configuracion_llm.cache_clear()
        self.conn = ConexionFalsa([("empresa_demo", self.INTERNO, "222-IGSS-2023"),
                                   ("otra_empresa", "ajeno", "999-IGSS-2024")], self.DOCUMENTOS)
        self.sesiones = []
        self.recuperador = RecuperadorFalso()
        self.visto = []
        api.app.dependency_overrides[api.obtener_enrutador] = EnrutadorReglas
        api.app.dependency_overrides[api.obtener_recuperador] = lambda: self.recuperador
        api.app.dependency_overrides[api.obtener_generador] = GeneradorFalso
        api.app.dependency_overrides[api.obtener_repositorio] = RepositorioMemoria
        self.parche = patch.object(api, "_abrir_conexion_rol2",
                                   lambda: (self.conn, lambda c, x: self.sesiones.append((c, x.tenant_id))))
        self.parche.start()
        # El evento se resuelve con la función del rol 2; el doble responde por empresa y valor como la tabla.
        self.resoluciones = []

        def resolver(ctx, evento, conn=None):
            self.resoluciones.append((ctx.tenant_id, evento))
            fila = next((f for f in self.conn.filas if f[0] == ctx.tenant_id and evento in f[1:]), None)
            return fila[1] if fila else None
        self.parche_resolver = patch("licigt.recuperacion.busqueda.resolver_evento", resolver)
        self.parche_resolver.start()
        self.cliente = TestClient(api.app)
        soporte.iniciar_sesion(self.cliente)

    def tearDown(self):
        self.parche_resolver.stop()
        self.parche.stop()
        api.app.dependency_overrides.clear()
        self.entorno.stop()
        obtener_configuracion_llm.cache_clear()

    def test_traduce_numero_de_evento_al_id_interno(self):
        r = self.cliente.post("/api/eventos/222-IGSS-2023/consultas", json={"pregunta": "¿Dónde se reciben ofertas?"})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(self.recuperador.llamadas[0][1], self.INTERNO)
        self.assertEqual(r.json()["evento_id"], "222-IGSS-2023")

    def test_la_respuesta_lleva_el_valor_de_la_ruta_tambien_con_el_id_interno(self):
        r = self.cliente.post(f"/api/eventos/{self.INTERNO}/consultas", json={"pregunta": "¿Dónde se reciben ofertas?"})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["evento_id"], self.INTERNO)

    def test_la_abstencion_tambien_lleva_el_valor_de_la_ruta(self):
        self.recuperador.busqueda["suficiente"] = False
        r = self.cliente.post("/api/eventos/222-IGSS-2023/consultas", json={"pregunta": "¿Dónde se reciben ofertas?"})
        self.assertTrue(r.json()["abstained"])
        self.assertEqual(r.json()["evento_id"], "222-IGSS-2023")

    def test_acepta_el_id_interno_y_lo_resuelve_con_la_funcion_del_rol_2(self):
        r = self.cliente.get(f"/api/eventos/{self.INTERNO}/lista")
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(self.resoluciones, [("empresa_demo", self.INTERNO)])
        self.assertEqual(self.conn.consultas, [])  # la API ya no escribe SQL para resolver el evento

    def test_evento_de_otra_empresa_o_inexistente_da_404(self):
        for valor in ("999-IGSS-2024", "ajeno", "no-existe"):
            for metodo, ruta in (("post", "consultas"), ("post", "lista/propuesta"), ("get", "lista"),
                                 ("post", "lista"), ("patch", "lista/x"), ("get", "documentos")):
                with self.subTest(valor=valor, ruta=ruta):
                    r = self.cliente.request(metodo.upper(), f"/api/eventos/{valor}/{ruta}", json={"pregunta": "x"})
                    self.assertEqual(r.status_code, 404, r.text)
                    self.assertEqual(r.json(), {"detail": {"codigo": "evento_no_encontrado"}})
        self.assertEqual(self.recuperador.llamadas, [])

    # C16: el valor de la ruta llega a quien llama en la propuesta, el listado y los ítems guardados.
    def montar_lista(self):
        pedido = "222-IGSS-2023"
        interno = self.INTERNO

        class RecuperadorDelEvento(tl.RecuperadorPorConsulta):
            def buscar(self, *a, **k):
                return {**super().buscar(*a, **k), "evento_id": interno}

        self.repo = RepositorioMemoria()
        api.app.dependency_overrides[api.obtener_repositorio] = lambda: self.repo
        api.app.dependency_overrides[api.obtener_recuperador] = lambda: RecuperadorDelEvento({
            tl.CONSULTAS_POR_CATEGORIA["legal"]: [tl.FUNDAMENTAL], tl.CONSULTA_CRONOGRAMA: [tl.FECHA_BASES]})
        api.app.dependency_overrides[api.obtener_cliente_jev] = lambda: None
        lector = LectorFalso({interno: {f["chunk_id"]: f for f in (tl.FUNDAMENTAL, tl.FECHA_BASES)}})
        api.app.dependency_overrides[api.obtener_lector] = lambda: lector
        return f"/api/eventos/{pedido}", pedido

    def test_c16_la_propuesta_el_listado_y_los_items_guardados_llevan_el_valor_de_la_ruta(self):
        base, pedido = self.montar_lista()
        p = self.cliente.post(base + "/lista/propuesta", json={"categoria": "legal"})
        self.assertEqual(p.status_code, 200, p.text)
        self.assertEqual((p.json()["evento_id"], p.json()["respuesta"]["evento_id"]), (pedido, pedido))
        guardados = self.cliente.post(base + "/lista", json={"items": p.json()["items"], "confirmado": True})
        self.assertEqual(guardados.status_code, 200, guardados.text)
        self.assertEqual({i["evento_id"] for i in guardados.json()}, {pedido})
        self.assertEqual({i["evento_id"] for i in self.cliente.get(base + "/lista").json()}, {pedido})
        item = guardados.json()[0]
        cambio = self.cliente.patch(f"{base}/lista/{item['item_id']}", json={
            "estado_anterior": "pendiente", "estado_nuevo": "preparado", "confirmado": True})
        self.assertEqual(cambio.status_code, 200, cambio.text)
        self.assertEqual(cambio.json()["evento_id"], pedido)
        # El repositorio sigue con el id interno.
        self.assertEqual(len(self.repo.items("empresa_demo", self.INTERNO)), len(guardados.json()))
        self.assertEqual(self.repo.items("empresa_demo", pedido), [])

    def test_c16_la_propuesta_abstenida_tambien_lleva_el_valor_de_la_ruta(self):
        r = self.cliente.post("/api/eventos/222-IGSS-2023/lista/propuesta")
        self.assertEqual(r.json()["evento_id"], "222-IGSS-2023")
        self.assertEqual(r.json()["respuesta"]["evento_id"], "222-IGSS-2023")

    # C16: panel de cobertura del evento.
    def test_c16_documentos_del_evento_con_lo_que_falta(self):
        r = self.cliente.get("/api/eventos/222-IGSS-2023/documentos")
        self.assertEqual(r.status_code, 200, r.text)
        cuerpo = r.json()
        self.assertEqual(cuerpo["evento_id"], "222-IGSS-2023")
        self.assertEqual(cuerpo["documentos"], [
            {"doc_id": "d-bases", "tipo_documento": "bases", "version_oficial": None, "version_ingesta": 1,
             "estado": "completo", "paginas_total": 35, "paginas_no_indexadas": [], "advertencias": []},
            {"doc_id": "d-mod", "tipo_documento": "modificacion", "version_oficial": "Modificación Número 1",
             "version_ingesta": 1, "estado": "requiere_revision", "paginas_total": 4, "paginas_no_indexadas": [4],
             "advertencias": ["Hay páginas incompletas o ilegibles",
                              "Menciona un anexo de 11 hojas que no está cargado"]}])

    def test_c16_documentos_usa_la_sesion_de_la_empresa_y_solo_lee(self):
        self.cliente.get("/api/eventos/222-IGSS-2023/documentos")
        self.assertEqual(self.sesiones, [(self.conn, "empresa_demo")])  # los documentos; el evento lo resuelve el rol 2
        sql, params = self.conn.consultas[-1]
        self.assertTrue(sql.startswith("SELECT"), sql)
        self.assertNotIn("texto", sql.lower().replace("inventario", ""))
        self.assertEqual(params, ("empresa_demo", self.INTERNO))
        self.assertTrue(all(c[0].startswith("SELECT") for c in self.conn.consultas))
        self.assertTrue(self.conn.cerrada)

    def test_c16_documentos_sin_filas_da_lista_vacia(self):
        self.conn.documentos.clear()
        r = self.cliente.get("/api/eventos/222-IGSS-2023/documentos")
        self.assertEqual(r.json()["documentos"], [])


    def test_las_rutas_de_lista_reciben_el_id_resuelto(self):
        recibido = {}
        def capturar(nombre):
            def falso(ctx, evento_id, *a, **k):
                recibido[nombre] = evento_id
                raise RuntimeError("corte")
            return falso
        for nombre in ("proponer_lista", "listar", "guardar_items"):
            self.addCleanup(setattr, api, nombre, getattr(api, nombre))
            setattr(api, nombre, capturar(nombre))
        cliente = TestClient(api.app, raise_server_exceptions=False)
        soporte.iniciar_sesion(cliente)
        base = "/api/eventos/222-IGSS-2023"
        cliente.post(f"{base}/lista/propuesta")
        cliente.get(f"{base}/lista")
        cliente.post(f"{base}/lista", json={"items": [], "confirmado": True})
        self.assertEqual(recibido, {n: self.INTERNO for n in ("proponer_lista", "listar", "guardar_items")})
