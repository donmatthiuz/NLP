"""Vista previa y registro del sondeo con un cliente falso."""

import contextlib
import io
import json
import tempfile
import unittest
from collections import Counter
from pathlib import Path
from unittest.mock import patch

from licigt.consulta.sondeo_jev import cargar_casos, ejecutar_sondeo, main
from licigt.consulta.preguntas_jev import VERSION_PREGUNTAS
from test_enrutador import JevFalso


class SondeoTests(unittest.TestCase):
    def test_casos_y_vista_previa_sin_cliente(self):
        casos = cargar_casos()
        self.assertEqual(Counter(c["grupo"] for c in casos),
                         {"desarrollo": 27, "inyeccion": 5, "prohibido": 5,
                          "ambiguo": 5, "comparacion": 5})
        salida = io.StringIO()
        with patch("licigt.consulta.sondeo_jev.ClienteJevSdk") as cliente:
            with contextlib.redirect_stdout(salida):
                main([])
            cliente.assert_not_called()
        self.assertIn("Sin envío", salida.getvalue())
        self.assertIn(casos[0]["pregunta"], salida.getvalue())

    def test_registro_exacto_con_doble(self):
        cliente = JevFalso()
        original = {"model": "jev-1.14.0", "answers": cliente.respuesta.respuestas,
                    "usage": {"input_tokens": 100, "output_tokens": 20}, "campo_futuro": "conservar"}
        cliente.respuesta = cliente.respuesta.model_copy(update={"original": original})
        casos = [{"id": "prueba", "grupo": "desarrollo", "pregunta": "¿Cuál es el código?"}]
        with tempfile.TemporaryDirectory() as carpeta, contextlib.redirect_stdout(io.StringIO()):
            ruta = ejecutar_sondeo(cliente, casos, Path(carpeta), "jev-1.14.0")
            registros = json.loads(ruta.read_text())
        self.assertEqual(registros[0]["payload"]["state"], cliente.llamadas[0][0])
        self.assertEqual(registros[0]["payload"]["questions"], cliente.llamadas[0][1])
        self.assertEqual(registros[0]["respuesta"]["modelo"], "jev-1.14.0")
        self.assertEqual(registros[0]["respuesta"]["tokens_entrada"], 100)
        self.assertEqual(registros[0]["respuesta"]["original"], original)
        self.assertEqual(registros[0]["jev"]["accion"], "usar_herramienta")
        self.assertEqual(registros[0]["version_preguntas"], VERSION_PREGUNTAS)
        self.assertIn("contexto", registros[0]["payload"]["state"])
