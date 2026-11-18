"""evaluar.py con la conexión de la aplicación: toda lectura de documentos exige la sesión por empresa."""

import contextlib
import unittest
from unittest import mock

from licigt.recuperacion import evaluar
from licigt.recuperacion.busqueda import Contexto


class ConexionConRLS:
    """Doble de conexión: documentos solo devuelve filas dentro de una transacción con rol y empresa activos."""

    def __init__(self):
        self.en_transaccion, self.rol, self.tenant = False, False, None

    @contextlib.contextmanager
    def transaction(self):
        self.en_transaccion = True
        try:
            yield
        finally:
            self.en_transaccion, self.rol, self.tenant = False, False, None

    def execute(self, sql, params=()):
        if sql.startswith("SET LOCAL ROLE"):
            self.rol = True
        elif "set_config('app.tenant_id'" in sql:
            self.tenant = params[0]
        if "FROM documentos" in sql:
            filas = [("222-IGSS-2023", "ev-222")] if self.en_transaccion and self.rol and self.tenant else []
            return mock.Mock(fetchall=lambda: filas, fetchone=lambda: filas[0] if filas else None)
        return mock.Mock(fetchall=list, fetchone=lambda: None)


class SesionTests(unittest.TestCase):
    def test_evaluar_lee_eventos_con_la_sesion_de_la_empresa(self):
        frag = {"tipo_documento": "bases", "pagina_inicio": 1, "pagina_fin": 1, "score": 0.9}
        respuesta = {"suficiente": True, "fragmentos": [frag], "alertas": []}
        casos = [{"id": "a", "evento": "222-IGSS-2023", "pregunta": "q", "relevantes": []},
                 {"id": "b", "evento": "222-IGSS-2023", "pregunta": "q",
                  "relevantes": [{"tipo_documento": "bases", "paginas": [1]}]}]
        with mock.patch.object(evaluar, "buscar", return_value=respuesta) as buscar:
            resumen, _ = evaluar.evaluar(casos, Contexto("empresa_demo"), ConexionConRLS())
        self.assertEqual(resumen["base"]["hit@5"], 1.0)
        self.assertEqual(buscar.call_args.args[1], "ev-222")

    def test_leer_como_devuelve_filas_solo_con_sesion(self):
        conn = ConexionConRLS()
        self.assertEqual(conn.execute("SELECT 1 FROM documentos").fetchall(), [])
        filas = evaluar.leer_como(conn, Contexto("empresa_demo"), "SELECT 1 FROM documentos")
        self.assertEqual(filas, [("222-IGSS-2023", "ev-222")])


class CliBuscarTests(unittest.TestCase):
    def test_buscar_resuelve_el_evento_con_la_sesion_de_la_empresa(self):
        import contextlib as cl, io, runpy, sys
        conn = ConexionConRLS()
        conn_execute = conn.execute

        def execute(sql, params=()):
            r = conn_execute(sql, params)
            if "SELECT evento_id FROM documentos" in sql and conn.en_transaccion and conn.rol and conn.tenant:
                return mock.Mock(fetchone=lambda: ("ev-222",))
            return r
        conn.execute = execute
        salida = io.StringIO()
        with mock.patch("licigt.recuperacion.indice.conectar", return_value=conn), \
                mock.patch("licigt.recuperacion.busqueda.buscar", return_value={"fragmentos": []}) as buscar, \
                mock.patch.object(sys, "argv", ["x", "buscar", "--evento", "222-IGSS-2023", "q"]), \
                cl.redirect_stdout(salida):
            runpy.run_module("licigt.recuperacion", run_name="__main__")
        self.assertEqual(buscar.call_args.args[1], "ev-222")


if __name__ == "__main__":
    unittest.main()
