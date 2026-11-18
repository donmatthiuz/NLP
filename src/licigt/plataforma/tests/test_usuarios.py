"""Hash de contraseñas con scrypt y carga de usuarios."""

import contextlib
import json
import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from licigt.plataforma import usuarios


def registro(contrasena, n=None, p=None, rol="analista"):
    """Entrada de usuarios.json; n y p permiten fabricar un hash con parámetros anteriores."""
    if n is None:
        almacenado = usuarios.hash_contrasena(contrasena)
    else:
        import base64, hashlib
        sal = b"s" * 16
        derivado = hashlib.scrypt(contrasena.encode(), salt=sal, n=n, r=8, p=p, maxmem=512 * 1024 * 1024, dklen=32)
        almacenado = "scrypt$%d$8$%d$%s$%s" % (n, p, base64.b64encode(sal).decode(), base64.b64encode(derivado).decode())
    return {"hash": almacenado, "tenant_id": "empresa_demo", "rol": rol}


@contextlib.contextmanager
def archivo_de_usuarios(contenido, crudo=False):
    with tempfile.TemporaryDirectory() as d:
        ruta = Path(d) / "usuarios.json"
        ruta.write_text(json.dumps({"usuarios": contenido}))
        os.chmod(ruta, 0o600)
        with patch.dict(os.environ, {"LICIGT_USUARIOS_ARCHIVO": str(ruta)}):
            yield ruta


class UsuariosTests(unittest.TestCase):
    def test_hash_y_verificacion(self):
        almacenado = usuarios.hash_contrasena("una clave")
        self.assertTrue(almacenado.startswith("scrypt$"))
        self.assertNotIn("una clave", almacenado)
        self.assertTrue(usuarios.verificar_contrasena("una clave", almacenado))
        self.assertFalse(usuarios.verificar_contrasena("otra", almacenado))

    def test_parametros_actuales_n_2_14_r_8_p_5(self):
        self.assertTrue(usuarios.hash_contrasena("x").startswith("scrypt$16384$8$5$"))

    def test_existente_e_inexistente_derivan_con_los_mismos_parametros(self):
        llamadas = []
        real = usuarios._derivar

        def espia(contrasena, sal, n, r, p):
            llamadas.append((n, r, p))
            return real(contrasena, sal, n, r, p)

        with archivo_de_usuarios({"ana": registro("secreta")}):
            with patch.object(usuarios, "_derivar", espia):
                self.assertIsNone(usuarios.autenticar("ana", "mala"))
                self.assertIsNone(usuarios.autenticar("nadie", "mala"))
        self.assertEqual(llamadas, [(2**14, 8, 5)] * 2)

    def test_nunca_hay_mas_de_dos_derivaciones_a_la_vez(self):
        import threading, time
        from concurrent.futures import ThreadPoolExecutor
        real, cerrojo, activas, maximo = usuarios._derivar, threading.Lock(), [0], [0]

        def espia(*a):
            with cerrojo:
                activas[0] += 1
                maximo[0] = max(maximo[0], activas[0])
            time.sleep(0.01)
            try:
                return real(*a)
            finally:
                with cerrojo:
                    activas[0] -= 1

        with archivo_de_usuarios({"ana": registro("secreta")}):
            with patch.object(usuarios, "_derivar", espia), ThreadPoolExecutor(max_workers=40) as pool:
                resultados = list(pool.map(lambda i: usuarios.autenticar("ana", "secreta" if i % 2 else "mala"),
                                           range(40)))
        self.assertEqual(sum(r is not None for r in resultados), 20)
        self.assertEqual(maximo[0], 2)

    def test_hash_viejo_verifica_y_se_reescribe_con_los_parametros_actuales(self):
        for n, p in ((2**17, 1), (2**14, 1)):
            with self.subTest(n=n, p=p):
                otro = registro("otra", rol="lector")
                with archivo_de_usuarios({"ana": registro("secreta", n=n, p=p), "bea": otro}) as ruta:
                    self.assertTrue(usuarios.autenticar("ana", "secreta"))
                    datos = json.loads(ruta.read_text())["usuarios"]
                    self.assertTrue(datos["ana"]["hash"].startswith("scrypt$16384$8$5$"))
                    self.assertEqual(datos["bea"], otro)
                    self.assertEqual((datos["ana"]["tenant_id"], datos["ana"]["rol"]), ("empresa_demo", "analista"))
                    self.assertEqual(stat.S_IMODE(os.stat(ruta).st_mode), 0o600)
                    self.assertEqual(os.listdir(ruta.parent), [ruta.name])
                    self.assertTrue(usuarios.autenticar("ana", "secreta"))
                    self.assertIsNone(usuarios.autenticar("ana", "mala"))

    def test_contrasena_mala_no_reescribe_el_hash_viejo(self):
        with archivo_de_usuarios({"ana": registro("secreta", n=2**14, p=1)}) as ruta:
            antes = ruta.read_text()
            self.assertIsNone(usuarios.autenticar("ana", "mala"))
            self.assertEqual(ruta.read_text(), antes)

    def test_usuarios_que_no_es_un_dict_no_deja_entrar_ni_lanza(self):
        for malo in ([], "x", 3, None):
            with self.subTest(malo=malo), archivo_de_usuarios(malo, crudo=True):
                self.assertEqual(usuarios.cargar(), {})
                self.assertIsNone(usuarios.autenticar("ana", "x"))

    def test_la_sal_es_distinta_en_cada_hash(self):
        self.assertNotEqual(usuarios.hash_contrasena("x"), usuarios.hash_contrasena("x"))

    def test_hash_mal_formado_no_verifica_ni_lanza(self):
        for malo in ("", "scrypt$1$2", "md5$a$b$c$d$e", "scrypt$x$8$1$AA$AA", None):
            with self.subTest(malo=malo):
                self.assertFalse(usuarios.verificar_contrasena("x", malo))

    def test_contrasena_demasiado_larga_no_verifica(self):
        almacenado = usuarios.hash_contrasena("x")
        self.assertFalse(usuarios.verificar_contrasena("x" * 5000, almacenado))

    def test_autenticar(self):
        with tempfile.TemporaryDirectory() as d:
            ruta = Path(d) / "usuarios.json"
            ruta.write_text(json.dumps({"usuarios": {"ana": {
                "hash": usuarios.hash_contrasena("secreta"), "tenant_id": "empresa_demo", "rol": "analista"}}}))
            with patch.dict(os.environ, {"LICIGT_USUARIOS_ARCHIVO": str(ruta)}):
                u = usuarios.autenticar("ana", "secreta")
                self.assertEqual((u.usuario, u.tenant_id, u.rol), ("ana", "empresa_demo", "analista"))
                self.assertIsNone(usuarios.autenticar("ana", "mala"))
                self.assertIsNone(usuarios.autenticar("nadie", "secreta"))

    def test_sin_archivo_de_usuarios_nadie_entra(self):
        with patch.dict(os.environ, {"LICIGT_USUARIOS_ARCHIVO": "/no/existe.json"}):
            self.assertIsNone(usuarios.autenticar("ana", "x"))

    def test_rol_desconocido_en_el_archivo_no_entra(self):
        with tempfile.TemporaryDirectory() as d:
            ruta = Path(d) / "u.json"
            ruta.write_text(json.dumps({"usuarios": {"ana": {
                "hash": usuarios.hash_contrasena("s"), "tenant_id": "t", "rol": "admin"}}}))
            with patch.dict(os.environ, {"LICIGT_USUARIOS_ARCHIVO": str(ruta)}):
                self.assertIsNone(usuarios.autenticar("ana", "s"))


if __name__ == "__main__":
    unittest.main()
