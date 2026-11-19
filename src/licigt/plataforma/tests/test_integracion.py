"""Permisos entre empresas con Postgres real (se saltan sin base, como las del rol 2).

Requieren make db-up, make importar y make empresa-b. El generador es un doble; la recuperación es la real."""

import json
import os
import re
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from html import unescape
from pathlib import Path
from unittest.mock import patch

from licigt.consulta.config import obtener_configuracion_llm
from licigt.consulta.enrutador import EnrutadorReglas
from licigt.consulta.lista_escritura import RepositorioMemoria
from licigt.plataforma.tests import soporte

try:
    from fastapi.testclient import TestClient
    from licigt.consulta import api
    from licigt.recuperacion import busqueda
    from licigt.recuperacion.indice import conectar
except ImportError:
    TestClient = None

def conectar_admin():
    """Lecturas de verificación como dueño de la base (sin seguridad por fila): LICIGT_DB_ADMIN_URL, que pone make."""
    import psycopg
    return psycopg.connect(os.environ["LICIGT_DB_ADMIN_URL"], autocommit=True)


EVENTO_222, EVENTO_363 = "222-IGSS-2023", "363-IGSS-2026"
PREGUNTA = "¿Dónde se reciben las ofertas?"


class GeneradorDeCita:
    """Doble del LLM: cita el primer fragmento que recibe, con un tramo literal sin cifras."""
    modelo_generador = "generador-doble"
    perfil = "local"

    def generar(self, mensajes, esquema, semilla_extra=0):
        contenido = mensajes[-1]["content"]
        fragmento = re.search(r'<fragmento id="(F\d+)"[^>]*>\n(.*?)\n</fragmento>', contenido, re.S)
        alias, texto = fragmento.group(1), " ".join(unescape(fragmento.group(2)).split())
        tramo = re.search(r"[A-Za-zÁÉÍÓÚáéíóúñÑ ,.]{40,200}", texto)
        if not tramo:
            return json.dumps({"abstener": True, "revision_humana": False, "afirmaciones": []})
        cita = tramo.group(0).strip()
        return json.dumps({"abstener": False, "revision_humana": False, "afirmaciones": [
            {"texto": cita, "citas": [{"fragmento": alias, "cita": cita}], "datos": []}]})


class Recuperador:
    """Envuelve el recuperador real y anota con qué empresa se llamó y qué fragmentos devolvió."""

    def __init__(self):
        self.llamadas, self._cerrojo = [], threading.Lock()

    def buscar(self, ctx, evento_id, pregunta, *a, **k):
        resultado = busqueda.buscar(ctx, evento_id, pregunta, *a, **k)
        with self._cerrojo:
            self.llamadas.append((ctx.tenant_id, evento_id, [f["chunk_id"] for f in resultado["fragmentos"]]))
        return resultado

    def __getattr__(self, nombre):
        return getattr(busqueda, nombre)


def _hay_base():
    """Sin LICIGT_DB_ADMIN_URL (no corre bajo make) se omite. Con ella, la base debe estar lista: si no, falla."""
    exigida = bool(os.environ.get("LICIGT_DB_ADMIN_URL"))
    if TestClient is None or not os.environ.get("LICIGT_DB_URL") or not exigida:
        return False
    try:
        conn = conectar()
        try:
            # La conexión de la aplicación no ve filas sin empresa en la sesión: se cuenta por empresa, como la API.
            for tenant in ("empresa_demo", "empresa_b"):
                with conn.transaction():
                    conn.execute("SET LOCAL ROLE licigt_app")
                    conn.execute("SELECT set_config('app.tenant_id', %s, true)", (tenant,))
                    if conn.execute("SELECT count(*) FROM documentos").fetchone()[0] == 0:
                        raise RuntimeError(f"sin documentos de {tenant}: corre make importar y make empresa-b")
        finally:
            conn.close()
    except Exception as e:
        raise RuntimeError(f"La integración de plataforma no puede correr: {e}. "
                           "Requisitos: make db-up, db-rol-app, lista-schema, importar y empresa-b") from e
    return True


@unittest.skipUnless(_hay_base(), "requiere make db-up, make importar y make empresa-b (LICIGT_DB_URL)")
class IntegracionPermisosTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        conn = conectar_admin()
        try:
            cls.docs = {t: {e: [r[0] for r in conn.execute(
                "SELECT doc_id FROM documentos WHERE tenant_id = %s AND numero_evento = %s", (t, e)).fetchall()]
                for e in (EVENTO_222, EVENTO_363)} for t in ("empresa_demo", "empresa_b")}
            cls.interno_363 = {t: conn.execute("SELECT DISTINCT evento_id FROM documentos WHERE tenant_id = %s "
                                               "AND numero_evento = %s", (t, EVENTO_363)).fetchone()[0]
                               for t in ("empresa_demo", "empresa_b")}
            cls.interno_222 = conn.execute("SELECT DISTINCT evento_id FROM documentos WHERE numero_evento = %s",
                                           (EVENTO_222,)).fetchone()[0]
        finally:
            conn.close()
        assert cls.docs["empresa_demo"][EVENTO_222] and cls.docs["empresa_demo"][EVENTO_363]
        assert cls.docs["empresa_b"][EVENTO_363] and not cls.docs["empresa_b"][EVENTO_222]

    def setUp(self):
        entorno = patch.dict(os.environ, soporte.preparar(soporte.carpeta_temporal(self)))
        entorno.start()
        self.addCleanup(entorno.stop)
        obtener_configuracion_llm.cache_clear()
        self.addCleanup(obtener_configuracion_llm.cache_clear)
        self.recuperador = Recuperador()
        api.app.dependency_overrides[api.obtener_enrutador] = EnrutadorReglas
        api.app.dependency_overrides[api.obtener_recuperador] = lambda: self.recuperador
        api.app.dependency_overrides[api.obtener_generador] = GeneradorDeCita
        self.repositorio = RepositorioMemoria()
        api.app.dependency_overrides[api.obtener_repositorio] = lambda: self.repositorio
        self.addCleanup(api.app.dependency_overrides.clear)

    @staticmethod
    def tenant_de(chunk_ids):
        """Empresas dueñas de los fragmentos, leídas con el dueño de la base (sin seguridad por fila)."""
        conn = conectar_admin()
        try:
            return {r[0] for r in conn.execute("SELECT DISTINCT tenant_id FROM fragmentos WHERE chunk_id = ANY(%s)",
                                               (list(chunk_ids),)).fetchall()}
        finally:
            conn.close()

    def cliente(self, usuario):
        cliente = TestClient(api.app)
        soporte.iniciar_sesion(cliente, usuario)
        return cliente

    # Acceso cruzado

    def test_analista_b_no_ve_el_222_ni_con_el_id_interno(self):
        b = self.cliente("analista_b")
        for evento in (EVENTO_222, self.interno_222):
            for metodo, ruta, cuerpo in (("POST", "consultas", {"pregunta": PREGUNTA}), ("GET", "documentos", None),
                                         ("GET", "lista", None), ("POST", "lista/propuesta", None)):
                with self.subTest(evento=evento, ruta=ruta):
                    r = b.request(metodo, f"/api/eventos/{evento}/{ruta}", json=cuerpo)
                    self.assertEqual(r.status_code, 404, r.text)
        self.assertEqual(self.recuperador.llamadas, [])

    def test_cada_empresa_ve_solo_sus_documentos_del_363(self):
        for usuario, tenant in (("analista_demo", "empresa_demo"), ("analista_b", "empresa_b")):
            r = self.cliente(usuario).get(f"/api/eventos/{EVENTO_363}/documentos")
            self.assertEqual(r.status_code, 200, r.text)
            self.assertEqual({d["doc_id"] for d in r.json()["documentos"]}, set(self.docs[tenant][EVENTO_363]))

    # Mezcla de eventos

    def test_consulta_sobre_el_363_solo_cita_fragmentos_de_la_propia_empresa(self):
        for usuario, tenant, otra in (("analista_demo", "empresa_demo", "empresa_b"),
                                      ("analista_b", "empresa_b", "empresa_demo")):
            with self.subTest(usuario=usuario):
                self.recuperador.llamadas.clear()
                r = self.cliente(usuario).post(f"/api/eventos/{EVENTO_363}/consultas", json={"pregunta": PREGUNTA})
                self.assertEqual(r.status_code, 200, r.text)
                (llamada,) = self.recuperador.llamadas
                self.assertTrue(llamada[2])
                self.assertEqual(self.tenant_de(llamada[2]), {tenant})
                cuerpo = r.json()
                self.assertFalse(cuerpo["abstained"], cuerpo["answer"])
                self.assertTrue(cuerpo["sources"])
                for fuente in cuerpo["sources"]:
                    self.assertIn(fuente["doc_id"], self.docs[tenant][EVENTO_363])
                    self.assertNotIn(fuente["doc_id"], self.docs[otra][EVENTO_363])
                # El 222 de empresa_demo no se mezcla con el 363 en ninguna fuente.
                self.assertFalse({f["doc_id"] for f in cuerpo["sources"]} & set(self.docs["empresa_demo"][EVENTO_222]))

    # Original sin permiso

    def test_original_propio_200_y_ajeno_404(self):
        doc_222 = self.docs["empresa_demo"][EVENTO_222][0]
        doc_363_demo = self.docs["empresa_demo"][EVENTO_363][0]
        doc_363_b = self.docs["empresa_b"][EVENTO_363][0]
        demo, b = self.cliente("analista_demo"), self.cliente("analista_b")
        for cliente, evento, doc in ((demo, EVENTO_222, doc_222), (demo, EVENTO_363, doc_363_demo),
                                     (b, EVENTO_363, doc_363_b)):
            r = cliente.get(f"/api/eventos/{evento}/documentos/{doc}/original")
            self.assertEqual(r.status_code, 200, r.text)
            self.assertTrue(r.content.startswith(b"%PDF"))
        sin_permiso = [(b, EVENTO_222, doc_222), (b, EVENTO_363, doc_363_demo), (demo, EVENTO_363, doc_363_b),
                       (demo, EVENTO_363, doc_222), (b, EVENTO_363, "e" * 32)]
        for cliente, evento, doc in sin_permiso:
            with self.subTest(evento=evento, doc=doc):
                self.assertEqual(cliente.get(f"/api/eventos/{evento}/documentos/{doc}/original").status_code, 404)

    # Rol lector

    def test_lector_no_escribe_la_lista_ni_con_el_id_interno_de_otra_empresa(self):
        lector = self.cliente("lector_demo")
        interno_363_b = self.interno_363["empresa_b"]
        cuerpo = {"items": [], "confirmado": True}
        for evento in (EVENTO_363, interno_363_b):
            with self.subTest(evento=evento):
                self.assertEqual(lector.post(f"/api/eventos/{evento}/lista", json=cuerpo).status_code, 403)
        for tenant in ("empresa_demo", "empresa_b"):
            for evento in self.interno_363.values():
                self.assertEqual(self.repositorio.items(tenant, evento), [])
        self.assertEqual(self.repositorio._cambios, {})

    # Concurrencia

    def verificar_aislamiento(self, resultados):
        """Cada respuesta cita solo documentos del 363 de la empresa del usuario; 5 llamadas por empresa."""
        propias = {"analista_demo": "empresa_demo", "analista_b": "empresa_b"}
        for usuario, cuerpo in resultados:
            tenant = propias[usuario]
            otro = "empresa_b" if tenant == "empresa_demo" else "empresa_demo"
            self.assertFalse(cuerpo["abstained"], cuerpo["answer"])
            self.assertTrue(cuerpo["sources"])
            for fuente in cuerpo["sources"]:
                self.assertIn(fuente["doc_id"], self.docs[tenant][EVENTO_363])
                self.assertNotIn(fuente["doc_id"], self.docs[otro][EVENTO_363])
        por_tenant = {}
        for tenant, _, chunk_ids in self.recuperador.llamadas:
            por_tenant[tenant] = por_tenant.get(tenant, 0) + 1
            self.assertEqual(self.tenant_de(chunk_ids), {tenant})
        self.assertEqual(por_tenant, {"empresa_demo": 5, "empresa_b": 5})

    def consultas_en_paralelo(self):
        self.cliente("analista_demo").post(f"/api/eventos/{EVENTO_363}/consultas", json={"pregunta": PREGUNTA})
        self.recuperador.llamadas.clear()  # el calentamiento carga los modelos antes de las hebras

        def consultar(usuario):
            r = self.cliente(usuario).post(f"/api/eventos/{EVENTO_363}/consultas", json={"pregunta": PREGUNTA})
            self.assertEqual(r.status_code, 200, r.text)
            return usuario, r.json()

        with ThreadPoolExecutor(max_workers=10) as pool:
            return list(pool.map(consultar, ["analista_demo", "analista_b"] * 5))

    def test_diez_consultas_en_paralelo_de_las_dos_empresas_no_se_mezclan(self):
        self.verificar_aislamiento(self.consultas_en_paralelo())

    def test_la_comprobacion_paralela_detecta_un_contexto_que_siempre_es_empresa_demo(self):
        from licigt.recuperacion.busqueda import Contexto
        api.app.dependency_overrides[api.contexto_acceso] = lambda: Contexto(tenant_id="empresa_demo", usuario="x")
        resultados = self.consultas_en_paralelo()
        with self.assertRaises(AssertionError):
            self.verificar_aislamiento(resultados)


if __name__ == "__main__":
    unittest.main()
