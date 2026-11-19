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


class PresupuestoTiempoTests(unittest.TestCase):
    def test_sin_limite_de_tiempo_siempre_cabe(self):
        self.assertTrue(Presupuesto().cabe_generacion(1e9))

    def test_cabe_si_gastado_mas_estimado_no_supera_el_limite(self):
        t = [0.0]
        presupuesto = Presupuesto(max_segundos=15, reloj=lambda: t[0])
        t[0] = 6
        self.assertTrue(presupuesto.cabe_generacion(9))
        self.assertFalse(presupuesto.cabe_generacion(9.1))
        t[0] = 15
        self.assertFalse(presupuesto.cabe_generacion(0.1))

    def test_limite_invalido(self):
        for malo in (0, -1, float("nan")):
            with self.subTest(malo=malo), self.assertRaises(ValueError):
                Presupuesto(max_segundos=malo)
