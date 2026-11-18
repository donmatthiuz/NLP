"""El rol de conexión de la aplicación no salta la seguridad por fila.
Requiere make db-up, db-rol-app, lista-schema, importar y empresa-b (make test-plataforma)."""

import os
import unittest

DB_URL = os.environ.get("LICIGT_DB_URL")
BAJO_MAKE = bool(os.environ.get("LICIGT_DB_ADMIN_URL"))  # lo pone make test-plataforma con la base arriba
try:
    import psycopg
except ImportError:
    psycopg = None


@unittest.skipUnless(DB_URL and psycopg, "requiere LICIGT_DB_URL (make test-plataforma) y psycopg")
class RolDeConexionTests(unittest.TestCase):
    def setUp(self):
        try:
            self.conn = psycopg.connect(DB_URL, autocommit=True, connect_timeout=3)
        except psycopg.Error as e:
            if BAJO_MAKE:  # bajo make la base y el rol deben existir: un fallo aquí no se omite
                self.fail(f"No conecta como licigt_api ({type(e).__name__}): corre make db-up y make db-rol-app")
            self.skipTest(f"La base no responde: {type(e).__name__}")
        self.addCleanup(self.conn.close)
        super_, bypass = self.conn.execute(
            "SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user").fetchone()
        if super_ or bypass:
            self.skipTest("La conexión es de administrador; esta prueba corre con el rol de la aplicación (make test-plataforma)")

    def test_ni_licigt_api_ni_licigt_app_son_superusuario_ni_saltan_la_rls(self):
        filas = self.conn.execute("SELECT rolname, rolsuper, rolbypassrls, rolcanlogin FROM pg_roles "
                                  "WHERE rolname IN ('licigt_api', 'licigt_app') ORDER BY rolname").fetchall()
        self.assertEqual(filas, [("licigt_api", False, False, True), ("licigt_app", False, False, False)])
        self.assertEqual(self.conn.execute("SELECT current_user").fetchone()[0], "licigt_api")

    def test_sin_tenant_en_la_sesion_no_hay_filas_de_ninguna_empresa(self):
        for tabla in ("fragmentos", "documentos", "lista_items", "lista_cambios"):
            n = self.conn.execute(f"SELECT count(*) FROM {tabla}").fetchone()[0]
            self.assertEqual(n, 0, tabla)

    def test_con_tenant_propio_si_hay_filas_y_ninguna_ajena(self):
        with self.conn.transaction():
            self.conn.execute("SET LOCAL ROLE licigt_app")
            self.conn.execute("SELECT set_config('app.tenant_id', 'empresa_b', true)")
            propias = self.conn.execute("SELECT count(*) FROM fragmentos WHERE tenant_id = 'empresa_b'").fetchone()[0]
            ajenas = self.conn.execute("SELECT count(*) FROM fragmentos WHERE tenant_id <> 'empresa_b'").fetchone()[0]
        self.assertGreater(propias, 0, "control positivo: empresa_b debe ver sus filas (make empresa-b)")
        self.assertEqual(ajenas, 0)

    def test_el_rol_no_puede_modificar_el_corpus_ni_el_esquema(self):
        for sql in ("DELETE FROM documentos", "TRUNCATE fragmentos", "CREATE TABLE public.x (a int)",
                    "INSERT INTO documentos (doc_id) VALUES ('x')"):
            with self.subTest(sql=sql), self.assertRaises(psycopg.errors.InsufficientPrivilege):
                self.conn.execute(sql)


if __name__ == "__main__":
    unittest.main()
