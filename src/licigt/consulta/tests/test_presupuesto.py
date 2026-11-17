"""Presupuesto independiente por solicitud."""

import unittest

from licigt.consulta.presupuesto import LimiteAgotado, Presupuesto


class PresupuestoTests(unittest.TestCase):
    def test_limites_independientes(self):
        presupuesto = Presupuesto()
        for _ in range(3):
            presupuesto.usar_llamada()
        for _ in range(2):
            with self.assertRaises(LimiteAgotado) as error:
                presupuesto.usar_llamada()
            self.assertEqual(error.exception.tipo, "llamadas")
        presupuesto.usar_regeneracion()
        with self.assertRaises(LimiteAgotado) as error:
            presupuesto.usar_regeneracion()
        self.assertEqual(error.exception.tipo, "regeneraciones")
        Presupuesto().usar_llamada()

    def test_limites_configurables(self):
        presupuesto = Presupuesto(max_llamadas=0, max_regeneraciones=0)
        with self.assertRaises(LimiteAgotado):
            presupuesto.usar_llamada()
        with self.assertRaises(LimiteAgotado):
            presupuesto.usar_regeneracion()
        for cambios in ({"max_llamadas": -1}, {"max_regeneraciones": True}):
            with self.subTest(cambios=cambios), self.assertRaises(ValueError):
                Presupuesto(**cambios)
