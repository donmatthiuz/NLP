"""F5b: la lista de verificación en Postgres. Sin base corren las pruebas con doble de conexión; con LICIGT_DB_URL, las de integración."""

import ast
import contextlib
import os
import threading
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from licigt.consulta.lista_escritura import FallaLista, RepositorioLista, cambiar_estado, listar
from licigt.consulta.lista_sql import COLUMNAS_ITEM, LectorFragmentosPostgres, RepositorioPostgres
from licigt.consulta.tests import test_lista_escritura as base
from licigt.consulta.tests.test_lista_escritura import CONFIRMADO, propuesta

CARPETA = Path(__file__).resolve().parent.parent
AHORA = datetime(2026, 11, 17, 12, 0, tzinfo=timezone.utc)
DB_URL = os.environ.get("LICIGT_DB_URL")
psycopg = None
if DB_URL:
    import psycopg


class ViolacionUnica(Exception):
    sqlstate = "23505"


class CursorFalso:
    def __init__(self, filas):
        self.filas = list(filas)

    def fetchone(self):
        return self.filas[0] if self.filas else None

    def fetchall(self):
        return self.filas


class ConexionFalsa:
    """Registra cada sentencia y cada frontera de transacción; las filas se escogen con `respuesta(sql)`."""

    def __init__(self, respuesta=lambda sql: [], falla=None):
        self.eventos, self.respuesta, self.falla, self.cerrada = [], respuesta, falla, False

    def execute(self, sql, params=None):
        self.eventos.append(("sql", sql, params))
        if self.falla and self.falla(sql):
            raise self.falla(sql)
        return CursorFalso(self.respuesta(sql))

    @contextlib.contextmanager
    def transaction(self):
        self.eventos.append(("BEGIN",))
        try:
            yield
        except BaseException:
            self.eventos.append(("ROLLBACK",))
            raise
        self.eventos.append(("COMMIT",))

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.cerrada = True

    @property
    def sentencias(self):
        return [(e[1], e[2]) for e in self.eventos if e[0] == "sql"]


def fila(item):
    d = item.model_dump(mode="json")
    d["creado_en"], d["actualizado_en"] = item.creado_en, item.actualizado_en
    return tuple(d[c] for c in COLUMNAS_ITEM)


def item_guardado(estado="pendiente"):
    from licigt.consulta.lista import ItemLista
    return ItemLista(**propuesta()[0].model_dump(), item_id="i1", evento_id="222", estado=estado,
                     creado_por="persona-a", creado_en=AHORA, actualizado_por="persona-a", actualizado_en=AHORA)


class SqlEstaticoTests(unittest.TestCase):
    def test_todo_el_sql_va_parametrizado(self):
        arbol = ast.parse((CARPETA / "lista_sql.py").read_text(encoding="utf-8"))
        llamadas = [n for n in ast.walk(arbol) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                    and n.func.attr == "execute"]
        self.assertGreaterEqual(len(llamadas), 5)
        for llamada in llamadas:
            sql = llamada.args[0]
            with self.subTest(linea=llamada.lineno):
                self.assertFalse(isinstance(sql, (ast.JoinedStr, ast.BinOp)))
                if not isinstance(sql, ast.Constant):
                    self.assertIsInstance(sql, ast.Name)  # constante del módulo, nunca armada con datos
        modulo = ast.unparse(arbol)
        self.assertNotIn(".format(", modulo)

    def test_esquema_habilita_rls_y_la_politica_en_las_dos_tablas(self):
        sql = (CARPETA / "lista_schema.sql").read_text(encoding="utf-8")
        for tabla in ("lista_items", "lista_cambios"):
            self.assertIn(f"CREATE TABLE IF NOT EXISTS {tabla}", sql)
            self.assertIn(f"ALTER TABLE {tabla} ENABLE ROW LEVEL SECURITY", sql)
            self.assertIn(f"DROP POLICY IF EXISTS por_empresa ON {tabla}", sql)
            self.assertIn(f"CREATE POLICY por_empresa ON {tabla} TO licigt_app", sql)
            self.assertIn(f"CREATE INDEX IF NOT EXISTS {tabla}_tenant ON {tabla} (tenant_id)", sql)
            self.assertIn(f"CREATE INDEX IF NOT EXISTS {tabla}_evento ON {tabla} (evento_id)", sql)
        self.assertEqual(sql.count("current_setting('app.tenant_id', true)"), 2)
        self.assertNotIn("INSERT", sql.replace("GRANT SELECT, INSERT", ""))


class ContratoConDobleTests(unittest.TestCase):
    def repo(self, conn):
        return RepositorioPostgres(lambda: conn)

    def assert_sesion_por_empresa(self, conn, tenant):
        sentencias = conn.sentencias
        self.assertEqual(conn.eventos[0], ("BEGIN",))
        self.assertIn("SET LOCAL ROLE licigt_app", sentencias[0][0])
        self.assertIn("set_config('app.tenant_id', %s, true)", sentencias[1][0])
        self.assertEqual(sentencias[1][1], (tenant,))
        self.assertEqual(conn.eventos[-1], ("COMMIT",))
        self.assertTrue(conn.cerrada)

    def test_cumple_el_protocolo(self):
        self.assertTrue(isinstance(self.repo(ConexionFalsa()), RepositorioLista))
        self.assertTrue(callable(LectorFragmentosPostgres(lambda: ConexionFalsa()).obtener))

    def test_lecturas_fijan_la_empresa_y_la_filtran_en_el_sql(self):
        item = item_guardado()
        conn = ConexionFalsa(lambda sql: [fila(item)])
        self.assertEqual(self.repo(conn).items("empresa-a", "222"), [item])
        self.assert_sesion_por_empresa(conn, "empresa-a")
        sql, params = conn.sentencias[2]
        self.assertIn("tenant_id = %s", sql)
        self.assertEqual(params[0], "empresa-a")
        self.assertNotIn("empresa-a", sql)

        conn = ConexionFalsa(lambda sql: [fila(item)])
        self.assertEqual(self.repo(conn).obtener("empresa-a", "i1"), item)
        self.assertIn("tenant_id = %s", conn.sentencias[2][0])
        conn = ConexionFalsa()
        self.assertIsNone(self.repo(conn).obtener("empresa-a", "no-existe"))

    def test_insertar_es_una_transaccion_con_items_y_cambios(self):
        guardados = base.guardar_items(
            SimpleNamespace(tenant_id="empresa-a", usuario="persona-a"), "222", propuesta(), CONFIRMADO,
            repositorio=base.RepositorioMemoria(), lector=base.LectorFalso(
                {"222": {f["chunk_id"]: f for f in (base.FUNDAMENTAL, base.NO_FUNDAMENTAL, base.FECHA_BASES)}}))
        from licigt.consulta.lista import CambioLista
        cambios = [CambioLista(item_id=i.item_id, accion="alta", estado_anterior=None, estado_nuevo="pendiente",
                               usuario="persona-a", momento=AHORA) for i in guardados]
        conn = ConexionFalsa()
        self.repo(conn).insertar("empresa-a", guardados, cambios)
        self.assert_sesion_por_empresa(conn, "empresa-a")
        inserciones = [s for s in conn.sentencias[2:]]
        self.assertEqual(len(inserciones), 6)
        self.assertTrue(all(s[0].lstrip().startswith("INSERT INTO") and "%s" in s[0] for s in inserciones))
        self.assertTrue(all(s[1][0] == "empresa-a" for s in inserciones))

    def test_insertar_repetido_es_value_error_y_revierte(self):
        item = item_guardado()
        conn = ConexionFalsa(falla=lambda sql: ViolacionUnica("dup") if "INSERT" in sql else None)
        with self.assertRaises(ValueError):
            self.repo(conn).insertar("empresa-a", [item], [])
        self.assertEqual(conn.eventos[-1], ("ROLLBACK",))
        self.assertTrue(conn.cerrada)

    def test_actualizar_estado_es_un_update_condicionado_y_registra_el_cambio(self):
        nuevo = item_guardado("preparado")
        conn = ConexionFalsa(lambda sql: [fila(nuevo)] if sql.lstrip().startswith("UPDATE") else [])
        resultado = self.repo(conn).actualizar_estado("empresa-a", "i1", "pendiente", "preparado", "persona-a", AHORA)
        self.assertEqual(resultado, nuevo)
        self.assert_sesion_por_empresa(conn, "empresa-a")
        update, cambio = conn.sentencias[2], conn.sentencias[3]
        self.assertTrue(update[0].lstrip().startswith("UPDATE lista_items"))
        for condicion in ("tenant_id = %s", "item_id = %s", "estado = %s", "RETURNING"):
            self.assertIn(condicion, update[0])
        self.assertIn("pendiente", update[1])
        self.assertIn("INSERT INTO lista_cambios", cambio[0])
        self.assertEqual(cambio[1][0], "empresa-a")

    def test_estado_desactualizado_devuelve_none_sin_registrar_cambio(self):
        conn = ConexionFalsa()  # el UPDATE no devuelve filas
        self.assertIsNone(self.repo(conn).actualizar_estado("empresa-a", "i1", "pendiente", "revisado", "u", AHORA))
        self.assertEqual(len(conn.sentencias), 3)
        self.assertFalse(any("lista_cambios" in s[0] for s in conn.sentencias))

    def test_cambiar_estado_traduce_none_a_estado_desactualizado(self):
        class Repo(RepositorioPostgres):
            def obtener(self, tenant_id, item_id):
                return item_guardado()
        conn = ConexionFalsa()
        with self.assertRaises(FallaLista) as falla:
            cambiar_estado(SimpleNamespace(tenant_id="empresa-a", usuario="u"), "i1", "pendiente", "revisado",
                           CONFIRMADO, repositorio=Repo(lambda: conn))
        self.assertEqual(falla.exception.codigo, "estado_desactualizado")

    def test_lector_delega_en_obtener_fragmentos_del_rol_2(self):
        from unittest.mock import patch
        conn = ConexionFalsa()
        llamadas = []

        def falso(ctx, evento_id, chunk_ids, conn=None):
            llamadas.append((ctx.tenant_id, evento_id, list(chunk_ids), conn))
            return [{"chunk_id": "c1", "doc_id": "d1", "tipo_documento": "bases", "version_ingesta": 1,
                     "pagina_inicio": 2, "pagina_fin": 2, "seccion": "S", "texto": "t", "url_origen": "http://x",
                     "identificador_version_oficial": "v1", "pagina_impresa": 1, "score": 0.0}]
        lector = LectorFragmentosPostgres(lambda: conn)
        ctx = SimpleNamespace(tenant_id="empresa-a", usuario="persona-a")
        with patch("licigt.recuperacion.busqueda.obtener_fragmentos", falso):
            resultado = lector.obtener(ctx, "222", ["c1", "c2"])
            self.assertEqual(lector.obtener(ctx, "222", []), {})
        self.assertEqual(llamadas, [("empresa-a", "222", ["c1", "c2"], conn)])
        self.assertEqual(list(resultado), ["c1"])
        self.assertEqual((resultado["c1"].pagina_inicio, resultado["c1"].pagina_impresa), (2, 1))
        self.assertTrue(conn.cerrada)
        self.assertEqual(conn.sentencias, [])  # sin SQL propio


@unittest.skipUnless(DB_URL, "Sin LICIGT_DB_URL: pruebas de integración de la lista en Postgres omitidas (levanta la base con make db-up)")
class IntegracionTests(base.EscrituraTests):
    """Las mismas pruebas de contrato que RepositorioMemoria, contra Postgres."""

    @classmethod
    def setUpClass(cls):
        try:
            with psycopg.connect(DB_URL, autocommit=True, connect_timeout=3) as conn:
                conn.execute((CARPETA / "lista_schema.sql").read_text(encoding="utf-8"))
        except psycopg.Error as e:
            raise unittest.SkipTest(f"La base no responde o falta el esquema del rol 2: {type(e).__name__}")

    def setUp(self):
        super().setUp()
        self.limpiar()
        self.repo = RepositorioPostgres(lambda: psycopg.connect(DB_URL, autocommit=True))
        self.addCleanup(self.limpiar)

    @staticmethod
    def limpiar():
        with psycopg.connect(DB_URL, autocommit=True) as conn:
            conn.execute("DELETE FROM lista_cambios WHERE tenant_id LIKE 'empresa-%'")
            conn.execute("DELETE FROM lista_items WHERE tenant_id LIKE 'empresa-%'")

    def test_otra_empresa_no_ve_los_items_aunque_se_salte_el_filtro_de_la_aplicacion(self):
        self.guardar()
        with psycopg.connect(DB_URL, autocommit=True) as conn, conn.transaction():
            conn.execute("SET LOCAL ROLE licigt_app")
            conn.execute("SELECT set_config('app.tenant_id', %s, true)", ("empresa-b",))
            for tabla in ("lista_items", "lista_cambios"):
                self.assertEqual(conn.execute(f"SELECT count(*) FROM {tabla}").fetchone()[0], 0)
            conn.execute("SELECT set_config('app.tenant_id', %s, true)", ("empresa-a",))
            self.assertEqual(conn.execute("SELECT count(*) FROM lista_items").fetchone()[0], 3)

    def test_sin_empresa_fijada_la_politica_no_devuelve_filas(self):
        self.guardar()
        with psycopg.connect(DB_URL, autocommit=True) as conn, conn.transaction():
            conn.execute("SET LOCAL ROLE licigt_app")
            self.assertEqual(conn.execute("SELECT count(*) FROM lista_items").fetchone()[0], 0)

    def test_concurrencia_solo_un_cambio_gana(self):
        item = self.guardar()[0]
        barrera, resultados = threading.Barrier(2), []

        def cambiar(nuevo, usuario):
            barrera.wait()
            resultados.append(self.repo.actualizar_estado("empresa-a", item.item_id, "pendiente", nuevo, usuario,
                                                          AHORA))

        hilos = [threading.Thread(target=cambiar, args=a) for a in (("preparado", "u1"), ("revisado", "u2"))]
        [h.start() for h in hilos]
        [h.join() for h in hilos]
        self.assertEqual(sum(r is not None for r in resultados), 1)
        cambios = [c for c in self.repo.cambios("empresa-a", "222") if c.accion == "estado"]
        self.assertEqual(len(cambios), 1)
        self.assertEqual(self.repo.obtener("empresa-a", item.item_id).estado, cambios[0].estado_nuevo)

    def test_lector_no_devuelve_chunks_de_otro_evento_ni_de_otra_empresa(self):
        with psycopg.connect(DB_URL, autocommit=True) as conn:
            hay = conn.execute("SELECT to_regclass('fragmentos')").fetchone()[0]
            if hay is None:
                self.skipTest("Falta la tabla fragmentos del rol 2")
            conn.execute("DELETE FROM fragmentos WHERE tenant_id LIKE 'empresa-%'")
            conn.execute("DELETE FROM documentos WHERE tenant_id LIKE 'empresa-%'")
            conn.execute("""INSERT INTO documentos VALUES ('doc-a', 'empresa-a', '222', 'n', 'bases', 1, NULL,
                            'ok', '{}', '{}')""")
            conn.execute("""INSERT INTO fragmentos (chunk_id, variante, doc_id, tenant_id, evento_id, numero_evento,
                            tipo_documento, version_ingesta, pagina_inicio, pagina_fin, texto, url_origen, meta)
                            VALUES ('chunk-sql', 'base', 'doc-a', 'empresa-a', '222', 'n', 'bases', 1, 1, 1, 't',
                            'u', '{}')""")
        self.addCleanup(lambda: self._borrar_fragmentos())
        lector = LectorFragmentosPostgres(lambda: psycopg.connect(DB_URL, autocommit=True))
        self.assertEqual(list(lector.obtener(self.ctx, "222", ["chunk-sql"])), ["chunk-sql"])
        self.assertEqual(lector.obtener(self.ctx, "otro-evento", ["chunk-sql"]), {})
        self.assertEqual(lector.obtener(self.otra, "222", ["chunk-sql"]), {})

    @staticmethod
    def _borrar_fragmentos():
        with psycopg.connect(DB_URL, autocommit=True) as conn:
            conn.execute("DELETE FROM fragmentos WHERE tenant_id LIKE 'empresa-%'")
            conn.execute("DELETE FROM documentos WHERE tenant_id LIKE 'empresa-%'")


if __name__ == "__main__":
    unittest.main()
