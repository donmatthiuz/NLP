"""make usuarios-demo: crea una vez, con permisos 600, sin imprimir las contraseñas."""

import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from licigt.plataforma import usuarios, usuarios_demo


class UsuariosDemoTests(unittest.TestCase):
    def setUp(self):
        self.temporal = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporal.cleanup)
        d = Path(self.temporal.name) / "plataforma"
        self.rutas = {"LICIGT_SESION_CLAVE_ARCHIVO": str(d / "sesion.key"),
                      "LICIGT_USUARIOS_ARCHIVO": str(d / "usuarios.json"),
                      "LICIGT_CONTRASENAS_DEMO_ARCHIVO": str(d / "contrasenas_demo.txt")}
        entorno = patch.dict(os.environ, self.rutas)
        entorno.start()
        self.addCleanup(entorno.stop)

    def test_crea_todo_con_permisos_privados_y_sin_imprimir_contrasenas(self):
        informe = "\n".join(usuarios_demo.crear())
        contrasenas = dict(l.split("\t") for l in Path(self.rutas["LICIGT_CONTRASENAS_DEMO_ARCHIVO"]).read_text().splitlines())
        self.assertEqual(set(contrasenas), {"analista_demo", "lector_demo", "analista_b"})
        for clave in self.rutas.values():
            self.assertEqual(stat.S_IMODE(os.stat(clave).st_mode), 0o600)
        for c in contrasenas.values():
            self.assertNotIn(c, informe)
            self.assertNotIn(c, Path(self.rutas["LICIGT_USUARIOS_ARCHIVO"]).read_text())
        u = usuarios.autenticar("analista_b", contrasenas["analista_b"])
        self.assertEqual((u.tenant_id, u.rol), ("empresa_b", "analista"))
        self.assertEqual(usuarios.autenticar("lector_demo", contrasenas["lector_demo"]).rol, "lector")

    def test_forzar_regenera_usuarios_y_contrasenas_sin_imprimirlas(self):
        usuarios_demo.crear()
        antes = Path(self.rutas["LICIGT_CONTRASENAS_DEMO_ARCHIVO"]).read_text()
        clave = Path(self.rutas["LICIGT_SESION_CLAVE_ARCHIVO"]).read_bytes()
        informe = "\n".join(usuarios_demo.crear(forzar=True))
        despues = Path(self.rutas["LICIGT_CONTRASENAS_DEMO_ARCHIVO"]).read_text()
        self.assertNotEqual(antes, despues)
        self.assertEqual(clave, Path(self.rutas["LICIGT_SESION_CLAVE_ARCHIVO"]).read_bytes())
        for linea in despues.splitlines():
            usuario, contrasena = linea.split("\t")
            self.assertNotIn(contrasena, informe)
            self.assertTrue(usuarios.autenticar(usuario, contrasena))
        self.assertIn("creado", informe)
        for ruta in self.rutas.values():
            self.assertEqual(stat.S_IMODE(os.stat(ruta).st_mode), 0o600)

    def test_no_pisa_lo_que_ya_existe(self):
        usuarios_demo.crear()
        antes = {k: Path(v).read_bytes() for k, v in self.rutas.items()}
        informe = usuarios_demo.crear()
        self.assertEqual(antes, {k: Path(v).read_bytes() for k, v in self.rutas.items()})
        self.assertTrue(all(l.startswith("existe") for l in informe))


if __name__ == "__main__":
    unittest.main()
