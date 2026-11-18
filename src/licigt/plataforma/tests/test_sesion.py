"""Cookie de sesión firmada con HMAC: emisión, verificación, alteración y vencimiento."""

import base64
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from licigt.plataforma import sesion

CLAVE = b"k" * 64


class SesionTests(unittest.TestCase):
    def test_ida_y_vuelta(self):
        valor = sesion.emitir(CLAVE, "ana", "empresa_demo", "analista", horas=1, ahora=1000)
        s = sesion.verificar(valor, CLAVE, ahora=1001)
        self.assertEqual((s.usuario, s.tenant_id, s.rol), ("ana", "empresa_demo", "analista"))

    def test_vencida(self):
        valor = sesion.emitir(CLAVE, "ana", "t", "lector", horas=1, ahora=1000)
        self.assertIsNotNone(sesion.verificar(valor, CLAVE, ahora=1000 + 3599))
        self.assertIsNone(sesion.verificar(valor, CLAVE, ahora=1000 + 3600))

    def test_clave_distinta(self):
        valor = sesion.emitir(CLAVE, "ana", "t", "lector", horas=1, ahora=1000)
        self.assertIsNone(sesion.verificar(valor, b"z" * 64, ahora=1001))

    def test_carga_alterada_no_verifica(self):
        valor = sesion.emitir(CLAVE, "ana", "empresa_demo", "lector", horas=1, ahora=1000)
        carga, firma = valor.split(".")
        datos = json.loads(base64.urlsafe_b64decode(carga + "=" * (-len(carga) % 4)))
        for campo, nuevo in (("t", "empresa_b"), ("r", "analista"), ("u", "otro")):
            with self.subTest(campo=campo):
                falsa = base64.urlsafe_b64encode(json.dumps({**datos, campo: nuevo}).encode()).rstrip(b"=").decode()
                self.assertIsNone(sesion.verificar(f"{falsa}.{firma}", CLAVE, ahora=1001))

    def test_firma_alterada_o_basura(self):
        valor = sesion.emitir(CLAVE, "ana", "t", "lector", horas=1, ahora=1000)
        for malo in (valor[:-2] + "AA", valor + "x", "", "sin-punto", "a.b.c", ".", None, "é.é"):
            with self.subTest(malo=malo):
                self.assertIsNone(sesion.verificar(malo, CLAVE, ahora=1001))

    def test_rol_invalido_no_se_emite(self):
        with self.assertRaises(ValueError):
            sesion.emitir(CLAVE, "ana", "t", "admin", horas=1)

    def test_clave_desde_archivo(self):
        with tempfile.TemporaryDirectory() as d:
            ruta = Path(d) / "sesion.key"
            with patch.dict(os.environ, {"LICIGT_SESION_CLAVE_ARCHIVO": str(ruta)}):
                with self.assertRaises(sesion.SesionNoConfigurada):
                    sesion.leer_clave()
                ruta.write_text("corta")
                with self.assertRaises(sesion.SesionNoConfigurada):
                    sesion.leer_clave()
                ruta.write_text("k" * 64 + "\n")
                self.assertEqual(sesion.leer_clave(), b"k" * 64)


if __name__ == "__main__":
    unittest.main()
